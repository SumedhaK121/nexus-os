"""NEXUS-OS Worker Node.
Handles registration, real process execution via subprocess & psutil,
block-based distributed storage via BlockStore,
heartbeat telemetry, and local RPC server for inter-node communication.
Concept: Worker node daemon (similar to Kubernetes kubelet / HDFS DataNode / Slurm slurmd).
"""

import os
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication.tcp_client import Conn
from communication import rpc
from distributed_clock.lamport_clock import LamportClock
from jobs import catalog
from nodes.block_store import BlockStore
from nodes.node_server import NodeServer

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class Node:
    def __init__(self, node_id, host="127.0.0.1", port=9000):
        self.id = node_id
        self.host = host
        self.coord_port = port
        self.clock = LamportClock()
        self.running = True
        self.conn = None

        # Data directory for this node
        self.data_dir = os.environ.get("NEXUS_DATA_DIR", os.path.join("storage", self.id))
        os.makedirs(self.data_dir, exist_ok=True)

        # Block storage engine
        self.block_store = BlockStore(self.data_dir, self.id)

        # Process tracking table
        self.local_procs = {}  # pid -> {popen, psutil, start, job_type}
        self.proc_lock = threading.Lock()

        # Start internal RPC server on an ephemeral port
        self.server = NodeServer(host=os.environ.get("NEXUS_BIND", "127.0.0.1"), port=0)
        self._register_rpc_methods()
        self.rpc_port = self.server.start()

        # Node hardware capacities
        self.cpu_slots = int(os.environ.get("NEXUS_CPU_SLOTS", 2))
        self.mem_mb = int(os.environ.get("NEXUS_MEM_MB", 256))
        self.io_slots = int(os.environ.get("NEXUS_IO_SLOTS", 2))

        # Connect to coordinator
        for _ in range(30):
            try:
                self.conn = Conn(socket.create_connection((host, port)))
                break
            except OSError:
                time.sleep(1)
        if not self.conn:
            print(f"[{self.id}] Failed to connect to coordinator at {host}:{port}", flush=True)

    def _register_rpc_methods(self):
        """Register local RPC methods accessible by peers or coordinator."""
        self.server.register_method("PING", lambda p: {"type": "PONG", "node_id": self.id})
        self.server.register_method("PROC_KILL", self._rpc_kill)
        self.server.register_method("PROC_SUSPEND", self._rpc_suspend)
        self.server.register_method("PROC_RESUME", self._rpc_resume)

        # Distributed Block Storage endpoints
        self.server.register_method("PutBlock", self.block_store.put_block)
        self.server.register_method("GetBlock", self.block_store.get_block)
        self.server.register_method("DeleteBlock", self.block_store.delete_block)
        self.server.register_method("ListBlocks", self.block_store.list_blocks)
        self.server.register_method("CorruptBlock", self.block_store.corrupt_block)
        self.server.register_method("CacheStats", self.block_store.cache_stats)
        self.server.register_method("CacheConfig", self.block_store.cache_config)

    def _rpc_kill(self, payload):
        pid = payload.get("pid")
        with self.proc_lock:
            entry = self.local_procs.get(pid)
            if entry and entry["popen"]:
                try:
                    entry["popen"].kill()
                    return {"type": "OK", "killed": pid}
                except Exception as e:
                    return {"type": "ERROR", "error": str(e)}
        return {"type": "ERROR", "error": f"PID {pid} not found on {self.id}"}

    def _rpc_suspend(self, payload):
        pid = payload.get("pid")
        with self.proc_lock:
            entry = self.local_procs.get(pid)
            if entry and entry.get("psutil"):
                try:
                    entry["psutil"].suspend()
                    return {"type": "OK", "suspended": pid}
                except Exception as e:
                    return {"type": "ERROR", "error": str(e)}
        return {"type": "ERROR", "error": f"psutil handle not available for PID {pid}"}

    def _rpc_resume(self, payload):
        pid = payload.get("pid")
        with self.proc_lock:
            entry = self.local_procs.get(pid)
            if entry and entry.get("psutil"):
                try:
                    entry["psutil"].resume()
                    return {"type": "OK", "resumed": pid}
                except Exception as e:
                    return {"type": "ERROR", "error": str(e)}
        return {"type": "ERROR", "error": f"psutil handle not available for PID {pid}"}

    def send(self, msg):
        msg["ts"] = self.clock.tick()
        if self.conn:
            self.conn.send(msg)

    def run(self):
        reg_payload = {
            "type": "REGISTER",
            "node_id": self.id,
            "addr": [self.server.host, self.rpc_port],
            "cpu_slots": self.cpu_slots,
            "mem_mb": self.mem_mb,
            "io_slots": self.io_slots,
        }
        self.send(reg_payload)

        # Heartbeat loop
        threading.Thread(target=self._heartbeat, daemon=True).start()

        # Coordinator message receiver loop
        while self.running and self.conn:
            try:
                msg = self.conn.recv()
            except (OSError, ValueError):
                break
            if msg is None:
                break
            self.clock.update(msg.get("ts", 0))
            mtype = msg.get("type")

            if mtype == "EXEC":
                threading.Thread(target=self._exec, args=(msg,), daemon=True).start()
            elif mtype == "PROC_KILL":
                self._rpc_kill(msg)
            elif mtype == "PROC_SUSPEND":
                self._rpc_suspend(msg)
            elif mtype == "PROC_RESUME":
                self._rpc_resume(msg)
            elif mtype == "REGISTERED":
                self.send({"type": "PEERS"})
            elif mtype == "PEERS":
                rpc.update_peer_cache(msg.get("peers", {}))

    def _exec(self, m):
        pid = m["pid"]
        job_type = m.get("job_type", "sim")
        burst = m.get("burst", 1)
        args = m.get("args", [])
        print(f"[{self.id}] T={self.clock.t} EXEC {pid} ({job_type}, burst={burst})", flush=True)

        if job_type == "sim":
            time.sleep(burst * 0.3)
            self.send({"type": "TASK_DONE", "pid": pid, "node_id": self.id, "burst": burst})
            return

        cmd = catalog.get_command(job_type, args)
        if not cmd:
            time.sleep(burst * 0.3)
            self.send({"type": "TASK_DONE", "pid": pid, "node_id": self.id, "burst": burst})
            return

        self.send({"type": "TASK_STARTED", "pid": pid, "node_id": self.id, "job_type": job_type})
        start_time = time.time()
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ps_proc = None
            if HAS_PSUTIL:
                try:
                    ps_proc = psutil.Process(p.pid)
                except Exception:
                    pass

            with self.proc_lock:
                self.local_procs[pid] = {
                    "popen": p,
                    "psutil": ps_proc,
                    "start": start_time,
                    "job_type": job_type,
                    "burst": burst,
                }

            stdout, stderr = p.communicate()
            end_time = time.time()
            wall_time = end_time - start_time
            cpu_time = wall_time
            if ps_proc:
                try:
                    c_times = ps_proc.cpu_times()
                    cpu_time = c_times.user + c_times.system
                except Exception:
                    pass

            with self.proc_lock:
                self.local_procs.pop(pid, None)

            if p.returncode == 0:
                self.send({
                    "type": "TASK_DONE",
                    "pid": pid,
                    "node_id": self.id,
                    "exit_code": 0,
                    "wall_time": round(wall_time, 3),
                    "cpu_time": round(cpu_time, 3),
                    "burst": burst,
                })
            else:
                err_msg = stderr.decode(errors="replace").strip() if stderr else f"Exit code {p.returncode}"
                self.send({
                    "type": "TASK_FAILED",
                    "pid": pid,
                    "node_id": self.id,
                    "exit_code": p.returncode,
                    "error": err_msg,
                })
        except Exception as e:
            with self.proc_lock:
                self.local_procs.pop(pid, None)
            self.send({
                "type": "TASK_FAILED",
                "pid": pid,
                "node_id": self.id,
                "error": str(e),
            })

    def _heartbeat(self):
        while self.running:
            cpu = 0.0
            mem = 0.0
            if HAS_PSUTIL:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                except Exception:
                    pass
            elif hasattr(os, "getloadavg"):
                cpu = round(os.getloadavg()[0] * 10, 1)

            with self.proc_lock:
                running_count = len(self.local_procs)

            try:
                self.send({
                    "type": "HEARTBEAT",
                    "node_id": self.id,
                    "cpu": cpu,
                    "mem": mem,
                    "load": running_count,
                })
            except OSError:
                return
            time.sleep(2)


if __name__ == "__main__":
    node_id = sys.argv[1] if len(sys.argv) > 1 else "node-1"
    coord_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
    Node(node_id, port=coord_port).run()
