"""NEXUS-OS RPC Benchmark: TCP-JSON vs gRPC / HTTP/2.
Benchmarks request/response latency and data transfer throughput for TCP-JSON vs gRPC.
Exports benchmark metrics into logs/rpc_bench.csv.
Concept: Application layer RPC protocols, HTTP/2 multiplexing, Protocol Buffers binary framing vs JSON.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication import rpc
from communication.grpc_transport import HAS_GRPC, grpc_call_node, start_node_grpc_server
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer


class MockBenchmarkNode:
    """Lightweight in-process worker node exposing both TCP and gRPC endpoints."""

    def __init__(self, node_id="bench-node", base_dir=None):
        self.id = node_id
        self.base_dir = base_dir or tempfile.mkdtemp(prefix="nexus_bench_")
        self.block_store = BlockStore(self.base_dir, self.id)

        # 1. TCP Server
        self.tcp_server = NodeServer(host="127.0.0.1", port=0)
        self.tcp_server.register_method("PING", lambda p: {"type": "PONG", "node_id": self.id})
        self.tcp_server.register_method("PutBlock", self.block_store.put_block)
        self.tcp_server.register_method("GetBlock", self.block_store.get_block)
        self.tcp_port = self.tcp_server.start()

        # 2. gRPC Server
        self.grpc_server = None
        self.grpc_port = None
        if HAS_GRPC:
            srv, port = start_node_grpc_server(self, port=0)
            self.grpc_server = srv
            self.grpc_port = port

    def stop(self):
        if self.tcp_server:
            self.tcp_server.stop()
        if self.grpc_server:
            self.grpc_server.stop(grace=None)
        shutil.rmtree(self.base_dir, ignore_errors=True)


def measure_calls(call_fn, iterations=50):
    """Executes call_fn() iterations times and calculates latency quantiles."""
    latencies = []
    t_start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        res = call_fn()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # milliseconds

    total_time = time.perf_counter() - t_start
    latencies.sort()
    calls_per_sec = iterations / max(0.0001, total_time)

    return {
        "iterations": iterations,
        "total_time_sec": round(total_time, 4),
        "calls_per_sec": round(calls_per_sec, 1),
        "avg_ms": round(sum(latencies) / len(latencies), 3),
        "min_ms": round(latencies[0], 3),
        "p50_ms": round(latencies[len(latencies) // 2], 3),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 3),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 3),
        "max_ms": round(latencies[-1], 3),
    }


def run_rpc_benchmark(iterations=50, payload_kb=16):
    """Executes comparative benchmark between TCP-JSON and gRPC."""
    node = MockBenchmarkNode()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    csv_path = os.path.join(logs_dir, "rpc_bench.csv")

    payload_data = "Z" * (payload_kb * 1024)

    try:
        # 1. TCP-JSON Benchmarks
        tcp_ping = measure_calls(
            lambda: rpc.call_addr("127.0.0.1", node.tcp_port, "PING", {}),
            iterations=iterations,
        )
        tcp_put = measure_calls(
            lambda: rpc.call_addr("127.0.0.1", node.tcp_port, "PutBlock", {
                "block_id": "blk_tcp_bench",
                "data": payload_data,
                "base64": False,
                "checksum": "chk_tcp",
            }),
            iterations=iterations,
        )

        # 2. gRPC Benchmarks
        grpc_ping = None
        grpc_put = None
        if HAS_GRPC and node.grpc_port:
            grpc_ping = measure_calls(
                lambda: grpc_call_node(node.id, "127.0.0.1", node.grpc_port, "PING", {}),
                iterations=iterations,
            )
            grpc_put = measure_calls(
                lambda: grpc_call_node(node.id, "127.0.0.1", node.grpc_port, "PutBlock", {
                    "block_id": "blk_grpc_bench",
                    "data": payload_data.encode("utf-8"),
                    "base64": False,
                    "checksum": "chk_grpc",
                }),
                iterations=iterations,
            )

        # 3. Export to CSV
        file_exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "timestamp", "transport", "rpc_method", "iterations",
                    "payload_bytes", "avg_latency_ms", "p50_ms", "p95_ms", "p99_ms", "calls_per_sec"
                ])
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            writer.writerow([now_iso, "TCP-JSON", "PING", iterations, 0, tcp_ping["avg_ms"], tcp_ping["p50_ms"], tcp_ping["p95_ms"], tcp_ping["p99_ms"], tcp_ping["calls_per_sec"]])
            writer.writerow([now_iso, "TCP-JSON", "PutBlock", iterations, len(payload_data), tcp_put["avg_ms"], tcp_put["p50_ms"], tcp_put["p95_ms"], tcp_put["p99_ms"], tcp_put["calls_per_sec"]])

            if grpc_ping:
                writer.writerow([now_iso, "gRPC", "PING", iterations, 0, grpc_ping["avg_ms"], grpc_ping["p50_ms"], grpc_ping["p95_ms"], grpc_ping["p99_ms"], grpc_ping["calls_per_sec"]])
            if grpc_put:
                writer.writerow([now_iso, "gRPC", "PutBlock", iterations, len(payload_data), grpc_put["avg_ms"], grpc_put["p50_ms"], grpc_put["p95_ms"], grpc_put["p99_ms"], grpc_put["calls_per_sec"]])

        return {
            "csv_file": csv_path,
            "iterations": iterations,
            "payload_bytes": len(payload_data),
            "tcp_json": {
                "ping": tcp_ping,
                "put_block": tcp_put,
            },
            "grpc": {
                "supported": HAS_GRPC,
                "ping": grpc_ping,
                "put_block": grpc_put,
            },
        }

    finally:
        node.stop()


if __name__ == "__main__":
    res = run_rpc_benchmark(iterations=30, payload_kb=8)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        print("=================================================================")
        print("       NEXUS-OS RPC Micro-Benchmark: TCP-JSON vs gRPC             ")
        print("=================================================================")
        print(f"Iterations: {res['iterations']} · Payload: {res['payload_bytes']} B · Log: {res['csv_file']}")
        print("-----------------------------------------------------------------")
        print(f"TCP-JSON PING     : {res['tcp_json']['ping']['avg_ms']} ms avg · {res['tcp_json']['ping']['calls_per_sec']} calls/s")
        print(f"TCP-JSON PutBlock : {res['tcp_json']['put_block']['avg_ms']} ms avg · {res['tcp_json']['put_block']['calls_per_sec']} calls/s")
        if res["grpc"]["supported"] and res["grpc"]["ping"]:
            print(f"gRPC PING         : {res['grpc']['ping']['avg_ms']} ms avg · {res['grpc']['ping']['calls_per_sec']} calls/s")
            print(f"gRPC PutBlock     : {res['grpc']['put_block']['avg_ms']} ms avg · {res['grpc']['put_block']['calls_per_sec']} calls/s")
        print("=================================================================")
