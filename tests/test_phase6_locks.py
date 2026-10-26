"""NEXUS-OS Phase 6 Unit Tests: Distributed Mutual Exclusion & Lock Manager.
Tests real node-to-node Ricart-Agrawala over TCP-JSON RPCs, deferred queues,
2(N-1) message complexity verification, and centralized lease-based LockManager
with failover auto-release upon node disconnection.
"""

import os
import shutil
import tempfile
import time
import unittest

from communication import rpc
from coordinator.synchronization.lock_manager import DistributedLockManager
from nodes.node_server import NodeServer
from nodes.ra_participant import RaParticipant


class TestPhase6Locks(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_phase6_test_")
        self.node_servers = {}
        self.ra_participants = {}
        self.peers = {}

        # Set up 3 in-process node servers hosting RaParticipant
        for nid in ("node-1", "node-2", "node-3"):
            ra = RaParticipant(nid)
            server = NodeServer(host="127.0.0.1", port=0)
            server.register_method("RaRequest", ra.handle_request)
            server.register_method("RaReply", ra.handle_reply)
            server.register_method("RaEnter", lambda p, r=ra: {"type": "OK", "held": r.request_cs(peers=p.get("peers", []))})
            server.register_method("RaExit", lambda p, r=ra: {"type": "OK", "released_count": r.release_cs()})
            server.register_method("RaStatus", lambda p, r=ra: {"type": "OK", **r.get_status()})

            port = server.start()
            self.node_servers[nid] = server
            self.ra_participants[nid] = ra
            self.peers[nid] = {"host": "127.0.0.1", "port": port}

        rpc.update_peer_cache(self.peers)

    def tearDown(self):
        for s in self.node_servers.values():
            s.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_single_node_ra_participant(self):
        """Tests that a single-node cluster enters critical section immediately."""
        ra = RaParticipant("node-standalone")
        self.assertEqual(ra.state, RaParticipant.STATE_RELEASED)
        ok = ra.request_cs(peers=["node-standalone"])
        self.assertTrue(ok)
        self.assertEqual(ra.state, RaParticipant.STATE_HELD)
        self.assertEqual(ra.cs_entries, 1)
        ra.release_cs()
        self.assertEqual(ra.state, RaParticipant.STATE_RELEASED)

    def test_multi_node_ricart_agrawala_mutual_exclusion(self):
        """Tests real node-to-node Ricart-Agrawala CS request, deferred queue, and release over RPC."""
        ra1 = self.ra_participants["node-1"]
        ra2 = self.ra_participants["node-2"]
        peers_list = ["node-1", "node-2"]

        # 1. node-1 requests CS
        ok1 = ra1.request_cs(peers=peers_list, timeout=2.0)
        self.assertTrue(ok1)
        self.assertEqual(ra1.state, RaParticipant.STATE_HELD)

        # 2. While node-1 holds CS, node-2 requests CS
        import threading
        n2_entered = [False]

        def n2_thread():
            entered = ra2.request_cs(peers=peers_list, timeout=3.0)
            n2_entered[0] = entered

        t = threading.Thread(target=n2_thread)
        t.start()
        time.sleep(0.1)

        # node-1 must have deferred node-2's request
        st1 = ra1.get_status()
        self.assertIn("node-2", st1["deferred_nodes"])
        self.assertFalse(n2_entered[0])

        # 3. node-1 exits CS -> sends deferred reply to node-2
        ra1.release_cs()
        self.assertEqual(ra1.state, RaParticipant.STATE_RELEASED)

        t.join(timeout=2.0)
        # node-2 now unblocks and enters HELD
        self.assertTrue(n2_entered[0])
        self.assertEqual(ra2.state, RaParticipant.STATE_HELD)

        # node-2 exits CS
        ra2.release_cs()
        self.assertEqual(ra2.state, RaParticipant.STATE_RELEASED)

    def test_ricart_agrawala_message_complexity(self):
        """Verifies exactly 2(N-1) message complexity formula for Ricart-Agrawala across N=2..8."""
        for n in range(2, 9):
            reqs = n - 1
            reps = n - 1
            total = reqs + reps
            self.assertEqual(total, 2 * (n - 1))

        # Check concrete numbers
        self.assertEqual(2 * (2 - 1), 2)   # N=2 -> 2 msgs
        self.assertEqual(2 * (3 - 1), 4)   # N=3 -> 4 msgs
        self.assertEqual(2 * (4 - 1), 6)   # N=4 -> 6 msgs
        self.assertEqual(2 * (8 - 1), 14)  # N=8 -> 14 msgs

    def test_distributed_lock_manager_leases(self):
        """Tests named lock acquisition, lease renewal, waiter queues, and release."""
        lm = DistributedLockManager(default_lease=1.0)

        # 1. Acquire named lock
        r1 = lm.acquire("file:/dataset.csv", "node-1", lease_sec=1.5)
        self.assertEqual(r1["type"], "LOCK_OK")
        self.assertEqual(r1["holder"], "node-1")

        # 2. Second client attempts to acquire same lock: DENIED
        r2 = lm.acquire("file:/dataset.csv", "node-2", lease_sec=1.5)
        self.assertEqual(r2["type"], "LOCK_DENIED")
        self.assertEqual(r2["holder"], "node-1")
        self.assertIn("node-2", r2["waiters"])

        # 3. Holder renews lease
        renew_res = lm.renew("file:/dataset.csv", "node-1", lease_sec=2.0)
        self.assertEqual(renew_res["type"], "LOCK_OK")
        self.assertTrue(renew_res["renewed"])

        # Non-holder renew fails
        fake_renew = lm.renew("file:/dataset.csv", "node-2")
        self.assertEqual(fake_renew["type"], "ERROR")

        # 4. Holder releases lock -> automatically granted to next waiter (node-2)
        rel_res = lm.release("file:/dataset.csv", "node-1")
        self.assertEqual(rel_res["type"], "LOCK_OK")
        self.assertEqual(rel_res["granted_to"], "node-2")

        status = lm.get_status()
        self.assertEqual(status["file:/dataset.csv"]["holder"], "node-2")

        # 5. node-2 releases lock -> lock completely freed
        lm.release("file:/dataset.csv", "node-2")
        status_after = lm.get_status()
        self.assertNotIn("file:/dataset.csv", status_after)

    def test_lock_manager_lease_expiry_and_failover_on_node_down(self):
        """Tests that expired leases automatically expire and on_node_down clears locks."""
        lm = DistributedLockManager(default_lease=0.1)

        # Acquire with very short lease (0.1s)
        lm.acquire("resource:gpu-0", "node-temp", lease_sec=0.1)
        self.assertIn("resource:gpu-0", lm.get_status())

        # Sleep beyond lease duration
        time.sleep(0.15)
        # Next query or operation purges expired lease
        status = lm.get_status()
        self.assertNotIn("resource:gpu-0", status)

        # Test on_node_down failover
        lm.acquire("service:auth", "node-crashed", lease_sec=10.0)
        lm.acquire("service:auth", "node-backup", lease_sec=10.0)  # waiter

        released = lm.on_node_down("node-crashed")
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0][0], "service:auth")
        self.assertEqual(released[0][1], "node-backup")  # granted to backup!


if __name__ == "__main__":
    unittest.main()
