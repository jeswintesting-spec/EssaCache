import asyncio
import os
import logging

logger = logging.getLogger(__name__)

class AOF:
    """
    Append-Only File (AOF) Persistence.
    Asynchronously appends commands to a file, and fsyncs at regular intervals.
    """
    def __init__(self, filepath="essacache.aof", fsync_interval=1.0):
        self.filepath = filepath
        self.fsync_interval = fsync_interval
        self.buffer = bytearray()
        self.lock = asyncio.Lock()
        self.running = False
        self._task = None
        
        # Touch file if not exists
        if not os.path.exists(self.filepath):
            open(self.filepath, 'wb').close()
            
        self.file = open(self.filepath, 'a+b')

    async def start(self):
        """Starts the background fsync loop."""
        self.running = True
        self._task = asyncio.create_task(self._fsync_loop())

    async def stop(self):
        """Stops the background loop and flushes remaining data."""
        self.running = False
        if self._task:
            await self._task
        self.file.close()

    async def append(self, resp_bytes: bytes):
        """Appends RESP byte strings to the memory buffer."""
        async with self.lock:
            self.buffer.extend(resp_bytes)

    async def _fsync_loop(self):
        while self.running:
            await asyncio.sleep(self.fsync_interval)
            async with self.lock:
                if self.buffer:
                    self.file.write(self.buffer)
                    self.file.flush()
                    try:
                        os.fsync(self.file.fileno())
                    except Exception as e:
                        logger.error(f"AOF fsync failed: {e}")
                    self.buffer.clear()
        
        # Final flush on stop
        async with self.lock:
            if self.buffer:
                self.file.write(self.buffer)
                self.file.flush()
                try:
                    os.fsync(self.file.fileno())
                except Exception as e:
                    logger.error(f"Final AOF fsync failed: {e}")
                self.buffer.clear()

    def get_file_content(self) -> bytes:
        """Reads the entire AOF file for startup recovery."""
        self.file.seek(0)
        return self.file.read()
