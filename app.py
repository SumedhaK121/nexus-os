"""One command to run everything:  python app.py   ->  http://localhost:8080"""
import subprocess, sys, time, webbrowser, os, signal
R, py = os.path.dirname(os.path.abspath(__file__)), sys.executable
port = str(os.environ.get("PORT", "8080"))
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
ps = [subprocess.Popen([py, "coordinator/main.py"], cwd=R)]; time.sleep(1)
ps += [subprocess.Popen([py, f"nodes/node{i}/node.py"], cwd=R) for i in (1, 2, 3)]
ps.append(subprocess.Popen([py, "dashboard/app.py", "9000", port], cwd=R)); time.sleep(1.5)
print(f"NEXUS-OS running on port {port} -> http://0.0.0.0:{port} (Ctrl+C to stop)", flush=True)
try:
    if not os.environ.get("RENDER") and not os.environ.get("HEADLESS"):
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass
    [p.wait() for p in ps]
except KeyboardInterrupt: pass
finally: [p.terminate() for p in ps]
