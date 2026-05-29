# JARVIS Functionality Audit

Generated: 2026-05-30 01:35:01

## 1. Server Endpoints

✅ /api/status — 200 OK
✅ /api/proactive — 200 OK
✅ /api/history — 200 OK
✅ /api/tts (audio) — 200 OK
✅ / (jarvis.html) — 200 OK
✅ /bubble (bubble.html) — 200 OK
✅ /api/end_session — 200 OK

## 2. Test Suites

    ==================================== ERRORS ====================================
    ___________________ ERROR collecting tests/test_run_shell.py ___________________
    tests/test_run_shell.py:2: in <module>
        from control.code_executor import run_shell
    control/code_executor.py:182: in <module>
        def _self_heal(language: str, code: str, error: str, attempt: int) -> str | None:
    E   TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
    =========================== short test summary info ============================
    ERROR tests/test_run_shell.py - TypeError: unsupported operand type(s) for |:...
    !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
    1 error in 0.12s
⚠️  Some tests failed (see above)

## 3. Core Subsystem Imports

✅ brain.router.route
✅ brain.think.think_stream
✅ brain.think.think_vision_stream
✅ memory.memory.get_recent_history
✅ memory.vault.VaultManager
✅ voice.speak.speak
✅ voice.wake.WakeWordListener
✅ voice.listen.listen_until_silence

## 4. Tool Registry

✅ Tool registry loaded — 125 tools registered

## 5. API Keys

⚠️  Anthropic (Claude) — NOT SET
✅ Groq (Whisper + LLM) — gsk_UdkP…qk30
✅ ElevenLabs (TTS) — sk_4ffe5…c909
✅ Gemini (vision fallback) — AIzaSyB2…igvs

## 6. Voice Chain

✅ Microphone devices: 2 found (E Microphone, MacBook Air Microphone)
✅ TTS /api/tts — 52844 bytes audio returned

## 7. Second Brain / Memory

✅ Conversation DB — 5 recent messages
✅ Vault search — 1579 chars returned

## 8. Tonight's New Features

✅ Wake word listener module — importable
✅ Vision stream (think_vision_stream) — importable
✅ bubble.html — conversation mode + wake word wired
✅ jarvis.html — display surface overlay present
✅ app/hud.html — deleted (house-cleaning done)
⚠️  JARVISApp — still present (house-cleaning incomplete)
✅ jarvis.py — deleted (house-cleaning done)
✅ start.sh — deleted (house-cleaning done)
✅ voice/clone_daemon.py — deleted (house-cleaning done)
