"""NEXUS-OS Distributed Clock API Handlers.
Implements event batch collection (EVENTS) and logical clock coordination.
Concept: Lamport timestamps and Vector Clocks for causal event ordering across nodes.
"""


def register(coord):
    @coord.handler("EVENTS")
    def _events(c, ctx, m):
        new_events = m.get("events", [])
        with c.lock:
            for ev in new_events:
                # Merge into events log
                c.events.append(ev)
                if "ts" in ev:
                    c.clock.update(ev["ts"])
            # Keep bounded history
            if len(c.events) > 500:
                c.events = c.events[-500:]
        return {"type": "EVENTS_ACK", "count": len(new_events)}
