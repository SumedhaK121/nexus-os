import threading, collections

def producer_consumer(items=6, size=2):
    """Bounded buffer using two semaphores + a mutex. Returns the event log."""
    buf, log = collections.deque(), []
    empty, full, mutex = threading.Semaphore(size), threading.Semaphore(0), threading.Lock()
    def prod():
        for i in range(items):
            empty.acquire()
            with mutex: buf.append(i); log.append(f"Producer put {i}  buffer={list(buf)}")
            full.release()
    def cons():
        for _ in range(items):
            full.acquire()
            with mutex: x = buf.popleft(); log.append(f"Consumer got {x}  buffer={list(buf)}")
            empty.release()
    ts = [threading.Thread(target=prod), threading.Thread(target=cons)]
    [t.start() for t in ts]; [t.join() for t in ts]
    return log

def mutex_demo(threads=4, n=1500):
    """Shared counter incremented by many threads, with and without a mutex."""
    import time
    res = {}
    for use in (False, True):
        total, lock = [0], threading.Lock()
        def work():
            for _ in range(n):
                if use:
                    with lock: v = total[0]; time.sleep(0); total[0] = v + 1
                else: v = total[0]; time.sleep(0); total[0] = v + 1
        ts = [threading.Thread(target=work) for _ in range(threads)]
        [t.start() for t in ts]; [t.join() for t in ts]
        res["with_mutex" if use else "without_mutex"] = total[0]
    return {"expected": threads * n, **res}
