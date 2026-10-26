from coordinator.scheduler.fcfs import fcfs
from coordinator.scheduler.sjf import sjf
from coordinator.scheduler.priority import priority
from coordinator.scheduler.round_robin import round_robin

def run(algo, procs, quantum=2):
    if algo == "rr": return round_robin(procs, quantum)
    return {"sjf": sjf, "priority": priority}.get(algo, fcfs)(procs)

def compare(procs, quantum=2):
    return [fcfs(procs), sjf(procs), priority(procs), round_robin(procs, quantum)]
