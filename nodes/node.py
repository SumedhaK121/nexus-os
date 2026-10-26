"""NEXUS-OS Node: registers, sends heartbeats, executes tasks pushed by the coordinator,
and runs an internal RPC server for peer-to-peer data plane interactions.
"""

import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication.tcp_client import Conn
from communication import rpc
from distributed_clock.lamport_clock import LamportClock
from nodes.node_server import NodeServer


class Node:
    def __init__(self, node_id, host="127.0.0.1", port=9000):
        self.id = node_id
        self.host = host
        self.coord_port = port
        self.clock = LamportClock()
        self.running = True
        self.conn = None

        # Start internal RPC server on an OS-assigned free port
        self.server = NodeServer(host=os.environ.get("NEXUS_BIND", "127.0.0.1"), port=0)
        self.rpc_port = self.server.start()

        # Node hardware capacities
        self.cpu_slots = int(os.environ.get("NEXUS_CPU_SLOTS", 2))
        self.mem_mb = int(os.environ.get("NEXUS_MEM_MB", 256))
        self.io_slots = int(os.environ.get("NEXUS_IO_SLOTS", 2))

        # Connect to coordinator with retries
        for _ in range(30):
            try:
                self.conn = Conn(socket.create_connection((host, port)))
                break
            except OSError:
                time.sleep(1)
        if not self.conn:
            print(f"[{self.id}] Failed to connect to coordinator at {host}:{port}", flush=True)

    def send(self, msg):
        msg["ts"] = self.clock.tick()
        if self.conn:
            self.conn.send(msg)

    def run(self):
        # Register with coordinator including RPC server port and capacities
        reg_payload = {
            "type": "REGISTER",
            "node_id": self.id,
            "addr": [self.server.host, self.rpc_port],
            "cpu_slots": self.cpu_slots,
            "mem_mb": self.mem_mb,
            "io_slots": self.io_slots,
        }
        self.send(reg_payload)

        # Start periodic heartbeat thread
        threading.Thread(target=self._heartbeat, daemon=True).start()

        # Main message loop from coordinator
        while self.running and self.conn:
            try:
                msg = self.conn.recv()
            except (OSError, ValueError):
                break
            if msg is None:
                break
            self.clock.update(msg.get("ts", 0))
            mtype = msg.get("type")
            if mtype == "EXEC":
                threading.Thread(target=self._exec, args=(msg,), daemon=True).start()
            elif mtype == "REGISTERED":
                # Request peers
                self.send({"type": "PEERS"})
            elif mtype == "PEERS":
                rpc.update_peer_cache(msg.get("peers", {}))

    def _exec(self, m):
        print(f"[{self.id}] T={self.clock.t} running {m['pid']} (burst {m['burst']})", flush=True)
        # Phase 0 simulated CPU work (Phase 1 will add real subprocess execution)
        time.sleep(m["burst"] * 0.3)
        self.send({"type": "TASK_DONE", "pid": m["pid"]})

    def _heartbeat(self):
        while self.running:
            cpu = round(os.getloadavg()[0] * 10, 1) if hasattr(os, "getloadavg") else 0.0
            try:
                self.send({"type": "HEARTBEAT", "cpu": cpu, "node_id": self.id})
            except OSError:
                return
            time.sleep(2)


if __name__ == "__main__":
    node_id = sys.argv[1] if len(sys.argv) > 1 else "node-1"
    coord_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
    Node(node_id, port=coord_port).run()
