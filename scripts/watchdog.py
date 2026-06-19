#!/usr/bin/env python3
"""scripts/watchdog.py — Alfred's tiny BRAIN-FREE survival core (plan §R1).

It pings Alfred's server; if it's down for a few consecutive checks, it restarts it.
Deliberately minimal — no model, no heavy imports — so it keeps running when everything
else falls over. Run it detached:  nohup ./venv/bin/python scripts/watchdog.py &
"""
import subprocess
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_URL = "http://127.0.0.1:8080/api/status"
_FAIL_LIMIT = 3


def alive(url: str = _URL, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return getattr(r, "status", r.getcode()) == 200
    except Exception:
        return False


def should_restart(consecutive_failures: int) -> bool:
    """Pure decision (testable): restart once the server has missed _FAIL_LIMIT checks."""
    return consecutive_failures >= _FAIL_LIMIT


def restart_server():
    py = str(_ROOT / "venv" / "bin" / "python")
    subprocess.Popen([py, "-m", "ui.server"], cwd=str(_ROOT),
                     stdout=open("/tmp/alfred_server.log", "a"), stderr=subprocess.STDOUT)


def run(interval: float = 20.0):
    print("[watchdog] watching Alfred.", flush=True)
    fails = 0
    while True:
        if alive():
            fails = 0
        else:
            fails += 1
            if should_restart(fails):
                print("[watchdog] server down — restarting Alfred.", flush=True)
                restart_server()
                fails = 0
                time.sleep(15)
        time.sleep(interval)


if __name__ == "__main__":
    run()
