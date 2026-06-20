"""Tests for brain/app_control.py — the deterministic voice-control of dock panels.

Locks the exact behaviors the owner reported broken: "open approvals" must open
approvals, "close the tabs" must close everything, "switch to activity" must switch —
and everyday "see/look" language plus unrelated requests must NOT hijack a panel.
"""
from brain.app_control import match_panel_command as m


# ── the owner's exact failing cases now work ──────────────────────────────────
def test_open_approvals():
    r = m("open approvals")
    assert r and r["actions"] == [{"act": "open", "panel": "approvals"}]
    assert r["say"] == "Approvals, sir."


def test_open_my_activities_page():
    r = m("open up my activities page")
    assert r and r["actions"] == [{"act": "open", "panel": "activity"}]


def test_close_the_tabs_closes_all():
    r = m("close the tabs")
    assert r and r["actions"] == [{"act": "close_all"}]


def test_close_everything():
    assert m("close everything")["actions"] == [{"act": "close_all"}]
    assert m("close all the panels")["actions"] == [{"act": "close_all"}]


def test_switch_to_activity():
    r = m("switch to activity")
    assert r and r["actions"] == [{"act": "switch", "panel": "activity"}]


def test_show_me_pending_approvals():
    r = m("show me my pending approvals")
    assert r and r["actions"] == [{"act": "open", "panel": "approvals"}]


def test_pull_up_activity():
    assert m("pull up the activity feed")["actions"] == [{"act": "open", "panel": "activity"}]


def test_close_single_panel():
    r = m("close approvals")
    assert r and r["actions"] == [{"act": "close", "panel": "approvals"}]
    assert r["say"] == "Closed, sir."


def test_open_health_and_system_health():
    assert m("open health")["actions"] == [{"act": "open", "panel": "health"}]
    assert m("show me system health")["actions"] == [{"act": "open", "panel": "health"}]


def test_second_brain_not_double_counted():
    # "second brain" must map to the single 'brain' panel, not also a stray match.
    assert m("open the second brain")["actions"] == [{"act": "open", "panel": "brain"}]


def test_open_two_panels():
    r = m("open approvals and activity")
    panels = [a["panel"] for a in r["actions"]]
    assert set(panels) == {"approvals", "activity"}
    assert all(a["act"] == "open" for a in r["actions"])


# ── conservative: must NOT hijack non-panel / ambiguous speech ─────────────────
def test_everyday_see_does_not_trigger():
    assert m("so I can see what I have for today") is None


def test_open_email_is_not_a_panel():
    assert m("open my email") is None
    assert m("show me the file about approvals") is None


def test_question_without_verb_passes_through():
    assert m("what's in approvals") is None
    assert m("how's my health") is None


def test_unrelated_chat_passes_through():
    assert m("what time is it") is None
    assert m("hey alfred how are you") is None
    assert m("") is None
    assert m(None) is None


def test_long_compound_utterance_defers_to_brain():
    # > 12 words → let the brain field it (and, later, the model-driven tool).
    assert m("could you please open the approvals panel and then read me the first "
             "three items on it") is None
