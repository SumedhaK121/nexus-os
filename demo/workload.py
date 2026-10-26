"""NEXUS-OS Workload Generator.
Generates heavy-tailed job submission traces representative of a campus lab cluster:
~70% short interactive jobs (1-3s), ~20% medium batch jobs (4-7s), ~10% long compute tasks (8-12s).
Usage: python demo/workload.py [--seed 42] [--count 15] [--output demo/lab_trace.json]
Concept: Realistic heavy-tailed workload distribution (Pareto / log-normal cluster traces in Google Borg / Slurm).
"""

import argparse
import json
import os
import random


def generate_workload(count=15, seed=42):
    random.seed(seed)
    jobs = []
    job_types = {
        "short": [("wordcount", []), ("iosleep", ["1.5"]), ("primes", ["50000"])],
        "medium": [("compress", []), ("primes", ["120000"]), ("matmul", ["60"])],
        "long": [("matmul", ["110"]), ("primes", ["250000"]), ("compress", [])],
    }

    current_arrival = 0
    for i in range(1, count + 1):
        pid = f"J{i:02d}"
        roll = random.random()
        if roll < 0.70:
            category = "short"
            burst = random.randint(1, 3)
            prio = random.choice([2, 3, 4])
        elif roll < 0.90:
            category = "medium"
            burst = random.randint(4, 7)
            prio = random.choice([1, 2, 3])
        else:
            category = "long"
            burst = random.randint(8, 12)
            prio = random.choice([1, 2])

        j_type, args = random.choice(job_types[category])
        arrival = current_arrival
        current_arrival += random.choice([0, 1, 1, 2])

        jobs.append({
            "pid": pid,
            "name": f"lab-{j_type}-{pid}",
            "job_type": j_type,
            "args": args,
            "burst": burst,
            "arrival": arrival,
            "priority": prio,
            "category": category,
        })

    return jobs


def main():
    parser = argparse.ArgumentParser(description="Generate NEXUS-OS cluster workload trace.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--count", type=int, default=15, help="Number of jobs in workload trace")
    parser.add_argument("--output", type=str, default=os.path.join(os.path.dirname(__file__), "lab_trace.json"),
                        help="Output path for trace JSON file")
    args = parser.parse_args()

    trace = generate_workload(count=args.count, seed=args.seed)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2)

    print(f"Generated {len(trace)} jobs in {args.output} (seed={args.seed})")


if __name__ == "__main__":
    main()
