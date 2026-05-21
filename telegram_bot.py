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

    # Save chat ID on first message
    _save_chat_id(update.effective_chat.id)

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

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
