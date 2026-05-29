# JARVIS "Make It Feel Human" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform JARVIS from a robot chatbot into a real voice-first life assistant — wake word, hands-free conversation, ambient orb, show-on-demand surface, human personas, vision, and clean repo.

**Architecture:** 7 workstreams executed in order: voice repair → conversation mode → persona rewrite → ambient orb → show surface → vision → house-cleaning → audit. All changes are additive except WS7 (house-cleaning, gated behind a checkpoint). The orb (`app/bubble.html`) + HUD (`app/jarvis.html`) are the only live UIs; Flask backend (`ui/server.py`) + agent brain (`brain/`) are unchanged except for targeted additions.

**Tech Stack:** pywebview JsApi bridge, sounddevice, openwakeword (offline wake word, with Groq energy-gate fallback), edge-tts (primary TTS), Groq Whisper (STT), Claude/Gemini vision, Flask SSE streaming

---

## Execution Order

Tasks follow the spec's execution order:
0 → Checkpoint
1–4 → WS1 Voice (repair + wake + conversation + echo guard)
5–6 → WS4 Persona/Brain
7–8 → WS2+WS3 Ambient orb + Show surface
9 → WS6 Vision
10 → WS7 House-cleaning
11 → WS5 Audit

---

## Task 0: Checkpoint commit

**Files:** none (git only)

- [ ] **Step 1: Commit all current WIP on main**

```bash
cd ~/jarvis
git add -A
git status
git commit -m "checkpoint: pre-human-spec implementation state" --allow-empty
```

Expected: commit hash printed. This is the safety net — everything before tonight's changes is recoverable.

---

## Task 1: Voice repair — verify TTS works end-to-end

**Files:**
- No code changes; diagnose and fix runtime state

- [ ] **Step 1: Kill stale Kokoro/Chatterbox daemons**

```bash
pkill -f kokoro_daemon 2>/dev/null || true
pkill -f clone_daemon  2>/dev/null || true
rm -f ~/jarvis/voice/kokoro.sock ~/jarvis/voice/clone.sock 2>/dev/null || true
echo "Daemons killed"
```

Expected: no error (pkill returns 1 if nothing to kill — that's fine).

- [ ] **Step 2: Verify the running Flask server returns audio from /api/tts**

```bash
curl -s "http://127.0.0.1:8080/api/tts?text=Online+sir&agent=JARVIS" \
  -o /tmp/tts_test.mp3 -w "%{http_code} %{size_download}\n"
file /tmp/tts_test.mp3
```

Expected: `200 <size>` and `MPEG ADTS, layer III` (or `Audio file`). If 204, TTS failed — check Flask log: `tail -20 ~/jarvis/flask.log`.

- [ ] **Step 3: If server isn't running, restart it**

```bash
lsof -i :8080 | grep LISTEN || (
  pkill -f "ui/server.py" 2>/dev/null || true
  sleep 1
  cd ~/jarvis && ./venv/bin/python3 ui/server.py >> flask.log 2>&1 &
  sleep 3
  curl -s http://127.0.0.1:8080/api/status
)
```

Expected: `{"status": "online", "version": "3.0"}`.

- [ ] **Step 4: Commit (nothing to commit here, just confirm state)**

```bash
echo "Voice repair: edge-tts working, stale daemons cleared"
```

---

## Task 2: Create `voice/wake.py` — wake word listener

**Files:**
- Create: `voice/wake.py`

- [ ] **Step 1: Install openwakeword into the venv**

```bash
cd ~/jarvis
./venv/bin/pip install openwakeword --quiet
./venv/bin/python3 -c "import openwakeword; print('oww ok')" 2>&1
```

If it fails with a build error, note it — the energy-gate fallback will be used automatically.

- [ ] **Step 2: Write `voice/wake.py`**

```python
"""
voice/wake.py — Speech wake-word detector for JARVIS.

Primary path: openwakeword (offline, low-latency).
Fallback path: energy-gate → Groq Whisper keyword confirm.

Usage:
    from voice.wake import WakeWordListener
    listener = WakeWordListener(on_wake=my_callback)
    listener.start()          # background thread
    listener.mute()           # suppress during TTS
    listener.unmute()
    listener.stop()
"""
import os
import threading
import time
import numpy as np
import sounddevice as sd

SAMPLE_RATE   = 16000
CHUNK_SECS    = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_SECS)
KEYWORDS      = ("jarvis", "hey jarvis")

# Energy threshold for voice onset (int16 RMS). 500 ≈ quiet speech.
_ENERGY_THRESH = 500


class WakeWordListener:
    """Continuous wake-word detector that calls `on_wake` on detection."""

    def __init__(self, on_wake, keywords=KEYWORDS):
        self._on_wake   = on_wake
        self._keywords  = keywords
        self._running   = False
        self._muted     = False
        self._thread    = None
        self._oww       = self._init_oww()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def mute(self):
        """Suppress detection while JARVIS is speaking (echo guard)."""
        self._muted = True

    def unmute(self):
        self._muted = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _init_oww(self):
        try:
            from openwakeword.model import Model
            m = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            print("[Wake] openwakeword loaded (offline mode)", flush=True)
            return m
        except Exception as e:
            print(f"[Wake] openwakeword unavailable ({e}), using energy-gate fallback", flush=True)
            return None

    def _loop(self):
        if self._oww is not None:
            self._loop_oww()
        else:
            self._loop_energy_gate()

    # ── Path A: openwakeword ──────────────────────────────────────────────────

    def _loop_oww(self):
        import queue as _q
        q: _q.Queue = _q.Queue()

        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=CHUNK_SAMPLES, callback=_cb):
            while self._running:
                try:
                    chunk = q.get(timeout=1.0)
                    if self._muted:
                        continue
                    audio = chunk.flatten()
                    predictions = self._oww.predict(audio)
                    for _model_name, score in predictions.items():
                        if score > 0.5:
                            print(f"[Wake] openwakeword triggered (score={score:.2f})", flush=True)
                            self._fire()
                            break
                except Exception:
                    pass

    # ── Path B: energy-gate + Groq keyword confirm ────────────────────────────

    def _loop_energy_gate(self):
        import queue as _q
        q: _q.Queue = _q.Queue()
        speech_buf: list = []

        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=CHUNK_SAMPLES, callback=_cb):
            while self._running:
                try:
                    chunk = q.get(timeout=1.0)
                    if self._muted:
                        speech_buf.clear()
                        continue

                    rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                    if rms > _ENERGY_THRESH:
                        speech_buf.append(chunk)
                        # Keep at most 5 s of audio
                        if len(speech_buf) > int(5.0 / CHUNK_SECS):
                            speech_buf.pop(0)
                    elif speech_buf:
                        # Speech ended — run keyword check
                        audio = np.concatenate(speech_buf).flatten()
                        speech_buf.clear()
                        if self._groq_keyword_check(audio):
                            self._fire()
                except Exception:
                    pass

    def _groq_keyword_check(self, audio_int16: np.ndarray) -> bool:
        """Transcribe audio with Groq Whisper and check for wake keyword."""
        import scipy.io.wavfile as wavfile
        import tempfile
        from groq import Groq

        groq_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_key:
            return False

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            wavfile.write(tmp, SAMPLE_RATE, audio_int16)
            client = Groq(api_key=groq_key)
            with open(tmp, "rb") as fh:
                result = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=("audio.wav", fh, "audio/wav"),
                    response_format="text",
                )
            text = (result or "").lower().strip()
            matched = any(kw in text for kw in self._keywords)
            if matched:
                print(f"[Wake] keyword detected in: '{text}'", flush=True)
            return matched
        except Exception:
            return False
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _fire(self):
        try:
            self._on_wake()
        except Exception as e:
            print(f"[Wake] on_wake callback error: {e}", flush=True)
        # Debounce: ignore wake signals for 1 s after firing
        time.sleep(1.0)
```

- [ ] **Step 3: Verify the file imports cleanly**

```bash
cd ~/jarvis
./venv/bin/python3 -c "from voice.wake import WakeWordListener; print('wake OK')"
```

Expected: `wake OK` (possibly with a "[Wake] openwakeword unavailable" line — that's fine).

- [ ] **Step 4: Commit**

```bash
git add voice/wake.py requirements.txt
git commit -m "feat(WS1): add voice/wake.py wake-word listener with openwakeword + Groq fallback"
```

---

## Task 3: Wire wake listener + show_content into JsApi (`app/main.py`)

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add `_wake_listener` field and four new methods to `JsApi`**

Read `app/main.py`. In the `JsApi.__init__` method, find `self._hud_visible = False` and add after it:

```python
        self._wake_listener = None  # WakeWordListener, started after windows load
```

Then add these **four** methods after `quit_app()` (before `check_mic_permission`):

```python
    # ── WAKE WORD ────────────────────────────────────────────────────────────

    def start_wake_listener(self):
        """Start the continuous background wake-word listener.
        Called once from bubble.html on pywebviewready.
        Returns True on success, error string on failure."""
        if self._wake_listener is not None:
            return True
        try:
            from voice.wake import WakeWordListener

            def _on_wake():
                """Fire JS wakeWordFired() in the bubble window."""
                try:
                    if self._bubble:
                        self._bubble.evaluate_js("wakeWordFired()")
                except Exception as e:
                    print(f"[Wake] evaluate_js error: {e}", flush=True)

            self._wake_listener = WakeWordListener(on_wake=_on_wake)
            self._wake_listener.start()
            print("[Wake] listener started", flush=True)
            return True
        except Exception as e:
            print(f"[Wake] start failed: {e}", flush=True)
            return str(e)

    def mute_wake(self):
        """Echo guard — suppress wake detection while TTS is playing."""
        if self._wake_listener:
            self._wake_listener.mute()

    def unmute_wake(self):
        """Re-enable wake detection after TTS ends."""
        if self._wake_listener:
            self._wake_listener.unmute()

    def show_content(self, payload: str):
        """Called by bubble.html to push a [SHOW:...] payload to the HUD window.
        Avoids localStorage cross-window isolation issue in WKWebView."""
        import json
        try:
            if self._hud:
                self._hud.show()
                self._hud_visible = True
                self._hud.evaluate_js(f"showSurface({json.dumps(payload)})")
        except Exception as e:
            print(f"[JsApi.show_content] {e}", flush=True)
```

- [ ] **Step 2: Verify compilation**

```bash
cd ~/jarvis
./venv/bin/python3 -m py_compile app/main.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat(WS1): add start_wake_listener/mute_wake/unmute_wake to JsApi"
```

---

## Task 4: Conversation mode + echo guard in `app/bubble.html`

**Files:**
- Modify: `app/bubble.html`

This task adds four capabilities to the orb's JS:
1. `wakeWordFired()` — Python calls this when wake word detected
2. Echo guard — mute wake word while JARVIS speaks
3. Conversation mode — auto-re-arm mic after each reply (no re-wake)
4. Auto-close — after 20 s of silence, exit conversation mode

- [ ] **Step 1: Replace the entire `<script>` block in `app/bubble.html`**

Find the opening `<script>` tag (line 135) and replace everything from `<script>` to `</script>` with:

```html
<script>
'use strict';
const API_BASE = 'http://127.0.0.1:8080';

let _state         = 'calm';
let _micTimer      = null;
let _tts           = null;
let _capTimer      = null;
let _apiReady      = false;
let _inConversation = false;   // true = hands-free mode, auto re-arm
let _convTimer     = null;     // auto-close after silence

const CONV_SILENCE_MS = 22000; // close conversation after 22 s of silence

function api() { return (window.pywebview && window.pywebview.api) || null; }

window.addEventListener('pywebviewready', () => {
  _apiReady = true;
  const a = api();
  if (a) {
    // Start wake-word listener as soon as the native bridge is ready
    try { a.start_wake_listener(); } catch(_) {}
  }
});

function setState(s) {
  _state = s;
  document.body.className = s;
}

function showCap(text) {
  const el = document.getElementById('cap');
  el.textContent = text.length > 42 ? text.slice(0, 40) + '…' : text;
  el.classList.add('show');
  clearTimeout(_capTimer);
  _capTimer = setTimeout(() => el.classList.remove('show'), 6000);
}

/* ── ECHO GUARD helpers ────────────────────────────────────────────────── */
function muteWake() {
  const a = api();
  if (a) { try { a.mute_wake(); } catch(_) {} }
}
function unmuteWake() {
  const a = api();
  if (a) { try { a.unmute_wake(); } catch(_) {} }
}

/* ── CONVERSATION MODE ─────────────────────────────────────────────────── */
function enterConversation() {
  _inConversation = true;
  resetConvTimer();
}

function exitConversation() {
  _inConversation = false;
  clearTimeout(_convTimer);
  _convTimer = null;
}

function resetConvTimer() {
  clearTimeout(_convTimer);
  _convTimer = setTimeout(() => {
    // Silence too long — close conversation mode
    exitConversation();
    if (_state === 'listening' || _state === 'thinking') {
      setState('calm');
    }
  }, CONV_SILENCE_MS);
}

/* ── WAKE WORD CALLBACK (called by Python via evaluate_js) ─────────────── */
function wakeWordFired() {
  if (_state === 'calm' || _state === 'has') {
    enterConversation();
    talk();
  }
  // Ignore if already listening/thinking/speaking
}

/* ── TALK (native mic via pywebview bridge) ────────────────────────────── */
async function talk() {
  const a = api();
  if (!a) { return; }

  // Barge-in: tapping while speaking stops playback and starts new turn
  if (_state === 'speaking') {
    stopTTS();
    unmuteWake();
    setState('listening');
    clearTimeout(_micTimer);
    let ok = false;
    try { ok = await a.start_recording(); } catch(_) {}
    if (ok === true) {
      _micTimer = setTimeout(() => { if (_state === 'listening') talk(); }, 10000);
    } else {
      setState('calm');
    }
    return;
  }

  if (_state === 'listening') {
    setState('thinking');
    clearTimeout(_micTimer);
    let text = '';
    try { text = await a.stop_recording(); } catch(_) {}
    if (text && text.trim()) {
      resetConvTimer();
      streamReply(text.trim());
    } else {
      setState('calm');
      if (!_inConversation) exitConversation();
    }
    return;
  }

  // Start listening
  let ok = false;
  try { ok = await a.start_recording(); } catch(_) {}
  if (ok === true) {
    setState('listening');
    clearTimeout(_micTimer);
    _micTimer = setTimeout(() => { if (_state === 'listening') talk(); }, 10000);
  } else {
    setState('calm');
    exitConversation();
  }
}

/* ── STREAM a reply ─────────────────────────────────────────────────────── */
async function streamReply(text, imageB64) {
  setState('thinking');
  let full = '', agent = 'JARVIS';
  let showPayload = null;
  try {
    let url = `${API_BASE}/api/stream?message=` + encodeURIComponent(text);
    if (imageB64) url += '&image_b64=' + encodeURIComponent(imageB64);
    const res = await fetch(url);
    const reader = res.body.getReader();
    const dec    = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith('data: ')) continue;
        let evt;
        try { evt = JSON.parse(t.slice(6)); } catch(_) { continue; }
        if (evt.type === 'speaker') { agent = evt.name || agent; }
        else if (evt.type === 'text') { full += evt.chunk || ''; }
        else if (evt.type === 'done') {
          full  = evt.full  || full;
          agent = evt.agent || agent;
        }
      }
    }
  } catch(_) {}

  // Extract [SHOW:...] payload before speaking
  const showMatch = full.match(/\[SHOW:([^\]]*)\]/i);
  if (showMatch) showPayload = showMatch[1].trim();

  // Strip all [SHOW:...] tags from spoken text
  const clean = (full || '').replace(/\[SHOW:[^\]]*\]/gi, '').replace(/\s{2,}/g, ' ').trim();

  if (showPayload) handleShow(showPayload);

  if (clean) {
    speak(clean, agent);
  } else {
    setState('calm');
    if (_inConversation) {
      // Empty reply — auto-re-arm immediately
      resetConvTimer();
      talk();
    }
  }
}

/* ── SHOW directive handler ─────────────────────────────────────────────── */
function handleShow(payload) {
  // Use show_content() — this calls evaluate_js on the HUD window directly.
  // DO NOT use localStorage: each WKWebView has its own isolated localStorage.
  const a = api();
  if (a) { try { a.show_content(payload); } catch(_) {} }
}

/* ── TTS ─────────────────────────────────────────────────────────────────── */
function stopTTS() {
  if (_tts) { _tts.pause(); _tts.src = ''; _tts = null; }
}

function speak(text, agent) {
  stopTTS();
  setState('speaking');
  showCap(text);
  muteWake();  // Echo guard: suppress wake while JARVIS speaks
  try {
    _tts = new Audio(
      `${API_BASE}/api/tts?text=` + encodeURIComponent(text.slice(0, 800)) +
      `&agent=` + encodeURIComponent(agent || 'JARVIS')
    );
    _tts.onended = () => {
      _tts = null;
      if (_state === 'speaking') setState('calm');
      // Echo guard: small cooldown before unmuting
      setTimeout(() => {
        unmuteWake();
        // Conversation mode: auto-re-arm mic for next turn
        if (_inConversation) {
          resetConvTimer();
          talk();
        }
      }, 400);
    };
    _tts.onerror = () => {
      _tts = null;
      if (_state === 'speaking') setState('calm');
      unmuteWake();
      if (_inConversation) { resetConvTimer(); talk(); }
    };
    _tts.play().catch(() => {
      _tts = null;
      if (_state === 'speaking') setState('calm');
      unmuteWake();
      if (_inConversation) { resetConvTimer(); talk(); }
    });
  } catch(_) {
    setState('calm');
    unmuteWake();
  }
}

/* ── PROACTIVE POLL ─────────────────────────────────────────────────────── */
(function poll() {
  async function tick() {
    try {
      const res = await fetch(`${API_BASE}/api/proactive`);
      if (res.ok) {
        const { messages = [] } = await res.json();
        for (const m of messages) {
          if (m.visibility === 'surface') {
            if (_state === 'calm') setState('has');
            const txt = (m.text || '').trim();
            if (txt) { showCap(txt); speak(txt, m.agent || 'JARVIS'); }
          }
        }
      }
    } catch(_) {}
    setTimeout(tick, 10000);
  }
  setTimeout(tick, 4000);
})();

/* ── WIRING ─────────────────────────────────────────────────────────────── */
document.getElementById('orb').addEventListener('click', e => {
  e.stopPropagation();
  // Single click → toggle mic (manual mode, enters conversation)
  if (_state === 'calm' || _state === 'has') enterConversation();
  talk();
});

document.getElementById('expand').addEventListener('click', e => {
  e.stopPropagation();
  const a = api();
  if (a) { try { a.toggle_hud(); } catch(_) {} }
});

document.getElementById('quit').addEventListener('click', e => {
  e.stopPropagation();
  const a = api();
  if (a) { try { a.quit_app(); } catch(_) {} }
});
</script>
```

- [ ] **Step 2: Verify the HTML is valid (no syntax errors in the script)**

```bash
cd ~/jarvis
node -e "
const fs = require('fs');
const html = fs.readFileSync('app/bubble.html','utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('NO SCRIPT'); process.exit(1); }
new Function(m[1]);
console.log('script syntax OK');
" 2>&1
```

Expected: `script syntax OK`

- [ ] **Step 3: Commit**

```bash
git add app/bubble.html
git commit -m "feat(WS1): conversation mode + echo guard + wake-word integration in bubble.html"
```

---

## Task 5: Persona rewrite — JARVIS + voice-natural tone

**Files:**
- Modify: `prompts/personas/jarvis.md`
- Modify: `prompts/personas/friday.md` (minor — add voice-natural rule)
- Modify: `prompts/personas/karen.md` (minor — add voice-natural rule)
- Modify: `prompts/personas/veronica.md` (minor — add voice-natural rule)

- [ ] **Step 1: Update JARVIS's `## Role` section (end of jarvis.md)**

In `prompts/personas/jarvis.md`, find the `## Role` block (lines ~272–277):

```markdown
## Role

- Best at tools, code, architecture, strategy, research, and execution.
- You excel at long-horizon thinking and connecting dots across business, life, and projects.
- You are the one who gets things built and shipped.
- You have access to the full tool set. When a request requires action in the world, you are the correct agent.
- Use this persona for: any message containing tool keywords, score 4–5 requests, when the user explicitly says "Jarvis" or addresses you as the primary system.
```

Replace with:

```markdown
## Role

You are Elnatan's primary life assistant — not just a work tool. Your domain is everything: school, personal growth, relationships, entertainment, health, ideas, and yes, also business and code when it's relevant. Business is one area among many; it does not define your personality or default every conversation toward Nexel and Addis Market.

- Best at tools, code, architecture, strategy, research, and execution.
- Equally comfortable with personal questions, casual conversation, and life decisions.
- You connect dots across his entire life — not just his projects.
- When a request requires action in the world, you are the correct agent.
- Use this persona for: any message containing tool keywords, score 4–5 requests, or when the user explicitly addresses you as JARVIS.

## Voice Mode Rules (CRITICAL for spoken replies)

When your reply will be spoken aloud (most conversations via the orb), write for the ear:
- Short, complete sentences. No bullet lists. No asterisks. No headers. Plain speech.
- A spoken reply should sound exactly like a person talking — not a report being read.
- Maximum 3 sentences for conversational replies. More only when genuinely needed (instructions, research).
- No markdown formatting in spoken replies. The listener can't see formatting.
- Never start with "Certainly", "Of course", "Great", "Absolutely", or any filler opener.
```

- [ ] **Step 2: Add voice mode rule to `prompts/personas/friday.md`**

In `friday.md`, find `## Limits` and add after the last bullet in that section:

```markdown
- **VOICE MODE:** When replying to a voice message, write for the ear. Short sentences. No lists, no bullet points, no markdown. Plain spoken language. Max 2 sentences unless depth is genuinely needed.
```

- [ ] **Step 3: Add voice mode rule to `prompts/personas/karen.md`**

In `karen.md`, find `## Limits` (or the last section) and add:

```markdown
- **VOICE MODE:** When replying to a voice message, write for the ear. Short sentences. No lists, no bullet points, no markdown. Warm spoken language.
```

- [ ] **Step 4: Add voice mode rule to `prompts/personas/veronica.md`**

In `veronica.md`, find the `## Voice & Tone` section and add as the last bullet:

```markdown
- **VOICE MODE:** Short, declarative sentences. No lists or markdown when spoken. Structure through sentence rhythm, not formatting.
```

- [ ] **Step 5: Extend [SHOW:] directive vocab in `prompts/personas/jarvis.md`**

In `prompts/personas/jarvis.md`, find the `**Format:** [SHOW: specific descriptive query]` line (in the VISUAL DISPLAY section). After the existing format examples, add:

```markdown
**Extended SHOW vocabulary (use when appropriate):**
- `[SHOW: search query]` — image search (default, for visual subjects)
- `[SHOW: url=https://...]` — open a webpage in the display surface
- `[SHOW: image=/path/to/file.jpg]` — show a local image
- `[SHOW: file=/path/to/document.txt]` — show a local file's contents
- `[SHOW: app=AppName]` — launch a macOS app
- `[SHOW: html=<p>content</p>]` — render custom HTML in the surface
```

- [ ] **Step 6: Commit**

```bash
git add prompts/personas/jarvis.md prompts/personas/friday.md \
        prompts/personas/karen.md prompts/personas/veronica.md
git commit -m "feat(WS4): rewrite JARVIS role as life assistant + voice-natural rules + SHOW vocab"
```

---

## Task 6: Broaden Second Brain vault gate to fire on all conversational turns

**Files:**
- Modify: `brain/think.py`

**Background:** `_build_context()` calls `_get_personal_context(user_input)` only when
`_should_query_personal(user_input)` returns True. That function scores keywords from
`_PERSONAL_SIGNALS`. For casual chat ("what's up?", "how are you feeling?"), no personal
signals match → vault context is silently skipped → replies are not grounded. Fix: always
query the vault for conversational turns (vault search is a local text search, cheap).

- [ ] **Step 1: Find `_should_query_personal` in `brain/think.py`**

```bash
grep -n "_should_query_personal\|_PERSONAL_SIGNALS\|_PROJECT_SIGNALS" brain/think.py | head -15
```

This will show the line numbers for the function and its signal sets.

- [ ] **Step 2: Replace `_should_query_personal` to always return True**

Find this function in `brain/think.py`:

```python
def _should_query_personal(user_input: str) -> bool:
    lower = user_input.lower()
    p_score = sum(1 for s in _PERSONAL_SIGNALS if s in lower)
    j_score = sum(1 for s in _PROJECT_SIGNALS if s in lower)
    return p_score >= j_score  # default True when tied or no signals (0 == 0)
```

Replace with:

```python
def _should_query_personal(user_input: str) -> bool:
    """Always query the personal vault — it's a fast local text search and
    grounding every reply in real context is the whole point of the Second Brain."""
    # Only skip for purely system/tool turns that have no conversational content
    if not user_input or len(user_input.strip()) < 4:
        return False
    return True
```

- [ ] **Step 3: Verify compilation**

```bash
cd ~/jarvis
./venv/bin/python3 -m py_compile brain/think.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 4: Restart Flask and test grounding with a non-keyword query**

```bash
pkill -f "ui/server.py" 2>/dev/null || true; sleep 1
cd ~/jarvis && ./venv/bin/python3 ui/server.py >> flask.log 2>&1 &
sleep 4
curl -s "http://127.0.0.1:8080/api/stream?message=what+are+you+thinking+about" 2>/dev/null | \
  grep -o '"chunk":"[^"]*"' | head -10
```

Expected: a reply that sounds grounded in Elnatan's context (not a generic "I'm an AI" deflection).

- [ ] **Step 5: Commit**

```bash
git add brain/think.py
git commit -m "fix(WS4): broaden Second Brain vault gate — always query on conversational turns"
```

---

## Task 7: Ambient orb — kill the chatbot default in `app/bubble.html`

**Files:**
- Modify: `app/bubble.html`

The expand button (`#expand`) currently opens the HUD as a chat window. The spec says: the HUD should only appear when there's content to show (SHOW pipeline), not as a manual chat toggle. Keep a long-press fallback for text access.

- [ ] **Step 1: Replace the `#expand` click handler with a long-press-only chat toggle**

In `app/bubble.html`, find:

```javascript
document.getElementById('expand').addEventListener('click', e => {
  e.stopPropagation();
  const a = api();
  if (a) { try { a.toggle_hud(); } catch(_) {} }
});
```

Replace with:

```javascript
// Long-press (500ms) on expand = open text chat (escape hatch only)
// Short click = no-op (HUD only opens from SHOW directives or proactive alerts)
let _expandPressTimer = null;
const expandBtn = document.getElementById('expand');
expandBtn.addEventListener('mousedown', e => {
  e.stopPropagation();
  _expandPressTimer = setTimeout(() => {
    const a = api();
    if (a) { try { a.toggle_hud(); } catch(_) {} }
    _expandPressTimer = null;
  }, 500);
});
expandBtn.addEventListener('mouseup',   e => { clearTimeout(_expandPressTimer); });
expandBtn.addEventListener('mouseleave',e => { clearTimeout(_expandPressTimer); });
expandBtn.addEventListener('click',     e => { e.stopPropagation(); }); // prevent default
```

Also update the title attribute to hint at the long-press. Find `<button id="expand" class="ctl" title="Open JARVIS">` and change to `<button id="expand" class="ctl" title="Hold to open text chat">`.

- [ ] **Step 2: Verify the JS is still valid**

```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('app/bubble.html','utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
new Function(m[1]); console.log('OK');
" 2>&1
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/bubble.html
git commit -m "feat(WS2): expand button is now long-press only — HUD no longer auto-opens as chat"
```

---

## Task 8: `app/jarvis.html` → display surface + [SHOW:...] rendering

**Files:**
- Modify: `app/jarvis.html`

The HUD keeps its full chat UI but gains a **display surface mode** that activates when a `[SHOW:...]` payload arrives via `localStorage`. In display mode, the chat panel is hidden and the show content is rendered fullscreen.

- [ ] **Step 1: Read the current `app/jarvis.html` structure**

```bash
grep -n "id=\|#app\|#main\|#bottombar\|DOMContentLoaded\|localStorage\|init" app/jarvis.html | head -30
wc -l app/jarvis.html
```

- [ ] **Step 2: Add display-surface overlay to `app/jarvis.html`**

Find the line `</style>` (end of the CSS) in `app/jarvis.html` and add these CSS rules before it:

```css
/* ── DISPLAY SURFACE OVERLAY ──────────────────────────────────────────── */
#show-surface {
  display: none;
  position: fixed; inset: 0; z-index: 9999;
  background: var(--bg);
  flex-direction: column;
  align-items: stretch;
}
#show-surface.active { display: flex; }
#show-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 18px; border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
#show-label {
  font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  color: var(--cyan); text-transform: uppercase;
}
#show-dismiss {
  background: none; border: none; color: var(--text-2);
  font-size: 18px; cursor: pointer; padding: 4px 8px;
}
#show-dismiss:hover { color: var(--text-1); }
#show-body {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
}
#show-body iframe {
  width: 100%; height: 100%; border: none;
}
#show-body img {
  max-width: 100%; max-height: 100%; object-fit: contain;
}
#show-body .show-text {
  color: var(--text-1); font-size: 15px; line-height: 1.6;
  padding: 24px; max-width: 720px; overflow-y: auto;
  white-space: pre-wrap;
}
```

- [ ] **Step 3: Add display-surface HTML into `app/jarvis.html`**

Find `<div id="app">` and add the overlay immediately before it:

```html
<!-- ── DISPLAY SURFACE (shown when JARVIS emits a [SHOW:] directive) ── -->
<div id="show-surface">
  <div id="show-topbar">
    <span id="show-label">Display</span>
    <button id="show-dismiss" title="Dismiss" onclick="dismissSurface()">×</button>
  </div>
  <div id="show-body" id="show-content"></div>
</div>
```

- [ ] **Step 4: Add display-surface JS to `app/jarvis.html`**

Find the `<script>` tag (before `</body>`) in `app/jarvis.html`. Add these functions near the top of the script block:

```javascript
/* ── DISPLAY SURFACE ──────────────────────────────────────────────────── */
let _lastShowPayload = null;

function showSurface(payload) {
  const surface = document.getElementById('show-surface');
  const body    = document.getElementById('show-body');
  const label   = document.getElementById('show-label');
  if (!surface || !body) return;

  // Clear previous content
  body.innerHTML = '';
  _lastShowPayload = payload;

  // Parse payload: key=value or bare query string
  const kv = {};
  const eqIdx = payload.indexOf('=');
  if (eqIdx > 0) {
    kv[payload.slice(0, eqIdx).trim().toLowerCase()] = payload.slice(eqIdx + 1).trim();
  } else {
    kv['query'] = payload;
  }

  if (kv.url) {
    label.textContent = 'Web';
    const ifr = document.createElement('iframe');
    ifr.src = kv.url;
    ifr.sandbox = 'allow-scripts allow-same-origin allow-forms allow-popups';
    body.appendChild(ifr);
  } else if (kv.image) {
    label.textContent = 'Image';
    const img = document.createElement('img');
    img.src = kv.image.startsWith('data:') ? kv.image : `${kv.image}`;
    body.appendChild(img);
  } else if (kv.file) {
    label.textContent = 'File';
    const div = document.createElement('div');
    div.className = 'show-text';
    div.textContent = 'Loading…';
    body.appendChild(div);
    fetch(`/api/read_file?path=${encodeURIComponent(kv.file)}`)
      .then(r => r.text()).then(t => { div.textContent = t; }).catch(() => {
        div.textContent = `Cannot read: ${kv.file}`;
      });
  } else if (kv.html) {
    label.textContent = 'View';
    const ifr = document.createElement('iframe');
    ifr.srcdoc = kv.html;
    body.appendChild(ifr);
  } else if (kv.app) {
    // Just launch the app — no visual surface needed
    label.textContent = 'App';
    const div = document.createElement('div');
    div.className = 'show-text';
    div.textContent = `Opening ${kv.app}…`;
    body.appendChild(div);
    fetch(`/api/open_app?name=${encodeURIComponent(kv.app)}`).catch(() => {});
    setTimeout(() => dismissSurface(), 1500);
  } else {
    // Bare query → image search
    label.textContent = 'Search';
    const img = document.createElement('img');
    img.alt = payload;
    img.style.cssText = 'max-width:100%;max-height:100%;object-fit:contain;';
    // Use existing image search API
    fetch(`/api/image_search?q=${encodeURIComponent(kv.query || payload)}`)
      .then(r => r.json())
      .then(d => { if (d.url) img.src = d.url; else { body.innerHTML = `<div class="show-text">No image found for: ${payload}</div>`; } })
      .catch(() => { body.innerHTML = `<div class="show-text">Search failed.</div>`; });
    body.appendChild(img);
  }

  surface.classList.add('active');
}

function dismissSurface() {
  const surface = document.getElementById('show-surface');
  if (surface) surface.classList.remove('active');
}

// showSurface() is called directly by JsApi.show_content() via evaluate_js().
// No polling needed — the HUD window receives payloads through the native bridge.
```

- [ ] **Step 5: Commit**

```bash
git add app/jarvis.html
git commit -m "feat(WS2+WS3): add display surface overlay to jarvis.html + [SHOW:] rendering"
```

---

## Task 9: Vision on request (WS6)

**Files:**
- Modify: `app/bubble.html` (detect vision intent → capture frame → send with message)
- Modify: `ui/server.py` (accept `image_b64` param in `/api/stream`)
- Modify: `brain/router.py` (pass image to vision model)
- Modify: `brain/think.py` (add `think_vision()` using Claude vision)

- [ ] **Step 1: Add vision intent detection + frame capture to `app/bubble.html`**

In `app/bubble.html`, find the `streamReply(text.trim())` call inside the `talk()` function (after `stop_recording` returns) and replace it:

```javascript
    if (text && text.trim()) {
      resetConvTimer();
      // Vision intent detection
      const VISION_RE = /\b(see|look|show you|what['']?s this|what is this|inspect|room|camera|what am i holding|what do you see|describe what|look at this|what['']?s in front|can you see)\b/i;
      let imageB64 = null;
      if (VISION_RE.test(text)) {
        const a2 = api();
        if (a2) {
          try { imageB64 = await a2.capture_frame(); } catch(_) {}
        }
      }
      streamReply(text.trim(), imageB64 || undefined);
    }
```

- [ ] **Step 2: Add `image_b64` param support to `/api/stream` in `ui/server.py`**

Find this line in `ui/server.py`:

```python
    user_input = request.args.get("message", "").strip()
    if not user_input:
        return Response("data: {}\n\n", mimetype="text/event-stream")
```

Add after it:

```python
    image_b64 = request.args.get("image_b64", "").strip() or None
```

Then find the `route_stream` call:

```python
        for event_type, value in route_stream(user_input, active_agent=_active_agent["name"]):
```

Replace with:

```python
        for event_type, value in route_stream(user_input, active_agent=_active_agent["name"], image_b64=image_b64):
```

- [ ] **Step 3: Add `image_b64` parameter to `route_stream` in `brain/router.py`**

Find the `route_stream` function signature:

```python
def route_stream(user_input: str, active_agent: str = None):
```

Replace with:

```python
def route_stream(user_input: str, active_agent: str = None, image_b64: str = None):
```

Then, inside `route_stream`, find where it calls `think_stream(user_input, ...)` (the main JARVIS call). Before that call, add:

```python
    # If an image was captured, route to vision
    if image_b64:
        from brain.think import think_vision_stream
        yield ('agent', 'JARVIS')
        full = ''
        for chunk in think_vision_stream(user_input, image_b64):
            yield ('chunk', chunk)
            full += chunk
        yield ('done', full)
        return
```

- [ ] **Step 4: Add `think_vision_stream` to `brain/think.py`**

At the end of `brain/think.py`, add:

```python
def think_vision_stream(user_input: str, image_b64: str):
    """Route a vision request: send the image + question to Claude vision model."""
    _load_env()
    import anthropic, base64

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or
               os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or "").strip()
    if not api_key:
        yield "I can see the camera feed, but I don't have an API key to analyse it, sir."
        return

    try:
        client = anthropic.Anthropic(api_key=api_key)
        # Decode to verify, then re-encode to ensure clean base64
        img_bytes = base64.b64decode(image_b64)
        clean_b64 = base64.b64encode(img_bytes).decode()

        prompt = user_input or "Describe what you see in this image concisely and naturally, as if speaking aloud."

        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": clean_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"{prompt}\n\n"
                            "Reply in 1-3 short spoken sentences. No markdown. "
                            "Write for the ear, not the eye."
                        ),
                    },
                ],
            }],
            system=(
                "You are JARVIS, a personal AI assistant. Describe what you see naturally and concisely. "
                "Write as if speaking aloud — short sentences, no bullet points, no markdown."
            ),
        ) as stream:
            for chunk in stream.text_stream:
                if chunk:
                    yield expand_abbreviations(chunk)
    except Exception as e:
        print(f"[Vision] think_vision_stream error: {e}", flush=True)
        yield "I couldn't process the camera feed, sir. Check the logs."
```

- [ ] **Step 5: Verify the server compiles**

```bash
cd ~/jarvis
./venv/bin/python3 -m py_compile ui/server.py brain/router.py brain/think.py && echo "OK"
```

Expected: `OK`

- [ ] **Step 6: Restart the Flask server to pick up changes**

```bash
pkill -f "ui/server.py" 2>/dev/null || true
sleep 1
cd ~/jarvis
./venv/bin/python3 ui/server.py >> flask.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8080/api/status
```

Expected: `{"status": "online", "version": "3.0"}`

- [ ] **Step 7: Commit**

```bash
git add app/bubble.html ui/server.py brain/router.py brain/think.py
git commit -m "feat(WS6): vision on request — capture_frame → Claude vision → spoken reply"
```

---

## Task 10: House-cleaning — delete dead code (WS7)

**Files:**
- Delete: `app/hud.html`, `JARVISApp/`, `jarvis.py`, `jarvis-launch.sh`, `start.sh`
- Delete: `voice/clone_daemon.py`, `voice/clone_env/`, `voice_daemon.py`
- Delete: `fix_mic_permission.py`, `test_media_layers.py`
- Modify: `.gitignore` (add build/, dist/, JARVIS.app/, jarvis_app.log)

- [ ] **Step 1: Checkpoint before any deletions**

```bash
cd ~/jarvis
git add -A
git commit -m "checkpoint: before house-cleaning deletions"
```

- [ ] **Step 2: Verify the app still launches before deleting anything**

```bash
curl -s http://127.0.0.1:8080/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('status')=='online' else 'FAIL')"
```

Expected: `OK`

- [ ] **Step 3: Delete dead UIs**

```bash
cd ~/jarvis
git rm app/hud.html
git rm -r JARVISApp/
git rm jarvis.py jarvis-launch.sh start.sh
```

- [ ] **Step 4: Delete dead voice engines**

```bash
cd ~/jarvis
git rm voice/clone_daemon.py 2>/dev/null || true
git rm voice_daemon.py       2>/dev/null || true
# clone_env is not tracked by git (too large) — just remove from disk
rm -rf voice/clone_env/
```

- [ ] **Step 5: Delete stray debug scripts**

```bash
cd ~/jarvis
git rm fix_mic_permission.py test_media_layers.py 2>/dev/null || true
```

- [ ] **Step 6: Update `.gitignore` to exclude build artifacts**

```bash
cd ~/jarvis
cat >> .gitignore << 'EOF'

# JARVIS build artifacts (regenerated by scripts/build_app.sh)
build/
dist/
JARVIS.app/
*.log
jarvis_app.log
flask.log
EOF
git add .gitignore
```

- [ ] **Step 7: Remove tracked build artifacts from git (keep on disk)**

```bash
cd ~/jarvis
git rm -r --cached build/ dist/ JARVIS.app/ 2>/dev/null || true
```

- [ ] **Step 8: Commit all deletions**

```bash
git add -A
git commit -m "feat(WS7): house-cleaning — delete dead UIs, voice engines, debug scripts; update .gitignore"
```

- [ ] **Step 9: Verify app still works after cleanup**

```bash
curl -s http://127.0.0.1:8080/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('Status:', d.get('status'))"
```

Expected: `Status: online`

---

## Task 11: Audit harness + AUDIT_REPORT.md (WS5)

**Files:**
- Create: `scripts/audit.py`
- Create: `AUDIT_REPORT.md` (generated by the script)

- [ ] **Step 1: Write `scripts/audit.py`**

```python
#!/usr/bin/env python3
"""
scripts/audit.py — JARVIS functionality audit.
Generates AUDIT_REPORT.md with ✅/🔴/⚠️ status for all subsystems + tools.
Run: cd ~/jarvis && ./venv/bin/python3 scripts/audit.py
"""
import sys, os, subprocess, json, time, textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        if v.strip() and k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()

report = []
def log(line): print(line); report.append(line)

log("# JARVIS Functionality Audit")
log(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# ── 1. Server endpoints ───────────────────────────────────────────────────────
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

# ── 2. Python test suites ─────────────────────────────────────────────────────
log("\n## 2. Test Suites\n")
result = subprocess.run(
    [str(ROOT / "venv/bin/python3"), "-m", "pytest", str(ROOT / "tests"),
     "-q", "--tb=no", "--no-header", "--timeout=30"],
    capture_output=True, text=True, cwd=str(ROOT)
)
for line in (result.stdout + result.stderr).splitlines():
    if line.strip():
        log(f"    {line}")
if result.returncode == 0:
    log("✅ All test suites passed")
else:
    log("🔴 Some tests failed (see above)")

# ── 3. Core imports / subsystems ──────────────────────────────────────────────
log("\n## 3. Core Subsystem Imports\n")

subsystems = [
    ("brain.router",   "route"),
    ("brain.think",    "think_stream"),
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

# ── 4. Tool registry ──────────────────────────────────────────────────────────
log("\n## 4. Tool Registry\n")

try:
    from brain.tools.registry import get_all_tools
    tools = get_all_tools()
    log(f"✅ Tool registry loaded — {len(tools)} tools registered")

    # Categorise and smoke-test safe read-only tools
    safe_tests = {
        "get_weather":      {"city": "Addis Ababa"},
        "get_time":         {},
        "get_date":         {},
        "search_web":       {"query": "test"},
        "search_brain":     {"query": "Elnatan"},
    }
    results = {"ok": 0, "fail": 0, "skipped": 0}
    for tool in tools:
        name = getattr(tool, 'name', str(tool))
        if name in safe_tests:
            try:
                fn = tool if callable(tool) else getattr(tool, '__call__', None)
                # Don't actually call — just verify it's callable
                if callable(tool) or callable(fn):
                    results["ok"] += 1
                else:
                    results["fail"] += 1
            except Exception as e:
                log(f"  🔴 {name}: {e}")
                results["fail"] += 1
        else:
            results["skipped"] += 1

    log(f"  Callable: {results['ok']} | Skipped (manual-verify): {results['skipped']} | Failed: {results['fail']}")

except Exception as e:
    log(f"🔴 Tool registry failed to load: {e}")

# ── 5. API keys ───────────────────────────────────────────────────────────────
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

# ── 6. Voice chain ────────────────────────────────────────────────────────────
log("\n## 6. Voice Chain\n")
try:
    import sounddevice as sd
    devs = [d for d in sd.query_devices() if d['max_input_channels'] > 0]
    log(f"✅ Microphone devices: {len(devs)} found ({', '.join(d['name'] for d in devs[:3])})")
except Exception as e:
    log(f"🔴 Microphone: {e}")

import urllib.request as _ur
try:
    with _ur.urlopen("http://127.0.0.1:8080/api/tts?text=test&agent=JARVIS", timeout=5) as r:
        size = len(r.read())
    log(f"✅ TTS /api/tts — {size} bytes audio returned")
except Exception as e:
    log(f"🔴 TTS /api/tts — {e}")

# ── 7. Second Brain ───────────────────────────────────────────────────────────
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

# ── Write report ──────────────────────────────────────────────────────────────
report_path = ROOT / "AUDIT_REPORT.md"
report_path.write_text("\n".join(report) + "\n")
print(f"\n✓ Report written to {report_path}")
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x ~/jarvis/scripts/audit.py
```

- [ ] **Step 3: Run the audit**

```bash
cd ~/jarvis
./venv/bin/python3 scripts/audit.py 2>&1 | tail -40
```

Expected: `AUDIT_REPORT.md` written, summary of ✅/🔴/⚠️ per section.

- [ ] **Step 4: Read and fix any quick safe breaks the audit surfaces**

```bash
grep "🔴" ~/jarvis/AUDIT_REPORT.md
```

For each 🔴 item, assess:
- Import error → check if module exists, fix sys.path or missing dependency
- API key missing → note it; don't add keys
- Server endpoint down → restart server (`pkill -f ui/server.py && ./venv/bin/python3 ui/server.py &`)

Do NOT attempt to fix 🔴 items that require architectural changes.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit.py AUDIT_REPORT.md
git commit -m "feat(WS5): add audit harness + generate AUDIT_REPORT.md"
```

---

## Verification Checklist

After all tasks complete, verify the spec's five acceptance criteria:

- [ ] **Voice (system-wide):** With another app focused, say "Hey JARVIS" → orb enters listening → speak a question → hear spoken reply → ask follow-up without re-waking → interrupt mid-sentence (barge-in stops it) → silence 25 s → conversation closes. No self-talk loop.
- [ ] **Ambient orb:** Talking normally never auto-opens the chat window. Orb stays in corner.
- [ ] **Show-on-demand:** Say "show me the weather in Tokyo" → HUD surface appears with image → dismiss → back to orb.
- [ ] **Smarter + human:** Ask "what do you know about my life?" → grounded reply from vault, not invented or Nexel-deflected. Casual chat sounds natural.
- [ ] **Audit report:** `AUDIT_REPORT.md` exists with ✅/🔴/⚠️ per section.
