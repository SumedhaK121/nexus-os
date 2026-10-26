def metrics(procs, first_run, finish):
    rows = []
    for p in procs:
        tat = finish[p["pid"]] - p["arrival"]
        rows.append({"pid": p["pid"], "waiting": tat - p["burst"], "turnaround": tat,
                     "response": first_run[p["pid"]] - p["arrival"]})
    n = len(rows) or 1
    avg = {k: round(sum(r[k] for r in rows) / n, 2) for k in ("waiting", "turnaround", "response")}
    return rows, avg

