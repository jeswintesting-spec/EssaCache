# EssaCache 🚀

A blazing-fast, in-memory data structure store, serving as a Redis clone implemented purely in Python. While traditional databases write to the hard drive, EssaCache lives entirely in RAM for lightning-fast performance, offering custom memory management, eviction algorithms, and persistent backups.

## Key Features

1. **LRU Eviction (Least Recently Used)**: 
   Custom Doubly-Linked-List + Hash Map algorithm that maintains an O(1) time complexity for reading/writing and automatically evicts the oldest unused data when the RAM capacity is full.

2. **AOF (Append-Only File)**:
   Async background threads that periodically snapshot the RAM modifications to an append-only file on the disk (default: 1-second interval). This ensures that if the server crashes or loses power, the data is flawlessly recovered upon restarting.

3. **Active Expiration (Background Cleanup)**:
   An asynchronous loop runs 10 times a second to perform randomized probabilistic sampling on keys with a TTL. It dynamically purges expired data to intelligently clean memory without blocking the primary thread.

4. **Advanced Data Types (Lists & Hashes)**:
   Beyond simple strings, it deeply integrates `collections.deque` and Hash Maps to power complex commands like `HSET`, `HGET`, `LPUSH`, and `LRANGE` dynamically with strict type checking.

5. **Atomic Counters**:
   High-performance `INCR` and `DECR` operations designed for building real-time rate limiters and hit counters, backed by standard string encoding and strict integer type verification.

6. **Pub/Sub (Publish/Subscribe Messaging)**:
   Engineered a high-performance message broker internally. Clients can `SUBSCRIBE` to custom channels and listen in real-time as other clients `PUBLISH` messages to them. Powered by native `asyncio` streams broadcasting.

7. **Prometheus Telemetry**:
   Built-in observability. Automatically spins up an asynchronous HTTP server on port `8000` exposing real-time metrics (`Cache Hits/Misses`, `Active Connections`, `RAM Usage`, `Total Commands`) perfectly formatted for Grafana dashboards.

8. **Transactions (`MULTI` & `EXEC`)**:
   Full support for atomic transaction blocks. By wrapping commands in `MULTI` and `EXEC`, the server queues up executions securely in isolated blocks ensuring database consistency. Supports `DISCARD` for transaction rollback.

9. **Point-In-Time Snapshotting (RDB)**:
   Allows you to create a compact, binary serialization dump of the exact memory state using the `SAVE` and `BGSAVE` commands. `BGSAVE` utilizes `asyncio.to_thread` to ensure zero blocking on the main event loop while dumping the snapshot.

10. **RESP Protocol (Redis Serialization Protocol)**:
   A lightweight pure Python implementation of the official Redis protocol. This means you can connect to EssaCache using the standard `redis-cli` or any standard Redis client library.

## Project Structure

```text
EssaCache/
├── essacache/
│   ├── __init__.py
│   ├── __main__.py      # CLI Entry point
│   ├── aof.py           # Append-Only File async implementation
│   ├── cache.py         # O(1) LRU Cache + Datatypes + RDB Snapshotting
│   ├── resp.py          # Redis Serialization Protocol Parser & Encoder
│   └── server.py        # Asyncio Socket Server bridging Cache, Pub/Sub, Transactions & Persistence
├── test_cache.py        # E2E Test Suite
└── README.md
```

## Quick Start

### 1. Installation (1-Click)
Clone the repository and run the setup script to instantly install the dependencies and package the server globally.

```bash
git clone https://github.com/jeswintesting-spec/EssaCache.git
cd EssaCache
./install.sh
```

### 2. Run the Server
Once installed, you can launch the server from anywhere on your terminal:

```bash
essacache-server --host 127.0.0.1 --port 6379
```

### 3. Connect with the Custom CLI (`essacli.py`)
EssaCache comes with its own beautifully formatted, interactive terminal client built with `prompt_toolkit` and `rich`. It features auto-completion, colored outputs, and a seamless connection experience.

```bash
./essacli.py
```

Inside the CLI, try standard commands:
```text
127.0.0.1:6379> PING
"PONG"
127.0.0.1:6379> MULTI
OK
127.0.0.1:6379> SET hits 10
QUEUED
127.0.0.1:6379> INCR hits
QUEUED
127.0.0.1:6379> EXEC
1) OK
2) (integer) 11
127.0.0.1:6379> PUBLISH news "EssaCache v1 is live!"
(integer) 0
127.0.0.1:6379> SUBSCRIBE news
Reading messages... (press Ctrl-C to quit)
1) "subscribe"
2) "news"
3) (integer) 1
```

*(You can also still connect using the standard `redis-cli` if you prefer!)*

### 4. Use the Python SDK (`essacache-py`)
EssaCache comes with a clean, fully-typed object-oriented Python client. You can use it in your own apps to interact with the server natively, without dealing with raw sockets.

```python
from essacache import EssaCacheClient

with EssaCacheClient(host="127.0.0.1", port=6379) as client:
    # Set and Get
    client.set("user:1", "jeswin", ex=60)
    print(client.get("user:1"))  # b'jeswin'

    # Lists
    client.lpush("tasks", "task1", "task2")
    print(client.lrange("tasks", 0, -1)) # [b'task2', b'task1']

    # Atomic Counters
    client.incr("page_views")
    
    # Hashes
    client.hset("profile", {"name": "Essa", "version": "1.0"})
    print(client.hgetall("profile")) # {b'name': b'Essa', b'version': b'1.0'}
```

### 5. Run via Docker (Cloud Ready ☁️)
EssaCache is fully containerized and production-ready. You can spin up the entire architecture (with persistent `/data` volume mounting) in one command:

```bash
docker compose up -d
```
You can then seamlessly connect to it from your host machine via `./essacli.py` or `redis-cli`.

### 6. Run Tests
You can verify the system's integrity by running the test file:
```bash
python3 test_cache.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Why build this?
EssaCache was built as a masterclass to deeply understand:
- Event loops and asynchronous network programming.
- Low-level network serialization and protocol parsing.
- Advanced data structures (Doubly Linked Lists combined with Hash Maps).
- Background threaded I/O operations.
