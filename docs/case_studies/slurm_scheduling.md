# Case Study 1: Slurm Workload Manager & NEXUS-OS CPU Scheduling

## 1. Industrial Background: Slurm
**Slurm** (Simple Linux Utility for Resource Management) is the dominant open-source cluster management and job scheduling system for Linux supercomputers and High-Performance Computing (HPC) clusters worldwide, powering over 60% of the TOP500 supercomputers.

Slurm's primary responsibilities include:
1. Allocating exclusive or shared access to resources (compute nodes) to users for some duration of time.
2. Providing a framework for starting, executing, and monitoring work on allocated nodes.
3. Arbitrating resource contention by managing a queue of pending work.

---

## 2. Theoretical OS/DS Concepts Implemented
- **Process Control Blocks (PCB)**: Tracking job state transitions through `PENDING`, `RUNNING`, `SUSPENDED`, `COMPLETED`, `CANCELLED`, and `FAILED`.
- **CPU Scheduling Policies**:
  - **FCFS**: Simple queue order; prone to head-of-line blocking (convoy effect).
  - **SJF / SRTF**: Shortest Job First and Shortest Remaining Time First; mathematically minimizes average waiting time.
  - **Priority with Aging**: Prevents starvation of long or low-priority background jobs by increasing effective priority over time.
  - **Round Robin**: Real preemptive time-slicing using process suspension and resumption (`psutil`).
- **Resource Reservation & Deadlock Avoidance**: Enforcing resource quotas so compute jobs do not exhaust cluster physical memory.

---

## 3. How NEXUS-OS Implements the Slurm Model
In NEXUS-OS:
1. **Control Plane (`coordinator/main.py`)**: Acts as `slurmctld`, maintaining the global job queue and node registration catalog.
2. **Worker Nodes (`nodes/node.py`)**: Act as `slurmd` daemons, receiving `EXEC` messages, launching native processes via `subprocess.Popen`, tracking CPU/RAM usage via `psutil`, and reporting `TASK_STARTED` / `TASK_DONE`.
3. **Multifactor Scheduling Engine (`coordinator/scheduler/scheduler_manager.py`)**:
   - Compares predicted vs live execution metrics.
   - Evaluates FCFS, SJF, SRTF, Priority, and Round Robin on identical heavy-tailed workloads (`demo/lab_trace.json`).
   - Exports real execution metrics to CSV files in `logs/` for offline scientific evaluation.
4. **Live Process Control**:
   - The web dashboard exposes interactive buttons to suspend (`PROC_SUSPEND`), resume (`PROC_RESUME`), or terminate (`PROC_KILL`) running processes, mirroring Slurm's `scontrol` and `scancel` commands.
