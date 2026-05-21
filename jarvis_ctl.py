#!/usr/bin/env python3
"""
JARVIS Control Terminal — run this in a side window.
Type commands, JARVIS controls your screen.
Type 'stop' to abort a running task.
Type 'exit' or Ctrl+C to quit.
"""
import sys
import os
import threading
import requests
import socketio as sio_client

SERVER = "http://localhost:8080"

# ANSI colors
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

sock = sio_client.SimpleClient()
_task_done = threading.Event()
_current_result = [""]


def connect_socket():
    try:
        sock.connect(SERVER)
    except Exception:
        pass  # socket is optional; HTTP still works


def listen_for_events():
    while True:
        try:
            event, data = sock.receive()
            if event == "agent_progress":
                step = data.get("step", "")
                action = data.get("action", "")
                print(f"\r  {CYAN}[{step}]{RESET} {action}          ", flush=True)
            elif event == "agent_done":
                result = data.get("result", "")
                _current_result[0] = result
                _task_done.set()
        except Exception:
            break


def send_task(task: str):
    _task_done.clear()
    _current_result[0] = ""
    try:
        r = requests.post(f"{SERVER}/api/agent", json={"task": task}, timeout=10)
        if r.status_code != 200:
            print(f"{RED}Error: {r.text}{RESET}")
            return
    except requests.exceptions.ConnectionError:
        print(f"{RED}JARVIS server not running. Start it with: python ui/server.py{RESET}")
        return

    print(f"  {YELLOW}JARVIS taking control...{RESET}")
    # Wait for done event (max 5 minutes)
    if _task_done.wait(timeout=300):
        print(f"\n  {GREEN}{BOLD}JARVIS:{RESET} {_current_result[0]}")
    else:
        print(f"\n  {RED}Timed out waiting for JARVIS.{RESET}")


def send_abort():
    try:
        requests.post(f"{SERVER}/api/agent/abort", timeout=5)
        print(f"  {YELLOW}Abort signal sent.{RESET}")
    except Exception:
        print(f"  {RED}Could not reach server.{RESET}")


def print_banner():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════╗
║         J A R V I S  C O N T R O L      ║
║      Screen Control Terminal v1.0        ║
╚══════════════════════════════════════════╝{RESET}

  Type a command → JARVIS controls your screen
  Type {YELLOW}'stop'{RESET} to abort a running task
  Type {YELLOW}'exit'{RESET} or press {YELLOW}Ctrl+C{RESET} to quit
  Move mouse to {YELLOW}top-left corner{RESET} for emergency stop

""")


def main():
    print_banner()

    # Try to connect WebSocket for live progress
    t = threading.Thread(target=connect_socket, daemon=True)
    t.start()

    listener = threading.Thread(target=listen_for_events, daemon=True)
    listener.start()

    import time; time.sleep(0.5)  # let socket connect

    while True:
        try:
            raw = input(f"{BOLD}{CYAN}JARVIS ctl >{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Goodbye, sir.{RESET}")
            break

        if not raw:
            continue

        if raw.lower() in ("exit", "quit", "bye"):
            print(f"{YELLOW}Goodbye, sir.{RESET}")
            break

        if raw.lower() in ("stop", "cancel", "abort"):
            send_abort()
            continue

        send_task(raw)


if __name__ == "__main__":
    main()
