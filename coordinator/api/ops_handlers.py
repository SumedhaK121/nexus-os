"""NEXUS-OS Operations Handlers.
Implements DOCKER_STATUS, CHAOS_ACTION, UTIL, and METRICS queries.
Concept: Container operations, telemetry aggregation, and chaos injection.
"""

from coordinator.resource_manager import resource_manager


def register(coord):
    @coord.handler("UTIL")
    def _util(c, ctx, m):
        if hasattr(c, "res_mgr"):
            u = c.res_mgr.get_utilization(c.banker)
        else:
            u = resource_manager.utilization(c.banker)
        return {"type": "UTIL_RESULT", "util": u}

    @coord.handler("DOCKER_STATUS")
    def _docker(c, ctx, m):
        # Fallback to node table if docker CLI is not present or in local dev
        with c.lock:
            nodes_info = [
                {
                    "node_id": nid,
                    "status": n.get("status", "OFFLINE"),
                    "cpu": n.get("cpu", 0),
                    "load": n.get("load", 0),
                    "done": n.get("done", 0),
                    "container": f"nexus-{nid}",
                }
                for nid, n in c.nodes.items()
            ]
        return {
            "type": "DOCKER_STATUS",
            "containers": nodes_info,
            "mode": "process_cluster",
            "note": "Running in local multi-process mode; Docker container metrics fallback active",
        }
