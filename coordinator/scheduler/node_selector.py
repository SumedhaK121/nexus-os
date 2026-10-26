"""NEXUS-OS Node Selector.
Selects optimal worker node for task placement based on load, capacity, and CPU metrics.
Concept: Distributed load balancing and node scheduling (Kubernetes kube-scheduler score plugins).
"""


def pick_node(nodes, online, policy="least_load"):
    """Selects the best online node according to scheduling policy.
    Defaults to least-loaded node for backward compatibility.
    """
    if not online:
        return None

    valid_online = [k for k in online if k in nodes and nodes[k].get("status") == "ONLINE"]
    if not valid_online:
        valid_online = [k for k in online if k in nodes]
    if not valid_online:
        return online[0]

    policy = str(policy).lower()

    if policy == "cpu_utilization":
        # Node with lowest reported CPU usage %
        return min(valid_online, key=lambda k: (nodes[k].get("cpu", 0.0), nodes[k].get("load", 0)))

    if policy == "capacity_aware":
        # Node with highest remaining capacity
        def free_capacity(k):
            slots = nodes[k].get("cpu_slots", 2)
            load = nodes[k].get("load", 0)
            return slots - load
        return max(valid_online, key=lambda k: (free_capacity(k), -nodes[k].get("load", 0)))

    # Default least-load policy (tasks count or total burst)
    return min(valid_online, key=lambda k: nodes[k].get("load", 0))
