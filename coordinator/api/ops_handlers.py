"""NEXUS-OS Operations & Metrics Handlers.
Implements DOCKER_STATUS, CHAOS_ACTION, UTIL, and METRICS queries with CSV export.
Concept: Observability, measured performance evaluation, and container metrics.
"""

import csv
import os
import time
from coordinator.resource_manager import resource_manager


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
        with c.lock:
            nodes_info = [
                {
                    "node_id": nid,
                    "status": n.get("status", "OFFLINE"),
                    "cpu": n.get("cpu", 0),
                    "load": n.get("load", 0),
                    "done": n.get("done", 0),
                    "container": f"nexus-{nid}",
                }
                for nid, n in c.nodes.items()
            ]
        return {
            "type": "DOCKER_STATUS",
            "containers": nodes_info,
            "mode": "process_cluster",
            "note": "Running in local multi-process mode; Docker container metrics fallback active",
        }

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
