"""NEXUS-OS Resource & Deadlock API Handlers.
Implements BANKER_INIT, BANKER_REQUEST, BANKER_STATE, BANKER_TOGGLE,
DEADLOCK_DEMO, DEADLOCK_DETECT, DEADLOCK_RECOVER.
Concept: Deadlock avoidance (Banker's Algorithm) and wait-for graph cycle detection/recovery.
"""

from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock import deadlock_detector


def register(coord):
    @coord.handler("BANKER_INIT")
    def _bi(c, ctx, m):
        available = m["available"]
        maximum = m["max"]
        alloc = m["alloc"]
        c.banker = Banker(available, maximum, alloc)
        safe, seq = c.banker.is_safe()
        c.log("banker", f"Textbook Banker initialized: safe={safe}, seq={seq}")
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
        # Prefer live cluster banker if available, else textbook banker
        b = getattr(c.res_mgr, "cluster_banker", None) if hasattr(c, "res_mgr") else c.banker
        if not b:
            if c.banker:
                b = c.banker
            else:
                return {"type": "ERROR", "error": "Banker algorithm not initialized"}
        safe, seq = b.is_safe()
        return {
            "type": "BANKER_STATE",
            "available": b.available,
            "max": b.max,
            "alloc": b.alloc,
            "safe": safe,
            "safe_sequence": seq,
            "enabled": getattr(c.res_mgr, "banker_enabled", True) if hasattr(c, "res_mgr") else True,
        }

    @coord.handler("BANKER_TOGGLE")
    def _bt(c, ctx, m):
        mode = m.get("enabled")
        if hasattr(c, "res_mgr"):
            new_state = c.res_mgr.toggle_banker(mode)
        else:
            new_state = True
        c.log("banker", f"Admission control Banker set to {'ON' if new_state else 'OFF'}")
        return {"type": "OK", "enabled": new_state}

    @coord.handler("DEADLOCK_DEMO")
    def _dd(c, ctx, m):
        scenario = m.get("scenario", "circular")
        wf = deadlock_detector.SCENARIOS.get(scenario, deadlock_detector.SCENARIOS["circular"])
        cyc = deadlock_detector.detect(wf)
        c.log("deadlock", f"Scenario {scenario}: cycle {' -> '.join(cyc)} DETECTED" if cyc else "no cycle, safe")
        return {"type": "DEADLOCK_RESULT", "wait_for": wf, "cycle": cyc, "deadlock": bool(cyc)}

    @coord.handler("DEADLOCK_DETECT")
    def _detect_live(c, ctx, m):
        wf = c.res_mgr.get_wait_for_graph() if hasattr(c, "res_mgr") else {}
        cycles = deadlock_detector.find_all_cycles(wf)
        primary_cycle = cycles[0] if cycles else []
        c.log("deadlock", f"Live detection: {len(cycles)} cycle(s) found: {cycles}")
        return {
            "type": "DEADLOCK_RESULT",
            "wait_for": wf,
            "cycle": primary_cycle,
            "all_cycles": cycles,
            "deadlock": bool(cycles),
            "detected_count": getattr(c.res_mgr, "deadlocks_detected", 0) if hasattr(c, "res_mgr") else 0,
            "resolved_count": getattr(c.res_mgr, "deadlocks_resolved", 0) if hasattr(c, "res_mgr") else 0,
        }

    @coord.handler("DEADLOCK_RECOVER")
    def _recover(c, ctx, m):
        policy = m.get("policy", "youngest")
        if not hasattr(c, "res_mgr"):
            return {"type": "ERROR", "error": "Resource manager unavailable"}

        wf = c.res_mgr.get_wait_for_graph()
        cycles = deadlock_detector.find_all_cycles(wf)
        if not cycles:
            return {"type": "RECOVERY_RESULT", "recovered": False, "reason": "No active deadlock cycles detected"}

        proc_table = c.proc_mgr.list_all() if hasattr(c, "proc_mgr") else c.tasks
        victim = c.res_mgr.select_victim(cycles[0], proc_table, policy)
        if not victim:
            return {"type": "ERROR", "error": "Failed to select victim from cycle"}

        # Kill victim to release resources
        kill_fn = c.handlers.get("PROC_KILL")
        if kill_fn:
            kill_fn(c, ctx, {"pid": victim})
        c.res_mgr.release(victim)
        c.res_mgr.deadlocks_resolved += 1
        record = {
            "time": c.clock.t,
            "victim": victim,
            "policy": policy,
            "cycle": cycles[0],
        }
        c.res_mgr.recovery_log.append(record)
        c.log("deadlock", f"Deadlock resolved: terminated victim {victim} (policy: {policy})")

        return {
            "type": "RECOVERY_RESULT",
            "recovered": True,
            "victim": victim,
            "policy": policy,
            "cycle": cycles[0],
            "resolved_count": c.res_mgr.deadlocks_resolved,
        }
