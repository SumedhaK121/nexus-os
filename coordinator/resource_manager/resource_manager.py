"""NEXUS-OS Resource Manager.
Defines resource vectors, aggregates cluster capacity across online nodes,
tracks real resource utilization, and manages wait-for dependencies for deadlocks.
Concept: Admission control and resource reservation (similar to Kubernetes Resource Quotas / Slurm).
"""

import collections
import threading
import time

RESOURCE_NAMES = ["CPU", "Memory", "I/O"]


class ResourceManager:
    """Manages cluster-wide resources [cpu_slots, mem_units, io_slots]."""
    def __init__(self):
        self.lock = threading.Lock()
        self.total = [0, 0, 0]          # [cpu, mem, io]
        self.allocated = {}             # pid -> [cpu, mem, io]
        self.wait_for_graph = {}        # waiter_pid -> set(holder_pids)
        # Ring buffer for utilization history: deque of (timestamp, [cpu_pct, mem_pct, io_pct])
        self.history = collections.deque(maxlen=300)

    def update_cluster_capacity(self, nodes_dict):
        """Aggregate capacities from all ONLINE nodes."""
        cpu = 0
        mem = 0
        io = 0
        with self.lock:
            for info in nodes_dict.values():
                status = info.get("status") if isinstance(info, dict) else getattr(info, "status", None)
                if status == "ONLINE":
                    c = info.get("cpu_slots", 2) if isinstance(info, dict) else getattr(info, "cpu_slots", 2)
                    m = info.get("mem_mb", 256) if isinstance(info, dict) else getattr(info, "mem_mb", 256)
                    i = info.get("io_slots", 2) if isinstance(info, dict) else getattr(info, "io_slots", 2)
                    cpu += int(c)
                    mem += int(m) // 128  # 1 unit = 128 MB
                    io += int(i)
            self.total = [max(1, cpu), max(1, mem), max(1, io)]

    def get_available(self):
        with self.lock:
            curr_alloc = [0, 0, 0]
            for vec in self.allocated.values():
                for idx in range(3):
                    curr_alloc[idx] += vec[idx]
            return [max(0, self.total[i] - curr_alloc[i]) for i in range(3)]

    def allocate(self, pid, req_vec):
        with self.lock:
            self.allocated[pid] = list(req_vec)

    def release(self, pid):
        with self.lock:
            self.allocated.pop(pid, None)
            self.wait_for_graph.pop(pid, None)
            for s in self.wait_for_graph.values():
                s.discard(pid)

    def register_wait(self, waiter, holder):
        with self.lock:
            if waiter not in self.wait_for_graph:
                self.wait_for_graph[waiter] = set()
            self.wait_for_graph[waiter].add(holder)

    def clear_wait(self, waiter, holder=None):
        with self.lock:
            if waiter in self.wait_for_graph:
                if holder:
                    self.wait_for_graph[waiter].discard(holder)
                else:
                    self.wait_for_graph.pop(waiter, None)

    def get_wait_for_graph(self):
        with self.lock:
            return {k: list(v) for k, v in self.wait_for_graph.items() if v}

    def record_snapshot(self):
        with self.lock:
            tot = self.total
            alloc = [sum(vec[i] for vec in self.allocated.values()) for i in range(3)]
            pcts = [(alloc[i] / tot[i] * 100) if tot[i] > 0 else 0 for i in range(3)]
            self.history.append((time.time(), pcts))

    def get_utilization(self, banker=None):
        if banker:
            return utilization(banker)
        with self.lock:
            tot = self.total
            alloc = [sum(vec[i] for vec in self.allocated.values()) for i in range(3)]
            return [
                {
                    "resource": RESOURCE_NAMES[i],
                    "allocated": alloc[i],
                    "total": tot[i],
                    "rate": round(alloc[i] / max(1, tot[i]) * 100, 1),
                }
                for i in range(3)
            ]


# Global instance
_default_res_mgr = ResourceManager()


def utilization(b=None):
    """Backward-compatible utilization query for Banker's or cluster resources."""
    if b:
        al = [sum(a[i] for a in b.alloc.values()) for i in range(len(b.available))]
        return [
            {
                "resource": f"R{i+1}",
                "allocated": al[i],
                "total": al[i] + b.available[i],
                "rate": round(100 * al[i] / max(1, al[i] + b.available[i]), 1),
            }
            for i in range(len(al))
        ]
    return _default_res_mgr.get_utilization()
