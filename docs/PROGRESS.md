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
