"""NEXUS-OS Phase 4 Unit Tests: Cache, Page Replacement, & Local Synchronization.
Tests in-memory node block caching, trace logging, replay & Belady's Anomaly,
RWLock reader/writer preference and starvation, CountingSemaphore rate-limiting,
BoundedQueue monitor pattern, Dining Philosophers deadlock vs hierarchical ordering,
and storage race condition demonstrations.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from coordinator.file_manager.page_replacement import (
    simulate as page_sim,
    beladys_anomaly_demo,
    replay_trace,
)
from coordinator.synchronization.primitives import (
    CountingSemaphore,
    BoundedQueue,
    producer_consumer,
    mutex_demo,
    file_store_race_demo,
)
from coordinator.synchronization.readers_writers import (
    RWLock,
    demonstrate_starvation,
)
from demo.philosophers import run_philosophers
from nodes.block_store import BlockStore
from nodes.node_cache import NodeBlockCache
from tools.vmstat_snapshot import get_vm_snapshot


class TestPhase4CacheSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="nexus_phase4_test_")
        self.trace_file = os.path.join(self.temp_dir, "access_trace.jsonl")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_node_block_cache_lru_and_fifo(self):
        """Tests NodeBlockCache eviction policies (LRU, FIFO) and access trace recording."""
        # 1. LRU Cache with capacity 2
        lru_cache = NodeBlockCache("node-1", capacity=2, policy="LRU", trace_path=self.trace_file)
        lru_cache.put("blk_1", b"Data-1")
        lru_cache.put("blk_2", b"Data-2")

        # Access blk_1 so it becomes most recently used
        self.assertEqual(lru_cache.get("blk_1"), b"Data-1")

        # Insert blk_3 -> should evict blk_2 (least recently used)
        lru_cache.put("blk_3", b"Data-3")
        self.assertIsNone(lru_cache.get("blk_2"))
        self.assertEqual(lru_cache.get("blk_1"), b"Data-1")
        self.assertEqual(lru_cache.get("blk_3"), b"Data-3")

        # 2. FIFO Cache with capacity 2
        fifo_cache = NodeBlockCache("node-2", capacity=2, policy="FIFO", trace_path=self.trace_file)
        fifo_cache.put("blk_A", b"Data-A")
        fifo_cache.put("blk_B", b"Data-B")
        # Access blk_A (does NOT affect FIFO order)
        fifo_cache.get("blk_A")
        # Insert blk_C -> should evict blk_A (first inserted)
        fifo_cache.put("blk_C", b"Data-C")
        self.assertIsNone(fifo_cache.get("blk_A"))
        self.assertEqual(fifo_cache.get("blk_B"), b"Data-B")
        self.assertEqual(fifo_cache.get("blk_C"), b"Data-C")

        # 3. Verify access trace file was written
        self.assertTrue(os.path.exists(self.trace_file))
        with open(self.trace_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        self.assertGreaterEqual(len(lines), 6)
        self.assertEqual(lines[0]["block_id"], "blk_1")

    def test_block_store_cache_integration(self):
        """Tests that BlockStore serves repeated reads from cache and invalidates on delete/corrupt."""
        bs = BlockStore(self.temp_dir, "node-1", cache_capacity=3, cache_policy="LRU")

        # Put block
        bs.put_block({"block_id": "blk_hot", "data": "Hot Cached Content"})

        # Read block: should be served from cache
        res1 = bs.get_block({"block_id": "blk_hot"})
        self.assertEqual(res1["type"], "OK")
        self.assertEqual(res1["data"], "Hot Cached Content")
        self.assertEqual(res1.get("source"), "cache")

        # Corrupt block: invalidates cache
        bs.corrupt_block({"block_id": "blk_hot"})
        # Read block now gets corrupted data from disk and detects mismatch
        res2 = bs.get_block({"block_id": "blk_hot"})
        self.assertEqual(res2.get("source"), "disk")
        self.assertEqual(res2["data"], "CORRUPTED_BLOCK_DATA")

        # Delete block
        bs.delete_block({"block_id": "blk_hot"})
        res3 = bs.get_block({"block_id": "blk_hot"})
        self.assertEqual(res3["type"], "ERROR")

    def test_beladys_anomaly_and_page_replacement(self):
        """Verifies Belady's Anomaly on FIFO [1,2,3,4,1,2,5,1,2,3,4,5] and monotonic stack behavior."""
        res = beladys_anomaly_demo()
        self.assertTrue(res["anomaly_detected"])

        comp = res["comparison"]
        # FIFO 3 frames -> 9 faults; FIFO 4 frames -> 10 faults (ANOMALY!)
        self.assertEqual(comp["FIFO"][3]["faults"], 9)
        self.assertEqual(comp["FIFO"][4]["faults"], 10)

        # LRU (Stack algorithm): 3 frames -> 10 faults; 4 frames -> 8 faults (Monotonically improves)
        self.assertEqual(comp["LRU"][3]["faults"], 10)
        self.assertEqual(comp["LRU"][4]["faults"], 8)
        self.assertLess(comp["LRU"][4]["faults"], comp["LRU"][3]["faults"])

        # Optimal: 3 frames -> 7 faults; 4 frames -> 6 faults
        self.assertEqual(comp["Optimal"][3]["faults"], 7)
        self.assertEqual(comp["Optimal"][4]["faults"], 6)

    def test_cache_replay_trace(self):
        """Tests trace replay on recorded or synthetic references."""
        refs = ["blk_1", "blk_2", "blk_3", "blk_1", "blk_4", "blk_1", "blk_2"]
        rep = replay_trace(refs, frame_sizes=[2, 3])
        self.assertEqual(rep["reference_count"], 7)
        self.assertIn(2, rep["by_frame"])
        self.assertIn(3, rep["by_frame"])
        # With 3 frames, faults should be less than or equal to 2 frames
        res2 = {r["algo"]: r["faults"] for r in rep["by_frame"][2]}
        res3 = {r["algo"]: r["faults"] for r in rep["by_frame"][3]}
        self.assertLessEqual(res3["LRU"], res2["LRU"])

    def test_rwlock_reader_writer_starvation(self):
        """Tests RWLock mutual exclusion and verifies writer progress under writer-preference."""
        rw = RWLock(preference="writer")
        read_concurrent = [0]
        max_concurrent_readers = [0]
        lock = threading.Lock()

        def reader_task():
            with rw.read_locked():
                with lock:
                    read_concurrent[0] += 1
                    if read_concurrent[0] > max_concurrent_readers[0]:
                        max_concurrent_readers[0] = read_concurrent[0]
                time.sleep(0.02)
                with lock:
                    read_concurrent[0] -= 1

        threads = [threading.Thread(target=reader_task) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        # Multiple readers could read concurrently
        self.assertGreaterEqual(max_concurrent_readers[0], 2)

        # Starvation demonstration: writer preference must allow writer to acquire lock
        starv_res = demonstrate_starvation(preference="writer", test_time_sec=0.2)
        self.assertTrue(starv_res["writer_acquired"])

    def test_counting_semaphore_and_bounded_queue(self):
        """Tests CountingSemaphore permit counting and BoundedQueue monitor pattern."""
        # 1. Semaphore with 2 permits
        sem = CountingSemaphore(initial=2, max_permits=2)
        self.assertTrue(sem.acquire(timeout=0.1))
        self.assertTrue(sem.acquire(timeout=0.1))
        self.assertEqual(sem.permits, 0)
        # Third acquire should timeout
        self.assertFalse(sem.acquire(timeout=0.05))
        sem.release()
        self.assertEqual(sem.permits, 1)
        self.assertTrue(sem.acquire(timeout=0.05))

        # 2. BoundedQueue with capacity 3
        bq = BoundedQueue(capacity=3)
        self.assertTrue(bq.put("A"))
        self.assertTrue(bq.put("B"))
        self.assertTrue(bq.put("C"))
        self.assertTrue(bq.is_full())
        # Put on full queue times out
        self.assertFalse(bq.put("D", timeout=0.05))

        # Get item
        self.assertEqual(bq.get(), "A")
        self.assertFalse(bq.is_full())
        self.assertTrue(bq.put("D"))
        self.assertEqual(bq.metrics()["high_watermark"], 3)
        self.assertEqual(bq.metrics()["total_produced"], 4)

    def test_dining_philosophers(self):
        """Tests Dining Philosophers deadlock under naive mode vs deadlock-free under hierarchical ordering."""
        # Hierarchical mode: all 5 philosophers complete without deadlock
        hier = run_philosophers(mode="hierarchical", rounds=2, num_philosophers=5)
        self.assertFalse(hier["deadlocked"])
        self.assertEqual(hier["total_meals"], 10)

        # Naive mode: circular wait causes deadlock or meals eaten < expected
        naive = run_philosophers(mode="naive", rounds=1, num_philosophers=5)
        self.assertTrue(naive["deadlocked"] or naive["total_meals"] < naive["expected_meals"])

    def test_storage_race_condition_demo(self):
        """Tests file store race condition: lost updates without mutex vs exact count with mutex."""
        res = file_store_race_demo(threads=4, iterations=100)
        self.assertEqual(res["expected"], 400)
        self.assertEqual(res["with_lock"], 400)
        # Without lock, concurrent writes clobber each other
        self.assertTrue(res["race_detected"])
        self.assertGreater(res["lost_updates"], 0)

    def test_vmstat_snapshot(self):
        """Tests virtual memory telemetry snapshot extraction."""
        snap = get_vm_snapshot()
        self.assertIn("virtual_memory", snap)
        self.assertIn("swap_memory", snap)
        self.assertGreater(snap["virtual_memory"]["total_mb"], 0)


if __name__ == "__main__":
    unittest.main()
