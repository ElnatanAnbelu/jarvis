#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from brain.router import route
from voice.speak import speak

# ANSI colors
_R = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_CYAN = "\033[96m"
_PURPLE = "\033[35m"
_LIME = "\033[92m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"

AGENT_COLORS = {
    "JARVIS":   _CYAN,
    "FRIDAY":   _PURPLE,
    "VERONICA": _LIME,
    "KAREN":    _YELLOW,
}

ASCII_HEADER = f"""{_GREEN}
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██ ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{_DIM}  Just A Rather Very Intelligent System  v3.0{_R}
"""


def agent_color(name):
    return AGENT_COLORS.get(name.upper(), _GREEN)


def print_response(agent, text):
    color = agent_color(agent)
    print(f"\n{color}{_BOLD}[ {agent.upper()} ]{_R}")
    for line in text.splitlines():
        print(f"  {color}{line}{_R}")
    print()


def main():
    voice_mode = "--voice" in sys.argv or "-v" in sys.argv

    print(ASCII_HEADER)
    print(f"{_GREEN}{'─' * 52}{_R}")
    print(f"{_DIM}  Commands: voice | text | exit{_R}")
    print(f"{_DIM}  Address agents: 'jarvis,...'  'friday,...'  etc.{_R}")
    print(f"{_GREEN}{'─' * 52}{_R}\n")

    speak("Systems online.", "JARVIS")

    if voice_mode:
        from voice.listen import load_model
        load_model()

    while True:
        try:
            if voice_mode:
                from voice.listen import listen_until_silence
                user_input = listen_until_silence()
                if not user_input:
                    continue
                print(f"\n{_DIM}[ YOU ]{_R} {user_input}")
            else:
                user_input = input(f"{_GREEN}▶ {_R}").strip()
                if not user_input:
                    continue

            if user_input.lower() in ["exit", "quit", "shutdown"]:
                speak("Shutting down. Stay focused, sir.", "JARVIS")
                print(f"\n{_DIM}[ JARVIS ] Offline.{_R}\n")
                break
            elif user_input.lower() == "voice":
                voice_mode = True
                from voice.listen import load_model
                load_model()
                speak("Switching to voice mode.", "JARVIS")
                continue
            elif user_input.lower() == "text":
                voice_mode = False
                speak("Switching to text mode.", "JARVIS")
                continue

            response, agent = route(user_input)
            print_response(agent, response)
            speak(response, agent)

        except KeyboardInterrupt:
            speak("Shutting down.", "JARVIS")
            print(f"\n{_DIM}[ JARVIS ] Offline.{_R}\n")
            break
        except Exception as e:
            print(f"{_DIM}[ ERROR ] {e}{_R}")


if __name__ == "__main__":
    main()
