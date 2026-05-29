#!/usr/bin/env python3
"""
scripts/audit.py — JARVIS functionality audit.
Generates AUDIT_REPORT.md with ✅/🔴/⚠️ status for all subsystems + tools.
Run: cd ~/jarvis && ./venv/bin/python3 scripts/audit.py
"""
import sys, os, subprocess, json, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

report = []
def log(line): print(line); report.append(line)

log("# JARVIS Functionality Audit")
log(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# ── 1. Server endpoints ────────────────────────────────────────────────────
log("## 1. Server Endpoints\n")
import urllib.request, urllib.error

def check_url(url, label, method="GET", expected_key=None):
    try:
        req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode(errors="ignore")
            if expected_key and expected_key not in body:
                log(f"⚠️  {label} — responded but missing key '{expected_key}': {body[:80]}")
            else:
                log(f"✅ {label} — {r.status} OK")
    except Exception as e:
        log(f"🔴 {label} — {e}")

check_url("http://127.0.0.1:8080/api/status",    "/api/status",    expected_key="online")
check_url("http://127.0.0.1:8080/api/proactive", "/api/proactive", expected_key="messages")
check_url("http://127.0.0.1:8080/api/history",   "/api/history")
check_url("http://127.0.0.1:8080/api/tts?text=test&agent=JARVIS", "/api/tts (audio)")
check_url("http://127.0.0.1:8080/",              "/ (jarvis.html)")
check_url("http://127.0.0.1:8080/bubble",        "/bubble (bubble.html)")
check_url("http://127.0.0.1:8080/api/end_session", "/api/end_session", method="POST", expected_key="ok")

# ── 2. Python test suites ──────────────────────────────────────────────────
log("\n## 2. Test Suites\n")
result = subprocess.run(
    [str(ROOT / "venv/bin/python3"), "-m", "pytest", str(ROOT / "tests"),
     "-q", "--tb=short", "--no-header"],
    capture_output=True, text=True, cwd=str(ROOT)
)
for line in (result.stdout + result.stderr).splitlines():
    if line.strip():
        log(f"    {line}")
if result.returncode == 0:
    log("✅ All test suites passed")
else:
    log("⚠️  Some tests failed (see above)")

# ── 3. Core imports / subsystems ──────────────────────────────────────────
log("\n## 3. Core Subsystem Imports\n")

subsystems = [
    ("brain.router",   "route"),
    ("brain.think",    "think_stream"),
    ("brain.think",    "think_vision_stream"),
    ("memory.memory",  "get_recent_history"),
    ("memory.vault",   "VaultManager"),
    ("voice.speak",    "speak"),
    ("voice.wake",     "WakeWordListener"),
    ("voice.listen",   "listen_until_silence"),
]

for module, symbol in subsystems:
    try:
        m = __import__(module, fromlist=[symbol])
        getattr(m, symbol)
        log(f"✅ {module}.{symbol}")
    except Exception as e:
        log(f"🔴 {module}.{symbol} — {e}")

# ── 4. Tool registry ───────────────────────────────────────────────────────
log("\n## 4. Tool Registry\n")
try:
    from brain.tools.registry import get_tools
    tools = get_tools()
    log(f"✅ Tool registry loaded — {len(tools)} tools registered")
except Exception as e:
    log(f"🔴 Tool registry — {e}")

# ── 5. API keys ────────────────────────────────────────────────────────────
log("\n## 5. API Keys\n")
keys = {
    "ANTHROPIC_API_KEY":   "Anthropic (Claude)",
    "GROQ_API_KEY":        "Groq (Whisper + LLM)",
    "ELEVENLABS_API_KEY":  "ElevenLabs (TTS)",
    "GEMINI_API_KEY":      "Gemini (vision fallback)",
}
for env_key, label in keys.items():
    val = os.environ.get(env_key, "")
    if val:
        masked = val[:8] + "…" + val[-4:] if len(val) > 12 else "***"
        log(f"✅ {label} — {masked}")
    else:
        log(f"⚠️  {label} — NOT SET")

# ── 6. Voice chain ─────────────────────────────────────────────────────────
log("\n## 6. Voice Chain\n")
try:
    import sounddevice as sd
    devs = [d for d in sd.query_devices() if d['max_input_channels'] > 0]
    log(f"✅ Microphone devices: {len(devs)} found ({', '.join(d['name'] for d in devs[:3])})")
except Exception as e:
    log(f"🔴 Microphone: {e}")

try:
    with urllib.request.urlopen("http://127.0.0.1:8080/api/tts?text=test&agent=JARVIS", timeout=5) as r:
        size = len(r.read())
    log(f"✅ TTS /api/tts — {size} bytes audio returned")
except Exception as e:
    log(f"🔴 TTS /api/tts — {e}")

# ── 7. Second Brain ────────────────────────────────────────────────────────
log("\n## 7. Second Brain / Memory\n")
try:
    from memory.memory import get_recent_history
    hist = get_recent_history(limit=5)
    log(f"✅ Conversation DB — {len(hist)} recent messages")
except Exception as e:
    log(f"🔴 Conversation DB: {e}")

try:
    from memory.vault import VaultManager
    vm = VaultManager()
    results = vm.search_vault("Elnatan", max_results=3)
    log(f"✅ Vault search — {len(results)} chars returned")
except Exception as e:
    log(f"🔴 Vault search: {e}")

# ── 8. New features from tonight ──────────────────────────────────────────
log("\n## 8. Tonight's New Features\n")

# Wake word module
try:
    from voice.wake import WakeWordListener
    log("✅ Wake word listener module — importable")
except Exception as e:
    log(f"🔴 Wake word listener — {e}")

# Vision stream
try:
    from brain.think import think_vision_stream
    log("✅ Vision stream (think_vision_stream) — importable")
except Exception as e:
    log(f"🔴 Vision stream — {e}")

# bubble.html has wakeWordFired
bubble = (ROOT / "app" / "bubble.html").read_text()
if "wakeWordFired" in bubble and "enterConversation" in bubble:
    log("✅ bubble.html — conversation mode + wake word wired")
else:
    log("🔴 bubble.html — missing conversation mode or wake word")

# jarvis.html has showSurface
hud = (ROOT / "app" / "jarvis.html").read_text()
if "showSurface" in hud and "show-surface" in hud:
    log("✅ jarvis.html — display surface overlay present")
else:
    log("🔴 jarvis.html — missing display surface")

# Dead files confirmed deleted
for dead in ["app/hud.html", "JARVISApp", "jarvis.py", "start.sh", "voice/clone_daemon.py"]:
    if not (ROOT / dead).exists():
        log(f"✅ {dead} — deleted (house-cleaning done)")
    else:
        log(f"⚠️  {dead} — still present (house-cleaning incomplete)")

# ── Write report ───────────────────────────────────────────────────────────
report_path = ROOT / "AUDIT_REPORT.md"
report_path.write_text("\n".join(report) + "\n")
print(f"\n✓ Report written to {report_path}")
