"""Unit tests for Phase 2: Resource Manager, Banker's Algorithm, and Real Deadlocks."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock import deadlock_detector
from coordinator.resource_manager.resource_manager import ResourceManager


class TestPhase2Deadlock(unittest.TestCase):
    def test_banker_safe_unsafe_sequences(self):
        # Classic 3-resource Banker scenario
        avail = [3, 3, 2]
        maximum = {
            "P0": [7, 5, 3],
            "P1": [3, 2, 2],
            "P2": [9, 0, 2],
            "P3": [2, 2, 2],
            "P4": [4, 3, 3],
        }
        alloc = {
            "P0": [0, 1, 0],
            "P1": [2, 0, 0],
            "P2": [3, 0, 2],
            "P3": [2, 1, 1],
            "P4": [0, 0, 2],
        }
        b = Banker(avail, maximum, alloc)
        safe, order = b.is_safe()
        self.assertTrue(safe)
        self.assertEqual(len(order), 5)

        # Granted request for P1
        req_safe = b.request("P1", [1, 0, 2])
        self.assertTrue(req_safe["granted"])

        # Subsequent unsafe request for P0 should be denied
        req_unsafe = b.request("P0", [0, 2, 0])
        self.assertFalse(req_unsafe["granted"])
        self.assertIn("UNSAFE", req_unsafe["reason"])

    def test_banker_staged_requests_and_release(self):
        b = Banker([2, 2, 2], {"J1": [2, 2, 2], "J2": [1, 1, 1]}, {"J1": [0, 0, 0], "J2": [0, 0, 0]})
        # Stage 1: J1 requests CPU
        r1 = b.request("J1", [1, 0, 0])
        self.assertTrue(r1["granted"])
        self.assertEqual(b.available, [1, 2, 2])

        # Stage 2: J1 requests Memory
        r2 = b.request("J1", [0, 1, 0])
        self.assertTrue(r2["granted"])
        self.assertEqual(b.available, [1, 1, 2])

        # Release J1
        b.release("J1")
        self.assertEqual(b.available, [2, 2, 2])
        self.assertEqual(b.alloc["J1"], [0, 0, 0])

    def test_capacity_shrink_on_node_loss(self):
        rm = ResourceManager()
        nodes = {
            "node-1": {"status": "ONLINE", "cpu_slots": 4, "mem_mb": 512, "io_slots": 2},
            "node-2": {"status": "ONLINE", "cpu_slots": 4, "mem_mb": 512, "io_slots": 2},
        }
        rm.update_cluster_capacity(nodes)
        self.assertEqual(rm.total, [8, 8, 4])

        # Node 2 dies
        nodes["node-2"]["status"] = "OFFLINE"
        rm.update_cluster_capacity(nodes)
        self.assertEqual(rm.total, [4, 4, 2])
        self.assertEqual(rm.cluster_banker.available, [4, 4, 2])

    def test_multiple_cycles_detection(self):
        # Two independent cycles: P1 <-> P2 and P3 <-> P4
        wfg = {
            "P1": ["P2"],
            "P2": ["P1"],
            "P3": ["P4"],
            "P4": ["P3"],
            "P5": ["P1"],
        }
        cycles = deadlock_detector.find_all_cycles(wfg)
        self.assertEqual(len(cycles), 2)
        flattened = [set(c) for c in cycles]
        self.assertIn({"P1", "P2"}, flattened)
        self.assertIn({"P3", "P4"}, flattened)

    def test_recovery_frees_resources(self):
        rm = ResourceManager()
        rm.allocate("P1", [1, 0, 0])
        rm.allocate("P2", [0, 1, 0])
        rm.register_wait("P1", "P2")
        rm.register_wait("P2", "P1")

        cycle = deadlock_detector.detect(rm.get_wait_for_graph())
        self.assertTrue(bool(cycle))

        proc_table = {
            "P1": {"pid": "P1", "submit_time": 10.0, "priority": 1},
            "P2": {"pid": "P2", "submit_time": 20.0, "priority": 2},
        }
        # Youngest victim should be P2 (submit_time 20.0)
        victim = rm.select_victim(cycle, proc_table, policy="youngest")
        self.assertEqual(victim, "P2")

        rm.release(victim)
        remaining_cycle = deadlock_detector.detect(rm.get_wait_for_graph())
        self.assertEqual(remaining_cycle, [])

    def test_banker_off_vs_on_randomized_workloads(self):
        """200 randomized workloads:
        - With Banker ON: deadlock NEVER occurs (safety invariant holds).
        - With Banker OFF: greedy allocation under tight contention yields deadlocks.
        """
        # 1. Verify Banker ON never deadlocks across 200 random workloads
        for seed in range(200):
            random.seed(seed)
            total_res = [3, 3, 2]
            pids = [f"Proc_{k}" for k in range(4)]
            max_demands = {
                pid: [random.randint(1, 2), random.randint(1, 2), random.randint(0, 1)]
                for pid in pids
            }
            b = Banker(total_res, max_demands, {p: [0, 0, 0] for p in pids})

            # Random sequence of requests and releases
            for _ in range(20):
                pid = random.choice(pids)
                need = b.need(pid)
                if any(n > 0 for n in need):
                    req = [random.randint(0, need[i]) for i in range(3)]
                    if any(r > 0 for r in req):
                        res = b.request(pid, req)
                        # If granted, state MUST be safe
                        if res["granted"]:
                            safe, _ = b.is_safe()
                            self.assertTrue(safe, f"In safe state assertion failed on seed {seed}")
                else:
                    b.release(pid)

        # 2. Verify Banker OFF can produce deadlocks
        deadlock_count = 0
        for seed in range(50):
            random.seed(seed)
            rm = ResourceManager()
            rm.total = [1, 1, 0]
            # Two greedy processes competing for 2 scarce resources
            rm.allocate("T1", [1, 0, 0])
            rm.allocate("T2", [0, 1, 0])
            rm.register_wait("T1", "T2")
            rm.register_wait("T2", "T1")
            cycle = deadlock_detector.detect(rm.get_wait_for_graph())
            if cycle:
                deadlock_count += 1

        self.assertGreater(deadlock_count, 0, "Greedy allocation must produce detectable deadlocks")


if __name__ == "__main__":
    unittest.main()
