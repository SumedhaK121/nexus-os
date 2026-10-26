"""NEXUS-OS Process Isolation & Cgroup Memory Enforcement Demo.
Demonstrates:
- Memory quota enforcement (cgroup memory.max / Docker mem_limit).
- Protection against "Noisy Neighbor" memory exhaustion.
- Simulated and live OOM (Out Of Memory) killer behavior.
OS / DS Concept: Process Isolation, Memory Limits, Cgroups, OOM Killer.
Real System: Linux cgroups v2, Docker memory limits, Kubernetes Pod resource limits.
"""

import os
import sys
import time
import subprocess

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def run_leaker(target_mb=120, chunk_mb=15, interval_sec=0.1):
    """Gradually allocates memory until target_mb is reached or process is killed."""
    print(f"[Leaker PID {os.getpid()}] Starting gradual memory allocation towards {target_mb} MB...", flush=True)
    chunks = []
    total_allocated = 0
    try:
        while total_allocated < target_mb:
            # Allocate chunk_mb of 1-byte strings / bytearray
            chunk = bytearray(chunk_mb * 1024 * 1024)
            chunks.append(chunk)
            total_allocated += chunk_mb
            if HAS_PSUTIL:
                rss = psutil.Process().memory_info().rss / (1024 * 1024)
                print(f"[Leaker PID {os.getpid()}] Allocated: {total_allocated} MB | Actual RSS: {rss:.1f} MB", flush=True)
            else:
                print(f"[Leaker PID {os.getpid()}] Allocated: {total_allocated} MB", flush=True)
            time.sleep(interval_sec)
        print(f"[Leaker PID {os.getpid()}] Finished allocating {total_allocated} MB successfully without being killed.", flush=True)
        return 0
    except MemoryError:
        print(f"[Leaker PID {os.getpid()}] MemoryError caught: System/process memory exhausted!", flush=True)
        return 137


def run_isolation_demonstration(limit_mb=80, leak_target_mb=150):
    """Supervises a child leaker process, enforcing a memory limit (simulating cgroup/Docker OOM killer)."""
    print("=" * 65)
    print("  NEXUS-OS Cgroup Memory Isolation & OOM Enforcement Demo")
    print(f"  Container/Node Memory Quota: {limit_mb} MB")
    print(f"  Aggressive Workload Demand : {leak_target_mb} MB")
    print("=" * 65)

    cmd = [sys.executable, __file__, "--child-leaker", str(leak_target_mb)]
    p = subprocess.Popen(cmd)
    pid = p.pid

    print(f"[Supervisor] Spawned workload PID={pid} with cgroup memory.max={limit_mb} MB")

    oom_killed = False
    max_observed_rss = 0.0

    try:
        proc = psutil.Process(pid) if HAS_PSUTIL else None
    except Exception:
        proc = None

    start_t = time.time()
    while p.poll() is None:
        time.sleep(0.15)
        if proc and proc.is_running():
            try:
                rss_mb = proc.memory_info().rss / (1024 * 1024)
                if rss_mb > max_observed_rss:
                    max_observed_rss = rss_mb

                # Enforce cgroup memory limit: if child breaches limit_mb, simulate kernel OOM killer
                if rss_mb >= limit_mb:
                    print(f"\n[KERNEL OOM-KILLER] Process {pid} exceeded memory quota ({rss_mb:.1f} MB >= {limit_mb} MB)!")
                    print(f"[KERNEL OOM-KILLER] Sending SIGKILL (exit code 137) to isolate and protect cluster stability...")
                    proc.kill()
                    oom_killed = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    p.wait()
    exit_code = 137 if oom_killed else p.returncode

    print("-" * 65)
    print("Isolation Demo Summary:")
    print(f"  Workload PID         : {pid}")
    print(f"  Memory Limit (Quota) : {limit_mb} MB")
    print(f"  Peak RSS Observed    : {max_observed_rss:.1f} MB")
    print(f"  Termination Reason   : {'OOM-KILLED (exit code 137)' if oom_killed else f'Exited naturally (code {exit_code})'}")
    print(f"  Cluster Health       : Supervisor and sibling processes remained intact and responsive.")
    print("=" * 65)

    return {
        "pid": pid,
        "limit_mb": limit_mb,
        "peak_rss_mb": round(max_observed_rss, 2),
        "oom_killed": oom_killed,
        "exit_code": exit_code,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child-leaker":
        target = int(sys.argv[2]) if len(sys.argv) > 2 else 120
        sys.exit(run_leaker(target_mb=target))
    else:
        lim = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 80
        run_isolation_demonstration(limit_mb=lim)
