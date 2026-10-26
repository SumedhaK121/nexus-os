"""NEXUS-OS Vector Clock Implementation.
Implements Fidge-Mattern Vector Clocks for causal ordering and concurrency detection.
Supports tick, merge, update, serialization, and partial-order comparisons:
BEFORE (<), AFTER (>), EQUAL (==), and CONCURRENT (||).
Concept: Vector Clocks (Fidge 1988, Mattern 1989), Version Vectors in DynamoDB / Riak / Cassandra.
"""

import threading


REL_BEFORE = "BEFORE"
REL_AFTER = "AFTER"
REL_EQUAL = "EQUAL"
REL_CONCURRENT = "CONCURRENT"
BEFORE = REL_BEFORE
AFTER = REL_AFTER
EQUAL = REL_EQUAL
CONCURRENT = REL_CONCURRENT


class VectorClock:
    """Thread-safe Vector Clock representing causal history across distributed processes."""

    REL_BEFORE = REL_BEFORE
    REL_AFTER = REL_AFTER
    REL_EQUAL = REL_EQUAL
    REL_CONCURRENT = REL_CONCURRENT

    def __init__(self, node_id=None, initial=None):
        self.node_id = str(node_id) if node_id is not None else None
        self.lock = threading.Lock()
        self.clock = dict(initial or {})
        if self.node_id and self.node_id not in self.clock:
            self.clock[self.node_id] = 0

    def tick(self):
        """Increments local counter and returns a snapshot dictionary."""
        with self.lock:
            if self.node_id:
                self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
            return dict(self.clock)

    def update(self, other_dict):
        """Merges another vector clock and increments local counter on message receipt."""
        with self.lock:
            if other_dict and isinstance(other_dict, dict):
                for k, v in other_dict.items():
                    self.clock[k] = max(self.clock.get(k, 0), int(v))
            if self.node_id:
                self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
            return dict(self.clock)

    def merge(self, other_dict):
        """Pure merge without incrementing local counter."""
        with self.lock:
            if other_dict and isinstance(other_dict, dict):
                for k, v in other_dict.items():
                    self.clock[k] = max(self.clock.get(k, 0), int(v))
            return dict(self.clock)

    def to_dict(self):
        with self.lock:
            return dict(self.clock)

    def clone(self):
        with self.lock:
            return VectorClock(self.node_id, initial=dict(self.clock))

    def __repr__(self):
        with self.lock:
            return f"VC({self.node_id}: {dict(self.clock)})"

    @classmethod
    def compare(cls, vc1, vc2):
        """Compares two vector clock dictionaries.
        Returns:
          - 'EQUAL' if vc1 == vc2
          - 'BEFORE' if vc1 strictly happened before vc2 (vc1 < vc2)
          - 'AFTER' if vc1 strictly happened after vc2 (vc1 > vc2)
          - 'CONCURRENT' if vc1 and vc2 are causally independent / conflicting (vc1 || vc2)
        """
        d1 = dict(vc1 or {})
        d2 = dict(vc2 or {})
        all_keys = set(d1.keys()).union(set(d2.keys()))

        less = False
        greater = False

        for k in all_keys:
            v1 = d1.get(k, 0)
            v2 = d2.get(k, 0)
            if v1 < v2:
                less = True
            elif v1 > v2:
                greater = True

        if less and greater:
            return cls.REL_CONCURRENT
        if less and not greater:
            return cls.REL_BEFORE
        if greater and not less:
            return cls.REL_AFTER
        return cls.REL_EQUAL

    def compare_to(self, other):
        """Compares this clock to another VectorClock or dict."""
        other_dict = other.to_dict() if isinstance(other, VectorClock) else other
        return self.compare(self.to_dict(), other_dict)

    @classmethod
    def are_concurrent(cls, vc1, vc2):
        return cls.compare(vc1, vc2) == cls.REL_CONCURRENT

    @classmethod
    def happens_before(cls, vc1, vc2):
        return cls.compare(vc1, vc2) == cls.REL_BEFORE


def happens_before(vc1, vc2):
    """Returns True if vc1 strictly happened before vc2."""
    return VectorClock.compare(vc1, vc2) == VectorClock.REL_BEFORE


def are_concurrent(vc1, vc2):
    """Returns True if vc1 and vc2 are causally concurrent (neither dominates)."""
    return VectorClock.compare(vc1, vc2) == VectorClock.REL_CONCURRENT
