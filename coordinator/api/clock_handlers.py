"""NEXUS-OS Distributed Clock API Handlers.
Implements event batch collection (EVENTS), unified causal timeline (CAUSAL_LOG),
and vector clock concurrency detection demonstration (CONCURRENT_DEMO).
Concept: Lamport timestamps (Lamport 1978) and Vector Clocks (Mattern 1989).
"""

from distributed_clock.vector_clock import VectorClock, are_concurrent, happens_before


def register(coord):
    @coord.handler("EVENTS")
    def _events(c, ctx, m):
        new_events = m.get("events", [])
        node_id = m.get("node_id") or (ctx.node_id if ctx else "unknown")

        with c.lock:
            for ev in new_events:
                # Normalize keys
                t = ev.get("ts", ev.get("T", 0))
                who = ev.get("node_id", ev.get("who", node_id))
                text = ev.get("event", "")
                vc = ev.get("vc", {})

                # Update coordinator clocks
                c.clock.update(t)
                c.vc.merge(vc)

                c.events.append({
                    "T": t,
                    "who": who,
                    "event": text,
                    "vc": dict(vc),
                    "wall_time": ev.get("wall_time"),
                })

            # Sort unified timeline by (Lamport timestamp, node_id)
            c.events.sort(key=lambda x: (x.get("T", 0), x.get("who", "")))

            # Keep bounded history
            if len(c.events) > 1000:
                c.events = c.events[-1000:]

        return {"type": "EVENTS_ACK", "count": len(new_events)}

    @coord.handler("CAUSAL_LOG")
    def _causal_log(c, ctx, m):
        limit = int(m.get("limit", 100))
        filter_node = m.get("node")
        filter_mode = m.get("filter", "all")

        with c.lock:
            events_copy = list(c.events)

        if filter_node:
            events_copy = [e for e in events_copy if e.get("who") == filter_node]

        timeline = events_copy[-limit:]

        # Find concurrent event pairs if requested
        concurrent_pairs = []
        if filter_mode in ("concurrent", "all"):
            n = len(timeline)
            for i in range(n):
                for j in range(i + 1, min(i + 20, n)):
                    e1 = timeline[i]
                    e2 = timeline[j]
                    if e1.get("who") != e2.get("who") and e1.get("vc") and e2.get("vc"):
                        if are_concurrent(e1["vc"], e2["vc"]):
                            concurrent_pairs.append({
                                "event_1": {"who": e1["who"], "T": e1["T"], "event": e1["event"], "vc": e1["vc"]},
                                "event_2": {"who": e2["who"], "T": e2["T"], "event": e2["event"], "vc": e2["vc"]},
                                "relation": "CONCURRENT",
                            })

        return {
            "type": "CAUSAL_LOG_RESULT",
            "current_lamport": c.clock.t,
            "coordinator_vc": c.vc.to_dict(),
            "timeline": timeline,
            "concurrent_pairs": concurrent_pairs[:20],
        }

    @coord.handler("CONCURRENT_DEMO")
    def _concurrent_demo(c, ctx, m):
        """Demonstrates concurrent edits with non-dominating vector clocks.
        Node A and Node B fork from common snapshot V0 = {A: 1, B: 1}.
        Node A performs edit -> V_A = {A: 2, B: 1}
        Node B performs edit -> V_B = {A: 1, B: 2}
        Vector comparison shows V_A || V_B (CONCURRENT!).
        """
        v0 = {"node-1": 1, "node-2": 1, "coordinator": 1}

        vc_a = VectorClock("node-1", initial=v0)
        vc_b = VectorClock("node-2", initial=v0)

        # Node A performs independent write to report.txt
        v_a = vc_a.tick()  # {"node-1": 2, "node-2": 1, "coordinator": 1}
        e_a = {"node": "node-1", "action": "Write report.txt (student 1 hypothesis)", "vc": v_a, "T": 4}

        # Node B performs independent concurrent write to report.txt
        v_b = vc_b.tick()  # {"node-1": 1, "node-2": 2, "coordinator": 1}
        e_b = {"node": "node-2", "action": "Write report.txt (student 2 proof)", "vc": v_b, "T": 4}

        rel = VectorClock.compare(v_a, v_b)

        c.log("clock_demo", f"Concurrent edit demo: node-1 ({v_a}) vs node-2 ({v_b}) -> {rel}")

        return {
            "type": "CONCURRENT_DEMO_RESULT",
            "initial_state": v0,
            "event_a": e_a,
            "event_b": e_b,
            "relation": rel,
            "explanation": (
                "Under Lamport scalar clocks, both events have timestamp T=4, hiding the causal relationship. "
                f"Under Vector Clocks, node-1 has {v_a} and node-2 has {v_b}. "
                "Neither vector clock dominates the other: node-1 is ahead on node-1, but node-2 is ahead on node-2. "
                "Therefore, the relation is strictly CONCURRENT (causal fork / conflicting edits). "
                "This allows NEXUS-OS to preserve both versions as conflicted copies rather than silently overwriting data."
            ),
        }
