"""NEXUS-OS Core API Handlers.
Implements REGISTER, HEARTBEAT, SUBMIT, SUBMIT_TRACE, TASK_STARTED, TASK_DONE, TASK_FAILED,
COMPARE, STATUS, PEERS, PROC_LIST, PROC_KILL, PROC_SUSPEND, PROC_RESUME.
Concept: Process Control Blocks (PCB), CPU scheduling, process lifecycle, and peer discovery.
"""

import json
import os
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
                if n.get("simulated_down"):
                    return None
                if n.get("simulated_suspect"):
                    if time.time() - n.get("simulated_suspect_time", 0) < 6.0:
                        n["status"] = "SUSPECT"
                        return None
                    else:
                        n["simulated_suspect"] = False
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
        procs = m["processes"]
        algo = m.get("algo", "fcfs")
        quantum = m.get("quantum", 2)
        c.active_policy = algo

        result = scheduler.run(algo, procs, quantum)
        by_pid = {p["pid"]: p for p in procs}

        order = []
        for item in result["gantt"]:
            pid = item[0]
            if pid not in order:
                order.append(pid)
        c.log("scheduler", f"Policy {algo.upper()} dispatch order: {order}")

        with c.lock:
            online = node_manager.online(c.nodes)
        if not online:
            return {"type": "ERROR", "error": "no nodes online"}

        assigned = {}
        now = time.time()
        if not hasattr(c, "task_explanations"):
            c.task_explanations = {}

        with c.lock:
            for pid in order:
                nid = pick_node(c.nodes, online)
                burst = by_pid[pid].get("burst", 1)
                prio = by_pid[pid].get("priority", 1)
                arr = by_pid[pid].get("arrival", 0)

                # Generate factual explainable execution trace reason
                if algo == "sjf":
                    reason = f"{pid} selected because its burst time ({burst}s) was the shortest among all ready tasks."
                elif algo == "srtf":
                    reason = f"{pid} selected because its remaining burst ({burst}s) was the shortest at scheduling decision time."
                elif algo in ("priority", "priority_aging"):
                    reason = f"{pid} selected because it had the highest priority level (priority={prio}) among ready tasks."
                elif algo == "rr":
                    reason = f"{pid} allocated execution time slice (quantum={quantum}s) as head of circular ready queue."
                else:
                    reason = f"{pid} scheduled in first-come first-served arrival order (arrival={arr}s)."

                c.tasks[pid] = {
                    "node": nid,
                    "state": "Waiting",
                    "burst": burst,
                    "submit_time": now,
                    "start_time": None,
                    "end_time": None,
                    "job_type": by_pid[pid].get("job_type", "sim"),
                    "args": by_pid[pid].get("args", []),
                    "priority": prio,
                    "arrival": arr,
                    "algo": algo.upper(),
                    "reason": reason,
                }
                c.task_explanations[pid] = {
                    "pid": pid,
                    "algo": algo.upper(),
                    "burst": burst,
                    "priority": prio,
                    "arrival": arr,
                    "node": nid,
                    "reason": reason,
                }
                assigned[pid] = nid
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
                            priority=prio,
                        )
                    pcb.node = nid
                    try:
                        pcb.set_state("READY")
                    except ValueError:
                        pass

                exec_msg = {
                    "type": "EXEC",
                    "pid": pid,
                    "burst": burst,
                    "job_type": by_pid[pid].get("job_type", "sim"),
                    "args": by_pid[pid].get("args", []),
                    "ts": c.clock.tick(),
                }
                c.nodes[nid]["conn"].send(exec_msg)
                c.log("scheduler", f"{pid} -> {nid} ({by_pid[pid].get('job_type', 'sim')}): {reason}")

        return {
            "type": "SUBMITTED",
            "assigned": assigned,
            "metrics": result["avg"],
            "gantt": result["gantt"],
            "explanations": c.task_explanations,
        }

    @coord.handler("SUBMIT_TRACE")
    def _submit_trace(c, ctx, m):
        trace_path = m.get("path")
        procs = m.get("processes")
        if not procs and trace_path and os.path.exists(trace_path):
            with open(trace_path, "r", encoding="utf-8") as f:
                procs = json.load(f)
        if not procs:
            default_trace = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "demo", "lab_trace.json")
            if os.path.exists(default_trace):
                with open(default_trace, "r", encoding="utf-8") as f:
                    procs = json.load(f)
            else:
                return {"type": "ERROR", "error": "No workload trace specified"}

        algo = m.get("algo", "fcfs")
        quantum = m.get("quantum", 2)
        return _submit(c, ctx, {"processes": procs, "algo": algo, "quantum": quantum})

    @coord.handler("TASK_STARTED")
    def _started(c, ctx, m):
        pid = m["pid"]
        node_id = ctx.node_id or m.get("node_id")
        now = time.time()
        with c.lock:
            if pid in c.tasks:
                if c.tasks[pid]["start_time"] is None:
                    c.tasks[pid]["start_time"] = now
                c.tasks[pid]["state"] = "Running"
            if node_id and node_id in c.nodes:
                c.nodes[node_id]["load"] = max(0, c.nodes[node_id].get("load", 0) + 1)
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "RUNNING")
                except Exception:
                    pass
        c.log(node_id or "node", f"started execution of {pid}")
        return None

    @coord.handler("TASK_DONE")
    def _done(c, ctx, m):
        pid = m.get("pid")
        node_id = ctx.node_id or m.get("node_id")
        now = time.time()
        with c.lock:
            if pid not in c.tasks:
                c.log("coordinator", f"TASK_DONE ignored for unknown pid: {pid}")
                return None
            task = c.tasks[pid]
            task["state"] = "Completed"
            task["end_time"] = now
            if task.get("start_time") is None:
                task["start_time"] = now - m.get("wall_time", 0.5)

            submit_time = task.get("submit_time", task["start_time"])
            start_time = task["start_time"]
            waiting_time = max(0.0, start_time - submit_time)
            turnaround_time = max(0.0, now - submit_time)
            response_time = waiting_time

            c.actual_gantt.append((pid, round(start_time, 2), round(now, 2), node_id))
            c.measured_metrics.append({
                "pid": pid,
                "policy": getattr(c, "active_policy", "fcfs"),
                "submit_time": round(submit_time, 2),
                "start_time": round(start_time, 2),
                "end_time": round(now, 2),
                "waiting_time": round(waiting_time, 3),
                "turnaround_time": round(turnaround_time, 3),
                "response_time": round(response_time, 3),
                "cpu_time": m.get("cpu_time", 0.0),
                "wall_time": m.get("wall_time", turnaround_time),
            })

            if node_id and node_id in c.nodes:
                c.nodes[node_id]["load"] = max(0, c.nodes[node_id].get("load", 1) - 1)
                c.nodes[node_id]["done"] = c.nodes[node_id].get("done", 0) + 1

            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "COMPLETED")
                except Exception:
                    pass

        c.log(node_id or "node", f"completed {pid} (turnaround={turnaround_time:.2f}s)")
        return None

    @coord.handler("TASK_FAILED")
    def _failed(c, ctx, m):
        pid = m.get("pid")
        node_id = ctx.node_id or m.get("node_id")
        with c.lock:
            if pid in c.tasks:
                c.tasks[pid]["state"] = "Failed"
                c.tasks[pid]["error"] = m.get("error")
            if node_id and node_id in c.nodes:
                c.nodes[node_id]["load"] = max(0, c.nodes[node_id]["load"] - c.tasks.get(pid, {}).get("burst", 0))
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "FAILED")
                except Exception:
                    pass
        c.log(node_id or "node", f"task {pid} FAILED: {m.get('error')}")
        return None

    @coord.handler("PROC_LIST")
    def _proc_list(c, ctx, m):
        with c.lock:
            if hasattr(c, "proc_mgr"):
                return {"type": "PROC_LIST", "processes": c.proc_mgr.list_all()}
            return {"type": "PROC_LIST", "processes": dict(c.tasks)}

    @coord.handler("PROC_KILL")
    def _proc_kill(c, ctx, m):
        pid = m.get("pid")
        target_node = None
        with c.lock:
            task = c.tasks.get(pid)
            if task:
                target_node = task.get("node")
                task["state"] = "Killed"
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "KILLED")
                except Exception:
                    pass
        if target_node and target_node in c.nodes:
            conn = c.nodes[target_node].get("conn")
            if conn:
                conn.send({"type": "PROC_KILL", "pid": pid, "ts": c.clock.tick()})
        c.log("coordinator", f"PROC_KILL issued for PID {pid} on {target_node}")
        return {"type": "OK", "killed": pid}

    @coord.handler("PROC_SUSPEND")
    def _proc_suspend(c, ctx, m):
        pid = m.get("pid")
        target_node = None
        with c.lock:
            task = c.tasks.get(pid)
            if task:
                target_node = task.get("node")
                task["state"] = "Waiting"
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "WAITING")
                except Exception:
                    pass
        if target_node and target_node in c.nodes:
            conn = c.nodes[target_node].get("conn")
            if conn:
                conn.send({"type": "PROC_SUSPEND", "pid": pid, "ts": c.clock.tick()})
        c.log("coordinator", f"PROC_SUSPEND issued for PID {pid}")
        return {"type": "OK", "suspended": pid}

    @coord.handler("PROC_RESUME")
    def _proc_resume(c, ctx, m):
        pid = m.get("pid")
        target_node = None
        with c.lock:
            task = c.tasks.get(pid)
            if task:
                target_node = task.get("node")
                task["state"] = "Running"
            if hasattr(c, "proc_mgr"):
                try:
                    c.proc_mgr.transition(pid, "READY")
                    c.proc_mgr.transition(pid, "RUNNING")
                except Exception:
                    pass
        if target_node and target_node in c.nodes:
            conn = c.nodes[target_node].get("conn")
            if conn:
                conn.send({"type": "PROC_RESUME", "pid": pid, "ts": c.clock.tick()})
        c.log("coordinator", f"PROC_RESUME issued for PID {pid}")
        return {"type": "OK", "resumed": pid}

    @coord.handler("COMPARE")
    def _cmp(c, ctx, m):
        procs = m["processes"]
        quantum = m.get("quantum", 2)
        extended = m.get("extended", True)
        results = scheduler.compare(procs, quantum, extended=extended)
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
                if "mem" in v:
                    nodes_status[k]["mem"] = v["mem"]

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

            pcb_table = (
                c.proc_mgr.list_all()
                if hasattr(c, "proc_mgr")
                else {pid: {"pid": pid, "state": t["state"], "node": t.get("node", "—"), "burst": t.get("burst", 1)}
                      for pid, t in tasks_dict.items()}
            )

            # Distributed File System stats
            dfs_files = c.dfs.meta.get_all_files() if hasattr(c, "dfs") else []
            dfs_node_counts = c.dfs.meta.get_node_block_counts() if hasattr(c, "dfs") else {}
            dfs_under_rep = len(c.dfs.meta.get_under_replicated_blocks(2)) if hasattr(c, "dfs") else 0

            containers_summary = [
                {
                    "container": f"nexus-{k}",
                    "node_id": k,
                    "status": v.get("status", "OFFLINE"),
                    "cpu": v.get("cpu", 0),
                    "load": v.get("load", 0),
                    "done": v.get("done", 0),
                    "mem_limit": f"{v.get('mem_mb', 256)}MB",
                    "cpus": f"{v.get('cpu_slots', 2)}.0",
                }
                for k, v in c.nodes.items()
            ]

            return {
                "type": "STATUS",
                "clock": c.clock.t,
                "clock_vc": c.vc.to_dict() if hasattr(c, "vc") else {},
                "nodes": nodes_status,
                "tasks": tasks_dict,
                "proc_table": pcb_table,
                "events": events_list,
                "files": files_list,
                "dfs_files": dfs_files,
                "dfs_node_counts": dfs_node_counts,
                "dfs_under_replicated": dfs_under_rep,
                "locks": c.locks.get_status() if hasattr(c, "locks") else {},
                "sync": c.sync_mgr.get_stats() if hasattr(c, "sync_mgr") else {},
                "containers": containers_summary,
                "util": util_data,
                "procs": procs_data,
                "safe": safe_flag,
                "net": net_dict,
                "cache": cache_stats,
                "replicas": rep_placement,
                "banker": banker_data,
                "policy": getattr(c, "active_policy", "fcfs"),
                "metrics_count": len(getattr(c, "measured_metrics", [])),
                "explanations": getattr(c, "task_explanations", {}),
            }
