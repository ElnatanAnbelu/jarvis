"""Close the loop (plan §1): when sir approves an offer, work_on_goal acts on it —
acks immediately and kicks off the autonomous runner in the background."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.tools.goal_tools as gt
from brain.tools.registry import TOOL_REGISTRY


def test_work_on_goal_is_registered():
    assert "work_on_goal" in TOOL_REGISTRY


def test_work_on_goal_acks_and_starts_the_runner(monkeypatch):
    called = threading.Event()
    seen = {}
    import brain.runner

    def fake_run_goal(goal, label=""):
        seen["goal"] = goal
        seen["label"] = label
        called.set()

    monkeypatch.setattr(brain.runner, "run_goal", fake_run_goal)
    out = gt.work_on_goal("Launch Addis Market")
    assert "Launch Addis Market" in out and "sir" in out.lower()
    assert called.wait(timeout=2)                       # the runner was kicked off
    assert "Launch Addis Market" in seen["goal"]
    assert seen["label"] == "goal:Launch Addis Market"


def test_empty_goal_asks_which():
    assert "which goal" in gt.work_on_goal("").lower()
