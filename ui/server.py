import sys
import os
import queue
import asyncio as _asyncio
import threading as _threading
from pathlib import Path

# Persistent event loop for async TTS — avoids asyncio.run() startup cost
_async_loop = _asyncio.new_event_loop()
_threading.Thread(target=_async_loop.run_forever, daemon=True).start()

def _run_async(coro):
    fut = _asyncio.run_coroutine_threadsafe(coro, _async_loop)
    return fut.result(timeout=15)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import threading
import json
import time
import tempfile
import subprocess
import re
import base64

app = Flask(__name__)
CORS(app)


@app.before_request
def _localhost_only():
    """Reject any request that didn't originate from localhost."""
    from flask import request, abort
    remote = request.remote_addr
    if remote not in ("127.0.0.1", "::1"):
        abort(403)


# ── LOCATION DETECTION ──────────────────────────────────────
_location = {"city": "", "country": "", "timezone": "UTC", "loc": ""}

def _detect_location():
    global _location
    try:
        import requests as req
        r = req.get("https://ipinfo.io/json", timeout=6)
        if r.status_code == 200:
            d = r.json()
            _location = {
                "city": d.get("city", ""),
                "country": d.get("country", ""),
                "timezone": d.get("timezone", "UTC"),
                "loc": d.get("loc", ""),
            }
            loc_str = f"{_location['city']}, {_location['country']}"
            os.environ["JARVIS_LOCATION"] = loc_str
            os.environ["JARVIS_TIMEZONE"] = _location["timezone"]
    except Exception:
        pass

threading.Thread(target=_detect_location, daemon=True).start()

KOKORO_PYTHON  = str(Path(__file__).parent.parent / "voice" / "kokoro_env" / "bin" / "python3")
KOKORO_WORKER  = str(Path(__file__).parent.parent / "voice" / "kokoro_worker.py")
KOKORO_DAEMON  = str(Path(__file__).parent.parent / "voice" / "kokoro_daemon.py")
KOKORO_SOCK    = str(Path(__file__).parent.parent / "voice" / "kokoro.sock")
KOKORO_MODEL   = str(Path(__file__).parent.parent / "voice" / "kokoro-v1.0.onnx")
KOKORO_VOICES  = str(Path(__file__).parent.parent / "voice" / "voices-v1.0.bin")

CLONE_PYTHON   = str(Path(__file__).parent.parent / "voice" / "clone_env" / "bin" / "python3")
CLONE_DAEMON   = str(Path(__file__).parent.parent / "voice" / "clone_daemon.py")
CLONE_SOCK     = str(Path(__file__).parent.parent / "voice" / "clone.sock")


def _warmup_tts():
    """Pre-warm Kokoro and edge-tts so first real call is fast."""
    # Kokoro warmup — first synthesis is always slowest
    if os.path.exists(KOKORO_SOCK):
        try:
            _tts_kokoro_daemon(".", "JARVIS")
        except Exception:
            pass
    # edge-tts warmup — pre-establish TLS connection
    try:
        import edge_tts as _et, tempfile as _tf
        async def _w():
            c = _et.Communicate(".", "en-GB-RyanNeural")
            with _tf.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                t = f.name
            await c.save(t)
            os.unlink(t)
        _run_async(_w())
    except Exception:
        pass

threading.Thread(target=_warmup_tts, daemon=True).start()

# ── PROACTIVE EVENT QUEUE ────────────────────────────────────
_proactive_q: queue.Queue = queue.Queue()


def _strip_markdown(text):
    import re
    # Preserve code fences (```lang\n...\n```) — HUD renders them as executable blocks
    # Extract code blocks, replace with placeholders, strip markdown, restore
    code_blocks = []
    def _save_block(m):
        code_blocks.append(m.group(0))
        return f'\x00CODE{len(code_blocks)-1}\x00'
    text = re.sub(r'```[\s\S]*?```', _save_block, text)
    # Strip conversational markdown
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}(.+?)_{1,2}', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)  # inline code — strip backticks, keep content
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Restore code blocks
    for i, block in enumerate(code_blocks):
        text = text.replace(f'\x00CODE{i}\x00', block)
    return text.strip()


def _route(user_input):
    from brain.router import route
    response, agent = route(user_input)
    return _strip_markdown(response), agent


def _speak(text, agent):
    pass  # TTS now handled by browser via /api/tts


_active_agent = {"name": None}  # session state — which agent is currently active


@app.route("/api/stream", methods=["GET"])
def stream():
    user_input = request.args.get("message", "").strip()
    if not user_input:
        return Response("data: {}\n\n", mimetype="text/event-stream")

    def generate():
        try:
            from voice.speak import stop_speaking
            stop_speaking()
        except Exception:
            pass
        yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

        if user_input == "__init__":
            from brain.think import think_stream
            from datetime import datetime
            import pytz
            try:
                _tz = pytz.timezone(os.environ.get("JARVIS_TIMEZONE", "Africa/Addis_Ababa"))
                _hour = datetime.now(_tz).hour
            except Exception:
                _hour = datetime.now().hour
            if _hour < 12:
                _period = "morning"
            elif _hour < 17:
                _period = "afternoon"
            elif _hour < 21:
                _period = "evening"
            else:
                _period = "night"
            yield f"data: {json.dumps({'type': 'speaker', 'name': 'JARVIS'})}\n\n"
            chunks = []
            greeting_prompt = (
                f"Generate a single short greeting. You are JARVIS and Elnatan just opened the system. "
                f"It is currently {_period} local time. Acknowledge the time naturally — not robotically. "
                f"Be composed, dry, in character. One sentence only. No markdown. No name prefix."
            )
            for chunk in think_stream(greeting_prompt, model="claude-haiku-4-5-20251001"):
                stripped = _strip_markdown(chunk)
                if stripped:
                    chunks.append(stripped)
                    yield f"data: {json.dumps({'type': 'text', 'chunk': stripped})}\n\n"
            full = "".join(chunks).strip()
            if full:
                from memory.memory import save_message
                save_message("jarvis", full)
                try:
                    from voice.speak import _speak
                    import threading
                    threading.Thread(target=lambda: _speak(full, "JARVIS"), daemon=True).start()
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'done', 'agent': 'JARVIS', 'full': full})}\n\n"
            return

        try:
            from brain.router import route_stream
            agent = "JARVIS"
            full = ""
            last_done_sent = False
            for event_type, value in route_stream(user_input, active_agent=_active_agent["name"]):
                if event_type == "agent":
                    agent = value
                    yield f"data: {json.dumps({'type': 'speaker', 'name': agent})}\n\n"
                elif event_type == "chunk":
                    stripped = _strip_markdown(value)
                    if stripped:
                        yield f"data: {json.dumps({'type': 'text', 'chunk': stripped})}\n\n"
                elif event_type == "done":
                    full = value
                    # In work-together mode, each agent emits done separately
                    yield f"data: {json.dumps({'type': 'done', 'agent': agent, 'full': full})}\n\n"
                    last_done_sent = True
                elif event_type == "persist":
                    _active_agent["name"] = value  # update session
            if not last_done_sent:
                yield f"data: {json.dumps({'type': 'done', 'agent': agent, 'full': full})}\n\n"
        except Exception as e:
            import traceback
            print("ROUTE ERROR:", traceback.format_exc(), flush=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/active_agent", methods=["GET", "DELETE"])
def active_agent_endpoint():
    if request.method == "DELETE":
        _active_agent["name"] = None
        return jsonify({"status": "cleared"})
    return jsonify({"agent": _active_agent["name"]})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user_input = data.get("message", "").strip()
    if not user_input:
        return jsonify({"error": "Empty message"}), 400
    if user_input == "__init__":
        from brain.think import think as think_jarvis
        from datetime import datetime
        import pytz
        try:
            tz = pytz.timezone(os.environ.get("JARVIS_TIMEZONE", "Africa/Addis_Ababa"))
            hour = datetime.now(tz).hour
        except Exception:
            hour = datetime.now().hour
        if hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        elif hour < 21:
            period = "evening"
        else:
            period = "night"
        greeting_prompt = (
            f"Generate a single short greeting. You are JARVIS and Elnatan just opened the system. "
            f"It is currently {period} local time. Acknowledge the time naturally — not robotically. "
            f"Be composed, dry, in character. One sentence only. No markdown. No name prefix."
        )
        greeting = think_jarvis(greeting_prompt, model="claude-haiku-4-5-20251001")
        if not greeting:
            greeting = f"Good {period}, sir. Systems are online."
        threading.Thread(target=lambda: _speak(greeting, "JARVIS"), daemon=True).start()
        return jsonify({"response": greeting, "agent": "JARVIS"})

    # Work together — accumulate each agent's streamed chunks, return complete responses
    from brain.team import is_work_together, work_together
    if is_work_together(user_input):
        responses = []
        current_agent = None
        agent_chunks = []
        for event_type, value in work_together(user_input):
            if event_type == "agent":
                current_agent = value
                agent_chunks = []
            elif event_type == "chunk" and current_agent:
                agent_chunks.append(value)
            elif event_type == "done_agent":
                if current_agent and agent_chunks:
                    full = _strip_markdown("".join(agent_chunks).strip())
                    responses.append({"agent": current_agent, "response": full})
                current_agent = None
                agent_chunks = []
        return jsonify({"responses": responses})

    response, agent = _route(user_input)
    threading.Thread(target=lambda: _speak(response, agent), daemon=True).start()
    return jsonify({"response": response, "agent": agent})


@app.route("/api/voice", methods=["POST"])
def voice_input():
    if "audio" not in request.files:
        return jsonify({"error": "No audio"}), 400
    audio_file = request.files["audio"]
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        audio_file.save(f.name)
        tmp_path = f.name
    text = ""
    try:
        # Groq Whisper — fast cloud transcription
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
            for line in open(env_path).readlines():
                if line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1].strip()
        if groq_key:
            from groq import Groq
            client = Groq(api_key=groq_key)
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=("audio.webm", f, "audio/webm"),
                    response_format="text",
                )
            text = (result or "").strip()
    except Exception:
        pass
    finally:
        try: os.unlink(tmp_path)
        except: pass
    return jsonify({"text": text})


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload a file or image; stream back JARVIS's analysis via SSE."""
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    uploaded = request.files["file"]
    question = request.form.get("question", "").strip() or "Summarize this for me."
    suffix = Path(uploaded.filename).suffix.lower() if uploaded.filename else ".tmp"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        uploaded.save(f.name)
        tmp_path = f.name

    from brain.router import _IMAGE_EXTENSIONS, _DOC_EXTENSIONS
    is_image = suffix in _IMAGE_EXTENSIONS
    is_doc = suffix in _DOC_EXTENSIONS

    def generate():
        try:
            from brain.reader import ask_about_file, ask_about_image
            from memory.memory import save_message
            name = uploaded.filename or "uploaded file"
            save_message("user", f"[uploaded {name}] {question}")
            yield f"data: {json.dumps({'type': 'speaker', 'name': 'JARVIS'})}\n\n"
            chunks = []
            if is_image:
                gen = ask_about_image(tmp_path, question)
            else:
                gen = ask_about_file(tmp_path, question)
            for chunk in gen:
                stripped = _strip_markdown(chunk)
                if stripped:
                    chunks.append(stripped)
                    yield f"data: {json.dumps({'type': 'text', 'chunk': stripped})}\n\n"
            full = "".join(chunks).strip()
            if full:
                save_message("jarvis", full)
            yield f"data: {json.dumps({'type': 'done', 'agent': 'JARVIS', 'full': full})}\n\n"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.route("/api/agent", methods=["POST"])
def agent_task():
    data = request.json or {}
    task = data.get("task", "").strip()
    if not task:
        return jsonify({"error": "No task"}), 400
    from control.agent import get_agent
    agent = get_agent()
    def run_agent():
        result = agent.run(task)
        threading.Thread(target=lambda: _speak(result, "JARVIS"), daemon=True).start()
    threading.Thread(target=run_agent, daemon=True).start()
    return jsonify({"status": "running"})


@app.route("/api/agent/abort", methods=["POST"])
def agent_abort():
    from control.agent import get_agent
    get_agent().abort()
    return jsonify({"status": "aborted"})


@app.route("/api/execute", methods=["POST"])
def execute_code_endpoint():
    """Execute code directly — used by the HUD run button on code blocks."""
    data = request.json or {}
    language = data.get("language", "python").strip()
    code = data.get("code", "").strip()
    timeout = int(data.get("timeout", 30))
    cwd = data.get("cwd")
    if not code:
        return jsonify({"success": False, "output": "No code provided."})
    from control.code_executor import execute_code, format_execution_result
    result = execute_code(language=language, code=code, timeout=timeout, cwd=cwd)
    output = format_execution_result(result, language)
    return jsonify({
        "success": result["success"],
        "output": output,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    })


@app.route("/api/chart", methods=["GET"])
def serve_chart():
    """Serve a chart PNG by file path — used by the HUD chart panel."""
    path = request.args.get("path", "").strip()
    if not path:
        return "No path", 400
    import os
    from pathlib import Path
    full = str(Path(os.path.expanduser(path)).resolve())
    charts_dir = str(Path(os.path.expanduser("~/Desktop/jarvis_charts")).resolve())
    if not full.startswith(charts_dir):
        return "Forbidden", 403
    if not os.path.exists(full):
        return "Not found", 404
    from flask import send_file
    return send_file(full, mimetype="image/png")


@app.route("/api/whatsapp", methods=["POST"])
def whatsapp_incoming():
    data = request.json or {}
    user_input = data.get("message", "").strip()
    sender = data.get("sender", "WhatsApp")
    if not user_input:
        return jsonify({"response": ""})
    response, agent = _route(f"[WhatsApp from {sender}]: {user_input}")
    return jsonify({"response": response, "agent": agent})


@app.route("/api/history", methods=["GET"])
def history():
    from memory.memory import get_recent_history
    rows = get_recent_history(limit=50)
    return jsonify([{"role": r, "content": c} for r, c in rows])


@app.route("/api/briefing", methods=["GET"])
def briefing():
    from brain.briefing import get_briefing_text
    return jsonify({"briefing": get_briefing_text()})


_kokoro_daemon_proc = None
_clone_daemon_proc  = None


def _start_clone_daemon():
    """Launch the Chatterbox voice-cloning daemon if available."""
    global _clone_daemon_proc
    if not os.path.exists(CLONE_PYTHON):
        return
    try:
        if os.path.exists(CLONE_SOCK):
            os.unlink(CLONE_SOCK)
        _clone_daemon_proc = subprocess.Popen(
            [CLONE_PYTHON, CLONE_DAEMON],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        for line in _clone_daemon_proc.stdout:
            if b"ready" in line.lower() or b"listening" in line.lower():
                break
    except Exception:
        pass


def _tts_clone(text: str, agent: str):
    """Ask the Chatterbox clone daemon for voice-cloned audio. Returns WAV bytes or None."""
    import socket as _socket, struct as _struct, json as _json
    if not os.path.exists(CLONE_SOCK):
        return None
    try:
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.settimeout(8)
        sock.connect(CLONE_SOCK)
        msg = _json.dumps({"text": text, "agent": agent}).encode()
        sock.sendall(_struct.pack(">I", len(msg)) + msg)
        raw_len = sock.recv(4)
        if not raw_len or len(raw_len) < 4:
            sock.close(); return None
        wav_len = _struct.unpack(">I", raw_len)[0]
        if wav_len == 0:
            sock.close(); return None
        data = b""
        while len(data) < wav_len:
            chunk = sock.recv(min(65536, wav_len - len(data)))
            if not chunk: break
            data += chunk
        sock.close()
        return data if len(data) == wav_len else None
    except Exception:
        return None


def _start_kokoro_daemon():
    """Launch the Kokoro TTS daemon if model files exist."""
    global _kokoro_daemon_proc
    if not (os.path.exists(KOKORO_PYTHON) and os.path.exists(KOKORO_MODEL)
            and os.path.exists(KOKORO_VOICES)):
        return
    try:
        # Remove stale socket if leftover from previous run
        if os.path.exists(KOKORO_SOCK):
            os.unlink(KOKORO_SOCK)
        _kokoro_daemon_proc = subprocess.Popen(
            [KOKORO_PYTHON, KOKORO_DAEMON],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        # Read until "Kokoro ready." to know it's loaded
        for line in _kokoro_daemon_proc.stdout:
            if b"ready" in line.lower():
                break
    except Exception:
        pass


def _tts_kokoro_daemon(text: str, agent: str):
    """Ask the running Kokoro daemon for audio. Returns WAV bytes or None."""
    import socket as _socket, struct as _struct, json as _json
    if not os.path.exists(KOKORO_SOCK):
        return None
    try:
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.settimeout(25)
        sock.connect(KOKORO_SOCK)
        msg = _json.dumps({"text": text, "agent": agent}).encode()
        sock.sendall(_struct.pack(">I", len(msg)) + msg)
        raw_len = sock.recv(4)
        if not raw_len or len(raw_len) < 4:
            sock.close()
            return None
        wav_len = _struct.unpack(">I", raw_len)[0]
        if wav_len == 0:
            sock.close()
            return None
        data = b""
        while len(data) < wav_len:
            chunk = sock.recv(min(65536, wav_len - len(data)))
            if not chunk:
                break
            data += chunk
        sock.close()
        return data if len(data) == wav_len else None
    except Exception:
        return None


def _tts_kokoro_subprocess(text: str, agent: str):
    """Fallback: spawn kokoro_worker.py process. Slower (model reload each time)."""
    if not (os.path.exists(KOKORO_PYTHON) and os.path.exists(KOKORO_MODEL)
            and os.path.exists(KOKORO_VOICES)):
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
        result = subprocess.run(
            [KOKORO_PYTHON, KOKORO_WORKER, agent, tmp],
            input=text.encode(), capture_output=True, timeout=30,
        )
        if result.returncode == 0 and os.path.exists(tmp):
            data = open(tmp, "rb").read()
            os.unlink(tmp)
            return data
        try:
            os.unlink(tmp)
        except Exception:
            pass
    except Exception:
        pass
    return None


def _tts_kokoro(text: str, agent: str):
    """Try daemon first, fall back to subprocess."""
    wav = _tts_kokoro_daemon(text, agent)
    if wav:
        return wav
    return _tts_kokoro_subprocess(text, agent)


_elevenlabs_dead = False  # cached — don't retry a 401

@app.route("/api/tts", methods=["GET"])
def tts():
    global _elevenlabs_dead
    text = request.args.get("text", "").strip()[:800]
    agent = request.args.get("agent", "JARVIS").strip().upper()
    if not text:
        return Response(status=204)

    from voice.speak import load_key, VOICE_MAP, JARVIS_VOICE_ID, EDGE_VOICE_MAP
    import asyncio, edge_tts as _edge_tts

    # 1. Chatterbox — only if daemon socket is live
    if os.path.exists(CLONE_SOCK):
        wav = _tts_clone(text, agent)
        if wav:
            return Response(wav, mimetype="audio/wav")

    # 2. Kokoro — only if daemon socket is live (skip subprocess; too slow)
    if os.path.exists(KOKORO_SOCK):
        wav = _tts_kokoro_daemon(text, agent)
        if wav:
            return Response(wav, mimetype="audio/wav")

    # 3. edge-tts — fast (~1.5s), free, no auth needed
    voice = EDGE_VOICE_MAP.get(agent, "en-GB-RyanNeural")
    async def _edge_run():
        tts_obj = _edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        await tts_obj.save(tmp)
        return tmp
    try:
        tmp = _run_async(_edge_run())
        data = open(tmp, "rb").read()
        os.unlink(tmp)
        return Response(data, mimetype="audio/mpeg")
    except Exception:
        pass

    # 4. ElevenLabs — cloud fallback (skip if previously 401'd)
    if not _elevenlabs_dead:
        import requests as req
        api_key = load_key()
        if api_key:
            voice_id = VOICE_MAP.get(agent, JARVIS_VOICE_ID)
            try:
                r = req.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    json={"text": text, "model_id": "eleven_turbo_v2_5",
                          "voice_settings": {"stability": 0.75, "similarity_boost": 0.85, "style": 0.2}},
                    headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                    timeout=15,
                )
                if r.status_code == 200:
                    return Response(r.content, mimetype="audio/mpeg")
                if r.status_code == 401:
                    _elevenlabs_dead = True
            except Exception:
                pass

    return Response(status=204)


@app.route("/api/contact_photo", methods=["GET"])
def contact_photo():
    name = request.args.get("name", "").strip()
    if not name or '"' in name:
        return Response(status=404)
    script = f'''tell application "Contacts"
    set matches to (every person whose name contains "{name}")
    if length of matches = 0 then return ""
    set thePerson to item 1 of matches
    try
        return vcard of thePerson
    on error
        return ""
    end try
end tell'''
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=6)
        vcard = result.stdout.strip()
        if not vcard:
            return Response(status=404)
        match = re.search(r'PHOTO[^\n:]*:\s*([A-Za-z0-9+/=\r\n\t ]+)', vcard)
        if not match:
            return Response(status=404)
        photo_b64 = re.sub(r'\s+', '', match.group(1))
        photo_bytes = base64.b64decode(photo_b64)
        return Response(photo_bytes, mimetype="image/jpeg")
    except Exception:
        return Response(status=404)


def _image_search_bing(query: str):
    """Scrape Bing image search — no API key needed."""
    import re as _re, urllib.parse as _up
    import requests as _req
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    url = f"https://www.bing.com/images/search?q={_up.quote(query)}&first=1&count=5"
    r = _req.get(url, headers=headers, timeout=8)
    urls = _re.findall(r"mediaurl=([^&]+)", r.text)
    for u in urls:
        decoded = _up.unquote(u)
        if decoded.startswith("http") and any(decoded.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            return decoded
    # Fallback: return first URL even without clean extension
    for u in urls:
        decoded = _up.unquote(u)
        if decoded.startswith("http"):
            return decoded
    return None


@app.route("/api/image_search", methods=["GET"])
def image_search():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "No query"}), 400
    try:
        url = _image_search_bing(query)
        if url:
            return jsonify({"url": url, "title": query})
    except Exception as e:
        print(f"Image search error: {e}", flush=True)
    # Fallback: DuckDuckGo
    try:
        import warnings, time
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS
        time.sleep(0.3)
        results = list(DDGS().images(query, max_results=3))
        for r in results:
            img_url = r.get("image", "")
            if img_url and img_url.startswith("http"):
                return jsonify({"url": img_url, "title": r.get("title", query)})
    except Exception:
        pass
    return jsonify({"error": "No results"}), 404


@app.route("/api/proactive", methods=["GET"])
def proactive_poll():
    msgs = []
    while not _proactive_q.empty():
        try:
            msgs.append(_proactive_q.get_nowait())
        except Exception:
            break
    return jsonify({"messages": msgs})


@app.route("/api/system_stats", methods=["GET"])
def system_stats():
    stats = {}
    # Battery
    try:
        batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3)
        m = re.search(r'(\d+)%', batt.stdout)
        if m:
            stats["battery"] = int(m.group(1))
            stats["charging"] = "AC Power" in batt.stdout or "charging" in batt.stdout.lower()
            remaining = re.search(r'(\d+:\d+) remaining', batt.stdout)
            stats["battery_time"] = remaining.group(1) if remaining else ""
    except Exception:
        pass
    # CPU (user + sys)
    try:
        cpu_out = subprocess.run(
            ["bash", "-c", "top -l 1 -n 0 | grep 'CPU usage'"],
            capture_output=True, text=True, timeout=5
        )
        mu = re.search(r'([\d.]+)%\s+user', cpu_out.stdout)
        ms = re.search(r'([\d.]+)%\s+sys', cpu_out.stdout)
        if mu and ms:
            stats["cpu"] = round(float(mu.group(1)) + float(ms.group(1)), 1)
    except Exception:
        pass
    # Apple Music now playing
    try:
        music_script = '''tell application "Music"
    if player state is playing or player state is paused then
        set st to player state as string
        set tn to name of current track
        set ar to artist of current track
        set pos to player position as integer
        set dur to duration of current track as integer
        return st & "|" & tn & "|" & ar & "|" & (pos as string) & "|" & (dur as string)
    else
        return "stopped"
    end if
end tell'''
        music_out = subprocess.run(["osascript", "-e", music_script],
                                   capture_output=True, text=True, timeout=4)
        raw = music_out.stdout.strip()
        if raw and raw != "stopped":
            parts = raw.split("|")
            if len(parts) >= 5:
                stats["music"] = {
                    "state": parts[0],
                    "track": parts[1],
                    "artist": parts[2],
                    "position": int(parts[3]),
                    "duration": int(parts[4]),
                    "playing": parts[0] == "playing",
                }
        else:
            stats["music"] = {"playing": False}
    except Exception:
        stats["music"] = {"playing": False}
    return jsonify(stats)


@app.route("/api/music/control", methods=["POST"])
def music_control():
    action = (request.json or {}).get("action", "")
    scripts = {
        "toggle":   'tell application "Music" to playpause',
        "next":     'tell application "Music" to next track',
        "prev":     'tell application "Music" to previous track',
        "play":     'tell application "Music" to play',
        "pause":    'tell application "Music" to pause',
    }
    if action in scripts:
        subprocess.run(["osascript", "-e", scripts[action]], timeout=3)
    return jsonify({"ok": True})


@app.route("/api/observer/quiet", methods=["GET", "POST"])
def observer_quiet():
    from brain.observer import is_quiet, toggle_quiet
    if request.method == "POST":
        now_quiet = toggle_quiet()
        return jsonify({"quiet": now_quiet})
    return jsonify({"quiet": is_quiet()})


@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"status": "online", "version": "3.0", "location": _location})


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


@app.route("/")
def hud():
    hud_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "hud.html")
    resp = send_file(hud_path, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp


if __name__ == "__main__":
    # Background push policy:
    #   ENABLED:
    #     - brain.observer  (every-6-min pattern detection, max 3 pushes/hour,
    #                        5-min cooldown, respects observer_quiet flag)
    #   DISABLED:
    #     - brain.proactive (scheduled weather/news/habit pushes to HUD + Telegram)
    #     - control.wake    (Mac-wake → Telegram morning briefing)
    try:
        from brain.observer import start_observer
        start_observer(hud_queue=_proactive_q)
    except Exception as _e:
        print(f"observer not started: {_e}")
    # Start Chatterbox voice-cloning daemon (actual actor voices via reference audio)
    threading.Thread(target=_start_clone_daemon, daemon=True).start()
    # Start Kokoro TTS daemon (fallback preset voices, fast)
    threading.Thread(target=_start_kokoro_daemon, daemon=True).start()
    print("JARVIS API running on port 8080")
    app.run(host="127.0.0.1", port=8080, debug=False, use_reloader=False, threaded=True)
