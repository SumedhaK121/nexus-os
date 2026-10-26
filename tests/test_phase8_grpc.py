import hashlib
import json
"""NEXUS-OS Phase 8 Unit Tests: gRPC, HTTP/2, IPC Benchmarking & Transport Robustness.
Tests Protobuf message compilation, dual logical clock propagation over gRPC,
NodeService RPC endpoints (Ping, PutBlock, GetBlock, DeleteBlock, RaRequest, RaReply),
message robustness against malformed payloads and size limits, and IPC micro-benchmarks.
OS/DS Concepts: RPC Protocol Layer (gRPC / Protobuf / HTTP/2), Sockets vs Shared Memory (Zero-Copy),
transient failure handling with exponential backoff.
"""

import base64
import os
import shutil
import tempfile
import time
import unittest

from communication import rpc
from communication.grpc_transport import (
    HAS_GRPC,
    get_grpc_metrics,
    grpc_call_node,
    record_rpc_metric,
    start_node_grpc_server,
)
from communication.tcp_client import Conn
from coordinator.main import Coordinator
from distributed_clock.lamport_clock import LamportClock
from distributed_clock.vector_clock import VectorClock
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer
from nodes.ra_participant import RaParticipant
from tools.ipc_demo import benchmark_socket_ipc, run_ipc_benchmark
from tools.rpc_bench import run_rpc_benchmark

if HAS_GRPC:
    from communication.generated import nexus_pb2, nexus_pb2_grpc


class MockGrpcNode:
    """Mock worker node exposing BlockStore and RaParticipant over gRPC."""

    def __init__(self, node_id="test-grpc-node", data_dir=None):
        self.id = node_id
        self.clock = LamportClock()
        self.vc = VectorClock(node_id=node_id)
        self.data_dir = data_dir or tempfile.mkdtemp(prefix="nexus_grpc_node_")
        self.block_store = BlockStore(self.data_dir, self.id)
        self.ra = RaParticipant(node_id=self.id, clock=self.clock)


class TestPhase8Grpc(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_test_p8_")
        self.node = MockGrpcNode(data_dir=self.temp_dir)
        self.server = None
        self.port = None

        if HAS_GRPC:
            srv, port = start_node_grpc_server(self.node, port=0)
            self.server = srv
            self.port = port
            rpc.update_peer_cache({self.node.id: {"host": "127.0.0.1", "port": port, "grpc_port": port}})

    def tearDown(self):
        if self.server:
            self.server.stop(grace=None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_protobuf_stubs_and_envelope_timestamps(self):
        """Tests Protobuf message compilation, field encoding, and logical clock mapping."""
        if not HAS_GRPC:
            self.skipTest("grpcio not installed")

        req = nexus_pb2.PingRequest(
            ts=42,
            vc={"node-1": 3, "node-2": 5},
            client_id="unit-tester",
        )
        self.assertEqual(req.ts, 42)
        self.assertEqual(req.vc["node-1"], 3)
        self.assertEqual(req.client_id, "unit-tester")

        raw_bytes = req.SerializeToString()
        parsed = nexus_pb2.PingRequest()
        parsed.ParseFromString(raw_bytes)
        self.assertEqual(parsed.ts, 42)
        self.assertEqual(parsed.client_id, "unit-tester")

    def test_grpc_ping_pong_and_clocks(self):
        """Tests gRPC Ping call and dual logical clock progression."""
        if not HAS_GRPC:
            self.skipTest("grpcio not installed")

        res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "PING", {"client_id": "client-1"})
        self.assertEqual(res["type"], "PONG")
        self.assertEqual(res["node_id"], self.node.id)
        self.assertGreaterEqual(res["ts"], 1)
        self.assertIn(self.node.id, res["vc"])

    def test_grpc_block_store_crud_lifecycle(self):
        """Tests PutBlock, GetBlock, and DeleteBlock over gRPC HTTP/2 transport."""
        if not HAS_GRPC:
            self.skipTest("grpcio not installed")

        test_bytes = b"Hello gRPC block storage! This is a test chunk."
        blk_id = "blk_test_grpc_0001"

        # 1. PutBlock
        put_res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "PutBlock", {
            "block_id": blk_id,
            "data": test_bytes,
            "checksum": hashlib.sha256(test_bytes).hexdigest(),
            "forward_to": [],
        })
        self.assertEqual(put_res["type"], "OK")
        self.assertEqual(put_res["block_id"], blk_id)

        # 2. GetBlock
        get_res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "GetBlock", {
            "block_id": blk_id,
        })
        self.assertEqual(get_res["type"], "OK")
        self.assertEqual(get_res["block_id"], blk_id)
        self.assertEqual(get_res["data"], test_bytes)

        # 3. DeleteBlock
        del_res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "DeleteBlock", {
            "block_id": blk_id,
        })
        self.assertEqual(del_res["type"], "OK")
        self.assertTrue(del_res["deleted"])

        # 4. GetBlock after delete returns ERROR
        get_after = grpc_call_node(self.node.id, "127.0.0.1", self.port, "GetBlock", {
            "block_id": blk_id,
        })
        self.assertEqual(get_after["type"], "ERROR")

    def test_grpc_ricart_agrawala_messages(self):
        """Tests Ricart-Agrawala RaRequest and RaReply message delivery over gRPC."""
        if not HAS_GRPC:
            self.skipTest("grpcio not installed")

        # Node is initially in RELEASED state -> RaRequest should return RaReply
        req_res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "RaRequest", {
            "req_node": "node-2",
            "ts": 10,
        })
        self.assertEqual(req_res["type"], "RaReply")
        self.assertEqual(req_res["from_node"], self.node.id)

        # Send RaReply to node
        rep_res = grpc_call_node(self.node.id, "127.0.0.1", self.port, "RaReply", {
            "from_node": "node-2",
            "ts": 15,
        })
        self.assertEqual(rep_res["type"], "OK")

    def test_tcp_conn_robustness_malformed_and_size_limits(self):
        """Tests socket Conn layer against malformed JSON payloads and size limits."""
        import io

        class FakeSocket:
            def __init__(self, data_to_read):
                self.rfile = io.BytesIO(data_to_read)
                self.written = []

            def makefile(self, mode, encoding=None):
                return io.TextIOWrapper(self.rfile, encoding=encoding or "utf-8")

            def sendall(self, data):
                self.written.append(data)

            def close(self):
                pass

        # 1. Malformed JSON handling
        bad_sock = FakeSocket(b"THIS IS NOT VALID JSON\n")
        conn = Conn(bad_sock)
        parsed = conn.recv()
        self.assertEqual(parsed["type"], "ERROR")
        self.assertIn("Malformed JSON", parsed["error"])

        # 2. Size limit guard on send
        conn.send({"type": "BIG"}, max_size=10)
        out = json.loads(bad_sock.written[0].decode())
        self.assertEqual(out["type"], "ERROR")
        self.assertIn("exceeds limit", out["error"])

    def test_ipc_demo_and_shared_memory_speedup(self):
        """Tests OSDS Practical 9 IPC benchmark comparing TCP Sockets vs Shared Memory."""
        res = run_ipc_benchmark(iterations=30, payload_size=2048)
        self.assertIn("tcp_socket", res)
        self.assertIn("shared_memory", res)
        self.assertGreater(res["tcp_socket"]["throughput_mb_s"], 0)
        self.assertGreater(res["iterations"], 0)

    def test_rpc_micro_benchmark_execution(self):
        """Tests comparative RPC benchmark and CSV metric generation."""
        res = run_rpc_benchmark(iterations=10, payload_kb=4)
        self.assertIn("csv_file", res)
        self.assertTrue(os.path.exists(res["csv_file"]))
        self.assertIn("tcp_json", res)
        self.assertGreater(res["tcp_json"]["ping"]["calls_per_sec"], 0)

    def test_coordinator_ops_api_handlers(self):
        """Tests RPC_BENCH, IPC_BENCH, and GRPC_METRICS coordinator message handlers."""
        coord = Coordinator(host="127.0.0.1", port=0)

        class FakeCtx:
            node_id = "test-client"

        ctx = FakeCtx()

        # 1. GRPC_METRICS
        gm = coord.handlers["GRPC_METRICS"](coord, ctx, {})
        self.assertEqual(gm["type"], "GRPC_METRICS_RESULT")
        self.assertIn("total_calls", gm)

        # 2. IPC_BENCH
        ib = coord.handlers["IPC_BENCH"](coord, ctx, {"iterations": 20, "payload_bytes": 1024})
        self.assertEqual(ib["type"], "IPC_BENCH_RESULT")
        self.assertIn("tcp_socket", ib)

        # 3. RPC_BENCH
        rb = coord.handlers["RPC_BENCH"](coord, ctx, {"iterations": 10, "payload_kb": 2})
        self.assertEqual(rb["type"], "RPC_BENCH_RESULT")
        self.assertIn("tcp_json", rb)


if __name__ == "__main__":
    unittest.main()
