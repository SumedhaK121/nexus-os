"""NEXUS-OS Core API Handlers.
Implements REGISTER, HEARTBEAT, SUBMIT, TASK_DONE, COMPARE, STATUS, PEERS.
Concept: Control plane coordination, process admission, health monitoring, and peer discovery.
"""

import time
from coordinator.scheduler import scheduler_manager as scheduler
from coordinator.scheduler.node_selector import pick_node
from coordinator.node_manager import node_manager
from coordinator.process_manager import process_manager
from coordinator.resource_manager import resource_manager


def register(coord):
    @coord.handler("REGISTER")
    def _reg(c, ctx, m):
        ctx.node_id = m["node_id"]
        addr = m.get("addr", ["127.0.0.1", 0])
        cpu_slots = m.get("cpu_slots", 2)
        mem_mb = m.get("mem_mb", 256)
        io_slots = m.get("io_slots", 2)
        with c.lock:
            c.nodes[ctx.node_id] = {
                "conn": ctx.conn,
                "last_seen": time.time(),
                "cpu": 0,
                "load": 0,
                "done": 0,
                "status": "ONLINE",
                "addr": addr,
                "cpu_slots": cpu_slots,
                "mem_mb": mem_mb,
                "io_slots": io_slots,
            }
            if hasattr(c, "node_mgr"):
                c.node_mgr.register_node(ctx.node_id, addr=addr, cpu_slots=cpu_slots, mem_mb=mem_mb, io_slots=io_slots)
            if hasattr(c, "res_mgr"):
                c.res_mgr.update_cluster_capacity(c.nodes)
        c.log("coordinator", f"{ctx.node_id} registered at {addr}")
        return {"type": "REGISTERED", "node_id": ctx.node_id}

    @coord.handler("HEARTBEAT")
    def _hb(c, ctx, m):
        node_id = ctx.node_id or m.get("node_id")
        if not node_id:
            return None
        with c.lock:
            n = c.nodes.get(node_id)
            if n:
                n.update(last_seen=time.time(), cpu=m.get("cpu", 0), status="ONLINE")
                if "mem" in m:
                    n["mem"] = m["mem"]
                if "load" in m:
                    n["load"] = m["load"]
            if hasattr(c, "node_mgr"):
                c.node_mgr.update_heartbeat(node_id, cpu=m.get("cpu", 0))
        return None

    @coord.handler("SUBMIT")
    def _submit(c, ctx, m):
        procs, algo = m["processes"], m.get("algo", "fcfs")
        quantum = m.get("quantum", 2)
        result = scheduler.run(algo, procs, quantum)
        by_pid = {p["pid"]: p for p in procs}
        order = []
        for item in result["gantt"]:
            pid = item[0]
            if pid not in order:
                order.append(pid)
        c.log("scheduler", f"{result['algo']} order: {order}")

        with c.lock:
            online = node_manager.online(c.nodes)
        if not online:
            return {"type": "ERROR", "error": "no nodes online"}

        assigned = {}
        with c.lock:
            for pid in order:
                nid = pick_node(c.nodes, online)
                burst = by_pid[pid].get("burst", 1)
                c.nodes[nid]["load"] += burst
                c.tasks[pid] = {
                    "node": nid,
                    "state": "Running",
                    "burst": burst,
                    "submit_time": time.time(),
                    "job_type": by_pid[pid].get("job_type", "sim"),
                    "args": by_pid[pid].get("args", []),
                }
                assigned[pid] = nid
                # Update process manager PCB if present
                if hasattr(c, "proc_mgr"):
                    pcb = c.proc_mgr.get(pid)
                    if not pcb:
                        pcb = c.proc_mgr.add(
                            pid,
                            name=by_pid[pid].get("name", pid),
                            node=nid,
                            resources=by_pid[pid].get("resources"),
                            job_type=by_pid[pid].get("job_type", "sim"),
                            args=by_pid[pid].get("args", []),
                            burst=burst,
                            priority=by_pid[pid].get("priority", 1),
                        )
                    pcb.node = nid
                    try:
                        pcb.set_state("RUNNING")
                    except ValueError:
                        pass

                # Dispatch EXEC to worker node
                exec_msg = {
                    "type": "EXEC",
                    "pid": pid,
                    "burst": burst,
                    "job_type": by_pid[pid].get("job_type", "sim"),
                    "args": by_pid[pid].get("args", []),
                    "ts": c.clock.tick(),
                }
                c.nodes[nid]["conn"].send(exec_msg)
                c.log("scheduler", f"{pid} -> {nid}")

        return {
            "type": "SUBMITTED",
            "assigned": assigned,
            "metrics": result["avg"],
            "gantt": result["gantt"],
        }

    @coord.handler("TASK_DONE")
    def _done(c, ctx, m):
        pid = m.get("pid")
        node_id = ctx.node_id or m.get("node_id")
        with c.lock:
            if pid not in c.tasks:
                c.log("coordinator", f"TASK_DONE ignored for unknown pid: {pid}")
                return None
            c.tasks[pid]["state"] = "Completed"
            if node_id and node_id in c.nodes:
                c.nodes[node_id]["load"] = max(0, c.nodes[node_id]["load"] - c.tasks[pid].get("burst", 0))
                c.nodes[node_id]["done"] += 1
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "COMPLETED")
                except Exception:
                    pass
        c.log(node_id or "node", f"completed {pid}")
        return None

    @coord.handler("COMPARE")
    def _cmp(c, ctx, m):
        procs = m["processes"]
        quantum = m.get("quantum", 2)
        results = scheduler.compare(procs, quantum)
        return {
            "type": "COMPARED",
            "results": [{"algo": r["algo"], **r["avg"], "gantt": r["gantt"]} for r in results],
        }

    @coord.handler("PEERS")
    def _peers(c, ctx, m):
        with c.lock:
            if hasattr(c, "node_mgr"):
                peers = c.node_mgr.get_peers()
            else:
                peers = {
                    nid: {"host": n.get("addr", ["127.0.0.1", 0])[0], "port": n.get("addr", ["127.0.0.1", 0])[1]}
                    for nid, n in c.nodes.items()
                    if n.get("status") == "ONLINE"
                }
        return {"type": "PEERS", "peers": peers}

    @coord.handler("STATUS")
    def _status(c, ctx, m):
        with c.lock:
            nodes_status = {}
            for k, v in c.nodes.items():
                nodes_status[k] = {
                    x: v[x] for x in ("status", "cpu", "load", "done", "last_seen") if x in v
                }
                if "addr" in v:
                    nodes_status[k]["addr"] = v["addr"]
            tasks_dict = dict(c.tasks)
            events_list = c.events[-60:]
            files_list = c.files.listing() if hasattr(c, "files") else {}
            util_data = (
                c.res_mgr.get_utilization(c.banker)
                if hasattr(c, "res_mgr")
                else resource_manager.utilization(c.banker)
            )
            procs_data = process_manager.summary(tasks_dict)
            safe_flag = (c.banker.is_safe()[0] if c.banker else None)
            net_dict = dict(c.net)
            cache_stats = c.files.cache.stats() if hasattr(c, "files") else {}
            rep_placement = c.files.rep.placement if hasattr(c, "files") and hasattr(c.files, "rep") else {}
            banker_data = (
                {"available": c.banker.available, "max": c.banker.max, "alloc": c.banker.alloc}
                if c.banker
                else None
            )

            return {
                "type": "STATUS",
                "clock": c.clock.t,
                "nodes": nodes_status,
                "tasks": tasks_dict,
                "events": events_list,
                "files": files_list,
                "util": util_data,
                "procs": procs_data,
                "safe": safe_flag,
                "net": net_dict,
                "cache": cache_stats,
                "replicas": rep_placement,
                "banker": banker_data,
            }
