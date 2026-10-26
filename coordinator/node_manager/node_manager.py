def online(nodes):
    return [k for k, n in nodes.items() if n["status"] == "ONLINE"]
