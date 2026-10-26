"""NEXUS-OS Distributed File System (DFS) Manager.
Coordinates HDFS/GFS-style block chunking, pipeline replication, checksum verification,
fault-tolerant failover reads, background self-healing re-replication, and data scrubbing.
Concept: Hadoop Distributed File System (HDFS NameNode pipeline & block placement).
"""

import base64
import hashlib
import os
import threading
import time
from communication import rpc
from coordinator.file_manager.dfs_metadata import DfsMetadataStore
from coordinator.synchronization.readers_writers import RWLock


class DfsManager:
    """Cluster-wide distributed file system manager with block-level replication."""
    def __init__(self, coord=None, db_path=None):
        self.coord = coord
        self.meta = DfsMetadataStore(db_path)
        self.rw = RWLock()

        # Block size (default 64 KB) and target replication factor (default 2)
        block_kb = int(os.environ.get("NEXUS_BLOCK_KB", 64))
        self.block_size = block_kb * 1024
        self.replication_factor = int(os.environ.get("NEXUS_REPLICAS", 2))

    def _select_replica_nodes(self, count, online_nodes, exclude=None):
        """Chooses replica nodes with least block load."""
        exclude = set(exclude or [])
        candidates = [n for n in online_nodes if n not in exclude]
        if not candidates:
            return []

        counts = self.meta.get_node_block_counts()
        # Sort by block count ascending, then node name
        sorted_candidates = sorted(candidates, key=lambda n: (counts.get(n, 0), n))
        return sorted_candidates[:count]

    def write_file(self, path, content, online_nodes=None, user="root", base=None, vector_clock=None):
        if online_nodes is None:
            if hasattr(self.coord, "nodes") and self.coord.nodes:
                from coordinator.node_manager import node_manager
                online_nodes = node_manager.online(self.coord.nodes)
            else:
                online_nodes = ["node-1", "node-2", "node-3"]
        """Splits content into 64KB blocks, coordinates pipeline replication,
        and commits metadata to SQLite catalog.
        """
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = bytes(content or b"")

        path = DfsMetadataStore._norm(path)

        # Check permissions
        if not self.meta.check_permission(path, user=user, mode="w"):
            return {"type": "ERROR", "error": f"Permission denied for user '{user}' writing to {path}"}

        self.rw.acquire_write()
        try:
            # Optimistic conflict check
            existing = self.meta.get_file_metadata(path)
            if existing:
                curr_version = existing["version"]
                if base is not None and base != curr_version:
                    return {
                        "type": "CONFLICT",
                        "conflict": True,
                        "name": os.path.basename(path),
                        "path": path,
                        "current": curr_version,
                        "base": base,
                    }

            total_size = len(content_bytes)
            file_checksum = hashlib.sha256(content_bytes).hexdigest()

            # Split into fixed-size blocks (default 64 KB)
            chunks = []
            if total_size == 0:
                chunks = [b""]  # Empty file has 1 empty block
            else:
                for offset in range(0, total_size, self.block_size):
                    chunks.append(content_bytes[offset:offset + self.block_size])

            effective_nodes = list(online_nodes) if online_nodes else ["node-1", "node-2", "node-3"]
            blocks_info = []
            successful_blocks = []

            for seq, chunk in enumerate(chunks):
                blk_checksum = hashlib.sha256(chunk).hexdigest()
                block_id = f"blk_{file_checksum[:8]}_{seq:04d}_{blk_checksum[:8]}"

                # Select placement nodes
                needed_replicas = min(self.replication_factor, len(effective_nodes))
                chosen = self._select_replica_nodes(needed_replicas, effective_nodes)
                if not chosen:
                    chosen = effective_nodes[:needed_replicas]

                # Pipeline replication: first replica receives chunk and forwards to subsequent replicas
                primary = chosen[0]
                forward_to = chosen[1:]

                payload = {
                    "block_id": block_id,
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "base64": True,
                    "checksum": blk_checksum,
                    "forward_to": forward_to,
                }

                # RPC to primary replica
                res = rpc.call_node(primary, "PutBlock", payload)
                if res.get("type") == "ERROR":
                    # Rollback previous written blocks
                    self._rollback_blocks(successful_blocks)
                    return {"type": "ERROR", "error": f"Write pipeline failed on node {primary}: {res.get('error')}"}

                successful_blocks.append((block_id, chosen))
                blocks_info.append({
                    "block_id": block_id,
                    "size": len(chunk),
                    "checksum": blk_checksum,
                    "nodes": chosen,
                })

            # Commit metadata to SQLite
            version = self.meta.put_file_metadata(
                path=path,
                size=total_size,
                blocks_info=blocks_info,
                owner=user,
                perms=0o644,
                checksum=file_checksum,
                vector_clock=vector_clock,
            )

            all_replicas = sorted(list({n for b in blocks_info for n in b["nodes"]}))
            return {
                "type": "FILE_OK",
                "name": os.path.basename(path),
                "path": path,
                "version": version,
                "vector_clock": vector_clock or {},
                "size": total_size,
                "blocks": len(blocks_info),
                "checksum": file_checksum,
                "nodes": all_replicas,
                "block_details": blocks_info,
            }
        finally:
            self.rw.release_write()

    def _rollback_blocks(self, blocks_to_delete):
        """Rolls back blocks on failure."""
        for blk_id, nodes in blocks_to_delete:
            for n in nodes:
                try:
                    rpc.call_node(n, "DeleteBlock", {"block_id": blk_id})
                except Exception:
                    pass

    def read_file(self, path, user="root"):
        """Reads file by reassembling its constituent blocks with replica failover."""
        path = DfsMetadataStore._norm(path)
        if not self.meta.check_permission(path, user=user, mode="r"):
            return {"type": "ERROR", "error": f"Permission denied reading {path}"}

        self.rw.acquire_read()
        try:
            file_meta = self.meta.get_file_metadata(path)
            if not file_meta:
                return None

            blocks = file_meta.get("blocks", [])
            assembled_bytes = bytearray()

            for blk in blocks:
                blk_id = blk["block_id"]
                expected_sha = blk["checksum"]
                replicas = blk.get("all_nodes", [])

                block_read_ok = False
                for node_id in replicas:
                    res = rpc.call_node(node_id, "GetBlock", {"block_id": blk_id})
                    if res.get("type") == "OK":
                        raw_data = res.get("data")
                        is_b64 = res.get("base64", False)
                        if is_b64:
                            data_chunk = base64.b64decode(raw_data)
                        elif isinstance(raw_data, str):
                            data_chunk = raw_data.encode("utf-8")
                        else:
                            data_chunk = bytes(raw_data or b"")

                        actual_sha = hashlib.sha256(data_chunk).hexdigest()
                        if actual_sha == expected_sha:
                            assembled_bytes.extend(data_chunk)
                            block_read_ok = True
                            break
                        else:
                            print(f"[DfsManager] Corrupt replica of {blk_id} on {node_id}, failing over", flush=True)

                if not block_read_ok and blk["size"] > 0:
                    return {"type": "ERROR", "error": f"Failed to retrieve healthy replica for block {blk_id}"}

            # Decode to string if possible, else return base64
            try:
                content_str = assembled_bytes.decode("utf-8")
                is_text = True
            except UnicodeDecodeError:
                content_str = base64.b64encode(assembled_bytes).decode("ascii")
                is_text = False

            return {
                "type": "FILE_OK",
                "name": os.path.basename(path),
                "path": path,
                "content": content_str,
                "is_text": is_text,
                "size": len(assembled_bytes),
                "version": file_meta["version"],
                "checksum": file_meta["checksum"],
                "blocks": len(blocks),
                "source": "dfs_cluster",
            }
        finally:
            self.rw.release_read()

    def delete_file(self, path, user="root"):
        path = DfsMetadataStore._norm(path)
        if not self.meta.check_permission(path, user=user, mode="w"):
            return False, "Permission denied"

        self.rw.acquire_write()
        try:
            ok, blocks = self.meta.delete_file_metadata(path)
            if ok:
                # Tell nodes to delete blocks
                online_nodes = list(self.coord.nodes.keys()) if self.coord else []
                for b_id in blocks:
                    for n in online_nodes:
                        rpc.call_node(n, "DeleteBlock", {"block_id": b_id})
            return ok, "Deleted" if ok else "File not found"
        finally:
            self.rw.release_write()

    def re_replicate_under_replicated(self, online_nodes):
        """Scans for blocks with < replication_factor copies and replicates to new nodes."""
        under_replicated = self.meta.get_under_replicated_blocks(self.replication_factor)
        replicated_count = 0

        for blk in under_replicated:
            blk_id = blk["block_id"]
            healthy_nodes = blk.get("healthy_nodes", [])
            if not healthy_nodes:
                continue

            # Pick a donor node
            donor = healthy_nodes[0]
            # Find an online node that does NOT have this block
            dest_candidates = [n for n in online_nodes if n not in healthy_nodes]
            if not dest_candidates:
                continue

            dest = dest_candidates[0]

            # Fetch from donor
            get_res = rpc.call_node(donor, "GetBlock", {"block_id": blk_id})
            if get_res.get("type") == "OK":
                put_payload = {
                    "block_id": blk_id,
                    "data": get_res.get("data"),
                    "base64": get_res.get("base64", False),
                    "checksum": blk["checksum"],
                    "forward_to": [],
                }
                put_res = rpc.call_node(dest, "PutBlock", put_payload)
                if put_res.get("type") == "OK":
                    self.meta.add_block_replica(blk_id, dest, status="HEALTHY")
                    replicated_count += 1
                    if self.coord:
                        self.coord.log("dfs", f"Re-replicated under-replicated block {blk_id} from {donor} -> {dest}")

        return replicated_count

    def scrub(self, repair=True):
        """Verifies block checksums across all replicas and auto-repairs corruption."""
        files = self.meta.get_all_files()
        report = {}
        repaired_count = 0
        corrupted_count = 0

        for f in files:
            p = f["path"]
            f_meta = self.meta.get_file_metadata(p)
            report[p] = {}

            for blk in f_meta.get("blocks", []):
                blk_id = blk["block_id"]
                expected_sha = blk["checksum"]
                replicas = blk.get("all_nodes", [])
                report[p][blk_id] = {}

                healthy_data = None
                corrupt_nodes = []

                for node_id in replicas:
                    res = rpc.call_node(node_id, "GetBlock", {"block_id": blk_id})
                    if res.get("type") == "OK":
                        raw_data = res.get("data")
                        is_b64 = res.get("base64", False)
                        d_bytes = base64.b64decode(raw_data) if is_b64 else (raw_data.encode("utf-8") if isinstance(raw_data, str) else bytes(raw_data))
                        actual_sha = hashlib.sha256(d_bytes).hexdigest()
                        if actual_sha == expected_sha:
                            report[p][blk_id][node_id] = "OK"
                            healthy_data = (raw_data, is_b64)
                        else:
                            report[p][blk_id][node_id] = "CORRUPT"
                            corrupt_nodes.append(node_id)
                            corrupted_count += 1
                    else:
                        report[p][blk_id][node_id] = "MISSING"
                        corrupt_nodes.append(node_id)
                        corrupted_count += 1

                # If repair is enabled and we have healthy data, fix the corrupt replicas
                if repair and healthy_data and corrupt_nodes:
                    raw, is_b64 = healthy_data
                    for c_node in corrupt_nodes:
                        put_res = rpc.call_node(c_node, "PutBlock", {
                            "block_id": blk_id,
                            "data": raw,
                            "base64": is_b64,
                            "checksum": expected_sha,
                            "forward_to": [],
                        })
                        if put_res.get("type") == "OK":
                            report[p][blk_id][c_node] = "REPAIRED"
                            self.meta.add_block_replica(blk_id, c_node, status="HEALTHY")
                            repaired_count += 1
                            if self.coord:
                                self.coord.log("dfs", f"Scrub auto-repaired corrupted replica of {blk_id} on {c_node}")

        return {
            "type": "SCRUB_RESULT",
            "report": report,
            "corrupted_detected": corrupted_count,
            "repaired": repaired_count,
        }
