"""Web dashboard server. python dashboard/app.py [coordinator_port] [web_port]"""
import sys, os, json, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from communication.tcp_client import Client
CP = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
WP = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("PORT", 8080))
ST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_l, _c = threading.Lock(), None
def call(msg):
    global _c
    with _l:
        for _ in (1, 2):
            try:
                _c = _c or Client(host=os.environ.get("NEXUS_HOST", "127.0.0.1"), port=CP)
                return _c.call(msg) or {"type": "ERROR", "error": "no reply"}
            except OSError: _c = None
    return {"type": "ERROR", "error": "coordinator not reachable"}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, code, body, ct="application/json"):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-cache, no-store, must-revalidate"); self.send_header("Pragma", "no-cache"); self.send_header("Expires", "0"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/api/status": return self._s(200, json.dumps(call({"type": "STATUS"})))
        n = os.path.basename(self.path.split("?")[0]); n = n if n in ("style.css", "script.js") else "index.html"
        ct = {"css": "text/css", "js": "application/javascript"}.get(n.split(".")[1], "text/html; charset=utf-8")
        self._s(200, open(os.path.join(ST, n), "rb").read(), ct)
    def do_POST(self):
        self._s(200, json.dumps(call(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"))))
if __name__ == "__main__":
    print(f"Dashboard http://localhost:{WP} (coordinator :{CP})", flush=True); ThreadingHTTPServer(("0.0.0.0", WP), H).serve_forever()
