"""NEXUS-OS Deadlock Reproduction & Resolution Scenario.
Demonstrates:
1. Banker's Algorithm OFF -> Greedy staged allocation causes circular wait deadlock (Proc-A <-> Proc-B).
2. Live Wait-For Graph detects cycle.
3. Deadlock recovery terminates victim and frees resources.
4. Banker's Algorithm ON -> Unsafe state avoided through admission control; no deadlock occurs.
Usage: python demo/deadlock_scene.py
Concept: Coffman conditions (hold-and-wait, circular wait), deadlock detection, and Dijkstra's Banker's algorithm.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coordinator.deadlock.bankers_algorithm import Banker
from coordinator.deadlock.deadlock_detector import detect, find_all_cycles
from coordinator.resource_manager.resource_manager import ResourceManager


def run_deadlock_demo():
    print("=" * 60)
    print("  NEXUS-OS SCENARIO: DEADLOCK FORMATION & AVOIDANCE")
    print("=" * 60)

    # -------------------------------------------------------------
    # PART 1: Banker OFF (Greedy staged acquisition -> Circular wait)
    # -------------------------------------------------------------
    print("\n--- PART 1: BANKER ADMISSION CONTROL = OFF ---")
    print("Available resources: [1 CPU, 1 Memory, 0 I/O]")
    rm = ResourceManager()
    rm.total = [1, 1, 0]
    rm.banker_enabled = False

    print("Job-A acquires Stage 1: [1 CPU, 0 Mem]")
    rm.allocate("Job-A", [1, 0, 0])
    print(f"Cluster available: {rm.get_available()}")

    print("Job-B acquires Stage 1: [0 CPU, 1 Mem]")
    rm.allocate("Job-B", [0, 1, 0])
    print(f"Cluster available: {rm.get_available()}")

    print("Job-A needs Stage 2: [0 CPU, 1 Mem] (held by Job-B) -> WAITING")
    rm.register_wait("Job-A", "Job-B")

    print("Job-B needs Stage 2: [1 CPU, 0 Mem] (held by Job-A) -> WAITING")
    rm.register_wait("Job-B", "Job-A")

    wfg = rm.get_wait_for_graph()
    print(f"Current Wait-For Graph: {wfg}")

    cycle = detect(wfg)
    print(f"Cycle Detection: {'DEADLOCK DETECTED! ' + ' -> '.join(cycle) if cycle else 'No cycle'}")
    assert cycle, "Cycle should be detected with Banker OFF!"

    # Recovery
    proc_table = {
        "Job-A": {"pid": "Job-A", "submit_time": 100.0, "priority": 2},
        "Job-B": {"pid": "Job-B", "submit_time": 105.0, "priority": 1},
    }
    victim = rm.select_victim(cycle, proc_table, policy="youngest")
    print(f"Recovery policy 'youngest' selected victim: {victim}")
    rm.release(victim)
    new_wfg = rm.get_wait_for_graph()
    new_cycle = detect(new_wfg)
    print(f"Post-recovery Wait-For Graph: {new_wfg}, Cycle: {new_cycle} (Deadlock Resolved!)")
    assert not new_cycle, "Deadlock should be resolved after victim termination!"

    # -------------------------------------------------------------
    # PART 2: Banker ON (Admission Control avoids unsafe states)
    # -------------------------------------------------------------
    print("\n--- PART 2: BANKER ADMISSION CONTROL = ON ---")
    banker = Banker(available=[1, 1, 0], maximum={"Job-A": [1, 1, 0], "Job-B": [1, 1, 0]}, allocation={"Job-A": [0, 0, 0], "Job-B": [0, 0, 0]})
    print("Initial Banker state safe:", banker.is_safe())

    # Job-A requests [1, 0, 0]
    reqA1 = banker.request("Job-A", [1, 0, 0])
    print(f"Job-A requests [1, 0, 0] -> Granted: {reqA1['granted']}, Safe sequence: {reqA1.get('safe_sequence')}")

    # Job-B attempts greedy request [0, 1, 0]
    reqB1 = banker.request("Job-B", [0, 1, 0])
    print(f"Job-B requests [0, 1, 0] -> Granted: {reqB1['granted']}, Reason: {reqB1.get('reason')}")
    print("Banker blocked Job-B because allocating to both would leave 0 resources and prevent either from finishing!")

    print("\nConclusion: With Banker's Algorithm ON, deadlocks cannot occur because unsafe states are rejected before allocation.")
    return True


if __name__ == "__main__":
    run_deadlock_demo()
