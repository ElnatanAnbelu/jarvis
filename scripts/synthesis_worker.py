#!/usr/bin/env python3
"""
Background synthesis worker. Drains quality observations from
memory/observations.py into the vault as Daily/ notes or area proposals.

Strategy:
- Group observations by source + relevance_hint + day
- For each group, build a synthesis note that summarizes the day's
  signal in that area
- Stage as a proposal (high-risk areas) or auto-write (Daily/)
- Mark each observation as synthesized=1 so it's not re-processed

Idempotent. Run periodically (manually for now, scheduled later).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import defaultdict
from datetime import datetime


def main():
    from memory.observations import get_pending_observations, mark_synthesized
    from memory.vault import VaultManager

    vm = VaultManager()
    pending = get_pending_observations(limit=200, include_high_sensitivity=True)
    if not pending:
        print("No pending quality observations to synthesize.")
        return 0

    # Group by (area, day)
    groups = defaultdict(list)
    for obs in pending:
        captured = obs.get("captured_at", "")[:10] or "undated"
        area = obs.get("relevance_hint") or "Daily"
        groups[(area, captured)].append(obs)

    print(f"Synthesizing {len(pending)} observations into {len(groups)} groups...")
    synthesized = []

    for (area, day), obs_list in groups.items():
        # Build a daily synthesis note for that area+day
        lines = [f"## {area} — {day}", ""]
        for o in obs_list:
            sd = o.get("source_detail") or ""
            sd_short = sd[:80]
            content_snip = (o.get("content") or "")[:300].replace("\n", " ")
            lines.append(f"- **{sd_short}**")
            lines.append(f"  {content_snip}")
            lines.append("")
        content = "\n".join(lines)

        # Stage as a proposal in the target area (or Daily if area unknown)
        title = f"Synthesis — {area} — {day}"
        try:
            result = vm.propose_change(
                title=title, proposed_content=content,
                action="create", area=area if area in (
                    "Personal","Business","Relationships","Goals","Decisions",
                    "Daily","Learning","Archive","Health","Finances","Ideas",
                    "Books","Beliefs","Tools","Skills","Memories","Places",
                    "Career","Patterns","Routines","Network",
                ) else "Daily",
                source=f"observation synthesis worker {day}",
                reason=f"Drained {len(obs_list)} observation(s) from {area}/{day}",
            )
            print(f"  ✓ {result}")
            for o in obs_list:
                mark_synthesized(o["id"])
                synthesized.append(o["id"])
        except Exception as e:
            print(f"  ✗ {title}: {e}")

    print(f"\nSynthesized {len(synthesized)} observations into the vault.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
