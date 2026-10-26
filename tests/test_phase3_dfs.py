"""NEXUS-OS Phase 3 Unit Tests: Distributed File System (DFS).
Tests block chunking, pipeline replication, failover reads, integrity scrubbing,
re-replication after node failure, POSIX permissions, and metadata persistence.
OS/DS Concepts: HDFS NameNode metadata, DataNode block placement, pipeline I/O,
data scrubbers, fault-tolerant replication.
"""

import hashlib
import os
import shutil
import tempfile
import time
import unittest

from communication import rpc
from coordinator.file_manager.dfs_manager import DfsManager
from coordinator.file_manager.dfs_metadata import DfsMetadataStore
from coordinator.main import Coordinator
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer


class TestPhase3Dfs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_dfs_test_")
        self.db_path = os.path.join(self.temp_dir, "test_metadata.db")

        # Set up 3 in-process node servers with BlockStores
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

    def tearDown(self):
        for s in self.node_servers.values():
            s.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dfs_metadata_crud_and_persistence(self):
        """Tests SQLite NameNode metadata storage, POSIX permissions, and DB reopen persistence."""
        store = DfsMetadataStore(self.db_path)

        # 1. Directory creation
        ok, res = store.mkdir("/datasets", owner="alice", perms=0o750)
        self.assertTrue(ok)
        self.assertEqual(res, "/datasets")

        # Duplicate mkdir fails
        ok2, err2 = store.mkdir("/datasets")
        self.assertFalse(ok2)

        # 2. Permissions check
        self.assertTrue(store.check_permission("/datasets", user="alice", mode="rwx"))
        self.assertTrue(store.check_permission("/datasets", user="root", mode="rwx"))
        self.assertFalse(store.check_permission("/datasets", user="bob", mode="w"))

        # 3. File metadata creation
        blocks_sample = [
            {"block_id": "blk_001", "size": 65536, "checksum": "abc123sha", "nodes": ["node-1", "node-2"]},
            {"block_id": "blk_002", "size": 20480, "checksum": "def456sha", "nodes": ["node-2", "node-3"]},
        ]
        v = store.put_file_metadata(
            path="/datasets/genome.fa",
            size=86016,
            blocks_info=blocks_sample,
            owner="alice",
            perms=0o644,
            checksum="fullfilesha256",
        )
        self.assertEqual(v, 1)

        # 4. Verify get_file_metadata
        meta = store.get_file_metadata("/datasets/genome.fa")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["size"], 86016)
        self.assertEqual(len(meta["blocks"]), 2)
        self.assertEqual(meta["blocks"][0]["block_id"], "blk_001")
        self.assertEqual(sorted(meta["blocks"][0]["nodes"]), ["node-1", "node-2"])

        # 5. Directory listing
        listing = store.ls("/datasets")
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["name"], "genome.fa")

        # 6. Persistence across DB reopen (simulating NameNode restart)
        reopened_store = DfsMetadataStore(self.db_path)
        meta_reopened = reopened_store.get_file_metadata("/datasets/genome.fa")
        self.assertIsNotNone(meta_reopened)
        self.assertEqual(meta_reopened["version"], 1)
        self.assertEqual(len(meta_reopened["blocks"]), 2)

    def test_dfs_metadata_rename_and_move(self):
        """Tests renaming and directory hierarchy relocation."""
        store = DfsMetadataStore(self.db_path)
        store.mkdir("/lab", owner="alice")
        store.put_file_metadata(
            path="/lab/experiment.csv",
            size=1024,
            blocks_info=[{"block_id": "blk_csv_1", "size": 1024, "checksum": "c1", "nodes": ["node-1"]}],
            owner="alice",
        )

        # Rename file
        ok, res = store.rename("/lab/experiment.csv", "/lab/results.csv")
        self.assertTrue(ok)
        self.assertIsNone(store.get_file_metadata("/lab/experiment.csv"))
        self.assertIsNotNone(store.get_file_metadata("/lab/results.csv"))

        # Move directory with contents
        store.mkdir("/archive")
        ok_dir, _ = store.rename("/lab", "/archive/lab")
        self.assertTrue(ok_dir)
        self.assertIsNotNone(store.get_file_metadata("/archive/lab/results.csv"))

    def test_dfs_block_store_standalone(self):
        """Tests node-side BlockStore operations directly."""
        bs = self.block_stores["node-1"]

        # Put block
        test_data = b"Hello NEXUS-OS Distributed Block Store!"
        sha = hashlib.sha256(test_data).hexdigest()
        res = bs.put_block({"block_id": "blk_test_01", "data": test_data.decode("utf-8"), "checksum": sha})
        self.assertEqual(res["type"], "OK")
        self.assertEqual(res["size"], len(test_data))

        # Get block
        get_res = bs.get_block({"block_id": "blk_test_01"})
        self.assertEqual(get_res["type"], "OK")
        self.assertEqual(get_res["data"], test_data.decode("utf-8"))
        self.assertEqual(get_res["checksum"], sha)

        # Corrupt block
        c_res = bs.corrupt_block({"block_id": "blk_test_01"})
        self.assertEqual(c_res["type"], "OK")
        corrupted = bs.get_block({"block_id": "blk_test_01"})
        self.assertNotEqual(corrupted["checksum"], sha)

        # Delete block
        del_res = bs.delete_block({"block_id": "blk_test_01"})
        self.assertEqual(del_res["type"], "OK")
        missing = bs.get_block({"block_id": "blk_test_01"})
        self.assertEqual(missing["type"], "ERROR")

    def test_dfs_manager_chunking_and_pipeline(self):
        """Tests 64KB block chunking, pipeline writes, and failover reads across nodes."""
        dfs = DfsManager(db_path=self.db_path)
        online_nodes = ["node-1", "node-2", "node-3"]

        # 1. Empty file round trip
        w_empty = dfs.write_file("/empty.txt", "", online_nodes)
        self.assertEqual(w_empty["type"], "FILE_OK")
        self.assertEqual(w_empty["size"], 0)
        self.assertEqual(w_empty["blocks"], 1)

        r_empty = dfs.read_file("/empty.txt")
        self.assertEqual(r_empty["type"], "FILE_OK")
        self.assertEqual(r_empty["content"], "")

        # 2. Multi-block odd-sized file (140 KB = 64KB + 64KB + 12KB)
        chunk_pattern = "NEXUS-DFS-BLOCK-DATA-PACKET-" * 100  # ~2.8 KB
        big_content = chunk_pattern * 50  # ~140 KB
        raw_bytes = big_content.encode("utf-8")
        raw_size = len(raw_bytes)
        expected_blocks = (raw_size + dfs.block_size - 1) // dfs.block_size

        w_res = dfs.write_file("/bigfile.dat", big_content, online_nodes)
        self.assertEqual(w_res["type"], "FILE_OK")
        self.assertEqual(w_res["size"], raw_size)
        self.assertEqual(w_res["blocks"], expected_blocks)
        self.assertGreaterEqual(expected_blocks, 3)

        # Read back and verify exact byte content
        r_res = dfs.read_file("/bigfile.dat")
        self.assertEqual(r_res["type"], "FILE_OK")
        self.assertEqual(r_res["size"], raw_size)
        self.assertEqual(r_res["content"], big_content)
        self.assertEqual(r_res["checksum"], hashlib.sha256(raw_bytes).hexdigest())

    def test_dfs_failover_read_and_scrub_repair(self):
        """Tests reading through replica corruption via failover, and auto-repairing via FS_SCRUB."""
        dfs = DfsManager(db_path=self.db_path)
        online_nodes = ["node-1", "node-2", "node-3"]

        content = "Critical cluster research report: distributed systems and fault tolerance."
        w_res = dfs.write_file("/report.txt", content, online_nodes)
        self.assertEqual(w_res["type"], "FILE_OK")

        # Find the primary node for block 0
        file_meta = dfs.meta.get_file_metadata("/report.txt")
        blk_0 = file_meta["blocks"][0]
        blk_id = blk_0["block_id"]
        replicas = blk_0["nodes"]
        self.assertEqual(len(replicas), 2)

        # Deliberately corrupt replica on the first node
        primary_node = replicas[0]
        c_res = rpc.call_node(primary_node, "CorruptBlock", {"block_id": blk_id})
        self.assertEqual(c_res["type"], "OK")

        # Read file: should gracefully failover to second healthy replica
        r_res = dfs.read_file("/report.txt")
        self.assertEqual(r_res["type"], "FILE_OK")
        self.assertEqual(r_res["content"], content)

        # Run scrub with repair=True: detects corrupted replica and repairs it from healthy replica
        scrub_res = dfs.scrub(repair=True)
        self.assertEqual(scrub_res["type"], "SCRUB_RESULT")
        self.assertGreaterEqual(scrub_res["corrupted_detected"], 1)
        self.assertGreaterEqual(scrub_res["repaired"], 1)

        # Verify that corrupted replica on primary_node is now repaired
        recheck = rpc.call_node(primary_node, "GetBlock", {"block_id": blk_id})
        self.assertEqual(recheck["type"], "OK")
        self.assertEqual(recheck["checksum"], blk_0["checksum"])

    def test_dfs_under_replication_healing_on_node_down(self):
        """Tests that node failure marks replicas OFFLINE and re_replicate_under_replicated restores k=2."""
        dfs = DfsManager(db_path=self.db_path)
        # Write file with replicas on node-1 and node-2
        content = "Self-healing replication test payload."
        dfs.write_file("/healing.txt", content, ["node-1", "node-2"])

        # Both replicas are healthy
        under_before = dfs.meta.get_under_replicated_blocks(2)
        self.assertEqual(len(under_before), 0)

        # Simulate node-1 crashing
        dfs.meta.mark_node_offline("node-1")
        under_after = dfs.meta.get_under_replicated_blocks(2)
        self.assertEqual(len(under_after), 1)
        self.assertEqual(under_after[0]["healthy_nodes"], ["node-2"])

        # Trigger re-replication with remaining online nodes (node-2, node-3)
        replicated_count = dfs.re_replicate_under_replicated(["node-2", "node-3"])
        self.assertEqual(replicated_count, 1)

        # Now healthy replica count is restored to 2 (node-2 and node-3)
        under_healed = dfs.meta.get_under_replicated_blocks(2)
        self.assertEqual(len(under_healed), 0)

    def test_dfs_coordinator_api_handlers(self):
        """Tests FS_* coordinator message handlers end-to-end."""
        coord = Coordinator(host="127.0.0.1", port=0)
        coord.nodes = {
            "node-1": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-1"]["port"]], "load": 0, "done": 0},
            "node-2": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-2"]["port"]], "load": 0, "done": 0},
            "node-3": {"status": "ONLINE", "addr": ["127.0.0.1", self.peers["node-3"]["port"]], "load": 0, "done": 0},
        }
        coord.dfs = DfsManager(coord=coord, db_path=self.db_path)

        class FakeCtx:
            node_id = "test-client"

        ctx = FakeCtx()

        # 1. FS_MKDIR
        mk_res = coord.handlers["FS_MKDIR"](coord, ctx, {"path": "/shared/projects", "user": "alice"})
        self.assertEqual(mk_res["type"], "OK")

        # 2. FS_WRITE
        w_res = coord.handlers["FS_WRITE"](coord, ctx, {
            "path": "/shared/projects/readme.md",
            "content": "# Distributed Lab Project\nBuilt with NEXUS-OS.",
            "user": "alice",
        })
        self.assertEqual(w_res["type"], "FILE_OK")
        self.assertEqual(w_res["version"], 1)

        # 3. FS_READ
        r_res = coord.handlers["FS_READ"](coord, ctx, {"path": "/shared/projects/readme.md", "user": "alice"})
        self.assertEqual(r_res["type"], "FILE_OK")
        self.assertIn("Distributed Lab Project", r_res["content"])

        # 4. FS_LS
        ls_res = coord.handlers["FS_LS"](coord, ctx, {"path": "/shared/projects"})
        self.assertEqual(ls_res["type"], "FS_LS_RESULT")
        self.assertEqual(len(ls_res["entries"]), 1)
        self.assertEqual(ls_res["entries"][0]["name"], "readme.md")

        # 5. FS_SCRUB
        scrub_res = coord.handlers["FS_SCRUB"](coord, ctx, {"repair": True})
        self.assertEqual(scrub_res["type"], "SCRUB_RESULT")
        self.assertEqual(scrub_res["corrupted_detected"], 0)


if __name__ == "__main__":
    unittest.main()
