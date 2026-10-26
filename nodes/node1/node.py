import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from nodes.node import Node
Node("node-1", host=os.environ.get("NEXUS_HOST", "127.0.0.1"), port=int(os.environ.get("NEXUS_PORT", 9000))).run()
