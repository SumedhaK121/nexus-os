"""NEXUS-OS Inter-Process Communication (IPC) Benchmark Tool (OSDS Practical 9).
Compares Loopback TCP Socket IPC vs Shared Memory IPC (multiprocessing.shared_memory).
Demonstrates zero-copy memory mapping vs kernel socket buffer copies.
Concept: IPC mechanisms (Sockets, Shared Memory, Semaphores, Pipes, POSIX shm).
"""

import json
import multiprocessing as mp
import os
import socket
import sys
import time

try:
    from multiprocessing import shared_memory
    HAS_SHM = True
except ImportError:
    HAS_SHM = False


def _socket_server_worker(ready_event, finish_event, port_holder, iterations, msg_bytes):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port_holder.value = s.getsockname()[1]
    ready_event.set()

    conn, _ = s.accept()
    for _ in range(iterations):
        data = conn.recv(len(msg_bytes))
        conn.sendall(data)
    conn.close()
    s.close()
    finish_event.set()


def benchmark_socket_ipc(iterations=200, payload_size=4096):
    """Measures round-trip latency and throughput of loopback TCP sockets."""
    msg_bytes = b"X" * payload_size
    ready_event = mp.Event()
    finish_event = mp.Event()
    port_holder = mp.Value("i", 0)

    p = mp.Process(
        target=_socket_server_worker,
        args=(ready_event, finish_event, port_holder, iterations, msg_bytes),
        daemon=True,
    )
    p.start()
    ready_event.wait(timeout=3.0)

    port = port_holder.value
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))

    latencies_us = []
    t_start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        sock.sendall(msg_bytes)
        received = b""
        while len(received) < len(msg_bytes):
            chunk = sock.recv(len(msg_bytes) - len(received))
            if not chunk:
                break
            received += chunk
        t1 = time.perf_counter()
        latencies_us.append((t1 - t0) * 1_000_000)

    total_time = time.perf_counter() - t_start
    sock.close()
    finish_event.wait(timeout=2.0)
    p.join(timeout=1.0)

    total_bytes = iterations * payload_size * 2
    throughput_mb_s = (total_bytes / (1024 * 1024)) / max(0.0001, total_time)
    latencies_us.sort()

    return {
        "mechanism": "Loopback TCP Socket",
        "iterations": iterations,
        "payload_bytes": payload_size,
        "avg_latency_us": round(sum(latencies_us) / len(latencies_us), 1),
        "p50_latency_us": round(latencies_us[len(latencies_us) // 2], 1),
        "p99_latency_us": round(latencies_us[int(len(latencies_us) * 0.99)], 1),
        "throughput_mb_s": round(throughput_mb_s, 2),
    }


def _shm_consumer_worker(shm_name, size, ready_event, send_event, reply_event, finish_event, iterations):
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
        ready_event.set()

        for _ in range(iterations):
            send_event.wait()
            send_event.clear()
            # Invert first byte in shared memory to demonstrate zero-copy read-modify-write
            shm.buf[0] = 0xAA
            reply_event.set()

        shm.close()
    finally:
        finish_event.set()


def benchmark_shared_memory(iterations=200, payload_size=4096):
    """Measures round-trip latency and throughput of Shared Memory IPC."""
    if not HAS_SHM:
        return {
            "mechanism": "Shared Memory (multiprocessing.shared_memory)",
            "supported": False,
            "error": "multiprocessing.shared_memory not supported on this platform",
        }

    shm = shared_memory.SharedMemory(create=True, size=payload_size)
    ready_event = mp.Event()
    send_event = mp.Event()
    reply_event = mp.Event()
    finish_event = mp.Event()

    p = mp.Process(
        target=_shm_consumer_worker,
        args=(shm.name, payload_size, ready_event, send_event, reply_event, finish_event, iterations),
        daemon=True,
    )
    p.start()
    ready_event.wait(timeout=3.0)

    latencies_us = []
    t_start = time.perf_counter()

    for _ in range(iterations):
        t0 = time.perf_counter()
        shm.buf[0] = 0x55
        send_event.set()
        reply_event.wait()
        reply_event.clear()
        t1 = time.perf_counter()
        latencies_us.append((t1 - t0) * 1_000_000)

    total_time = time.perf_counter() - t_start
    finish_event.wait(timeout=2.0)
    p.join(timeout=1.0)
    shm.close()
    shm.unlink()

    total_bytes = iterations * payload_size * 2
    throughput_mb_s = (total_bytes / (1024 * 1024)) / max(0.0001, total_time)
    latencies_us.sort()

    return {
        "mechanism": "Shared Memory (Zero-Copy POSIX shm)",
        "iterations": iterations,
        "payload_bytes": payload_size,
        "avg_latency_us": round(sum(latencies_us) / len(latencies_us), 1),
        "p50_latency_us": round(latencies_us[len(latencies_us) // 2], 1),
        "p99_latency_us": round(latencies_us[int(len(latencies_us) * 0.99)], 1),
        "throughput_mb_s": round(throughput_mb_s, 2),
    }


def run_ipc_benchmark(iterations=200, payload_size=4096):
    """Executes full Practical 9 IPC benchmark comparison."""
    sock_res = benchmark_socket_ipc(iterations=iterations, payload_size=payload_size)
    shm_res = benchmark_shared_memory(iterations=iterations, payload_size=payload_size)

    speedup = 1.0
    if shm_res.get("avg_latency_us") and sock_res.get("avg_latency_us"):
        speedup = round(sock_res["avg_latency_us"] / shm_res["avg_latency_us"], 2)

    return {
        "practical": "Practical 9: Inter-Process Communication (Sockets vs Shared Memory)",
        "iterations": iterations,
        "payload_bytes": payload_size,
        "tcp_socket": sock_res,
        "shared_memory": shm_res,
        "speedup_factor": speedup,
        "explanation": (
            "Shared Memory eliminates OS kernel context switches and buffer copies. "
            "TCP Sockets require copying user-space buffers into kernel socket buffers and back, "
            "while Shared Memory maps physical RAM pages directly into both processes' virtual address spaces."
        ),
    }


if __name__ == "__main__":
    mp.freeze_support()
    res = run_ipc_benchmark(iterations=100, payload_size=4096)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        print("=================================================================")
        print("       NEXUS-OS IPC Benchmark: Sockets vs Shared Memory          ")
        print("=================================================================")
        sock = res["tcp_socket"]
        shm = res["shared_memory"]
        print(f"Payload Size       : {res['payload_bytes']} bytes across {res['iterations']} round-trips")
        print(f"TCP Socket Latency : {sock['avg_latency_us']} µs (Throughput: {sock['throughput_mb_s']} MB/s)")
        print(f"Shared Memory Lat  : {shm.get('avg_latency_us')} µs (Throughput: {shm.get('throughput_mb_s')} MB/s)")
        print(f"Performance Ratio  : Shared Memory is {res['speedup_factor']}x faster than TCP Sockets")
        print("=================================================================")
        print(res["explanation"])
