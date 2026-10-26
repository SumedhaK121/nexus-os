"""NEXUS-OS Distributed File System Metadata Store.
Persists directory hierarchy, POSIX-style permissions, file versions,
and block replica mappings into SQLite (database/metadata.db).
Concept: NameNode metadata management with persistent write-ahead logging (HDFS NameNode fsimage/edits).
"""

import json
import os
import sqlite3
import threading
import time


class DfsMetadataStore:
    def __init__(self, db_path=None):
        if db_path is None:
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(root, "database")
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, "metadata.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self.lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inodes (
                    path TEXT PRIMARY KEY,
                    is_dir INTEGER NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    owner TEXT NOT NULL DEFAULT 'root',
                    perms INTEGER NOT NULL DEFAULT 493,
                    version INTEGER NOT NULL DEFAULT 1,
                    created REAL NOT NULL,
                    modified REAL NOT NULL,
                    checksum TEXT DEFAULT '',
                    vector_clock TEXT DEFAULT '{}'
                )
            """)
            cur.execute("PRAGMA table_info(inodes)")
            cols = [r[1] for r in cur.fetchall()]
            if 'vector_clock' not in cols:
                cur.execute("ALTER TABLE inodes ADD COLUMN vector_clock TEXT DEFAULT '{}'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    block_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    FOREIGN KEY(path) REFERENCES inodes(path) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS block_replicas (
                    block_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'HEALTHY',
                    PRIMARY KEY(block_id, node_id),
                    FOREIGN KEY(block_id) REFERENCES blocks(block_id) ON DELETE CASCADE
                )
            """)
            # Ensure root directory "/" exists
            cur.execute("SELECT path FROM inodes WHERE path = '/'")
            if not cur.fetchone():
                now = time.time()
                cur.execute(
                    "INSERT INTO inodes (path, is_dir, size, owner, perms, version, created, modified, checksum, vector_clock) VALUES ('/', 1, 0, 'root', ?, 1, ?, ?, '', '{}')",
                    (0o777, now, now)
                )
            conn.commit()
            conn.close()

    @staticmethod
    def _norm(path):
        """Normalize posix path."""
        p = "/" + "/".join(segment for segment in path.replace("\\", "/").split("/") if segment)
        return p

    def check_permission(self, path, user="root", mode="r"):
        """Enforces POSIX permissions: owner, group, other."""
        if user == "root":
            return True
        meta = self.get_inode(path)
        if not meta:
            return True
        perms = meta["perms"]
        is_owner = (meta["owner"] == user)
        # Shift: owner (6), group (3), other (0)
        shift = 6 if is_owner else 0
        mask = 0
        if "r" in mode: mask |= 4
        if "w" in mode: mask |= 2
        if "x" in mode: mask |= 1
        needed = mask << shift
        return (perms & needed) == needed

    def mkdir(self, path, owner="root", perms=0o755, parents=True):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (path,))
            row = cur.fetchone()
            if row:
                conn.close()
                return False, "Directory or file already exists"

            now = time.time()
            segments = [s for s in path.strip("/").split("/")[:-1] if s]
            if parents:
                accum = ""
                for seg in segments:
                    accum += "/" + seg
                    cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (accum,))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO inodes (path, is_dir, size, owner, perms, version, created, modified, checksum, vector_clock) VALUES (?, 1, 0, ?, ?, 1, ?, ?, '', '{}')",
                            (accum, owner, perms, now, now)
                        )
            else:
                parent = "/" + "/".join(segments)
                if parent != "/" and parent != "":
                    parent_norm = self._norm(parent)
                    cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (parent_norm,))
                    p_row = cur.fetchone()
                    if not p_row or not p_row["is_dir"]:
                        conn.close()
                        return False, f"Parent directory {parent_norm} does not exist"

            cur.execute(
                "INSERT INTO inodes (path, is_dir, size, owner, perms, version, created, modified, checksum, vector_clock) VALUES (?, 1, 0, ?, ?, 1, ?, ?, '', '{}')",
                (path, owner, perms, now, now)
            )
            conn.commit()
            conn.close()
            return True, path

    def ls(self, path):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inodes WHERE path = ?", (path,))
            target = cur.fetchone()
            if not target:
                conn.close()
                return None
            if not target["is_dir"]:
                conn.close()
                return [dict(target)]

            # Query direct children
            prefix = path if path != "/" else ""
            cur.execute("SELECT * FROM inodes WHERE path != ? ORDER BY path", (path,))
            rows = cur.fetchall()
            conn.close()

            children = []
            for r in rows:
                p = r["path"]
                if p.startswith(prefix + "/"):
                    rel = p[len(prefix) + 1:]
                    if "/" not in rel:
                        d = dict(r)
                        d["name"] = rel
                        children.append(d)
            return children

    def rmdir(self, path):
        path = self._norm(path)
        if path == "/":
            return False, "Cannot delete root directory"
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (path,))
            row = cur.fetchone()
            if not row or not row["is_dir"]:
                conn.close()
                return False, "Not a directory"

            # Check if directory has contents
            prefix = path + "/"
            cur.execute("SELECT path FROM inodes WHERE path LIKE ? LIMIT 1", (prefix + "%",))
            if cur.fetchone():
                conn.close()
                return False, "Directory not empty"

            cur.execute("DELETE FROM inodes WHERE path = ?", (path,))
            conn.commit()
            conn.close()
            return True, "Directory removed"

    def get_inode(self, path):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inodes WHERE path = ?", (path,))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None

    def chmod(self, path, perms):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE inodes SET perms = ?, modified = ? WHERE path = ?", (int(perms), time.time(), path))
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0

    def rename(self, src, dst):
        src = self._norm(src)
        dst = self._norm(dst)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inodes WHERE path = ?", (src,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return False, "Source path does not exist"

            cur.execute("SELECT * FROM inodes WHERE path = ?", (dst,))
            if cur.fetchone():
                conn.close()
                return False, "Destination path already exists"

            # Check if parent directory of dst exists
            dst_parent = "/" + "/".join([s for s in dst.strip("/").split("/")[:-1] if s])
            if dst_parent != "/" and dst_parent != "":
                cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (dst_parent,))
                p_row = cur.fetchone()
                if not p_row or not p_row["is_dir"]:
                    conn.close()
                    return False, f"Parent directory {dst_parent} does not exist"

            now = time.time()
            is_dir = bool(row["is_dir"])
            cur.execute("UPDATE inodes SET path = ?, modified = ? WHERE path = ?", (dst, now, src))
            cur.execute("UPDATE blocks SET path = ? WHERE path = ?", (dst, src))

            if is_dir:
                src_prefix = src.rstrip("/") + "/"
                dst_prefix = dst.rstrip("/") + "/"
                cur.execute("SELECT path FROM inodes WHERE path LIKE ?", (src_prefix + "%",))
                child_rows = cur.fetchall()
                for cr in child_rows:
                    old_child = cr["path"]
                    new_child = dst_prefix + old_child[len(src_prefix):]
                    cur.execute("UPDATE inodes SET path = ? WHERE path = ?", (new_child, old_child))
                    cur.execute("UPDATE blocks SET path = ? WHERE path = ?", (new_child, old_child))

            conn.commit()
            conn.close()
            return True, dst

    def put_file_metadata(self, path, size, blocks_info, owner="root", perms=0o644, checksum="", vector_clock=None):
        """Records file inode and its associated block mappings."""
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            now = time.time()

            # Ensure parent directories exist
            segments = [s for s in path.strip("/").split("/")[:-1] if s]
            accum = ""
            for seg in segments:
                accum += "/" + seg
                cur.execute("SELECT is_dir FROM inodes WHERE path = ?", (accum,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO inodes (path, is_dir, size, owner, perms, version, created, modified, checksum, vector_clock) VALUES (?, 1, 0, ?, ?, 1, ?, ?, '', '{}')",
                        (accum, owner, 0o755, now, now)
                    )

            cur.execute("SELECT version FROM inodes WHERE path = ?", (path,))
            row = cur.fetchone()
            version = (row["version"] + 1) if row else 1

            if row:
                vc_str = json.dumps(vector_clock) if isinstance(vector_clock, dict) else (str(vector_clock) if vector_clock else "{}")
                cur.execute(
                    "UPDATE inodes SET size = ?, version = ?, modified = ?, checksum = ?, vector_clock = ? WHERE path = ?",
                    (size, version, now, checksum, vc_str, path)
                )
                # Remove old block mappings
                cur.execute("SELECT block_id FROM blocks WHERE path = ?", (path,))
                old_blocks = [r["block_id"] for r in cur.fetchall()]
                for b_id in old_blocks:
                    cur.execute("DELETE FROM block_replicas WHERE block_id = ?", (b_id,))
                cur.execute("DELETE FROM blocks WHERE path = ?", (path,))
            else:
                vc_str = json.dumps(vector_clock) if isinstance(vector_clock, dict) else (str(vector_clock) if vector_clock else "{}")
                cur.execute(
                    "INSERT INTO inodes (path, is_dir, size, owner, perms, version, created, modified, checksum, vector_clock) VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (path, size, owner, perms, version, now, now, checksum, vc_str)
                )

            # Insert blocks and replicas
            for seq, b in enumerate(blocks_info):
                b_id = b["block_id"]
                cur.execute(
                    "INSERT INTO blocks VALUES (?, ?, ?, ?, ?)",
                    (b_id, path, seq, b["size"], b["checksum"])
                )
                for nid in b.get("nodes", []):
                    cur.execute(
                        "INSERT OR REPLACE INTO block_replicas VALUES (?, ?, 'HEALTHY')",
                        (b_id, nid)
                    )

            conn.commit()
            conn.close()
            return version

    def get_file_metadata(self, path):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inodes WHERE path = ? AND is_dir = 0", (path,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            res = dict(row)
            vc_val = res.get("vector_clock", "{}")
            if isinstance(vc_val, str):
                try:
                    res["vector_clock"] = json.loads(vc_val)
                except Exception:
                    res["vector_clock"] = {}
            elif isinstance(vc_val, dict):
                res["vector_clock"] = vc_val
            else:
                res["vector_clock"] = {}

            # Fetch blocks in sequence
            cur.execute("SELECT * FROM blocks WHERE path = ? ORDER BY seq", (path,))
            blocks = []
            for b_row in cur.fetchall():
                b = dict(b_row)
                cur.execute("SELECT node_id, status FROM block_replicas WHERE block_id = ?", (b["block_id"],))
                rep_rows = cur.fetchall()
                b["replicas"] = {r["node_id"]: r["status"] for r in rep_rows}
                b["nodes"] = [r["node_id"] for r in rep_rows if r["status"] == "HEALTHY"]
                b["all_nodes"] = [r["node_id"] for r in rep_rows]
                blocks.append(b)
            res["blocks"] = blocks
            conn.close()
            return res

    def delete_file_metadata(self, path):
        path = self._norm(path)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT block_id FROM blocks WHERE path = ?", (path,))
            blocks = [r["block_id"] for r in cur.fetchall()]
            for b_id in blocks:
                cur.execute("DELETE FROM block_replicas WHERE block_id = ?", (b_id,))
            cur.execute("DELETE FROM blocks WHERE path = ?", (path,))
            cur.execute("DELETE FROM inodes WHERE path = ?", (path,))
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0, blocks

    def mark_node_offline(self, node_id):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE block_replicas SET status = 'OFFLINE' WHERE node_id = ?", (node_id,))
            conn.commit()
            conn.close()

    def mark_node_online(self, node_id):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE block_replicas SET status = 'HEALTHY' WHERE node_id = ?", (node_id,))
            conn.commit()
            conn.close()

    def get_under_replicated_blocks(self, desired_k=2):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT b.block_id, b.path, b.seq, b.size, b.checksum,
                       COUNT(CASE WHEN r.status = 'HEALTHY' THEN 1 END) as healthy_count
                FROM blocks b
                LEFT JOIN block_replicas r ON b.block_id = r.block_id
                GROUP BY b.block_id
                HAVING healthy_count < ?
            """, (desired_k,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                cur.execute("SELECT node_id FROM block_replicas WHERE block_id = ? AND status = 'HEALTHY'", (r["block_id"],))
                r["healthy_nodes"] = [x["node_id"] for x in cur.fetchall()]
            conn.close()
            return rows

    def add_block_replica(self, block_id, node_id, status="HEALTHY"):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO block_replicas VALUES (?, ?, ?)", (block_id, node_id, status))
            conn.commit()
            conn.close()

    def remove_block_replica(self, block_id, node_id):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM block_replicas WHERE block_id = ? AND node_id = ?", (block_id, node_id))
            conn.commit()
            conn.close()

    def get_all_files(self):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM inodes WHERE is_dir = 0")
            files = [dict(r) for r in cur.fetchall()]
            conn.close()
            return files

    def get_node_block_counts(self):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT node_id, COUNT(*) as count
                FROM block_replicas
                WHERE status = 'HEALTHY'
                GROUP BY node_id
            """)
            counts = {r["node_id"]: r["count"] for r in cur.fetchall()}
            conn.close()
            return counts
