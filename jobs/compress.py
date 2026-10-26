"""NEXUS-OS Job: Data Compression (CPU + I/O bound).
Zlib-compresses an input payload or synthetic stream.
Usage: python jobs/compress.py [input_file] [output_file]
Concept: Storage optimization and pipeline data reduction.
"""

import os
import sys
import time
import zlib


def run_compress(input_file=None, output_file=None):
    start = time.time()
    if input_file and os.path.exists(input_file):
        with open(input_file, "rb") as f:
            data = f.read()
    else:
        # Synthetic repetitive text stream ~500 KB
        data = (b"NEXUS-OS Distributed Computing Systems Lab Dataset Block " * 10000)

    compressed = zlib.compress(data, level=6)
    ratio = len(compressed) / max(1, len(data)) * 100

    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "wb") as f:
            f.write(compressed)

    elapsed = time.time() - start
    print(f"Compress complete: {len(data)} -> {len(compressed)} bytes ({ratio:.1f}%) in {elapsed:.3f}s")
    return len(compressed)


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    run_compress(inp, out)
