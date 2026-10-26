# NEXUS-OS Implementation Progress

> ### ⚠️ Remote Repository Sync Commands
> If you wish to connect this local repository to your remote GitHub account:
> ```bash
> git remote add origin <YOUR_GITHUB_REPO_URL>
> git push -u origin main
> git push --all
> git push --tags
> ```

---

## Phase 0: Foundation, Architecture Restructure & Bug Fixes
- **Branch**: `phase-0-foundation` (merged into `main`)
- **Tag**: `phase-0-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Initialized Git repository on `main`, created `.gitignore` with runtime exemptions, committed original baseline (`Baseline: original NEXUS-OS v2`), and created `docs/GIT_WORKFLOW.md`.
  2. Modularized API handler registration under `coordinator/api/`: `core_handlers.py`, `resource_handlers.py`, `file_handlers.py`, `sync_handlers.py`, `clock_handlers.py`, and `ops_handlers.py`. Retained `coordinator/api/handlers.py` as backward-compatible install wrapper.
  3. Implemented concrete subsystems:
     - `coordinator/node_manager/node_manager.py`: Node registry tracking ONLINE, SUSPECT, OFFLINE states, hardware capacities, addresses, and failure callback hooks (`subscribe_node_down`, `subscribe_node_up`).
     - `coordinator/process_manager/process_manager.py`: Full Process Control Block (PCB) table with lifecycle states (`NEW`, `READY`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `KILLED`) and validated transition graph. Retained backward-compatible `summary()`.
     - `coordinator/resource_manager/resource_manager.py`: Resource vector definitions `[cpu_slots, mem_units, io_slots]`, dynamic cluster capacity aggregation over online nodes, wait-for dependency graph tracking, and rolling utilization history.
  4. Fixed critical coordinator bugs:
     - Guarded `c.banker is None` in `BANKER_REQUEST` to prevent thread crashes.
     - Protected all access to `c.tasks` with `c.lock`.
     - Handled unknown PIDs in `TASK_DONE` gracefully without raising `KeyError`.
     - Wrapped client request execution with exception handlers to return structured ERROR messages while keeping the TCP connection alive.
  5. Implemented `nodes/node_server.py` providing a generic threaded TCP-JSON server on an OS-assigned ephemeral port. Workers advertise their port in `REGISTER` and discover peers via `PEERS`.
  6. Implemented `communication/rpc.py` with `call_node(...)` and `call_addr(...)`.
  7. Added `requirements.txt` (`psutil`, `grpcio`, `grpcio-tools`, `protobuf`) and verified dependencies.
  8. Created `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/PROGRESS.md`.
  9. Rewrote `README.md` and converted `tests/test_core.py` to standard `unittest.TestCase` format retaining all baseline assertions.
- **Files Changed/Created**:
  - `requirements.txt`
  - `.gitignore`
  - `coordinator/main.py`
  - `coordinator/api/__init__.py`
  - `coordinator/api/handlers.py`
  - `coordinator/api/core_handlers.py`
  - `coordinator/api/resource_handlers.py`
  - `coordinator/api/file_handlers.py`
  - `coordinator/api/sync_handlers.py`
  - `coordinator/api/clock_handlers.py`
  - `coordinator/api/ops_handlers.py`
  - `coordinator/node_manager/node_manager.py`
  - `coordinator/process_manager/process_manager.py`
  - `coordinator/resource_manager/resource_manager.py`
  - `nodes/node.py`
  - `nodes/node_server.py`
  - `communication/rpc.py`
  - `jobs/__init__.py`
  - `demo/__init__.py`
  - `proto/__init__.py`
  - `tools/__init__.py`
  - `docs/PLAN.md`
  - `docs/CONTRACT.md`
  - `docs/ARCHITECTURE.md`
  - `docs/PROGRESS.md`
  - `docs/GIT_WORKFLOW.md`
  - `README.md`
  - `tests/test_core.py`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python app.py
  ```
- **Known Gaps**: Subprocess job execution, Banker's admission dispatch, and distributed DFS to be implemented in Phases 1-3.

---

## Phase 1: Real Processes and CPU Scheduling
- **Branch**: `phase-1-processes-scheduling` (merged into `main`)
- **Tag**: `phase-1-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Built the real job catalog in `jobs/`: `wordcount.py`, `primes.py`, `compress.py`, `matmul.py`, `iosleep.py`, and `catalog.py` declaring resource profiles `{cpu_slots, mem_units, io_slots}`.
  2. Implemented real execution in `nodes/node.py`: spawns jobs using `subprocess.Popen`, tracks them using `psutil`, measures wall and CPU times, and reports `TASK_STARTED`, `TASK_DONE`, or `TASK_FAILED`. Retained simulated mode for `job_type == "sim"`.
  3. Integrated process lifecycle states (`NEW -> READY -> RUNNING -> WAITING -> COMPLETED/FAILED/KILLED`) with messages `PROC_LIST`, `PROC_KILL`, `PROC_SUSPEND`, and `PROC_RESUME`.
  4. Expanded scheduler policies in `coordinator/scheduler/`: added SRTF (`srtf.py`) and Preemptive Priority with Aging (`priority_aging.py`), added live selection via `scheduler_manager.pick_next(ready_queue, policy, now)`.
  5. Implemented measured metrics computation (waiting, turnaround, response times) with automated CSV logging to `logs/metrics_<policy>_<timestamp>.csv`, queryable via `METRICS`.
  6. Created deterministic workload generator `demo/workload.py` generating `demo/lab_trace.json` (~70% short, ~20% medium, ~10% long) with handler `SUBMIT_TRACE`.
  7. Extended node selection in `node_selector.py` with dynamic capacity awareness, and implemented automatic task rescheduling upon node failure (`_on_node_down`).
  8. Upgraded Dashboard UI with policy selector (SRTF, Priority+Aging), 15-job trace submission button, live PCB table with Suspend/Resume/Kill controls, measured vs predicted metrics table, and actual execution Gantt chart.
  9. Resolved coordinator reentrant lock deadlock by using `threading.RLock()`.
- **Files Changed/Created**:
  - `jobs/wordcount.py`
  - `jobs/primes.py`
  - `jobs/compress.py`
  - `jobs/matmul.py`
  - `jobs/iosleep.py`
  - `jobs/catalog.py`
  - `coordinator/scheduler/srtf.py`
  - `coordinator/scheduler/priority_aging.py`
  - `coordinator/scheduler/scheduler_manager.py`
  - `coordinator/scheduler/node_selector.py`
  - `coordinator/api/core_handlers.py`
  - `coordinator/api/ops_handlers.py`
  - `coordinator/main.py`
  - `nodes/node.py`
  - `demo/workload.py`
  - `demo/lab_trace.json`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase1_scheduling.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python app.py
  # In web dashboard, navigate to Process Manager and click "⚡ Submit Lab Trace (15 Jobs)"
  ```
- **Known Gaps**: Banker's admission control on staged resource requests and distributed DFS blocks to be completed in Phases 2-3.

---

## Phase 2: Resource Manager, Banker's, and Real Deadlocks
- **Branch**: `phase-2-resources-deadlock` (merged into `main`)
- **Tag**: `phase-2-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented real cluster capacity aggregation: dynamically reads online node capacities (`cpu_slots`, `mem_units`, `io_slots`) from registrations/cgroups/psutil, shrinking when nodes disconnect and re-evaluating admission safety.
  2. Integrated Dijkstra's Banker's Algorithm with cluster admission control and staged resource acquisition. Added toggleable admission control (`NEXUS_BANKER=on|off`, message `BANKER_TOGGLE`), `BANKER_STATE`, and maintained textbook what-if simulation.
  3. Extended deadlock detector (`deadlock_detector.py`) with `find_all_cycles()` to identify all distinct elementary cycles in wait-for graphs.
  4. Implemented live wait-for graph builder in `resource_manager.py` with multi-strategy deadlock recovery (`select_victim` via `youngest`, `least_work`, or `lowest_priority`), process termination, and recovery counter tracking (`DEADLOCK_RECOVER`).
  5. Implemented `demo/deadlock_scene.py` demonstrating circular wait formation under Banker OFF, wait-for cycle detection, victim termination, and deadlock avoidance under Banker ON.
  6. Upgraded Dashboard UI with Banker ON/OFF toggle, live wait-for graph visualization, deadlock recovery controls with victim selection policy dropdown, and recovery event logs.
- **Files Changed/Created**:
  - `coordinator/deadlock/deadlock_detector.py`
  - `coordinator/deadlock/bankers_algorithm.py`
  - `coordinator/resource_manager/resource_manager.py`
  - `coordinator/api/resource_handlers.py`
  - `coordinator/main.py`
  - `demo/deadlock_scene.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase2_deadlock.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python demo/deadlock_scene.py
  python app.py
  # In web dashboard, navigate to Deadlock Detection tab and click "🔍 Live Cluster WFG"
  ```
- **Known Gaps**: Distributed block-based storage (64KB chunks, pipeline replication) to be implemented in Phase 3.

---

## Phase 3: Distributed Block-based File System (DFS)
- **Branch**: `phase-3-distributed-fs` (merged into `main`)
- **Tag**: `phase-3-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Created `nodes/block_store.py` (DataNode storage engine) managing block storage under `blocks/`, with SHA-256 integrity verification, pipeline replication forwarding, and RPC methods `PutBlock`, `GetBlock`, `DeleteBlock`, `ListBlocks`, and `CorruptBlock`.
  2. Implemented persistent NameNode metadata catalog in `coordinator/file_manager/dfs_metadata.py` using SQLite (`database/metadata.db`). Persists hierarchical directories, file inodes, versions, checksums, block sequence mappings, replica health states, and POSIX-style permission checking (`mkdir`, `rmdir`, `ls`, `chmod`, `rename`, `check_permission`).
  3. Implemented cluster DFS orchestration in `coordinator/file_manager/dfs_manager.py`:
     - 64 KB block chunking (configurable via `NEXUS_BLOCK_KB`).
     - Pipeline replication across cluster nodes (replication factor 2, configurable via `NEXUS_REPLICAS`).
     - Fault-tolerant failover reads: transparently detects corrupt SHA-256 blocks and fails over to alternate healthy replicas.
     - Self-healing re-replication: automatically detects under-replicated blocks upon node disconnect (`re_replicate_under_replicated`) and coordinates donor-to-destination transfers to restore target replication factor.
     - Data integrity scrubber (`FS_SCRUB`): scans all cluster replicas, flags corruptions, and auto-repairs corrupted blocks from healthy replicas.
  4. Integrated DFS into `coordinator/main.py` with failure callbacks, and registered API handlers in `coordinator/api/file_handlers.py` (`FS_MKDIR`, `FS_LS`, `FS_RMDIR`, `FS_STAT`, `FS_CHMOD`, `FS_RENAME`, `FS_WRITE`, `FS_READ`, `FS_DELETE`, `FS_SCRUB`) while preserving backward-compatible `FILE_*` endpoints.
  5. Upgraded Dashboard UI with DFS Cluster Namespace manager, directory browser with POSIX permission badges, detailed block layout viewer (seq, hash, node replicas), node block load distribution, and one-click DFS Scrub & Repair tool.
  6. Implemented comprehensive test suite in `tests/test_phase3_dfs.py` (7 tests covering chunking, pipeline writes, failover reads, scrub auto-repair, re-replication on node crash, POSIX permissions, and metadata persistence across DB reopen).
- **Files Changed/Created**:
  - `nodes/block_store.py`
  - `nodes/node.py`
  - `coordinator/file_manager/dfs_metadata.py`
  - `coordinator/file_manager/dfs_manager.py`
  - `coordinator/main.py`
  - `coordinator/api/file_handlers.py`
  - `coordinator/api/core_handlers.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase3_dfs.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python app.py
  # In web dashboard, navigate to File Manager to explore the DFS directory tree, block layouts, and scrubber.
  ```
- **Known Gaps**: Per-node block caching (LRU/FIFO/Optimal trace replay) and local synchronization primitives to be implemented in Phase 4.

---

## Phase 4: Cache (Page Replacement for Real) & Local Synchronization
- **Branch**: `phase-4-cache-sync` (merged into `main`)
- **Tag**: `phase-4-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented per-node block caching in `nodes/node_cache.py`:
     - Configurable eviction policies (`LRU`, `FIFO`, `OPTIMAL`) and capacity (`NEXUS_CACHE_CAP`).
     - Persistent access trace logging to `logs/access_trace.jsonl` recording timestamps, block IDs, operations, hits, and policy.
     - Integrated into `nodes/block_store.py`: `get_block` checks in-memory cache first returning immediate hits, while `delete_block` and `corrupt_block` properly invalidate cached entries.
     - Node RPC endpoints `CacheStats` and `CacheConfig`.
  2. Implemented cache replay and Belady's Anomaly demonstration in `coordinator/file_manager/page_replacement.py`:
     - Canonical Belady reference string `[1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]`.
     - Demonstrated that FIFO page faults increase from 9 (3 frames) to 10 (4 frames), proving Belady's Anomaly.
     - Proved that stack algorithms (LRU, Optimal) satisfy Mattson's inclusion property and page faults monotonically decrease (LRU: 10 -> 8; Optimal: 7 -> 6).
     - Handler `CACHE_REPLAY` replaying recorded access traces across multiple frame sizes.
  3. Implemented advanced local synchronization primitives in `coordinator/synchronization/`:
     - `readers_writers.py`: Configurable `RWLock` with Reader-Preference (Courtois 1st problem, demonstrating writer starvation), Writer-Preference (Courtois 2nd problem, preventing writer starvation), and Fair FIFO queueing. Added `demonstrate_starvation()`.
     - `primitives.py`: `CountingSemaphore` for in-flight transfer rate limiting, `BoundedQueue` monitor pattern with condition variables and high-watermark instrumentation, and `file_store_race_demo()` proving lost updates without mutex vs exact counts with mutex.
  4. Implemented `demo/philosophers.py`:
     - Dining Philosophers problem comparing Naive symmetric acquisition (simultaneous left pick causes circular wait deadlock) vs Dijkstra's Resource Hierarchy ordering (lower fork ID acquired first, breaking Coffman condition 4 and preventing deadlock).
  5. Implemented `tools/vmstat_snapshot.py`:
     - Virtual memory and swap telemetry snapshot tool utilizing `psutil` with safe platform fallbacks.
  6. Upgraded Dashboard UI:
     - Added Belady's Anomaly interactive demonstration table and Access Trace Replayer in File & Block Cache view.
     - Added RWLock Starvation tester, Dining Philosophers interactive visualizer, and Storage Race Condition tester in Synchronization view.
  7. Comprehensive test suite in `tests/test_phase4_cache_sync.py` (9 tests covering LRU/FIFO eviction, trace logging, block store cache hits, Belady's Anomaly, trace replay, RWLock starvation, CountingSemaphore, BoundedQueue, Dining Philosophers, storage race condition, and vmstat telemetry).
- **Files Changed/Created**:
  - `nodes/node_cache.py`
  - `nodes/block_store.py`
  - `nodes/node.py`
  - `coordinator/file_manager/page_replacement.py`
  - `coordinator/synchronization/readers_writers.py`
  - `coordinator/synchronization/primitives.py`
  - `coordinator/api/file_handlers.py`
  - `coordinator/api/sync_handlers.py`
  - `demo/philosophers.py`
  - `tools/vmstat_snapshot.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase4_cache_sync.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python demo/philosophers.py
  python tools/vmstat_snapshot.py
  python app.py
  # In web dashboard, navigate to Cache tab for Belady's Anomaly, or Sync tab for RWLock and Philosophers.
  ```
- **Known Gaps**: Vector clocks and causal ordering across distributed nodes to be implemented in Phase 5.

---

## Phase 5: Logical Clocks & Merged Event Log
- **Branch**: `phase-5-logical-clocks` (merged into `main`)
- **Tag**: `phase-5-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented Fidge-Mattern Vector Clocks in `distributed_clock/vector_clock.py`:
     - Full partial-order causality evaluation: `BEFORE` ($V_1 < V_2$), `AFTER` ($V_1 > V_2$), `EQUAL` ($V_1 == V_2$), and `CONCURRENT` ($V_1 \parallel V_2$).
     - Thread-safe operations: `tick()`, `update()`, `merge()`, `to_dict()`, `clone()`, `happens_before()`, and `are_concurrent()`.
  2. Implemented dual logical timestamp envelopes (`ts` for Lamport clock, `vc` for Vector Clock) across all cluster communications:
     - `communication/tcp_client.py`: `Client.call()` automatically injects `ts` and `vc`, updating local clocks on response.
     - `coordinator/main.py`: Coordinator maintains both `LamportClock` and `VectorClock(node_id="coordinator")`. Stamps every log entry (`[T=...] [coord:X n1:Y ...]`), request reply, and dispatch message.
     - `nodes/node.py`: Worker node maintains `VectorClock(node_id=self.id)`. Updates clocks on incoming TCP messages and RPC calls, and attaches vector clocks to heartbeats and task notifications.
  3. Implemented node batch event buffering and causal timeline merging:
     - `nodes/node.py`: Buffers local lifecycle and process events (`local_events`) and flushes them to the coordinator via `EVENTS` batches.
     - `coordinator/api/clock_handlers.py`: Ingests `EVENTS`, merges node clocks into cluster timeline, and sorts events by `(Lamport T, node_id)`.
     - Handler `CAUSAL_LOG`: Serves unified timeline and detects pairs of causally concurrent events.
  4. Implemented interactive concurrency demonstration:
     - `demo/vector_clock_scene.py`: Scripted walkthrough of sequential events ($E_1 \to E_2 \to E_3$), causal branching/concurrency ($E_4 \parallel E_5$), and coordinator reconciliation ($E_6$).
     - Handler `CONCURRENT_DEMO`: Demonstrates how vector clocks identify concurrent writes where scalar Lamport clocks fail.
  5. Upgraded Dashboard UI:
     - Formatted Event Log entries with dual timestamp badges (Lamport $T$ + Vector Clock snapshot).
     - Added "Demonstrate Concurrent Edits (Vector Clocks)" and "Detect Concurrent Event Pairs" controls to the Event Log view.
  6. Comprehensive test suite in `tests/test_phase5_clocks.py` (6 tests covering comparisons, tick/update/merge, causal transitivity/antisymmetry, dual timestamp envelopes over TCP sockets, batch event sorting, and concurrent demo scene).
- **Files Changed/Created**:
  - `distributed_clock/vector_clock.py`
  - `communication/tcp_client.py`
  - `coordinator/main.py`
  - `coordinator/api/clock_handlers.py`
  - `coordinator/api/core_handlers.py`
  - `coordinator/api/__init__.py`
  - `nodes/node.py`
  - `demo/vector_clock_scene.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase5_clocks.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python demo/vector_clock_scene.py
  python app.py
  # In web dashboard, navigate to Event Log tab to view vector clocks and click "▶ Demonstrate Concurrent Edits"
  ```
- **Known Gaps**: Real node-to-node Ricart-Agrawala mutual exclusion and lease-based distributed lock manager to be implemented in Phase 6.


---

## Phase 6: Distributed Locks (Ricart-Agrawala)
- **Branch**: `phase-6-locks` (merged into `main`)
- **Tag**: `phase-6-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented real node-to-node Ricart-Agrawala distributed mutual exclusion in `nodes/ra_participant.py`:
     - Protocol states: `RELEASED`, `WANTED`, `HELD`.
     - Entering CS: increments local Lamport clock, marks state `WANTED`, broadcasts `RaRequest(req_node, ts)` to all $N-1$ peers, and waits for $N-1$ incoming `RaReply` messages.
     - Handling requests: if state is `HELD` or (`WANTED` and own request has lower/equal priority `(ts, node_id)`), request is deferred in `deferred_nodes` queue; otherwise sends immediate `RaReply`.
     - Exiting CS: marks state `RELEASED`, drains and flushes deferred queue by sending `RaReply` to each waiting peer, achieving exactly $2(N-1)$ message complexity.
     - Integrated into worker node (`nodes/node.py`) with RPC endpoints: `RaRequest`, `RaReply`, `RaEnter`, `RaExit`, and `RaStatus`.
  2. Implemented Coordinator-side Distributed Lock Manager in `coordinator/synchronization/lock_manager.py`:
     - Named resource locks (e.g. `file:/path`, `table:records`).
     - Time-bounded leases (`lease_sec`, default 15.0 s) with automatic expiration to prevent deadlocks from orphaned leases.
     - FIFO waiter queue: releasing a lock automatically promotes and grants the lock to the next waiting client.
     - Wait-For Graph integration: waiting clients dynamically register dependency edges in `res_mgr.wait_for_graph` for cycle detection.
     - Node failure auto-release: `on_node_down(node_id)` cleans up and frees all leases held by a disconnected node.
  3. Added Coordinator API Handlers in `coordinator/api/sync_handlers.py`:
     - `LOCK_ACQUIRE`, `LOCK_RELEASE`, `LOCK_RENEW`, `LOCK_STATUS`.
     - `RA_CLUSTER_DEMO`: End-to-end multi-node Ricart-Agrawala demonstration showing node-1 entering CS, node-2 being deferred, node-1 exiting CS, and node-2 being unblocked.
     - `RA_COMPLEXITY`: Message complexity table comparing Ricart-Agrawala $2(N-1)$ with Lamport's $3(N-1)$.
  4. Upgraded Dashboard UI in `dashboard/static/index.html` and `dashboard/static/script.js`:
     - Distributed Lock Manager control panel: interactive lock acquire, renew, release, and live table of active leases and wait queues.
     - Real Ricart-Agrawala Cluster Mutual Exclusion visualizer: cluster demo runner, step-by-step execution trace log, and theoretical complexity table.
  5. Comprehensive test suite in `tests/test_phase6_locks.py` (5 unit tests covering local RA participant logic, multi-node RPC mutual exclusion and deferral, lease expiration, lock queue grant, and auto-release on node failure).
- **Files Changed/Created**:
  - `nodes/ra_participant.py`
  - `nodes/node.py`
  - `coordinator/synchronization/lock_manager.py`
  - `coordinator/main.py`
  - `coordinator/api/sync_handlers.py`
  - `coordinator/api/core_handlers.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase6_locks.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python app.py
  # In web dashboard, navigate to Sync tab to test Distributed Locks and run "▶ Run Real Ricart-Agrawala Cluster Demo"
  ```
- **Known Gaps**: Sync engine (Dropbox-Lite) with folder watcher, chunk-level delta synchronization, and vector clock conflict copies to be implemented in Phase 7.


---

## Phase 7: Sync Engine ("Dropbox-Lite")
- **Branch**: `phase-7-sync` (merged into `main`)
- **Tag**: `phase-7-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented local sync agent in `nodes/sync_agent.py`:
     - Watches `storage/<node_id>/sync/` using recursive filesystem polling.
     - Detects `CREATE`, `MODIFY`, and `DELETE` events by comparing size, mtime, and SHA-256 hashes against an in-memory snapshot.
     - Buffers change events into Phase 4's `BoundedQueue` (producer) providing flow control and queue back-pressure.
     - Employs a worker pool (consumers) governed by `CountingSemaphore` to rate-limit in-flight network transfers.
     - Transfer job scheduling via `scheduler_manager.pick_next(pending_transfers, policy=self.policy)`: dispatches shortest transfer job first (`burst = size`) under `policy="SJF"`, minimizing average sync latency compared to `FCFS`.
     - Incremental rsync delta sync: chunks files into 64KB blocks, queries coordinator `SYNC_CHECK_CHUNKS` for missing chunk indices, and transmits only modified/missing blocks.
     - Distributed locking: acquires `file:/sync/<rel_path>` lock before writes and releases upon completion.
     - Vector clock ticking on local changes and snapshot tracking.
  2. Implemented cluster sync manager in `coordinator/file_manager/sync_manager.py`:
     - Coordinates cluster-level Dropbox-Lite operations across nodes and integrates with DFS metadata.
     - Tracks bandwidth metrics: `bytes_transferred`, `bytes_saved`, `full_bytes`, `savings_pct`.
     - Vector Clock Concurrency evaluation via `VectorClock.compare(cur_vc, new_vc)`:
       - If `CONCURRENT`: detects conflict, increments `conflicts_detected`, generates conflicted copy `<stem> (conflict <node_id> T=<Lamport_T>)<ext>`, logs to coordinator event log, and preserves original file.
       - If `BEFORE` / dominating: fast-forwards update without conflict.
     - End-to-end 4-step automated demonstration `run_sync_demo()`.
  3. Integrated into worker node (`nodes/node.py`):
     - Starts `SyncAgent` on node startup watching `storage/<node_id>/sync/`.
     - Exposes node RPC endpoints: `SyncStatus`, `SyncScan`, `SyncPull`.
     - Added clean `stop()` method to terminate agent and threads.
  4. Added Coordinator API Handlers in `coordinator/api/sync_handlers.py`:
     - `SYNC_CHECK_CHUNKS`, `SYNC_PUSH`, `SYNC_PULL`, `SYNC_DELETE`, `SYNC_STATUS`, `SYNC_CONFIG`, `SYNC_ENGINE_DEMO`.
  5. Upgraded Dashboard UI in `dashboard/static/index.html` and `dashboard/static/script.js`:
     - Added Distributed Sync Engine (Dropbox-Lite) panel.
     - Headline metric bar displaying active policy, total syncs, bytes transferred, bytes saved vs full copy, savings percentage, and conflict count.
     - Policy selector (SJF vs FCFS).
     - Interactive Dropbox-Lite demonstration runner with step-by-step trace output.
  6. Comprehensive test suite in `tests/test_phase7_sync.py` (7 unit tests covering change detection, rsync chunk delta sync bandwidth savings, vector clock conflict copy creation, causal fast-forward, SJF vs FCFS transfer scheduling, BoundedQueue back-pressure, and sync demo scenario).
- **Files Changed/Created**:
  - `coordinator/file_manager/sync_manager.py`
  - `nodes/sync_agent.py`
  - `coordinator/file_manager/dfs_metadata.py`
  - `coordinator/file_manager/dfs_manager.py`
  - `coordinator/main.py`
  - `coordinator/api/core_handlers.py`
  - `coordinator/api/sync_handlers.py`
  - `nodes/node.py`
  - `distributed_clock/vector_clock.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase7_sync.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python app.py
  # In web dashboard, navigate to Sync tab to view Dropbox-Lite metrics and click "▶ Run Dropbox-Lite Sync Demo"
  ```
- **Known Gaps**: gRPC transport stubs, protobuf definitions, RPC benchmarks, and Wireshark trace documentation to be implemented in Phase 8.


---

## Phase 8: gRPC and IPC
- **Branch**: `phase-8-grpc` (merged into `main`)
- **Tag**: `phase-8-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented Protobuf service contracts in `proto/nexus.proto`:
     - Defined `Coordinator` service (`Register`, `Heartbeat`, `SubmitJob`, `ReportTask`, `Status`, `StreamTasks`).
     - Defined `NodeService` service (`ExecuteTask`, `PutBlock`, `GetBlock`, `DeleteBlock`, `RaRequest`, `RaReply`, `Ping`, `SyncPull`).
     - Embedded dual logical timestamp envelopes (`ts` integer + `vc` map) on every message.
  2. Implemented stub compiler in `tools/gen_proto.py`:
     - Compiles `nexus.proto` into `communication/generated/nexus_pb2.py` and `nexus_pb2_grpc.py` using `grpc_tools.protoc`.
     - Patches Python import paths for seamless module import.
  3. Implemented `communication/grpc_transport.py`:
     - `NodeServiceServicer` dispatching incoming gRPC calls to `BlockStore`, `RaParticipant`, and worker engines.
     - `grpc_call_node()` stub wrapper with deadlines, exponential backoff retries, and dict-to-protobuf translation.
     - Global RPC metrics interceptor tracking calls, sent/received bytes, and average latencies into `coord.net`.
  4. Multi-transport switch in `communication/rpc.py`:
     - Configurable transport via `NEXUS_TRANSPORT=tcp|grpc`.
     - Preserves 100% backward compatibility for TCP-JSON local IPC.
  5. Implemented OSDS Practical 9 IPC benchmark in `tools/ipc_demo.py`:
     - Compares loopback TCP sockets vs `multiprocessing.shared_memory` zero-copy page mapping.
  6. Implemented RPC micro-benchmark in `tools/rpc_bench.py`:
     - Compares TCP-JSON vs gRPC HTTP/2 on lightweight (`PING`) and payload (`PutBlock`) calls.
     - Logs benchmarks to `logs/rpc_bench.csv`.
  7. Authored Wireshark packet inspection guide in `docs/wireshark.md`:
     - Filter expressions for port 9000, HTTP/2 frames, and Protobuf dissection.
  8. Enforced message robustness in `communication/tcp_client.py` (16MB size limit, malformed JSON recovery, version envelope).
  9. Comprehensive unit test suite in `tests/test_phase8_grpc.py` (8 tests passing, total suite 68 tests passing).
- **Files Changed/Created**:
  - `proto/nexus.proto`
  - `tools/gen_proto.py`
  - `communication/generated/nexus_pb2.py`
  - `communication/generated/nexus_pb2_grpc.py`
  - `communication/grpc_transport.py`
  - `communication/rpc.py`
  - `tools/ipc_demo.py`
  - `tools/rpc_bench.py`
  - `docs/wireshark.md`
  - `communication/tcp_client.py`
  - `coordinator/api/ops_handlers.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase8_grpc.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python tools/ipc_demo.py
  python tools/rpc_bench.py
  python app.py
  # In web dashboard, navigate to Network / IPC to view live gRPC telemetry and run RPC/IPC benchmarks.
  ```
- **Known Gaps**: Docker multi-container cluster setup, cgroup memory limits, live container metrics, and chaos testing to be implemented in Phase 9.

---

## Phase 9: Docker, Live Monitoring & Chaos Engineering
- **Branch**: `phase-9-docker-chaos` (merged into `main`)
- **Tag**: `phase-9-complete`
- **Completed**: Yes
- **What Was Done**:
  1. Updated container infrastructure in `docker/`:
     - `docker/Dockerfile`: Multi-stage build with system utilities, Python dependency installation, and production entrypoint `CMD ["python", "app.py"]`.
     - `docker/docker-compose.yml`: Multi-container topology orchestrating `coordinator`, `node1`, `node2`, `node3`, and `dashboard` with resource limits (`mem_limit: 256m`, `cpus: 1.0`), healthchecks, and persistent named volumes (`nexus_storage`, `nexus_db`).
  2. Implemented 3-state failure detector in `coordinator/main.py`:
     - Transitions: `ONLINE` -> `SUSPECT` (after 4s without heartbeat) -> `OFFLINE` (after 6s).
     - Automated recovery: Heartbeat from `SUSPECT`/`OFFLINE` node transitions it back to `ONLINE` and triggers `_on_node_up` callback.
  3. Implemented Chaos Engineering Tool and API:
     - `tools/chaos.py`: CLI and programmatic chaos injector supporting `kill`, `suspect`, `partition`, `heal`, and `delay`.
     - Handler `CHAOS_ACTION` in `coordinator/api/ops_handlers.py`: Injects faults into cluster control plane, triggers failure callbacks (`_on_node_down`), closes sockets, and records events in Lamport event log.
  4. Implemented Process Isolation & Cgroup Memory Enforcement Demo:
     - `demo/isolation_demo.py`: Demonstrates cgroup memory limits (`memory.max` / Docker `mem_limit`). Runs a memory-hungry workload, tracks peak RSS via `psutil`, intercepts memory threshold breaches, and terminates with simulated SIGKILL (exit code 137) to prevent "Noisy Neighbor" memory exhaustion.
     - Handler `ISO_DEMO` in `coordinator/api/ops_handlers.py`.
  5. Implemented Live Container Telemetry:
     - Updated `DOCKER_STATUS` in `ops_handlers.py` to probe Docker daemon via `docker ps` when running in Docker, or synthesize live container metrics from cluster nodes and `psutil` host statistics in multi-process mode.
     - Embedded `containers` telemetry directly in `STATUS` message.
  6. Upgraded Dashboard UI:
     - Replaced static Docker table with interactive Docker Deployment & Live Container Telemetry panel in `dashboard/static/index.html` and `dashboard/static/script.js`.
     - Added Chaos Engineering & Failure Injection control panel with interactive buttons (`💥 Kill Node`, `⏳ Delay Heartbeat`, `🚫 Partition Node`, `💚 Heal / Recover`, `⏱ Inject 250ms Delay`).
     - Added Cgroup Memory Isolation & OOM Killer Demo runner.
  7. Comprehensive test suite in `tests/test_phase9_monitoring.py` (5 tests covering 3-state failure detector transitions, chaos kill/heal, chaos suspect/delay, container telemetry, and process isolation OOM enforcement; 73 total tests passing).
- **Files Changed/Created**:
  - `docker/Dockerfile`
  - `docker/docker-compose.yml`
  - `coordinator/main.py`
  - `coordinator/api/core_handlers.py`
  - `coordinator/api/ops_handlers.py`
  - `tools/chaos.py`
  - `demo/isolation_demo.py`
  - `dashboard/static/index.html`
  - `dashboard/static/script.js`
  - `tests/test_phase9_monitoring.py`
  - `tools/smoke_test.py`
  - `docs/CONTRACT.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python demo/isolation_demo.py 80
  python tools/chaos.py kill node-1
  python app.py
  # In web dashboard, navigate to Docker view to inspect live container telemetry and execute chaos actions.
  ```
- **Known Gaps**: None. All Phase 9 milestones completed.

---

## Phase 10: Demo, Integration Test, Documentation & Release
- **Branch**: `phase-10-release` (merged into `main`)
- **Tag**: `v1.0`
- **Completed**: Yes
- **What Was Done**:
  1. Implemented canonical 8-scene automated cluster walkthrough in `demo/lab_day.py`:
     - **Scene 1**: Boot in-process cluster with 3 nodes having distinct CPU/RAM/IO limits; aggregates dynamic hardware capacity vector `[CPU: 8, RAM: 1024MB, I/O: 7]`.
     - **Scene 2**: Upload 140 KB dataset to DFS across 3 blocks with 2x pipelined replication and 100% SHA-256 integrity verification.
     - **Scene 3 & 4**: Evaluate 15-job heavy-tailed campus workload trace across FCFS, SJF, Priority, Round Robin, SRTF, and Priority+Aging schedulers.
     - **Scene 5**: Resource deadlock demonstration comparing Banker's admission control (safe request granted vs unsafe denied) vs Banker OFF circular wait with WFG cycle detection and victim recovery.
     - **Scene 6**: Collaborative file synchronization with named distributed lock leases and Dropbox-Lite offline concurrent edit conflict resolution producing conflicted copies.
     - **Scene 7**: Chaos fault injection with sudden crash on `node-1`, automatic job migration to `node-2`, background block re-replication self-healing, and capacity restoration upon node recovery.
     - **Scene 8**: Executive curriculum verification summary report.
  2. Implemented comprehensive end-to-end integration test suite in `tests/test_integration.py`:
     - `test_end_to_end_cluster_lifecycle`: Full cluster pipeline, storage, locking, concurrent sync, node failure, job migration, and self-healing.
     - `test_cpu_scheduling_optimality_invariants`: Verifies mathematical invariants (SJF/SRTF average waiting time $\le$ FCFS).
     - `test_banker_algorithm_safety_invariants`: Verifies Banker's safe sequence discovery and denial of unsafe states.
     - Total test suite now stands at **76 passing tests** across 10 test modules.
  3. Authored complete OSDS curriculum documentation:
     - `docs/REAL_LIFE_MAPPING.md`: Comprehensive mapping linking textbook concepts to NEXUS-OS implementations and production systems (Slurm, HDFS, Dropbox, Chubby, Linux Cgroups).
     - `docs/PRACTICALS_MAP.md`: Alignment matrix mapping university syllabus practicals 1 through 12 to source code and interactive dashboards, complete with viva interview Q&A.
     - `docs/LIMITATIONS.md`: Transparent discussion of engineering trade-offs (SPoF, SQLite catalog, in-process networking, vector clock growth) and future roadmap (Raft consensus, Reed-Solomon, FUSE driver).
  4. Authored 4 in-depth industrial case studies:
     - `docs/case_studies/slurm_scheduling.md` (Slurm Workload Manager)
     - `docs/case_studies/hdfs_replication.md` (Apache Hadoop HDFS)
     - `docs/case_studies/dropbox_sync.md` (Dropbox Architecture)
     - `docs/case_studies/chubby_locks.md` (Google Chubby Lock Service)
  5. Completely rewrote `README.md` into a polished, comprehensive project guide with architecture diagrams, quick-start instructions, benchmark tables, and CLI tool documentation.
  6. Verified zero regressions: Full test suite passing, `demo/lab_day.py` passing, and `python app.py` smoke test verified at `http://localhost:8080`.
  7. Final Release: Merged `phase-10-release` into `main` and tagged `v1.0`.
- **Files Changed/Created**:
  - `demo/lab_day.py`
  - `tests/test_integration.py`
  - `distributed_clock/vector_clock.py`
  - `README.md`
  - `docs/REAL_LIFE_MAPPING.md`
  - `docs/PRACTICALS_MAP.md`
  - `docs/LIMITATIONS.md`
  - `docs/case_studies/slurm_scheduling.md`
  - `docs/case_studies/hdfs_replication.md`
  - `docs/case_studies/dropbox_sync.md`
  - `docs/case_studies/chubby_locks.md`
  - `docs/PROGRESS.md`
- **How to Try It**:
  ```bash
  python -m unittest discover -s tests
  python demo/lab_day.py
  python app.py
  ```
- **Known Gaps**: None. All phases 0 through 10 fully completed, tested, documented, and released as v1.0.


