# NEXUS-OS: Engineering Upgrade Plan

**Project**: NEXUS-OS (Operating Systems and Distributed Systems — Campus Lab Cluster)
**Target**: Production-grade mini Slurm + HDFS + Dropbox architecture
**Author**: Systems Engineering Lead

---

## 1. Architectural Overview & Campus Lab Cluster Context

NEXUS-OS implements a decentralized compute and storage infrastructure designed for a campus lab environment (3-10 physical/virtual nodes).
- **Coordinator**: Control plane providing scheduling, admission control (Banker's Algorithm), DFS metadata catalog (NameNode), distributed lock orchestration, and logical clock log merging.
- **Worker Nodes**: Data plane providing job execution (psutil / subprocess), distributed block storage (DataNodes), per-node caching, Ricart-Agrawala peer-to-peer mutual exclusion, and local folder synchronization agents.
- **Inter-node Communication**: Unified RPC abstraction (`communication/rpc.py`) supporting TCP-JSON and gRPC (`NEXUS_TRANSPORT=tcp|grpc`) with Lamport and Vector Clock propagation.

---

## 2. Phase-by-Phase Implementation Strategy

### Phase 0: Foundation, Architecture Restructure & Bug Fixes
1. **Git Initialization**: Follow Git Workflow (Step A) — initialize git (`main`), configure `.gitignore`, commit baseline, create `docs/GIT_WORKFLOW.md`.
2. **API Handler Modularization**:
   - Refactor `coordinator/api/handlers.py` into dedicated modules under `coordinator/api/`:
     - `core_handlers.py`: `REGISTER`, `HEARTBEAT`, `SUBMIT`, `TASK_DONE`, `COMPARE`, `STATUS`, `PEERS`.
     - `resource_handlers.py`: `BANKER_*`, `DEADLOCK_*`.
     - `file_handlers.py`: `FILE_*`, `CACHE_*`, `FS_*`.
     - `sync_handlers.py`: `RA_*`, `SYNC_DEMO`, `LOCK_*`.
     - `clock_handlers.py`: `EVENTS`, `CLOCK_*`.
     - `ops_handlers.py`: `DOCKER_*`, `CHAOS_*`, `UTIL`, `METRICS`.
   - Maintain `coordinator/api/handlers.py` as a backward-compatible shim.
3. **Core Package Implementation**:
   - `node_manager.py`: Node registry tracking ONLINE, SUSPECT, OFFLINE states, capacity, network addresses, and lifecycle event callbacks (`on_node_down`, `on_node_up`).
   - `process_manager.py`: Process Control Block (PCB) table with states `NEW`, `READY`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `KILLED` and validated state transitions.
   - `resource_manager.py`: Dynamic resource vectors `[cpu_slots, mem_units, io_slots]`, dynamic cluster capacity aggregation over online nodes, and utilization tracking.
4. **Bug Fixes**:
   - Guard against uninitialized `Banker` in `BANKER_REQUEST` (return descriptive error).
   - Thread-safe access to `c.tasks` using `c.lock`.
   - Safe lookup in `TASK_DONE` for unknown PIDs.
   - Robust error handling in TCP connection handler (`_client`) to keep server connections resilient against payload errors.
5. **Node RPC & Server**:
   - Create `nodes/node_server.py`: Threaded TCP-JSON server listening on a dynamic/configured port per node.
   - Introduce `communication/rpc.py` with `call_node(node_id, method, payload, timeout)`.
   - Support `PEERS` query from coordinator.
6. **Documentation & Tests**:
   - Create `requirements.txt` (`psutil`, `grpcio`, `grpcio-tools`, `protobuf`).
   - Create `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/PROGRESS.md`.
   - Rewrite `README.md`.
   - Convert `tests/test_core.py` to standard `unittest` format while retaining all baseline assertions.

### Phase 1: Real Processes and CPU Scheduling
1. **Jobs Catalog**: Implement standalone jobs in `jobs/` (`wordcount.py`, `primes.py`, `compress.py`, `matmul.py`, `iosleep.py`) and metadata profiles in `jobs/catalog.py`.
2. **Subprocess & psutil Execution**: In `nodes/node.py`, spawn real processes via `subprocess.Popen`, track PID/CPU/memory via `psutil`, report `TASK_STARTED`, `TASK_DONE`, and `TASK_FAILED`. Keep simulation mode for `job_type == "sim"`.
3. **Process Control**: Add `PROC_LIST`, `PROC_KILL`, `PROC_SUSPEND`, `PROC_RESUME` handlers.
4. **Live Scheduling Engine**:
   - Implement `scheduler_manager.pick_next(ready_queue, policy, now)`.
   - Implement SRTF, Preemptive Priority with Aging (preventing starvation), and Round Robin with process suspension/resumption via `psutil`.
5. **Metrics & Traces**:
   - Compute real turnaround, waiting, and response times; CSV export in `logs/`.
   - Workload generator `demo/workload.py` creating `demo/lab_trace.json`; `SUBMIT_TRACE` message.
   - Dashboard extension: Live PCB table, kill/suspend buttons, predicted vs measured metrics, real Gantt chart.

### Phase 2: Resource Manager, Banker's Algorithm, Real Deadlocks
1. **Dynamic Capacity**: Aggregate node capacities (`cpu_slots`, `mem_units`, `io_slots`) from node registrations (environment / cgroups / psutil). Shrink cluster capacity on node failure.
2. **Banker's Admission Control**: Staged resource acquisition; hold unsafe jobs in `WAITING` until resources are released. Add `BANKER_STATE` message.
3. **Deadlock Detection & Scenarios**:
   - Configurable `NEXUS_BANKER=on|off`.
   - Reproduce genuine deadlocks via `demo/deadlock_scene.py`.
   - Automated wait-for graph builder in `resource_manager.py` with multi-cycle DFS detection in `deadlock_detector.py`.
4. **Deadlock Recovery**: Victim selection strategies (youngest, least work, lowest priority), termination via `PROC_KILL`, re-queueing, and recovery counters.
5. **Utilization Time-Series**: 5-minute rolling window for node utilization via `UTIL`.
6. **Dashboard**: Live Banker matrix, safe sequence indicator, wait-for graph visualization, recovery logs.

### Phase 3: Block-based Distributed File System (DFS)
1. **Namespace & Metadata**: Directory hierarchy (`mkdir`, `ls`, `rmdir`, `rename`, `move`, `stat`, `chmod`), POSIX-style permissions, SQLite persistence (`database/metadata.db`).
2. **Chunking & Placement**: 64 KB block division (`NEXUS_BLOCK_KB`), SHA-256 verification, rack/node aware placement (replication factor = 2).
3. **Node Block Store**: `nodes/block_store.py` serving block storage via RPC under `NEXUS_DATA_DIR/blocks/`.
4. **Pipelined Writes & Resilient Reads**: HDFS-style pipeline replication (Client -> Node A -> Node B). Checksum verification with failover to healthy replicas.
5. **Self-Healing & Scrubbing**: Automated background re-replication on `on_node_down`, reconciliation on `on_node_up`, and `FS_SCRUB` command.
6. **Job Integration**: Jobs read from and write to DFS blocks.
7. **Dashboard**: File tree, block placement heat map, replica status indicators.

### Phase 4: Cache & Page Replacement & Local Synchronization
1. **Node Block Cache**: LRU, FIFO, and Optimal caching policies with trace recording in `logs/access_trace.jsonl`.
2. **Trace Replay & Belady's Anomaly**: `CACHE_REPLAY` endpoint comparing FIFO, LRU, and Optimal; live demonstration of Belady's Anomaly.
3. **Local Synchronization Primitives**:
   - RWLock with fair reader/writer preference policies.
   - Counting semaphores for transfer rate-limiting.
   - `BoundedQueue` producer-consumer pipeline with performance instrumentation.
   - Dining Philosophers simulation (`demo/philosophers.py`) showing deadlock vs resource hierarchy solution.
4. **Race Condition Demonstration**: Live storage race without mutex vs synchronized storage with mutex.
5. **System Telemetry**: `tools/vmstat_snapshot.py` for virtual memory and swap tracking.

### Phase 5: Logical Clocks & Merged Event Log
1. **Vector Clock Implementation**: `VectorClock` supporting `tick`, `merge`, and causal relationship evaluation (`BEFORE`, `AFTER`, `CONCURRENT`, `EQUAL`).
2. **Dual Timestamp Envelope**: Stamp all messages and RPCs with `ts` (Lamport) and `vc` (Vector Clock).
3. **Causal Event Merging**: Node event aggregation (`EVENTS` message) and causal ordering by `(lamport, node_id)`.
4. **Concurrency Detection**: Interactive demonstration showing concurrent edits with non-dominating vector clocks.

### Phase 6: Distributed Mutual Exclusion & Lock Manager
1. **Real Ricart-Agrawala**: `RaParticipant` running over `communication/rpc.py`, managing `RELEASED`, `WANTED`, and `HELD` states with timestamp-ordered deferred queues.
2. **Failure-Resilient Distributed Lock Manager**: `coordinator/synchronization/lock_manager.py` providing named locks with lease expiration on node death.
3. **Complexity Instrumentation**: Measure $2(N-1)$ message overhead across cluster sizes.
4. **Deadlock Integration**: Register lock waits with the cluster wait-for graph.
5. **Dashboard Panel**: Active locks, waiters, and animated message trace.

### Phase 7: Sync Engine (Dropbox-Lite)
1. **Sync Agent**: File system polling watcher on `NEXUS_DATA_DIR/sync/` feeding change events into `BoundedQueue`.
2. **Rsync-Style Incremental Transfer**: Chunk-level delta synchronization transferring only missing blocks.
3. **Transfer Scheduling**: Transfers treated as scheduled jobs ordered by size (SJF policy).
4. **Conflict Resolution**: Vector clock concurrency check creating conflicted copies (`filename (conflict node-X T=Y).ext`) when non-dominating edits occur.

### Phase 8: gRPC and IPC
1. **Protobuf Definition**: `proto/nexus.proto` defining `Coordinator` and `NodeService`.
2. **Stub Generation & Transport Layer**: `tools/gen_proto.py` compiling stubs into `communication/generated/`. `communication/grpc_transport.py` with clock interceptors and telemetry.
3. **Multi-Transport RPC**: Unified `rpc.py` routing over gRPC or TCP-JSON based on `NEXUS_TRANSPORT`.
4. **IPC Benchmark & Tools**: `tools/ipc_demo.py` (sockets vs shared memory), `tools/rpc_bench.py` (TCP-JSON vs gRPC).
5. **Wireshark Capture Guide**: `docs/wireshark.md` detailing packet capture filters and HTTP/2 framing analysis.

### Phase 9: Docker, Live Monitoring & Chaos Engineering
1. **Container Infrastructure**: Production `Dockerfile` and `docker/docker-compose.yml` with cgroup resource constraints and volume mappings.
2. **Live Container Telemetry**: `DOCKER_STATUS` fetching container statistics or graceful fallback to psutil node metrics.
3. **Heartbeat Time-Series & Failure Detection**: 3-state failure detector (`ONLINE` -> `SUSPECT` -> `OFFLINE`) triggering `on_node_down`/`on_node_up`.
4. **Chaos Injector**: `tools/chaos.py` simulating node death, message delays, and network partitions.
5. **Process Isolation Demo**: `demo/isolation_demo.py` demonstrating cgroup memory enforcement (OOM killer).

### Phase 10: Demo, Integration Test, Documentation & Release
1. **"A Day in the Lab" Script**: `demo/lab_day.py` orchestrating the full 8-scene scenario.
2. **Comprehensive Integration Suite**: `tests/test_integration.py` verifying full cluster execution, mutual exclusion invariants, fault tolerance, and causal order.
3. **Curriculum Documentation**: `docs/REAL_LIFE_MAPPING.md`, `docs/PRACTICALS_MAP.md`, `docs/LIMITATIONS.md`, and 4 OSDS case study drafts.
4. **Release**: Final smoke tests, Git merge to `main`, and `v1.0` tag.
