"""NEXUS-OS Coordinator.
Central control plane for cluster management, job scheduling, distributed file catalog,
and synchronization.
"""

import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication.tcp_client import Conn
from coordinator.api.handlers import install
from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.file_manager.file_manager import FileManager
from coordinator.node_manager.node_manager import NodeManager
from coordinator.process_manager.process_manager import ProcessManager
from coordinator.resource_manager.resource_manager import ResourceManager
from distributed_clock.lamport_clock import LamportClock

# Check optional feature availability
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import grpc
    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False


class Ctx:
    def __init__(self, conn):
        self.conn = conn
        self.node_id = None


class Coordinator:
    def __init__(self, host="127.0.0.1", port=9000):
        self.host = host
        self.port = port
        self.clock = LamportClock()
        self.nodes = {}            # node_id -> {conn, last_seen, cpu, load, done, status, addr}
        self.tasks = {}            # task_id -> {node, state, burst, ...}
        self.events = []           # Lamport-stamped event log
        self.lock = threading.Lock()
        self.handlers = {}
        self.banker = None
        self.files = FileManager()
        self.net = {}

        # Core subsystem managers
        self.node_mgr = NodeManager()
        self.proc_mgr = ProcessManager()
        self.res_mgr = ResourceManager()

        # Subscribe to node failure events
        self.node_mgr.subscribe_node_down(self._on_node_down)
        self.node_mgr.subscribe_node_up(self._on_node_up)

        # Install modular handlers
        install(self)

    def _print_banner(self):
        print("=" * 55, flush=True)
        print(f"  NEXUS-OS Distributed Coordinator (OSDS Final Year)", flush=True)
        print(f"  Listening on {self.host}:{self.port}", flush=True)
        print(f"  Optional Features: gRPC: {'ON' if HAS_GRPC else 'OFF'}, psutil: {'ON' if HAS_PSUTIL else 'OFF'}", flush=True)
        print("=" * 55, flush=True)

    def _on_node_down(self, node_id):
        self.log("coordinator", f"Node failure detected: {node_id} is OFFLINE")
        with self.lock:
            self.res_mgr.update_cluster_capacity(self.nodes)

    def _on_node_up(self, node_id):
        self.log("coordinator", f"Node joined or recovered: {node_id} is ONLINE")
        with self.lock:
            self.res_mgr.update_cluster_capacity(self.nodes)

    # ---------- plugin API ----------
    def handler(self, mtype):
        def deco(fn):
            self.handlers[mtype] = fn
            return fn
        return deco

    def log(self, who, what):
        t = self.clock.tick()
        with self.lock:
            self.events.append({"T": t, "who": who, "event": what})
        print(f"[T={t:>3}] {who}: {what}", flush=True)

    # ---------- server ----------
    def serve(self):
        self._print_banner()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(128)
        self.server = s
        threading.Thread(target=self._monitor, daemon=True).start()
        while True:
            try:
                c, _ = s.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(Conn(c),), daemon=True).start()

    def _client(self, conn):
        ctx = Ctx(conn)
        try:
            while (msg := conn.recv()) is not None:
                self.clock.update(msg.get("ts", 0))
                mtype = msg.get("type", "?")
                if mtype != "STATUS":
                    self.net[mtype] = self.net.get(mtype, 0) + 1
                fn = self.handlers.get(mtype)
                try:
                    if fn:
                        reply = fn(self, ctx, msg)
                    else:
                        reply = {"type": "ERROR", "error": f"unknown type: {mtype}"}
                except Exception as ex:
                    print(f"[Coordinator] error in handler for {mtype}: {ex}", flush=True)
                    reply = {"type": "ERROR", "error": str(ex)}

                if reply is not None:
                    reply["ts"] = self.clock.tick()
                    reply["req_id"] = msg.get("req_id")
                    conn.send(reply)
        except (OSError, ValueError):
            pass
        finally:
            if ctx.node_id:
                with self.lock:
                    if ctx.node_id in self.nodes:
                        self.nodes[ctx.node_id]["status"] = "OFFLINE"
                    self.node_mgr.mark_offline(ctx.node_id)
                self.log("coordinator", f"{ctx.node_id} disconnected")
            conn.close()

    def _monitor(self):
        """Failure detection: marks node OFFLINE if no heartbeat received for > 6s."""
        while True:
            time.sleep(2)
            with self.lock:
                for nid, n in list(self.nodes.items()):
                    if time.time() - n["last_seen"] > 6 and n["status"] == "ONLINE":
                        n["status"] = "OFFLINE"
                        self.node_mgr.mark_offline(nid)
                        print(f"!! {nid} marked OFFLINE (heartbeat timeout)", flush=True)


if __name__ == "__main__":
    bind_host = os.environ.get("NEXUS_BIND", "127.0.0.1")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    Coordinator(host=bind_host, port=port).serve()
