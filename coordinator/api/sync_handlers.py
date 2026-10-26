"""NEXUS-OS Synchronization & Distributed Mutual Exclusion Handlers.
Implements RA_SIMULATE, SYNC_DEMO, RW_DEMO, PHILOSOPHERS_DEMO,
BOUNDED_QUEUE_DEMO, RACE_DEMO, and VMSTAT telemetry.
Concept: Ricart-Agrawala algorithm with logical clocks, Semaphores, Monitors, RWLock, and Dining Philosophers.
"""

from coordinator.synchronization.ricart_agrawala import simulate
from coordinator.synchronization.primitives import (
    producer_consumer,
    mutex_demo,
    file_store_race_demo,
    BoundedQueue,
)
from coordinator.synchronization.readers_writers import demonstrate_starvation
from demo.philosophers import run_philosophers
from tools.vmstat_snapshot import get_vm_snapshot
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

    @coord.handler("RW_DEMO")
    def _rw_demo(c, ctx, m):
        pref = m.get("preference", "reader")
        duration = float(m.get("duration", 0.3))
        res = demonstrate_starvation(preference=pref, test_time_sec=duration)
        c.log("sync", f"RWLock demo: preference={pref}, starved={res['starved']}")
        return {"type": "RW_DEMO_RESULT", **res}

    @coord.handler("PHILOSOPHERS_DEMO")
    def _ph_demo(c, ctx, m):
        mode = m.get("mode", "hierarchical")
        rounds = int(m.get("rounds", 2))
        res = run_philosophers(mode=mode, rounds=rounds)
        c.log("sync", f"Dining Philosophers ({mode}): deadlocked={res['deadlocked']}, meals={res['total_meals']}")
        return {"type": "PHILOSOPHERS_RESULT", **res}

    @coord.handler("BOUNDED_QUEUE_DEMO")
    def _bq_demo(c, ctx, m):
        cap = int(m.get("capacity", 5))
        items_count = int(m.get("items", 12))
        bq = BoundedQueue(capacity=cap)

        import threading
        log = []

        def producer():
            for i in range(items_count):
                bq.put(f"item-{i}")
                log.append(f"Produced item-{i} (depth={bq.qsize()})")

        def consumer():
            for _ in range(items_count):
                val = bq.get()
                log.append(f"Consumed {val} (depth={bq.qsize()})")

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        return {
            "type": "BOUNDED_QUEUE_RESULT",
            "metrics": bq.metrics(),
            "log": log[-15:],
        }

    @coord.handler("RACE_DEMO")
    def _race_demo(c, ctx, m):
        threads = int(m.get("threads", 4))
        iters = int(m.get("iterations", 200))
        res = file_store_race_demo(threads=threads, iterations=iters)
        c.log("sync", f"Storage race demo: race_detected={res['race_detected']}, lost={res['lost_updates']}")
        return {"type": "RACE_RESULT", **res}

    @coord.handler("VMSTAT")
    def _vmstat(c, ctx, m):
        return {"type": "VMSTAT_RESULT", **get_vm_snapshot()}
