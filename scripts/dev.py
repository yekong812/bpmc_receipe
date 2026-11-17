"""Run both development servers and stop their child processes on exit."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
api = [
    sys.executable,
    "-m",
    "uvicorn",
    "backend.app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
    "--reload",
]
if (root / ".env").is_file():
    api += ["--env-file", str(root / ".env")]
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)


def interrupted(*_):
    stop()
    raise SystemExit(0)

signal.signal(signal.SIGINT, interrupted)
signal.signal(signal.SIGTERM, interrupted)
try:
    children.append(subprocess.Popen(api, cwd=root, start_new_session=True))
    children.append(
        subprocess.Popen(["npm", "run", "dev"], cwd=root / "frontend", start_new_session=True)
    )
    print("BPMC: http://127.0.0.1:3000", flush=True)
    while all(child.poll() is None for child in children):
        time.sleep(0.5)
    raise SystemExit(next((child.returncode for child in children if child.returncode is not None),1))
finally:
    stop()
