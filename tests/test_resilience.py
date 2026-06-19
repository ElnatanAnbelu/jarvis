"""Resilience & succession (plan §9): graceful degradation, the brain-free watchdog,
identity re-alignment on level-up, and the inheritance handoff."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from brain import resilience, realign
from memory import export
import watchdog


# ── graceful degradation ─────────────────────────────────────────────────────
def test_subsystem_status_reports_all_subsystems():
    s = resilience.subsystem_status()
    assert set(s.keys()) == {"brain", "stt", "tts", "vault"}
    assert all(isinstance(v, bool) for v in s.values())


def test_degraded_messages_are_in_alfreds_voice():
    assert "sir" in resilience.degraded_message("brain").lower()
    assert "sir" in resilience.degraded_message("something_unknown").lower()
    assert isinstance(resilience.health_line(), str)


# ── watchdog (brain-free) ────────────────────────────────────────────────────
def test_watchdog_restart_decision():
    assert watchdog.should_restart(3) is True
    assert watchdog.should_restart(2) is False


def test_watchdog_alive_false_on_dead_endpoint():
    assert watchdog.alive("http://127.0.0.1:59999/nope", timeout=1) is False


# ── identity re-alignment on level-up ────────────────────────────────────────
def test_persona_intact_on_the_live_persona():
    assert realign.persona_intact() is True          # live persona carries Alfred/sir/butler
    r = realign.realign()
    assert r["persona_intact"] is True and r["assertion"] is None


# ── inheritance handoff ──────────────────────────────────────────────────────
def test_export_inheritance_writes_bundle_and_heir_manifest(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    conn = sqlite3.connect(src / "jarvis.db")
    conn.execute("CREATE TABLE facts (k TEXT, v TEXT)")
    conn.execute("INSERT INTO facts VALUES ('name','Elnatan')")
    conn.commit()
    conn.close()

    mpath = export.export_inheritance(tmp_path / "out", heir="Yostina",
                                      note="for my sister", stamp="t1", src_dir=str(src))
    import json
    manifest = json.loads(Path(mpath).read_text())
    assert manifest["kind"] == "alfred-inheritance"
    assert manifest["heir"] == "Yostina"
    assert (tmp_path / "out" / "alfred-self-t1.tar.gz").exists()
