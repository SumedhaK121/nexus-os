"""NEXUS-OS Resource & Deadlock API Handlers.
Implements BANKER_INIT, BANKER_REQUEST, BANKER_STATE, DEADLOCK_DEMO, DEADLOCK_DETECT, DEADLOCK_RECOVER.
Concept: Deadlock avoidance (Dijkstra's Banker's Algorithm) and Deadlock detection via Wait-For Graphs (DFS cycle detection).
"""

from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock.deadlock_detector import detect, SCENARIOS


def register(coord):
    @coord.handler("BANKER_INIT")
    def _bi(c, ctx, m):
        available = m["available"]
        maximum = m["max"]
        alloc = m["alloc"]
        c.banker = Banker(available, maximum, alloc)
        safe, seq = c.banker.is_safe()
        c.log("banker", f"Banker initialized: safe={safe}, seq={seq}")
        return {"type": "OK", "safe": [safe, seq]}

    @coord.handler("BANKER_REQUEST")
    def _br(c, ctx, m):
        if c.banker is None:
            return {"type": "ERROR", "error": "Banker algorithm not initialized; call BANKER_INIT first"}
        pid = m["pid"]
        req = m["request"]
        r = c.banker.request(pid, req)
        c.log("banker", f"{pid} request {req} -> {r}")
        return {"type": "BANKER_RESULT", **r}

    @coord.handler("BANKER_STATE")
    def _bs(c, ctx, m):
        if c.banker is None:
            return {"type": "ERROR", "error": "Banker algorithm not initialized"}
        safe, seq = c.banker.is_safe()
        return {
            "type": "BANKER_STATE",
            "available": c.banker.available,
            "max": c.banker.max,
            "alloc": c.banker.alloc,
            "safe": safe,
            "safe_sequence": seq,
        }

    @coord.handler("DEADLOCK_DEMO")
    def _dd(c, ctx, m):
        scenario = m.get("scenario", "circular")
        wf = SCENARIOS.get(scenario, SCENARIOS["circular"])
        cyc = detect(wf)
        c.log("deadlock", f"cycle {' -> '.join(cyc)} DETECTED" if cyc else "no cycle, system deadlock-free")
        return {"type": "DEADLOCK_RESULT", "wait_for": wf, "cycle": cyc, "deadlock": bool(cyc)}

    @coord.handler("DEADLOCK_DETECT")
    def _detect_live(c, ctx, m):
        wf = {}
        if hasattr(c, "res_mgr"):
            wf = c.res_mgr.get_wait_for_graph()
        cyc = detect(wf)
        c.log("deadlock", f"Live deadlock check: cycle={cyc}")
        return {"type": "DEADLOCK_RESULT", "wait_for": wf, "cycle": cyc, "deadlock": bool(cyc)}
