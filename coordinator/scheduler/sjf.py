from coordinator.scheduler.metrics import metrics as _metrics


def sjf(procs):
    """Shortest Job First (non-preemptive)."""
    pending, t, gantt, first, fin = sorted(procs, key=lambda x: x["arrival"]), 0, [], {}, {}
    while pending:
        ready = [p for p in pending if p["arrival"] <= t]
        if not ready: t = pending[0]["arrival"]; continue
        p = min(ready, key=lambda x: (x["burst"], x["arrival"], x["pid"]))
        pending.remove(p); first[p["pid"]] = t
        gantt.append((p["pid"], t, t + p["burst"])); t += p["burst"]; fin[p["pid"]] = t
    rows, avg = _metrics(procs, first, fin)
    return {"algo": "SJF", "gantt": gantt, "per_process": rows, "avg": avg}
