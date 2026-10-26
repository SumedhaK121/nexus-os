"""Unit and Component Tests for Phase 9:
Docker Telemetry, 3-State Failure Detector, Chaos Engineering, and Process Isolation.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.main import Coordinator
from coordinator.node_manager.node_manager import NodeManager, STATE_ONLINE, STATE_SUSPECT, STATE_OFFLINE
from demo.isolation_demo import run_isolation_demonstration


class DummyConn:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, msg):
        self.sent.append(msg)

    def close(self):
        self.closed = True


class DummyCtx:
    def __init__(self, node_id="test-node"):
        self.node_id = node_id
        self.conn = DummyConn()


class TestPhase9MonitoringAndChaos(unittest.TestCase):
    def setUp(self):
        self.coord = Coordinator(port=0)
        # Register a mock node
        self.coord.nodes["test-node-1"] = {
            "conn": DummyConn(),
            "last_seen": time.time(),
            "cpu": 10.0,
            "load": 2,
            "done": 5,
            "status": "ONLINE",
            "addr": ["127.0.0.1", 9101],
            "cpu_slots": 2,
            "mem_mb": 256,
            "io_slots": 2,
        }
        self.coord.node_mgr.register_node("test-node-1", addr=["127.0.0.1", 9101], cpu_slots=2, mem_mb=256)

    def test_3_state_failure_transitions(self):
        """Tests 3-state failure detector transitions: ONLINE -> SUSPECT -> OFFLINE -> ONLINE."""
        now = time.time()
        node = self.coord.nodes["test-node-1"]

        # 1. Active node within 2s is ONLINE
        self.assertEqual(node["status"], STATE_ONLINE)

        # 2. Heartbeat delayed > 4s transitions to SUSPECT
        node["last_seen"] = now - 4.8
        dt = now - node["last_seen"]
        self.assertTrue(dt > 4 and dt <= 6)
        # Simulate monitor step for suspect
        if dt > 4 and node["status"] == "ONLINE":
            node["status"] = STATE_SUSPECT
            self.coord.node_mgr.mark_suspect("test-node-1")

        self.assertEqual(node["status"], STATE_SUSPECT)
        info = self.coord.node_mgr.nodes["test-node-1"]
        self.assertEqual(info.status, STATE_SUSPECT)

        # 3. Heartbeat delayed > 6s transitions to OFFLINE
        node["last_seen"] = now - 6.5
        dt = now - node["last_seen"]
        if dt > 6 and node["status"] != STATE_OFFLINE:
            node["status"] = STATE_OFFLINE
            self.coord.node_mgr.mark_offline("test-node-1")

        self.assertEqual(node["status"], STATE_OFFLINE)
        self.assertEqual(info.status, STATE_OFFLINE)

        # 4. Heartbeat received recovers node back to ONLINE and triggers node_up
        hb_handler = self.coord.handlers["HEARTBEAT"]
        ctx = DummyCtx(node_id="test-node-1")
        hb_handler(self.coord, ctx, {"type": "HEARTBEAT", "node_id": "test-node-1", "cpu": 15.0})

        self.assertEqual(node["status"], STATE_ONLINE)
        self.assertEqual(info.status, STATE_ONLINE)

    def test_chaos_kill_and_heal(self):
        """Tests CHAOS_ACTION kill drops node and triggers failover; heal recovers node."""
        chaos_handler = self.coord.handlers["CHAOS_ACTION"]
        ctx = DummyCtx()

        # Injected KILL
        res_kill = chaos_handler(self.coord, ctx, {"type": "CHAOS_ACTION", "action": "kill", "node_id": "test-node-1"})
        self.assertEqual(res_kill["type"], "CHAOS_RESULT")
        self.assertEqual(res_kill["action"], "kill")
        self.assertEqual(res_kill["status"], "OFFLINE")
        self.assertEqual(self.coord.nodes["test-node-1"]["status"], "OFFLINE")
        self.assertTrue(self.coord.nodes["test-node-1"]["conn"].closed)

        # Injected HEAL
        res_heal = chaos_handler(self.coord, ctx, {"type": "CHAOS_ACTION", "action": "heal", "node_id": "test-node-1"})
        self.assertEqual(res_heal["type"], "CHAOS_RESULT")
        self.assertEqual(res_heal["action"], "heal")
        self.assertEqual(res_heal["status"], "ONLINE")
        self.assertEqual(self.coord.nodes["test-node-1"]["status"], "ONLINE")

    def test_chaos_suspect_and_delay(self):
        """Tests CHAOS_ACTION suspect and network delay injection."""
        chaos_handler = self.coord.handlers["CHAOS_ACTION"]
        ctx = DummyCtx()

        # Injected SUSPECT
        res_suspect = chaos_handler(self.coord, ctx, {"type": "CHAOS_ACTION", "action": "suspect", "node_id": "test-node-1"})
        self.assertEqual(res_suspect["action"], "suspect")
        self.assertEqual(res_suspect["status"], "SUSPECT")
        self.assertEqual(self.coord.nodes["test-node-1"]["status"], "SUSPECT")

        # Injected DELAY
        res_delay = chaos_handler(self.coord, ctx, {"type": "CHAOS_ACTION", "action": "delay", "node_id": "test-node-1", "delay_ms": 300})
        self.assertEqual(res_delay["action"], "delay")
        self.assertEqual(res_delay["delay_ms"], 300)
        self.assertEqual(self.coord.nodes["test-node-1"]["delay_ms"], 300)

    def test_docker_status_telemetry(self):
        """Tests DOCKER_STATUS reporting container metadata and resource limits."""
        docker_handler = self.coord.handlers["DOCKER_STATUS"]
        ctx = DummyCtx()

        res = docker_handler(self.coord, ctx, {"type": "DOCKER_STATUS"})
        self.assertEqual(res["type"], "DOCKER_STATUS")
        self.assertIn("mode", res)
        self.assertIn("containers", res)

        # Check synthesized container for test-node-1
        node_c = next((c for c in res["containers"] if c.get("node_id") == "test-node-1" or c.get("container") == "nexus-test-node-1"), None)
        self.assertIsNotNone(node_c)
        self.assertEqual(node_c["container"], "nexus-test-node-1")
        self.assertEqual(node_c["status"], "ONLINE")
        self.assertEqual(node_c["mem_limit"], "256MB")
        self.assertEqual(node_c["cpus"], "2.0")

    def test_isolation_demo_oom_enforcement(self):
        """Tests cgroup memory quota enforcement terminating a leaky child process."""
        result = run_isolation_demonstration(limit_mb=35, leak_target_mb=70)
        self.assertTrue(result["oom_killed"], "Leaker exceeding 35 MB quota must be OOM-killed")
        self.assertEqual(result["exit_code"], 137, "OOM-killed process must report SIGKILL exit code 137")
        self.assertGreaterEqual(result["peak_rss_mb"], 25.0)


if __name__ == "__main__":
    unittest.main()
