"""NEXUS-OS Process Manager.
Implements Process Control Block (PCB) tracking, life-cycle state transitions,
and process accounting.
Concept: Operating System Process States and Process Control Blocks (POSIX / Linux kernel task_struct).
"""

import threading
import time

STATE_NEW = "NEW"
STATE_READY = "READY"
STATE_RUNNING = "RUNNING"
STATE_WAITING = "WAITING"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"
STATE_KILLED = "KILLED"

VALID_TRANSITIONS = {
    STATE_NEW: {STATE_READY, STATE_KILLED},
    STATE_READY: {STATE_RUNNING, STATE_KILLED},
    STATE_RUNNING: {STATE_WAITING, STATE_READY, STATE_COMPLETED, STATE_FAILED, STATE_KILLED},
    STATE_WAITING: {STATE_READY, STATE_KILLED},
    STATE_COMPLETED: set(),
    STATE_FAILED: set(),
    STATE_KILLED: set(),
}


class ProcessControlBlock:
    """Represents a process control block (PCB) in the distributed cluster."""
    def __init__(self, pid, name=None, node=None, resources=None, job_type="sim", args=None, burst=1, priority=1):
        self.pid = str(pid)
        self.name = name or f"proc-{pid}"
        self.state = STATE_NEW
        self.node = node
        self.submit_time = time.time()
        self.start_time = None
        self.end_time = None
        self.resources = resources or {"cpu_slots": 1, "mem_units": 1, "io_slots": 0}
        self.job_type = job_type
        self.args = args or []
        self.burst = burst
        self.priority = priority

    def can_transition_to(self, new_state):
        # Allow case-insensitive or legacy mapping ("Running" -> RUNNING)
        target = new_state.upper()
        current = self.state.upper()
        if target == current:
            return True
        return target in VALID_TRANSITIONS.get(current, set())

    def set_state(self, new_state):
        target = new_state.upper()
        current = self.state.upper()
        if target == current:
            return True
        if target not in VALID_TRANSITIONS.get(current, set()):
            raise ValueError(f"Invalid process state transition: {current} -> {target} for PID {self.pid}")
        if target == STATE_RUNNING and self.start_time is None:
            self.start_time = time.time()
        if target in (STATE_COMPLETED, STATE_FAILED, STATE_KILLED):
            self.end_time = time.time()
        self.state = target
        return True

    def to_dict(self):
        return {
            "pid": self.pid,
            "name": self.name,
            "state": self.state,
            "node": self.node,
            "submit_time": self.submit_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "resources": dict(self.resources),
            "job_type": self.job_type,
            "args": list(self.args),
            "burst": self.burst,
            "priority": self.priority,
        }


class ProcessManager:
    """Manages cluster process table and transitions."""
    def __init__(self):
        self.table = {}  # pid -> ProcessControlBlock
        self.lock = threading.Lock()

    def add(self, pid, name=None, node=None, resources=None, job_type="sim", args=None, burst=1, priority=1):
        with self.lock:
            pcb = ProcessControlBlock(pid, name, node, resources, job_type, args, burst, priority)
            self.table[pid] = pcb
            return pcb

    def get(self, pid):
        with self.lock:
            return self.table.get(pid)

    def transition(self, pid, new_state):
        with self.lock:
            pcb = self.table.get(pid)
            if not pcb:
                raise KeyError(f"Unknown PID {pid}")
            return pcb.set_state(new_state)

    def list_all(self):
        with self.lock:
            return {pid: pcb.to_dict() for pid, pcb in self.table.items()}


# Backward-compatible summary function
def summary(tasks):
    """Summarizes task states. Backward compatible with old dict-based c.tasks."""
    out = {"Running": 0, "Completed": 0, "Waiting": 0, "Ready": 0, "Failed": 0, "Killed": 0}
    if not tasks:
        return out
    for t in tasks.values():
        raw_state = t["state"] if isinstance(t, dict) else getattr(t, "state", "Unknown")
        state_title = raw_state.title()
        out[state_title] = out.get(state_title, 0) + 1
        if raw_state != state_title:
            out[raw_state] = out.get(raw_state, 0) + 1
    return out
