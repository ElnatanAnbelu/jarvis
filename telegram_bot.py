import sys
import os
import asyncio
import tempfile
import threading
import schedule
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from brain.router import route
from voice.speak import load_key, VOICE_MAP
import requests

def _load_env():
    env = Path(__file__).parent / ".env"
    for line in env.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

_load_env()

# Global bot reference for scheduler to use
_bot_app = None
_chat_id = None


def _save_chat_id(chat_id: int):
    global _chat_id
    _chat_id = chat_id
    env_path = Path(__file__).parent / ".env"
    env = env_path.read_text()
    if "TELEGRAM_CHAT_ID=" not in env:
        env_path.write_text(env.rstrip() + f"\nTELEGRAM_CHAT_ID={chat_id}\n")
    else:
        import re
        env = re.sub(r'TELEGRAM_CHAT_ID=.*', f'TELEGRAM_CHAT_ID={chat_id}', env)
        env_path.write_text(env)


def _get_chat_id() -> str:
    global _chat_id
    if _chat_id:
        return str(_chat_id)
    env_path = Path(__file__).parent / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("TELEGRAM_CHAT_ID="):
            return line.split("=", 1)[1].strip()
    return ""


# ── owner command parsing ─────────────────────────────────────────────────────
# Single-word owner commands (no argument).
_OWNER_COMMANDS_NOARG = {
    "pause", "resume", "away", "home", "back", "status", "pending",
    "auto", "supervised", "panic", "digest", "lock",
}
# Owner commands that take a single integer id.
_OWNER_COMMANDS_ARG = {"approve", "reject", "undo"}
# Owner commands that take a free-text argument (e.g. a PIN).
_OWNER_COMMANDS_TEXT = {"unlock", "setpin"}


def parse_owner_command(text: str):
    """Parse an owner control message into ``(cmd, arg)`` or ``None``.

    Pure function — no I/O — so it is trivially unit-testable.

    Returns:
      * ``(cmd, None)`` for no-arg commands (pause/resume/away/home/back/
        status/pending). ``home`` and ``back`` are normalized to ``"home"``.
      * ``(cmd, arg_str)`` for id commands (approve/reject/undo); ``arg_str`` is
        the raw remainder (may be empty/invalid — the handler validates it).
      * ``None`` if the message is not an owner command (falls through to the
        normal brain router).

    Matching is case-insensitive and tolerates a single leading slash.
    """
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("/"):
        stripped = stripped[1:].strip()
        if not stripped:
            return None

    parts = stripped.split(None, 1)
    cmd = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if cmd in _OWNER_COMMANDS_NOARG:
        # No-arg commands must not carry trailing text (avoid eating real chat
        # like "status of the project ...").
        if rest:
            return None
        if cmd == "back":
            cmd = "home"
        return (cmd, None)

    if cmd in _OWNER_COMMANDS_ARG:
        return (cmd, rest)

    if cmd in _OWNER_COMMANDS_TEXT:
        return (cmd, rest)

    return None


def _is_owner(chat_id) -> bool:
    """True if ``chat_id`` is the configured owner (or no owner is set yet).

    Owner is the explicit ``OWNER_CHAT_ID`` env var if present, otherwise the
    persisted ``TELEGRAM_CHAT_ID`` the bot already captures on first contact.
    If neither is known we have not yet locked to an owner, so allow (first-run
    capture path) — once a chat id is known it is treated as the owner.
    """
    owner = os.environ.get("OWNER_CHAT_ID", "").strip()
    if not owner:
        # Fall back to the persisted chat id in .env (stable — not the mutable
        # in-memory global, which a non-owner's normal message could overwrite).
        env_path = Path(__file__).parent / ".env"
        try:
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_CHAT_ID="):
                    owner = line.split("=", 1)[1].strip()
                    break
        except OSError:
            owner = ""
        # Last resort: the in-memory global (first run before .env persists).
        if not owner and _chat_id:
            owner = str(_chat_id)
    if not owner:
        return True
    return str(chat_id) == str(owner)


def _handle_owner_command(cmd: str, arg):
    """Execute a parsed owner command and return the reply text.

    Imports autonomy/memory at the call site to avoid circular imports.
    """
    from brain import autonomy
    from memory import memory

    if cmd in ("approve", "reject", "undo"):
        try:
            cid = int(str(arg).strip())
        except (TypeError, ValueError):
            return f"Usage: {cmd} <id>  (id must be a number)"
        if cmd == "approve":
            return autonomy.approve(cid)
        if cmd == "reject":
            return autonomy.reject(cid)
        return memory.revert_action(cid)

    if cmd == "pause":
        autonomy.set_paused(True)
        return "⏸ Paused — all autonomous actions halted."
    if cmd == "resume":
        autonomy.set_paused(False)
        return "▶️ Resumed."
    if cmd == "away":
        autonomy.set_away(True)
        return "🌙 Away-mode ON — red-list actions will need your approval."
    if cmd == "home":
        autonomy.set_away(False)
        return "🏠 Away-mode OFF."
    if cmd == "auto":
        autonomy.set_autonomy_mode("auto")
        return "⚙️ Autonomy: AUTO — routine runs on its own; red-list still confirms."
    if cmd == "supervised":
        autonomy.set_autonomy_mode("supervised")
        return "👀 Autonomy: SUPERVISED — I'll propose every action for your approval."
    if cmd == "panic":
        return autonomy.panic()
    if cmd == "digest":
        from brain.runner import build_digest
        return build_digest()
    if cmd == "lock":
        from security import identity
        return identity.lock()
    if cmd == "unlock":
        from security import identity
        res = identity.authenticate(pin=arg)
        return "🔓 Unlocked, sir — welcome back." if res["ok"] else "That didn't match, sir."
    if cmd == "setpin":
        from security import identity
        return identity.set_pin(arg)
    if cmd == "status":
        paused = "yes" if autonomy.is_paused() else "no"
        away = "yes" if autonomy.is_away() else "no"
        mode = autonomy.get_autonomy_mode()
        return f"Paused: {paused} · Away: {away} · Mode: {mode}\n{autonomy.pending_summary()}"
    if cmd == "pending":
        return autonomy.pending_summary()

    return None


def _tts_to_file(text: str, speaker: str):
    api_key = load_key()
    if not api_key:
        return None
    voice_id = VOICE_MAP.get(speaker, VOICE_MAP["JARVIS"])
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_turbo_v2_5",
                  "voice_settings": {"stability": 0.75, "similarity_boost": 0.85}},
            timeout=15,
        )
        if r.status_code == 200:
            f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            f.write(r.content)
            f.close()
            return f.name
    except Exception:
        pass
    return None


def _send_briefing():
    """Called by scheduler at 8 AM — sends briefing to Telegram."""
    chat_id = _get_chat_id()
    if not chat_id or not _bot_app:
        return
    try:
        from brain.briefing import generate_briefing, mark_sent, already_sent_today
        if already_sent_today():
            return
        text = generate_briefing()
        mark_sent()

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"*JARVIS — Morning Briefing*\n\n{text}", "parse_mode": "Markdown"},
            timeout=10,
        )

        audio_path = _tts_to_file(text, "JARVIS")
        if audio_path:
            with open(audio_path, "rb") as f:
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendVoice",
                    data={"chat_id": chat_id},
                    files={"voice": f},
                    timeout=20,
                )
            os.unlink(audio_path)
    except Exception as e:
        print(f"Briefing error: {e}")


def _run_scheduler():
    schedule.every().day.at("08:00").do(_send_briefing)
    while True:
        schedule.run_pending()
        time.sleep(30)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    chat_id = update.effective_chat.id

    # Owner control commands (approve/reject/pause/resume/away/home/status/
    # pending/undo) are handled BEFORE the brain router and short-circuit it.
    parsed = parse_owner_command(text)
    if parsed is not None:
        if not _is_owner(chat_id):
            # Security (C4): once an owner is known, ignore control commands
            # from any other sender.
            await update.message.reply_text("Not authorized.")
            return
        cmd, arg = parsed
        reply = await asyncio.get_event_loop().run_in_executor(
            None, _handle_owner_command, cmd, arg
        )
        if reply is not None:
            await update.message.reply_text(reply)
            return

    # Save chat ID on first message
    _save_chat_id(chat_id)

    await context.bot.send_chat_action(chat_id, "typing")

    loop = asyncio.get_event_loop()
    response, model = await loop.run_in_executor(None, route, text)

    speaker = model if model in ("FRIDAY", "VERONICA", "KAREN") else "JARVIS"
    await update.message.reply_text(f"*{speaker}*\n{response}", parse_mode="Markdown")

    audio_path = await loop.run_in_executor(None, _tts_to_file, response, model)
    if audio_path:
        try:
            with open(audio_path, "rb") as f:
                await context.bot.send_voice(update.effective_chat.id, f)
        except Exception:
            pass
        finally:
            os.unlink(audio_path)


def main():
    global _bot_app
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("No TELEGRAM_BOT_TOKEN in .env")
        return

    print("JARVIS Telegram bot starting...")
    print("Message your bot: t.me/ElnatanJarvisBot")
    print("Morning briefing scheduled at 08:00 daily.")

    # Start scheduler in background thread
    threading.Thread(target=_run_scheduler, daemon=True).start()

    # Start wake monitor — triggers briefing when Mac wakes
    from control.wake import start_wake_monitor
    start_wake_monitor()

    # Start proactive reminders
    from brain.proactive import start_proactive_scheduler
    start_proactive_scheduler()

    _bot_app = ApplicationBuilder().token(token).build()
    _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    _bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
