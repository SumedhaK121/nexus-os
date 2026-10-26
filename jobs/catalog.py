"""NEXUS-OS Jobs Catalog.
Defines resource profiles, parameter presets, and execution descriptors for cluster jobs.
Concept: Workload classification and resource request definitions (Kubernetes resource requests / Slurm partitions).
"""

import os
import sys

JOBS_DIR = os.path.dirname(os.path.abspath(__file__))

CATALOG = {
    "wordcount": {
        "script": os.path.join(JOBS_DIR, "wordcount.py"),
        "description": "Word frequency counter (I/O + CPU)",
        "resources": {"cpu_slots": 1, "mem_units": 1, "io_slots": 2},
        "default_args": [],
        "category": "io_heavy",
    },
    "primes": {
        "script": os.path.join(JOBS_DIR, "primes.py"),
        "description": "Prime sieve computation (CPU-bound)",
        "resources": {"cpu_slots": 2, "mem_units": 1, "io_slots": 0},
        "default_args": ["120000"],
        "category": "cpu_heavy",
    },
    "compress": {
        "script": os.path.join(JOBS_DIR, "compress.py"),
        "description": "Zlib block stream compression (CPU + I/O)",
        "resources": {"cpu_slots": 1, "mem_units": 2, "io_slots": 1},
        "default_args": [],
        "category": "balanced",
    },
    "matmul": {
        "script": os.path.join(JOBS_DIR, "matmul.py"),
        "description": "Dense NxN float matrix multiplication (CPU + Memory)",
        "resources": {"cpu_slots": 2, "mem_units": 2, "io_slots": 0},
        "default_args": ["80"],
        "category": "compute_memory",
    },
    "iosleep": {
        "script": os.path.join(JOBS_DIR, "iosleep.py"),
        "description": "Simulated I/O wait and device blocking",
        "resources": {"cpu_slots": 1, "mem_units": 1, "io_slots": 2},
        "default_args": ["1.5"],
        "category": "io_wait",
    },
    "sim": {
        "script": None,
        "description": "Simulated synthetic CPU work",
        "resources": {"cpu_slots": 1, "mem_units": 1, "io_slots": 0},
        "default_args": [],
        "category": "simulated",
    },
}


def get_profile(job_type):
    """Retrieve resource vector [cpu_slots, mem_units, io_slots] for a job type."""
    meta = CATALOG.get(job_type, CATALOG["sim"])
    res = meta["resources"]
    return [res["cpu_slots"], res["mem_units"], res["io_slots"]]


def get_command(job_type, args=None):
    """Constructs the command list for subprocess execution."""
    meta = CATALOG.get(job_type)
    if not meta or not meta["script"]:
        return None
    py_exec = sys.executable
    cmd = [py_exec, meta["script"]]
    if args:
        cmd.extend([str(a) for a in args])
    elif meta["default_args"]:
        cmd.extend(meta["default_args"])
    return cmd
