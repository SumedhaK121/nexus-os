"""One command to run everything:  python app.py   ->  http://localhost:8080"""
import subprocess, sys, time, webbrowser, os, signal
R, py = os.path.dirname(os.path.abspath(__file__)), sys.executable
signal.signal(signal.SIGTERM, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
ps = [subprocess.Popen([py, "coordinator/main.py"], cwd=R)]; time.sleep(1)
ps += [subprocess.Popen([py, f"nodes/node{i}/node.py"], cwd=R) for i in (1, 2, 3)]
ps.append(subprocess.Popen([py, "dashboard/app.py"], cwd=R)); time.sleep(1.5)
print("NEXUS-OS running -> http://localhost:8080   (Ctrl+C to stop)", flush=True)
try:
    webbrowser.open("http://localhost:8080"); [p.wait() for p in ps]
except KeyboardInterrupt: pass
finally: [p.terminate() for p in ps]
