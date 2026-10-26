# NEXUS-OS: Distributed Operating System & Campus Lab Cluster

**NEXUS-OS** is an educational, production-grade distributed operating system built for final-year Operating Systems and Distributed Systems (OSDS) curriculum. It provides a mini **Slurm + HDFS + Dropbox** stack designed for a campus lab environment (3-10 commodity workstations).

---

## The Real-World Scenario: Campus Lab Cluster

In academic research labs and small startup teams:
1. **Compute contention**: High-priority short interactive jobs wait behind long batch jobs, or machines crash from uncoordinated memory exhaustion. NEXUS-OS provides CPU scheduling policies (FCFS, SJF, SRTF, Preemptive Priority with Aging, Round Robin) and Dijkstra's Banker's Algorithm for admission control.
2. **Scattered and conflicted data**: Concurrent edits on shared reports overwrite each other, and single-machine disk failures destroy artifacts. NEXUS-OS provides a block-based Distributed File System (64 KB chunks, SHA-256 verification, 2x replication), readers-writers locking, and a Dropbox-like background sync engine with vector clock conflict detection.
3. **Causal ordering**: Distributed asynchronous events can become unexplainable due to physical clock drift. NEXUS-OS integrates Lamport Logical Timestamps and Vector Clocks across every message and RPC.

---

## Architecture Overview

```
+-------------------------------------------------------------+
|               Web Dashboard (http://localhost:8080)         |
+------------------------------+------------------------------+
                               | HTTP / JSON API
+------------------------------v------------------------------+
|               Coordinator Control Plane (:9000)             |
|   - Node Manager (Heartbeat monitor & Failure detection)    |
|   - Process Manager (PCB table & state machine)             |
|   - Resource Manager (Banker's Algorithm & Wait-for graphs) |
|   - Scheduler (FCFS, SJF, SRTF, Priority+Aging, RR)         |
|   - DFS Metadata Catalog (SQLite & block placement)         |
|   - Lamport & Vector Clock log merging                      |
+------------------------------+------------------------------+
                               | Inter-Node RPC (TCP / gRPC)
+------------------------------v------------------------------+
|               Worker Nodes (node-1, node-2, node-3)         |
|   - Subprocess execution & psutil process metrics           |
|   - Distributed Block Store (64 KB blocks, SHA-256)         |
|   - Page-replacement Block Cache (FIFO, LRU, Optimal)       |
|   - Ricart-Agrawala Distributed Mutual Exclusion            |
|   - Sync Agent (Delta chunk sync & conflict resolution)     |
+-------------------------------------------------------------+
```

---

## Quick Start

### Prerequisites
Python 3.8+ on Windows, Linux, or macOS.

```bash
pip install -r requirements.txt
```

### 1. Launch the Cluster
Run everything with a single command:
```bash
python app.py
```
This spawns:
- The **Coordinator** listening on port `9000`.
- Three **Worker Nodes** (`node-1`, `node-2`, `node-3`) on dynamic RPC ports.
- The **Control Center Dashboard** at [http://localhost:8080](http://localhost:8080).

### 2. Run Tests
Execute the comprehensive test suite:
```bash
python -m unittest discover -s tests
```

### 3. Docker Deployment
```bash
docker compose -f docker/docker-compose.yml up --build
```

---

## Core Subsystem Modules

| Subsystem | Location | Description |
|---|---|---|
| **Control Plane** | `coordinator/main.py` | Coordinator server, failure detection, event log |
| **Modular Handlers**| `coordinator/api/` | Handlers for core, resources, files, sync, clock, ops |
| **Node Manager** | `coordinator/node_manager/` | Heartbeat tracking, node states (ONLINE/SUSPECT/OFFLINE) |
| **Process Manager**| `coordinator/process_manager/`| Process Control Blocks, lifecycle transitions |
| **Resource Manager**| `coordinator/resource_manager/`| Resource vectors, Banker's admission, Wait-For Graph |
| **Scheduling** | `coordinator/scheduler/` | FCFS, SJF, SRTF, Priority with Aging, Round Robin |
| **Distributed FS** | `coordinator/file_manager/` | DFS metadata, block placement, replication, cache |
| **Synchronization**| `coordinator/synchronization/`| RWLock, semaphores, Ricart-Agrawala mutual exclusion |
| **Communication** | `communication/` | TCP client, RPC layer, gRPC stubs & interceptors |
| **Worker Nodes** | `nodes/` | Worker daemon, node server, block store, sync agent |
| **Dashboard** | `dashboard/` | Real-time web UI, SVG Gantt charts, live metrics |
