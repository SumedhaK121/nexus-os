"""NEXUS-OS Virtual Memory & System Telemetry Snapshot Tool.
Inspects physical RAM, page cache, swap utilization, and memory pressure metrics.
Concept: Virtual memory paging, swap space, page frame allocation (Linux /proc/meminfo & vmstat).
"""

import json
import os
import sys

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_vm_snapshot():
    """Captures a snapshot of host virtual memory and swap statistics."""
    if HAS_PSUTIL:
        try:
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()
            return {
                "source": "psutil",
                "virtual_memory": {
                    "total_mb": round(vm.total / (1024 * 1024), 1),
                    "available_mb": round(vm.available / (1024 * 1024), 1),
                    "used_mb": round(vm.used / (1024 * 1024), 1),
                    "percent": vm.percent,
                },
                "swap_memory": {
                    "total_mb": round(sw.total / (1024 * 1024), 1),
                    "used_mb": round(sw.used / (1024 * 1024), 1),
                    "free_mb": round(sw.free / (1024 * 1024), 1),
                    "percent": sw.percent,
                },
                "os": sys.platform,
            }
        except Exception as e:
            return {"source": "error", "error": str(e)}

    # Fallback when psutil is unavailable
    return {
        "source": "simulated",
        "virtual_memory": {
            "total_mb": 8192.0,
            "available_mb": 4096.0,
            "used_mb": 4096.0,
            "percent": 50.0,
        },
        "swap_memory": {
            "total_mb": 2048.0,
            "used_mb": 256.0,
            "free_mb": 1792.0,
            "percent": 12.5,
        },
        "os": sys.platform,
        "note": "psutil not available; returning baseline metrics",
    }


def print_vm_snapshot():
    data = get_vm_snapshot()
    vm = data.get("virtual_memory", {})
    sw = data.get("swap_memory", {})

    print("========================================")
    print("      NEXUS-OS Virtual Memory Snapshot   ")
    print("========================================")
    print(f"OS Platform     : {data.get('os')}")
    print(f"Collector       : {data.get('source')}")
    print("--- Virtual Memory (RAM) ---")
    print(f"Total RAM       : {vm.get('total_mb')} MB")
    print(f"Available RAM   : {vm.get('available_mb')} MB")
    print(f"Used RAM        : {vm.get('used_mb')} MB ({vm.get('percent')}%)")
    print("--- Swap Space ---")
    print(f"Total Swap      : {sw.get('total_mb')} MB")
    print(f"Used Swap       : {sw.get('used_mb')} MB ({sw.get('percent')}%)")
    print(f"Free Swap       : {sw.get('free_mb')} MB")
    print("========================================")


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(get_vm_snapshot(), indent=2))
    else:
        print_vm_snapshot()
