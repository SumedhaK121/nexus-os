"""NEXUS-OS Job: Prime Search (CPU-bound).
Counts prime numbers up to N using a sieve algorithm.
Usage: python jobs/primes.py [N]
Concept: High-performance compute batch task (scientific number theory simulation).
"""

import sys
import time


def count_primes(n):
    start = time.time()
    n = int(n)
    if n < 2:
        return 0
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for p in range(2, int(n**0.5) + 1):
        if sieve[p]:
            for i in range(p * p, n + 1, p):
                sieve[i] = False
    total = sum(sieve)
    elapsed = time.time() - start
    print(f"PrimeSearch complete: Found {total} primes up to {n} in {elapsed:.3f}s")
    return total


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 150000
    count_primes(limit)
