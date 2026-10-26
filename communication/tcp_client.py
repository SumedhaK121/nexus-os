import json, socket, itertools, threading
from distributed_clock.lamport_clock import LamportClock


class Conn:
    """Thread-safe wrapper around a socket. One JSON message per line."""
    def __init__(self, sock):
        self.sock = sock
        self.rfile = sock.makefile("r", encoding="utf-8")
        self._wlock = threading.Lock()
    def send(self, msg):
        data = (json.dumps(msg) + "\n").encode()
        with self._wlock:
            self.sock.sendall(data)
    def recv(self):
        line = self.rfile.readline()
        return json.loads(line) if line else None
    def close(self):
        try: self.sock.close()
        except OSError: pass


class Client:
    """Request/response client used by the dashboard, CLI and tests."""
    def __init__(self, host="127.0.0.1", port=9000):
        self.conn, self.clock, self._id = Conn(socket.create_connection((host, port))), LamportClock(), itertools.count()
    def call(self, msg):
        msg["ts"], msg["req_id"] = self.clock.tick(), next(self._id)
        self.conn.send(msg)
        while (r := self.conn.recv()) is not None:
            self.clock.update(r.get("ts", 0))
            if r.get("req_id") == msg["req_id"]: return r
