"""Regression: approve() must be idempotent under concurrency and must honor the
pause/panic kill-switch (second-audit P2s).

- A check-then-act race let two concurrent approvals both execute the same
  irreversible red-list action (double-send/double-pay).
- approve() runs with _bypass_gate=True, so the gate's pause check never fired —
  a queued action could be approved and executed AFTER panic/pause.
"""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "approve.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    yield p


def test_claim_confirmation_is_atomic_single_winner(db):
    cid = memory.enqueue_confirmation("send_email", {"to": "x@y.com"}, risk="red")
    assert memory.claim_confirmation(cid) is True     # first wins
    assert memory.claim_confirmation(cid) is False    # second loses


def test_pause_blocks_approve(db):
    runs = {"n": 0}

    @registry.tool(description="paid", parameters={}, risk="red")
    def _pay_probe():
        runs["n"] += 1
        return "paid"

    try:
        cid = memory.enqueue_confirmation("_pay_probe", {}, risk="red")
        autonomy.set_paused(True)
        out = autonomy.approve(cid)
        assert runs["n"] == 0, "approved & executed while paused!"
        assert "paused" in out.lower()
        # still pending (recoverable after resume)
        assert memory.get_confirmation(cid)["status"] == "pending"
    finally:
        autonomy.set_paused(False)
        registry.TOOL_REGISTRY.pop("_pay_probe", None)


def test_concurrent_approve_executes_once(db):
    runs = {"n": 0}
    lock = threading.Lock()

    @registry.tool(description="send once", parameters={}, risk="red")
    def _send_once():
        with lock:
            runs["n"] += 1
        return "sent"

    try:
        cid = memory.enqueue_confirmation("_send_once", {}, risk="red")
        barrier = threading.Barrier(2)
        results = []

        def go():
            barrier.wait()
            results.append(autonomy.approve(cid))

        t1, t2 = threading.Thread(target=go), threading.Thread(target=go)
        t1.start(); t2.start(); t1.join(); t2.join()

        assert runs["n"] == 1, f"red-list action executed {runs['n']} times (double-send!)"
        assert any("already" in r.lower() for r in results)
    finally:
        registry.TOOL_REGISTRY.pop("_send_once", None)
