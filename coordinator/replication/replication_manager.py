import os

class ReplicationManager:
    """Keeps `k` copies of every file on different nodes (storage/replicas/<node>/<file>)."""
    def __init__(self, root, k=2): self.root, self.k, self.placement = root, k, {}
    def replicate(self, name, data, version, nodes):
        nodes = nodes or ["node-1", "node-2", "node-3"]
        old = self.placement.get(name)
        load = {n: sum(n in v for v in self.placement.values()) for n in nodes}
        chosen = old if old and set(old) <= set(nodes) else sorted(nodes, key=lambda n: (load[n], n))[:self.k]
        for n in chosen:
            d = os.path.join(self.root, "storage", "replicas", n); os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, name), "w", encoding="utf-8") as f: f.write(data)
        self.placement[name] = chosen; return chosen
    def remove(self, name):
        for n in self.placement.pop(name, []):
            try: os.remove(os.path.join(self.root, "storage", "replicas", n, name))
            except OSError: pass
