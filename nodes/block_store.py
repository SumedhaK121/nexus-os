"""NEXUS-OS Block Store (DataNode Storage Engine).
Manages block storage under NEXUS_DATA_DIR/blocks/.
Serves PutBlock, GetBlock, DeleteBlock, and ListBlocks over RPC.
Integrates per-node in-memory page cache (LRU/FIFO/Optimal) with access tracing.
Concept: Distributed block storage layer (HDFS DataNode / Ceph OSD) + Page Cache (Linux buffer cache).
"""

import base64
import hashlib
import os
import threading
from communication import rpc
from nodes.node_cache import NodeBlockCache


class BlockStore:
    """Node-side block storage engine with SHA-256 integrity verification and in-memory cache."""
    def __init__(self, data_dir, node_id, cache_capacity=None, cache_policy=None):
        self.node_id = node_id
        self.blocks_dir = os.path.join(data_dir, "blocks")
        os.makedirs(self.blocks_dir, exist_ok=True)
        self.lock = threading.Lock()

        cap = cache_capacity if cache_capacity is not None else int(os.environ.get("NEXUS_CACHE_CAP", 4))
        pol = cache_policy or os.environ.get("NEXUS_CACHE_POLICY", "LRU")
        self.cache = NodeBlockCache(node_id=node_id, capacity=cap, policy=pol)

    def _block_path(self, block_id):
        safe_id = "".join(c for c in block_id if c.isalnum() or c in ("-", "_", "."))
        return os.path.join(self.blocks_dir, safe_id)

    def put_block(self, payload):
        """Stores a block, caches it, and forwards to next replica in the pipeline if forward_to is specified."""
        block_id = payload["block_id"]
        raw_data = payload.get("data")
        is_b64 = payload.get("base64", False)
        forward_to = list(payload.get("forward_to", []))
        expected_checksum = payload.get("checksum")

        if is_b64:
            data_bytes = base64.b64decode(raw_data)
        elif isinstance(raw_data, str):
            data_bytes = raw_data.encode("utf-8")
        else:
            data_bytes = bytes(raw_data or b"")

        actual_checksum = hashlib.sha256(data_bytes).hexdigest()
        if expected_checksum and actual_checksum != expected_checksum:
            return {"type": "ERROR", "error": f"Checksum mismatch: expected {expected_checksum}, got {actual_checksum}"}

        # Write to disk
        path = self._block_path(block_id)
        with self.lock:
            with open(path, "wb") as f:
                f.write(data_bytes)

        # Update in-memory page cache
        self.cache.put(block_id, data_bytes)

        # Pipeline forwarding to next replica (HDFS-style)
        forwarded = []
        if forward_to:
            next_node = forward_to[0]
            remaining = forward_to[1:]
            forward_payload = {
                "block_id": block_id,
                "data": base64.b64encode(data_bytes).decode("ascii"),
                "base64": True,
                "checksum": actual_checksum,
                "forward_to": remaining,
            }
            res = rpc.call_node(next_node, "PutBlock", forward_payload)
            if res.get("type") == "ERROR":
                print(f"[{self.node_id}] Failed pipeline forward of {block_id} to {next_node}: {res.get('error')}", flush=True)
            else:
                forwarded.append(next_node)
                if "forwarded" in res:
                    forwarded.extend(res["forwarded"])

        return {
            "type": "OK",
            "block_id": block_id,
            "size": len(data_bytes),
            "checksum": actual_checksum,
            "node_id": self.node_id,
            "forwarded": forwarded,
        }

    def get_block(self, payload):
        """Retrieves block data (checking cache first) and verifies SHA-256 checksum."""
        block_id = payload["block_id"]

        # Check in-memory cache
        cached_bytes = self.cache.get(block_id)
        if cached_bytes is not None:
            checksum = hashlib.sha256(cached_bytes).hexdigest()
            try:
                text = cached_bytes.decode("utf-8")
                return {"type": "OK", "block_id": block_id, "data": text, "checksum": checksum, "base64": False, "source": "cache"}
            except UnicodeDecodeError:
                return {
                    "type": "OK",
                    "block_id": block_id,
                    "data": base64.b64encode(cached_bytes).decode("ascii"),
                    "checksum": checksum,
                    "base64": True,
                    "source": "cache",
                }

        # Cache miss: read from disk
        path = self._block_path(block_id)
        with self.lock:
            if not os.path.exists(path):
                return {"type": "ERROR", "error": f"Block {block_id} not found on node {self.node_id}"}
            with open(path, "rb") as f:
                data_bytes = f.read()

        checksum = hashlib.sha256(data_bytes).hexdigest()
        # Populate cache
        self.cache.put(block_id, data_bytes)

        # Return as utf-8 if valid text, else base64
        try:
            text = data_bytes.decode("utf-8")
            return {"type": "OK", "block_id": block_id, "data": text, "checksum": checksum, "base64": False, "source": "disk"}
        except UnicodeDecodeError:
            return {
                "type": "OK",
                "block_id": block_id,
                "data": base64.b64encode(data_bytes).decode("ascii"),
                "checksum": checksum,
                "base64": True,
                "source": "disk",
            }

    def delete_block(self, payload):
        """Removes a block file from local disk and invalidates cache."""
        block_id = payload["block_id"]
        self.cache.invalidate(block_id)
        path = self._block_path(block_id)
        with self.lock:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    return {"type": "OK", "block_id": block_id}
                except OSError as e:
                    return {"type": "ERROR", "error": str(e)}
        return {"type": "OK", "block_id": block_id}

    def list_blocks(self, payload=None):
        """Returns inventory of local blocks."""
        with self.lock:
            files = os.listdir(self.blocks_dir)
            inventory = []
            for fname in files:
                fpath = os.path.join(self.blocks_dir, fname)
                if os.path.isfile(fpath):
                    inventory.append({"block_id": fname, "size": os.path.getsize(fpath)})
        return {"type": "OK", "node_id": self.node_id, "blocks": inventory, "count": len(inventory)}

    def corrupt_block(self, payload):
        """Test helper: deliberately corrupts a local block for verify/scrub demonstrations."""
        block_id = payload["block_id"]
        self.cache.invalidate(block_id)
        path = self._block_path(block_id)
        with self.lock:
            if os.path.exists(path):
                with open(path, "wb") as f:
                    f.write(b"CORRUPTED_BLOCK_DATA")
                return {"type": "OK", "corrupted": block_id}
        return {"type": "ERROR", "error": f"Block {block_id} not found"}

    def cache_stats(self, payload=None):
        """Returns node block cache hit/miss statistics."""
        return {"type": "OK", **self.cache.stats()}

    def cache_config(self, payload):
        """Updates node cache capacity and/or policy."""
        cap = payload.get("capacity")
        pol = payload.get("policy")
        self.cache.set_config(capacity=cap, policy=pol)
        return {"type": "OK", **self.cache.stats()}
