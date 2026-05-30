# EssaCache - Official User Manual

Welcome to the **EssaCache User Manual**. This document covers absolutely everything you need to know to install, configure, deploy, and master the EssaCache system. 

EssaCache is a blazing-fast, strictly typed, in-memory data structure store built entirely in Python. It supports advanced features like background persistence, LRU memory eviction, active key expiration, Pub/Sub broadcasting, atomic transactions, and Prometheus telemetry.

---

## Table of Contents
1. [Installation Guide](#1-installation-guide)
2. [Starting the Server](#2-starting-the-server)
3. [Connecting to the Database](#3-connecting-to-the-database)
4. [Command Reference & Data Types](#4-command-reference--data-types)
5. [Pub/Sub (Real-Time Messaging)](#5-pubsub-real-time-messaging)
6. [Transactions (Atomic Blocks)](#6-transactions-atomic-blocks)
7. [Persistence (AOF & RDB)](#7-persistence-aof--rdb)
8. [Prometheus Telemetry](#8-prometheus-telemetry)
9. [Python SDK Usage](#9-python-sdk-usage)
10. [Running Tests](#10-running-tests)

---

## 1. Installation Guide

### Option A: The 1-Click Install Script (Recommended)
For the easiest installation on Linux or macOS, use the provided Bash script. This automatically verifies your Python version, installs dependencies, and registers the server commands globally.

```bash
git clone https://github.com/jeswintesting-spec/EssaCache.git
cd EssaCache
./install.sh
```

### Option B: Docker (Cloud Ready)
If you prefer not to install Python dependencies on your host machine, you can run the entire system inside an isolated Docker container. 

```bash
docker compose up -d --build
```
This spins up the server in the background and mounts a `./data` folder to your host machine so your database files safely persist even if the container is destroyed.

### Option C: Manual Installation
If you want to install it manually:
```bash
pip install -e .
```

---

## 2. Starting the Server

If you used the `install.sh` script or installed via `pip`, you can launch the server from anywhere on your terminal using the global command:

```bash
essacache-server
```

### Configuration Arguments
You can customize the server behavior using the following CLI flags:

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | The IP address to bind the TCP server to. Use `0.0.0.0` to allow external connections. |
| `--port` | `6379` | The port the TCP server listens on. |
| `--capacity` | `10000` | The maximum number of keys allowed in RAM before LRU eviction triggers. |
| `--aof` | `essacache.aof` | The filepath to store the Append-Only File logs. |
| `--rdb` | `essacache.rdb` | The filepath to store binary memory snapshots. |

**Example:**
```bash
essacache-server --host 0.0.0.0 --port 6380 --capacity 50000
```

---

## 3. Connecting to the Database

### Using the Custom CLI (`essacli.py`)
EssaCache ships with a beautiful, custom-built terminal client featuring syntax highlighting and auto-completion.
1. Ensure the server is running.
2. Open a new terminal and run:
   ```bash
   ./essacli.py
   ```
3. *(Optional)* Pass connection flags if your server is on a different port: `./essacli.py --host 127.0.0.1 --port 6380`.

### Using standard `redis-cli`
Because EssaCache speaks the exact same language as Redis (The RESP Protocol), you can use the official `redis-cli`:
```bash
redis-cli -h 127.0.0.1 -p 6379
```

---

## 4. Command Reference & Data Types

EssaCache strictly enforces type safety. If you attempt to run a List command on a String key, it will instantly throw a `WRONGTYPE` error.

### Core Strings & Keys
*   **`PING`**: Ping the server. Returns `PONG`.
*   **`SET key value [EX seconds] [PX milliseconds]`**: Set a string value. Optionally provide an expiration time in seconds (`EX`) or milliseconds (`PX`).
*   **`GET key`**: Retrieve a string value. Returns `(nil)` if it doesn't exist.
*   **`DEL key [key ...]`**: Delete one or more keys. Returns the number of keys successfully deleted.
*   **`EXISTS key [key ...]`**: Check how many of the requested keys exist.
*   **`KEYS`**: Returns an array of all keys currently in memory.

### Atomic Counters
Designed for hit-counters and rate-limiters.
*   **`INCR key`**: Increments the integer value of a key by 1. If the key doesn't exist, it is set to `0` first.
*   **`DECR key`**: Decrements the integer value of a key by 1.

### Lists (Double-Ended Queues)
Extremely fast $O(1)$ mutations on the front or back of arrays.
*   **`LPUSH key value [value ...]`**: Prepend one or more values to the front of a list.
*   **`RPUSH key value [value ...]`**: Append one or more values to the back of a list.
*   **`LPOP key`**: Remove and return the first element of a list.
*   **`RPOP key`**: Remove and return the last element of a list.
*   **`LRANGE key start stop`**: Return a range of elements. Use `0 -1` to fetch the entire list.

### Hashes (Dictionaries)
Perfect for storing objects and user profiles.
*   **`HSET key field value [field value ...]`**: Set multiple fields on a hash key.
*   **`HGET key field`**: Retrieve the value of a specific field.
*   **`HGETALL key`**: Return all fields and values inside the hash as an array.

---

## 5. Pub/Sub (Real-Time Messaging)

EssaCache acts as a high-performance message broker using asynchronous broadcasting.

*   **`SUBSCRIBE channel [channel ...]`**: Listen to one or more channels. The terminal will block and continuously stream incoming payloads in real-time. Press `Ctrl-C` to exit.
*   **`PUBLISH channel message`**: Broadcast a message payload to all clients currently listening to that channel. Returns the integer count of clients who received the broadcast.

---

## 6. Transactions (Atomic Blocks)

Execute multiple commands securely without interference from other clients.

1.  **`MULTI`**: Starts the transaction block. Subsequent commands will reply with `QUEUED` instead of executing.
2.  *(Queue your commands)*: e.g. `SET hits 10`, `INCR hits`.
3.  **`EXEC`**: Atomically executes all queued commands instantly. Returns an array of all the responses.
4.  **`DISCARD`**: Aborts the transaction and destroys the queue without executing anything.

---

## 7. Persistence (AOF & RDB)

EssaCache employs dual-persistence strategies to ensure zero data loss.

### AOF (Append-Only File)
Every time a command modifies data (e.g., `SET`, `DEL`), the raw protocol byte stream is appended to `essacache.aof` asynchronously in the background. If the server crashes, it replays this entire file line-by-line upon rebooting to instantly restore the state.

### RDB Snapshotting
You can serialize the exact state of the LRU Cache memory into a compact binary file.
*   **`SAVE`**: Blocks the main thread and dumps the state to `essacache.rdb`.
*   **`BGSAVE`**: Safely offloads the snapshotting process to a background thread using `asyncio.to_thread`, ensuring the server continues handling live traffic without lagging.

*Note: On boot, EssaCache loads the RDB snapshot first (for blazing speed), and then replays the AOF logs on top of it to fill in any missing gaps!*

---

## 8. Prometheus Telemetry

EssaCache is built for observability. Whenever you launch the server, it automatically spins up a parallel HTTP metrics endpoint on Port `8000`.

To view the live telemetry, open a web browser or run:
```bash
curl http://127.0.0.1:8000/metrics
```

**Exported Metrics:**
*   `essacache_active_connections` (Gauge): Current connected TCP sockets.
*   `essacache_keys_total` (Gauge): Exact size of the memory cache.
*   `essacache_commands_total` (Counter): Total ops processed.
*   `essacache_cache_hits_total` (Counter): Successful cache lookups.
*   `essacache_cache_misses_total` (Counter): Failed cache lookups.

You can point Grafana at this endpoint to generate beautiful real-time dashboards!

---

## 9. Python SDK Usage

If you are building Python applications, you don't need to write raw socket wrappers. Use the fully-typed native client!

```python
from essacache import EssaCacheClient

# The 'with' block ensures the connection gracefully closes when done
with EssaCacheClient(host="127.0.0.1", port=6379) as client:
    
    # Standard caching
    client.set("session_token", "abc123xyz", ex=3600)
    print(client.get("session_token")) # Returns b'abc123xyz'
    
    # Hash mapping
    client.hset("user:99", {"name": "Jeswin", "role": "Admin"})
    profile = client.hgetall("user:99")
    print(profile) # Returns {b'name': b'Jeswin', b'role': b'Admin'}

    # Publishing messages
    client.publish("global_alerts", "Server maintenance in 5 mins!")
```

---

## 10. Running Tests

To verify that your installation is perfectly stable, run the End-to-End test suite. It creates raw sockets, runs commands covering every single feature, and asserts the correct byte responses.

1. Keep the server running in one terminal (`essacache-server`).
2. Open a new terminal in the `EssaCache` directory and run:
   ```bash
   python3 test_cache.py
   ```
If successful, you will see:
```text
Testing EssaCache...
All tests passed!
```

---
**Thank you for using EssaCache!**
