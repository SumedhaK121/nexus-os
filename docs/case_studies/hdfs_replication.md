# Case Study 2: Apache Hadoop HDFS & NEXUS-OS Block Storage

## 1. Industrial Background: Hadoop HDFS
The **Hadoop Distributed File System (HDFS)** is a distributed, scalable, and portable file-system written in Java for the Hadoop framework. Modeled after the Google File System (GFS, Ghemawat et al., 2003), HDFS is designed to store massive datasets reliably and stream high-bandwidth data patterns to user applications.

Key architectural characteristics:
- **Master/Slave Architecture**: A single `NameNode` manages file system namespace and metadata; multiple `DataNodes` store data blocks.
- **Block Division**: Large files are divided into uniform blocks (default 64 MB / 128 MB) distributed across the cluster.
- **Replication**: Every block is replicated across multiple independent nodes (default replication factor $RF=3$) for fault tolerance.
- **Pipelined Writes**: Data is streamed along a pipeline of DataNodes rather than sent redundantly from the client.

---

## 2. Theoretical OS/DS Concepts Implemented
- **Hierarchical File System Namespace**: Directory inodes, parent/child relationships, path normalization, and POSIX permission bits (`rwxr-xr-x`).
- **Data Chunking & Address Translation**: Mapping linear byte offsets $[0, S)$ into a sequence of discrete fixed-size blocks:
  $$\text{block\_index} = \lfloor \text{offset} / \text{BLOCK\_SIZE} \rfloor, \quad \text{block\_offset} = \text{offset} \pmod{\text{BLOCK\_SIZE}}$$
- **Pipelined Block Replication**: Client $\to$ DataNode 1 $\to$ DataNode 2.
- **Data Integrity & Scrubbing**: Cryptographic hashing (SHA-256) per block to detect bit rot and silent disk corruption.
- **Self-Healing & Automated Re-Replication**: Background health monitor detecting node failure and re-replicating under-replicated blocks.

---

## 3. How NEXUS-OS Implements the HDFS Model
In NEXUS-OS:
1. **NameNode Catalog (`coordinator/file_manager/dfs_metadata.py`)**:
   - Manages SQLite catalog tracking directory trees, block locations, replication factors, and SHA-256 checksums.
2. **DataNode Block Store (`nodes/block_store.py`)**:
   - Worker nodes serve block storage RPCs (`PutBlock`, `GetBlock`, `DeleteBlock`, `ListBlocks`, `CorruptBlock`).
   - Blocks are saved as binary files under `storage/<node_id>/blocks/<block_id>.blk`.
3. **Pipelined Writes (`coordinator/file_manager/dfs_manager.py`)**:
   - Files are partitioned into 64 KB blocks (`NEXUS_BLOCK_KB`).
   - The coordinator selects candidate replica nodes using least-loaded placement.
   - The primary node receives the block and forwards it along the pipeline to the secondary node.
4. **Integrity Scrubbing & Self-Healing**:
   - `FS_SCRUB` command scans all stored replicas against recorded SHA-256 digests.
   - When a worker node fails, `_on_node_down` invokes `re_replicate_under_replicated()`, copying blocks from surviving replicas to restore the replication factor.
