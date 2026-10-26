"""NEXUS-OS Scheduler: Preemptive Priority with Aging.
Prevents indefinite starvation of low-priority processes by increasing priority over wait duration.
Concept: Priority aging in operating system schedulers (Solaris, BSD, Linux nice/decay mechanisms).
"""

from coordinator.scheduler.metrics import metrics as _metrics


def priority_aging(procs, age_interval=2):
    """Preemptive priority scheduling where effective priority increases (value decrements)
    by 1 for every age_interval units a process spends in the ready queue without CPU.
    Lower priority value = higher execution priority.
    """
    if not procs:
        return {"algo": "Priority+Aging", "gantt": [], "per_process": [], "avg": {"waiting": 0, "turnaround": 0, "response": 0}}

    incoming = sorted(procs, key=lambda x: (x["arrival"], x["pid"]))
    rem = {p["pid"]: p["burst"] for p in procs}
    wait_time = {p["pid"]: 0 for p in procs}
    by_pid = {p["pid"]: p for p in procs}
    t = 0
    gantt = []
    first = {}
    fin = {}
    ready = []
    i = 0
    current_pid = None
    slice_start = 0
    total_procs = len(incoming)
    completed = 0

    while completed < total_procs:
        while i < len(incoming) and incoming[i]["arrival"] <= t:
            ready.append(incoming[i]["pid"])
            i += 1

        if not ready:
            if i < len(incoming):
                t = incoming[i]["arrival"]
                continue
            break

        # Calculate effective priority: base_priority - (wait_time // age_interval)
        def effective_prio(pid):
            base = by_pid[pid]["priority"]
            boost = wait_time[pid] // age_interval
            return base - boost

        best_pid = min(ready, key=lambda pid: (effective_prio(pid), by_pid[pid]["arrival"], pid))

        if best_pid != current_pid:
            if current_pid is not None and t > slice_start:
                gantt.append((current_pid, slice_start, t))
            current_pid = best_pid
            slice_start = t
            first.setdefault(current_pid, t)

        # Execute 1 unit
        rem[current_pid] -= 1
        t += 1

        # Age waiting processes
        for pid in ready:
            if pid != current_pid:
                wait_time[pid] += 1

        if rem[current_pid] == 0:
            gantt.append((current_pid, slice_start, t))
            fin[current_pid] = t
            ready.remove(current_pid)
            completed += 1
            current_pid = None
            slice_start = t

    merged_gantt = []
    for item in gantt:
        if merged_gantt and merged_gantt[-1][0] == item[0] and merged_gantt[-1][2] == item[1]:
            merged_gantt[-1] = (item[0], merged_gantt[-1][1], item[2])
        else:
            merged_gantt.append(item)

    rows, avg = _metrics(procs, first, fin)
    return {"algo": "Priority+Aging", "gantt": merged_gantt, "per_process": rows, "avg": avg}
