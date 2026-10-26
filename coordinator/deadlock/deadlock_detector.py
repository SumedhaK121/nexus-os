"""NEXUS-OS Deadlock Detection.
Implements cycle search on directed wait-for graphs (WFG).
Concept: Deadlock detection in distributed and operating systems (Silberschatz / Coffman conditions).
"""


def detect(wait_for):
    """Finds the first cycle in the wait_for graph.
    Returns list of vertices forming the cycle (e.g. ['P1', 'P2', 'P1']) or empty list.
    """
    color = {}  # 0: unvisited, 1: visiting, 2: visited
    stack = []

    def dfs(u):
        color[u] = 1
        stack.append(u)
        for v in wait_for.get(u, []):
            if color.get(v) == 1:
                idx = stack.index(v)
                return stack[idx:] + [v]
            if v not in color:
                res = dfs(v)
                if res:
                    return res
        color[u] = 2
        stack.pop()
        return None

    for u in list(wait_for):
        if u not in color:
            cycle = dfs(u)
            if cycle:
                return cycle
    return []


def find_all_cycles(wait_for):
    """Finds all distinct elementary cycles in the wait_for graph."""
    cycles = []
    visited = set()

    def dfs(start, current, path):
        for neighbor in wait_for.get(current, []):
            if neighbor == start and len(path) > 1:
                # Found cycle back to start
                normalized = path + [start]
                # Avoid duplicate representations of rotated cycle
                cycle_nodes = tuple(path)
                rotations = {cycle_nodes[i:] + cycle_nodes[:i] for i in range(len(cycle_nodes))}
                if not any(tuple(c[:-1]) in rotations for c in cycles):
                    cycles.append(normalized)
            elif neighbor not in path and neighbor not in visited:
                dfs(start, neighbor, path + [neighbor])

    nodes = list(wait_for.keys())
    for node in nodes:
        dfs(node, node, [node])
        visited.add(node)

    return cycles


SCENARIOS = {
    "circular": {"P1": ["P2"], "P2": ["P3"], "P3": ["P1"]},
    "chain": {"P1": ["P2"], "P2": ["P3"], "P3": []},
    "dual_cycle": {"P1": ["P2"], "P2": ["P1"], "P3": ["P4"], "P4": ["P3"]},
}
