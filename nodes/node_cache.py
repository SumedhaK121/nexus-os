"""NEXUS-OS Node-Level Block Cache.
Provides per-node in-memory block caching with configurable eviction policies
(LRU, FIFO, and Optimal), thread-safety, and persistent access trace logging.
Concept: Linux page cache / buffer cache (fs/buffer.c) and virtual memory page replacement.
"""

import collections
import json
import os
import threading
import time


class NodeBlockCache:
    """In-memory block cache with access tracing to logs/access_trace.jsonl."""

    def __init__(self, node_id, capacity=4, policy="LRU", trace_path=None):
        self.node_id = node_id
        self.capacity = max(1, int(capacity))
        self.policy = policy.upper()
        self.lock = threading.Lock()

        # Cache storage: block_id -> data_bytes
        self._cache = collections.OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = []

        # Access trace log
        if trace_path is None:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logs_dir = os.path.join(root, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            self.trace_path = os.path.join(logs_dir, "access_trace.jsonl")
        else:
            self.trace_path = trace_path
            os.makedirs(os.path.dirname(os.path.abspath(trace_path)), exist_ok=True)

    def _log_trace(self, block_id, op, hit):
        entry = {
            "timestamp": round(time.time(), 4),
            "node_id": self.node_id,
            "block_id": block_id,
            "op": op,
            "hit": hit,
            "policy": self.policy,
            "capacity": self.capacity,
        }
        try:
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def get(self, block_id):
        """Retrieve block from cache if present. Returns bytes or None."""
        with self.lock:
            if block_id in self._cache:
                self.hits += 1
                if self.policy == "LRU":
                    self._cache.move_to_end(block_id)
                data = self._cache[block_id]
                self._log_trace(block_id, op="read", hit=True)
                return data

            self.misses += 1
            self._log_trace(block_id, op="read", hit=False)
            return None

    def put(self, block_id, data_bytes, future_refs=None):
        """Stores a block into the cache, performing eviction if capacity exceeded."""
        with self.lock:
            hit = block_id in self._cache
            if hit:
                self.hits += 1
                if self.policy == "LRU":
                    self._cache.move_to_end(block_id)
                self._cache[block_id] = data_bytes
                self._log_trace(block_id, op="write", hit=True)
                return

            # Eviction required if full
            if len(self._cache) >= self.capacity:
                self._evict(future_refs)

            self._cache[block_id] = data_bytes
            self._log_trace(block_id, op="write", hit=False)

    def _evict(self, future_refs=None):
        """Evicts a block according to configured policy (LRU, FIFO, or Optimal)."""
        if not self._cache:
            return

        if self.policy == "FIFO":
            evicted_id, _ = self._cache.popitem(last=False)
        elif self.policy == "OPTIMAL" and future_refs:
            # Belady's Optimal: evict the page that will not be used for the longest period
            keys = list(self._cache.keys())
            farthest_idx = -1
            victim = keys[0]
            for k in keys:
                if k not in future_refs:
                    victim = k
                    break
                else:
                    idx = future_refs.index(k)
                    if idx > farthest_idx:
                        farthest_idx = idx
                        victim = k
            del self._cache[victim]
            evicted_id = victim
        else:
            # LRU default
            evicted_id, _ = self._cache.popitem(last=False)

        self.evictions.append(evicted_id)
        if len(self.evictions) > 20:
            self.evictions.pop(0)

    def invalidate(self, block_id):
        """Evicts a specific block (e.g. upon block delete or corruption)."""
        with self.lock:
            self._cache.pop(block_id, None)

    def clear(self):
        with self.lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions.clear()

    def set_config(self, capacity=None, policy=None):
        with self.lock:
            if capacity is not None:
                self.capacity = max(1, int(capacity))
                while len(self._cache) > self.capacity:
                    self._evict()
            if policy is not None:
                self.policy = policy.upper()

    def stats(self):
        with self.lock:
            total = self.hits + self.misses
            rate = round(100.0 * self.hits / total, 1) if total > 0 else 0.0
            return {
                "node_id": self.node_id,
                "policy": self.policy,
                "capacity": self.capacity,
                "size": len(self._cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": rate,
                "cached_blocks": list(self._cache.keys()),
                "recent_evictions": list(self.evictions[-5:]),
            }
