"""NEXUS-OS Chaos Engineering Tool.
Simulates real-world distributed systems failures:
- Node termination (kill)
- Heartbeat drop / suspicion (suspect)
- Network latency injection (delay)
- Network partition (isolate / heal)
Concept: Chaos Engineering (Netflix Chaos Monkey / Chaos Mesh).
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from communication import rpc
from communication.tcp_client import Client


def execute_chaos(action, node_id, coord_host="127.0.0.1", coord_port=9000, **kwargs):
    """Executes a chaos action against the cluster through the coordinator or node RPC."""
    action = str(action).lower()

    if action in ("kill", "terminate"):
        # Send PROC_KILL or instruct coordinator to drop node connection
        try:
            client = Client(host=coord_host, port=coord_port, client_id="chaos-agent")
            res = client.call({"type": "CHAOS_ACTION", "action": "kill", "node_id": node_id})
            client.close()
            return res
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to send chaos kill: {e}"}

    elif action in ("suspect", "miss_heartbeat"):
        try:
            client = Client(host=coord_host, port=coord_port, client_id="chaos-agent")
            res = client.call({"type": "CHAOS_ACTION", "action": "suspect", "node_id": node_id})
            client.close()
            return res
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to send chaos suspect: {e}"}

    elif action in ("partition", "isolate"):
        try:
            client = Client(host=coord_host, port=coord_port, client_id="chaos-agent")
            res = client.call({"type": "CHAOS_ACTION", "action": "partition", "node_id": node_id})
            client.close()
            return res
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to send chaos partition: {e}"}

    elif action in ("heal", "restore"):
        try:
            client = Client(host=coord_host, port=coord_port, client_id="chaos-agent")
            res = client.call({"type": "CHAOS_ACTION", "action": "heal", "node_id": node_id})
            client.close()
            return res
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to send chaos heal: {e}"}

    elif action == "delay":
        delay_ms = int(kwargs.get("delay_ms", 200))
        try:
            client = Client(host=coord_host, port=coord_port, client_id="chaos-agent")
            res = client.call({"type": "CHAOS_ACTION", "action": "delay", "node_id": node_id, "delay_ms": delay_ms})
            client.close()
            return res
        except Exception as e:
            return {"type": "ERROR", "error": f"Failed to send chaos delay: {e}"}

    return {"type": "ERROR", "error": f"Unknown chaos action '{action}'"}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/chaos.py <kill|suspect|partition|heal|delay> <node_id> [delay_ms]")
        sys.exit(1)

    act = sys.argv[1]
    nid = sys.argv[2]
    d_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    out = execute_chaos(act, nid, delay_ms=d_ms)
    print(json.dumps(out, indent=2))
