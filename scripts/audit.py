#!/usr/bin/env python3
"""
scripts/audit.py — JARVIS health check for the FULLY-LOCAL architecture.

Verifies the things that actually make this product work: the local brain
(Ollama), the safety gate, the token-gated server, the autonomy engine, vault
RAG, and the local voice chain. Writes AUDIT_REPORT.md.

Run: cd ~/jarvis && ./venv/bin/python3 scripts/audit.py

Notes:
- The JARVIS brain is local (Ollama). Cloud keys (Anthropic/Groq/Gemini/
  ElevenLabs) are OPTIONAL fallbacks — their absence is NOT a failure.
- This audit is READ-ONLY w.r.t. your data: it never instantiates VaultManager
  against the real ~/Documents/SecondBrain (which would scaffold/write files);
  it exercises vault RAG in a throwaway sandbox instead.
"""
import sys, os, subprocess, tempfile, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env (without clobbering anything already in the environment)
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

report = []
fails = []
def log(line): print(line); report.append(line)
def ok(msg): log(f"✅ {msg}")
def warn(msg): log(f"⚠️  {msg}")
def bad(msg): log(f"🔴 {msg}"); fails.append(msg)

log("# JARVIS Health Check (fully-local)")
log(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# ── 1. Local brain (Ollama) ─────────────────────────────────────────────────
log("## 1. Local Brain (the reasoning path)\n")
try:
    from brain import agent, llm
    if llm.available():
        ok(f"Ollama reachable — FAST={llm.FAST_MODEL}, COMPLEX={llm.COMPLEX_MODEL}")
    else:
        bad("Ollama NOT reachable — start it with `ollama serve` (the brain is offline)")
    for model in (llm.FAST_MODEL, llm.COMPLEX_MODEL):
        try:
            if llm.has_model(model):
                ok(f"model present — {model}")
            else:
                warn(f"model NOT pulled — {model}  (run: ollama pull {model})")
        except Exception as e:
            warn(f"could not check model {model} — {e}")
    if agent.enabled():
        ok("local brain ENABLED (agent.enabled) — JARVIS reasons locally")
    else:
        bad("local brain DISABLED — would fall back to cloud/offline note")
    if agent.cloud_reasoning_allowed():
        warn("cloud reasoning is ALLOWED (JARVIS_ALLOW_CLOUD_BRAIN=1 or local off)")
    else:
        ok("cloud reasoning OFF — fully local (default)")
except Exception as e:
    bad(f"local brain check failed — {e}")

# ── 2. Safety gate ───────────────────────────────────────────────────────────
log("\n## 2. Safety Gate (the non-negotiable)\n")
try:
    from brain import autonomy
    if autonomy.RED_LIST:
        ok(f"RED_LIST loaded — {len(autonomy.RED_LIST)} guarded tools")
    else:
        bad("RED_LIST is EMPTY — the gate would not confirm anything")
    reds = [t for t in ("send_email", "transfer_money", "control_screen",
                        "write_file", "run_shell") if autonomy.is_red(t)]
    if len(reds) >= 4:
        ok(f"is_red() recognizes high-risk tools — {', '.join(reds)}")
    else:
        bad(f"is_red() missing expected red tools — only {reds}")
    log(f"    mode={autonomy.get_autonomy_mode()}  away={autonomy.is_away()}  paused={autonomy.is_paused()}")
    # Fail-closed: a gate exception must DENY, not execute (read-only probe).
    import brain.tools.registry as reg
    _g = autonomy.gate
    try:
        autonomy.gate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("probe"))
        @reg.tool(description="probe", parameters={}, risk="red")
        def _audit_failclose_probe():
            return "RAN"
        out = reg.execute_tool("_audit_failclose_probe", {}, source="user")
        if "RAN" not in out:
            ok("gate FAILS CLOSED on internal error (does not execute)")
        else:
            bad("gate FAILS OPEN — tool ran despite gate error")
    finally:
        autonomy.gate = _g
        reg.TOOL_REGISTRY.pop("_audit_failclose_probe", None)
except Exception as e:
    bad(f"safety gate check failed — {e}")

# ── 3. Self-write firewall ───────────────────────────────────────────────────
log("\n## 3. Self-write Firewall\n")
try:
    import control.files as cf
    if "Refused" in cf.write_file("brain/autonomy.py", "RED_LIST=set()"):
        ok("refuses to overwrite its own code (brain/autonomy.py)")
    else:
        bad("self-write firewall did NOT block writing to brain/autonomy.py")
except Exception as e:
    bad(f"self-write firewall check failed — {e}")

# ── 4. Token-gated server ───────────────────────────────────────────────────
log("\n## 4. Token-gated Server\n")
import urllib.request, urllib.error
BASE = "http://127.0.0.1:8080"

def _status(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return None, b""

st, _ = _status(f"{BASE}/api/status")
if st is None:
    warn("server not running — start with `bash scripts/start.sh` to check the gate")
else:
    ok("/api/status reachable (exempt endpoint)")
    # A NON-exempt endpoint must reject an unauthenticated request.
    code_noauth, _ = _status(f"{BASE}/api/pending")
    if code_noauth == 403:
        ok("/api/pending → 403 WITHOUT token (gate enforced)")
    else:
        bad(f"/api/pending returned {code_noauth} without a token — gate NOT enforced")
    tok_file = ROOT / ".session_token"
    if tok_file.exists():
        tok = tok_file.read_text().strip()
        code_auth, _ = _status(f"{BASE}/api/pending", {"X-JARVIS-Token": tok})
        if code_auth == 200:
            ok("/api/pending → 200 WITH the persisted token")
        else:
            warn(f"/api/pending returned {code_auth} with token (server may predate the token)")

# ── 5. Autonomy engine ───────────────────────────────────────────────────────
log("\n## 5. Autonomy Engine\n")
for module, symbol in [("brain.runner", "run_goal"), ("brain.proactive", None),
                       ("brain.presence", None)]:
    try:
        m = __import__(module, fromlist=[symbol or "x"])
        if symbol:
            getattr(m, symbol)
        ok(f"{module}{('.' + symbol) if symbol else ''} — importable")
    except Exception as e:
        bad(f"{module} — {e}")

# ── 6. Core subsystems + tool registry ──────────────────────────────────────
log("\n## 6. Core Subsystems\n")
for module, symbol in [
    ("brain.router", "route"),
    ("brain.think", "think_stream"),
    ("memory.memory", "get_recent_history"),
    ("memory.vault", "VaultManager"),
    ("security.identity", "authenticate"),
    ("voice.local_stt", "transcribe_or"),
    ("voice.speak", "speak"),
]:
    try:
        m = __import__(module, fromlist=[symbol])
        getattr(m, symbol)
        ok(f"{module}.{symbol}")
    except Exception as e:
        bad(f"{module}.{symbol} — {e}")

try:
    from brain.tools.registry import get_tools
    ok(f"tool registry — {len(get_tools())} tools registered")
except Exception as e:
    bad(f"tool registry — {e}")

# ── 7. Vault RAG (sandbox — NEVER the real vault) ───────────────────────────
log("\n## 7. Vault RAG (Second Brain)\n")
try:
    from memory.vault import VaultManager, DEFAULT_VAULT_PATH
    with tempfile.TemporaryDirectory() as td:
        vm = VaultManager(vault_path=td)          # sandbox — no writes to the real vault
        vm.search_vault("Elnatan", max_results=3)  # exercises the search path
        ok("vault search path works (verified in a sandbox)")
    # Report the real vault read-only (stat only, no instantiation).
    real = Path(DEFAULT_VAULT_PATH)
    if real.exists():
        n = sum(1 for _ in real.rglob("*.md"))
        ok(f"real vault present at {real} — {n} notes (not modified by this audit)")
    else:
        warn(f"real vault not found at {real} (will scaffold on first real use)")
except Exception as e:
    bad(f"vault RAG check failed — {e}")

# ── 8. Local voice chain ────────────────────────────────────────────────────
log("\n## 8. Local Voice Chain\n")
try:
    import sounddevice as sd
    devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
    ok(f"microphone devices: {len(devs)} ({', '.join(d['name'] for d in devs[:3])})")
except Exception as e:
    warn(f"microphone probe — {e}")
try:
    import voice.local_stt as stt
    if stt.available():
        ok("local STT available (faster-whisper)")
    else:
        warn("local STT unavailable — would fall back to Groq (needs network)")
except Exception as e:
    warn(f"local STT — {e}")
# TTS daemon is optional/needs starting; report, don't fail.
st_tts, body = _status(f"{BASE}/api/tts?text=test&agent=JARVIS")
if st_tts == 200 and body:
    ok(f"TTS /api/tts — {len(body)} bytes (Kokoro daemon up)")
elif st_tts is None:
    warn("TTS not checked (server not running)")
else:
    warn("TTS returned no audio — start the Kokoro daemon (bash scripts/start.sh)")

# ── 9. Test suite ────────────────────────────────────────────────────────────
log("\n## 9. Test Suite\n")
result = subprocess.run(
    [str(ROOT / "venv/bin/python3"), "-m", "pytest", str(ROOT / "tests"), "-q", "--no-header"],
    capture_output=True, text=True, cwd=str(ROOT),
)
tail = [l for l in (result.stdout + result.stderr).splitlines() if l.strip()][-3:]
for l in tail:
    log(f"    {l}")
if result.returncode == 0:
    ok("test suite passed")
else:
    bad("test suite FAILED (see above)")

# ── Summary ──────────────────────────────────────────────────────────────────
log("\n## Summary\n")
if fails:
    log(f"🔴 {len(fails)} issue(s) need attention:")
    for f in fails:
        log(f"   - {f}")
else:
    log("✅ All health checks passed.")

report_path = ROOT / "AUDIT_REPORT.md"
report_path.write_text("\n".join(report) + "\n")
print(f"\n✓ Report written to {report_path}")
sys.exit(1 if fails else 0)
