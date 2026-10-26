from coordinator.scheduler.metrics import metrics as _metrics


def fcfs(procs):
    t, gantt, first, fin = 0, [], {}, {}
    for p in sorted(procs, key=lambda x: (x["arrival"], x["pid"])):
        t = max(t, p["arrival"]); first[p["pid"]] = t
        gantt.append((p["pid"], t, t + p["burst"])); t += p["burst"]; fin[p["pid"]] = t
    rows, avg = _metrics(procs, first, fin)
    return {"algo": "FCFS", "gantt": gantt, "per_process": rows, "avg": avg}

