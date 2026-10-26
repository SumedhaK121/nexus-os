"""NEXUS-OS Synchronization & Distributed Mutual Exclusion Handlers.
Implements RA_SIMULATE, SYNC_DEMO, and distributed lock routing.
Concept: Ricart-Agrawala algorithm with logical clocks, Semaphores, and Mutexes.
"""

from coordinator.synchronization.ricart_agrawala import simulate
from coordinator.synchronization.primitives import producer_consumer, mutex_demo
from coordinator.node_manager import node_manager


def register(coord):
    online = lambda: node_manager.online(coord.nodes)

    @coord.handler("RA_SIMULATE")
    def _ra(c, ctx, m):
        nodes = m.get("nodes") or online() or ["node-1", "node-2", "node-3"]
        r = simulate(nodes, m["requesters"])
        c.log("ricart-agrawala", f"CS entry order {r['order']} ({r['messages']} messages)")
        return {"type": "RA_RESULT", **r}

    @coord.handler("SYNC_DEMO")
    def _pc(c, ctx, m):
        if m.get("kind") == "mutex":
            return {"type": "SYNC_RESULT", **mutex_demo()}
        return {"type": "SYNC_RESULT", "log": producer_consumer()}
