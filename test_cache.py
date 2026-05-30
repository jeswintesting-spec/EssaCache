import socket
import time

def test_essacache():
    print("Testing EssaCache...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 6379))

    def send_cmd(cmd):
        s.sendall(cmd.encode())
        return s.recv(4096)

    # Test PING
    res = send_cmd("*1\r\n$4\r\nPING\r\n")
    assert res == b'+PONG\r\n', f"Expected +PONG\\r\\n, got {res}"

    # Test SET
    res = send_cmd("*3\r\n$3\r\nSET\r\n$7\r\nmy_name\r\n$6\r\nJeswin\r\n")
    assert res == b'+OK\r\n', f"Expected +OK\\r\\n, got {res}"

    # Test GET
    res = send_cmd("*2\r\n$3\r\nGET\r\n$7\r\nmy_name\r\n")
    assert res == b'$6\r\nJeswin\r\n', f"Expected $6\\r\\nJeswin\\r\\n, got {res}"
    
    # Test DEL
    res = send_cmd("*2\r\n$3\r\nDEL\r\n$7\r\nmy_name\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"

    # Test GET after DEL
    res = send_cmd("*2\r\n$3\r\nGET\r\n$7\r\nmy_name\r\n")
    assert res == b'$-1\r\n', f"Expected $-1\\r\\n, got {res}"
    
    # Test Active Expiration
    res = send_cmd("*5\r\n$3\r\nSET\r\n$10\r\nactive_key\r\n$3\r\nval\r\n$2\r\nPX\r\n$3\r\n100\r\n")
    assert res == b'+OK\r\n', f"Expected +OK\\r\\n, got {res}"
    
    # Wait for background expiration (0.1s + buffer)
    time.sleep(0.3)
    
    # Using raw KEYS command or EXISTS to verify it was purged
    res = send_cmd("*2\r\n$6\r\nEXISTS\r\n$10\r\nactive_key\r\n")
    assert res == b':0\r\n', f"Expected :0\\r\\n, got {res}"

    # Test Lists
    res = send_cmd("*3\r\n$5\r\nLPUSH\r\n$6\r\nmylist\r\n$1\r\na\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"
    res = send_cmd("*3\r\n$5\r\nLPUSH\r\n$6\r\nmylist\r\n$1\r\nb\r\n")
    assert res == b':2\r\n', f"Expected :2\\r\\n, got {res}"
    res = send_cmd("*4\r\n$6\r\nLRANGE\r\n$6\r\nmylist\r\n$1\r\n0\r\n$2\r\n-1\r\n")
    assert res == b'*2\r\n$1\r\nb\r\n$1\r\na\r\n', f"Expected array of b, a, got {res}"

    # Test Hashes
    res = send_cmd("*4\r\n$4\r\nHSET\r\n$6\r\nmyhash\r\n$5\r\nfield\r\n$5\r\nvalue\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"
    res = send_cmd("*3\r\n$4\r\nHGET\r\n$6\r\nmyhash\r\n$5\r\nfield\r\n")
    assert res == b'$5\r\nvalue\r\n', f"Expected $5\\r\\nvalue\\r\\n, got {res}"

    # Test Atomic Counters
    res = send_cmd("*2\r\n$4\r\nINCR\r\n$7\r\ncounter\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"
    res = send_cmd("*2\r\n$4\r\nINCR\r\n$7\r\ncounter\r\n")
    assert res == b':2\r\n', f"Expected :2\\r\\n, got {res}"
    res = send_cmd("*2\r\n$4\r\nDECR\r\n$7\r\ncounter\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"

    # Test Snapshotting
    res = send_cmd("*1\r\n$4\r\nSAVE\r\n")
    assert res == b'+OK\r\n', f"Expected +OK\\r\\n, got {res}"

    # Test Pub/Sub
    sub_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sub_sock.connect(('127.0.0.1', 6379))
    sub_sock.sendall(b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n")
    res = sub_sock.recv(4096)
    assert b'subscribe' in res, f"Expected subscribe response, got {res}"
    
    # Wait to ensure server processed the subscribe
    time.sleep(0.1)
    
    res = send_cmd("*3\r\n$7\r\nPUBLISH\r\n$4\r\nnews\r\n$5\r\nhello\r\n")
    assert res == b':1\r\n', f"Expected :1\\r\\n, got {res}"
    
    res = sub_sock.recv(4096)
    assert b'hello' in res, f"Expected hello message, got {res}"
    
    sub_sock.close()

    # Test Transactions
    res = send_cmd("*1\r\n$5\r\nMULTI\r\n")
    assert res == b'+OK\r\n', f"Expected +OK\\r\\n, got {res}"
    res = send_cmd("*3\r\n$3\r\nSET\r\n$4\r\ntx_k\r\n$4\r\ntx_v\r\n")
    assert res == b'+QUEUED\r\n', f"Expected +QUEUED\\r\\n, got {res}"
    res = send_cmd("*2\r\n$3\r\nGET\r\n$4\r\ntx_k\r\n")
    assert res == b'+QUEUED\r\n', f"Expected +QUEUED\\r\\n, got {res}"
    res = send_cmd("*1\r\n$4\r\nEXEC\r\n")
    assert res == b'*2\r\n+OK\r\n$4\r\ntx_v\r\n', f"Expected transaction array, got {res}"

    # Test DISCARD
    send_cmd("*1\r\n$5\r\nMULTI\r\n")
    send_cmd("*3\r\n$3\r\nSET\r\n$5\r\nd_key\r\n$5\r\nd_val\r\n")
    res = send_cmd("*1\r\n$7\r\nDISCARD\r\n")
    assert res == b'+OK\r\n', f"Expected +OK\\r\\n, got {res}"
    res = send_cmd("*2\r\n$3\r\nGET\r\n$5\r\nd_key\r\n")
    assert res == b'$-1\r\n', f"Expected $-1\\r\\n, got {res}"

    print("All tests passed!")
    s.close()

if __name__ == "__main__":
    time.sleep(1) # wait for server to start
    test_essacache()
