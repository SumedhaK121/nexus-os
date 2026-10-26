import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NEXUS-OS Node: registers, sends heartbeats, executes tasks pushed by the coordinator."""
import socket, threading, time, sys, os
from communication.tcp_client import Conn
from distributed_clock.lamport_clock import LamportClock

class Node:
    def __init__(self, node_id, host="127.0.0.1", port=9000):
        self.id, self.clock = node_id, LamportClock()
        for _ in range(30):
            try: self.conn = Conn(socket.create_connection((host, port))); break
            except OSError: time.sleep(1)
        self.running = True

    def send(self, msg): msg["ts"] = self.clock.tick(); self.conn.send(msg)

    def run(self):
        self.send({"type": "REGISTER", "node_id": self.id})
        threading.Thread(target=self._heartbeat, daemon=True).start()
        while self.running and (msg := self.conn.recv()) is not None:
            self.clock.update(msg.get("ts", 0))
            if msg["type"] == "EXEC":
                threading.Thread(target=self._exec, args=(msg,), daemon=True).start()
            # TODO teammates: handle LOCK_REQUEST/LOCK_REPLY (Ricart-Agrawala), FILE_SYNC, etc. here

    def _exec(self, m):
        print(f"[{self.id}] T={self.clock.t} running {m['pid']} (burst {m['burst']})", flush=True)
        time.sleep(m["burst"] * 0.3)   # simulated CPU work
        self.send({"type": "TASK_DONE", "pid": m["pid"]})

    def _heartbeat(self):
        while self.running:
            cpu = round(os.getloadavg()[0] * 10, 1) if hasattr(os, "getloadavg") else 0
            try: self.send({"type": "HEARTBEAT", "cpu": cpu})
            except OSError: return
            time.sleep(2)

if __name__ == "__main__":
    Node(sys.argv[1], port=int(sys.argv[2]) if len(sys.argv) > 2 else 9000).run()
