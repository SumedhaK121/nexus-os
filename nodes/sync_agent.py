"""NEXUS-OS Local Sync Agent (Dropbox-Lite Node Client).
Watches local sync directory (storage/<node_id>/sync/), detects file system events (CREATE, MODIFY, DELETE),
buffers transfers in a BoundedQueue monitor, limits in-flight network transfers via CountingSemaphore,
schedules uploads via Shortest Job First (SJF) or FCFS, and executes rsync-style incremental delta chunk transfers.
Concept: Distributed Folder Synchronization (Dropbox sync daemon, Syncthing, rsync chunk-level delta transfers).
"""

import hashlib
import os
import threading
import time

from coordinator.scheduler import scheduler_manager
from coordinator.synchronization.primitives import BoundedQueue, CountingSemaphore
from distributed_clock.vector_clock import VectorClock


class SyncAgent:
    """Node-side file watcher and incremental sync daemon."""

    def __init__(self, node_id, sync_dir, coord_client=None, poll_interval=1.0, workers=2, policy="SJF", chunk_size=65536):
        self.node_id = str(node_id)
        self.sync_dir = os.path.abspath(sync_dir)
        os.makedirs(self.sync_dir, exist_ok=True)
        self.coord_client = coord_client
        self.poll_interval = float(poll_interval)
        self.workers_count = max(1, int(workers))
        self.policy = str(policy).upper()  # "SJF" or "FCFS"
        self.chunk_size = int(chunk_size)

        # Concurrency & queueing primitives
        self.queue = BoundedQueue(capacity=20)
        self.semaphore = CountingSemaphore(initial=self.workers_count)
        self.vc = VectorClock(node_id=self.node_id)

        # Transfer scheduling structures
        self.pending_transfers = []
        self.transfers_lock = threading.Lock()
        self.snapshot = {}  # rel_path -> {"size": int, "mtime": float, "hash": str, "vc": dict, "version": int}
        self.snapshot_lock = threading.Lock()

        # Telemetry & performance metrics
        self.bytes_transferred = 0
        self.bytes_saved = 0
        self.full_bytes = 0
        self.transfers_completed = 0
        self.conflicts = 0
        self.latency_log = []

        # Lifecycle control
        self.running = False
        self.watcher_thread = None
        self.worker_threads = []

    def _call_coord(self, msg):
        """Sends a message to the coordinator via TCP client or direct reference."""
        if not self.coord_client:
            return {"type": "ERROR", "error": "No coordinator client configured"}

        try:
            if hasattr(self.coord_client, "call"):
                return self.coord_client.call(msg)
            elif callable(self.coord_client):
                return self.coord_client(msg)
            elif hasattr(self.coord_client, "send") and hasattr(self.coord_client, "recv"):
                self.coord_client.send(msg)
                return self.coord_client.recv()
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to call coordinator: {e}"}
        return {"type": "ERROR", "error": "Unsupported coord_client type"}

    def scan_changes(self):
        """Scans the local sync directory, detects CREATE/MODIFY/DELETE, and enqueues events."""
        current_files = {}

        for root, _, files in os.walk(self.sync_dir):
            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.sync_dir).replace("\\", "/")
                # Ignore temp and conflict lock artifacts
                if rel_path.endswith(".tmp") or rel_path.endswith(".swp"):
                    continue

                try:
                    stat = os.stat(full_path)
                    size = stat.st_size
                    mtime = stat.st_mtime
                    with open(full_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()

                    current_files[rel_path] = {
                        "full_path": full_path,
                        "size": size,
                        "mtime": mtime,
                        "hash": file_hash,
                    }
                except (OSError, IOError):
                    continue

        with self.snapshot_lock:
            # 1. Detect CREATE and MODIFY events
            for rel, meta in current_files.items():
                if rel not in self.snapshot:
                    job = {
                        "type": "CREATE",
                        "path": rel,
                        "full_path": meta["full_path"],
                        "size": meta["size"],
                        "burst": max(1, meta["size"]),
                        "pid": rel,
                        "arrival": time.time(),
                        "hash": meta["hash"],
                        "mtime": meta["mtime"],
                    }
                    self.queue.put(job, timeout=0.2)
                elif meta["hash"] != self.snapshot[rel].get("hash"):
                    job = {
                        "type": "MODIFY",
                        "path": rel,
                        "full_path": meta["full_path"],
                        "size": meta["size"],
                        "burst": max(1, meta["size"]),
                        "pid": rel,
                        "arrival": time.time(),
                        "hash": meta["hash"],
                        "mtime": meta["mtime"],
                    }
                    self.queue.put(job, timeout=0.2)

            # 2. Detect DELETE events
            for rel in list(self.snapshot.keys()):
                if rel not in current_files:
                    job = {
                        "type": "DELETE",
                        "path": rel,
                        "full_path": os.path.join(self.sync_dir, rel),
                        "size": 0,
                        "burst": 1,
                        "pid": rel,
                        "arrival": time.time(),
                        "hash": "",
                        "mtime": time.time(),
                    }
                    self.queue.put(job, timeout=0.2)

    def _worker_loop(self):
        """Worker thread executing transfers governed by CountingSemaphore and SJF scheduling."""
        while self.running:
            item = self.queue.get(timeout=0.3)
            if item is None:
                continue

            with self.transfers_lock:
                self.pending_transfers.append(item)

            # Acquire permit to rate-limit concurrent uploads
            if not self.semaphore.acquire(timeout=0.5):
                continue

            # Pick next job according to transfer scheduling policy (e.g. SJF vs FCFS)
            job = None
            with self.transfers_lock:
                if self.pending_transfers:
                    job = scheduler_manager.pick_next(self.pending_transfers, policy=self.policy, now=time.time())
                    if job in self.pending_transfers:
                        self.pending_transfers.remove(job)

            if job:
                try:
                    self._execute_transfer(job)
                finally:
                    self.semaphore.release()
            else:
                self.semaphore.release()

    def _execute_transfer(self, job):
        """Executes a single file upload or delete with delta chunking and vector clocks."""
        start_time = time.time()
        wait_time = max(0.0, start_time - job.get("arrival", start_time))
        rel_path = job["path"]
        dfs_path = f"/sync/{rel_path}"

        if job["type"] in ("CREATE", "MODIFY"):
            try:
                with open(job["full_path"], "rb") as f:
                    content_bytes = f.read()
            except (OSError, IOError) as e:
                return

            full_size = len(content_bytes)
            file_hash = hashlib.sha256(content_bytes).hexdigest()

            # Split into chunks
            chunks = []
            if full_size == 0:
                chunks = [b""]
            else:
                for off in range(0, full_size, self.chunk_size):
                    chunks.append(content_bytes[off:off + self.chunk_size])

            chunk_hashes = [hashlib.sha256(c).hexdigest() for c in chunks]

            # Inquire coordinator for missing chunk indices (rsync delta check)
            check_msg = {
                "type": "SYNC_CHECK_CHUNKS",
                "path": dfs_path,
                "chunk_checksums": chunk_hashes,
            }
            check_reply = self._call_coord(check_msg)
            missing = check_reply.get("missing_indices", list(range(len(chunks))))

            # Package delta chunks
            delta_chunks = []
            for idx in missing:
                if idx < len(chunks):
                    # Transmit as string (latin1 preserved for binary)
                    c_data = chunks[idx].decode("latin1")
                    delta_chunks.append({
                        "seq": idx,
                        "data": c_data,
                        "checksum": chunk_hashes[idx],
                    })

            # Acquire distributed lock before write (Phase 6 integration)
            self._call_coord({
                "type": "LOCK_ACQUIRE",
                "name": f"file:{dfs_path}",
                "client_id": self.node_id,
                "lease_sec": 15.0,
            })

            # Advance vector clock on local change
            new_vc = self.vc.tick()
            with self.snapshot_lock:
                base_vc = self.snapshot.get(rel_path, {}).get("vc", {})
                base_ver = self.snapshot.get(rel_path, {}).get("version")

            # Push sync to cluster
            push_msg = {
                "type": "SYNC_PUSH",
                "path": dfs_path,
                "content": content_bytes.decode("latin1"),
                "chunks": delta_chunks,
                "full_size": full_size,
                "file_checksum": file_hash,
                "node_id": self.node_id,
                "new_vc": new_vc,
                "base_vc": base_vc,
                "base_version": base_ver,
            }
            push_res = self._call_coord(push_msg)

            # Release distributed lock
            self._call_coord({
                "type": "LOCK_RELEASE",
                "name": f"file:{dfs_path}",
                "client_id": self.node_id,
            })

            transfer_time = max(0.0001, time.time() - start_time)

            if push_res.get("type") == "SYNC_OK":
                with self.snapshot_lock:
                    self.snapshot[rel_path] = {
                        "size": full_size,
                        "mtime": job.get("mtime", time.time()),
                        "hash": file_hash,
                        "vc": new_vc,
                        "version": push_res.get("version", 1),
                    }
                self.bytes_transferred += push_res.get("bytes_transferred", full_size)
                self.bytes_saved += push_res.get("bytes_saved", 0)
                self.full_bytes += full_size
                self.transfers_completed += 1
            elif push_res.get("type") == "SYNC_CONFLICT":
                self.conflicts += 1
                # If conflicted copy was created, note it
                with self.snapshot_lock:
                    self.snapshot[rel_path] = {
                        "size": full_size,
                        "mtime": job.get("mtime", time.time()),
                        "hash": file_hash,
                        "vc": new_vc,
                        "version": push_res.get("version", 1),
                    }

            self.latency_log.append({
                "path": rel_path,
                "policy": self.policy,
                "size": full_size,
                "wait_sec": round(wait_time, 4),
                "transfer_sec": round(transfer_time, 4),
                "total_sec": round(wait_time + transfer_time, 4),
            })

        elif job["type"] == "DELETE":
            # Delete from cluster
            self._call_coord({
                "type": "LOCK_ACQUIRE",
                "name": f"file:{dfs_path}",
                "client_id": self.node_id,
                "lease_sec": 10.0,
            })
            del_res = self._call_coord({
                "type": "SYNC_DELETE",
                "path": dfs_path,
                "node_id": self.node_id,
            })
            self._call_coord({
                "type": "LOCK_RELEASE",
                "name": f"file:{dfs_path}",
                "client_id": self.node_id,
            })
            with self.snapshot_lock:
                self.snapshot.pop(rel_path, None)

    def pull_file(self, rel_path):
        """Pulls a file from the cluster sync space into local disk and updates snapshot."""
        dfs_path = f"/sync/{rel_path}"
        res = self._call_coord({"type": "SYNC_PULL", "path": dfs_path})
        if res.get("type") != "SYNC_PULL_OK":
            return False, res.get("error", "Pull failed")

        content_raw = res.get("content", "")
        content_bytes = content_raw.encode("latin1") if isinstance(content_raw, str) else bytes(content_raw)
        dest_path = os.path.join(self.sync_dir, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with open(dest_path, "wb") as f:
            f.write(content_bytes)

        file_hash = hashlib.sha256(content_bytes).hexdigest()
        remote_vc = res.get("vector_clock", {})
        self.vc.merge(remote_vc)

        with self.snapshot_lock:
            self.snapshot[rel_path] = {
                "size": len(content_bytes),
                "mtime": os.stat(dest_path).st_mtime,
                "hash": file_hash,
                "vc": remote_vc,
                "version": res.get("version", 1),
            }
        return True, "Synced successfully"

    def _watcher_loop(self):
        """Periodically polls local directory for file changes."""
        while self.running:
            self.scan_changes()
            time.sleep(self.poll_interval)

    def start(self):
        """Starts background watcher and worker pool."""
        if self.running:
            return
        self.running = True
        self.watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True, name=f"SyncWatcher-{self.node_id}")
        self.watcher_thread.start()

        self.worker_threads = []
        for i in range(self.workers_count):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"SyncWorker-{self.node_id}-{i}")
            t.start()
            self.worker_threads.append(t)

    def stop(self):
        """Stops background threads cleanly."""
        self.running = False
        if self.watcher_thread and self.watcher_thread.is_alive():
            self.watcher_thread.join(timeout=1.0)
        for t in self.worker_threads:
            if t.is_alive():
                t.join(timeout=1.0)

    def get_status(self):
        """Returns current sync queue depth, active worker permits, and throughput statistics."""
        with self.transfers_lock:
            pending_count = len(self.pending_transfers)
        with self.snapshot_lock:
            tracked_files = len(self.snapshot)

        pct = round((self.bytes_saved / self.full_bytes) * 100, 1) if self.full_bytes > 0 else 0.0

        return {
            "node_id": self.node_id,
            "running": self.running,
            "policy": self.policy,
            "queue_depth": self.queue.qsize() + pending_count,
            "active_workers": self.semaphore.in_flight,
            "max_workers": self.workers_count,
            "tracked_files": tracked_files,
            "transfers_completed": self.transfers_completed,
            "bytes_transferred": self.bytes_transferred,
            "bytes_saved": self.bytes_saved,
            "savings_pct": pct,
            "conflicts": self.conflicts,
            "recent_latencies": self.latency_log[-5:],
        }
