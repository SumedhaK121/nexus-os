"""NEXUS-OS Distributed Sync Manager (Dropbox-Lite Engine).
Coordinates file synchronization, rsync-style incremental delta chunk transfers,
vector clock concurrency evaluation, conflicted copy generation, and transfer scheduling.
Concept: Distributed File Synchronization (Dropbox, Syncthing, rsync, DynamoDB version vectors).
"""

import hashlib
import json
import os
import threading
import time

from distributed_clock.vector_clock import VectorClock


class SyncManager:
    """Cluster-side manager for Dropbox-Lite folder synchronization."""

    def __init__(self, coord=None):
        self.coord = coord
        self.lock = threading.Lock()
        self.policy = "SJF"  # Default transfer scheduling policy: Shortest Job First
        self.metrics = {
            "bytes_transferred": 0,
            "bytes_saved": 0,
            "full_bytes": 0,
            "conflicts_detected": 0,
            "total_syncs": 0,
            "transfers": [],
        }

    def check_chunks(self, path, chunk_checksums):
        """Compares client chunk checksums with current DFS block checksums.
        Returns missing chunk indices that need to be transmitted (rsync delta).
        """
        path = "/" + "/".join(segment for segment in path.replace("\\", "/").split("/") if segment)
        meta = self.coord.dfs.meta.get_file_metadata(path) if hasattr(self.coord, "dfs") else None

        if not meta or not meta.get("blocks"):
            return {
                "exists": False,
                "version": 0,
                "vector_clock": {},
                "missing_indices": list(range(len(chunk_checksums))),
                "total_chunks": len(chunk_checksums),
            }

        existing_checksums = [b["checksum"] for b in meta["blocks"]]
        missing_indices = []
        for i, chk in enumerate(chunk_checksums):
            if i >= len(existing_checksums) or existing_checksums[i] != chk:
                missing_indices.append(i)

        return {
            "exists": True,
            "version": meta.get("version", 1),
            "vector_clock": meta.get("vector_clock", {}),
            "missing_indices": missing_indices,
            "total_chunks": len(chunk_checksums),
        }

    def sync_push(self, path, content, chunks_data, full_size, file_checksum, node_id, new_vc, base_vc=None, base_version=None):
        """Processes incoming file sync from worker node.
        Performs Vector Clock concurrency evaluation:
        - If new_vc dominates current_vc (happens-before / BEFORE): Fast-forward update.
        - If new_vc and current_vc are CONCURRENT: Create a conflicted copy!
        """
        path = "/" + "/".join(segment for segment in path.replace("\\", "/").split("/") if segment)
        with self.lock:
            existing = self.coord.dfs.meta.get_file_metadata(path) if hasattr(self.coord, "dfs") else None

            if existing:
                cur_vc = existing.get("vector_clock", {})
                rel = VectorClock.compare(cur_vc, new_vc)

                # Case 1: CONCURRENT CONFLICT
                if rel == VectorClock.REL_CONCURRENT:
                    self.metrics["conflicts_detected"] += 1
                    lamport_t = self.coord.clock.t if hasattr(self.coord, "clock") else int(time.time())
                    dir_part, filename = os.path.split(path)
                    stem, ext = os.path.splitext(filename)
                    conflict_filename = f"{stem} (conflict {node_id} T={lamport_t}){ext}"
                    conflict_path = f"{dir_part.rstrip('/')}/{conflict_filename}"
                    if not conflict_path.startswith("/"):
                        conflict_path = "/" + conflict_path

                    raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
                    write_res = self.coord.dfs.write_file(conflict_path, raw_bytes, user="root", vector_clock=new_vc)

                    self.coord.log("sync", f"Conflict detected on {path}: created conflicted copy {conflict_filename}")

                    return {
                        "type": "SYNC_CONFLICT",
                        "conflict": True,
                        "conflict_file": conflict_path,
                        "conflict_filename": conflict_filename,
                        "base_file": path,
                        "current_vc": cur_vc,
                        "incoming_vc": new_vc,
                        "version": write_res.get("version", 1),
                    }

                # Case 2: Outdated update (current is causally newer)
                if rel == VectorClock.REL_AFTER:
                    return {
                        "type": "SYNC_OUTDATED",
                        "error": "Incoming sync is causally older than cluster copy",
                        "current_vc": cur_vc,
                        "incoming_vc": new_vc,
                    }

            # Case 3: Fast-forward / Fresh creation
            raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
            write_res = self.coord.dfs.write_file(path, raw_bytes, user="root", vector_clock=new_vc, base=base_version)
            if write_res.get("type") in ("ERROR", "CONFLICT"):
                return write_res

            # Calculate rsync delta savings
            if chunks_data and len(chunks_data) > 0:
                transferred = sum(len(c.get("data", "")) for c in chunks_data)
            else:
                transferred = full_size

            saved = max(0, full_size - transferred)
            self.metrics["bytes_transferred"] += transferred
            self.metrics["bytes_saved"] += saved
            self.metrics["full_bytes"] += full_size
            self.metrics["total_syncs"] += 1
            pct = round((saved / full_size) * 100, 1) if full_size > 0 else 0.0

            rec = {
                "time": time.time(),
                "path": path,
                "node_id": node_id,
                "full_size": full_size,
                "transferred": transferred,
                "saved": saved,
                "savings_pct": pct,
                "version": write_res.get("version", 1),
            }
            self.metrics["transfers"].append(rec)
            self.coord.log("sync", f"{node_id} synced {path}: transferred {transferred}B, saved {saved}B ({pct}% saved)")

            return {
                "type": "SYNC_OK",
                "path": path,
                "version": write_res.get("version", 1),
                "vector_clock": new_vc,
                "bytes_transferred": transferred,
                "bytes_saved": saved,
                "savings_pct": pct,
                "full_size": full_size,
            }

    def sync_pull(self, path):
        """Fetches latest file content and vector clock from DFS."""
        path = "/" + "/".join(segment for segment in path.replace("\\", "/").split("/") if segment)
        read_res = self.coord.dfs.read_file(path) if hasattr(self.coord, "dfs") else None
        if not read_res or read_res.get("type") != "FILE_OK":
            return {"type": "ERROR", "error": f"File {path} not found"}

        meta = self.coord.dfs.meta.get_file_metadata(path)
        return {
            "type": "SYNC_PULL_OK",
            "path": path,
            "content": read_res.get("content", ""),
            "version": read_res.get("version", 1),
            "vector_clock": meta.get("vector_clock", {}) if meta else {},
            "size": read_res.get("size", 0),
            "checksum": read_res.get("checksum", ""),
        }

    def sync_delete(self, path, node_id="client"):
        """Deletes file from cluster sync space."""
        path = "/" + "/".join(segment for segment in path.replace("\\", "/").split("/") if segment)
        res = self.coord.dfs.delete_file(path, user="root") if hasattr(self.coord, "dfs") else {"type": "ERROR"}
        if res.get("type") == "FILE_OK":
            self.coord.log("sync", f"{node_id} deleted synced file {path}")
        return res

    def get_stats(self):
        """Returns aggregated telemetry on sync operations and bandwidth efficiency."""
        with self.lock:
            full = self.metrics["full_bytes"]
            saved = self.metrics["bytes_saved"]
            pct = round((saved / full) * 100, 1) if full > 0 else 0.0
            return {
                "policy": self.policy,
                "total_syncs": self.metrics["total_syncs"],
                "bytes_transferred": self.metrics["bytes_transferred"],
                "bytes_saved": saved,
                "full_bytes": full,
                "savings_pct": pct,
                "conflicts_detected": self.metrics["conflicts_detected"],
                "recent_transfers": self.metrics["transfers"][-10:],
            }

    def run_sync_demo(self):
        """Executes a 4-step demonstration of Dropbox-Lite:
        1. Initial sync of doc.txt by node-1.
        2. Fast-forward edit by node-2 (dominating vector clock).
        3. Concurrency fork & Conflicted Copy generation (node-1 vs node-3 concurrent edits).
        4. Rsync-style incremental delta sync (50% bandwidth saved).
        """
        trace = []
        doc_path = "/sync/project_report.txt"

        # Step 1: Initial creation by node-1
        trace.append("Step 1: node-1 creates /sync/project_report.txt (initial draft)")
        vc1 = {"node-1": 1}
        c1 = "# NEXUS-OS Project Report\nInitial draft by node-1."
        r1 = self.sync_push(doc_path, c1, None, len(c1), hashlib.sha256(c1.encode()).hexdigest(), "node-1", vc1)
        trace.append(f"   node-1 sync result: {r1.get('type')} v{r1.get('version')} (VC: {r1.get('vector_clock')})")

        # Step 2: Fast-forward edit by node-2
        trace.append("Step 2: node-2 pulls file, edits Introduction (causal successor), and syncs")
        vc2 = {"node-1": 1, "node-2": 1}
        c2 = "# NEXUS-OS Project Report\nInitial draft by node-1.\nIntroduction updated by node-2."
        r2 = self.sync_push(doc_path, c2, None, len(c2), hashlib.sha256(c2.encode()).hexdigest(), "node-2", vc2)
        trace.append(f"   node-2 sync result: {r2.get('type')} v{r2.get('version')} (Fast-forward, no conflict)")

        # Step 3: Concurrency Fork
        trace.append("Step 3: Concurrency Fork — node-1 and node-3 edit concurrently offline")
        vc_fork1 = {"node-1": 2, "node-2": 1}
        c_fork1 = c2 + "\nSection A by node-1."
        trace.append("   node-1 syncs Section A first -> succeeds")
        r3_a = self.sync_push(doc_path, c_fork1, None, len(c_fork1), hashlib.sha256(c_fork1.encode()).hexdigest(), "node-1", vc_fork1)
        trace.append(f"   node-1 sync result: {r3_a.get('type')} v{r3_a.get('version')}")

        vc_fork3 = {"node-1": 1, "node-2": 1, "node-3": 1}
        c_fork3 = c2 + "\nSection B by node-3."
        trace.append(f"   node-3 syncs Section B with VC {vc_fork3} (CONCURRENT with cluster VC {vc_fork1})")
        r3_b = self.sync_push(doc_path, c_fork3, None, len(c_fork3), hashlib.sha256(c_fork3.encode()).hexdigest(), "node-3", vc_fork3)
        trace.append(f"   node-3 sync result: {r3_b.get('type')} -> Created: {r3_b.get('conflict_filename')}")

        # Step 4: Rsync incremental delta sync
        trace.append("Step 4: Rsync-style incremental delta transfer demonstration")
        large_path = "/sync/experiment_data.bin"
        chunk_0 = "A" * 65536
        chunk_1 = "B" * 65536
        full_large = chunk_0 + chunk_1
        full_size = len(full_large)
        h0 = hashlib.sha256(chunk_0.encode()).hexdigest()
        h1 = hashlib.sha256(chunk_1.encode()).hexdigest()

        # Initial write of large file
        vc_large = {"node-1": 1}
        self.sync_push(large_path, full_large, None, full_size, hashlib.sha256(full_large.encode()).hexdigest(), "node-1", vc_large)

        # Modify only chunk 1
        chunk_1_mod = "B" * 65500 + "MODIFIED"
        full_mod = chunk_0 + chunk_1_mod
        h1_mod = hashlib.sha256(chunk_1_mod.encode()).hexdigest()

        check_res = self.check_chunks(large_path, [h0, h1_mod])
        missing = check_res.get("missing_indices", [])
        trace.append(f"   Delta check: Total chunks=2, Missing/Changed chunks={missing}")

        # Send ONLY chunk 1
        delta_chunks = [{"seq": 1, "data": chunk_1_mod, "checksum": h1_mod}]
        vc_large_mod = {"node-1": 2}
        r4 = self.sync_push(large_path, full_mod, delta_chunks, len(full_mod), hashlib.sha256(full_mod.encode()).hexdigest(), "node-1", vc_large_mod)
        trace.append(f"   Delta sync result: Transferred {r4.get('bytes_transferred')}B, Saved {r4.get('bytes_saved')}B ({r4.get('savings_pct')}% bandwidth savings)")

        return {
            "type": "SYNC_DEMO_RESULT",
            "trace": trace,
            "stats": self.get_stats(),
            "success": True,
        }
