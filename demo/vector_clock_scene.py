"""NEXUS-OS Demo: Vector Clocks & Causal Concurrency Detection.
Demonstrates causal ordering (happens-before), concurrent edits detection,
and causal reconciliation across 3 campus lab cluster nodes.
Concept: Fidge-Mattern Vector Clocks, DynamoDB version vectors, causal consistency.
"""

from distributed_clock.vector_clock import VectorClock, happens_before, are_concurrent


def run_vector_clock_scene():
    print("=" * 65)
    print("   NEXUS-OS Demo: Vector Clocks & Causal Concurrency Detection   ")
    print("=" * 65)

    # 1. Initial common state
    nodes = ["node-1", "node-2", "node-3"]
    init = {n: 0 for n in nodes}

    vc1 = VectorClock("node-1", initial=init)
    vc2 = VectorClock("node-2", initial=init)
    vc3 = VectorClock("node-3", initial=init)

    print("\n[Phase 1] Sequential Causal History (E1 -> E2 -> E3)")
    # E1 on node-1: create report.txt
    e1 = vc1.tick()
    print(f"E1: node-1 creates /report.txt     -> VC: {e1}")

    # Message sent from node-1 to node-2
    e2 = vc2.update(e1)
    print(f"E2: node-2 receives and edits      -> VC: {e2}")

    # Message sent from node-2 to node-3
    e3 = vc3.update(e2)
    print(f"E3: node-3 receives and reviews    -> VC: {e3}")

    print(f"Check E1 -> E2 (happens-before)   : {happens_before(e1, e2)} (Expected: True)")
    print(f"Check E2 -> E3 (happens-before)   : {happens_before(e2, e3)} (Expected: True)")
    print(f"Check E1 -> E3 (transitivity)     : {happens_before(e1, e3)} (Expected: True)")

    print("\n[Phase 2] Causal Fork: Concurrent Edits (E4 || E5)")
    # Both node-1 and node-2 start from E3 and perform local edits without communicating
    vc1_fork = VectorClock("node-1", initial=e3)
    vc2_fork = VectorClock("node-2", initial=e3)

    e4 = vc1_fork.tick()  # node-1 modifies section A
    e5 = vc2_fork.tick()  # node-2 modifies section B simultaneously
    print(f"E4: node-1 edits Section A (offline) -> VC: {e4}")
    print(f"E5: node-2 edits Section B (offline) -> VC: {e5}")

    rel = VectorClock.compare(e4, e5)
    print(f"Comparison of E4 vs E5             : {rel} (Expected: CONCURRENT)")
    print(f"Are E4 and E5 concurrent?          : {are_concurrent(e4, e5)}")

    print("\n[Phase 3] Causal Reconciliation (Merge E4 and E5 into E6)")
    vc_coord = VectorClock("coordinator", initial=e3)
    vc_coord.merge(e4)
    vc_coord.merge(e5)
    e6 = vc_coord.tick()
    print(f"E6: Coordinator resolves conflict    -> VC: {e6}")
    print(f"Check E4 -> E6 (happens-before)   : {happens_before(e4, e6)} (Expected: True)")
    print(f"Check E5 -> E6 (happens-before)   : {happens_before(e5, e6)} (Expected: True)")

    print("=" * 65)
    print("Demo completed successfully: Vector Clocks successfully distinguished")
    print("true causal dependencies from concurrent edits.")
    print("=" * 65)

    return {
        "e1": e1,
        "e2": e2,
        "e3": e3,
        "e4": e4,
        "e5": e5,
        "e6": e6,
        "e4_e5_concurrent": are_concurrent(e4, e5),
    }


if __name__ == "__main__":
    run_vector_clock_scene()
