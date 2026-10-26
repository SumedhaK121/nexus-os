"""NEXUS-OS Distributed Lock Manager with Ephemeral Leases.
Provides named mutual exclusion locks (e.g., 'file:/report.txt', 'table:users', 'node:gpu')
with time-bounded leases, automated renewal, deadlock wait-for-graph integration,
and automatic failover release upon holder node disconnection.
Concept: Distributed lock service with leases (Chubby, ZooKeeper ephemeral znode, etcd lease).
"""

import threading
import time


class DistributedLockManager:
    """Cluster-wide distributed lock manager with leases and deadlock detection integration."""

    def __init__(self, coord=None, default_lease=10.0):
        self.coord = coord
        self.default_lease = float(default_lease)
        self.locks = {}  # lock_name -> dict(holder, lease_expiry, lease_sec, waiters)
        self.lock = threading.RLock()

    def _purge_expired(self):
        """Releases locks whose leases have expired (failure of holder to heartbeat/renew)."""
        now = time.time()
        for name, info in list(self.locks.items()):
            if now > info["lease_expiry"]:
                expired_holder = info["holder"]
                waiters = info["waiters"]
                if waiters:
                    next_holder = waiters.pop(0)
                    info["holder"] = next_holder
                    info["lease_expiry"] = now + info["lease_sec"]
                    if self.coord:
                        self.coord.log(
                            "lock_mgr",
                            f"Lock '{name}' lease expired for {expired_holder}; granted to waiter {next_holder}",
                        )
                else:
                    del self.locks[name]
                    if self.coord:
                        self.coord.log(
                            "lock_mgr",
                            f"Lock '{name}' lease expired for {expired_holder}; lock released",
                        )

    def acquire(self, lock_name, client_id, lease_sec=None):
        """Acquires a named lock with lease duration.
        Returns LOCK_OK if granted, or LOCK_DENIED if held by another client.
        """
        lease_sec = float(lease_sec if lease_sec is not None else self.default_lease)
        now = time.time()

        with self.lock:
            self._purge_expired()

            if lock_name not in self.locks:
                # Grant lock immediately
                self.locks[lock_name] = {
                    "holder": str(client_id),
                    "lease_expiry": now + lease_sec,
                    "lease_sec": lease_sec,
                    "waiters": [],
                }
                if self.coord:
                    self.coord.log("lock_mgr", f"Lock '{lock_name}' acquired by {client_id} (lease={lease_sec}s)")
                return {
                    "type": "LOCK_OK",
                    "lock": lock_name,
                    "holder": str(client_id),
                    "lease_sec": lease_sec,
                    "expiry": round(now + lease_sec, 2),
                }

            info = self.locks[lock_name]
            # If already held by same client: renew lease
            if info["holder"] == str(client_id):
                info["lease_expiry"] = now + lease_sec
                return {
                    "type": "LOCK_OK",
                    "lock": lock_name,
                    "holder": str(client_id),
                    "renewed": True,
                    "expiry": round(now + lease_sec, 2),
                }

            # Lock is held by another client
            if str(client_id) not in info["waiters"]:
                info["waiters"].append(str(client_id))

            # Integrate wait dependency into wait-for graph if available
            if self.coord and hasattr(self.coord, "res_mgr"):
                try:
                    self.coord.res_mgr.wait_for_graph.setdefault(str(client_id), set()).add(info["holder"])
                except Exception:
                    pass

            return {
                "type": "LOCK_DENIED",
                "lock": lock_name,
                "holder": info["holder"],
                "remaining_lease": round(max(0.0, info["lease_expiry"] - now), 2),
                "waiters": list(info["waiters"]),
            }

    def release(self, lock_name, client_id):
        """Releases a named lock. If waiters exist, passes lock to next waiter in FIFO queue."""
        now = time.time()
        with self.lock:
            self._purge_expired()
            if lock_name not in self.locks:
                return {"type": "ERROR", "error": f"Lock '{lock_name}' not held"}

            info = self.locks[lock_name]
            if info["holder"] != str(client_id):
                return {"type": "ERROR", "error": f"Client '{client_id}' is not the holder of '{lock_name}'"}

            # Remove wait dependency from wait-for graph
            if self.coord and hasattr(self.coord, "res_mgr"):
                try:
                    self.coord.res_mgr.wait_for_graph.get(str(client_id), set()).discard(info["holder"])
                except Exception:
                    pass

            waiters = info["waiters"]
            if waiters:
                next_holder = waiters.pop(0)
                info["holder"] = next_holder
                info["lease_expiry"] = now + info["lease_sec"]
                if self.coord:
                    self.coord.log("lock_mgr", f"Lock '{lock_name}' released by {client_id}; granted to {next_holder}")
                return {
                    "type": "LOCK_OK",
                    "lock": lock_name,
                    "released_by": str(client_id),
                    "granted_to": next_holder,
                    "expiry": round(now + info["lease_sec"], 2),
                }
            else:
                del self.locks[lock_name]
                if self.coord:
                    self.coord.log("lock_mgr", f"Lock '{lock_name}' released by {client_id}")
                return {"type": "LOCK_OK", "lock": lock_name, "released_by": str(client_id)}

    def renew(self, lock_name, client_id, lease_sec=None):
        """Renews an active lock lease (heartbeat)."""
        lease_sec = float(lease_sec if lease_sec is not None else self.default_lease)
        now = time.time()
        with self.lock:
            self._purge_expired()
            if lock_name not in self.locks:
                return {"type": "ERROR", "error": f"Lock '{lock_name}' not held"}
            info = self.locks[lock_name]
            if info["holder"] != str(client_id):
                return {"type": "ERROR", "error": f"Client '{client_id}' is not holder of '{lock_name}'"}

            info["lease_expiry"] = now + lease_sec
            return {"type": "LOCK_OK", "lock": lock_name, "renewed": True, "expiry": round(now + lease_sec, 2)}

    def on_node_down(self, node_id):
        """Automatically releases locks held by failed node and clears its pending waits."""
        node_str = str(node_id)
        released_locks = []
        now = time.time()

        with self.lock:
            for name, info in list(self.locks.items()):
                # Remove node from waiters
                if node_str in info["waiters"]:
                    info["waiters"].remove(node_str)

                # If node was the active holder, failover immediately
                if info["holder"] == node_str:
                    waiters = info["waiters"]
                    if waiters:
                        next_holder = waiters.pop(0)
                        info["holder"] = next_holder
                        info["lease_expiry"] = now + info["lease_sec"]
                        released_locks.append((name, next_holder))
                    else:
                        del self.locks[name]
                        released_locks.append((name, None))

        if released_locks and self.coord:
            self.coord.log(
                "lock_mgr",
                f"Auto-released {len(released_locks)} lock(s) held by failed node {node_id}: {released_locks}",
            )
        return released_locks

    def get_status(self):
        """Returns snapshot of all active locks, holders, lease times, and waiters."""
        now = time.time()
        with self.lock:
            self._purge_expired()
            res = {}
            for name, info in self.locks.items():
                res[name] = {
                    "holder": info["holder"],
                    "remaining_lease": round(max(0.0, info["lease_expiry"] - now), 2),
                    "lease_sec": info["lease_sec"],
                    "waiters": list(info["waiters"]),
                }
            return res
