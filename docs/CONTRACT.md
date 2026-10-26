# NEXUS-OS Protocol & Message Contracts

This document formalizes all message types, required/optional fields, expected reply formats, and the owning subsystem.

---

## Message Envelope Conventions
Every message transported over TCP or RPC carries logical timestamps:
- `ts`: Lamport logical timestamp (integer).
- `vc`: Vector clock mapping `{node_id: counter}` (introduced in Phase 5).
- `req_id`: Unique request identifier matched by the synchronous client wrapper.

---

## 1. Core Lifecycle & Coordination Messages (`coordinator/api/core_handlers.py`)

### `REGISTER`
- **Sender**: Worker Node -> Coordinator
- **Payload**:
  ```json
  {
    "type": "REGISTER",
    "node_id": "node-1",
    "addr": ["127.0.0.1", 52140],
    "cpu_slots": 2,
    "mem_mb": 256,
    "io_slots": 2
  }
  ```
- **Reply**:
  ```json
  {
    "type": "REGISTERED",
    "node_id": "node-1"
  }
  ```

### `HEARTBEAT`
- **Sender**: Worker Node -> Coordinator (every 2s)
- **Payload**:
  ```json
  {
    "type": "HEARTBEAT",
    "node_id": "node-1",
    "cpu": 12.5,
    "mem": 45.0,
    "load": 2
  }
  ```
- **Reply**: `None`

### `PEERS`
- **Sender**: Node / Dashboard -> Coordinator
- **Payload**:
  ```json
  { "type": "PEERS" }
  ```
- **Reply**:
  ```json
  {
    "type": "PEERS",
    "peers": {
      "node-1": {"host": "127.0.0.1", "port": 52140},
      "node-2": {"host": "127.0.0.1", "port": 52141}
    }
  }
  ```

### `SUBMIT`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**:
  ```json
  {
    "type": "SUBMIT",
    "processes": [
      {"pid": "P1", "arrival": 0, "burst": 4, "priority": 2, "job_type": "sim"}
    ],
    "algo": "fcfs",
    "quantum": 2
  }
  ```
- **Reply**:
  ```json
  {
    "type": "SUBMITTED",
    "assigned": {"P1": "node-1"},
    "metrics": {"waiting": 0.0, "turnaround": 4.0, "response": 0.0},
    "gantt": [["P1", 0, 4]]
  }
  ```

### `TASK_DONE`
- **Sender**: Worker Node -> Coordinator
- **Payload**:
  ```json
  {
    "type": "TASK_DONE",
    "pid": "P1",
    "node_id": "node-1"
  }
  ```
- **Reply**: `None`

### `COMPARE`
- **Sender**: Dashboard -> Coordinator
- **Payload**:
  ```json
  {
    "type": "COMPARE",
    "processes": [...],
    "quantum": 2
  }
  ```
- **Reply**:
  ```json
  {
    "type": "COMPARED",
    "results": [
      {"algo": "FCFS", "waiting": 1.5, "turnaround": 4.5, "response": 1.5, "gantt": [...]},
      {"algo": "SJF", ...},
      {"algo": "Priority", ...},
      {"algo": "Round Robin", ...}
    ]
  }
  ```

### `STATUS`
- **Sender**: Dashboard -> Coordinator
- **Payload**:
  ```json
  { "type": "STATUS" }
  ```
- **Reply**:
  ```json
  {
    "type": "STATUS",
    "clock": 42,
    "nodes": { ... },
    "tasks": { ... },
    "events": [ ... ],
    "files": { ... },
    "util": [ ... ],
    "procs": { ... },
    "safe": true,
    "net": { ... },
    "cache": { ... },
    "replicas": { ... },
    "banker": { ... },
    "dfs_files": [ ... ],
    "dfs_node_counts": { ... },
    "dfs_under_replicated": 0
  }
  ```

---

## 2. Resource & Deadlock Messages (`coordinator/api/resource_handlers.py`)

### `BANKER_INIT`
- **Payload**: `available` (list), `max` (dict of lists), `alloc` (dict of lists).
- **Reply**: `{"type": "OK", "safe": [bool, safe_sequence]}`

### `BANKER_REQUEST`
- **Payload**: `pid` (str), `request` (list).
- **Reply**: `{"type": "BANKER_RESULT", "granted": bool, "reason": str, "safe_sequence": list}`

### `BANKER_STATE`
- **Payload**: `{}`
- **Reply**: `{"type": "BANKER_STATE", "available": [...], "max": {...}, "alloc": {...}, "safe": bool, "safe_sequence": [...]}`

### `DEADLOCK_DEMO`
- **Payload**: `scenario` ("circular" or "chain").
- **Reply**: `{"type": "DEADLOCK_RESULT", "wait_for": {...}, "cycle": [...], "deadlock": bool}`

### `DEADLOCK_DETECT`
- **Payload**: `{}`
- **Reply**: `{"type": "DEADLOCK_RESULT", "wait_for": {...}, "cycle": [...], "deadlock": bool}`

---

## 3. Distributed File & Cache Messages (`coordinator/api/file_handlers.py`)

### `FS_MKDIR`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str), `user` (optional str, default "root"), `perms` (optional int, default 0o755).
- **Reply**: `{"type": "OK", "path": str}` or `{"type": "ERROR", "error": str}`

### `FS_LS`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (optional str, default "/").
- **Reply**: `{"type": "FS_LS_RESULT", "path": str, "entries": [{"path": str, "name": str, "is_dir": int, "size": int, "owner": str, "perms": int, "version": int}]}`

### `FS_RMDIR`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str).
- **Reply**: `{"type": "OK", "path": str}` or `{"type": "ERROR", "error": str}`

### `FS_STAT`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str).
- **Reply**: `{"type": "FS_STAT_RESULT", "stat": {"path": str, "is_dir": int, "size": int, "version": int, "checksum": str, "blocks": [...]}}`

### `FS_CHMOD`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str), `perms` (int), `user` (optional str).
- **Reply**: `{"type": "OK", "path": str, "perms": int}` or `{"type": "ERROR"}`

### `FS_RENAME` / `FS_MOVE`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `src` (str), `dst` (str), `user` (optional str).
- **Reply**: `{"type": "OK", "src": str, "dst": str}` or `{"type": "ERROR", "error": str}`

### `FS_WRITE`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str), `content` (str or bytes), `user` (optional str), `base` (optional int).
- **Reply**: `{"type": "FILE_OK", "name": str, "path": str, "version": int, "size": int, "blocks": int, "checksum": str, "nodes": [...]}` or `{"type": "CONFLICT", ...}` or `{"type": "ERROR"}`

### `FS_READ`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str), `user` (optional str).
- **Reply**: `{"type": "FILE_OK", "name": str, "path": str, "content": str, "size": int, "version": int, "checksum": str, "blocks": int, "source": "dfs_cluster"}` or `{"type": "ERROR"}`

### `FS_DELETE`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `path` (str), `user` (optional str).
- **Reply**: `{"type": "OK", "path": str}` or `{"type": "ERROR", "error": str}`

### `FS_SCRUB`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `repair` (bool, default true).
- **Reply**: `{"type": "SCRUB_RESULT", "report": {...}, "corrupted_detected": int, "repaired": int}`

### `CACHE_REPLAY`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `trace_path` (optional str), `refs` (optional list), `frame_sizes` (optional list, default [2, 3, 4]).
- **Reply**: `{"type": "CACHE_REPLAY_RESULT", "reference_count": int, "unique_references": int, "by_frame": {...}}`

### `BELADY_DEMO`
- **Sender**: Client / Dashboard -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "BELADY_ANOMALY_RESULT", "refs": [...], "comparison": {...}, "anomaly_detected": bool, "explanation": str}`

### Node-Level Block Store RPCs (`nodes/block_store.py`)
- `PutBlock`: `{"block_id": str, "data": str/b64, "base64": bool, "checksum": str, "forward_to": [node_ids...]}` -> `{"type": "OK", "block_id": str, "size": int, "checksum": str, "forwarded": [...]}`
- `GetBlock`: `{"block_id": str}` -> `{"type": "OK", "block_id": str, "data": str/b64, "checksum": str, "base64": bool, "source": "cache"|"disk"}`
- `DeleteBlock`: `{"block_id": str}` -> `{"type": "OK", "block_id": str}`
- `ListBlocks`: `{}` -> `{"type": "OK", "node_id": str, "blocks": [...], "count": int}`
- `CorruptBlock`: `{"block_id": str}` -> `{"type": "OK", "corrupted": str}`
- `CacheStats`: `{}` -> `{"type": "OK", "node_id": str, "policy": str, "capacity": int, "hits": int, "misses": int, "hit_rate": float, ...}`
- `CacheConfig`: `{"capacity": int, "policy": str}` -> `{"type": "OK", ...}`

### Backward-Compatible Legacy `FILE_*` Handlers

### `FILE_WRITE`
- **Payload**: `name` (str), `content` (str), `base` (optional int version).
- **Reply**: `{"type": "FILE_OK", "name": str, "version": int, "size": int, "nodes": [...]}` or `{"type": "CONFLICT", ...}`

### `FILE_READ`
- **Payload**: `name` (str).
- **Reply**: `{"type": "FILE_OK", "name": str, "content": str, "source": "cache"|"disk", "version": int}` or `{"type": "ERROR"}`

### `FILE_DELETE`
- **Payload**: `name` (str).
- **Reply**: `{"type": "FILE_OK"}` or `{"type": "ERROR"}`

### `CACHE_CONFIG`
- **Payload**: `capacity` (int), `policy` ("LRU"|"FIFO").
- **Reply**: `{"type": "OK"}`

### `CACHE_SIM`
- **Payload**: `refs` (list), `frames` (int).
- **Reply**: `{"type": "CACHE_SIM", "results": [...]}`

### `FILE_VERIFY`
- **Payload**: `repair` (bool), `corrupt` (optional str filename).
- **Reply**: `{"type": "VERIFY", "result": {...}}`

---

## 4. Synchronization & Locking Messages (`coordinator/api/sync_handlers.py`)

### `RA_SIMULATE`
- **Payload**: `nodes` (list), `requesters` (list).
- **Reply**: `{"type": "RA_RESULT", "order": [...], "messages": int, "trace": [...]}`

### `RA_CLUSTER_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "RA_CLUSTER_DEMO_RESULT", "nodes": [...], "trace": [...], "success": bool}`

### `RA_COMPLEXITY`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "RA_COMPLEXITY_RESULT", "algorithm": str, "message_complexity": "2(N-1)", "table": [...]}`

### `LOCK_ACQUIRE`
- **Sender**: Client / Worker Node -> Coordinator
- **Payload**: `name` (str), `client_id` (str), `lease_sec` (optional float).
- **Reply**: `{"type": "LOCK_OK", "lock": str, "holder": str, "lease_sec": float, "expiry": float}` or `{"type": "LOCK_DENIED", ...}`

### `LOCK_RELEASE`
- **Sender**: Client / Worker Node -> Coordinator
- **Payload**: `name` (str), `client_id` (str).
- **Reply**: `{"type": "LOCK_OK", "lock": str, "released_by": str, "granted_to": optional str}` or `{"type": "ERROR"}`

### `LOCK_RENEW`
- **Sender**: Client / Worker Node -> Coordinator
- **Payload**: `name` (str), `client_id` (str), `lease_sec` (optional float).
- **Reply**: `{"type": "LOCK_OK", "lock": str, "renewed": true, "expiry": float}` or `{"type": "ERROR"}`

### `LOCK_STATUS`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "LOCK_STATUS_RESULT", "locks": {...}}`

### Node-Level Ricart-Agrawala RPCs (`nodes/ra_participant.py`)
- `RaRequest`: `{"req_node": str, "ts": int}` -> `{"type": "RaReply", ...}` or `{"type": "RaDeferred", ...}`
- `RaReply`: `{"from_node": str, "ts": int}` -> `{"type": "OK"}`
- `RaEnter`: `{"peers": [node_ids...]}` -> `{"type": "OK", "held": bool}`
- `RaExit`: `{}` -> `{"type": "OK", "released_count": int}`
- `RaStatus`: `{}` -> `{"type": "OK", "node_id": str, "state": str, "req_ts": [...], "deferred_nodes": [...]}`

### `SYNC_DEMO`
- **Payload**: `kind` ("mutex", "dropbox"|"engine", or omit for producer-consumer).
- **Reply**: `{"type": "SYNC_RESULT", ...}` or `{"type": "SYNC_DEMO_RESULT", ...}`

### `SYNC_CHECK_CHUNKS`
- **Sender**: Worker Node Sync Agent -> Coordinator
- **Payload**: `path` (str), `chunk_checksums` (list of hex SHA-256 strings).
- **Reply**: `{"exists": bool, "version": int, "vector_clock": dict, "missing_indices": list[int], "total_chunks": int}`

### `SYNC_PUSH`
- **Sender**: Worker Node Sync Agent -> Coordinator
- **Payload**: `path` (str), `content` (str/bytes), `chunks` (list[dict]), `full_size` (int), `file_checksum` (str), `node_id` (str), `new_vc` (dict), `base_vc` (optional dict), `base_version` (optional int).
- **Reply**: `{"type": "SYNC_OK", "path": str, "version": int, "vector_clock": dict, "bytes_transferred": int, "bytes_saved": int, "savings_pct": float, "full_size": int}` or `{"type": "SYNC_CONFLICT", "conflict": true, "conflict_file": str, ...}`

### `SYNC_PULL`
- **Sender**: Worker Node Sync Agent -> Coordinator
- **Payload**: `path` (str).
- **Reply**: `{"type": "SYNC_PULL_OK", "path": str, "content": str, "version": int, "vector_clock": dict, "size": int, "checksum": str}` or `{"type": "ERROR"}`

### `SYNC_DELETE`
- **Sender**: Worker Node Sync Agent -> Coordinator
- **Payload**: `path` (str), `node_id` (str).
- **Reply**: `{"type": "FILE_OK", ...}` or `{"type": "ERROR"}`

### `SYNC_STATUS`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "SYNC_STATUS_RESULT", "policy": str, "total_syncs": int, "bytes_transferred": int, "bytes_saved": int, "savings_pct": float, "conflicts_detected": int, "recent_transfers": list, "node_agents": dict}`

### `SYNC_CONFIG`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `policy` ("SJF"|"FCFS").
- **Reply**: `{"type": "OK", "policy": str}`

### `SYNC_ENGINE_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "SYNC_DEMO_RESULT", "trace": list[str], "stats": dict, "success": bool}`

### Node-Level Sync RPCs (`nodes/sync_agent.py`)
- `SyncStatus`: `{}` -> `{"node_id": str, "running": bool, "policy": str, "queue_depth": int, "active_workers": int, "bytes_saved": int, ...}`
- `SyncScan`: `{}` -> `{"type": "OK"}`
- `SyncPull`: `{"path": str}` -> `{"type": "OK", "success": bool}`

### `RW_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `preference` ("reader"|"writer"), `duration` (float).
- **Reply**: `{"type": "RW_DEMO_RESULT", "preference": str, "writer_acquired": bool, "writer_wait_seconds": float, "total_reads_during_wait": int, "starved": bool}`

### `PHILOSOPHERS_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `mode` ("hierarchical"|"naive"), `rounds` (int).
- **Reply**: `{"type": "PHILOSOPHERS_RESULT", "mode": str, "total_meals": int, "expected_meals": int, "deadlocked": bool, "log": [...], "explanation": str}`

### `BOUNDED_QUEUE_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `capacity` (int), `items` (int).
- **Reply**: `{"type": "BOUNDED_QUEUE_RESULT", "metrics": {...}, "log": [...]}`

### `RACE_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `threads` (int), `iterations` (int).
- **Reply**: `{"type": "RACE_RESULT", "expected": int, "without_lock": int, "with_lock": int, "lost_updates": int, "race_detected": bool}`

### `VMSTAT`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "VMSTAT_RESULT", "virtual_memory": {...}, "swap_memory": {...}, "os": str}`

---

## 5. Operations & Events (`coordinator/api/ops_handlers.py` & `clock_handlers.py`)

### `EVENTS`
- **Sender**: Worker Node -> Coordinator
- **Payload**: `events`: list of event objects (`[{"ts": int, "vc": dict, "node_id": str, "event": str}]`), `node_id`: str.
- **Reply**: `{"type": "EVENTS_ACK", "count": int}`

### `CAUSAL_LOG`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `limit` (int), `node` (optional str), `filter` ("all"|"concurrent").
- **Reply**: `{"type": "CAUSAL_LOG_RESULT", "current_lamport": int, "coordinator_vc": dict, "timeline": list, "concurrent_pairs": list}`

### `CONCURRENT_DEMO`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{}`
- **Reply**: `{"type": "CONCURRENT_DEMO_RESULT", "initial_state": dict, "event_a": dict, "event_b": dict, "relation": str, "explanation": str}`

### `UTIL`
- **Payload**: `{}`
- **Reply**: `{"type": "UTIL_RESULT", "util": [...]}`

### `DOCKER_STATUS`
- **Payload**: `{}`
- **Reply**: `{"type": "DOCKER_STATUS", "containers": [...], "mode": str, "note": str}`

### `SUBMIT_TRACE`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{"type": "SUBMIT_TRACE", "algo": "srtf", "quantum": 2, "processes": [...]}`
- **Reply**: `{"type": "SUBMITTED", "assigned": {...}, "metrics": {...}, "gantt": [...]}`

### `TASK_STARTED`
- **Sender**: Worker Node -> Coordinator
- **Payload**: `{"type": "TASK_STARTED", "pid": "P1", "node_id": "node-1", "job_type": "primes"}`
- **Reply**: `None`

### `TASK_FAILED`
- **Sender**: Worker Node -> Coordinator
- **Payload**: `{"type": "TASK_FAILED", "pid": "P1", "node_id": "node-1", "error": "details"}`
- **Reply**: `None`

### `PROC_LIST`
- **Sender**: Dashboard -> Coordinator
- **Payload**: `{"type": "PROC_LIST"}`
- **Reply**: `{"type": "PROC_LIST", "processes": {...}}`

### `PROC_KILL`
- **Sender**: Dashboard -> Coordinator
- **Payload**: `{"type": "PROC_KILL", "pid": "P1"}`
- **Reply**: `{"type": "OK", "killed": "P1"}`

### `PROC_SUSPEND`
- **Sender**: Dashboard -> Coordinator
- **Payload**: `{"type": "PROC_SUSPEND", "pid": "P1"}`
- **Reply**: `{"type": "OK", "suspended": "P1"}`

### `PROC_RESUME`
- **Sender**: Dashboard -> Coordinator
- **Payload**: `{"type": "PROC_RESUME", "pid": "P1"}`
- **Reply**: `{"type": "OK", "resumed": "P1"}`

### `METRICS`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{"type": "METRICS", "policy": "srtf", "export_csv": true}`
- **Reply**: `{"type": "METRICS_RESULT", "policy": "srtf", "measured_avg": {"waiting": 0.02, "turnaround": 0.53, "response": 0.02}, "actual_gantt": [...], "csv_exported": "metrics_srtf_12345.csv"}`

### `BANKER_TOGGLE`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{"type": "BANKER_TOGGLE", "enabled": optional bool}`
- **Reply**: `{"type": "OK", "enabled": bool}`

### `DEADLOCK_RECOVER`
- **Sender**: Dashboard / CLI -> Coordinator
- **Payload**: `{"type": "DEADLOCK_RECOVER", "policy": "youngest"|"least_work"|"lowest_priority"}`
- **Reply**: `{"type": "RECOVERY_RESULT", "recovered": bool, "victim": str, "policy": str, "cycle": [...], "resolved_count": int}`
