"""NEXUS-OS Synchronization Primitives & Concurrency Demos.
Implements CountingSemaphore, BoundedQueue (monitor pattern),
producer-consumer pipeline, and race condition demonstrations.
Concept: Semaphores (Dijkstra 1965), Monitors (Hoare 1974), Mutual Exclusion.
"""

import collections
import os
import tempfile
import threading
import time


class CountingSemaphore:
    """Thread-safe Counting Semaphore for resource pooling and rate limiting (e.g. max in-flight network transfers).
    Concept: Counting semaphore (Dijkstra 1965).
    """

    def __init__(self, initial=2, max_permits=None):
        if initial < 0:
            raise ValueError("Initial semaphore permits must be >= 0")
        self._initial = initial
        self._max = max_permits
        self._permits = initial
        self._cond = threading.Condition(threading.Lock())
        self.acquired_total = 0
        self.released_total = 0

    def acquire(self, timeout=None):
        """Acquires a permit, blocking if permits == 0."""
        end_time = (time.time() + timeout) if timeout is not None else None
        with self._cond:
            while self._permits <= 0:
                if timeout is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                else:
                    self._cond.wait()
            self._permits -= 1
            self.acquired_total += 1
            return True

    def release(self):
        """Releases a permit and wakes a waiting thread."""
        with self._cond:
            if self._max is not None and self._permits >= self._max:
                raise ValueError("Semaphore permit overflow exceeding max_permits")
            self._permits += 1
            self.released_total += 1
            self._cond.notify()

    @property
    def permits(self):
        with self._cond:
            return self._permits

    @property
    def in_flight(self):
        with self._cond:
            return self._initial - self._permits


class BoundedQueue:
    """Thread-safe Bounded Buffer / Monitor queue with metrics instrumentation.
    Concept: Monitor pattern with condition variables (Hoare 1974).
    """

    def __init__(self, capacity=10):
        self.capacity = max(1, int(capacity))
        self._buf = collections.deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

        # Performance instrumentation
        self.total_produced = 0
        self.total_consumed = 0
        self.high_watermark = 0

    def put(self, item, timeout=None):
        """Adds an item to the queue, blocking if full."""
        end_time = (time.time() + timeout) if timeout is not None else None
        with self._not_full:
            while len(self._buf) >= self.capacity:
                if timeout is not None:
                    rem = end_time - time.time()
                    if rem <= 0:
                        return False
                    self._not_full.wait(rem)
                else:
                    self._not_full.wait()

            self._buf.append(item)
            self.total_produced += 1
            if len(self._buf) > self.high_watermark:
                self.high_watermark = len(self._buf)
            self._not_empty.notify()
            return True

    def get(self, timeout=None):
        """Removes and returns an item from the queue, blocking if empty."""
        end_time = (time.time() + timeout) if timeout is not None else None
        with self._not_empty:
            while len(self._buf) == 0:
                if timeout is not None:
                    rem = end_time - time.time()
                    if rem <= 0:
                        return None
                    self._not_empty.wait(rem)
                else:
                    self._not_empty.wait()

            item = self._buf.popleft()
            self.total_consumed += 1
            self._not_full.notify()
            return item

    def qsize(self):
        with self._lock:
            return len(self._buf)

    def is_empty(self):
        with self._lock:
            return len(self._buf) == 0

    def is_full(self):
        with self._lock:
            return len(self._buf) >= self.capacity

    def metrics(self):
        with self._lock:
            return {
                "capacity": self.capacity,
                "current_size": len(self._buf),
                "high_watermark": self.high_watermark,
                "total_produced": self.total_produced,
                "total_consumed": self.total_consumed,
            }


def producer_consumer(items=6, size=2):
    """Bounded buffer using two semaphores + a mutex. Returns the event log.
    Preserves exact backward-compatible signature and behavior for tests/test_core.py.
    """
    buf, log = collections.deque(), []
    empty, full, mutex = threading.Semaphore(size), threading.Semaphore(0), threading.Lock()

    def prod():
        for i in range(items):
            empty.acquire()
            with mutex:
                buf.append(i)
                log.append(f"Producer put {i}  buffer={list(buf)}")
            full.release()

    def cons():
        for _ in range(items):
            full.acquire()
            with mutex:
                x = buf.popleft()
                log.append(f"Consumer got {x}  buffer={list(buf)}")
            empty.release()

    ts = [threading.Thread(target=prod), threading.Thread(target=cons)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return log


def mutex_demo(threads=4, n=1500):
    """Shared counter incremented by many threads, with and without a mutex.
    Preserves exact backward-compatible signature and behavior for tests/test_core.py.
    """
    res = {}
    for use in (False, True):
        total, lock = [0], threading.Lock()

        def work():
            for _ in range(n):
                if use:
                    with lock:
                        v = total[0]
                        time.sleep(0)
                        total[0] = v + 1
                else:
                    v = total[0]
                    time.sleep(0)
                    total[0] = v + 1

        ts = [threading.Thread(target=work) for _ in range(threads)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        res["with_mutex" if use else "without_mutex"] = total[0]
    return {"expected": threads * n, **res}


def file_store_race_demo(threads=4, iterations=250):
    """Demonstrates lost-update race conditions on persistent storage.
    Multiple threads perform read-modify-write on a shared storage file.
    Without synchronization: lost updates cause final count < expected.
    With synchronization: exact count is guaranteed.
    """
    temp_dir = tempfile.mkdtemp(prefix="nexus_race_")
    unprotected_path = os.path.join(temp_dir, "unprotected.txt")
    protected_path = os.path.join(temp_dir, "protected.txt")
    lock = threading.Lock()

    # Initial file value: 0
    with open(unprotected_path, "w") as f:
        f.write("0")
    with open(protected_path, "w") as f:
        f.write("0")

    def unprotected_worker():
        for _ in range(iterations):
            with open(unprotected_path, "r") as f:
                val = int(f.read().strip() or "0")
            time.sleep(0.0001)  # Context switch window
            with open(unprotected_path, "w") as f:
                f.write(str(val + 1))

    def protected_worker():
        for _ in range(iterations):
            with lock:
                with open(protected_path, "r") as f:
                    val = int(f.read().strip() or "0")
                time.sleep(0.0001)
                with open(protected_path, "w") as f:
                    f.write(str(val + 1))

    ts1 = [threading.Thread(target=unprotected_worker) for _ in range(threads)]
    for t in ts1: t.start()
    for t in ts1: t.join()

    ts2 = [threading.Thread(target=protected_worker) for _ in range(threads)]
    for t in ts2: t.start()
    for t in ts2: t.join()

    with open(unprotected_path, "r") as f:
        unprotected_final = int(f.read().strip())
    with open(protected_path, "r") as f:
        protected_final = int(f.read().strip())

    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    expected = threads * iterations
    return {
        "expected": expected,
        "without_lock": unprotected_final,
        "with_lock": protected_final,
        "lost_updates": expected - unprotected_final,
        "race_detected": unprotected_final < expected,
    }
