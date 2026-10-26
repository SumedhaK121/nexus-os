"""NEXUS-OS Job: Word Count (I/O and CPU bound).
Reads an input text file, calculates word frequencies, and writes counts.
Usage: python jobs/wordcount.py [input_file] [output_file]
Concept: Classic MapReduce / batch processing job (Hadoop word count).
"""

import collections
import os
import re
import sys
import time

SAMPLE_TEXT = """
Operating systems manage hardware resources and provide a common execution environment for application programs.
Distributed systems consist of autonomous computing nodes that communicate over a network to coordinate actions.
In a campus lab cluster, multiple students submit concurrent batch and interactive jobs.
Schedulers such as Slurm, Kubernetes, and Linux CFS balance fairness, throughput, and turnaround time.
"""


def run_wordcount(input_file=None, output_file=None):
    start = time.time()
    if input_file and os.path.exists(input_file):
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = SAMPLE_TEXT * 50  # synthetic workload

    words = re.findall(r"\b\w+\b", text.lower())
    counts = collections.Counter(words)

    top10 = counts.most_common(10)
    out_str = "\n".join(f"{word}: {cnt}" for word, cnt in top10)

    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(out_str)

    elapsed = time.time() - start
    print(f"WordCount complete: {len(words)} words processed, {len(counts)} unique. Top word: {top10[0] if top10 else 'None'} ({elapsed:.3f}s)")
    return counts


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    run_wordcount(inp, out)
