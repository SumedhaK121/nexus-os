# NEXUS-OS: Operating Systems & Distributed Systems (OSDS) Practicals Map

This document explicitly maps the laboratory practicals of standard university Operating Systems and Distributed Systems curricula (e.g. Units I through V, Practicals 1 through 12) directly to NEXUS-OS source code, interactive web dashboards, and test suites.

---

## Curriculum Alignment Matrix

| Practical # | OSDS Syllabus Topic / Practical Title | NEXUS-OS Module & Script | Demonstration & Verification Command | Dashboard View |
| :--- | :--- | :--- | :--- | :--- |
| **Practical 1** | **CPU Scheduling Algorithms** (FCFS, SJF, Priority, Round Robin) | `coordinator/scheduler/scheduler_manager.py`, `coordinator/scheduler/` | `python -m unittest tests/test_phase1_scheduling.py` | **Process Manager** (`#proc`) — Submit processes, live Gantt chart, metrics table |
| **Practical 2** | **Preemptive CPU Scheduling & Starvation** (SRTF, Priority with Aging) | `coordinator/scheduler/srtf.py`, `coordinator/scheduler/priority_aging.py` | `python demo/workload.py`<br>`python -m unittest tests/test_phase1_scheduling.py` | **Process Manager** (`#proc`) — Compare All algorithms, Aging demonstration |
| **Practical 3** | **Deadlock Avoidance** (Dijkstra's Banker's Algorithm) | `coordinator/deadlock/bankers_algorithm.py`, `coordinator/resource_manager/` | `python -c "from coordinator.deadlock.bankers_algorithm import Banker; b=Banker([3,3,2], {'P0':[7,5,3],'P1':[3,2,2],'P2':[9,0,2],'P3':[2,2,2],'P4':[4,3,3]}, {'P0':[0,1,0],'P1':[2,0,0],'P2':[3,0,2],'P3':[2,1,1],'P4':[0,0,2]}); print(b.is_safe())"` | **Resource Manager** (`#res`) — Live Allocation/Max/Need matrix, Safe Sequence |
| **Practical 4** | **Deadlock Detection & Recovery** (Wait-For Graph Cycle DFS) | `coordinator/deadlock/deadlock_detector.py`, `demo/deadlock_scene.py` | `python demo/deadlock_scene.py`<br>`python -m unittest tests/test_phase2_deadlock.py` | **Deadlock Detection** (`#dead`) — Directed WFG graph, cycle highlight, victim kill |
| **Practical 5** | **Virtual Memory & Page Replacement** (FIFO, LRU, Optimal & Belady's Anomaly) | `coordinator/file_manager/page_replacement.py`, `nodes/node_cache.py` | `python -m unittest tests/test_phase4_cache_sync.py` | **Cache & Paging** (`#cache`) — Reference string simulator, Belady's Anomaly test |
| **Practical 6** | **Classical Process Synchronization** (Readers-Writers Problem, Producer-Consumer) | `coordinator/synchronization/readers_writers.py`, `coordinator/synchronization/primitives.py` | `python -m unittest tests/test_phase4_cache_sync.py` | **Synchronization** (`#sync`) — Writer starvation demo, BoundedQueue high-watermark |
| **Practical 7** | **Dining Philosophers Problem** (Deadlock vs Resource Ordering) | `demo/philosophers.py` | `python demo/philosophers.py naive`<br>`python demo/philosophers.py hierarchical` | **Synchronization** (`#sync`) — Naive symmetric circular wait vs Dijkstra ordering |
| **Practical 8** | **Race Conditions & Critical Section Mutual Exclusion** | `coordinator/synchronization/primitives.py` | `python -c "from coordinator.synchronization.primitives import file_store_race_demo; print(file_store_race_demo(10, 100))"` | **Synchronization** (`#sync`) — Storage race with lost updates vs Mutex |
| **Practical 9** | **Inter-Process Communication (IPC)** (Sockets vs Shared Memory) | `tools/ipc_demo.py` | `python tools/ipc_demo.py --iterations 50 --size 4096` | **Network / IPC** (`#netp`) — Micro-benchmark table, zero-copy shared memory |
| **Practical 10** | **Logical Clocks & Causal Event Ordering** (Lamport & Vector Clocks) | `distributed_clock/lamport_clock.py`, `distributed_clock/vector_clock.py`, `demo/vector_clock_scene.py` | `python demo/vector_clock_scene.py` | **Lamport & Events** (`#ev`) — Dual-stamped event log, detect concurrent edits |
| **Practical 11** | **Distributed Mutual Exclusion & RPC** (Ricart-Agrawala & gRPC) | `nodes/ra_participant.py`, `communication/grpc_transport.py`, `tools/rpc_bench.py` | `python tools/rpc_bench.py`<br>`python -m unittest tests/test_phase6_locks.py` | **Synchronization** (`#sync`) — Real 2(N-1) RA trace, **Network/IPC** (`#netp`) |
| **Practical 12** | **Distributed File Systems, Replication & Fault Tolerance** | `coordinator/file_manager/dfs_manager.py`, `nodes/block_store.py`, `tools/chaos.py` | `python demo/lab_day.py`<br>`python -m unittest tests/test_integration.py` | **Distributed Files** (`#files`) — Block heat map, replica status, scrubber |

---

## Detailed Lab Viva Preparation Guide

### 1. CPU Scheduling (Practicals 1 & 2)
- **Question**: Why does SJF provide optimal average waiting time, and why can it not always be used in general-purpose OS?
  - **NEXUS-OS Answer**: SJF minimizes $\frac{1}{n} \sum_{i=1}^n (n-i) p_i$ by ordering jobs with shortest bursts first. In general-purpose OS (like Linux desktop), future burst time cannot be known in advance; NEXUS-OS demonstrates both offline simulation on recorded traces and historical moving average burst prediction.
- **Question**: How does Priority with Aging prevent starvation?
  - **NEXUS-OS Answer**: Without aging, high-priority jobs continually pre-empt low-priority batch jobs. With aging, every scheduling tick increments the effective priority:
    $$\text{effective\_priority} = \max(1, \text{base\_priority} - \lfloor \text{wait\_time} / 3 \rfloor)$$
    Demonstrated live in `coordinator/scheduler/priority_aging.py`.

### 2. Banker's Algorithm & Deadlocks (Practicals 3 & 4)
- **Question**: What are Coffman's four conditions for deadlock, and how does Banker's algorithm break them?
  - **NEXUS-OS Answer**:
    1. Mutual Exclusion
    2. Hold and Wait
    3. No Preemption
    4. Circular Wait
    Banker's algorithm breaks **Circular Wait** by ensuring that resources are only allocated if there exists at least one safe sequence where all processes can acquire their maximum declared needs and finish. If no safe sequence exists, the request is held in `WAITING`.

### 3. Page Replacement & Belady's Anomaly (Practical 5)
- **Question**: What is Belady's Anomaly and which algorithms are immune to it?
  - **NEXUS-OS Answer**: Belady's Anomaly is the counter-intuitive phenomenon where increasing physical page frames results in *more* page faults under FIFO. Stack algorithms (LRU, Optimal) satisfy Mattson's inclusion property ($M(m) \subseteq M(m+1)$) and are mathematically immune. Demonstrated in `coordinator/file_manager/page_replacement.py` using reference string `[1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]`.

### 4. Logical & Vector Clocks (Practical 10)
- **Question**: Why are Lamport timestamps insufficient to determine whether two events are causally concurrent?
  - **NEXUS-OS Answer**: Lamport clocks enforce a strict total order: $A \to B \implies T(A) < T(B)$. However, the converse does not hold: $T(A) < T(B)$ does NOT imply $A \to B$ (they might be independent concurrent events). Vector clocks track causal histories across all $N$ nodes. If neither $V(A) \le V(B)$ nor $V(B) \le V(A)$, the events are proven concurrent ($A \parallel B$). Demonstrated in `demo/vector_clock_scene.py`.

### 5. Distributed Mutual Exclusion (Practical 11)
- **Question**: What is the message complexity of the Ricart-Agrawala algorithm compared to Lamport's algorithm?
  - **NEXUS-OS Answer**:
    - Lamport Mutual Exclusion: $3(N-1)$ messages (Request, Reply, Release).
    - Ricart-Agrawala: $2(N-1)$ messages ($N-1$ requests + $N-1$ replies). The release is implicitly conveyed by unblocking deferred replies.
    Demonstrated live across cluster nodes in `nodes/ra_participant.py`.
