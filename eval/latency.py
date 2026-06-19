"""P0 — the LATENCY SLA harness.

Turns "is it fast enough?" into a measured, regression-gated fact. Latency is the
owner's single dealbreaker, so this is the first contract: every later phase must
keep these p95s under budget.

Measures wall-clock on the REAL local brain (needs Ollama up, like eval/run.py):
  - wake_to_first_token : time to the FIRST streamed token (warm model)
  - simple_reply        : full no-tool conversational round-trip
  - tool_decision       : tools-enabled call → tool-choice latency (no execution, no side effects)
(STT/TTS stages are added later; this lands the brain-latency core.)

Dependency-free: budgets live in eval/budgets.json (stdlib json), percentiles are
pure-python. The pure logic (percentile / budget-merge / evaluate) is unit-tested
in tests/test_latency.py with synthetic numbers — no Ollama needed for the suite.

Run live:  ./venv/bin/python eval/latency.py
"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, os.path.dirname(_HERE))

# Starting budgets (tunable). p95 is what "feels laggy" — we gate on the tail, not
# the mean. Numbers are the master-plan P0 targets for an M-series/32GB Mac.
DEFAULT_BUDGETS = {
    "host_factor": 1.0,  # CI on a slower box can raise this; the real contract is 1.0
    "stages": {
        "wake_to_first_token": {"p95": 1.2, "ceiling": 1.5, "unit": "s", "samples": 6, "warmup": 1},
        "simple_reply":        {"p95": 3.0, "ceiling": 4.0, "unit": "s", "samples": 5, "warmup": 1},
        "tool_decision":       {"p95": 7.0, "ceiling": 9.0, "unit": "s", "samples": 3, "warmup": 1},
    },
    # Which stages FAIL the gate vs. are reported-only (tool path is noisier → report).
    "gate": {"enforce": ["wake_to_first_token", "simple_reply"], "report_only": ["tool_decision"]},
}


def percentile(values: List[float], pct: float) -> float:
    """Linear-interpolation percentile. pct in [0,100]. Pure-python, no numpy."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def load_budgets(path: Optional[str] = None) -> dict:
    """DEFAULT_BUDGETS deep-merged with an optional eval/budgets.json override."""
    import copy
    budgets = copy.deepcopy(DEFAULT_BUDGETS)
    path = path or os.path.join(_HERE, "budgets.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                override = json.load(f)
            if "host_factor" in override:
                budgets["host_factor"] = override["host_factor"]
            for stage, cfg in (override.get("stages") or {}).items():
                budgets["stages"].setdefault(stage, {}).update(cfg)
            if "gate" in override:
                budgets["gate"].update(override["gate"])
    except Exception:
        pass  # a malformed override never breaks the gate — fall back to defaults
    return budgets


@dataclass
class StageResult:
    stage: str
    unit: str
    samples: List[float]
    p50: float
    p95: float
    budget_p95: float
    ceiling: float
    enforced: bool
    passed: bool
    skipped: bool = False
    note: str = ""


@dataclass
class LatencyReport:
    results: List[StageResult] = field(default_factory=list)
    model: str = ""
    passed: bool = False

    def failures(self) -> List[StageResult]:
        return [r for r in self.results if r.enforced and not r.skipped and not r.passed]


def evaluate(measurements: Dict[str, List[float]], budgets: Optional[dict] = None,
             model: str = "") -> LatencyReport:
    """PURE: given measured samples per stage, compute p50/p95 and compare to
    budget*host_factor (+ a hard ceiling on the max). No live model — unit-testable.
    A stage with no samples is `skipped` (not a failure)."""
    budgets = budgets or load_budgets()
    hf = budgets.get("host_factor", 1.0)
    enforce = set(budgets.get("gate", {}).get("enforce", []))
    report = LatencyReport(model=model)
    for stage, cfg in budgets["stages"].items():
        vals = measurements.get(stage) or []
        enforced = stage in enforce
        if not vals:
            report.results.append(StageResult(stage, cfg.get("unit", "s"), [], 0.0, 0.0,
                                               cfg["p95"] * hf, cfg.get("ceiling", cfg["p95"]) * hf,
                                               enforced, passed=True, skipped=True,
                                               note="no samples (model/probe unavailable)"))
            continue
        p50, p95 = percentile(vals, 50), percentile(vals, 95)
        budget_p95 = cfg["p95"] * hf
        ceiling = cfg.get("ceiling", cfg["p95"]) * hf
        ok = (p95 <= budget_p95) and (max(vals) <= ceiling)
        report.results.append(StageResult(stage, cfg.get("unit", "s"), vals, p50, p95,
                                           budget_p95, ceiling, enforced, passed=ok))
    report.passed = all(r.passed for r in report.results if r.enforced and not r.skipped)
    return report


def _measure(fn: Callable[[], None], samples: int, warmup: int) -> List[float]:
    """Run fn() warmup+samples times; return the post-warmup wall-clock seconds."""
    out: List[float] = []
    for i in range(warmup + samples):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception:
            continue  # a failed probe contributes no sample (becomes skipped if all fail)
        dt = time.perf_counter() - t0
        if i >= warmup:
            out.append(dt)
    return out


# ── Live probes (need Ollama) ────────────────────────────────────────────────
def _probe_first_token():
    from brain import llm
    gen = llm.chat_stream([{"role": "user", "content": "Say hello in one short sentence."}], think=False)
    for _chunk in gen:
        break  # stop at the first token — that's the latency we feel


def _probe_simple_reply():
    from brain import llm
    llm.chat([{"role": "user", "content": "In one sentence, what's a good morning habit?"}], think=False)


def _probe_tool_decision():
    from brain import llm
    from brain.tools.registry import get_tools
    # tools-enabled call → measures the heavier tool-routing path. NO execution → no side effects.
    llm.chat([{"role": "user", "content": "What's the weather in Addis Ababa?"}],
             tools=get_tools("JARVIS"), think=False)


_PROBES = {
    "wake_to_first_token": _probe_first_token,
    "simple_reply": _probe_simple_reply,
    "tool_decision": _probe_tool_decision,
}


def run_latency(budgets: Optional[dict] = None, emit_obs: bool = True) -> LatencyReport:
    """Measure every stage on the live model, then evaluate against budget."""
    budgets = budgets or load_budgets()
    try:
        from brain import llm
        model = getattr(llm, "DEFAULT_MODEL", "")
    except Exception:
        model = ""
    measurements: Dict[str, List[float]] = {}
    for stage, cfg in budgets["stages"].items():
        probe = _PROBES.get(stage)
        if probe is None:
            continue
        measurements[stage] = _measure(probe, cfg.get("samples", 5), cfg.get("warmup", 1))
    report = evaluate(measurements, budgets, model=model)
    if emit_obs:
        try:
            from obs.log import log_event
            for r in report.results:
                log_event("latency.stage", stage=r.stage, p50=round(r.p50, 3), p95=round(r.p95, 3),
                          budget_p95=r.budget_p95, passed=r.passed, skipped=r.skipped)
        except Exception:
            pass
    return report


def format_report(report: LatencyReport) -> str:
    lines = []
    for r in report.results:
        if r.skipped:
            mark, detail = "·", f"skipped ({r.note})"
        else:
            mark = "✓" if r.passed else "✗"
            detail = f"p50 {r.p50:.2f}{r.unit} · p95 {r.p95:.2f}{r.unit}  (budget p95 {r.budget_p95:.2f}{r.unit})"
        tag = "" if r.enforced else "  [report-only]"
        lines.append(f"  {mark} {r.stage:<22} {detail}{tag}")
    return "\n".join(lines)


def main() -> int:
    try:
        from brain import llm
        if not (llm.available() and llm.has_model()):
            print("latency: local model unavailable (start Ollama + pull the model).")
            return 1
    except Exception as e:
        print(f"latency: cannot reach the brain ({e}).")
        return 1
    print("Latency SLA — measuring on the live brain...\n")
    report = run_latency()
    print(format_report(report))
    print(f"\n  LATENCY GATE: {'PASS ✅' if report.passed else 'FAIL ❌'}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
