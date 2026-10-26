def utilization(b):
    """Allocated vs total units of each resource type (from the Banker's state)."""
    if not b: return None
    al = [sum(a[i] for a in b.alloc.values()) for i in range(len(b.available))]
    return [{"resource": f"R{i+1}", "allocated": al[i], "total": al[i] + b.available[i]} for i in range(len(al))]
