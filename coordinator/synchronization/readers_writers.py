import threading

class RWLock:
    """Readers-Writers lock: many readers OR one writer."""
    def __init__(self): self._c, self._r, self._w = threading.Condition(), 0, False
    def acquire_read(self):
        with self._c:
            while self._w: self._c.wait()
            self._r += 1
    def release_read(self):
        with self._c: self._r -= 1; self._c.notify_all()
    def acquire_write(self):
        with self._c:
            while self._w or self._r: self._c.wait()
            self._w = True
    def release_write(self):
        with self._c: self._w = False; self._c.notify_all()
