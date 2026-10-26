"""Module 2: Banker's Algorithm (pure logic)."""
class Banker:
    def __init__(self, available, maximum, allocation):
        self.available = list(available)
        self.max = {p: list(v) for p, v in maximum.items()}
        self.alloc = {p: list(v) for p, v in allocation.items()}
    def need(self, p):
        return [m - a for m, a in zip(self.max[p], self.alloc[p])]
    def is_safe(self, available=None, alloc=None):
        work = list(available if available is not None else self.available)
        alloc = alloc if alloc is not None else self.alloc
        done, order = set(), []
        progress = True
        while progress:
            progress = False
            for p in alloc:
                need = [m - a for m, a in zip(self.max[p], alloc[p])]
                if p not in done and all(n <= w for n, w in zip(need, work)):
                    work = [w + a for w, a in zip(work, alloc[p])]
                    done.add(p); order.append(p); progress = True
        return len(done) == len(alloc), order
    def request(self, p, req):
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
        self.available = [a + x for a, x in zip(self.available, self.alloc[p])]
        self.alloc[p] = [0] * len(self.available)

if __name__ == "__main__":  # classic textbook example
    b = Banker([3, 3, 2],
               {"P0": [7,5,3], "P1": [3,2,2], "P2": [9,0,2], "P3": [2,2,2], "P4": [4,3,3]},
               {"P0": [0,1,0], "P1": [2,0,0], "P2": [3,0,2], "P3": [2,1,1], "P4": [0,0,2]})
    print(b.is_safe()); print(b.request("P1", [1,0,2])); print(b.request("P0", [0,2,0]))
