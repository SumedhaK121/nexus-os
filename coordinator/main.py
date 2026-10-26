import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""NEXUS-OS Coordinator. Teammates plug in modules with @coord.handler("MSG_TYPE").
Handler signature: fn(coord, ctx, msg) -> reply dict (or None). ctx.node_id is set after REGISTER."""
import socket, threading, time, sys
from communication.tcp_client import Conn
from distributed_clock.lamport_clock import LamportClock
from coordinator.scheduler import scheduler_manager as scheduler
from coordinator.scheduler.node_selector import pick_node
from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.file_manager.file_manager import FileManager
from coordinator.api.handlers import install
from coordinator.node_manager import node_manager
from coordinator.process_manager import process_manager
from coordinator.resource_manager import resource_manager

class Ctx:
    def __init__(self, conn): self.conn, self.node_id = conn, None

class Coordinator:
    def __init__(self, host="127.0.0.1", port=9000):
        self.host, self.port = host, port
        self.clock = LamportClock()
        self.nodes = {}            # node_id -> {conn, last_seen, cpu, tasks_done}
        self.tasks = {}            # task_id -> {...}
        self.events = []           # Lamport-stamped event log (Module 7)
        self.lock = threading.Lock()
        self.handlers = {}
        self.banker = None
        self.files, self.net = FileManager(), {}
        install(self)
        self._register_defaults()

    # ---------- plugin API ----------
    def handler(self, mtype):
        def deco(fn): self.handlers[mtype] = fn; return fn
        return deco

    def log(self, who, what):
        t = self.clock.tick()
        with self.lock: self.events.append({"T": t, "who": who, "event": what})
        print(f"[T={t:>3}] {who}: {what}", flush=True)

    # ---------- server ----------
    def serve(self):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port)); s.listen(); self.server = s
        print(f"Coordinator listening on {self.host}:{self.port}", flush=True)
        threading.Thread(target=self._monitor, daemon=True).start()
        while True:
            try: c, _ = s.accept()
            except OSError: return
            threading.Thread(target=self._client, args=(Conn(c),), daemon=True).start()

    def _client(self, conn):
        ctx = Ctx(conn)
        try:
            while (msg := conn.recv()) is not None:
                self.clock.update(msg.get("ts", 0))
                if msg.get("type") != "STATUS": self.net[msg.get("type", "?")] = self.net.get(msg.get("type", "?"), 0) + 1
                fn = self.handlers.get(msg.get("type"))
                reply = fn(self, ctx, msg) if fn else {"type": "ERROR", "error": "unknown type"}
                if reply is not None:
                    reply["ts"] = self.clock.tick(); reply["req_id"] = msg.get("req_id")
                    conn.send(reply)
        except (OSError, ValueError): pass
        finally:
            if ctx.node_id:
                with self.lock: self.nodes.pop(ctx.node_id, None)
                self.log("coordinator", f"{ctx.node_id} disconnected")
            conn.close()

    def _monitor(self):  # failure detection: no heartbeat for 6s -> OFFLINE
        while True:
            time.sleep(2)
            with self.lock:
                for nid, n in list(self.nodes.items()):
                    if time.time() - n["last_seen"] > 6 and n["status"] == "ONLINE":
                        n["status"] = "OFFLINE"; print(f"!! {nid} marked OFFLINE", flush=True)

    # ---------- default handlers ----------
    def _register_defaults(self):
        @self.handler("REGISTER")
        def _reg(c, ctx, m):
            ctx.node_id = m["node_id"]
            with c.lock:
                c.nodes[ctx.node_id] = {"conn": ctx.conn, "last_seen": time.time(),
                                        "cpu": 0, "load": 0, "done": 0, "status": "ONLINE"}
            c.log("coordinator", f"{ctx.node_id} registered")
            return {"type": "REGISTERED"}

        @self.handler("HEARTBEAT")
        def _hb(c, ctx, m):
            with c.lock:
                n = c.nodes.get(ctx.node_id)
                if n: n.update(last_seen=time.time(), cpu=m.get("cpu", 0), status="ONLINE")
            return None

        @self.handler("SUBMIT")   # Module 1: pick algorithm, order processes, dispatch to nodes
        def _submit(c, ctx, m):
            procs, algo = m["processes"], m.get("algo", "fcfs")
            result = scheduler.run(algo, procs, m.get("quantum", 2))
            by_pid = {p["pid"]: p for p in procs}
            order = []
            for pid, _, _ in result["gantt"]:
                if pid not in order: order.append(pid)
            c.log("scheduler", f"{result['algo']} order: {order}")
            with c.lock:
                online = node_manager.online(c.nodes)
            if not online: return {"type": "ERROR", "error": "no nodes online"}
            assigned = {}
            for pid in order:                       # least-loaded node first
                with c.lock: nid = pick_node(c.nodes, online); c.nodes[nid]["load"] += by_pid[pid]["burst"]
                c.tasks[pid] = {"node": nid, "state": "Running", "burst": by_pid[pid]["burst"]}
                c.nodes[nid]["conn"].send({"type": "EXEC", "pid": pid, "burst": by_pid[pid]["burst"], "ts": c.clock.tick()})
                c.log("scheduler", f"{pid} -> {nid}"); assigned[pid] = nid
            return {"type": "SUBMITTED", "assigned": assigned, "metrics": result["avg"], "gantt": result["gantt"]}

        @self.handler("TASK_DONE")
        def _done(c, ctx, m):
            with c.lock:
                c.tasks[m["pid"]]["state"] = "Completed"
                c.nodes[ctx.node_id]["load"] -= c.tasks[m["pid"]]["burst"]; c.nodes[ctx.node_id]["done"] += 1
            c.log(ctx.node_id, f"completed {m['pid']}")
            return None

        @self.handler("COMPARE")  # Module 1 demo: FCFS vs RR vs Priority
        def _cmp(c, ctx, m):
            return {"type": "COMPARED", "results": [{"algo": r["algo"], **r["avg"], "gantt": r["gantt"]} for r in scheduler.compare(m["processes"], m.get("quantum", 2))]}

        @self.handler("BANKER_INIT")  # Module 2
        def _bi(c, ctx, m):
            c.banker = Banker(m["available"], m["max"], m["alloc"])
            return {"type": "OK", "safe": c.banker.is_safe()}

        @self.handler("BANKER_REQUEST")
        def _br(c, ctx, m):
            r = c.banker.request(m["pid"], m["request"]); c.log("banker", f"{m['pid']} {m['request']} -> {r}")
            return {"type": "BANKER_RESULT", **r}

        @self.handler("STATUS")   # Module 8 dashboard data
        def _status(c, ctx, m):
            with c.lock:
                return {"type": "STATUS", "clock": c.clock.t,
                        "nodes": {k: {x: v[x] for x in ("status", "cpu", "load", "done", "last_seen")} for k, v in c.nodes.items()},
                        "tasks": dict(c.tasks), "events": c.events[-60:], "files": c.files.listing(), "util": resource_manager.utilization(c.banker), "procs": process_manager.summary(c.tasks), "safe": (c.banker.is_safe()[0] if c.banker else None), "net": dict(c.net), "cache": c.files.cache.stats(), "replicas": c.files.rep.placement, "banker": ({"available": c.banker.available, "max": c.banker.max, "alloc": c.banker.alloc} if c.banker else None)}

if __name__ == "__main__":
    Coordinator(host=os.environ.get("NEXUS_BIND", "127.0.0.1"), port=int(sys.argv[1]) if len(sys.argv) > 1 else 9000).serve()
