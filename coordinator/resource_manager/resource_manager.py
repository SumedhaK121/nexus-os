"""NEXUS-OS Resource Manager.
Aggregates dynamic cluster capacities, drives real Banker's admission control,
tracks live resource utilization, maintains wait-for dependency graphs,
and resolves deadlocks via victim selection policies.
Concept: Admission control (Banker's Algorithm), Wait-For Graph (WFG) deadlock detection, and recovery.
"""

import collections
import os
import threading
import time
from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock import deadlock_detector

RESOURCE_NAMES = ["CPU", "Memory", "I/O"]


class ResourceManager:
    """Manages cluster-wide resources [cpu_slots, mem_units, io_slots]."""
    def __init__(self):
        self.lock = threading.Lock()
        self.total = [6, 6, 6]          # [cpu, mem, io] default across 3 nodes
        self.allocated = {}             # pid -> [cpu, mem, io]
        self.wait_for_graph = {}        # waiter_pid -> set(holder_pids)
        self.history = collections.deque(maxlen=300)

        # Banker admission control
        env_banker = os.environ.get("NEXUS_BANKER", "on").lower()
        self.banker_enabled = (env_banker not in ("off", "0", "false"))
        self.cluster_banker = Banker(self.total, {}, {})

        # Deadlock accounting
        self.deadlocks_detected = 0
        self.deadlocks_resolved = 0
        self.recovery_log = []

    def toggle_banker(self, enabled=None):
        with self.lock:
            if enabled is not None:
                self.banker_enabled = bool(enabled)
            else:
                self.banker_enabled = not self.banker_enabled
            return self.banker_enabled

    def update_cluster_capacity(self, nodes_dict):
        """Aggregate capacities from all ONLINE nodes and update Banker."""
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
            self.cluster_banker.update_capacity(self.total)

    def get_available(self):
        with self.lock:
            curr_alloc = [0, 0, 0]
            for vec in self.allocated.values():
                for idx in range(3):
                    curr_alloc[idx] += vec[idx]
            return [max(0, self.total[i] - curr_alloc[i]) for i in range(3)]

    def allocate(self, pid, req_vec, max_demand=None):
        with self.lock:
            if pid not in self.allocated:
                self.allocated[pid] = [0, 0, 0]
            for i in range(3):
                self.allocated[pid][i] += req_vec[i]
            if max_demand:
                self.cluster_banker.add_process(pid, max_demand, self.allocated[pid])

    def release(self, pid):
        with self.lock:
            self.allocated.pop(pid, None)
            self.cluster_banker.remove_process(pid)
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
            return {k: sorted(list(v)) for k, v in self.wait_for_graph.items() if v}

    def detect_cycles(self):
        """Returns all cycles currently in the wait-for graph."""
        wfg = self.get_wait_for_graph()
        cycles = deadlock_detector.find_all_cycles(wfg)
        if cycles:
            self.deadlocks_detected += len(cycles)
        return cycles

    def select_victim(self, cycle, proc_table, policy="youngest"):
        """Picks a victim process to terminate according to policy:
        - 'youngest': newest process (highest submit_time)
        - 'least_work': lowest completed burst or work
        - 'lowest_priority': lowest priority (highest priority integer)
        """
        # Exclude cycle loop tail if identical to head
        candidates = list(dict.fromkeys(cycle[:-1])) if cycle else []
        if not candidates:
            return None

        policy = str(policy).lower()

        if policy == "lowest_priority":
            # Higher number = lower priority
            return max(candidates, key=lambda pid: proc_table.get(pid, {}).get("priority", 1))

        if policy == "least_work":
            # Lowest completed wall time or burst
            return min(candidates, key=lambda pid: proc_table.get(pid, {}).get("wall_time", proc_table.get(pid, {}).get("burst", 1)))

        # Default 'youngest': latest submit_time
        return max(candidates, key=lambda pid: proc_table.get(pid, {}).get("submit_time", 0))

    def record_snapshot(self):
        with self.lock:
            tot = self.total
            alloc = [sum(vec[i] for vec in self.allocated.values()) for i in range(3)]
            pcts = [(alloc[i] / max(1, tot[i]) * 100) for i in range(3)]
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


# Backward-compatible global instance
_default_res_mgr = ResourceManager()


def utilization(b=None):
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
