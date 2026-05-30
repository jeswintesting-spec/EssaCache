import socket
from typing import List, Dict, Optional, Union, Any
from .resp import RESPDecoder

class EssaCacheError(Exception):
    """Custom exception for EssaCache server errors."""
    pass

class EssaCacheClient:
    """
    A clean, object-oriented Python SDK to interface natively with the EssaCache server.
    Handles connections, protocol encoding/decoding, and exposes developer-friendly API methods.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._decoder = RESPDecoder()

    def connect(self):
        """Establish a TCP connection to the server."""
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
            
    def close(self):
        """Close the active connection."""
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _encode_command(self, *args) -> bytes:
        parts = [f"*{len(args)}\r\n".encode('utf-8')]
        for arg in args:
            if isinstance(arg, bytes):
                arg_bytes = arg
            else:
                arg_bytes = str(arg).encode('utf-8')
            parts.append(f"${len(arg_bytes)}\r\n".encode('utf-8'))
            parts.append(arg_bytes)
            parts.append(b"\r\n")
        return b"".join(parts)

    def execute(self, *args) -> Any:
        """Send a raw command to the server and return the parsed RESP response."""
        self.connect()
        cmd = self._encode_command(*args)
        self._sock.sendall(cmd)
        
        data = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            data += chunk
            cmds = self._decoder.decode(data)
            if cmds:
                # Return the first parsed response from the pipeline
                res = cmds[0]
                if isinstance(res, str) and (res.startswith("ERR") or res.startswith("WRONGTYPE")):
                    raise EssaCacheError(res)
                return res

    # --- Core Commands ---
    def ping(self) -> str:
        """Ping the server, returns 'PONG'."""
        res = self.execute("PING")
        if isinstance(res, bytes):
            return res.decode('utf-8')
        return res

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a key-value pair, optionally with an expiration (in seconds)."""
        args = ["SET", key, value]
        if ex is not None:
            args.extend(["EX", ex])
        res = self.execute(*args)
        return res == b"OK" or res == "OK"

    def get(self, key: str) -> Optional[bytes]:
        """Get the value of a key."""
        return self.execute("GET", key)

    def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns the number of keys deleted."""
        return self.execute("DEL", *keys)
        
    def exists(self, *keys: str) -> int:
        """Check if keys exist. Returns the number of existing keys."""
        return self.execute("EXISTS", *keys)

    # --- List Commands ---
    def lpush(self, key: str, *values: Any) -> int:
        """Prepend one or multiple values to a list."""
        return self.execute("LPUSH", key, *values)
        
    def rpush(self, key: str, *values: Any) -> int:
        """Append one or multiple values to a list."""
        return self.execute("RPUSH", key, *values)
        
    def lpop(self, key: str) -> Optional[bytes]:
        """Remove and return the first element of a list."""
        return self.execute("LPOP", key)
        
    def rpop(self, key: str) -> Optional[bytes]:
        """Remove and return the last element of a list."""
        return self.execute("RPOP", key)
        
    def lrange(self, key: str, start: int, stop: int) -> List[bytes]:
        """Get a range of elements from a list."""
        return self.execute("LRANGE", key, start, stop)

    # --- Hash Commands ---
    def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        """Set multiple hash fields to multiple values."""
        args = ["HSET", key]
        for k, v in mapping.items():
            args.extend([k, v])
        return self.execute(*args)
        
    def hget(self, key: str, field: str) -> Optional[bytes]:
        """Get the value of a hash field."""
        return self.execute("HGET", key, field)
        
    def hgetall(self, key: str) -> Dict[bytes, bytes]:
        """Get all fields and values in a hash."""
        arr = self.execute("HGETALL", key)
        if not isinstance(arr, list):
            return {}
        res = {}
        for i in range(0, len(arr), 2):
            res[arr[i]] = arr[i+1]
        return res

    # --- Counters ---
    def incr(self, key: str) -> int:
        """Increment the integer value of a key by one."""
        return self.execute("INCR", key)
        
    def decr(self, key: str) -> int:
        """Decrement the integer value of a key by one."""
        return self.execute("DECR", key)

    # --- Pub/Sub ---
    def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel."""
        return self.execute("PUBLISH", channel, message)
