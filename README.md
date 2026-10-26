# NEXUS-OS v2
Run everything:  python app.py   (opens http://localhost:8080). Python 3.8+, no packages.
Done: scheduler (FCFS, SJF, Priority, RR), Banker's, Lamport clock, TCP layer, nodes, file manager (versions), replication (2 copies), LRU/FIFO cache, Ricart-Agrawala, readers-writers lock, producer-consumer, web UI.
Lamport clock in distributed_clock, TCP layer in communication, nodes/node1-3, web UI in dashboard.
Still empty: coordinator/{node_manager,process_manager,resource_manager}, docker (logic currently lives in coordinator/main.py).
Add a feature: @coord.handler("TYPE") in coordinator/main.py, then show it in dashboard/static/script.js.
Tests: python tests/test_core.py
