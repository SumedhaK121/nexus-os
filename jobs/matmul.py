"""NEXUS-OS Job: Matrix Multiplication (CPU + Memory bound).
Multiplies two NxN matrices of floating-point numbers in pure Python.
Usage: python jobs/matmul.py [N]
Concept: Linear algebra kernel representing computational scientific modeling (e.g. BLAS/NumPy workloads).
"""

import sys
import time


def matrix_multiply(n):
    start = time.time()
    n = int(n)
    # Initialize deterministic pseudo-matrices
    a = [[((i + j) % 10) * 0.1 for j in range(n)] for i in range(n)]
    b = [[((i * 2 + j) % 10) * 0.1 for j in range(n)] for i in range(n)]
    c = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for k in range(n):
            aik = a[i][k]
            for j in range(n):
                c[i][j] += aik * b[k][j]

    elapsed = time.time() - start
    print(f"MatMul complete: {n}x{n} float matrices multiplied in {elapsed:.3f}s (c[0][0]={c[0][0]:.3f})")
    return c


if __name__ == "__main__":
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    matrix_multiply(size)
