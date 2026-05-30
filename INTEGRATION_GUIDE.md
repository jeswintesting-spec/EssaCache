# The Essa Ecosystem: Integration Guide

This manual explains how to connect and orchestrate the three core pillars of your architecture: **EssaDB**, **EssaCache**, and **EssaConnect**. 

By combining these three systems, you create a highly scalable, enterprise-grade data pipeline capable of handling massive throughput with minimal latency.

---

## 1. Architecture Overview

Here is how the systems interact:

1. **EssaConnect** (The Gateway / Application Layer) acts as the central brain. It receives HTTP/WebSocket requests from the frontend or external clients.
2. When a client requests data, EssaConnect first asks **EssaCache** (The In-Memory Layer). 
3. If the data exists (**Cache Hit**), EssaCache returns it instantly (in microseconds), bypassing the hard drive entirely.
4. If the data does not exist (**Cache Miss**), EssaConnect falls back and queries **EssaDB** (The Persistent Storage Layer).
5. EssaConnect takes the result from EssaDB and writes it back into EssaCache using the `SET ... EX` command so future requests are instantly served from memory.

### Diagram
```text
[ Clients ] 
    │
    ▼
(HTTP / WebSockets)
    │
    ▼
[ EssaConnect ] ────(1. Query Cache)───► [ EssaCache ]
    │   ▲                                 (RAM, Port: 6379)
    │   │                                      │
    │   └───(2. Cache Hit: Return Data)────────┘
    │
    │ (3. Cache Miss: Fallback to DB)
    ▼
[ EssaDB ] 
(Disk Storage, Port: XXXX)
```

---

## 2. Integrating EssaConnect with EssaCache

Since EssaCache features a native Python SDK, integrating it into EssaConnect is completely seamless.

### Step 1: Install the SDK in EssaConnect
Ensure EssaConnect has the `essacache` SDK installed.
```bash
pip install essacache
```

### Step 2: The "Cache-Aside" Pattern
Inside your EssaConnect handlers, wrap your database queries with a caching layer.

```python
from essacache import EssaCacheClient
# Assuming you have an EssaDB client imported
# from essadb import EssaDBClient 

# Initialize Clients
cache = EssaCacheClient(host="127.0.0.1", port=6379)
db = EssaDBClient(host="127.0.0.1", port=5000) # (Assuming EssaDB runs on 5000)

def get_user_profile(user_id):
    cache_key = f"user:{user_id}:profile"
    
    # 1. Try EssaCache first (Blazing Fast)
    cached_data = cache.get(cache_key)
    if cached_data:
        print("Cache Hit! Returning instantly.")
        return cached_data.decode('utf-8')
        
    # 2. Cache Miss: Query EssaDB (Slower, hits the disk)
    print("Cache Miss! Querying EssaDB...")
    db_data = db.query(f"SELECT * FROM profiles WHERE id = {user_id}")
    
    # 3. Store the result in EssaCache for the next 10 minutes (600 seconds)
    if db_data:
        cache.set(cache_key, db_data, ex=600)
        
    return db_data
```

---

## 3. Advanced Integration: Pub/Sub Cache Invalidation

One of the biggest challenges in distributed systems is "Cache Invalidation"—knowing when to delete data from EssaCache because it was updated in EssaDB.

You can use EssaCache's **Pub/Sub Broker** to solve this!

### The Setup
1. **EssaConnect** opens a background thread and runs `SUBSCRIBE db_updates` on EssaCache.
2. Whenever a user *updates* their profile, the write goes directly to **EssaDB**.
3. Immediately after the write succeeds, the update function runs `PUBLISH db_updates "user:123:profile"` to EssaCache.
4. The background thread in EssaConnect hears this broadcast and instantly deletes the stale key from EssaCache!

### Code Example:
**Writer Function (Updates Data):**
```python
def update_user_profile(user_id, new_data):
    # 1. Write to the source of truth (EssaDB)
    db.execute(f"UPDATE profiles SET data='{new_data}' WHERE id={user_id}")
    
    # 2. Broadcast the invalidation event via EssaCache Pub/Sub
    cache.publish("db_updates", f"user:{user_id}:profile")
```

**Listener Service (Runs in the background of EssaConnect):**
```python
def listen_for_invalidations():
    # Dedicated connection for subscribing
    listener = EssaCacheClient(host="127.0.0.1", port=6379)
    listener.connect()
    
    # Send Subscribe Command
    listener._sock.sendall(b"*2\r\n$9\r\nSUBSCRIBE\r\n$10\r\ndb_updates\r\n")
    
    print("Listening for EssaDB updates...")
    while True:
        data = listener._sock.recv(4096)
        # Parse the Pub/Sub array (e.g. ['message', 'db_updates', 'user:123:profile'])
        cmds = listener._decoder.decode(data)
        for cmd in cmds:
            if cmd[0] == b"message":
                stale_key = cmd[2].decode('utf-8')
                print(f"EssaDB updated! Invalidating cache key: {stale_key}")
                
                # Delete the stale key from Cache so the next request fetches fresh DB data
                cache.delete(stale_key)
```

---

## 4. Docker Compose Orchestration

The most professional way to link EssaDB, EssaCache, and EssaConnect is to put them all in a single Docker network. They will be able to talk to each other using their container names as hostnames!

Here is an example `docker-compose.yml` to put in your master deployment repository:

```yaml
version: "3.8"

services:
  # The In-Memory Cache
  essacache:
    image: jeswin/essacache:latest
    ports:
      - "6379:6379"
      - "8000:8000" # Prometheus Telemetry
    volumes:
      - essacache_data:/data

  # The Persistent Database
  essadb:
    image: jeswin/essadb:latest
    ports:
      - "5000:5000"
    volumes:
      - essadb_data:/var/lib/essadb

  # The Gateway / API
  essaconnect:
    image: jeswin/essaconnect:latest
    ports:
      - "8080:8080"
    depends_on:
      - essacache
      - essadb
    environment:
      - CACHE_HOST=essacache
      - CACHE_PORT=6379
      - DB_HOST=essadb
      - DB_PORT=5000

volumes:
  essacache_data:
  essadb_data:
```

With this single file, a simple `docker compose up -d` will spin up your entire distributed architecture securely!
