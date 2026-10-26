"""NEXUS-OS Phase 5 Unit Tests: Logical Clocks & Merged Event Log.
Tests Lamport Clocks and Fidge-Mattern Vector Clocks:
- tick, update, merge, clone
- Causality comparisons: BEFORE, AFTER, EQUAL, CONCURRENT
- Transitivity and antisymmetry
- Dual timestamp envelopes (ts + vc) across Client, Coordinator, and Node
- Causal event log merging and concurrency detection
"""

import os
import shutil
import tempfile
import time
import unittest

from communication.tcp_client import Client
from coordinator.main import Coordinator
from distributed_clock.lamport_clock import LamportClock
from distributed_clock.vector_clock import VectorClock, happens_before, are_concurrent
from demo.vector_clock_scene import run_vector_clock_scene


class TestPhase5Clocks(unittest.TestCase):
    def test_vector_clock_comparisons(self):
        """Tests partial-order comparisons: BEFORE, AFTER, EQUAL, CONCURRENT."""
        # 1. EQUAL
        vc_a = {"node-1": 2, "node-2": 3}
        vc_b = {"node-1": 2, "node-2": 3}
        self.assertEqual(VectorClock.compare(vc_a, vc_b), VectorClock.REL_EQUAL)

        # 2. BEFORE (Strictly happens-before)
        vc_c = {"node-1": 2, "node-2": 4}
        self.assertEqual(VectorClock.compare(vc_a, vc_c), VectorClock.REL_BEFORE)
        self.assertTrue(happens_before(vc_a, vc_c))
        self.assertFalse(happens_before(vc_c, vc_a))

        # 3. AFTER
        self.assertEqual(VectorClock.compare(vc_c, vc_a), VectorClock.REL_AFTER)

        # 4. CONCURRENT (Independent / conflicting edits)
        vc_d = {"node-1": 3, "node-2": 2}  # node-1 ahead, but node-2 behind
        self.assertEqual(VectorClock.compare(vc_c, vc_d), VectorClock.REL_CONCURRENT)
        self.assertTrue(are_concurrent(vc_c, vc_d))
        self.assertFalse(happens_before(vc_c, vc_d))
        self.assertFalse(happens_before(vc_d, vc_c))

    def test_vector_clock_tick_update_merge(self):
        """Tests ticking local events and updating on message receipt."""
        vc1 = VectorClock("node-1")
        # Tick
        t1 = vc1.tick()
        self.assertEqual(t1["node-1"], 1)

        t2 = vc1.tick()
        self.assertEqual(t2["node-1"], 2)

        # Update on message from node-2
        msg_vc = {"node-2": 5, "coordinator": 1}
        t3 = vc1.update(msg_vc)
        self.assertEqual(t3["node-1"], 3)  # local ticked
        self.assertEqual(t3["node-2"], 5)  # merged max
        self.assertEqual(t3["coordinator"], 1)

        # Pure merge without ticking local
        vc2 = VectorClock("node-2", initial={"node-2": 1})
        m = vc2.merge({"node-1": 10})
        self.assertEqual(m["node-1"], 10)
        self.assertEqual(m["node-2"], 1)

    def test_causal_transitivity(self):
        """Tests that happens-before satisfies transitivity and irreflexivity."""
        e1 = {"A": 1, "B": 0}
        e2 = {"A": 2, "B": 0}
        e3 = {"A": 2, "B": 1}

        self.assertTrue(happens_before(e1, e2))
        self.assertTrue(happens_before(e2, e3))
        # Transitivity: E1 -> E3
        self.assertTrue(happens_before(e1, e3))
        # Irreflexivity: NOT (E1 -> E1)
        self.assertFalse(happens_before(e1, e1))

    def test_dual_timestamp_envelope_over_network(self):
        """Tests that Client and Coordinator exchange both Lamport ts and VectorClock vc."""
        coord = Coordinator(host="127.0.0.1", port=0)
        import threading
        s_thread = threading.Thread(target=coord.serve, daemon=True)
        s_thread.start()
        time.sleep(0.1)

        client = Client(host=coord.host, port=coord.server.getsockname()[1], client_id="test-client")
        try:
            req = {"type": "STATUS"}
            reply = client.call(req)
            self.assertIsNotNone(reply)
            # Verify dual timestamp envelope on reply
            self.assertIn("ts", reply)
            self.assertIn("vc", reply)
            self.assertGreater(reply["ts"], 0)
            self.assertIn("coordinator", reply["vc"])

            # Verify client clock was updated
            self.assertGreaterEqual(client.clock.t, reply["ts"])
            self.assertIn("coordinator", client.vc.to_dict())
        finally:
            client.close()
            coord.server.close()

    def test_causal_event_merging(self):
        """Tests batch EVENTS ingestion and sorting by (Lamport T, node_id)."""
        coord = Coordinator(host="127.0.0.1", port=0)

        class FakeCtx:
            node_id = "node-1"

        ctx = FakeCtx()

        # Submit out-of-order event batches from two nodes
        batch1 = [
            {"ts": 5, "node_id": "node-1", "event": "Task 1 finished", "vc": {"node-1": 3}},
            {"ts": 2, "node_id": "node-1", "event": "Task 1 started", "vc": {"node-1": 1}},
        ]
        batch2 = [
            {"ts": 4, "node_id": "node-2", "event": "Block B cached", "vc": {"node-2": 2}},
            {"ts": 3, "node_id": "node-2", "event": "Block B fetched", "vc": {"node-2": 1}},
        ]

        coord.handlers["EVENTS"](coord, ctx, {"events": batch1, "node_id": "node-1"})
        coord.handlers["EVENTS"](coord, ctx, {"events": batch2, "node_id": "node-2"})

        # Call CAUSAL_LOG
        res = coord.handlers["CAUSAL_LOG"](coord, ctx, {"filter": "all"})
        self.assertEqual(res["type"], "CAUSAL_LOG_RESULT")
        timeline = res["timeline"]
        self.assertEqual(len(timeline), 4)

        # Verify sorted by Lamport timestamp ascending
        ts_seq = [e["T"] for e in timeline]
        self.assertEqual(ts_seq, [2, 3, 4, 5])

    def test_concurrent_demo_scene(self):
        """Tests the end-to-end vector clock concurrency demonstration scene."""
        scene_res = run_vector_clock_scene()
        self.assertTrue(scene_res["e4_e5_concurrent"])
        self.assertTrue(happens_before(scene_res["e1"], scene_res["e2"]))
        self.assertTrue(happens_before(scene_res["e2"], scene_res["e3"]))
        self.assertTrue(happens_before(scene_res["e4"], scene_res["e6"]))
        self.assertTrue(happens_before(scene_res["e5"], scene_res["e6"]))


if __name__ == "__main__":
    unittest.main()
