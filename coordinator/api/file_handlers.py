"""NEXUS-OS Distributed File & Namespace API Handlers.
Implements FS_MKDIR, FS_LS, FS_RMDIR, FS_RENAME, FS_MOVE, FS_STAT, FS_CHMOD,
FS_WRITE, FS_READ, FS_DELETE, FS_SCRUB, CACHE_REPLAY, BELADY_DEMO,
alongside backward-compatible FILE_* handlers.
Concept: Distributed NameNode filesystem operations and block placement (HDFS/GFS) + Virtual Memory Page Replacement.
"""

import os
from coordinator.file_manager.cache import Cache
from coordinator.file_manager.page_replacement import (
    simulate as page_sim,
    beladys_anomaly_demo,
    replay_trace,
)
from coordinator.node_manager import node_manager


def register(coord):
    online = lambda: node_manager.online(coord.nodes)

    # ------------------ Advanced DFS Operations ------------------

    @coord.handler("FS_MKDIR")
    def _fs_mkdir(c, ctx, m):
        user = m.get("user", "root")
        perms = int(m.get("perms", 0o755))
        ok, res = c.dfs.meta.mkdir(m["path"], owner=user, perms=perms)
        if ok:
            c.log("dfs", f"mkdir {res} by {user}")
            return {"type": "OK", "path": res}
        return {"type": "ERROR", "error": res}

    @coord.handler("FS_LS")
    def _fs_ls(c, ctx, m):
        path = m.get("path", "/")
        entries = c.dfs.meta.ls(path)
        if entries is None:
            return {"type": "ERROR", "error": f"Path {path} not found"}
        return {"type": "FS_LS_RESULT", "path": path, "entries": entries}

    @coord.handler("FS_RMDIR")
    def _fs_rmdir(c, ctx, m):
        ok, msg = c.dfs.meta.rmdir(m["path"])
        if ok:
            c.log("dfs", f"rmdir {m['path']}")
            return {"type": "OK", "path": m["path"]}
        return {"type": "ERROR", "error": msg}

    @coord.handler("FS_STAT")
    def _fs_stat(c, ctx, m):
        path = m["path"]
        meta = c.dfs.meta.get_file_metadata(path) or c.dfs.meta.get_inode(path)
        if not meta:
            return {"type": "ERROR", "error": f"Path {path} not found"}
        return {"type": "FS_STAT_RESULT", "stat": meta}

    @coord.handler("FS_CHMOD")
    def _fs_chmod(c, ctx, m):
        path = m["path"]
        perms = int(m["perms"])
        user = m.get("user", "root")
        if not c.dfs.meta.check_permission(path, user=user, mode="w"):
            return {"type": "ERROR", "error": "Permission denied"}
        ok = c.dfs.meta.chmod(path, perms)
        if ok:
            c.log("dfs", f"chmod {oct(perms)} on {path}")
            return {"type": "OK", "path": path, "perms": perms}
        return {"type": "ERROR", "error": "Failed to chmod"}

    @coord.handler("FS_RENAME")
    @coord.handler("FS_MOVE")
    def _fs_rename(c, ctx, m):
        src = m["src"]
        dst = m["dst"]
        user = m.get("user", "root")
        if not c.dfs.meta.check_permission(src, user=user, mode="w"):
            return {"type": "ERROR", "error": "Permission denied on source"}
        ok, res = c.dfs.meta.rename(src, dst)
        if ok:
            c.log("dfs", f"renamed {src} -> {dst}")
            return {"type": "OK", "src": src, "dst": dst}
        return {"type": "ERROR", "error": res}

    @coord.handler("FS_WRITE")
    def _fs_write(c, ctx, m):
        path = m.get("path") or m.get("name")
        content = m.get("content", "")
        user = m.get("user", "root")
        base = m.get("base")
        nodes_list = online()
        res = c.dfs.write_file(path, content, nodes_list, user=user, base=base)
        if res.get("conflict"):
            c.log("dfs", f"CONFLICT on {res['path']}: base v{base} != current v{res['current']}")
            return res
        if res.get("type") == "ERROR":
            return res
        c.log("dfs", f"{res['path']} v{res['version']} written across {res['blocks']} block(s) on {res['nodes']}")
        return res

    @coord.handler("FS_READ")
    def _fs_read(c, ctx, m):
        path = m.get("path") or m.get("name")
        user = m.get("user", "root")
        res = c.dfs.read_file(path, user=user)
        if not res:
            return {"type": "ERROR", "error": f"File {path} not found"}
        if res.get("type") == "ERROR":
            return res
        c.log("dfs", f"{path} v{res['version']} read from {res['blocks']} block(s)")
        return res

    @coord.handler("FS_DELETE")
    def _fs_delete(c, ctx, m):
        path = m.get("path") or m.get("name")
        user = m.get("user", "root")
        ok, msg = c.dfs.delete_file(path, user=user)
        if ok:
            c.log("dfs", f"{path} deleted from cluster")
            return {"type": "OK", "path": path}
        return {"type": "ERROR", "error": msg}

    @coord.handler("FS_SCRUB")
    def _fs_scrub(c, ctx, m):
        repair = m.get("repair", True)
        res = c.dfs.scrub(repair=repair)
        c.log("dfs", f"FS_SCRUB completed: {res['corrupted_detected']} corruptions, {res['repaired']} repaired")
        return res

    # ------------------ Cache & Trace Replay Operations ------------------

    @coord.handler("CACHE_REPLAY")
    def _cr(c, ctx, m):
        trace_path = m.get("trace_path")
        if not trace_path:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            trace_path = os.path.join(root, "logs", "access_trace.jsonl")
        refs = m.get("refs") or trace_path
        frame_sizes = m.get("frame_sizes", [2, 3, 4])
        res = replay_trace(refs, frame_sizes=frame_sizes)
        c.log("cache", f"CACHE_REPLAY evaluated on {res['reference_count']} references")
        return res

    @coord.handler("BELADY_DEMO")
    def _bd(c, ctx, m):
        res = beladys_anomaly_demo()
        c.log("cache", "Belady's anomaly evaluated: FIFO 3 frames vs 4 frames")
        return res

    # ------------------ Backward Compatible FILE_* Operations ------------------

    @coord.handler("FILE_WRITE")
    def _w(c, ctx, m):
        # Write to legacy file manager
        r = c.files.write(m["name"], m.get("content", ""), online(), m.get("base"))
        if r.get("conflict"):
            c.log("files", f"CONFLICT on {r['name']}: base v{m.get('base')} but current v{r['current']}")
            return {"type": "CONFLICT", **r}
        # Also sync to DFS under root directory /<name>
        if hasattr(c, "dfs"):
            try:
                c.dfs.write_file("/" + m["name"], m.get("content", ""), online(), base=m.get("base"))
            except Exception:
                pass
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
        if hasattr(c, "dfs"):
            try:
                c.dfs.delete_file("/" + m["name"])
            except Exception:
                pass
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
