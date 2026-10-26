import threading


class LamportClock:
    """Module 7. tick() for local events/sends, update(t) on receive."""
    def __init__(self):
        self.t = 0
        self._lock = threading.Lock()
    def tick(self):
        with self._lock:
            self.t += 1
            return self.t
    def update(self, received):
        with self._lock:
            self.t = max(self.t, received) + 1
            return self.t

