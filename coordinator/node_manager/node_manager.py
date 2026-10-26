"""NEXUS-OS Node Manager.
Implements cluster membership, heartbeat tracking, and failure detection.
Concept: Node lifecycle and membership management (similar to Kubernetes Node Controller & HDFS NameNode Heartbeat monitor).
"""

import threading
import time

STATE_ONLINE = "ONLINE"
STATE_SUSPECT = "SUSPECT"
STATE_OFFLINE = "OFFLINE"


class NodeInfo:
    """Represents a worker node's registration and hardware capacity."""
    def __init__(self, node_id, addr=("127.0.0.1", 0), cpu_slots=2, mem_mb=256, io_slots=2):
        self.node_id = node_id
        self.addr = addr  # (host, port)
        self.cpu_slots = int(cpu_slots)
        self.mem_mb = int(mem_mb)
        self.io_slots = int(io_slots)
        self.status = STATE_ONLINE
        self.last_seen = time.time()
        self.cpu_usage = 0.0
        self.load = 0
        self.done = 0

    def to_dict(self):
        return {
            "status": self.status,
            "addr": self.addr,
            "cpu_slots": self.cpu_slots,
            "mem_mb": self.mem_mb,
            "io_slots": self.io_slots,
            "last_seen": self.last_seen,
            "cpu": self.cpu_usage,
            "load": self.load,
            "done": self.done,
        }


class NodeManager:
    """Registry for cluster nodes with callback hooks for node lifecycle events."""
    def __init__(self):
        self.nodes = {}  # node_id -> NodeInfo
        self.lock = threading.Lock()
        self._down_callbacks = []
        self._up_callbacks = []

    def subscribe_node_down(self, fn):
        """Register a callback for when a node fails or is marked OFFLINE."""
        with self.lock:
            self._down_callbacks.append(fn)

    def subscribe_node_up(self, fn):
        """Register a callback for when a node registers or recovers to ONLINE."""
        with self.lock:
            self._up_callbacks.append(fn)

    def register_node(self, node_id, addr=("127.0.0.1", 0), cpu_slots=2, mem_mb=256, io_slots=2):
        was_offline = False
        with self.lock:
            if node_id in self.nodes:
                was_offline = (self.nodes[node_id].status == STATE_OFFLINE)
                info = self.nodes[node_id]
                info.addr = addr
                info.cpu_slots = cpu_slots
                info.mem_mb = mem_mb
                info.io_slots = io_slots
                info.status = STATE_ONLINE
                info.last_seen = time.time()
            else:
                info = NodeInfo(node_id, addr, cpu_slots, mem_mb, io_slots)
                self.nodes[node_id] = info
        if was_offline:
            self.on_node_up(node_id)
        return info

    def update_heartbeat(self, node_id, cpu=0.0):
        with self.lock:
            info = self.nodes.get(node_id)
            if info:
                was_down = (info.status == STATE_OFFLINE)
                info.last_seen = time.time()
                info.cpu_usage = float(cpu)
                info.status = STATE_ONLINE
                if was_down:
                    self.on_node_up(node_id)

    def mark_suspect(self, node_id):
        with self.lock:
            info = self.nodes.get(node_id)
            if info and info.status == STATE_ONLINE:
                info.status = STATE_SUSPECT

    def mark_offline(self, node_id):
        notify = False
        with self.lock:
            info = self.nodes.get(node_id)
            if info and info.status != STATE_OFFLINE:
                info.status = STATE_OFFLINE
                notify = True
        if notify:
            self.on_node_down(node_id)

    def on_node_down(self, node_id):
        for cb in list(self._down_callbacks):
            try:
                cb(node_id)
            except Exception as e:
                print(f"[NodeManager] error in on_node_down callback for {node_id}: {e}", flush=True)

    def on_node_up(self, node_id):
        for cb in list(self._up_callbacks):
            try:
                cb(node_id)
            except Exception as e:
                print(f"[NodeManager] error in on_node_up callback for {node_id}: {e}", flush=True)

    def online(self, nodes=None):
        """Returns list of online node IDs. Compatible with dict or self.nodes."""
        if nodes is not None:
            return online(nodes)
        with self.lock:
            return [nid for nid, info in self.nodes.items() if info.status == STATE_ONLINE]

    def get_peers(self):
        """Returns map of online node_id -> {addr: [host, port]}."""
        with self.lock:
            return {
                nid: {"host": info.addr[0], "port": info.addr[1]}
                for nid, info in self.nodes.items()
                if info.status == STATE_ONLINE
            }


# Backward-compatible module-level function
def online(nodes):
    """Returns list of node IDs that have status == 'ONLINE'."""
    if isinstance(nodes, dict):
        res = []
        for k, n in nodes.items():
            st = n.get("status") if isinstance(n, dict) else getattr(n, "status", None)
            if st == STATE_ONLINE:
                res.append(k)
        return res
    return []
