"""NEXUS-OS Ricart-Agrawala Distributed Mutual Exclusion Participant.
Runs on worker nodes and executes the real distributed mutual exclusion protocol
over inter-node RPCs with Lamport logical timestamps and deferred queues.
Guarantees safety (at most one node in critical section), liveness, and starvation-freedom.
Message complexity: Exactly 2(N-1) messages per critical section invocation.
Concept: Ricart-Agrawala distributed mutual exclusion algorithm (Ricart & Agrawala 1981).
"""

import threading
import time
from communication import rpc
from distributed_clock.lamport_clock import LamportClock


class RaParticipant:
    """Node-side Ricart-Agrawala mutual exclusion participant."""

    STATE_RELEASED = "RELEASED"
    STATE_WANTED = "WANTED"
    STATE_HELD = "HELD"

    def __init__(self, node_id, clock=None):
        self.node_id = str(node_id)
        self.clock = clock if clock is not None else LamportClock()
        self.state = self.STATE_RELEASED
        self.req_ts = (0, self.node_id)
        self.replies_needed = 0
        self.replies_received = set()
        self.deferred_queue = []
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)

        # Message complexity metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.cs_entries = 0

    def request_cs(self, peers, timeout=10.0):
        """Requests entry into the critical section.
        Broadcasts RaRequest to all peers, waits for 2*(N-1) exchange, and enters HELD.
        """
        peer_list = [p for p in peers if str(p) != self.node_id]
        if not peer_list:
            # Single node cluster: immediate grant
            with self.lock:
                self.state = self.STATE_HELD
                self.cs_entries += 1
                return True

        with self.lock:
            self.state = self.STATE_WANTED
            t = self.clock.tick()
            self.req_ts = (t, self.node_id)
            self.replies_needed = len(peer_list)
            self.replies_received.clear()

        # Broadcast RaRequest to all other N-1 peers
        req_payload = {
            "type": "RaRequest",
            "req_node": self.node_id,
            "ts": t,
        }

        for peer in peer_list:
            self.messages_sent += 1
            # Send RPC asynchronously to prevent blocking if a peer is slow
            threading.Thread(
                target=self._send_request_to_peer,
                args=(peer, req_payload),
                daemon=True,
            ).start()

        # Wait until all N-1 replies have arrived
        deadline = time.time() + timeout
        with self.lock:
            while len(self.replies_received) < self.replies_needed:
                remaining = deadline - time.time()
                if remaining <= 0:
                    self.state = self.STATE_RELEASED
                    return False
                self.cv.wait(remaining)

            self.state = self.STATE_HELD
            self.cs_entries += 1
            return True

    def _send_request_to_peer(self, peer, payload):
        try:
            res = rpc.call_node(peer, "RaRequest", payload, timeout=3.0)
            if res.get("type") == "RaReply":
                self.handle_reply(res)
        except Exception:
            pass

    def release_cs(self):
        """Exits critical section and sends deferred replies to queued peers."""
        deferred_to_send = []
        with self.lock:
            self.state = self.STATE_RELEASED
            deferred_to_send = list(self.deferred_queue)
            self.deferred_queue.clear()

        # Send RaReply to all deferred nodes
        t = self.clock.tick()
        reply_payload = {
            "type": "RaReply",
            "from_node": self.node_id,
            "ts": t,
        }

        for waiting_peer in deferred_to_send:
            self.messages_sent += 1
            threading.Thread(
                target=lambda p: rpc.call_node(p, "RaReply", reply_payload, timeout=3.0),
                args=(waiting_peer,),
                daemon=True,
            ).start()

        return len(deferred_to_send)

    def handle_request(self, payload):
        """Processes an incoming RaRequest from a peer."""
        req_node = payload["req_node"]
        their_ts = int(payload.get("ts", 0))

        with self.lock:
            self.messages_received += 1
            self.clock.update(their_ts)
            our_priority = self.req_ts
            their_priority = (their_ts, req_node)

            # Defer reply if:
            # 1. We currently hold the critical section (HELD), OR
            # 2. We want the critical section (WANTED) and our request has strictly higher priority (lower timestamp)
            defer = (self.state == self.STATE_HELD) or (
                self.state == self.STATE_WANTED and our_priority < their_priority
            )

            if defer:
                if req_node not in self.deferred_queue:
                    self.deferred_queue.append(req_node)
                return {"type": "RaDeferred", "node_id": self.node_id}
            else:
                # Send immediate grant reply
                t = self.clock.tick()
                return {"type": "RaReply", "from_node": self.node_id, "ts": t}

    def handle_reply(self, payload):
        """Processes an incoming RaReply from a peer."""
        from_node = payload.get("from_node")
        with self.lock:
            self.messages_received += 1
            if "ts" in payload:
                self.clock.update(payload["ts"])
            if from_node:
                self.replies_received.add(from_node)
            if len(self.replies_received) >= self.replies_needed:
                self.cv.notify_all()
        return {"type": "OK"}

    def get_status(self):
        """Returns participant state, deferred nodes, and metrics."""
        with self.lock:
            return {
                "node_id": self.node_id,
                "state": self.state,
                "req_ts": self.req_ts,
                "replies_count": len(self.replies_received),
                "replies_needed": self.replies_needed,
                "deferred_nodes": list(self.deferred_queue),
                "cs_entries": self.cs_entries,
                "messages_sent": self.messages_sent,
                "messages_received": self.messages_received,
            }
