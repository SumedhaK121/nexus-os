"""NEXUS-OS Distributed File & Cache API Handlers.
Implements FILE_WRITE, FILE_READ, FILE_DELETE, CACHE_CONFIG, CACHE_SIM, FILE_VERIFY.
Concept: Distributed file storage, optimistic concurrency control, replication, and caching.
"""

from coordinator.file_manager.cache import Cache
from coordinator.file_manager.page_replacement import simulate as page_sim
from coordinator.node_manager import node_manager


def register(coord):
    online = lambda: node_manager.online(coord.nodes)

    @coord.handler("FILE_WRITE")
    def _w(c, ctx, m):
        r = c.files.write(m["name"], m.get("content", ""), online(), m.get("base"))
        if r.get("conflict"):
            c.log("files", f"CONFLICT on {r['name']}: base v{m.get('base')} but current v{r['current']}")
            return {"type": "CONFLICT", **r}
        c.log("files", f"{r['name']} v{r['version']} written, replicas on {r['nodes']}")
        return {"type": "FILE_OK", **r}

    @coord.handler("FILE_READ")
    def _r(c, ctx, m):
        r = c.files.read(m["name"])
        if not r:
            return {"type": "ERROR", "error": "file not found"}
        c.log("files", f"{r['name']} read from {r['source'].upper()}")
        return {"type": "FILE_OK", **r}

    @coord.handler("FILE_DELETE")
    def _d(c, ctx, m):
        ok = c.files.delete(m["name"])
        c.log("files", f"{m['name']} deleted" if ok else f"delete failed: {m['name']}")
        return {"type": "FILE_OK" if ok else "ERROR", "error": "file not found"}

    @coord.handler("CACHE_CONFIG")
    def _cc(c, ctx, m):
        c.files.cache = Cache(int(m["capacity"]), m["policy"])
        c.log("cache", f"policy={m['policy']} capacity={m['capacity']}")
        return {"type": "OK"}

    @coord.handler("CACHE_SIM")
    def _cs(c, ctx, m):
        return {"type": "CACHE_SIM", "results": page_sim(m["refs"], max(1, int(m["frames"])))}

    @coord.handler("FILE_VERIFY")
    def _fv(c, ctx, m):
        r = c.files.verify(m.get("repair", False), m.get("corrupt"))
        if m.get("corrupt"):
            c.log("sync", f"replica of {m['corrupt']} corrupted (demo)")
        if m.get("repair"):
            c.log("sync", "replicas repaired from primary copy")
        return {"type": "VERIFY", "result": r}
