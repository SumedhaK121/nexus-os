"""Unit tests for NEXUS-OS Core Subsystems.
Converts all original test_core assertions to unittest.TestCase while adding
coverage for Phase 0 architectural components and bug fixes.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock.deadlock_detector import detect, SCENARIOS
from coordinator.file_manager.file_manager import FileManager
from coordinator.file_manager.page_replacement import simulate as ps
from coordinator.node_manager.node_manager import NodeManager, online, STATE_ONLINE, STATE_OFFLINE
from coordinator.process_manager.process_manager import ProcessManager, summary, STATE_RUNNING, STATE_COMPLETED
from coordinator.resource_manager.resource_manager import ResourceManager, utilization
from coordinator.scheduler.scheduler_manager import compare
from coordinator.synchronization.primitives import producer_consumer, mutex_demo
from coordinator.synchronization.ricart_agrawala import simulate


class TestSchedulerCore(unittest.TestCase):
    def test_compare_algorithms(self):
        procs = [
            {"pid": "P1", "arrival": 0, "burst": 4, "priority": 2},
            {"pid": "P2", "arrival": 1, "burst": 2, "priority": 1},
        ]
        results = compare(procs)
        self.assertEqual(len(results), 4)


class TestBankerCore(unittest.TestCase):
    def test_banker_safety_and_requests(self):
        b = Banker(
            [3, 3, 2],
            {"P0": [7, 5, 3], "P1": [3, 2, 2], "P2": [9, 0, 2], "P3": [2, 2, 2], "P4": [4, 3, 3]},
            {"P0": [0, 1, 0], "P1": [2, 0, 0], "P2": [3, 0, 2], "P3": [2, 1, 1], "P4": [0, 0, 2]},
        )
        safe, order = b.is_safe()
        self.assertTrue(safe)
        req1 = b.request("P1", [1, 0, 2])
        self.assertTrue(req1["granted"])
        req0 = b.request("P0", [0, 2, 0])
        self.assertFalse(req0["granted"])


class TestFileManagerCore(unittest.TestCase):
    def setUp(self):
        self.fm = FileManager(cache_size=2, policy="LRU")
        self.nodes = ["node-1", "node-2", "node-3"]

    def tearDown(self):
        for n in ("a.txt", "b.txt", "c.txt"):
            self.fm.delete(n)

    def test_file_write_read_cache_replication(self):
        for n in "abc":
            self.fm.write(n + ".txt", n * 3, self.nodes)

        first_read = self.fm.read("a.txt")
        self.assertEqual(first_read["source"], "disk")
        second_read = self.fm.read("a.txt")
        self.assertEqual(second_read["source"], "cache")

        self.assertTrue(all(len(v) == 2 for v in self.fm.rep.placement.values()))
        self.assertTrue(self.fm.delete("a.txt"))


class TestSynchronizationCore(unittest.TestCase):
    def test_ricart_agrawala_simulation(self):
        nodes = ["node-1", "node-2", "node-3"]
        r = simulate(nodes, ["node-1", "node-2", "node-3"])
        self.assertEqual(sorted(r["order"]), sorted(nodes))
        self.assertEqual(r["messages"], 12)

    def test_producer_consumer(self):
        log = producer_consumer()
        self.assertEqual(len(log), 12)

    def test_mutex_race_demonstration(self):
        m = mutex_demo()
        self.assertEqual(m["with_mutex"], m["expected"])
        self.assertLess(m["without_mutex"], m["expected"])


class TestDeadlockAndPagingCore(unittest.TestCase):
    def test_deadlock_detection_scenarios(self):
        self.assertTrue(bool(detect(SCENARIOS["circular"])))
        self.assertFalse(bool(detect(SCENARIOS["chain"])))

    def test_page_replacement_simulation(self):
        ref_string = "7,0,1,2,0,3,0,4,2,3,0,3,2".split(",")
        results = {x["algo"]: x["faults"] for x in ps(ref_string, 3)}
        self.assertEqual(results, {"FIFO": 10, "LRU": 9, "Optimal": 7})


class TestPhase0Subsystems(unittest.TestCase):
    def test_node_manager(self):
        nm = NodeManager()
        down_events = []
        nm.subscribe_node_down(lambda nid: down_events.append(nid))
        nm.register_node("node-1", addr=("127.0.0.1", 9001), cpu_slots=4, mem_mb=512)
        self.assertIn("node-1", nm.online())
        nm.mark_offline("node-1")
        self.assertNotIn("node-1", nm.online())
        self.assertEqual(down_events, ["node-1"])

    def test_process_manager_transitions(self):
        pm = ProcessManager()
        pcb = pm.add("P100", burst=5)
        self.assertEqual(pcb.state, "NEW")
        pm.transition("P100", "READY")
        self.assertEqual(pcb.state, "READY")
        pm.transition("P100", "RUNNING")
        self.assertEqual(pcb.state, "RUNNING")
        pm.transition("P100", "COMPLETED")
        self.assertEqual(pcb.state, "COMPLETED")

        # Invalid transition from COMPLETED should raise ValueError
        with self.assertRaises(ValueError):
            pm.transition("P100", "RUNNING")

        s = summary({"P100": {"state": "Completed"}})
        self.assertEqual(s.get("Completed"), 1)

    def test_resource_manager_capacity(self):
        rm = ResourceManager()
        nodes = {
            "node-1": {"status": "ONLINE", "cpu_slots": 4, "mem_mb": 512, "io_slots": 2},
            "node-2": {"status": "ONLINE", "cpu_slots": 2, "mem_mb": 256, "io_slots": 1},
            "node-3": {"status": "OFFLINE", "cpu_slots": 8, "mem_mb": 1024, "io_slots": 4},
        }
        rm.update_cluster_capacity(nodes)
        # node-1 (4 cpu, 4 mem, 2 io) + node-2 (2 cpu, 2 mem, 1 io) = [6, 6, 3]
        self.assertEqual(rm.total, [6, 6, 3])
        avail = rm.get_available()
        self.assertEqual(avail, [6, 6, 3])


if __name__ == "__main__":
    unittest.main()
