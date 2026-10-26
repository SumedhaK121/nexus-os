"""NEXUS-OS Page Replacement & Virtual Memory Simulator.
Compares FIFO, LRU, and Optimal (Belady's Min) page replacement algorithms on reference strings.
Provides replay of recorded block access traces and demonstrates Belady's Anomaly.
Concept: Virtual memory page replacement, stack algorithms, Mattson's inclusion property (Belady 1966).
"""

import json
import os


def simulate(refs, frames):
    """FIFO vs LRU vs Optimal (Belady) on a page reference string.
    Returns list of dicts with algo, hits, faults, ratio, and step-by-step trace.
    Preserves exact backward-compatible structure for tests/test_core.py.
    """
    frames = max(1, int(frames))
    out = []
    for name in ("FIFO", "LRU", "Optimal"):
        mem, hits, trace = [], 0, []
        for i, p in enumerate(refs):
            hit = p in mem
            if hit:
                hits += 1
                if name == "LRU":
                    mem.remove(p)
                    mem.append(p)
            else:
                if len(mem) >= frames:
                    if name == "Optimal":
                        rest = refs[i + 1:]
                        # Select page that will not be used for longest time in future
                        far = [rest.index(x) if x in rest else 10**9 for x in mem]
                        mem.pop(far.index(max(far)))
                    else:
                        mem.pop(0)
                mem.append(p)
            trace.append({"page": p, "hit": hit, "mem": list(mem)})
        faults = len(refs) - hits
        ratio = round(100 * hits / max(1, len(refs)))
        out.append({"algo": name, "hits": hits, "faults": faults, "ratio": ratio, "trace": trace})
    return out


def beladys_anomaly_demo():
    """Demonstrates Belady's Anomaly on the canonical reference sequence:
    [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5].
    Under FIFO: 3 frames yields 9 faults, while 4 frames yields 10 faults (faults increase with more memory!).
    Under LRU and Optimal (stack algorithms): page faults monotonically decrease with more memory.
    """
    refs = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    frame_sizes = [3, 4]
    comparison = {}

    for f in frame_sizes:
        res = simulate(refs, f)
        for r in res:
            algo = r["algo"]
            if algo not in comparison:
                comparison[algo] = {}
            comparison[algo][f] = {
                "faults": r["faults"],
                "hits": r["hits"],
                "ratio": r["ratio"],
            }

    # Verify anomaly condition
    fifo_f3 = comparison["FIFO"][3]["faults"]
    fifo_f4 = comparison["FIFO"][4]["faults"]
    anomaly_detected = (fifo_f4 > fifo_f3)

    return {
        "type": "BELADY_ANOMALY_RESULT",
        "refs": refs,
        "frame_sizes": frame_sizes,
        "comparison": comparison,
        "anomaly_detected": anomaly_detected,
        "explanation": (
            "Belady's Anomaly occurs when increasing the number of page frames results in MORE page faults. "
            f"Under FIFO, 3 frames gives {fifo_f3} faults, while 4 frames gives {fifo_f4} faults. "
            "In contrast, stack algorithms such as LRU and Optimal satisfy the inclusion property: "
            "the set of pages in memory for k frames is always a subset of memory for k+1 frames, "
            "guaranteeing page faults never increase with additional memory."
        ),
    }


def replay_trace(trace_source, frame_sizes=None):
    """Replays access references (from file path or list) across multiple frame sizes."""
    if frame_sizes is None:
        frame_sizes = [3, 4, 5]

    refs = []
    if isinstance(trace_source, str) and os.path.exists(trace_source):
        with open(trace_source, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if "block_id" in entry:
                            refs.append(entry["block_id"])
                    except json.JSONDecodeError:
                        pass
    elif isinstance(trace_source, list):
        refs = list(trace_source)

    if not refs:
        # Default synthetic trace if none recorded yet
        refs = ["blk_A", "blk_B", "blk_C", "blk_D", "blk_A", "blk_B", "blk_E", "blk_A", "blk_B", "blk_C", "blk_D", "blk_E"]

    by_frame = {}
    for f in frame_sizes:
        by_frame[f] = simulate(refs, f)

    return {
        "type": "CACHE_REPLAY_RESULT",
        "reference_count": len(refs),
        "unique_references": len(set(refs)),
        "references_sample": refs[:20],
        "by_frame": by_frame,
    }
