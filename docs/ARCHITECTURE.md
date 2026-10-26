# NEXUS-OS Architecture & System Design

**Course Context**: Operating Systems and Distributed Systems (OSDS), Final-Year Engineering Project
**Application Profile**: Campus Lab Cluster (Mini Slurm + HDFS + Dropbox)

---

## 1. System Topology Diagram

```
+------------------------------------------------------------------------------------+
|                                    CLIENT TIER                                     |
|  +-------------------------------------+   +------------------------------------+  |
|  |       Web Dashboard (:8080)         |   |    CLI Client / Workload Driver    |  |
|  |  (HTML5 / CSS / Vanilla JS / SVG)   |   |        (demo/workload.py)          |  |
|  +------------------+------------------+   +-----------------+------------------+  |
+---------------------|----------------------------------------|---------------------+
                      | HTTP / JSON                            | TCP-JSON / RPC
                      v                                        v
+------------------------------------------------------------------------------------+
|                     CONTROL PLANE — COORDINATOR (:9000)                            |
|                                                                                    |
|  +------------------------+  +------------------------+  +----------------------+  |
|  |   Plugin Handlers API  |  |  Logical Clocks Engine |  | Deadlock Avoidance   |  |
|  |   (core, res, fs, etc) |  |   (Lamport + Vector)   |  | (Banker's Algorithm) |  |
|  +-----------+------------+  +-----------+------------+  +----------+-----------+  |
|              |                           |                          |              |
|  +-----------v------------+  +-----------v------------+  +----------v-----------+  |
|  |     Node Manager       |  |    Process Manager     |  |   Resource Manager   |  |
|  | (Heartbeats / Failure) |  | (PCB / State Machine)  |  | (Wait-For / Capacity)|  |
|  +-----------+------------+  +-----------+------------+  +----------+-----------+  |
|              |                           |                          |              |
|  +-----------v---------------------------v--------------------------v-----------+  |
|  |              Distributed Scheduler (FCFS, SJF, SRTF, Priority, RR)           |  |
|  +------------------------------------------------------------------------------+  |
|  |              DFS Metadata & Lock Manager (SQLite catalog / RA leases)        |  |
|  +------------------------------------------------------------------------------+  |
+-----------------------------------------+------------------------------------------+
                                          |
                        Internal RPC / TCP / gRPC Data Plane
                                          |
       +----------------------------------+----------------------------------+
       |                                  |                                  |
       v                                  v                                  v
+---------------+                  +---------------+                  +---------------+
| WORKER NODE 1 | <==============> | WORKER NODE 2 | <==============> | WORKER NODE 3 |
| (:ephemeral)  |  Peer-to-Peer    | (:ephemeral)  |   Peer-to-Peer   | (:ephemeral)  |
|               |  Block Replicas  |               |   Block Replicas |               |
| +-----------+ |  Ricart-Agrawala | +-----------+ |   Ricart-Agrawala| +-----------+ |
| |Task Exec  | |  Sync Delta Chk  | |Task Exec  | |   Sync Delta Chk | |Task Exec  | |
| |(psutil)   | |                  | |(psutil)   | |                  | |(psutil)   | |
| +-----------+ |                  +-----------+ |                  +-----------+ |
| |BlockStore | |                  | |BlockStore | |                  | |BlockStore | |
| |(64KB/SHA) | |                  | |(64KB/SHA) | |                  | |(64KB/SHA) | |
| +-----------+ |                  +-----------+ |                  +-----------+ |
| |LRU Cache  | |                  | |LRU Cache  | |                  | |LRU Cache  | |
| +-----------+ |                  +-----------+ |                  +-----------+ |
| |Sync Agent | |                  | |Sync Agent | |                  | |Sync Agent | |
| +-----------+ |                  +-----------+ |                  +-----------+ |
+---------------+                  +---------------+                  +---------------+
```

---

## 2. Real-World Mapping Table

| Real-World Need | NEXUS-OS Mechanism | OS / DS Concept | Real System Equivalent |
|---|---|---|---|
| **Decide which job runs next and where** | Job queue + scheduler policy (FCFS, SJF, SRTF, Preemptive Priority with aging, Round Robin with real time-slicing via `psutil`) | CPU scheduling, process states, starvation prevention | Linux CFS, Slurm, Kubernetes Scheduler, Apache YARN |
| **Stop jobs exhausting machines or deadlocking** | Banker's algorithm as admission control on CPU/RAM/IO slots; wait-for graph detection + recovery as fallback | Deadlock avoidance, detection, cycle resolution | Kubernetes resource requests/limits, Slurm QoS, MySQL/PostgreSQL deadlock engine |
| **Survive machine loss** | Heartbeats, 3-state failure detector (ONLINE/SUSPECT/OFFLINE), task rescheduling, automatic block re-replication | Fault tolerance, failure detection, consensus | HDFS NameNode / DataNode heartbeat monitor, Kubernetes Node Lifecycle Controller |
| **Store big files across machines** | Block-based distributed file system, 64 KB chunks, replication factor 2, SHA-256 verification | Distributed file systems, chunking, block integrity | Hadoop Distributed File System (HDFS), Google File System (GFS) |
| **Keep multi-node copies up-to-date** | Folder watcher + incremental chunk sync + versioning + conflict copies | Distributed synchronization, delta encoding | Dropbox, rsync, Syncthing |
| **Hot files should be fast** | Per-node block cache, FIFO/LRU/Optimal compared on recorded traces | Page replacement, cache eviction policies | Linux page cache, Redis eviction algorithms, CDN edge caches |
| **Only one writer on a shared file** | Local Readers-Writers lock (RWLock) + distributed Ricart-Agrawala mutual exclusion | Mutual exclusion, readers-writers concurrency | Apache ZooKeeper, etcd, Google Chubby |
| **Order events across machines** | Lamport clock for total ordering, Vector Clock for causal concurrency detection | Logical clocks, causality tracking | Amazon DynamoDB, Apache Cassandra, Basho Riak |
| **Node communication** | Inter-node RPC abstraction over TCP-JSON and gRPC with clock interceptors | Inter-process communication, RPC, wire protocols | gRPC in Kubernetes, Envoy proxy, etcd raft |
| **Multi-tenancy on one machine** | Containers with resource limits (`cpus`, `mem_limit`) and isolated data directories | Process isolation, cgroups, namespaces | Docker, Kubernetes Pods, LXC |
