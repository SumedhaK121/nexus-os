# Case Study 4: Google Chubby Distributed Lock Service & NEXUS-OS Locks

## 1. Industrial Background: Google Chubby
**Google Chubby** (Burrows, 2006) is a coarse-grained distributed lock service used across Google infrastructure (including Google File System, Bigtable, and MapReduce) to provide coarse-grained synchronization and reliable leader election.

Chubby design principles:
- **Coarse-Grained Locking**: Designed for coarse-grained locks (held for hours or days, e.g. primary server election) rather than fine-grained locks held for milliseconds.
- **Lock Leases with Automatic Expiration**: Locks are held under time-bounded leases. If a primary fails or gets disconnected, its lease expires, and the lock is automatically released to prevent deadlocks.
- **Explicit Waiter Queues**: Clients contending for a lock join a FIFO waiting queue and are granted the lock in arrival order.

---

## 2. Theoretical OS/DS Concepts Implemented
- **Distributed Mutual Exclusion**: Guaranteeing that at most one node is executing within the critical section at any time:
  $$\forall i \ne j, \quad \neg (\text{InCS}_i \land \text{InCS}_j)$$
- **Lease Timers & Failure Independence**: Bounding the maximum time an inaccessible lock can block cluster progress.
- **Ricart-Agrawala Algorithm**: Peer-to-peer timestamp-ordered mutual exclusion with $2(N-1)$ message complexity and deferred reply queues.
- **Deadlock Registration**: Coupling lock waiting dependencies with the cluster Wait-For Graph (WFG) to detect circular waits involving distributed locks.

---

## 3. How NEXUS-OS Implements the Chubby Model
In NEXUS-OS:
1. **Distributed Lock Manager (`coordinator/synchronization/lock_manager.py`)**:
   - Manages named locks (`file:/shared/report.txt`, `res:/gpu/0`).
   - Issues time-bounded leases (e.g. 10–30 seconds) with lease renewal support (`LOCK_RENEW`).
   - Maintains explicit FIFO waiter queues for contested resources.
2. **Automated Failover on Node Disconnect**:
   - Subscribed to `on_node_down` in `NodeManager`.
   - When a node is marked `OFFLINE`, all locks held by that node are automatically revoked and granted to the next queued waiter.
3. **Peer-to-Peer Ricart-Agrawala (`nodes/ra_participant.py`)**:
   - Implements the completely decentralized, leaderless Ricart-Agrawala protocol.
   - Nodes transition across `RELEASED`, `WANTED`, and `HELD` states.
   - Uses Lamport logical timestamps to break ties: $(T_i, i) < (T_j, j)$ if $T_i < T_j$ or ($T_i = T_j$ and $i < j$).
   - Defers replies to lower-priority requests until critical section exit, achieving exact $2(N-1)$ message complexity.
