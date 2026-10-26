from collections import deque

class RANode:
    def __init__(self, nid): self.id, self.clock, self.state, self.req, self.replies, self.deferred = nid, 0, "RELEASED", None, set(), []

def simulate(ids, requesters):
    """Ricart-Agrawala distributed mutual exclusion with Lamport timestamps.
    All `requesters` ask for the critical section at (almost) the same time."""
    nodes, q, trace, order = {i: RANode(i) for i in ids}, deque(), [], []
    log = lambda n, t: trace.append({"T": nodes[n].clock, "node": n, "event": t})
    for r in requesters:
        n = nodes[r]; n.clock += 1; n.state, n.req = "WANTED", (n.clock, r); log(r, f"WANTS critical section, ts={n.clock}")
        for p in ids:
            if p != r: q.append(("REQUEST", r, p, n.clock)); log(r, f"REQUEST -> {p}")
    while q:
        typ, src, dst, ts = q.popleft(); d = nodes[dst]; d.clock = max(d.clock, ts) + 1
        if typ == "REQUEST":
            if d.state == "HELD" or (d.state == "WANTED" and d.req < (ts, src)):
                d.deferred.append(src); log(dst, f"DEFERS reply to {src} (own request has priority)")
            else: q.append(("REPLY", dst, src, d.clock)); log(dst, f"REPLY -> {src}")
        else:
            d.replies.add(src); log(dst, f"got REPLY from {src}")
            if d.state == "WANTED" and len(d.replies) == len(ids) - 1:
                d.state = "HELD"; order.append(dst); log(dst, "ENTERS critical section ✔")
                d.state = "RELEASED"; log(dst, "EXITS critical section, releases deferred replies")
                for x in d.deferred: q.append(("REPLY", dst, x, d.clock)); log(dst, f"REPLY -> {x} (deferred)")
                d.deferred = []
    return {"order": order, "trace": trace, "messages": sum(1 for t in trace if "REQUEST ->" in t["event"] or "REPLY ->" in t["event"])}
