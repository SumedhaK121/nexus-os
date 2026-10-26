# NEXUS-OS: Engineering Trade-Offs, Limitations & Future Extensions

This document explicitly details the architectural boundaries, deliberate trade-offs, and future research/engineering directions for NEXUS-OS.

---

## 1. Architectural Boundaries & Deliberate Trade-Offs

### 1.1 Centralized Coordinator (Single Point of Failure / SPoF)
- **Current Design**: NEXUS-OS adopts a centralized master architecture modeled after early Hadoop HDFS (NameNode) and Slurm (`slurmctld`). The Coordinator maintains cluster topology, scheduling decisions, DFS metadata catalogs, and lock manager leases.
- **Trade-off Justification**: Centralization drastically simplifies course laboratory demonstrations, predictable Lamport event ordering, and deterministic viva reproducibility without requiring complex distributed consensus (Raft or Paxos) just to schedule a batch job.
- **Limitation**: If the Coordinator process dies, worker nodes can continue serving cached blocks and local compute tasks, but new global job submissions, DFS writes, and lock acquisitions halt.
- **Production Evolution**: Modern production systems resolve this via active-standby pairs backed by ZooKeeper (HDFS High Availability) or multi-master consensus backed by Raft (Kubernetes `etcd` clusters).

### 1.2 Metadata Catalog Persistence (SQLite vs Distributed KV)
- **Current Design**: Metadata is persisted in a local SQLite database (`database/metadata.db`) protected by an in-memory `RWLock`.
- **Trade-off Justification**: SQLite provides zero-dependency, ACID-compliant relational transactions with standard SQL indexing across directories, inodes, and blocks without requiring external server setup (e.g. PostgreSQL or MySQL).
- **Limitation**: High-frequency concurrent writes across hundreds of collaborative files will experience lock serialization at the SQLite catalog level.
- **Production Evolution**: Distributed metadata engines like Google Spanner (TrueTime + multi-Paxos) or CockroachDB (Raft + distributed MVCC).

### 1.3 In-Process Network Emulation vs Asynchronous Network Partitions
- **Current Design**: Cluster communication runs over local loopback sockets (`127.0.0.1`) or Docker bridge networks (`172.28.0.0/16`) using TCP-JSON and gRPC HTTP/2.
- **Trade-off Justification**: Ensures that students and evaluators can run the entire multi-node cluster, dashboard, and test suite on a single laptop without physical networking equipment.
- **Limitation**: Loopback TCP sockets experience near-zero packet drop rates and sub-millisecond latencies. While `tools/chaos.py` injects artificial latency and connection drops, it does not reproduce hardware-level asymmetric partitions (e.g. Node A can send to Node B, but Node B cannot send to Node A).
- **Production Evolution**: Integration with Linux `tc-netem` (Traffic Control Network Emulation) or Chaos Mesh for live kernel packet drop injection.

### 1.4 Vector Clock State Growth
- **Current Design**: Fidge-Mattern vector clocks contain an entry for every participating node ID (`{"node-1": T1, "node-2": T2, ...}`).
- **Trade-off Justification**: For campus lab clusters with 3–10 nodes, a $10$-entry dictionary has negligible storage overhead (under 200 bytes per file metadata entry) and provides exact, unambiguous concurrency detection.
- **Limitation**: In systems with tens of thousands of dynamically joining nodes, full vector clocks exhibit unbounded size growth ($O(N)$ space per message).
- **Production Evolution**: Dynamic pruning (e.g. interval tree vector clocks or Dotted Version Vectors as implemented in Riak KV).

---

## 2. Quantitative Performance & Scale Limits

| Metric / Dimension | Supported Laboratory Scale | Bound / Bottleneck Source |
| :--- | :--- | :--- |
| **Worker Nodes** | 3 – 16 nodes | Coordinator socket accept thread, Ricart-Agrawala $O(N)$ message volume |
| **Concurrent Jobs** | 500 active jobs | In-memory PCB table, operating system process table (`psutil`) |
| **DFS File Size** | Up to 1 GB per file | 64 KB block chunking metadata granularity ($16{,}384$ block records per GB) |
| **DFS Block Size** | Configurable (64 KB default) | Memory buffer streaming over pipeline socket |
| **RPC Throughput** | ~12,500 calls/sec (Shared Memory)<br>~1,800 calls/sec (gRPC HTTP/2)<br>~1,200 calls/sec (TCP-JSON) | Loopback serialization, socket buffers, Python GIL context switching |

---

## 3. Roadmap for Future Distributed Extensions

1. **Raft Consensus Integration**:
   - Implement the Raft consensus algorithm (`Leader`, `Follower`, `Candidate`) across 3 coordinator instances to eliminate the single point of failure and provide automated leader election.
2. **Erasure Coding (Reed-Solomon $RS(6,3)$)**:
   - Complement $2\times$ block replication with $RS(6,3)$ Reed-Solomon erasure coding to achieve higher fault tolerance (surviving 3 simultaneous node losses) with only 50% storage overhead instead of 100%.
3. **Dynamic Auto-Scaling (Elastic Worker Pool)**:
   - Monitor aggregate CPU/RAM cluster load and dynamically spawn ephemeral Docker worker containers when ready queue depth exceeds configured thresholds.
4. **POSIX FUSE Filesystem Driver**:
   - Expose the DFS namespace as a mounted local Linux filesystem directory using `fuse-python`, allowing unmodified native applications (`cat`, `grep`, `ffmpeg`) to read and write directly to NEXUS-OS distributed blocks.
