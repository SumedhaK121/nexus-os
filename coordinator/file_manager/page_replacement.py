def simulate(refs, frames):
    """FIFO vs LRU vs Optimal (Belady) on a page reference string."""
    out = []
    for name in ("FIFO", "LRU", "Optimal"):
        mem, hits, trace = [], 0, []
        for i, p in enumerate(refs):
            hit = p in mem
            if hit:
                hits += 1
                if name == "LRU": mem.remove(p); mem.append(p)
            else:
                if len(mem) >= frames:
                    if name == "Optimal":
                        rest = refs[i + 1:]; far = [rest.index(x) if x in rest else 10**9 for x in mem]; mem.pop(far.index(max(far)))
                    else: mem.pop(0)
                mem.append(p)
            trace.append({"page": p, "hit": hit, "mem": list(mem)})
        out.append({"algo": name, "hits": hits, "faults": len(refs) - hits, "ratio": round(100 * hits / max(1, len(refs))), "trace": trace})
    return out
