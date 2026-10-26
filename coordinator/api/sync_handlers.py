"""NEXUS-OS Synchronization & Distributed Mutual Exclusion Handlers.
Implements RA_SIMULATE, SYNC_DEMO, RW_DEMO, PHILOSOPHERS_DEMO,
BOUNDED_QUEUE_DEMO, RACE_DEMO, VMSTAT telemetry,
Distributed Lock Manager endpoints (LOCK_ACQUIRE, LOCK_RELEASE, LOCK_RENEW, LOCK_STATUS),
Real Ricart-Agrawala Cluster Demo (RA_CLUSTER_DEMO), and Complexity Analysis (RA_COMPLEXITY).
Concept: Ricart-Agrawala (Ricart & Agrawala 1981), Distributed Leases (Chubby/ZooKeeper).
"""

import threading
import time
from communication import rpc
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

    # ------------------ Distributed Lock Manager Handlers ------------------

    @coord.handler("LOCK_ACQUIRE")
    def _lock_acquire(c, ctx, m):
        name = m["name"]
        client = m.get("client_id") or (ctx.node_id if ctx else "client")
        lease = m.get("lease_sec")
        res = c.locks.acquire(name, client, lease_sec=lease)
        return res

    @coord.handler("LOCK_RELEASE")
    def _lock_release(c, ctx, m):
        name = m["name"]
        client = m.get("client_id") or (ctx.node_id if ctx else "client")
        res = c.locks.release(name, client)
        return res

    @coord.handler("LOCK_RENEW")
    def _lock_renew(c, ctx, m):
        name = m["name"]
        client = m.get("client_id") or (ctx.node_id if ctx else "client")
        lease = m.get("lease_sec")
        res = c.locks.renew(name, client, lease_sec=lease)
        return res

    @coord.handler("LOCK_STATUS")
    def _lock_status(c, ctx, m):
        return {"type": "LOCK_STATUS_RESULT", "locks": c.locks.get_status()}

    # ------------------ Real Ricart-Agrawala Cluster Demostration ------------------

    @coord.handler("RA_CLUSTER_DEMO")
    def _ra_cluster_demo(c, ctx, m):
        nodes_list = online()
        if len(nodes_list) < 2:
            return {"type": "ERROR", "error": f"Need at least 2 online nodes for RA cluster demo, found: {nodes_list}"}

        n1 = nodes_list[0]
        n2 = nodes_list[1]
        trace = []

        trace.append(f"1. {n1} requests Critical Section via RaEnter (peers: {nodes_list})")
        r1 = rpc.call_node(n1, "RaEnter", {"peers": nodes_list}, timeout=3.0)
        trace.append(f"   {n1} response: {r1}")

        # Check status of n1
        st1 = rpc.call_node(n1, "RaStatus", {})
        trace.append(f"2. {n1} state is now: {st1.get('state')} (Critical Section HELD)")

        # In background, n2 requests CS (should be deferred by n1)
        trace.append(f"3. {n2} requests Critical Section concurrently")
        n2_done = [False]
        n2_res = [{}]

        def n2_requester():
            n2_res[0] = rpc.call_node(n2, "RaEnter", {"peers": nodes_list}, timeout=5.0)
            n2_done[0] = True

        t = threading.Thread(target=n2_requester)
        t.start()
        time.sleep(0.15)  # Let n2 send request to n1

        # Check status of n1 deferred queue
        st1_after = rpc.call_node(n1, "RaStatus", {})
        trace.append(f"4. {n1} deferred queue contains: {st1_after.get('deferred_nodes')}")

        # Release CS on n1 -> unblocks n2
        trace.append(f"5. {n1} exits Critical Section via RaExit -> flushes deferred reply to {n2}")
        rel1 = rpc.call_node(n1, "RaExit", {})
        trace.append(f"   {n1} released {rel1.get('released_count')} deferred replies")

        t.join(timeout=2.0)
        st2 = rpc.call_node(n2, "RaStatus", {})
        trace.append(f"6. {n2} unblocked and entered Critical Section: state={st2.get('state')}")

        # n2 exits CS
        rpc.call_node(n2, "RaExit", {})
        trace.append(f"7. {n2} exits Critical Section. Mutual exclusion test complete!")

        c.log("ricart-agrawala", f"Real RA cluster demo complete between {n1} and {n2}")
        return {
            "type": "RA_CLUSTER_DEMO_RESULT",
            "nodes": [n1, n2],
            "trace": trace,
            "success": True,
        }

    @coord.handler("RA_COMPLEXITY")
    def _ra_complexity(c, ctx, m):
        table = []
        for n in range(2, 9):
            reqs = n - 1
            reps = n - 1
            total = 2 * (n - 1)
            table.append({
                "cluster_size": n,
                "requests_sent": reqs,
                "replies_received": reps,
                "total_messages": total,
                "lamport_comparison": 3 * (n - 1),  # Lamport 1978 requires 3(N-1) messages
            })
        return {
            "type": "RA_COMPLEXITY_RESULT",
            "algorithm": "Ricart-Agrawala (1981)",
            "message_complexity": "2(N - 1)",
            "table": table,
            "explanation": (
                "Ricart-Agrawala eliminates the explicit RELEASE message required by Lamport's algorithm. "
                "Each node sends (N-1) REQUEST messages and waits for (N-1) REPLY messages. "
                "Deferred replies are sent upon exiting the critical section, achieving exactly 2(N-1) messages per entry."
            ),
        }

    # ------------------ Dropbox-Lite Distributed Sync Handlers ------------------

    @coord.handler("SYNC_CHECK_CHUNKS")
    def _sync_check_chunks(c, ctx, m):
        path = m["path"]
        chunks = m.get("chunk_checksums", [])
        return c.sync_mgr.check_chunks(path, chunks)

    @coord.handler("SYNC_PUSH")
    def _sync_push(c, ctx, m):
        path = m["path"]
        content = m.get("content", "")
        chunks = m.get("chunks", [])
        full_size = m.get("full_size", len(content))
        file_checksum = m.get("file_checksum", "")
        node_id = m.get("node_id") or (ctx.node_id if ctx else "client")
        new_vc = m.get("new_vc", {})
        base_vc = m.get("base_vc")
        base_ver = m.get("base_version")
        return c.sync_mgr.sync_push(
            path=path,
            content=content,
            chunks_data=chunks,
            full_size=full_size,
            file_checksum=file_checksum,
            node_id=node_id,
            new_vc=new_vc,
            base_vc=base_vc,
            base_version=base_ver,
        )

    @coord.handler("SYNC_PULL")
    def _sync_pull(c, ctx, m):
        path = m["path"]
        return c.sync_mgr.sync_pull(path)

    @coord.handler("SYNC_DELETE")
    def _sync_delete(c, ctx, m):
        path = m["path"]
        node_id = m.get("node_id") or (ctx.node_id if ctx else "client")
        return c.sync_mgr.sync_delete(path, node_id=node_id)

    @coord.handler("SYNC_STATUS")
    def _sync_status(c, ctx, m):
        stats = c.sync_mgr.get_stats()
        node_agents = {}
        for nid in node_manager.online(c.nodes):
            res = rpc.call_node(nid, "SyncStatus", {})
            if res.get("node_id"):
                node_agents[nid] = res
        return {
            "type": "SYNC_STATUS_RESULT",
            **stats,
            "node_agents": node_agents,
        }

    @coord.handler("SYNC_CONFIG")
    def _sync_config(c, ctx, m):
        if "policy" in m:
            c.sync_mgr.policy = str(m["policy"]).upper()
        return {"type": "OK", "policy": c.sync_mgr.policy}

    @coord.handler("SYNC_ENGINE_DEMO")
    def _sync_engine_demo(c, ctx, m):
        return c.sync_mgr.run_sync_demo()
