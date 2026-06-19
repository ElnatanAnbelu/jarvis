"""Persona drift-gate (plan §5): catch filler openers, AI-disclaimers, and stale-name
leaks; require self-identification as Alfred."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval import persona_gate as pg


def test_banned_opener_flagged():
    assert "banned-opener" in pg.violations("Certainly! Here's the report.")
    assert "banned-opener" in pg.violations("Of course, sir.")


def test_ai_disclaimer_flagged():
    assert "ai-disclaimer" in pg.violations("As an AI, I can't do that.")
    assert "ai-disclaimer" in pg.violations("I'm an AI language model.")


def test_jarvis_leak_flagged():
    assert "jarvis-leak" in pg.violations("I am JARVIS, at your service.")


def test_clean_alfred_reply_passes():
    assert pg.violations("Right away, sir. The report's ready when you are.") == []


def test_gate_passes_for_a_well_behaved_alfred():
    def alfred(prompt):
        return "I'm Alfred, sir — your second self and chief of staff."
    res = pg.run_persona_gate(alfred)
    assert res["passed"] is True and res["identity_ok"] is True


def test_gate_fails_on_drift():
    def driftbot(prompt):
        return "Certainly! As an AI, I'm here to help."
    res = pg.run_persona_gate(driftbot)
    assert res["passed"] is False and res["violations"]


def test_gate_fails_if_identity_missing():
    def nameless(prompt):
        return "At your service, sir."     # clean, but never says Alfred
    res = pg.run_persona_gate(nameless)
    assert res["identity_ok"] is False and res["passed"] is False
