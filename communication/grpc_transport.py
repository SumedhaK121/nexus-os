"""NEXUS-OS gRPC Transport Layer & IPC Telemetry.
Implements Coordinator and Node gRPC services, client stubs with deadline and retry backoff,
Lamport and Vector Clock propagation interceptors, and network message counters into coord.net.
Concept: RPC Protocol Layer (gRPC / HTTP/2 / Protobuf) vs TCP-JSON IPC (Kubernetes, etcd, Envoy).
"""

import base64
import json
import os
import sys
import threading
import time
from concurrent import futures

try:
    import grpc
    from communication.generated import nexus_pb2, nexus_pb2_grpc
    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False

# Global gRPC telemetry metrics (fed into coordinator Network panel)
GRPC_METRICS = {
    "total_calls": 0,
    "total_bytes": 0,
    "by_method": {},
}
_METRICS_LOCK = threading.Lock()


def record_rpc_metric(method, bytes_sent, bytes_recv, duration_sec, error=False):
    """Records RPC latency, throughput, and error metrics."""
    with _METRICS_LOCK:
        GRPC_METRICS["total_calls"] += 1
        GRPC_METRICS["total_bytes"] += (bytes_sent + bytes_recv)
        m = GRPC_METRICS["by_method"].setdefault(method, {
            "calls": 0,
            "bytes_sent": 0,
            "bytes_recv": 0,
            "total_latency": 0.0,
            "errors": 0,
        })
        m["calls"] += 1
        m["bytes_sent"] += bytes_sent
        m["bytes_recv"] += bytes_recv
        m["total_latency"] += duration_sec
        if error:
            m["errors"] += 1


def get_grpc_metrics():
    with _METRICS_LOCK:
        res = {
            "total_calls": GRPC_METRICS["total_calls"],
            "total_bytes": GRPC_METRICS["total_bytes"],
            "methods": {},
        }
        for k, v in GRPC_METRICS["by_method"].items():
            calls = v["calls"] or 1
            res["methods"][k] = {
                "calls": v["calls"],
                "bytes": v["bytes_sent"] + v["bytes_recv"],
                "avg_latency_ms": round((v["total_latency"] / calls) * 1000, 2),
                "errors": v["errors"],
            }
        return res


if HAS_GRPC:
    class NodeServiceServicer(nexus_pb2_grpc.NodeServiceServicer):
        """Dispatches incoming gRPC calls to worker node subsystem engines."""

        def __init__(self, node):
            self.node = node

        def Ping(self, request, context):
            t0 = time.time()
            reply = nexus_pb2.PingReply(
                ts=self.node.clock.tick() if hasattr(self.node, "clock") else 1,
                vc=self.node.vc.tick() if hasattr(self.node, "vc") else {},
                type="PONG",
                node_id=self.node.id,
            )
            record_rpc_metric("Ping", request.ByteSize(), reply.ByteSize(), time.time() - t0)
            return reply

        def PutBlock(self, request, context):
            t0 = time.time()
            # Forward to BlockStore
            raw_data = request.data
            block_id = request.block_id
            payload = {
                "block_id": block_id,
                "data": base64.b64encode(raw_data).decode("ascii"),
                "base64": True,
                "checksum": request.checksum,
                "forward_to": list(request.forward_to),
            }
            res = self.node.block_store.put_block(payload)
            reply = nexus_pb2.PutBlockReply(
                ts=self.node.clock.tick(),
                vc=self.node.vc.tick(),
                type=res.get("type", "OK"),
                block_id=block_id,
                status=res.get("status", "HEALTHY"),
                error=res.get("error", ""),
            )
            record_rpc_metric("PutBlock", request.ByteSize(), reply.ByteSize(), time.time() - t0, res.get("type") == "ERROR")
            return reply

        def GetBlock(self, request, context):
            t0 = time.time()
            res = self.node.block_store.get_block({"block_id": request.block_id})
            if res.get("type") == "ERROR":
                reply = nexus_pb2.GetBlockReply(
                    ts=self.node.clock.tick(),
                    vc=self.node.vc.tick(),
                    type="ERROR",
                    block_id=request.block_id,
                    data=b"",
                    checksum="",
                    error=res.get("error", "Not found"),
                )
            else:
                data_val = res.get("data", "")
                if res.get("base64"):
                    raw_bytes = base64.b64decode(data_val)
                elif isinstance(data_val, str):
                    raw_bytes = data_val.encode("utf-8")
                else:
                    raw_bytes = bytes(data_val)
                reply = nexus_pb2.GetBlockReply(
                    ts=self.node.clock.tick(),
                    vc=self.node.vc.tick(),
                    type="OK",
                    block_id=request.block_id,
                    data=raw_bytes,
                    checksum=res.get("checksum", ""),
                    error="",
                )
            record_rpc_metric("GetBlock", request.ByteSize(), reply.ByteSize(), time.time() - t0, res.get("type") == "ERROR")
            return reply

        def DeleteBlock(self, request, context):
            t0 = time.time()
            res = self.node.block_store.delete_block({"block_id": request.block_id})
            reply = nexus_pb2.DeleteBlockReply(
                ts=self.node.clock.tick(),
                vc=self.node.vc.tick(),
                type="OK",
                block_id=request.block_id,
                deleted=res.get("deleted", res.get("type") == "OK"),
                error=res.get("error", ""),
            )
            record_rpc_metric("DeleteBlock", request.ByteSize(), reply.ByteSize(), time.time() - t0)
            return reply

        def RaRequest(self, request, context):
            t0 = time.time()
            res = self.node.ra.handle_request({"req_node": request.req_node, "ts": request.req_ts})
            reply = nexus_pb2.RaReplyMessage(
                ts=self.node.clock.tick(),
                vc=self.node.vc.tick(),
                from_node=self.node.id,
                deferred=(res.get("type") == "RaDeferred"),
            )
            record_rpc_metric("RaRequest", request.ByteSize(), reply.ByteSize(), time.time() - t0)
            return reply

        def RaReply(self, request, context):
            t0 = time.time()
            self.node.ra.handle_reply({"from_node": request.from_node, "ts": request.ts})
            reply = nexus_pb2.RaAck(
                ts=self.node.clock.tick(),
                vc=self.node.vc.tick(),
                ok=True,
            )
            record_rpc_metric("RaReply", request.ByteSize(), reply.ByteSize(), time.time() - t0)
            return reply

        def SyncPull(self, request, context):
            t0 = time.time()
            content = ""
            dest = os.path.join(self.node.sync_agent.sync_dir, request.path.lstrip("/sync/").lstrip("/"))
            if os.path.exists(dest):
                with open(dest, "rb") as f:
                    content = f.read()
            reply = nexus_pb2.SyncPullReply(
                ts=self.node.clock.tick(),
                vc=self.node.vc.tick(),
                type="OK",
                path=request.path,
                content=content if isinstance(content, bytes) else content.encode("utf-8"),
                version=1,
            )
            record_rpc_metric("SyncPull", request.ByteSize(), reply.ByteSize(), time.time() - t0)
            return reply


def start_node_grpc_server(node, port=0):
    """Starts a gRPC server for a worker node."""
    if not HAS_GRPC:
        return None
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    servicer = NodeServiceServicer(node)
    nexus_pb2_grpc.add_NodeServiceServicer_to_server(servicer, server)
    bound_port = server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    return server, bound_port


def grpc_call_node(node_id, host, port, method, payload=None, timeout=5.0, retries=2):
    """Invokes a gRPC call on a target node with retries and exponential backoff.
    Converts between dict representations and protobuf objects.
    """
    if not HAS_GRPC:
        return {"type": "ERROR", "error": "grpcio not installed"}

    payload = payload or {}
    channel_addr = f"{host}:{port}"
    options = [
        ("grpc.max_send_message_length", 32 * 1024 * 1024),
        ("grpc.max_receive_message_length", 32 * 1024 * 1024),
    ]

    last_err = None
    for attempt in range(retries + 1):
        try:
            with grpc.insecure_channel(channel_addr, options=options) as channel:
                stub = nexus_pb2_grpc.NodeServiceStub(channel)
                start_t = time.time()

                if method == "PING":
                    req = nexus_pb2.PingRequest(client_id=payload.get("client_id", "caller"))
                    rep = stub.Ping(req, timeout=timeout)
                    return {"type": rep.type, "node_id": rep.node_id, "ts": rep.ts, "vc": dict(rep.vc)}

                elif method == "PutBlock":
                    raw_data = payload.get("data", b"")
                    if payload.get("base64") and isinstance(raw_data, str):
                        raw_data = base64.b64decode(raw_data)
                    elif isinstance(raw_data, str):
                        raw_data = raw_data.encode("latin1")

                    req = nexus_pb2.PutBlockRequest(
                        block_id=payload["block_id"],
                        data=bytes(raw_data),
                        checksum=payload.get("checksum", ""),
                        forward_to=payload.get("forward_to", []),
                    )
                    rep = stub.PutBlock(req, timeout=timeout)
                    return {"type": rep.type, "block_id": rep.block_id, "status": rep.status, "error": rep.error}

                elif method == "GetBlock":
                    req = nexus_pb2.GetBlockRequest(block_id=payload["block_id"])
                    rep = stub.GetBlock(req, timeout=timeout)
                    if rep.type == "ERROR":
                        return {"type": "ERROR", "error": rep.error}
                    data_ret = rep.data
                    if payload.get("base64"):
                        data_ret = base64.b64encode(rep.data).decode("ascii")
                    return {"type": "OK", "block_id": rep.block_id, "data": data_ret, "checksum": rep.checksum}

                elif method == "DeleteBlock":
                    req = nexus_pb2.DeleteBlockRequest(block_id=payload["block_id"])
                    rep = stub.DeleteBlock(req, timeout=timeout)
                    return {"type": "OK", "block_id": rep.block_id, "deleted": rep.deleted, "error": rep.error}

                elif method == "RaRequest":
                    req = nexus_pb2.RaRequestMessage(
                        req_node=payload["req_node"],
                        req_ts=payload["ts"],
                    )
                    rep = stub.RaRequest(req, timeout=timeout)
                    return {"type": "RaDeferred" if rep.deferred else "RaReply", "from_node": rep.from_node}

                elif method == "RaReply":
                    req = nexus_pb2.RaReplyMessage(
                        from_node=payload["from_node"],
                        ts=payload.get("ts", 0),
                    )
                    rep = stub.RaReply(req, timeout=timeout)
                    return {"type": "OK", "ok": rep.ok}

                elif method == "SyncPull":
                    req = nexus_pb2.SyncPullRequest(path=payload.get("path", ""))
                    rep = stub.SyncPull(req, timeout=timeout)
                    return {"type": rep.type, "path": rep.path, "content": rep.content.decode("utf-8", errors="replace")}

                else:
                    return {"type": "ERROR", "error": f"Unsupported gRPC method {method}"}

        except grpc.RpcError as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.05 * (2 ** attempt))  # Exponential backoff
            else:
                return {"type": "ERROR", "error": f"gRPC call to {channel_addr} failed: {e.code()} - {e.details()}"}

    return {"type": "ERROR", "error": f"gRPC call failed: {last_err}"}
