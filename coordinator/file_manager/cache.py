from collections import OrderedDict

class Cache:
    """Page-replacement style file cache. policy = LRU | FIFO."""
    def __init__(self, capacity=3, policy="LRU"):
        self.cap, self.policy, self.d, self.hits, self.misses, self.evicted = capacity, policy.upper(), OrderedDict(), 0, 0, []
    def get(self, k):
        if k in self.d:
            self.hits += 1
            if self.policy == "LRU": self.d.move_to_end(k)
            return self.d[k]
        self.misses += 1; return None
    def put(self, k, v):
        if k in self.d and self.policy == "LRU": self.d.move_to_end(k)
        self.d[k] = v
        while len(self.d) > self.cap: self.evicted.append(self.d.popitem(last=False)[0])
    def remove(self, k): self.d.pop(k, None)
    def stats(self):
        t = self.hits + self.misses
        return {"policy": self.policy, "capacity": self.cap, "hits": self.hits, "misses": self.misses,
                "rate": round(100 * self.hits / t) if t else 0, "keys": list(self.d), "evicted": self.evicted[-5:]}
