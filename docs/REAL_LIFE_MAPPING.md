# NEXUS-OS: Real-World Systems & OS/DS Concept Mapping

This document provides a comprehensive mapping between undergraduate Operating Systems and Distributed Systems (OSDS) curriculum concepts, their NEXUS-OS implementation, and the corresponding industrial production systems.

---

## 1. Concept to Production System Mapping Table

| OSDS Theoretical Concept | NEXUS-OS Implementation Module | Industrial Production System | Real-World Production Analogy |
| :--- | :--- | :--- | :--- |
| **Cluster Control Plane & Master Node** | `coordinator/main.py`, `coordinator/node_manager/` | **Kubernetes** (`kube-apiserver`, node controller), **Slurm** (`slurmctld`) | Centralized master managing worker node registration, heartbeat tracking, admission control, and event ordering. |
| **Process Control Block (PCB) & Lifecycle** | `coordinator/process_manager/process_manager.py` | **Linux Kernel** (`task_struct`), **POSIX** Process Model | Table tracking process states (`NEW`, `READY`, `RUNNING`, `WAITING`, `COMPLETED`, `KILLED`), PID, burst, priority, submit/start/finish timestamps. |
| **CPU Scheduling Algorithms** | `coordinator/scheduler/` (FCFS, SJF, SRTF, Priority+Aging, Round Robin) | **Linux CFS** (Completely Fair Scheduler), **Slurm Workload Manager** | Dispatches batch and compute jobs across worker nodes; SJF minimizes average waiting time, Priority with Aging prevents low-priority starvation. |
| **Deadlock Avoidance (Banker's Algorithm)** | `coordinator/deadlock/bankers_algorithm.py`, `coordinator/resource_manager/` | **Slurm Resource Limits**, **Kubernetes Resource Quotas / Requests** | Dynamic hardware capacity aggregation across cluster nodes; staged resource acquisition where unsafe requests are held back to avoid circular wait. |
| **Deadlock Detection & Recovery** | `coordinator/deadlock/deadlock_detector.py`, `coordinator/resource_manager/` | **PostgreSQL / MySQL InnoDB Deadlock Detector**, **Android OOM Killer** | Dynamic Wait-For Graph (WFG) maintenance, Tarjan/DFS cycle detection, and automated victim selection (`youngest`, `least_work`, `lowest_priority`). |
| **Distributed File System (DFS)** | `coordinator/file_manager/dfs_manager.py`, `nodes/block_store.py` | **Hadoop HDFS**, **Google File System (GFS)** | NameNode catalog metadata with DataNode 64 KB block division, pipelined replication ($RF=2$), SHA-256 data scrubbing, and failover reads. |
| **Page Replacement & Virtual Memory** | `coordinator/file_manager/page_replacement.py`, `nodes/node_cache.py` | **Linux Page Cache**, **Redis Cache Eviction**, **Cloudflare CDN** | Per-node block caching with FIFO, LRU, and Optimal eviction; demonstrated Belady's Anomaly where FIFO faults increase from 3 to 4 frames. |
| **Classical Synchronization Primitives** | `coordinator/synchronization/readers_writers.py`, `primitives.py`, `demo/philosophers.py` | **POSIX `pthread_rwlock`**, **OS Semaphores & Condition Variables** | Courtois 1st/2nd problem (reader- vs writer-preference), `CountingSemaphore`, monitor-based `BoundedQueue`, and Dijkstra's Resource Hierarchy. |
| **Logical Clocks (Lamport Clocks)** | `distributed_clock/lamport_clock.py`, `coordinator/main.py` | **Google Spanner** (TrueTime concepts), **Leslie Lamport 1978** | Scalar logical timestamps ensuring that if $A \to B$ then $T(A) < T(B)$; orders events deterministically across asynchronous distributed nodes. |
| **Vector Clocks & Concurrency** | `distributed_clock/vector_clock.py`, `coordinator/file_manager/sync_manager.py` | **Amazon DynamoDB**, **Apache Cassandra**, **Riak KV** | Fidge-Mattern vector clocks embedded in messages; detects true concurrent branches ($V_1 \parallel V_2$) and causality dominance ($V_1 < V_2$). |
| **Distributed Mutual Exclusion** | `nodes/ra_participant.py`, `coordinator/synchronization/lock_manager.py` | **Google Chubby Lock Service**, **Apache ZooKeeper**, **etcd** | Real peer-to-peer Ricart-Agrawala protocol with $2(N-1)$ message complexity, deferred queues, and lease-based distributed lock manager. |
| **Distributed Folder Synchronization** | `nodes/sync_agent.py`, `coordinator/file_manager/sync_manager.py` | **Dropbox**, **rsync**, **Syncthing** | Incremental chunk delta sync (64 KB chunk diffs), SJF transfer prioritization, and automatic generation of conflicted copies on concurrent edits. |
| **Remote Procedure Calls (RPC)** | `communication/grpc_transport.py`, `proto/nexus.proto`, `communication/rpc.py` | **gRPC / Protocol Buffers** in **Kubernetes**, **etcd**, **Envoy** | Binary Protocol Buffers over HTTP/2 with multiplexed streams, deadlines, exponential backoff, and comparative micro-benchmarks against TCP-JSON. |
| **Inter-Process Communication (IPC)** | `tools/ipc_demo.py` | **POSIX Sockets vs POSIX Shared Memory (`shm_open`)** | Micro-benchmark demonstrating zero-copy shared memory performance compared to loopback serialization socket overhead (OSDS Practical 9). |
| **Process Isolation & Resource Quotas** | `docker/`, `demo/isolation_demo.py` | **Linux cgroups v2**, **Docker Engine**, **Kubernetes Pod limits** | Multi-container isolation with CPU/RAM cgroup constraints; supervised memory monitor terminates leaky tasks with SIGKILL (code 137). |
| **Failure Detection & Self-Healing** | `coordinator/main.py`, `coordinator/node_manager/` | **HDFS DataNode Heartbeats**, **Kubernetes Node Lifecycle Controller** | 3-state failure detector (`ONLINE` $\to$ `SUSPECT` $\to$ `OFFLINE`), automatic job rescheduling, and background block re-replication. |
| **Chaos Engineering** | `tools/chaos.py`, `coordinator/api/ops_handlers.py` | **Netflix Chaos Monkey**, **Chaos Mesh** | Programmatic failure injection simulating sudden node crashes, heartbeat drops, network latency, and network partitioning. |

---

## 2. In-Depth Subsystem Architectural Parallels

### 2.1 Compute Subsystem vs Slurm Workload Manager
- **Cluster Registration**: Similar to `slurmd` daemons registering node socket, core, and memory limits with `slurmctld`, NEXUS-OS worker nodes emit `REGISTER` upon boot with `cpu_slots`, `mem_mb`, and `io_slots`.
- **Job Submission & Tracking**: Clients submit job profiles with declared maximum burst and priority. Schedulers manage a centralized ready queue with stateful execution tracking.
- **Fair-Share & Starvation Prevention**: Slurm's multifactor priority plugin uses job age to raise priority over time. NEXUS-OS implements `Priority+Aging` where every scheduling quantum increments the effective priority of waiting processes:
  $$\text{effective\_priority} = \max(1, \text{base\_priority} - \lfloor \text{wait\_time} / \text{aging\_factor} \rfloor)$$

### 2.2 Storage Subsystem vs Hadoop HDFS
- **NameNode & Catalog**: `coordinator/file_manager/dfs_metadata.py` maintains an SQLite-backed metadata catalog tracking inodes, permissions, block lists, and replica locations.
- **DataNode Block Store**: Worker nodes host block stores (`nodes/block_store.py`) storing 64 KB binary chunks under `storage/<node_id>/blocks/`.
- **Pipelined Writes**: Client writes block 0 to Node A, which streams the block to Node B in pipeline ($RF=2$).
- **Background Scrubbing & Self-Healing**: Background thread scans blocks against target replication factors. When `node-1` dies, `re_replicate_under_replicated()` identifies under-replicated blocks and streams healthy replicas from surviving nodes.

### 2.3 Concurrency & Lock Subsystem vs Google Chubby
- **Lease-Based Distributed Locks**: Rather than permanent lock holds that could freeze the cluster upon client failure, `DistributedLockManager` issues time-bounded leases (e.g. 10 seconds).
- **Automated Revocation**: If a holding node crashes or fails to send heartbeats, the lease expires and is automatically handed over to the first queued FIFO waiter.
- **Wait-For Graph Integration**: Lock contention edges ($P_{\text{waiter}} \to P_{\text{holder}}$) are registered with the cluster `ResourceManager` so distributed deadlocks can be identified and broken.

### 2.4 Synchronization & Version Vectors vs Dropbox & DynamoDB
- **Rsync-Style Delta Transfers**: Files are divided into 64 KB chunks. Before transferring an entire file, the client queries missing chunk checksums via `check_chunks` and only transmits newly modified or missing bytes.
- **Vector Clocks (Fidge-Mattern)**: Every collaborative edit carries a vector clock snapshot. When two nodes edit the same document offline, neither vector clock dominates:
  $$\text{VC}_1 = \{\text{node-1}: 2, \text{node-2}: 0\} \quad \parallel \quad \text{VC}_2 = \{\text{node-1}: 1, \text{node-2}: 1\}$$
- **Conflicted Copies**: NEXUS-OS detects the causal fork and preserves both versions by creating `<stem> (conflict <node_id> T=<Lamport_T>)<ext>`, ensuring zero data loss.
