#!/usr/bin/env python3
"""
Configure Obsidian graph view to show the three identity hubs (Elnatan,
JARVIS, Claude Code) at the visual center with everything orbiting around
them in colored rings by area — spherical arrangement.

Writes ~/Documents/SecondBrain/.obsidian/graph.json. Idempotent.
"""
import json
import sys
from pathlib import Path

GRAPH_CONFIG = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,
    "showAttachments": False,
    "hideUnresolved": True,
    "showOrphans": True,
    "collapse-color-groups": False,
    "colorGroups": [
        # Tier 1 — Identity hubs (bright gold, large)
        {"query": 'path:"Personal/Elnatan" OR path:"_JARVIS/JARVIS" OR path:"_JARVIS/Claude Code"',
         "color": {"a": 1, "rgb": 16770048}},
        # Tier 2 — Per-area colors
        {"query": 'path:"Personal/" -path:"Personal/Elnatan"',           "color": {"a": 1, "rgb": 5294200}},
        {"query": 'path:"Goals/"',                                        "color": {"a": 1, "rgb": 16744576}},
        {"query": 'path:"Business/"',                                     "color": {"a": 1, "rgb": 16729344}},
        {"query": 'path:"Relationships/"',                                "color": {"a": 1, "rgb": 16753920}},
        {"query": 'path:"Beliefs/" OR path:"Patterns/" OR path:"Decisions/"',  "color": {"a": 1, "rgb": 11534079}},
        {"query": 'path:"Books/" OR path:"Learning/" OR path:"Skills/"',  "color": {"a": 1, "rgb": 7855479}},
        {"query": 'path:"Tools/"',                                        "color": {"a": 1, "rgb": 8957952}},
        {"query": 'path:"Daily/" OR path:"Routines/" OR path:"Health/"',  "color": {"a": 1, "rgb": 8978687}},
        {"query": 'path:"Finances/" OR path:"Career/"',                   "color": {"a": 1, "rgb": 4521796}},
        {"query": 'path:"Memories/" OR path:"Places/" OR path:"Ideas/" OR path:"Network/"',
         "color": {"a": 1, "rgb": 13369343}},
        {"query": 'path:"_JARVIS/" -path:"_JARVIS/JARVIS" -path:"_JARVIS/Claude Code"',
         "color": {"a": 1, "rgb": 8421504}},
        {"query": 'path:"_JARVIS/Proposals/"',                            "color": {"a": 1, "rgb": 5263440}},
    ],
    "collapse-display": False,
    "showArrow": False,
    "textFadeMultiplier": -0.2,
    "nodeSizeMultiplier": 1.1,
    "lineSizeMultiplier": 1,
    "collapse-forces": False,
    # Force settings tuned for a roughly spherical arrangement:
    # - high center gravity pulls hubs to the visual middle
    # - moderate repulsion spaces non-hub notes outward
    # - softer link force lets the orbits relax instead of clumping
    "centerStrength": 0.85,
    "repelStrength": 14,
    "linkStrength": 0.45,
    "linkDistance": 280,
    "scale": 0.9,
    "close": False,
}


def main():
    vault = Path.home() / "Documents" / "SecondBrain"
    obsidian = vault / ".obsidian"
    if not obsidian.exists():
        print(f"No .obsidian/ folder at {vault} — open Obsidian once first.")
        return 1
    target = obsidian / "graph.json"
    target.write_text(json.dumps(GRAPH_CONFIG, indent=2), encoding="utf-8")
    print(f"Wrote {target}")
    print("Reload the graph view in Obsidian to see the change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
