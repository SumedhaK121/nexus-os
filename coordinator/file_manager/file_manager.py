import os, time
from coordinator.file_manager.cache import Cache
from coordinator.replication.replication_manager import ReplicationManager
from coordinator.synchronization.readers_writers import RWLock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class FileManager:
    """Distributed file store: versioning + replication + cache, guarded by a readers-writers lock."""
    def __init__(self, cache_size=3, policy="LRU"):
        self.dir = os.path.join(ROOT, "storage", "documents"); os.makedirs(self.dir, exist_ok=True)
        self.meta, self.rw, self.cache, self.rep = {}, RWLock(), Cache(cache_size, policy), ReplicationManager(ROOT)
    def write(self, name, content, nodes, base=None):
        name = os.path.basename(name) or "untitled.txt"; self.rw.acquire_write()
        try:
            if base is not None and name in self.meta and base != self.meta[name]["version"]:
                return {"conflict": True, "name": name, "current": self.meta[name]["version"]}
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f: f.write(content)
            m = self.meta.setdefault(name, {"version": 0}); m.update(version=m["version"] + 1, size=len(content), modified=time.time())
            m["nodes"] = self.rep.replicate(name, content, m["version"], nodes); self.cache.put(name, content)
            return {"name": name, **m}
        finally: self.rw.release_write()
    def read(self, name):
        name = os.path.basename(name)
        if name not in self.meta: return None
        self.rw.acquire_read()
        try:
            v, src = self.cache.get(name), "cache"
            if v is None:
                src = "disk"
                with open(os.path.join(self.dir, name), encoding="utf-8") as f:
                    v = f.read()
                self.cache.put(name, v)
            return {"name": name, "content": v, "source": src, **self.meta[name]}
        finally: self.rw.release_read()
    def delete(self, name):
        name = os.path.basename(name); self.rw.acquire_write()
        try:
            if name not in self.meta: return False
            os.remove(os.path.join(self.dir, name)); self.meta.pop(name); self.cache.remove(name); self.rep.remove(name); return True
        finally: self.rw.release_write()
    def listing(self): return {n: dict(m) for n, m in self.meta.items()}

    def verify(self, repair=False, corrupt=None):
        rd = os.path.join(ROOT, "storage", "replicas")
        if corrupt in self.meta:
            with open(os.path.join(rd, self.rep.placement[corrupt][0], corrupt), "w") as f: f.write("CORRUPTED")
        out = {}
        for name in self.meta:
            good, out[name] = open(os.path.join(self.dir, name), encoding="utf-8").read(), {}
            for n in self.rep.placement.get(name, []):
                p = os.path.join(rd, n, name); ok = os.path.exists(p) and open(p, encoding="utf-8").read() == good
                if not ok and repair:
                    with open(p, "w", encoding="utf-8") as f: f.write(good)
                    ok = "repaired"
                out[name][n] = ok
        return out
