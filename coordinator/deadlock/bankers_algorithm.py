"""Module 2: Banker's Algorithm (Dijkstra's Deadlock Avoidance Algorithm).
Manages resource requests by verifying that a safe sequence exists where all processes
can finish with their declared maximum demands.
Concept: Admission control and deadlock avoidance (used in resource reservation systems).
"""


class Banker:
    def __init__(self, available, maximum, allocation):
        self.available = list(available)
        self.max = {p: list(v) for p, v in maximum.items()}
        self.alloc = {p: list(v) for p, v in allocation.items()}

    def add_process(self, p, maximum, allocation=None):
        """Register a new process declaring its maximum resource demand vector."""
        self.max[p] = list(maximum)
        if allocation is not None:
            self.alloc[p] = list(allocation)
        else:
            self.alloc[p] = [0] * len(self.available)

    def remove_process(self, p):
        """Releases held resources and removes process from Banker tracking."""
        if p in self.alloc:
            self.release(p)
            self.alloc.pop(p, None)
            self.max.pop(p, None)

    def update_capacity(self, total_capacity):
        """Update available resources based on total cluster capacity."""
        cur_alloc = [0] * len(total_capacity)
        for vec in self.alloc.values():
            for i in range(len(total_capacity)):
                cur_alloc[i] += vec[i]
        self.available = [max(0, total_capacity[i] - cur_alloc[i]) for i in range(len(total_capacity))]

    def need(self, p):
        if p not in self.max:
            return [0] * len(self.available)
        return [m - a for m, a in zip(self.max[p], self.alloc.get(p, [0] * len(self.available)))]

    def is_safe(self, available=None, alloc=None):
        work = list(available if available is not None else self.available)
        alloc = alloc if alloc is not None else self.alloc
        done, order = set(), []
        progress = True
        while progress:
            progress = False
            for p in alloc:
                if p not in done:
                    need = [m - a for m, a in zip(self.max[p], alloc[p])]
                    if all(n <= w for n, w in zip(need, work)):
                        work = [w + a for w, a in zip(work, alloc[p])]
                        done.add(p)
                        order.append(p)
                        progress = True
        return len(done) == len(alloc), order

    def request(self, p, req):
        if p not in self.max:
            return {"granted": False, "reason": f"process {p} not registered with Banker"}
        if any(r > n for r, n in zip(req, self.need(p))):
            return {"granted": False, "reason": "exceeds declared maximum"}
        if any(r > a for r, a in zip(req, self.available)):
            return {"granted": False, "reason": "not enough available, must wait"}
        new_avail = [a - r for a, r in zip(self.available, req)]
        new_alloc = {k: list(v) for k, v in self.alloc.items()}
        new_alloc[p] = [a + r for a, r in zip(new_alloc[p], req)]
        safe, order = self.is_safe(new_avail, new_alloc)
        if not safe:
            return {"granted": False, "reason": "would lead to UNSAFE state"}
        self.available, self.alloc = new_avail, new_alloc
        return {"granted": True, "safe_sequence": order}

    def release(self, p):
        if p in self.alloc:
            self.available = [a + x for a, x in zip(self.available, self.alloc[p])]
            self.alloc[p] = [0] * len(self.available)


if __name__ == "__main__":  # classic textbook example
    b = Banker([3, 3, 2],
               {"P0": [7, 5, 3], "P1": [3, 2, 2], "P2": [9, 0, 2], "P3": [2, 2, 2], "P4": [4, 3, 3]},
               {"P0": [0, 1, 0], "P1": [2, 0, 0], "P2": [3, 0, 2], "P3": [2, 1, 1], "P4": [0, 0, 2]})
    print(b.is_safe())
    print(b.request("P1", [1, 0, 2]))
    print(b.request("P0", [0, 2, 0]))
