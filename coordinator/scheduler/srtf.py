"""NEXUS-OS Scheduler: Shortest Remaining Time First (SRTF).
Preemptive version of Shortest Job First (SJF).
Concept: Preemptive CPU scheduling minimizing average turnaround time (Linux SCHED_DEADLINE / real-time concepts).
"""

from coordinator.scheduler.metrics import metrics as _metrics


def srtf(procs):
    """Shortest Remaining Time First (preemptive SJF)."""
    if not procs:
        return {"algo": "SRTF", "gantt": [], "per_process": [], "avg": {"waiting": 0, "turnaround": 0, "response": 0}}

    incoming = sorted(procs, key=lambda x: (x["arrival"], x["pid"]))
    rem = {p["pid"]: p["burst"] for p in procs}
    by_pid = {p["pid"]: p for p in procs}
    t = 0
    gantt = []
    first = {}
    fin = {}
    i = 0
    ready = []
    current_pid = None
    slice_start = 0

    total_procs = len(incoming)
    completed = 0

    while completed < total_procs:
        # Check arrivals at current time t
        while i < len(incoming) and incoming[i]["arrival"] <= t:
            ready.append(incoming[i]["pid"])
            i += 1

        if not ready:
            if i < len(incoming):
                t = incoming[i]["arrival"]
                continue
            break

        # Pick job with shortest remaining time
        best_pid = min(ready, key=lambda pid: (rem[pid], by_pid[pid]["arrival"], pid))

        # Check for context switch
        if best_pid != current_pid:
            if current_pid is not None and t > slice_start:
                gantt.append((current_pid, slice_start, t))
            current_pid = best_pid
            slice_start = t
            first.setdefault(current_pid, t)

        # Execute 1 unit of time
        rem[current_pid] -= 1
        t += 1

        # Check if completed
        if rem[current_pid] == 0:
            gantt.append((current_pid, slice_start, t))
            fin[current_pid] = t
            ready.remove(current_pid)
            completed += 1
            current_pid = None
            slice_start = t

    # Merge contiguous Gantt slices for same process
    merged_gantt = []
    for item in gantt:
        if merged_gantt and merged_gantt[-1][0] == item[0] and merged_gantt[-1][2] == item[1]:
            merged_gantt[-1] = (item[0], merged_gantt[-1][1], item[2])
        else:
            merged_gantt.append(item)

    rows, avg = _metrics(procs, first, fin)
    return {"algo": "SRTF", "gantt": merged_gantt, "per_process": rows, "avg": avg}
