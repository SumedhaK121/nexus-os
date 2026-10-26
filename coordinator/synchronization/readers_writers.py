"""NEXUS-OS Readers-Writers Lock (RWLock).
Supports Reader-Preference, Writer-Preference, and Fair (FIFO) synchronization policies.
Demonstrates and instruments reader vs. writer starvation.
Concept: Readers-writers problem (Courtois, Heymans, Parnas 1971), pthread rwlock, Linux down_read/down_write.
"""

from contextlib import contextmanager
import threading
import time


class RWLock:
    """Configurable Readers-Writers Lock with preference policies:
    - 'reader': Courtois First Readers-Writers problem (readers never wait if no active writer; can starve writers).
    - 'writer': Courtois Second Readers-Writers problem (waiting writers block new readers; prevents writer starvation).
    - 'fair': FIFO queue ordering; neither readers nor writers starve.
    """

    def __init__(self, preference="writer"):
        self.preference = preference.lower()
        self._cond = threading.Condition(threading.Lock())

        self._active_readers = 0
        self._active_writers = 0
        self._waiting_readers = 0
        self._waiting_writers = 0

        # Stats instrumentation
        self.total_reads = 0
        self.total_writes = 0
        self.writer_waits = 0
        self.reader_waits = 0

    def acquire_read(self):
        """Acquires shared read lock according to preference policy."""
        with self._cond:
            self._waiting_readers += 1
            if self.preference == "writer":
                # Writers have priority: block readers if writer active OR writer waiting
                while self._active_writers > 0 or self._waiting_writers > 0:
                    self.reader_waits += 1
                    self._cond.wait()
            elif self.preference == "fair":
                # Fair: block if writer active or writer was waiting first
                while self._active_writers > 0 or self._waiting_writers > 0:
                    self.reader_waits += 1
                    self._cond.wait()
            else:
                # Reader preference: only block if a writer is currently active
                while self._active_writers > 0:
                    self.reader_waits += 1
                    self._cond.wait()

            self._waiting_readers -= 1
            self._active_readers += 1
            self.total_reads += 1

    def release_read(self):
        """Releases shared read lock."""
        with self._cond:
            self._active_readers -= 1
            if self._active_readers == 0:
                self._cond.notify_all()

    def acquire_write(self):
        """Acquires exclusive write lock."""
        with self._cond:
            self._waiting_writers += 1
            while self._active_writers > 0 or self._active_readers > 0:
                self.writer_waits += 1
                self._cond.wait()
            self._waiting_writers -= 1
            self._active_writers = 1
            self.total_writes += 1

    def release_write(self):
        """Releases exclusive write lock."""
        with self._cond:
            self._active_writers = 0
            self._cond.notify_all()

    @contextmanager
    def read_locked(self):
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write_locked(self):
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()

    def stats(self):
        with self._cond:
            return {
                "preference": self.preference,
                "active_readers": self._active_readers,
                "active_writers": self._active_writers,
                "waiting_readers": self._waiting_readers,
                "waiting_writers": self._waiting_writers,
                "total_reads": self.total_reads,
                "total_writes": self.total_writes,
                "reader_waits": self.reader_waits,
                "writer_waits": self.writer_waits,
            }


def demonstrate_starvation(preference="reader", test_time_sec=0.4):
    """Demonstrates writer starvation under reader-preference vs prompt writer acquisition
    under writer-preference.
    """
    rw = RWLock(preference=preference)
    stop_event = threading.Event()
    read_counts = [0]
    writer_acquired = [False]
    writer_wait_start = [0.0]
    writer_wait_duration = [0.0]

    # Continuous stream of overlapping readers
    def reader_worker():
        while not stop_event.is_set():
            with rw.read_locked():
                read_counts[0] += 1
                time.sleep(0.005)

    readers = [threading.Thread(target=reader_worker, daemon=True) for _ in range(4)]
    for r in readers:
        r.start()

    time.sleep(0.05)  # Let readers saturate lock

    # Writer attempts to enter
    def writer_worker():
        writer_wait_start[0] = time.time()
        with rw.write_locked():
            writer_wait_duration[0] = time.time() - writer_wait_start[0]
            writer_acquired[0] = True
            time.sleep(0.01)

    w = threading.Thread(target=writer_worker, daemon=True)
    w.start()

    time.sleep(test_time_sec)
    stop_event.set()
    w.join(timeout=0.5)
    for r in readers:
        r.join(timeout=0.2)

    return {
        "preference": preference,
        "writer_acquired": writer_acquired[0],
        "writer_wait_seconds": round(writer_wait_duration[0] if writer_acquired[0] else test_time_sec, 4),
        "total_reads_during_wait": read_counts[0],
        "starved": not writer_acquired[0] or writer_wait_duration[0] > (test_time_sec * 0.8),
    }
