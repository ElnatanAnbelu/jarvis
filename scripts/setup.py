#!/usr/bin/env python3
"""Alfred setup wizard — the one place YOU hand Alfred what only you can give it.

Run it yourself:  ./venv/bin/python scripts/setup.py

You type your own secrets here; they go straight into the macOS Keychain (the
local credential vault) and are NEVER logged, never sent anywhere, never seen by
the AI. Config (your iMessage handle, PIN) is set locally too. Every section is
optional — press Enter to skip and come back later. Re-run any time; it's
idempotent.
"""
import getpass
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
ENV_PATH = _ROOT / ".env"

# Services Alfred can use once you provide a token. (name in vault, friendly label.)
_SERVICES = [
    ("gmail_oauth", "Gmail / Google OAuth token"),
    ("notion_token", "Notion integration token"),
    ("whatsapp_token", "WhatsApp Business token"),
    ("telegram_bot_token", "Telegram bot token (fail-safe channel)"),
]


def _set_env_var(path, key: str, value: str) -> bool:
    """Idempotently set KEY=value in a .env-style file, preserving other lines.
    Pure file op — testable without prompts."""
    path = Path(path)
    lines = path.read_text().splitlines() if path.exists() else []
    out, found = [], False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")
    return found  # False = newly added, True = updated


def _ask(label: str) -> str:
    try:
        return input(f"  {label} (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _ask_secret(label: str) -> str:
    try:
        return getpass.getpass(f"  {label} (hidden; Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _section(title: str):
    print(f"\n── {title} " + "─" * max(2, 56 - len(title)))


def _setup_pin():
    _section("Security PIN (needed to approve money ≥ $100)")
    from security import identity
    if identity.has_pin():
        if _ask("A PIN is already set. Type 'change' to replace it").lower() != "change":
            print("  ✓ keeping existing PIN.")
            return
    pin = _ask_secret("Choose a numeric PIN")
    if pin:
        print("  " + identity.set_pin(pin))


def _setup_imessage():
    _section("iMessage — Alfred's primary remote surface")
    print("  Your iMessage handle(s) — the phone/email you'll text Alfred FROM.")
    print("  (Only these can command Alfred remotely. Also enable Full Disk Access for")
    print("   Terminal/Python in System Settings → Privacy so Alfred can read new messages.)")
    handles = _ask("Owner handle(s), comma-separated, e.g. +14155551212,me@icloud.com")
    if handles:
        _set_env_var(ENV_PATH, "ALFRED_IMESSAGE_OWNER", handles)
        print(f"  ✓ iMessage owner set. Alfred will listen for: {handles}")


def _setup_credentials():
    _section("Service credentials (stored in the macOS Keychain)")
    from security import vault
    for name, label in _SERVICES:
        marker = " [already set]" if vault.has(name) else ""
        secret = _ask_secret(f"{label}{marker}")
        if secret:
            print("  " + vault.put(name, secret))


def _setup_people():
    _section("People — VIP / family / blocklist (contact-aware gate)")
    print("  Messages to VIP/family always confirm; blocked contacts are never auto-actioned.")
    from memory import people
    people.init_people()
    while True:
        name = _ask("Person's name (Enter to finish)")
        if not name:
            break
        ident = _ask("  Their phone/email (how Alfred recognizes them)")
        flags = _ask("  Tags — any of: vip family blocked (space-separated)").lower().split()
        print("  " + people.add_person(
            name, ident,
            vip="vip" in flags, family="family" in flags, blocked="blocked" in flags,
        ))


def _status():
    _section("Status")
    from security import identity, vault
    from memory import people
    import imessage_channel
    print(f"  PIN set:           {'yes' if identity.has_pin() else 'no'}")
    print(f"  iMessage owner:    {'yes' if imessage_channel.enabled() else 'no (set to enable the channel)'}")
    print(f"  Vault credentials: {', '.join(vault.list_names()) or 'none yet'}")
    ppl = people.list_people()
    print(f"  People registered: {len(ppl)}")
    print("\n  You're set, sir. Launch Alfred with:  ./venv/bin/python app/main.py\n")


def main():
    print("\n" + "=" * 60)
    print("  ALFRED — setup wizard")
    print("  Your secrets stay on this Mac (Keychain). I never see them.")
    print("=" * 60)
    for step in (_setup_pin, _setup_imessage, _setup_credentials, _setup_people):
        try:
            step()
        except Exception as e:  # one section failing shouldn't abort the wizard
            print(f"  (skipped — {e})")
    _status()


if __name__ == "__main__":
    main()
