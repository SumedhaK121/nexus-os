import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from coordinator.scheduler.scheduler_manager import compare
from coordinator.deadlock.bankers_algorithm import Banker
P = [{"pid": "P1", "arrival": 0, "burst": 4, "priority": 2}, {"pid": "P2", "arrival": 1, "burst": 2, "priority": 1}]
assert len(compare(P)) == 4
b = Banker([3,3,2], {"P0":[7,5,3],"P1":[3,2,2],"P2":[9,0,2],"P3":[2,2,2],"P4":[4,3,3]}, {"P0":[0,1,0],"P1":[2,0,0],"P2":[3,0,2],"P3":[2,1,1],"P4":[0,0,2]})
assert b.is_safe()[0] and b.request("P1",[1,0,2])["granted"] and not b.request("P0",[0,2,0])["granted"]
print("core tests passed")
from coordinator.file_manager.file_manager import FileManager
from coordinator.synchronization.ricart_agrawala import simulate
from coordinator.synchronization.primitives import producer_consumer
fm = FileManager(cache_size=2, policy="LRU"); N = ["node-1", "node-2", "node-3"]
for n in "abc": fm.write(n + ".txt", n * 3, N)
assert fm.read("a.txt")["source"] == "disk" and fm.read("a.txt")["source"] == "cache"
assert all(len(v) == 2 for v in fm.rep.placement.values()) and fm.delete("a.txt")
r = simulate(N, ["node-1", "node-2", "node-3"]); assert sorted(r["order"]) == sorted(N) and r["messages"] == 12
assert len(producer_consumer()) == 12
for n in ("b.txt", "c.txt"): fm.delete(n)
print("files/cache/replication/sync tests passed")
from coordinator.deadlock.deadlock_detector import detect, SCENARIOS
from coordinator.file_manager.page_replacement import simulate as ps
from coordinator.synchronization.primitives import mutex_demo
assert detect(SCENARIOS["circular"]) and not detect(SCENARIOS["chain"])
R = {x["algo"]: x["faults"] for x in ps("7,0,1,2,0,3,0,4,2,3,0,3,2".split(","), 3)}
assert R == {"FIFO": 10, "LRU": 9, "Optimal": 7}, R
m = mutex_demo(); assert m["with_mutex"] == m["expected"] and m["without_mutex"] < m["expected"]
print("deadlock/page-replacement/mutex tests passed")
