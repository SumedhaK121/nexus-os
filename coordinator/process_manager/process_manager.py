def summary(tasks):
    out = {"Running": 0, "Completed": 0}
    for t in tasks.values(): out[t["state"]] = out.get(t["state"], 0) + 1
    return out
