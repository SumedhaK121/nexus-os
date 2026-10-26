# NEXUS-OS: Distributed Operating System & Campus Lab Cluster

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-76%20passed-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

**NEXUS-OS** is an educational, production-grade distributed operating system built for the final-year university course **Operating Systems and Distributed Systems (OSDS)**. It implements a complete **mini Slurm + HDFS + Dropbox** stack designed for a campus lab environment (3–10 commodity workstations).

---

## 1. The Real-Life Scenario: "Campus Lab Cluster"

In academic research laboratories and startup developer teams:
1. **Compute Contention & Deadlocks**: Interactive short jobs wait behind multi-hour batch jobs, or uncoordinated memory demands crash physical machines. NEXUS-OS provides CPU scheduling policies (FCFS, SJF, SRTF, Preemptive Priority with Aging, Round Robin) and Dijkstra's Banker's Algorithm for dynamic admission control.
2. **Scattered & Conflicted Data**: Concurrent edits on shared reports overwrite teammate changes, and single-disk failures destroy artifacts. NEXUS-OS provides a block-based Distributed File System (64 KB chunks, SHA-256 verification, 2x pipelined replication), named lease locks, and a Dropbox-like background sync engine with vector clock conflict detection.
3. **Causal Event Ordering**: Asynchronous events across machines become impossible to debug due to physical wall-clock drift. NEXUS-OS integrates Lamport Logical Timestamps and Fidge-Mattern Vector Clocks on every RPC and message.

---

## 2. Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                        Web Control Center (http://localhost:8080)                 |
|  - System Overview & Sparkline       - Process Manager & PCB Table (Live Actions) |
|  - DFS Namespace & Block Heat Map    - Banker's Matrix & Live Wait-For Graph (WFG)|
|  - Belady's Anomaly Simulator        - Dropbox-Lite Sync & Named Lease Locks      |
|  - gRPC & Shared Memory Telemetry    - Docker Containers & Chaos Failure Panel    |
+-----------------------------------------+-----------------------------------------+
                                          | HTTP / JSON API
+-----------------------------------------v-----------------------------------------+
|                        Coordinator Control Plane (:9000)                          |
|  - Node Manager: Heartbeat tracking (3-State: ONLINE -> SUSPECT -> OFFLINE)       |
|  - Process Manager: PCB table & lifecycle states (NEW, READY, RUNNING, WAITING)   |
|  - Resource Manager: Banker's admission control & DFS cycle recovery              |
|  - Scheduler: FCFS, SJF, SRTF, Preemptive Priority + Aging, Round Robin           |
|  - DFS Catalog: SQLite metadata store, 64 KB block placement, SHA-256 scrubber     |
|  - Distributed Lock Manager: Time-bounded lease locks with failover handover      |
|  - Sync Manager: Dropbox-Lite chunk delta sync, SJF queues & conflict resolution  |
|  - Logical & Vector Clocks: Dual-stamped event log & causal ordering              |
+-----------------------------------------+-----------------------------------------+
                                          | Inter-Node RPC (TCP-JSON / gRPC HTTP/2)
          +-------------------------------+-------------------------------+
          |                               |                               |
+---------v---------+           +---------v---------+           +---------v---------+
| Worker Node: node-1|          | Worker Node: node-2|          | Worker Node: node-3|
| - Subprocess &    |           | - Subprocess &    |           | - Subprocess &    |
|   psutil metrics  |           |   psutil metrics  |           |   psutil metrics  |
| - Block Store     |           | - Block Store     |           | - Block Store     |
|   (64 KB chunks)  |           |   (64 KB chunks)  |           |   (64 KB chunks)  |
| - Block Cache     |           | - Block Cache     |           | - Block Cache     |
|   (FIFO/LRU/Opt)  |           |   (FIFO/LRU/Opt)  |           |   (FIFO/LRU/Opt)  |
| - Ricart-Agrawala |           | - Ricart-Agrawala |           | - Ricart-Agrawala |
|   Participant     |           |   Participant     |           |   Participant     |
| - Sync Agent      |           | - Sync Agent      |           | - Sync Agent      |
|   (Folder Watcher)|           |   (Folder Watcher)|           |   (Folder Watcher)|
+-------------------+           +-------------------+           +-------------------+
```

---

## 3. Industrial Production Systems Mapping

| NEXUS-OS Subsystem | OSDS Textbook Concept | Production Industrial System | Real-World System Functionality |
| :--- | :--- | :--- | :--- |
| **Scheduler (`coordinator/scheduler/`)** | CPU Scheduling, Process States | **Slurm**, **Linux CFS** | Dispatches batch & interactive jobs; SJF minimizes average wait time; Priority+Aging breaks starvation. |
| **Deadlock (`coordinator/deadlock/`)** | Banker's Algorithm, WFG Cycle Detection | **Kubernetes Quotas**, **Postgres InnoDB** | Dynamic capacity aggregation; admission control holds unsafe jobs; WFG cycle detection terminates victims. |
| **DFS (`coordinator/file_manager/`)** | Block Storage, Pipelined Replication | **Apache Hadoop HDFS**, **Google GFS** | 64 KB chunks; pipelined writes ($RF=2$); SHA-256 scrubbing; automated re-replication on node crash. |
| **Sync Engine (`nodes/sync_agent.py`)** | Delta Transfers, Vector Clocks | **Dropbox**, **rsync**, **DynamoDB** | 64 KB chunk delta sync; SJF transfer scheduling; detects causal concurrency and saves conflict copies. |
| **Locks (`coordinator/synchronization/`)**| Distributed Mutual Exclusion, Leases | **Google Chubby**, **Apache ZooKeeper** | Named locks with time-bounded leases; automatic revocation on node death; Ricart-Agrawala $2(N-1)$ msgs. |
| **RPC & IPC (`communication/`)** | RPC, Inter-Process Communication | **gRPC HTTP/2**, **POSIX Shared Memory** | Protocol Buffers transport, deadlines, backoff retries, and zero-copy shared memory page mapping. |
| **Chaos & Isolation (`tools/chaos.py`)** | Cgroups, Fault Tolerance, Isolation | **Netflix Chaos Monkey**, **Docker/cgroups**| 3-state failure detector (`SUSPECT`/`OFFLINE`), automated task rescheduling, and cgroup OOM termination. |

---

## 4. Quick Start

### 4.1 Prerequisites
Python 3.8+ on Windows, Linux, or macOS.
```bash
pip install -r requirements.txt
```

### 4.2 Start the Complete Cluster
Launch the Coordinator, 3 worker nodes, and the web Control Center with one command:
```bash
python app.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.

### 4.3 Run the Automated "Day in the Lab" Demonstration
Experience the complete 8-scene automated walkthrough:
```bash
python demo/lab_day.py
```

### 4.4 Run All Test Suites
Execute the full unit and integration test suite (76 tests):
```bash
python -m unittest discover -s tests
```

### 4.5 Docker Multi-Container Cluster
Deploy the cluster with independent cgroup memory and CPU constraints:
```bash
docker compose -f docker/docker-compose.yml up --build
```

---

## 5. Demonstration Highlights & CLI Utilities

### 5.1 OSDS Practical 9: IPC Benchmark (Sockets vs Shared Memory)
Compare loopback TCP sockets vs zero-copy POSIX shared memory:
```bash
python tools/ipc_demo.py --iterations 50 --size 4096
```

### 5.2 OSDS Practical 11: RPC Micro-Benchmark (TCP-JSON vs gRPC HTTP/2)
Compare serialized TCP-JSON vs binary Protocol Buffers over gRPC:
```bash
python tools/rpc_bench.py --iterations 20 --payload-kb 8
```

### 5.3 Cgroup Memory Isolation & OOM Killer Demo
Verify that a leaky process is intercepted and terminated cleanly with exit code 137 without crashing the cluster:
```bash
python demo/isolation_demo.py 80
```

### 5.4 Chaos Engineering & Fault Injection
Inject failures into cluster nodes:
```bash
python tools/chaos.py kill node-1        # Crash node and trigger task migration
python tools/chaos.py suspect node-2     # Simulate delayed heartbeats
python tools/chaos.py heal node-1        # Rejoin node and restore cluster capacity
```

### 5.5 Dining Philosophers Simulation
Demonstrate naive circular wait deadlock vs Dijkstra's Resource Hierarchy ordering:
```bash
python demo/philosophers.py naive        # Demonstrates deadlock
python demo/philosophers.py hierarchical # Demonstrates deadlock-free execution
```

---

## 6. Project Directory Layout

```
nexus_os/
├── app.py                           # Master launcher (Coordinator + 3 Nodes + Dashboard)
├── requirements.txt                 # Dependencies (psutil, grpcio, grpcio-tools, protobuf)
├── communication/
│   ├── tcp_client.py                # TCP socket connection and JSON client
│   ├── rpc.py                       # Unified multi-transport dispatcher (TCP / gRPC)
│   ├── grpc_transport.py            # gRPC servicer, interceptors, and telemetry
│   └── generated/                   # Protobuf compiled stubs (nexus_pb2, nexus_pb2_grpc)
├── coordinator/
│   ├── main.py                      # Master control plane & 3-state failure detector
│   ├── api/                         # Modular handlers (core, resource, file, sync, ops)
│   ├── node_manager/                # Node registry, heartbeat monitoring & lifecycle hooks
│   ├── process_manager/             # Process Control Block (PCB) table & state transitions
│   ├── resource_manager/            # Resource vectors, Banker's admission & WFG cycles
│   ├── scheduler/                   # FCFS, SJF, SRTF, Priority+Aging, Round Robin
│   ├── deadlock/                    # Banker's algorithm & DFS cycle detector
│   ├── file_manager/                # DFS manager, SQLite metadata catalog & block caching
│   └── synchronization/             # Distributed lock manager, RWLock & semaphores
├── nodes/
│   ├── node.py                      # Node worker process execution daemon
│   ├── node_server.py               # Threaded TCP-JSON RPC server
│   ├── block_store.py               # On-disk 64 KB block repository & SHA-256 verification
│   ├── node_cache.py                # In-memory block cache (FIFO, LRU, Optimal)
│   ├── ra_participant.py            # Peer-to-peer Ricart-Agrawala mutual exclusion
│   └── sync_agent.py                # Dropbox-Lite folder watcher & transfer queue
├── dashboard/
│   ├── app.py                       # Lightweight HTTP dashboard server (:8080)
│   └── static/                      # Single-page UI (HTML5, SVG Gantt, dynamic JavaScript)
├── demo/
│   ├── lab_day.py                   # Canonical 8-scene automated walkthrough
│   ├── lab_trace.json               # 15-job heavy-tailed campus workload trace
│   ├── philosophers.py              # Dining Philosophers demonstration
│   ├── isolation_demo.py            # Cgroup memory quota & OOM killer demo
│   └── vector_clock_scene.py        # Vector clock causal concurrency demonstration
├── docker/
│   ├── Dockerfile                   # Multi-stage production container image
│   └── docker-compose.yml           # Multi-container cluster topology with cgroup limits
├── docs/
│   ├── ARCHITECTURE.md              # Detailed architectural design document
│   ├── CONTRACT.md                  # API message contract specification
│   ├── REAL_LIFE_MAPPING.md         # Concept to production system mapping
│   ├── PRACTICALS_MAP.md            # University syllabus practicals alignment
│   ├── LIMITATIONS.md               # Engineering trade-offs & future roadmap
│   ├── PROGRESS.md                  # Historical phase-by-phase implementation log
│   ├── wireshark.md                 # Packet capture & Wireshark HTTP/2 filter guide
│   └── case_studies/                # In-depth case studies (Slurm, HDFS, Dropbox, Chubby)
├── tests/                           # 76 unit and end-to-end integration test cases
└── tools/
    ├── chaos.py                     # CLI chaos engineering injector
    ├── ipc_demo.py                  # Practical 9 IPC benchmark (Sockets vs Shared Memory)
    ├── rpc_bench.py                 # RPC micro-benchmark (TCP-JSON vs gRPC)
    ├── vmstat_snapshot.py           # Virtual memory and swap telemetry tool
    └── gen_proto.py                 # Protobuf compiler utility
```

---

## 7. Documentation & Further Reading

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Message Contracts](docs/CONTRACT.md)
- [Real-Life Systems Mapping](docs/REAL_LIFE_MAPPING.md)
- [Syllabus Practicals Alignment Guide](docs/PRACTICALS_MAP.md)
- [Engineering Trade-Offs & Limitations](docs/LIMITATIONS.md)
- [Phase Implementation History](docs/PROGRESS.md)
- [Wireshark Capture Guide](docs/wireshark.md)
- Case Studies:
  - [Slurm Workload Manager](docs/case_studies/slurm_scheduling.md)
  - [Apache Hadoop HDFS](docs/case_studies/hdfs_replication.md)
  - [Dropbox File Synchronization](docs/case_studies/dropbox_sync.md)
  - [Google Chubby Lock Service](docs/case_studies/chubby_locks.md)
