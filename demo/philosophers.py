"""NEXUS-OS Demo: Dining Philosophers (Deadlock vs Resource Hierarchy Solution).
Simulates 5 philosophers competing for 5 shared forks.
Mode 1: Naive symmetric acquisition (Left then Right fork) -> Circular wait deadlock!
Mode 2: Resource ordering / hierarchy (Dijkstra 1965) -> Deadlock-free execution!
Concept: Deadlock prevention via breaking Coffman condition 4 (Circular Wait).
"""

import threading
import time


class Philosopher(threading.Thread):
    def __init__(self, idx, left_fork, right_fork, rounds=2, mode="hierarchical", log=None, timeout=0.3):
        super().__init__(name=f"Philosopher-{idx}")
        self.idx = idx
        self.left_id = idx
        self.right_id = (idx + 1) % 5
        self.left_fork = left_fork
        self.right_fork = right_fork
        self.rounds = rounds
        self.mode = mode
        self.log = log if log is not None else []
        self.timeout = timeout
        self.meals_eaten = 0
        self.deadlocked = False

    def run(self):
        for r in range(self.rounds):
            self._think()
            if self.mode == "naive":
                success = self._eat_naive(r)
            else:
                success = self._eat_hierarchical(r)

            if not success:
                self.deadlocked = True
                break

    def _think(self):
        time.sleep(0.005)

    def _eat_naive(self, r):
        # Naive: always left then right. If all philosophers pick left simultaneously, circular wait occurs!
        self.left_fork.acquire()
        self.log.append(f"[T] P{self.idx} picked Left Fork {self.left_id}")
        time.sleep(0.01)  # Window where all philosophers pick their left fork

        acquired_right = self.right_fork.acquire(timeout=self.timeout)
        if not acquired_right:
            self.log.append(f"[DEADLOCK] P{self.idx} timed out waiting for Right Fork {self.right_id}! Circular wait detected.")
            self.left_fork.release()
            return False

        # Eat
        self.log.append(f"[EAT] P{self.idx} eating meal {r+1} with forks {self.left_id} and {self.right_id}")
        time.sleep(0.01)
        self.meals_eaten += 1

        self.right_fork.release()
        self.left_fork.release()
        return True

    def _eat_hierarchical(self, r):
        # Dijkstra's Resource Hierarchy: always acquire the lower-numbered fork first!
        # For P4, left is 4, right is 0 -> acquires 0 first, then 4!
        first_fork = self.left_fork if self.left_id < self.right_id else self.right_fork
        second_fork = self.right_fork if self.left_id < self.right_id else self.left_fork
        first_id = min(self.left_id, self.right_id)
        second_id = max(self.left_id, self.right_id)

        first_fork.acquire()
        self.log.append(f"[T] P{self.idx} acquired Fork {first_id} (lower)")
        time.sleep(0.005)

        second_fork.acquire()
        self.log.append(f"[T] P{self.idx} acquired Fork {second_id} (higher)")

        # Eat
        self.log.append(f"[EAT] P{self.idx} eating meal {r+1} with forks {first_id} and {second_id}")
        time.sleep(0.01)
        self.meals_eaten += 1

        second_fork.release()
        first_fork.release()
        return True


def run_philosophers(mode="hierarchical", rounds=2, num_philosophers=5):
    """Executes the dining philosophers simulation under naive or hierarchical ordering."""
    forks = [threading.Lock() for _ in range(num_philosophers)]
    log = []
    philosophers = []

    for i in range(num_philosophers):
        p = Philosopher(
            idx=i,
            left_fork=forks[i],
            right_fork=forks[(i + 1) % num_philosophers],
            rounds=rounds,
            mode=mode,
            log=log,
            timeout=0.25,
        )
        philosophers.append(p)

    start = time.time()
    for p in philosophers:
        p.start()
    for p in philosophers:
        p.join()
    elapsed = time.time() - start

    deadlocked_count = sum(1 for p in philosophers if p.deadlocked)
    total_meals = sum(p.meals_eaten for p in philosophers)
    expected_meals = num_philosophers * rounds

    return {
        "mode": mode,
        "philosophers": num_philosophers,
        "rounds": rounds,
        "total_meals": total_meals,
        "expected_meals": expected_meals,
        "deadlocked": deadlocked_count > 0,
        "deadlocked_count": deadlocked_count,
        "elapsed_seconds": round(elapsed, 4),
        "log": log[-20:],
        "explanation": (
            "Resource Hierarchy (Dijkstra 1965) establishes a global total ordering on resources: "
            "F_0 < F_1 < F_2 < F_3 < F_4. Since philosophers always acquire the lower-numbered fork first, "
            "Philosopher 4 acquires Fork 0 before Fork 4. This breaks Coffman condition 4 (Circular Wait), "
            "preventing deadlock."
            if mode == "hierarchical"
            else "Naive symmetric acquisition allows every philosopher to hold their left fork while waiting "
                 "indefinitely for their right fork, forming a directed circular wait cycle: P0 -> P1 -> P2 -> P3 -> P4 -> P0."
        ),
    }


if __name__ == "__main__":
    print("--- Running Naive Dining Philosophers ---")
    naive_res = run_philosophers(mode="naive", rounds=1)
    print(f"Naive result: deadlocked={naive_res['deadlocked']}, meals={naive_res['total_meals']}/{naive_res['expected_meals']}")

    print("\n--- Running Hierarchical Dining Philosophers ---")
    hier_res = run_philosophers(mode="hierarchical", rounds=2)
    print(f"Hierarchical result: deadlocked={hier_res['deadlocked']}, meals={hier_res['total_meals']}/{hier_res['expected_meals']}")
