# Case Study 3: Dropbox Architecture & NEXUS-OS Synchronization

## 1. Industrial Background: Dropbox
**Dropbox** pioneered modern consumer cloud file synchronization. Designed to keep files across multiple personal computers continuously up to date over heterogeneous, unreliable internet connections, Dropbox relies on three core architectural principles:
1. **Chunk-Level Content Addressing**: Files are split into 4 MB blocks, each addressed by its cryptographic hash. If a user modifies only 10 bytes of a 500 MB video file, only the modified chunk is transferred over the network.
2. **Notification Pipelines**: Background sync daemons monitor local filesystem events and push changes through notification queues.
3. **Causality & Conflict Copies**: When multiple clients edit the same file disconnected from the internet, the server detects branching versions and creates a "Conflicted Copy" rather than silently destroying user data.

---

## 2. Theoretical OS/DS Concepts Implemented
- **Delta Compression & Incremental Transfers**: Utilizing chunk hash comparison (similar to Andrew Tridgell's rsync algorithm) to achieve bandwidth conservation:
  $$\text{Savings \%} = \frac{\text{Bytes Saved}}{\text{Total File Size}} \times 100$$
- **Producer-Consumer Notification Pipelines**: File system change watchers buffering events into a bounded queue drained by rate-limited worker threads.
- **Transfer Job Scheduling**: Scheduling sync tasks across network channels using Shortest Job First (SJF) to minimize average sync completion time.
- **Logical Version Vectors / Vector Clocks**: Detecting concurrent edits ($V_1 \parallel V_2$) without relying on synchronized physical wall clocks.

---

## 3. How NEXUS-OS Implements the Dropbox Model
In NEXUS-OS:
1. **Sync Agent (`nodes/sync_agent.py`)**:
   - Watches `storage/<node_id>/sync/` using filesystem polling.
   - Enqueues detected change events (`CREATE`, `MODIFY`, `DELETE`) into a thread-safe `BoundedQueue`.
   - Worker threads rate-limited by `CountingSemaphore` process the transfer queue.
2. **Chunk Delta Verification (`coordinator/file_manager/sync_manager.py`)**:
   - Splits files into 64 KB chunks.
   - Client sends chunk checksums to `SYNC_CHECK_CHUNKS`.
   - Server returns only missing chunk indices, transmitting only changed blocks.
3. **Transfer Job Scheduling (`scheduler_manager.pick_next`)**:
   - Pending file sync transfers are prioritized by size (SJF policy), ensuring small notes and code files sync instantly without getting blocked behind large media files.
4. **Vector Clock Conflict Detection**:
   - Evaluates incoming vector clocks against the coordinator version vector.
   - If concurrent, generates a conflicted copy: `<stem> (conflict <node_id> T=<Lamport_T>)<ext>`, preserving all revisions.
