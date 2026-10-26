"""NEXUS-OS TCP Client & Connection Layer with Dual Logical Clocks.
Maintains Lamport logical timestamps and Vector Clocks across request/response envelopes.
Concept: Dual logical timestamping for causal message ordering and concurrency tracking.
"""

import itertools
import json
import socket
import threading
from distributed_clock.lamport_clock import LamportClock
from distributed_clock.vector_clock import VectorClock


class Conn:
    """Thread-safe wrapper around a socket. One JSON message per line."""
    def __init__(self, sock):
        self.sock = sock
        self.rfile = sock.makefile("r", encoding="utf-8")
        self._wlock = threading.Lock()

    def send(self, msg, max_size=16 * 1024 * 1024):
        if not isinstance(msg, dict):
            msg = {"type": "ERROR", "error": "Message payload must be a dictionary"}
        data = (json.dumps(msg) + "\n").encode("utf-8")
        if len(data) > max_size:
            err_dict = {"type": "ERROR", "error": f"Message size {len(data)} exceeds limit {max_size}"}
            data = (json.dumps(err_dict) + "\n").encode("utf-8")
        with self._wlock:
            self.sock.sendall(data)

    def recv(self, max_size=16 * 1024 * 1024):
        line = self.rfile.readline(max_size)
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {"type": "ERROR", "error": "Malformed JSON payload"}

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Client:
    """Request/response client used by the dashboard, CLI and tests."""
    def __init__(self, host="127.0.0.1", port=9000, client_id="client"):
        self.client_id = client_id
        self.conn = Conn(socket.create_connection((host, int(port))))
        self.clock = LamportClock()
        self.vc = VectorClock(node_id=client_id)
        self._id = itertools.count()

    def call(self, msg):
        msg["ts"] = self.clock.tick()
        msg["vc"] = self.vc.tick()
        msg["req_id"] = next(self._id)
        self.conn.send(msg)
        while (r := self.conn.recv()) is not None:
            if "ts" in r:
                self.clock.update(r["ts"])
            if "vc" in r:
                self.vc.update(r["vc"])
            if r.get("req_id") == msg["req_id"]:
                return r
        return None

    def close(self):
        self.conn.close()
