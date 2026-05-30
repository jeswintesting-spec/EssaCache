class IncompleteMessage(Exception):
    pass

class RESPDecoder:
    """
    Decodes a stream of bytes into RESP Python objects.
    """
    def __init__(self):
        self.buffer = b""
        self.pos = 0

    def decode(self, data: bytes) -> list:
        """Parses available data and returns a list of complete commands."""
        self.buffer += data
        self.pos = 0
        cmds = []
        while self.pos < len(self.buffer):
            try:
                start_pos = self.pos
                obj = self._parse()
                cmds.append(obj)
                self.buffer = self.buffer[self.pos:]
                self.pos = 0
            except IncompleteMessage:
                self.pos = start_pos
                break
        return cmds

    def _read_until_crlf(self) -> bytes:
        idx = self.buffer.find(b"\r\n", self.pos)
        if idx == -1:
            raise IncompleteMessage()
        line = self.buffer[self.pos:idx]
        self.pos = idx + 2
        return line

    def _parse(self):
        if self.pos >= len(self.buffer):
            raise IncompleteMessage()
            
        byte = self.buffer[self.pos]
        self.pos += 1
        
        if byte == ord('*'):
            return self._parse_array()
        elif byte == ord('$'):
            return self._parse_bulk_string()
        elif byte == ord('+'):
            return self._parse_simple_string()
        elif byte == ord('-'):
            return self._parse_error()
        elif byte == ord(':'):
            return self._parse_integer()
        else:
            # Inline commands like `PING\r\n` which might not start with '*'
            self.pos -= 1
            line = self._read_until_crlf()
            return line.split()

    def _parse_array(self) -> list:
        line = self._read_until_crlf()
        count = int(line)
        if count == -1:
            return None
        return [self._parse() for _ in range(count)]

    def _parse_bulk_string(self) -> bytes:
        line = self._read_until_crlf()
        length = int(line)
        if length == -1:
            return None
        if self.pos + length + 2 > len(self.buffer):
            raise IncompleteMessage()
        data = self.buffer[self.pos:self.pos+length]
        self.pos += length + 2 # skip \r\n
        return data

    def _parse_simple_string(self) -> bytes:
        return self._read_until_crlf()

    def _parse_error(self) -> bytes:
        return self._read_until_crlf()

    def _parse_integer(self) -> int:
        return int(self._read_until_crlf())

def encode_simple_string(s: str) -> bytes:
    return f"+{s}\r\n".encode()

def encode_error(s: str) -> bytes:
    return f"-ERR {s}\r\n".encode()

def encode_integer(i: int) -> bytes:
    return f":{i}\r\n".encode()

def encode_bulk_string(b) -> bytes:
    if b is None:
        return b"$-1\r\n"
    if isinstance(b, str):
        b = b.encode()
    return f"${len(b)}\r\n".encode() + b + b"\r\n"

def encode_array(arr: list) -> bytes:
    if arr is None:
        return b"*-1\r\n"
    res = bytearray(f"*{len(arr)}\r\n".encode())
    for item in arr:
        if isinstance(item, int):
            res.extend(encode_integer(item))
        elif isinstance(item, (str, bytes)):
            res.extend(encode_bulk_string(item))
        elif isinstance(item, list):
            res.extend(encode_array(item))
        elif item is None:
            res.extend(encode_bulk_string(None))
    return bytes(res)
