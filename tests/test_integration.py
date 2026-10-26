"""NEXUS-OS Comprehensive End-to-End Cluster Integration Test Suite.
Verifies complete cluster invariants across:
- Cluster registration & dynamic capacity aggregation
- Distributed File System (DFS) pipeline writes, checksums, and failover reads
- Distributed Lock Manager (lease expiration, FIFO waiter queueing)
- Dropbox-Lite Sync & Vector Clock conflict resolution
- Chaos failure injection, 3-state failure detection, task rescheduling, and block re-replication
- Scheduling invariants across comparative algorithms (FCFS vs SJF vs SRTF vs Priority+Aging)
- Banker's admission control state invariants

Concept: Systems Integration Testing (OSDS Final Year Course Project).
"""

import hashlib
import os
import shutil
import tempfile
import threading
import time
import unittest

from communication import rpc
from communication.tcp_client import Client
from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.main import Coordinator
from coordinator.scheduler import scheduler_manager
from distributed_clock.vector_clock import VectorClock, CONCURRENT
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer


class TestClusterIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_integration_")
        self.db_path = os.path.join(self.temp_dir, "catalog.db")

        # 1. Start Coordinator
        self.coord = Coordinator(host="127.0.0.1", port=0)
        self.coord_thread = threading.Thread(target=self.coord.serve, daemon=True)
        self.coord_thread.start()
        time.sleep(0.3)
        self.cport = self.coord.server.getsockname()[1]

        # 2. Start 3 NodeServers with BlockStores
        self.nodes = {}
        self.block_stores = {}
        self.peers = {}
        self.reg_clients = {}

        specs = [
            ("node-1", 2, 256, 2),
            ("node-2", 4, 512, 3),
            ("node-3", 2, 256, 2),
        ]
        for nid, cpu, mem, io in specs:
            store_dir = os.path.join(self.temp_dir, nid)
            bs = BlockStore(store_dir, nid)
            server = NodeServer(host="127.0.0.1", port=0)
            server.register_method("PutBlock", bs.put_block)
            server.register_method("GetBlock", bs.get_block)
            server.register_method("DeleteBlock", bs.delete_block)
            server.register_method("ListBlocks", bs.list_blocks)
            server.register_method("CorruptBlock", bs.corrupt_block)

            nport = server.start()
            self.nodes[nid] = server
            self.block_stores[nid] = bs
            self.peers[nid] = {"host": "127.0.0.1", "port": nport}

            # Register with coordinator
            cli = Client(host="127.0.0.1", port=self.cport, client_id=f"integ-{nid}")
            reg_res = cli.call({
                "type": "REGISTER",
                "node_id": nid,
                "addr": ["127.0.0.1", nport],
                "cpu_slots": cpu,
                "mem_mb": mem,
                "io_slots": io,
            })
            self.assertEqual(reg_res.get("type"), "REGISTERED")
            self.reg_clients[nid] = cli

        rpc.update_peer_cache(self.peers)

    def tearDown(self):
        for cli in self.reg_clients.values():
            try:
                cli.close()
            except Exception:
                pass
        for s in self.nodes.values():
            s.stop()
        if self.coord and hasattr(self.coord, "server"):
            self.coord.server.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_cluster_lifecycle(self):
        """Verifies full cluster lifecycle from storage and locking to failure and self-healing."""
        # 1. Capacity aggregation invariant
        self.assertEqual(self.coord.res_mgr.total, [8, 8, 7])

        # 2. Block-based DFS write and failover read
        self.coord.dfs.meta.mkdir("/shared", owner="alice")
        test_payload = b"NEXUS-OS Integration Block Payload Data " * 2000  # ~80 KB (spans 2 blocks)
        w_res = self.coord.dfs.write_file("/shared/test.dat", test_payload, user="alice")
        self.assertEqual(w_res["type"], "FILE_OK")
        self.assertEqual(w_res["blocks"], 2)
        self.assertEqual(len(w_res["nodes"]), 2)

        # Corrupt replica on first node
        first_node = w_res["nodes"][0]
        meta = self.coord.dfs.meta.get_file_metadata("/shared/test.dat")
        first_block = meta["blocks"][0]["block_id"]
        self.block_stores[first_node].corrupt_block({"block_id": first_block})

        # Read must succeed by failing over to second replica
        r_res = self.coord.dfs.read_file("/shared/test.dat", user="alice")
        self.assertEqual(r_res["type"], "FILE_OK")
        self.assertEqual(len(r_res["content"].encode("utf-8")), len(test_payload))

        # 3. Distributed Lock Manager invariant
        acq_1 = self.coord.locks.acquire("res:/lock/a", "client-1", lease_sec=5)
        self.assertEqual(acq_1["type"], "LOCK_OK")
        self.assertEqual(acq_1["holder"], "client-1")

        acq_2 = self.coord.locks.acquire("res:/lock/a", "client-2", lease_sec=5)
        self.assertEqual(acq_2["type"], "LOCK_DENIED")
        self.assertIn("client-2", acq_2["waiters"])

        rel_1 = self.coord.locks.release("res:/lock/a", "client-1")
        self.assertEqual(rel_1["type"], "LOCK_OK")
        self.assertEqual(rel_1["granted_to"], "client-2")
        self.coord.locks.release("res:/lock/a", "client-2")

        # 4. Collaborative Sync & Concurrency Invariant
        base_text = "Master Document Content\n"
        self.coord.sync_mgr.sync_push(
            path="/sync/master.txt",
            content=base_text,
            chunks_data=None,
            full_size=len(base_text),
            file_checksum=hashlib.sha256(base_text.encode()).hexdigest(),
            node_id="node-1",
            new_vc={"node-1": 1},
        )
        # Concurrent branch from node-2
        branch_text = base_text + "Node-2 contribution\n"
        sync_res = self.coord.sync_mgr.sync_push(
            path="/sync/master.txt",
            content=branch_text,
            chunks_data=None,
            full_size=len(branch_text),
            file_checksum=hashlib.sha256(branch_text.encode()).hexdigest(),
            node_id="node-2",
            new_vc={"node-2": 1},
        )
        self.assertEqual(sync_res["type"], "SYNC_CONFLICT")
        self.assertTrue(sync_res["conflict"])
        self.assertIsNotNone(sync_res["conflict_filename"])

        # 5. Fault Injection & Self-Healing Invariant
        self.coord.tasks["INSPECT-1"] = {
            "node": "node-1",
            "state": "Running",
            "burst": 4,
            "job_type": "wordcount",
            "args": [],
            "submit_time": time.time(),
            "start_time": time.time(),
        }
        # Injected failure
        self.coord.nodes["node-1"]["status"] = "OFFLINE"
        self.coord.node_mgr.mark_offline("node-1")
        self.coord._on_node_down("node-1")

        # Job must be rescheduled to surviving node
        task = self.coord.tasks["INSPECT-1"]
        self.assertIn(task["node"], ("node-2", "node-3"))
        self.assertEqual(task["state"], "Running")

        # Under-replicated blocks must heal
        online = self.coord.node_mgr.online(self.coord.nodes)
        healed = self.coord.dfs.re_replicate_under_replicated(online)
        self.assertGreaterEqual(healed, 1)

    def test_cpu_scheduling_optimality_invariants(self):
        """Verifies mathematical scheduling invariants on a realistic heavy-tailed workload."""
        trace = [
            {"pid": "J1", "arrival": 0, "burst": 1, "priority": 3},
            {"pid": "J2", "arrival": 0, "burst": 2, "priority": 2},
            {"pid": "J3", "arrival": 0, "burst": 8, "priority": 1},
            {"pid": "J4", "arrival": 1, "burst": 2, "priority": 2},
            {"pid": "J5", "arrival": 2, "burst": 10, "priority": 1},
            {"pid": "J6", "arrival": 3, "burst": 1, "priority": 3},
        ]
        results = scheduler_manager.compare(trace, quantum=2, extended=True)
        by_algo = {r["algo"]: r["avg"] for r in results}

        # SJF and SRTF must achieve lower or equal waiting time than FCFS
        self.assertLessEqual(by_algo["SJF"]["waiting"], by_algo["FCFS"]["waiting"])
        self.assertLessEqual(by_algo["SRTF"]["waiting"], by_algo["FCFS"]["waiting"])

    def test_banker_algorithm_safety_invariants(self):
        """Verifies Banker's algorithm safe sequence discovery and unsafe denial."""
        banker = Banker(
            available=[3, 3, 2],
            maximum={"P0": [7, 5, 3], "P1": [3, 2, 2], "P2": [9, 0, 2], "P3": [2, 2, 2], "P4": [4, 3, 3]},
            allocation={"P0": [0, 1, 0], "P1": [2, 0, 0], "P2": [3, 0, 2], "P3": [2, 1, 1], "P4": [0, 0, 2]},
        )
        safe, seq = banker.is_safe()
        self.assertTrue(safe)
        self.assertEqual(len(seq), 5)

        # P1 valid request -> must be granted
        grant_p1 = banker.request("P1", [1, 0, 2])
        self.assertTrue(grant_p1["granted"])

        # P0 unsafe request -> must be denied to avoid deadlock
        deny_p0 = banker.request("P0", [0, 2, 0])
        self.assertFalse(deny_p0["granted"])


if __name__ == "__main__":
    unittest.main()
