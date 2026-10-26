"""NEXUS-OS Node Server.
Generic threaded TCP-JSON server hosting node-side endpoints (Block storage, Ricart-Agrawala, Sync).
Concept: Distributed RPC server for peer-to-peer data plane interactions.
"""

import json
import socket
import threading
from communication.tcp_client import Conn


class NodeServer:
    """Threaded TCP-JSON server for node-to-node and coordinator-to-node communication."""
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self.methods = {}  # method_name -> fn(payload) -> dict
        self.running = False
        self._sock = None
        self._thread = None

    def register_method(self, name, fn):
        """Register an RPC method handler."""
        self.methods[name] = fn

    def start(self):
        """Binds to socket and starts background listener thread."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(128)
        self._sock = s
        self.port = s.getsockname()[1]
        self.running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        print(f"[NodeServer] listening on {self.host}:{self.port}", flush=True)
        return self.port

    def _serve(self):
        while self.running:
            try:
                conn_sock, _ = self._sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(Conn(conn_sock),), daemon=True).start()

    def _handle_client(self, conn):
        try:
            while (msg := conn.recv()) is not None:
                method = msg.get("method") or msg.get("type")
                payload = msg.get("payload", msg)
                fn = self.methods.get(method)
                if fn:
                    try:
                        reply = fn(payload)
                    except Exception as e:
                        reply = {"type": "ERROR", "error": str(e)}
                else:
                    reply = {"type": "ERROR", "error": f"Unknown method: {method}"}

                if reply is not None:
                    reply["req_id"] = msg.get("req_id")
                    conn.send(reply)
        except (OSError, ValueError):
            pass
        finally:
            conn.close()

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
