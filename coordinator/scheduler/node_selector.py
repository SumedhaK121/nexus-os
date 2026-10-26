def pick_node(nodes, online):
    """Least-loaded online node."""
    return min(online, key=lambda k: nodes[k]["load"])
