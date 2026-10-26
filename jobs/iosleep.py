"""NEXUS-OS Job: I/O Wait Simulator.
Simulates network or disk I/O latency with intermittent small buffer operations.
Usage: python jobs/iosleep.py [duration_seconds]
Concept: Blocking I/O wait states (waiting for disk/network packets).
"""

import sys
import time


def run_iosleep(duration=2.0):
    start = time.time()
    duration = float(duration)
    # Simulate non-CPU I/O delay in small chunks
    remaining = duration
    chunk = 0.2
    while remaining > 0:
        step = min(chunk, remaining)
        time.sleep(step)
        remaining -= step
    elapsed = time.time() - start
    print(f"IOSleep complete: Waited {elapsed:.3f}s (target: {duration}s)")
    return elapsed


if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    run_iosleep(dur)
