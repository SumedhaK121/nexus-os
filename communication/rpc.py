"""NEXUS-OS Unified Remote Procedure Call (RPC) Abstraction.
Routes node-to-node and coordinator-to-node calls over TCP-JSON (or gRPC in Phase 8).
Concept: Remote Procedure Call (RPC) layer abstracting transport semantics (similar to gRPC / CORBA).
"""

import json
import os
import socket
import threading
import time
from communication.tcp_client import Conn

# Global peer cache: node_id -> {"host": str, "port": int}
_PEER_CACHE = {}
_PEER_LOCK = threading.Lock()


def update_peer_cache(peers_dict):
    """Update known peer addresses."""
    with _PEER_LOCK:
        _PEER_CACHE.update(peers_dict)


def get_peer_addr(node_id):
    with _PEER_LOCK:
        info = _PEER_CACHE.get(node_id)
        if info:
            return info.get("host", "127.0.0.1"), info.get("port")
    return None


def call_addr(host, port, method, payload=None, timeout=5.0):
    """Directly invokes an RPC method on target host:port over TCP-JSON."""
    payload = payload if payload is not None else {}
    req = {
        "method": method,
        "payload": payload,
        "req_id": f"rpc-{time.time()}-{os.getpid()}",
    }
    # Pass along timestamps if present in payload
    if "ts" in payload:
        req["ts"] = payload["ts"]
    if "vc" in payload:
        req["vc"] = payload["vc"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        conn = Conn(sock)
        conn.send(req)
        reply = conn.recv()
        conn.close()
        return reply or {"type": "ERROR", "error": "Empty reply from node"}
    except Exception as e:
        return {"type": "ERROR", "error": f"RPC call to {host}:{port} failed: {e}"}
    finally:
        try:
            sock.close()
        except OSError:
            pass


def call_node(node_id, method, payload=None, timeout=5.0, peers=None):
    """Invoke an RPC method on node_id using the configured transport."""
    transport = os.environ.get("NEXUS_TRANSPORT", "tcp").lower()
    if peers:
        update_peer_cache(peers)

    addr = get_peer_addr(node_id)
    if not addr or not addr[1]:
        return {"type": "ERROR", "error": f"Address for {node_id} not found in peer cache"}

    host, port = addr
    # If gRPC is enabled in Phase 8 and available, branch here
    if transport == "grpc":
        try:
            from communication.grpc_transport import grpc_call_node
            return grpc_call_node(node_id, host, port, method, payload, timeout)
        except ImportError:
            pass  # fallback to tcp

    return call_addr(host, port, method, payload, timeout)
