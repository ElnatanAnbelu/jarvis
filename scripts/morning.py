#!/usr/bin/env python3
"""Run this at startup or via cron for daily morning briefing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.life import morning_briefing
from voice.speak import speak
from brain.think import think

def run():
    briefing = morning_briefing()
    # Have JARVIS summarize and add personalized commentary
    prompt = f"Give a sharp, motivating morning briefing for Elnatan based on this data. Be brief, push him to act:\n\n{briefing}"
    response = think(prompt)
    print(response)
    speak(response)

if __name__ == "__main__":
    run()
