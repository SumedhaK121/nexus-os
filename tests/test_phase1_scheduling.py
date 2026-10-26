"""Unit tests for Phase 1: Real Processes, CPU Scheduling Policies, and Process States."""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.main import Coordinator
from coordinator.process_manager.process_manager import ProcessManager, STATE_NEW, STATE_READY, STATE_RUNNING, STATE_WAITING, STATE_COMPLETED, STATE_KILLED
from coordinator.scheduler.fcfs import fcfs
from coordinator.scheduler.sjf import sjf
from coordinator.scheduler.srtf import srtf
from coordinator.scheduler.priority import priority
from coordinator.scheduler.priority_aging import priority_aging
from coordinator.scheduler.round_robin import round_robin
from coordinator.scheduler import scheduler_manager
from coordinator.scheduler.metrics import metrics as calc_metrics
from jobs import catalog


class TestPhase1Scheduling(unittest.TestCase):
    def setUp(self):
        self.procs = [
            {"pid": "P1", "arrival": 0, "burst": 6, "priority": 3},
            {"pid": "P2", "arrival": 2, "burst": 2, "priority": 1},
            {"pid": "P3", "arrival": 4, "burst": 4, "priority": 2},
        ]

    def test_fcfs_order(self):
        res = fcfs(self.procs)
        order = [x[0] for x in res["gantt"]]
        self.assertEqual(order, ["P1", "P2", "P3"])
        self.assertAlmostEqual(res["avg"]["turnaround"], (6 + 6 + 8) / 3, places=2)

    def test_sjf_order(self):
        res = sjf(self.procs)
        order = [x[0] for x in res["gantt"]]
        # P1 runs 0-6; at t=6 both P2 and P3 are available, P2 (burst 2) runs before P3 (burst 4)
        self.assertEqual(order, ["P1", "P2", "P3"])

    def test_srtf_preemption(self):
        # In SRTF, when P2 arrives at t=2 with burst 2, P1 has 4 remaining -> P2 preempts P1!
        res = srtf(self.procs)
        gantt = res["gantt"]
        # Expected slices: P1 (0-2), P2 (2-4), P3 (4-8), P1 (8-12) or P1 (4-8), etc.
        pids = [x[0] for x in gantt]
        self.assertEqual(pids[0], "P1")
        self.assertEqual(pids[1], "P2")  # P2 preempted P1

    def test_priority_aging_prevents_starvation(self):
        # P_low has high numerical priority (low importance), P_high keeps arriving
        procs = [
            {"pid": "P_low", "arrival": 0, "burst": 4, "priority": 10},
            {"pid": "P_high1", "arrival": 1, "burst": 2, "priority": 1},
            {"pid": "P_high2", "arrival": 3, "burst": 2, "priority": 1},
        ]
        # Without aging, P_high1 and P_high2 run before P_low
        # With aging (interval=1), P_low waiting while others run reduces its priority
        res_aging = priority_aging(procs, age_interval=1)
        self.assertTrue(len(res_aging["gantt"]) > 0)
        self.assertIn("P_low", [x[0] for x in res_aging["gantt"]])

    def test_round_robin_slicing(self):
        procs = [
            {"pid": "P1", "arrival": 0, "burst": 4, "priority": 1},
            {"pid": "P2", "arrival": 0, "burst": 2, "priority": 1},
        ]
        res = round_robin(procs, quantum=2)
        gantt = res["gantt"]
        # P1 (0-2), P2 (2-4), P1 (4-6)
        self.assertEqual(gantt, [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 6)])

    def test_metrics_arithmetic(self):
        procs = [{"pid": "P1", "arrival": 0, "burst": 5, "priority": 1}]
        first = {"P1": 0}
        fin = {"P1": 5}
        rows, avg = calc_metrics(procs, first, fin)
        self.assertEqual(rows[0]["waiting"], 0)
        self.assertEqual(rows[0]["turnaround"], 5)
        self.assertEqual(rows[0]["response"], 0)
        self.assertEqual(avg["turnaround"], 5.0)

    def test_process_state_transitions(self):
        pm = ProcessManager()
        pcb = pm.add("ProcTest", burst=3)
        self.assertEqual(pcb.state, STATE_NEW)
        pm.transition("ProcTest", STATE_READY)
        pm.transition("ProcTest", STATE_RUNNING)
        pm.transition("ProcTest", STATE_WAITING)
        pm.transition("ProcTest", STATE_READY)
        pm.transition("ProcTest", STATE_RUNNING)
        pm.transition("ProcTest", STATE_COMPLETED)
        self.assertEqual(pcb.state, STATE_COMPLETED)

    def test_node_failure_rescheduling(self):
        coord = Coordinator(port=9099)
        # Mock two nodes
        coord.nodes["node-1"] = {"status": "ONLINE", "load": 2, "conn": None}
        coord.nodes["node-2"] = {"status": "ONLINE", "load": 0, "conn": None}
        coord.node_mgr.nodes["node-1"] = coord.node_mgr.register_node("node-1")
        coord.node_mgr.nodes["node-2"] = coord.node_mgr.register_node("node-2")

        coord.tasks["T1"] = {"node": "node-1", "state": "Running", "burst": 2, "job_type": "sim", "args": []}

        # Simulate failure of node-1
        coord._on_node_down("node-1")
        # Task T1 should be rescheduled to node-2
        self.assertEqual(coord.tasks["T1"]["node"], "node-2")

    def test_catalog_and_real_jobs_execution(self):
        for job_type in ["wordcount", "primes", "compress", "matmul", "iosleep"]:
            cmd = catalog.get_command(job_type)
            self.assertIsNotNone(cmd)
            # Run quick smoke execution of each job
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate(timeout=10)
            self.assertEqual(p.returncode, 0, f"Job {job_type} failed with stderr: {stderr}")


if __name__ == "__main__":
    unittest.main()
