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
    "banker": { ... }
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

### `SYNC_DEMO`
- **Payload**: `kind` ("mutex" or omit for producer-consumer).
- **Reply**: `{"type": "SYNC_RESULT", ...}`

---

## 5. Operations & Events (`coordinator/api/ops_handlers.py` & `clock_handlers.py`)

### `EVENTS`
- **Payload**: `events`: list of event objects.
- **Reply**: `{"type": "EVENTS_ACK", "count": int}`

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
