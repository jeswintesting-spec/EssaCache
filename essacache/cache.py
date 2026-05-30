import time
import collections
from typing import Optional, List, Any

class Node:
    __slots__ = ['key', 'value', 'expire_at', 'prev', 'next']
    def __init__(self, key: bytes, value: Any, expire_at: Optional[float] = None):
        self.key = key
        self.value = value
        self.expire_at = expire_at
        self.prev = None
        self.next = None

class LRUCache:
    """
    Least Recently Used (LRU) Cache using a Hash Map + Doubly-Linked List.
    Provides O(1) time complexity for get, set, and delete operations.
    """
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.cache = {}
        self.expires = set()
        # Sentinel nodes for easier double-linked list management
        self.head = Node(b'', b'')
        self.tail = Node(b'', b'')
        self.head.next = self.tail
        self.tail.prev = self.head

    def sample_and_evict_expired(self, sample_size: int = 20) -> int:
        """
        Randomly samples keys with expirations and deletes expired ones.
        Returns the number of keys that were actually expired and deleted.
        """
        import random
        if not self.expires:
            return 0
        
        sample = random.sample(list(self.expires), min(len(self.expires), sample_size))
        expired_count = 0
        now = time.time()
        
        for key in sample:
            if key in self.cache:
                node = self.cache[key]
                if node.expire_at and now > node.expire_at:
                    self._remove(node)
                    del self.cache[key]
                    self.expires.remove(key)
                    expired_count += 1
            else:
                self.expires.remove(key)
                
        return expired_count

    def _remove(self, node: Node):
        """Removes a node from the linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add(self, node: Node):
        """Adds a node right before the tail (most recently used)."""
        prev = self.tail.prev
        prev.next = node
        node.prev = prev
        node.next = self.tail
        self.tail.prev = node

    def get(self, key: bytes) -> Optional[bytes]:
        """Gets a value by key. Updates its position in LRU."""
        if key in self.cache:
            node = self.cache[key]
            if node.expire_at and time.time() > node.expire_at:
                # Key has expired
                self._remove(node)
                del self.cache[key]
                self.expires.discard(key)
                return None
            
            # Move to tail (most recently used)
            self._remove(node)
            self._add(node)
            return node.value
        return None

    def set(self, key: bytes, value: bytes, ex: Optional[int] = None, px: Optional[int] = None):
        """Sets a key-value pair. Handles expiration and capacity."""
        expire_at = None
        if ex is not None:
            expire_at = time.time() + ex
        elif px is not None:
            expire_at = time.time() + (px / 1000.0)

        if key in self.cache:
            node = self.cache[key]
            self._remove(node)
            node.value = value
            node.expire_at = expire_at
            self._add(node)
        else:
            if len(self.cache) >= self.capacity:
                # Evict least recently used (head.next)
                lru = self.head.next
                self._remove(lru)
                del self.cache[lru.key]
                self.expires.discard(lru.key)
            
            new_node = Node(key, value, expire_at)
            self._add(new_node)
            self.cache[key] = new_node

        if expire_at is not None:
            self.expires.add(key)
        else:
            self.expires.discard(key)

    def delete(self, keys: List[bytes]) -> int:
        """Deletes multiple keys. Returns count of deleted keys."""
        count = 0
        for key in keys:
            if key in self.cache:
                node = self.cache[key]
                self._remove(node)
                del self.cache[key]
                self.expires.discard(key)
                count += 1
        return count

    def exists(self, keys: List[bytes]) -> int:
        """Counts how many of the keys exist."""
        count = 0
        now = time.time()
        for key in keys:
            if key in self.cache:
                node = self.cache[key]
                if node.expire_at and now > node.expire_at:
                    # Cleanup expired
                    self._remove(node)
                    del self.cache[key]
                    self.expires.discard(key)
                else:
                    count += 1
        return count

    def keys(self) -> List[bytes]:
        """Returns all valid (unexpired) keys."""
        now = time.time()
        valid_keys = []
        for k, node in self.cache.items():
            if node.expire_at and now > node.expire_at:
                continue
            valid_keys.append(k)
        return valid_keys

    def _get_or_create_node(self, key: bytes, default_val: Any) -> Node:
        if key in self.cache:
            node = self.cache[key]
            if node.expire_at and time.time() > node.expire_at:
                self._remove(node)
                del self.cache[key]
                self.expires.discard(key)
            else:
                self._remove(node)
                self._add(node)
                return node

        if len(self.cache) >= self.capacity:
            lru = self.head.next
            self._remove(lru)
            del self.cache[lru.key]
            self.expires.discard(lru.key)

        new_node = Node(key, default_val)
        self._add(new_node)
        self.cache[key] = new_node
        return new_node

    # --- List Commands ---
    def lpush(self, key: bytes, values: List[bytes]) -> int:
        node = self._get_or_create_node(key, collections.deque())
        if not isinstance(node.value, collections.deque):
            raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
        for val in values:
            node.value.appendleft(val)
        return len(node.value)

    def rpush(self, key: bytes, values: List[bytes]) -> int:
        node = self._get_or_create_node(key, collections.deque())
        if not isinstance(node.value, collections.deque):
            raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
        for val in values:
            node.value.append(val)
        return len(node.value)

    def lpop(self, key: bytes) -> Optional[bytes]:
        if key in self.cache:
            node = self.cache[key]
            if not isinstance(node.value, collections.deque):
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
            if node.value:
                val = node.value.popleft()
                if not node.value: # Delete if empty
                    self.delete([key])
                return val
        return None

    def rpop(self, key: bytes) -> Optional[bytes]:
        if key in self.cache:
            node = self.cache[key]
            if not isinstance(node.value, collections.deque):
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
            if node.value:
                val = node.value.pop()
                if not node.value: # Delete if empty
                    self.delete([key])
                return val
        return None

    def lrange(self, key: bytes, start: int, stop: int) -> List[bytes]:
        if key in self.cache:
            node = self.cache[key]
            if not isinstance(node.value, collections.deque):
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
            
            lst = list(node.value)
            if stop == -1 or stop >= len(lst):
                stop = len(lst) - 1
            if start < 0:
                start = len(lst) + start
            if stop < 0:
                stop = len(lst) + stop + 1
            else:
                stop += 1
            return lst[start:stop]
        return []

    # --- Hash Commands ---
    def hset(self, key: bytes, field: bytes, value: bytes) -> int:
        node = self._get_or_create_node(key, {})
        if not isinstance(node.value, dict):
            raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
        
        is_new = 1 if field not in node.value else 0
        node.value[field] = value
        return is_new

    def hget(self, key: bytes, field: bytes) -> Optional[bytes]:
        if key in self.cache:
            node = self.cache[key]
            if not isinstance(node.value, dict):
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
            return node.value.get(field)
        return None

    def hgetall(self, key: bytes) -> List[bytes]:
        if key in self.cache:
            node = self.cache[key]
            if not isinstance(node.value, dict):
                raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
            
            res = []
            for k, v in node.value.items():
                res.extend([k, v])
            return res
        return []

    # --- Atomic Counters ---
    def incr(self, key: bytes, amount: int = 1) -> int:
        node = self._get_or_create_node(key, b"0")
        if not isinstance(node.value, bytes):
            raise TypeError("WRONGTYPE Operation against a key holding the wrong kind of value")
        
        try:
            val = int(node.value)
        except ValueError:
            raise ValueError("ERR value is not an integer or out of range")
            
        val += amount
        node.value = str(val).encode()
        return val

    def decr(self, key: bytes, amount: int = 1) -> int:
        return self.incr(key, -amount)

    # --- RDB Snapshotting ---
    def save_snapshot(self, filepath: str = "essacache.rdb"):
        import pickle
        import os
        now = time.time()
        data = {}
        for k, node in self.cache.items():
            if node.expire_at and now > node.expire_at:
                continue
            data[k] = {
                'value': node.value,
                'expire_at': node.expire_at
            }
        
        temp_path = filepath + ".tmp"
        with open(temp_path, 'wb') as f:
            pickle.dump(data, f)
        os.replace(temp_path, filepath)

    def load_snapshot(self, filepath: str = "essacache.rdb"):
        import pickle
        import os
        if not os.path.exists(filepath):
            return
            
        with open(filepath, 'rb') as f:
            try:
                data = pickle.load(f)
            except Exception:
                return

        self.cache.clear()
        self.expires.clear()
        self.head.next = self.tail
        self.tail.prev = self.head

        now = time.time()
        for k, v_dict in data.items():
            if v_dict['expire_at'] and now > v_dict['expire_at']:
                continue
            node = Node(k, v_dict['value'], v_dict['expire_at'])
            self._add(node)
            self.cache[k] = node
            if v_dict['expire_at'] is not None:
                self.expires.add(k)
