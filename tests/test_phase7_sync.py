"""NEXUS-OS Phase 7 Unit Tests: Distributed Sync Engine (Dropbox-Lite).
Tests file system change detection, BoundedQueue buffering, worker CountingSemaphore rate limiting,
rsync-style incremental chunk delta transfers, Vector Clock concurrency evaluation & conflicted copy creation,
fast-forward causal updates, and SJF transfer scheduling.
OS/DS Concepts: Distributed File Synchronization (Dropbox / Syncthing), Version Vectors (DynamoDB),
rsync rolling/chunk checksum delta algorithm, SJF job scheduling for network I/O.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest

from communication import rpc
from coordinator.file_manager.dfs_manager import DfsManager
from coordinator.file_manager.dfs_metadata import DfsMetadataStore
from coordinator.file_manager.sync_manager import SyncManager
from coordinator.main import Coordinator
from coordinator.scheduler import scheduler_manager
from coordinator.synchronization.lock_manager import DistributedLockManager
from coordinator.synchronization.primitives import BoundedQueue, CountingSemaphore
from distributed_clock.vector_clock import VectorClock
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer
from nodes.sync_agent import SyncAgent


class TestPhase7Sync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_sync_test_")
        self.db_path = os.path.join(self.temp_dir, "metadata.db")
        self.node_sync_dir = os.path.join(self.temp_dir, "node_sync")
        os.makedirs(self.node_sync_dir, exist_ok=True)

        # Set up 3 in-process node servers with BlockStores for pipeline block writes
        self.node_servers = {}
        self.block_stores = {}
        self.peers = {}

        for nid in ("node-1", "node-2", "node-3"):
            node_dir = os.path.join(self.temp_dir, nid)
            bs = BlockStore(node_dir, nid)
            server = NodeServer(host="127.0.0.1", port=0)
            server.register_method("PutBlock", bs.put_block)
            server.register_method("GetBlock", bs.get_block)
            server.register_method("DeleteBlock", bs.delete_block)
            server.register_method("ListBlocks", bs.list_blocks)
            server.register_method("CorruptBlock", bs.corrupt_block)

            port = server.start()
            self.node_servers[nid] = server
            self.block_stores[nid] = bs
            self.peers[nid] = {"host": "127.0.0.1", "port": port}

        rpc.update_peer_cache(self.peers)

        # Mock coordinator
        self.coord = Coordinator(host="127.0.0.1", port=0)
        self.coord.nodes = {
            "node-1": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-1"]["port"]], "load": 0, "done": 0},
            "node-2": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-2"]["port"]], "load": 0, "done": 0},
            "node-3": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-3"]["port"]], "load": 0, "done": 0},
        }
        self.coord.dfs = DfsManager(coord=self.coord, db_path=self.db_path)
        self.coord.locks = DistributedLockManager(coord=self.coord)
        self.coord.sync_mgr = SyncManager(coord=self.coord)

    def tearDown(self):
        for s in self.node_servers.values():
            s.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sync_agent_change_detection_and_queue(self):
        """Tests that SyncAgent accurately detects CREATE, MODIFY, and DELETE events."""
        agent = SyncAgent(
            node_id="node-1",
            sync_dir=self.node_sync_dir,
            coord_client=lambda m: {"type": "OK"},
            poll_interval=0.1,
            workers=1,
        )

        # 1. CREATE event
        file_a = os.path.join(self.node_sync_dir, "project_notes.txt")
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("Initial brainstorm notes.")

        agent.scan_changes()
        self.assertEqual(agent.queue.qsize(), 1)
        item = agent.queue.get()
        self.assertEqual(item["type"], "CREATE")
        self.assertEqual(item["path"], "project_notes.txt")

        # Simulate snapshot update after transfer
        agent.snapshot["project_notes.txt"] = {
            "size": item["size"],
            "hash": item["hash"],
            "mtime": item["mtime"],
            "vc": {"node-1": 1},
            "version": 1,
        }

        # 2. MODIFY event
        with open(file_a, "w", encoding="utf-8") as f:
            f.write("Updated brainstorm notes with new architecture plan.")

        agent.scan_changes()
        self.assertEqual(agent.queue.qsize(), 1)
        mod_item = agent.queue.get()
        self.assertEqual(mod_item["type"], "MODIFY")
        self.assertEqual(mod_item["path"], "project_notes.txt")
        self.assertNotEqual(mod_item["hash"], item["hash"])

        agent.snapshot["project_notes.txt"]["hash"] = mod_item["hash"]

        # 3. DELETE event
        os.remove(file_a)
        agent.scan_changes()
        self.assertEqual(agent.queue.qsize(), 1)
        del_item = agent.queue.get()
        self.assertEqual(del_item["type"], "DELETE")
        self.assertEqual(del_item["path"], "project_notes.txt")

    def test_rsync_chunk_delta_sync_bandwidth_savings(self):
        """Tests rsync-style chunk comparison: transmitting only modified blocks saves network bandwidth."""
        sync_mgr = self.coord.sync_mgr

        # Create 128KB test file consisting of two 64KB chunks
        chunk_0 = "A" * 65536
        chunk_1 = "B" * 65536
        full_content = chunk_0 + chunk_1
        full_size = len(full_content)
        h0 = hashlib.sha256(chunk_0.encode()).hexdigest()
        h1 = hashlib.sha256(chunk_1.encode()).hexdigest()

        # Step 1: Initial push of full file
        res1 = sync_mgr.sync_push(
            path="/sync/dataset.bin",
            content=full_content,
            chunks_data=None,
            full_size=full_size,
            file_checksum=hashlib.sha256(full_content.encode()).hexdigest(),
            node_id="node-1",
            new_vc={"node-1": 1},
        )
        self.assertEqual(res1["type"], "SYNC_OK")
        self.assertEqual(res1["bytes_transferred"], full_size)
        self.assertEqual(res1["bytes_saved"], 0)

        # Step 2: Modify ONLY chunk 1 (chunk 0 is identical)
        chunk_1_mod = "B" * 65500 + "MODIFIED"
        full_mod = chunk_0 + chunk_1_mod
        h1_mod = hashlib.sha256(chunk_1_mod.encode()).hexdigest()

        # Check chunks with coordinator
        check_res = sync_mgr.check_chunks("/sync/dataset.bin", [h0, h1_mod])
        self.assertTrue(check_res["exists"])
        self.assertEqual(check_res["missing_indices"], [1])  # Only chunk 1 differs!

        # Step 3: Send only delta chunk 1
        delta_chunks = [{"seq": 1, "data": chunk_1_mod, "checksum": h1_mod}]
        res2 = sync_mgr.sync_push(
            path="/sync/dataset.bin",
            content=full_mod,
            chunks_data=delta_chunks,
            full_size=len(full_mod),
            file_checksum=hashlib.sha256(full_mod.encode()).hexdigest(),
            node_id="node-1",
            new_vc={"node-1": 2},
        )
        self.assertEqual(res2["type"], "SYNC_OK")
        self.assertEqual(res2["version"], 2)
        # Verify bandwidth savings
        self.assertEqual(res2["bytes_transferred"], len(chunk_1_mod))
        self.assertGreater(res2["bytes_saved"], 60000)
        self.assertAlmostEqual(res2["savings_pct"], 50.0, delta=1.0)

    def test_vector_clock_concurrency_and_conflicted_copy(self):
        """Tests that concurrent edits (neither clock dominates) create a conflicted copy instead of overwriting."""
        sync_mgr = self.coord.sync_mgr
        path = "/sync/shared_doc.txt"

        # 1. Base version established by node-1
        base_c = "Initial base text."
        base_vc = {"node-1": 1}
        r0 = sync_mgr.sync_push(
            path=path,
            content=base_c,
            chunks_data=None,
            full_size=len(base_c),
            file_checksum=hashlib.sha256(base_c.encode()).hexdigest(),
            node_id="node-1",
            new_vc=base_vc,
        )
        self.assertEqual(r0["type"], "SYNC_OK")

        # 2. Node 1 makes an edit offline (VC: {node-1: 2})
        c1 = base_c + "\nNode 1 revisions."
        vc1 = {"node-1": 2, "node-2": 0}
        r1 = sync_mgr.sync_push(
            path=path,
            content=c1,
            chunks_data=None,
            full_size=len(c1),
            file_checksum=hashlib.sha256(c1.encode()).hexdigest(),
            node_id="node-1",
            new_vc=vc1,
        )
        self.assertEqual(r1["type"], "SYNC_OK")
        self.assertEqual(r1["version"], 2)

        # 3. Node 2 concurrently edited from base (VC: {node-1: 1, node-2: 1})
        # Neither clock dominates: {node-1: 2, node-2: 0} || {node-1: 1, node-2: 1}
        self.assertTrue(VectorClock.are_concurrent(vc1, {"node-1": 1, "node-2": 1}))

        c2 = base_c + "\nNode 2 concurrent revisions."
        vc2 = {"node-1": 1, "node-2": 1}
        r2 = sync_mgr.sync_push(
            path=path,
            content=c2,
            chunks_data=None,
            full_size=len(c2),
            file_checksum=hashlib.sha256(c2.encode()).hexdigest(),
            node_id="node-2",
            new_vc=vc2,
        )

        # Assert conflict detection and conflict copy creation
        self.assertEqual(r2["type"], "SYNC_CONFLICT")
        self.assertTrue(r2["conflict"])
        self.assertIn("conflict node-2", r2["conflict_filename"])

        # Verify that original file remains intact with node 1's content
        read_orig = sync_mgr.sync_pull(path)
        self.assertEqual(read_orig["content"], c1)

        # Verify that conflicted copy exists in DFS with node 2's content
        read_conflict = sync_mgr.sync_pull(r2["conflict_file"])
        self.assertEqual(read_conflict["type"], "SYNC_PULL_OK")
        self.assertEqual(read_conflict["content"], c2)

    def test_vector_clock_fast_forward_without_conflict(self):
        """Tests that causally ordered sequential edits fast-forward without conflict."""
        sync_mgr = self.coord.sync_mgr
        path = "/sync/sequential_notes.txt"

        # Step 1: node-1 writes v1
        c1 = "Version 1 by node-1"
        r1 = sync_mgr.sync_push(
            path=path,
            content=c1,
            chunks_data=None,
            full_size=len(c1),
            file_checksum=hashlib.sha256(c1.encode()).hexdigest(),
            node_id="node-1",
            new_vc={"node-1": 1},
        )
        self.assertEqual(r1["type"], "SYNC_OK")
        self.assertEqual(r1["version"], 1)

        # Step 2: node-2 pulls v1 and extends it (causally dominates)
        pull = sync_mgr.sync_pull(path)
        self.assertEqual(pull["version"], 1)

        c2 = c1 + " -> Version 2 by node-2"
        # node-2 merged remote VC and ticked its own: {node-1: 1, node-2: 1}
        vc2 = {"node-1": 1, "node-2": 1}
        self.assertTrue(VectorClock.happens_before({"node-1": 1}, vc2))

        r2 = sync_mgr.sync_push(
            path=path,
            content=c2,
            chunks_data=None,
            full_size=len(c2),
            file_checksum=hashlib.sha256(c2.encode()).hexdigest(),
            node_id="node-2",
            new_vc=vc2,
        )
        self.assertEqual(r2["type"], "SYNC_OK")
        self.assertEqual(r2["version"], 2)

        read_latest = sync_mgr.sync_pull(path)
        self.assertEqual(read_latest["content"], c2)
        self.assertEqual(read_latest["version"], 2)

    def test_transfer_scheduling_sjf_latency(self):
        """Tests that SJF policy dispatches shortest file transfers first, minimizing queue waiting time."""
        now = time.time()
        jobs = [
            {"pid": "large_file.iso", "burst": 100000, "arrival": now, "path": "large_file.iso"},
            {"pid": "medium_file.zip", "burst": 25000, "arrival": now, "path": "medium_file.zip"},
            {"pid": "tiny_file.txt", "burst": 500, "arrival": now, "path": "tiny_file.txt"},
        ]

        # 1. Under SJF: smallest burst picked first
        first_sjf = scheduler_manager.pick_next(jobs, policy="SJF", now=now)
        self.assertEqual(first_sjf["pid"], "tiny_file.txt")

        # 2. Under FCFS: arrival order picked first
        first_fcfs = scheduler_manager.pick_next(jobs, policy="FCFS", now=now)
        self.assertEqual(first_fcfs["pid"], "large_file.iso")

    def test_bounded_queue_back_pressure_under_burst(self):
        """Tests that BoundedQueue enforces flow control / back-pressure when events arrive faster than upload."""
        bq = BoundedQueue(capacity=3)
        self.assertTrue(bq.put("event-1", timeout=0.1))
        self.assertTrue(bq.put("event-2", timeout=0.1))
        self.assertTrue(bq.put("event-3", timeout=0.1))
        self.assertTrue(bq.is_full())

        # Attempting to put onto full queue blocks and returns False on timeout
        start = time.time()
        blocked = bq.put("event-overflow", timeout=0.15)
        duration = time.time() - start
        self.assertFalse(blocked)
        self.assertGreaterEqual(duration, 0.1)

        # Consumer drains one item, allowing producer to proceed
        item = bq.get()
        self.assertEqual(item, "event-1")
        self.assertTrue(bq.put("event-overflow", timeout=0.1))

    def test_sync_engine_demo_scenario(self):
        """Tests the end-to-end 4-step sync demonstration scenario."""
        res = self.coord.sync_mgr.run_sync_demo()
        self.assertTrue(res["success"])
        self.assertEqual(res["type"], "SYNC_DEMO_RESULT")
        self.assertGreaterEqual(len(res["trace"]), 10)

        stats = res["stats"]
        self.assertGreater(stats["total_syncs"], 0)
        self.assertGreater(stats["bytes_saved"], 0)
        self.assertGreater(stats["conflicts_detected"], 0)


if __name__ == "__main__":
    unittest.main()
