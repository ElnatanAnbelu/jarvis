#!/usr/bin/env python3
"""
Process every chat transcript dropped into the vault's _Inbox/ChatTranscripts/
folder. Distills each into proposals via brain.tools.ingest_chat, moves
the raw transcript into _processed/ when done.

Idempotent — running on an empty inbox is a no-op.
"""
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    from memory.vault import VaultManager
    from brain.tools.ingest_chat import synthesize_claude_chat
    vm = VaultManager()
    inbox = vm.vault_path / "_Inbox" / "ChatTranscripts"
    processed = inbox / "_processed"
    processed.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        print("Inbox folder not found.")
        return 0

    files = [p for p in inbox.iterdir()
             if p.is_file() and p.suffix.lower() in (".md", ".txt", ".json")
             and p.name != "README.md"]
    if not files:
        print("No new chat transcripts to ingest. Drop files in:")
        print(f"  {inbox}")
        return 0

    print(f"Processing {len(files)} transcript(s)...\n")
    for f in files:
        label = f.stem
        print(f"=== {f.name} ===")
        result = synthesize_claude_chat(str(f), session_label=label)
        print(result)
        # Move to processed
        target = processed / f.name
        n = 2
        while target.exists():
            target = processed / f"{f.stem} ({n}){f.suffix}"
            n += 1
        shutil.move(str(f), str(target))
        print(f"Moved to _processed/{target.name}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
