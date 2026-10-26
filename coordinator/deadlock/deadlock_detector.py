"""Deadlock detection: cycle search in the wait-for graph ({proc: [procs it waits for]})."""
def detect(wait_for):
    color, stack = {}, []
    def dfs(u):
        color[u] = 1; stack.append(u)
        for v in wait_for.get(u, []):
            if color.get(v) == 1: return stack[stack.index(v):] + [v]
            if v not in color and (r := dfs(v)): return r
        color[u] = 2; stack.pop(); return None
    for u in list(wait_for):
        if u not in color and (r := dfs(u)): return r
    return []

SCENARIOS = {"circular": {"P1": ["P2"], "P2": ["P3"], "P3": ["P1"]}, "chain": {"P1": ["P2"], "P2": ["P3"], "P3": []}}
