"""NEXUS-OS Unified Scheduler Manager.
Supports offline simulation and live dynamic process dispatch across multiple policies:
FCFS, SJF, SRTF (Preemptive SJF), Priority (non-preemptive and with Aging), and Round Robin.
"""

from coordinator.scheduler.fcfs import fcfs
from coordinator.scheduler.sjf import sjf
from coordinator.scheduler.srtf import srtf
from coordinator.scheduler.priority import priority
from coordinator.scheduler.priority_aging import priority_aging
from coordinator.scheduler.round_robin import round_robin


def run(algo, procs, quantum=2):
    algo_lower = str(algo).lower()
    if algo_lower in ("rr", "round_robin"):
        return round_robin(procs, quantum)
    if algo_lower in ("srtf", "sjf_preemptive"):
        return srtf(procs)
    if algo_lower in ("priority_aging", "prio_aging"):
        return priority_aging(procs)
    return {
        "sjf": sjf,
        "priority": priority,
        "srtf": srtf,
    }.get(algo_lower, fcfs)(procs)


def compare(procs, quantum=2, extended=False):
    # Retain the exact first 4 for full backward compatibility with test_core assertions
    base = [
        fcfs(procs),
        sjf(procs),
        priority(procs),
        round_robin(procs, quantum),
    ]
    if extended:
        base.extend([srtf(procs), priority_aging(procs)])
    return base


def pick_next(ready_queue, policy="fcfs", now=0.0):
    """Picks the next task to dispatch from ready_queue according to policy.
    Used by the live cluster dispatch loop.
    """
    if not ready_queue:
        return None

    policy = str(policy).lower()

    if policy in ("sjf", "shortest_job_first"):
        return min(ready_queue, key=lambda p: (p.get("burst", 1), p.get("arrival", 0), p["pid"]))

    if policy in ("srtf", "sjf_preemptive"):
        return min(ready_queue, key=lambda p: (p.get("remaining_burst", p.get("burst", 1)), p.get("arrival", 0), p["pid"]))

    if policy in ("priority", "prio"):
        # Lower numerical value = higher priority
        return min(ready_queue, key=lambda p: (p.get("priority", 1), p.get("arrival", 0), p["pid"]))

    if policy in ("priority_aging", "prio_aging"):
        # Effective priority decrements (improves) with wait time
        def effective_prio(p):
            base = p.get("priority", 1)
            wait = max(0.0, now - p.get("ready_time", now))
            boost = int(wait // 2)
            return base - boost
        return min(ready_queue, key=lambda p: (effective_prio(p), p.get("arrival", 0), p["pid"]))

    if policy in ("rr", "round_robin"):
        # Head of the FIFO queue
        return ready_queue[0]

    # Default FCFS
    return min(ready_queue, key=lambda p: (p.get("arrival", 0), p.get("submit_time", 0), p["pid"]))
