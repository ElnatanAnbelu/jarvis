#!/usr/bin/env python3
"""
JARVIS Always-On Voice Daemon
Continuously listens for your voice, sends commands to the web server.
Run this in a terminal alongside the web server.
"""
import sys
import os
import requests
import time

sys.path.insert(0, os.path.dirname(__file__))

SERVER = "http://localhost:8080"

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def print_status(msg, color=CYAN):
    print(f"\r{color}[JARVIS]{RESET} {msg}          ", flush=True)


def ping_server():
    try:
        r = requests.get(SERVER, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def send_command(text: str):
    # Check if it's an agent task or regular chat
    agent_triggers = [
        "go to ", "navigate to", "open and ", "click on", "fill in",
        "type into", "log into", "compose a", "submit the",
    ]
    is_agent = any(t in text.lower() for t in agent_triggers)
    endpoint = "/api/agent" if is_agent else "/api/chat"
    key = "task" if is_agent else "message"

    try:
        r = requests.post(f"{SERVER}{endpoint}", json={key: text}, timeout=120)
        data = r.json()
        return data.get("response") or data.get("status", "")
    except Exception as e:
        return f"Error: {e}"


def main():
    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════╗
║      J.A.R.V.I.S  Voice Daemon          ║
║      Always-on listening mode            ║
╚══════════════════════════════════════════╝{RESET}

  Listening continuously for your voice.
  Press {YELLOW}Ctrl+C{RESET} to stop.
""")

    if not ping_server():
        print(f"{YELLOW}  Warning: JARVIS server not running on {SERVER}{RESET}")
        print(f"  Start it with: python ui/server.py\n")

    # Load whisper
    print_status("Loading voice model...", YELLOW)
    from voice.listen import load_model, listen_until_silence
    load_model()
    print_status("Ready. Listening...", GREEN)

    while True:
        try:
            text = listen_until_silence()
            if not text or len(text.strip()) < 2:
                continue

            print(f"\n  {BOLD}You:{RESET} {text}")

            # Local stop command
            if text.strip().lower() in ("stop", "abort", "cancel"):
                requests.post(f"{SERVER}/api/agent/abort", timeout=5)
                print_status("Abort sent.", YELLOW)
                continue

            if text.strip().lower() in ("exit", "quit", "shutdown", "shut down"):
                print(f"\n{YELLOW}Voice daemon stopped.{RESET}")
                break

            response = send_command(text)
            if response:
                print(f"  {BOLD}{CYAN}JARVIS:{RESET} {response}\n")

            print_status("Listening...", GREEN)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}Voice daemon stopped.{RESET}")
            break
        except Exception as e:
            print_status(f"Error: {e} — retrying...", YELLOW)
            time.sleep(1)


if __name__ == "__main__":
    main()
