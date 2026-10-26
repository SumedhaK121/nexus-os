"""NEXUS-OS Operations & Metrics Handlers.
Implements DOCKER_STATUS, CHAOS_ACTION, UTIL, and METRICS queries with CSV export.
Concept: Observability, measured performance evaluation, and container metrics.
"""

import csv
import json
import os
import subprocess
import time
from coordinator.resource_manager import resource_manager

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


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
        docker_containers = []
        is_live_docker = False

        # Attempt to probe live Docker daemon if available
        try:
            res = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                is_live_docker = True
                for line in res.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if parts:
                        name = parts[0]
                        status = parts[1] if len(parts) > 1 else "Running"
                        ports = parts[2] if len(parts) > 2 else ""
                        docker_containers.append({
                            "container": name,
                            "status": status,
                            "ports": ports,
                            "mem_limit": "256MB",
                            "cpus": "1.0",
                        })
        except Exception:
            pass

        # Synthesize from cluster nodes and coordinator telemetry
        with c.lock:
            nodes_info = [
                {
                    "node_id": nid,
                    "container": f"nexus-{nid}",
                    "status": n.get("status", "OFFLINE"),
                    "cpu": n.get("cpu", 0),
                    "load": n.get("load", 0),
                    "done": n.get("done", 0),
                    "mem_limit": f"{n.get('mem_mb', 256)}MB",
                    "cpus": f"{n.get('cpu_slots', 2)}.0",
                    "delay_ms": n.get("delay_ms", 0),
                }
                for nid, n in c.nodes.items()
            ]

        host_stats = {}
        if HAS_PSUTIL:
            try:
                mem = psutil.virtual_memory()
                host_stats = {
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "memory_total_mb": round(mem.total / (1024 * 1024), 1),
                    "memory_used_mb": round(mem.used / (1024 * 1024), 1),
                    "memory_percent": mem.percent,
                }
            except Exception:
                pass

        return {
            "type": "DOCKER_STATUS",
            "containers": docker_containers if is_live_docker else nodes_info,
            "nodes": nodes_info,
            "host_stats": host_stats,
            "mode": "docker_compose" if is_live_docker else "process_cluster",
            "note": "Docker daemon connected" if is_live_docker else "Running in process cluster mode with live psutil cgroup emulation",
        }

    @coord.handler("CHAOS_ACTION")
    def _chaos(c, ctx, m):
        action = str(m.get("action", "")).lower()
        node_id = m.get("node_id")
        if not node_id:
            return {"type": "ERROR", "error": "Missing node_id for CHAOS_ACTION"}

        with c.lock:
            n = c.nodes.get(node_id)
            if not n and action != "heal":
                return {"type": "ERROR", "error": f"Node {node_id} not found in cluster"}

            if action == "kill":
                if n:
                    n["status"] = "OFFLINE"
                    conn = n.get("conn")
                    if conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                if hasattr(c, "node_mgr"):
                    c.node_mgr.mark_offline(node_id)
                c._on_node_down(node_id)
                c.log("chaos", f"Injected KILL on node {node_id}")
                return {"type": "CHAOS_RESULT", "action": "kill", "node_id": node_id, "status": "OFFLINE"}

            elif action == "suspect":
                if n:
                    n["status"] = "SUSPECT"
                    n["last_seen"] = time.time() - 4.5
                if hasattr(c, "node_mgr"):
                    c.node_mgr.mark_suspect(node_id)
                c.log("chaos", f"Injected SUSPECT on node {node_id} (simulated heartbeat delay)")
                return {"type": "CHAOS_RESULT", "action": "suspect", "node_id": node_id, "status": "SUSPECT"}

            elif action in ("partition", "isolate"):
                if n:
                    n["status"] = "PARTITIONED"
                if hasattr(c, "node_mgr"):
                    c.node_mgr.mark_offline(node_id)
                c._on_node_down(node_id)
                c.log("chaos", f"Injected PARTITION isolating node {node_id}")
                return {"type": "CHAOS_RESULT", "action": "partition", "node_id": node_id, "status": "PARTITIONED"}

            elif action in ("heal", "restore"):
                if n:
                    n["status"] = "ONLINE"
                    n["last_seen"] = time.time()
                if hasattr(c, "node_mgr"):
                    info = c.node_mgr.nodes.get(node_id)
                    if info:
                        info.status = "ONLINE"
                        info.last_seen = time.time()
                    c.node_mgr.on_node_up(node_id)
                c._on_node_up(node_id)
                c.log("chaos", f"Healed node {node_id}: restored to ONLINE")
                return {"type": "CHAOS_RESULT", "action": "heal", "node_id": node_id, "status": "ONLINE"}

            elif action == "delay":
                delay_ms = int(m.get("delay_ms", 200))
                if n:
                    n["delay_ms"] = delay_ms
                c.log("chaos", f"Injected network DELAY of {delay_ms}ms on node {node_id}")
                return {"type": "CHAOS_RESULT", "action": "delay", "node_id": node_id, "delay_ms": delay_ms}

            else:
                return {"type": "ERROR", "error": f"Unknown chaos action '{action}'"}

    @coord.handler("METRICS")
    def _metrics(c, ctx, m):
        policy = m.get("policy") or getattr(c, "active_policy", "fcfs")
        export_csv = m.get("export_csv", True)
        with c.lock:
            records = [r for r in getattr(c, "measured_metrics", []) if policy == "all" or r.get("policy") == policy]
            gantt = list(getattr(c, "actual_gantt", []))

        avg = {"waiting": 0.0, "turnaround": 0.0, "response": 0.0, "count": len(records)}
        if records:
            avg["waiting"] = round(sum(r["waiting_time"] for r in records) / len(records), 3)
            avg["turnaround"] = round(sum(r["turnaround_time"] for r in records) / len(records), 3)
            avg["response"] = round(sum(r["response_time"] for r in records) / len(records), 3)

        csv_file = None
        if export_csv and records:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            ts_str = int(time.time())
            csv_file = os.path.join(logs_dir, f"metrics_{policy}_{ts_str}.csv")
            try:
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=["pid", "policy", "submit_time", "start_time", "end_time", "waiting_time", "turnaround_time", "response_time", "cpu_time", "wall_time"]
                    )
                    writer.writeheader()
                    for row in records:
                        writer.writerow(row)
                c.log("metrics", f"Exported {len(records)} task metrics to {os.path.basename(csv_file)}")
            except Exception as e:
                print(f"[Coordinator] CSV export failed: {e}", flush=True)

        return {
            "type": "METRICS_RESULT",
            "policy": policy,
            "measured_avg": avg,
            "records": records,
            "actual_gantt": gantt,
            "csv_exported": os.path.basename(csv_file) if csv_file else None,
        }

    @coord.handler("RPC_BENCH")
    def _rpc_bench(c, ctx, m):
        from tools.rpc_bench import run_rpc_benchmark
        iters = int(m.get("iterations", 20))
        kb = int(m.get("payload_kb", 8))
        return {"type": "RPC_BENCH_RESULT", **run_rpc_benchmark(iterations=iters, payload_kb=kb)}

    @coord.handler("IPC_BENCH")
    def _ipc_bench(c, ctx, m):
        from tools.ipc_demo import run_ipc_benchmark
        iters = int(m.get("iterations", 50))
        size = int(m.get("payload_bytes", 4096))
        return {"type": "IPC_BENCH_RESULT", **run_ipc_benchmark(iterations=iters, payload_size=size)}

    @coord.handler("GRPC_METRICS")
    def _grpc_metrics(c, ctx, m):
        from communication.grpc_transport import get_grpc_metrics
        return {"type": "GRPC_METRICS_RESULT", **get_grpc_metrics()}

    @coord.handler("ISO_DEMO")
    def _iso_demo(c, ctx, m):
        from demo.isolation_demo import run_isolation_demonstration
        limit = int(m.get("limit_mb", 80))
        target = int(m.get("leak_target_mb", 140))
        res = run_isolation_demonstration(limit_mb=limit, leak_target_mb=target)
        c.log("isolation", f"Cgroup OOM demonstration: PID {res['pid']} terminated at peak RSS {res['peak_rss_mb']} MB (quota {limit} MB)")
        return {"type": "ISO_DEMO_RESULT", **res}
