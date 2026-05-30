import asyncio
import collections
import logging
from prometheus_client import start_http_server, Counter, Gauge
from .resp import RESPDecoder, encode_simple_string, encode_error, encode_bulk_string, encode_integer, encode_array
from .cache import LRUCache
from .aof import AOF

logger = logging.getLogger(__name__)

# --- Telemetry Metrics ---
PROMETHEUS_PORT = 8000
TOTAL_COMMANDS = Counter('essacache_commands_total', 'Total commands processed')
ACTIVE_CONNECTIONS = Gauge('essacache_active_connections', 'Current active client connections')
CACHE_SIZE = Gauge('essacache_keys_total', 'Total number of keys in memory')
CACHE_HITS = Counter('essacache_cache_hits_total', 'Total cache hits')
CACHE_MISSES = Counter('essacache_cache_misses_total', 'Total cache misses')

logger = logging.getLogger(__name__)

class EssaCacheServer:
    def __init__(self, host='127.0.0.1', port=6379, capacity=10000, aof_path="essacache.aof", rdb_path="essacache.rdb"):
        self.host = host
        self.port = port
        self.cache = LRUCache(capacity=capacity)
        self.aof = AOF(filepath=aof_path)
        self.rdb_path = rdb_path
        self._active_expiration_task = None
        self.pubsub_channels = collections.defaultdict(set)
        
    async def start(self):
        logger.info(f"Starting Prometheus telemetry server on port {PROMETHEUS_PORT}...")
        try:
            start_http_server(PROMETHEUS_PORT)
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")

        logger.info("Loading RDB snapshot if exists...")
        self.cache.load_snapshot(self.rdb_path)
        self._recover_from_aof()
        await self.aof.start()
        
        self._active_expiration_task = asyncio.create_task(self._active_expiration_loop())
        
        server = await asyncio.start_server(self.handle_connection, self.host, self.port)
        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        logger.info(f"Serving on {addrs}")

        async with server:
            await server.serve_forever()
            
    async def stop(self):
        if self._active_expiration_task:
            self._active_expiration_task.cancel()
        await self.aof.stop()

    async def _active_expiration_loop(self):
        """
        Runs 10 times per second. Samples 20 random keys with expirations.
        If more than 25% of them were expired, it repeats the process immediately.
        This ensures memory is cleaned up efficiently.
        """
        try:
            while True:
                await asyncio.sleep(0.1)
                while True:
                    expired_count = self.cache.sample_and_evict_expired(sample_size=20)
                    if expired_count <= 5:  # <= 25% of 20
                        break
        except asyncio.CancelledError:
            pass

    def _recover_from_aof(self):
        data = self.aof.get_file_content()
        if not data:
            return
            
        logger.info("Recovering from AOF...")
        decoder = RESPDecoder()
        cmds = decoder.decode(data)
        for cmd in cmds:
            if isinstance(cmd, list):
                self._execute_command_internal(cmd)
        logger.info("AOF Recovery complete.")
                
    async def handle_connection(self, reader, writer):
        ACTIVE_CONNECTIONS.inc()
        addr = writer.get_extra_info('peername')
        logger.debug(f"Connected: {addr}")
        decoder = RESPDecoder()
        subscribed_channels = set()
        transaction_queue = None

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                    
                cmds = decoder.decode(data)
                for cmd in cmds:
                    if isinstance(cmd, list):
                        cmd_name = str(cmd[0].decode('utf-8', errors='ignore')).upper() if isinstance(cmd[0], bytes) else str(cmd[0]).upper()

                        if cmd_name == 'MULTI':
                            if transaction_queue is not None:
                                writer.write(encode_error("ERR MULTI calls can not be nested"))
                            else:
                                transaction_queue = []
                                writer.write(encode_simple_string("OK"))
                            await writer.drain()
                            continue

                        elif cmd_name == 'EXEC':
                            if transaction_queue is None:
                                writer.write(encode_error("ERR EXEC without MULTI"))
                                await writer.drain()
                                continue
                            
                            responses = []
                            for queued_cmd in transaction_queue:
                                response_bytes, is_write = self._execute_command(queued_cmd)
                                if is_write:
                                    await self.aof.append(encode_array(queued_cmd))
                                responses.append(response_bytes)
                            
                            transaction_queue = None
                            array_header = f"*{len(responses)}\r\n".encode()
                            writer.write(array_header + b"".join(responses))
                            await writer.drain()
                            continue

                        elif cmd_name == 'DISCARD':
                            if transaction_queue is None:
                                writer.write(encode_error("ERR DISCARD without MULTI"))
                            else:
                                transaction_queue = None
                                writer.write(encode_simple_string("OK"))
                            await writer.drain()
                            continue

                        if transaction_queue is not None and cmd_name not in ['QUIT']:
                            transaction_queue.append(cmd)
                            writer.write(encode_simple_string("QUEUED"))
                            await writer.drain()
                            continue

                        if cmd_name == 'SUBSCRIBE':
                            for channel in cmd[1:]:
                                subscribed_channels.add(channel)
                                self.pubsub_channels[channel].add(writer)
                                writer.write(encode_array([b"subscribe", channel, len(subscribed_channels)]))
                            await writer.drain()
                            continue
                            
                        elif cmd_name == 'UNSUBSCRIBE':
                            channels_to_unsub = cmd[1:] if len(cmd) > 1 else list(subscribed_channels)
                            for channel in channels_to_unsub:
                                if channel in subscribed_channels:
                                    subscribed_channels.remove(channel)
                                    if writer in self.pubsub_channels[channel]:
                                        self.pubsub_channels[channel].remove(writer)
                                writer.write(encode_array([b"unsubscribe", channel, len(subscribed_channels)]))
                            await writer.drain()
                            continue
                            
                        elif cmd_name == 'PUBLISH':
                            if len(cmd) != 3:
                                writer.write(encode_error("ERR wrong number of arguments for 'publish' command"))
                                await writer.drain()
                                continue
                            channel = cmd[1]
                            message = cmd[2]
                            receivers = self.pubsub_channels.get(channel, set())
                            for w in list(receivers):
                                try:
                                    w.write(encode_array([b"message", channel, message]))
                                except Exception:
                                    pass
                            writer.write(encode_integer(len(receivers)))
                            await writer.drain()
                            continue

                        if subscribed_channels and cmd_name not in ['PING', 'QUIT']:
                            writer.write(encode_error("ERR only (P)SUBSCRIBE / (P)UNSUBSCRIBE / PING / QUIT allowed in this context"))
                            await writer.drain()
                            continue

                        response, is_write = self._execute_command(cmd)
                        writer.write(response)
                        await writer.drain()
                        
                        if is_write:
                            # Save to AOF on write
                            await self.aof.append(encode_array(cmd))
        except Exception as e:
            logger.error(f"Error handling connection {addr}: {e}")
        finally:
            ACTIVE_CONNECTIONS.dec()
            logger.debug(f"Disconnected: {addr}")
            for ch in subscribed_channels:
                if writer in self.pubsub_channels.get(ch, set()):
                    self.pubsub_channels[ch].remove(writer)
            writer.close()
            await writer.wait_closed()

    def _execute_command(self, cmd_array):
        TOTAL_COMMANDS.inc()
        CACHE_SIZE.set(len(self.cache.cache))
        
        if not cmd_array:
            return encode_error("Empty command"), False

        cmd_name = cmd_array[0]
        if isinstance(cmd_name, bytes):
            cmd_name = cmd_name.decode('utf-8', errors='ignore')
        
        cmd_name = str(cmd_name).upper()
        args = cmd_array[1:]

        try:
            if cmd_name == 'PING':
                if len(args) == 0:
                    return encode_simple_string("PONG"), False
                else:
                    return encode_bulk_string(args[0]), False
            elif cmd_name == 'SET':
                if len(args) < 2:
                    return encode_error("ERR wrong number of arguments for 'set' command"), False
                key = args[0]
                val = args[1]
                
                ex = None
                px = None
                
                idx = 2
                while idx < len(args):
                    arg_str = args[idx].decode('utf-8', errors='ignore').upper() if isinstance(args[idx], bytes) else str(args[idx]).upper()
                    if arg_str == 'EX':
                        if idx + 1 >= len(args):
                            return encode_error("ERR syntax error"), False
                        ex = int(args[idx+1])
                        idx += 2
                    elif arg_str == 'PX':
                        if idx + 1 >= len(args):
                            return encode_error("ERR syntax error"), False
                        px = int(args[idx+1])
                        idx += 2
                    else:
                        idx += 1

                self.cache.set(key, val, ex, px)
                return encode_simple_string("OK"), True
                
            elif cmd_name == 'GET':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'get' command"), False
                val = self.cache.get(args[0])
                if val is None:
                    CACHE_MISSES.inc()
                else:
                    CACHE_HITS.inc()
                return encode_bulk_string(val), False
                
            elif cmd_name == 'DEL':
                if len(args) < 1:
                    return encode_error("ERR wrong number of arguments for 'del' command"), False
                count = self.cache.delete(args)
                return encode_integer(count), True
                
            elif cmd_name == 'EXISTS':
                if len(args) < 1:
                    return encode_error("ERR wrong number of arguments for 'exists' command"), False
                count = self.cache.exists(args)
                return encode_integer(count), False
                
            elif cmd_name == 'LPUSH':
                if len(args) < 2:
                    return encode_error("ERR wrong number of arguments for 'lpush' command"), False
                count = self.cache.lpush(args[0], args[1:])
                return encode_integer(count), True

            elif cmd_name == 'RPUSH':
                if len(args) < 2:
                    return encode_error("ERR wrong number of arguments for 'rpush' command"), False
                count = self.cache.rpush(args[0], args[1:])
                return encode_integer(count), True

            elif cmd_name == 'LPOP':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'lpop' command"), False
                val = self.cache.lpop(args[0])
                return encode_bulk_string(val), True

            elif cmd_name == 'RPOP':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'rpop' command"), False
                val = self.cache.rpop(args[0])
                return encode_bulk_string(val), True

            elif cmd_name == 'LRANGE':
                if len(args) != 3:
                    return encode_error("ERR wrong number of arguments for 'lrange' command"), False
                try:
                    start = int(args[1])
                    stop = int(args[2])
                except ValueError:
                    return encode_error("ERR value is not an integer or out of range"), False
                vals = self.cache.lrange(args[0], start, stop)
                return encode_array(vals), False

            elif cmd_name == 'HSET':
                if len(args) < 3 or len(args) % 2 != 1:
                    return encode_error("ERR wrong number of arguments for 'hset' command"), False
                key = args[0]
                idx = 1
                new_fields = 0
                while idx < len(args):
                    new_fields += self.cache.hset(key, args[idx], args[idx+1])
                    idx += 2
                return encode_integer(new_fields), True

            elif cmd_name == 'HGET':
                if len(args) != 2:
                    return encode_error("ERR wrong number of arguments for 'hget' command"), False
                val = self.cache.hget(args[0], args[1])
                if val is None:
                    CACHE_MISSES.inc()
                else:
                    CACHE_HITS.inc()
                return encode_bulk_string(val), False

            elif cmd_name == 'HGETALL':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'hgetall' command"), False
                vals = self.cache.hgetall(args[0])
                return encode_array(vals), False
                
            elif cmd_name == 'INCR':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'incr' command"), False
                val = self.cache.incr(args[0], 1)
                return encode_integer(val), True
                
            elif cmd_name == 'DECR':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'decr' command"), False
                val = self.cache.decr(args[0], 1)
                return encode_integer(val), True

            elif cmd_name == 'SAVE':
                self.cache.save_snapshot(self.rdb_path)
                return encode_simple_string("OK"), False

            elif cmd_name == 'BGSAVE':
                asyncio.create_task(asyncio.to_thread(self.cache.save_snapshot, self.rdb_path))
                return encode_simple_string("Background saving started"), False
                
            elif cmd_name == 'ECHO':
                if len(args) != 1:
                    return encode_error("ERR wrong number of arguments for 'echo' command"), False
                return encode_bulk_string(args[0]), False
                
            elif cmd_name == 'KEYS':
                keys = self.cache.keys()
                return encode_array(keys), False
                
            elif cmd_name == 'COMMAND':
                # Return dummy to satisfy redis-cli connection handshake
                return encode_array([
                    [b"ping", 1, [b"fast"], 0, 0, 0],
                    [b"set", -3, [b"write"], 1, 1, 1],
                    [b"get", 2, [b"readonly"], 1, 1, 1]
                ]), False
                
            else:
                return encode_error(f"ERR unknown command '{cmd_name}'"), False

        except Exception as e:
            return encode_error(f"ERR {str(e)}"), False

    def _execute_command_internal(self, cmd_array):
        # Fire and forget for AOF recovery
        self._execute_command(cmd_array)
