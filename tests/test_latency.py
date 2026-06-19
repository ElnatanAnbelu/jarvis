"""P0 — unit tests for the latency SLA harness's PURE logic (no live model).

Covers percentile math, budget-override merge, and the gate-decision (evaluate):
under-budget passes, over-budget on an enforced stage fails, over-budget on a
report-only stage does NOT fail, and a stage with no samples is skipped (not a
failure). The live measurement path is exercised by `python eval/latency.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval import latency


def test_percentile_basic():
    assert latency.percentile([], 95) == 0.0
    assert latency.percentile([5.0], 95) == 5.0
    assert latency.percentile([1, 2, 3, 4], 50) == 2.5
    # p95 of 1..100 sits at ~95.05 via linear interpolation
    assert 94.0 <= latency.percentile(list(range(1, 101)), 95) <= 96.0


def test_load_budgets_defaults_and_merge(tmp_path):
    b = latency.load_budgets(str(tmp_path / "nope.json"))
    assert b["host_factor"] == 1.0
    assert "wake_to_first_token" in b["stages"]
    override = tmp_path / "budgets.json"
    override.write_text('{"host_factor": 2.0, "stages": {"simple_reply": {"p95": 9.9}}}')
    b2 = latency.load_budgets(str(override))
    assert b2["host_factor"] == 2.0
    assert b2["stages"]["simple_reply"]["p95"] == 9.9       # overridden
    assert "wake_to_first_token" in b2["stages"]            # untouched default preserved


BUDGETS = {
    "host_factor": 1.0,
    "stages": {
        "wake_to_first_token": {"p95": 1.2, "ceiling": 1.5, "unit": "s"},
        "tool_decision": {"p95": 7.0, "ceiling": 9.0, "unit": "s"},
    },
    "gate": {"enforce": ["wake_to_first_token"], "report_only": ["tool_decision"]},
}


def test_evaluate_under_budget_passes():
    rep = latency.evaluate({"wake_to_first_token": [0.5, 0.6, 0.7]}, BUDGETS)
    assert rep.passed is True
    assert not rep.failures()


def test_evaluate_over_budget_enforced_fails():
    rep = latency.evaluate({"wake_to_first_token": [2.0, 2.1, 2.2]}, BUDGETS)
    assert rep.passed is False
    assert any(f.stage == "wake_to_first_token" for f in rep.failures())


def test_evaluate_ceiling_breach_fails():
    # p95 fine but one sample blows the hard ceiling → fail
    rep = latency.evaluate({"wake_to_first_token": [0.4, 0.4, 0.4, 9.0]}, BUDGETS)
    assert rep.passed is False


def test_report_only_stage_does_not_fail_gate():
    rep = latency.evaluate({"wake_to_first_token": [0.5], "tool_decision": [99.0]}, BUDGETS)
    assert rep.passed is True  # tool_decision is over budget but report-only


def test_missing_samples_are_skipped_not_failed():
    rep = latency.evaluate({}, BUDGETS)  # nothing measured
    assert rep.passed is True
    assert all(r.skipped for r in rep.results)
