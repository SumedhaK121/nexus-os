import subprocess
import sys
import time
import urllib.request

print("Starting app.py smoke test...", flush=True)
p = subprocess.Popen([sys.executable, "app.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(3.0)
    req = urllib.request.urlopen("http://localhost:8080/api/status", timeout=5)
    body = req.read().decode("utf-8")
    print(f"HTTP status code: {req.status}", flush=True)
    print(f"Length of status response: {len(body)}", flush=True)
    assert req.status == 200, f"Expected 200, got {req.status}"
    assert '"type": "STATUS"' in body or '"type":"STATUS"' in body, "Invalid status response"
    print("app.py smoke test SUCCESSFUL!", flush=True)
finally:
    p.terminate()
    try:
        p.wait(timeout=2)
    except Exception:
        p.kill()
