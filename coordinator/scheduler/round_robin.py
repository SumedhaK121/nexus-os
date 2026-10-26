from collections import deque
from coordinator.scheduler.metrics import metrics as _metrics


def round_robin(procs, quantum=2):
    incoming = sorted(procs, key=lambda x: (x["arrival"], x["pid"]))
    rem = {p["pid"]: p["burst"] for p in procs}
    q, t, gantt, first, fin, i = deque(), 0, [], {}, {}, 0
    while i < len(incoming) or q:
        if not q:
            t = max(t, incoming[i]["arrival"])
        while i < len(incoming) and incoming[i]["arrival"] <= t:
            q.append(incoming[i]["pid"]); i += 1
        pid = q.popleft(); first.setdefault(pid, t)
        run = min(quantum, rem[pid]); gantt.append((pid, t, t + run)); t += run; rem[pid] -= run
        while i < len(incoming) and incoming[i]["arrival"] <= t:
            q.append(incoming[i]["pid"]); i += 1
        if rem[pid] > 0: q.append(pid)
        else: fin[pid] = t
    rows, avg = _metrics(procs, first, fin)
    return {"algo": f"RR(q={quantum})", "gantt": gantt, "per_process": rows, "avg": avg}

