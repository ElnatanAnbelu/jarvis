"""Central autonomy safety gate.

Single source of truth for whether a tool call may execute, must be confirmed
by the human (via Telegram / the UI), or is denied outright (kill-switch).

The whole safety substrate funnels through `gate()`. Everything else
(registry.execute_tool, the autonomous runner, inbound message handlers) calls
it; nothing irreversible auto-fires while the user is away.

State lives in the `meta` table via memory.get_flag/set_flag:
  - "paused"    : kill-switch — blocks all non-user (autonomous) actions.
  - "away_mode" : when on, red-list actions require human confirmation.

Decisions are dicts: {"action": "execute"|"confirm"|"deny",
                      "reason": str, "confirm_id": int|None}
"""
import json

from memory import memory

# Irreversible / high-stakes tools: never auto-fire in away-mode — always
# routed to human confirmation. (Tools may also opt in via risk="red".)
RED_LIST = {
    "send_email",
    "send_imessage",
    "send_whatsapp",
    "send_whatsapp_api",
    "send_whatsapp_by_name",
    "delete_file",
    "run_shell",
    "execute_code",
    "git_push",
    # money / payments (wired but confirm-only per spec)
    "transfer_money",
    "make_payment",
    "pay_bill",
}


# ── state ────────────────────────────────────────────────────────────────────
def is_paused() -> bool:
    return bool(memory.get_flag("paused", False))


def is_away() -> bool:
    return bool(memory.get_flag("away_mode", False))


def set_paused(value: bool) -> None:
    memory.set_flag("paused", bool(value))


def set_away(value: bool) -> None:
    memory.set_flag("away_mode", bool(value))


def get_autonomy_mode() -> str:
    """'supervised' (default — safe shakeout, every autonomous action proposes) or
    'auto' (routine executes, red-list still confirms). Per the trust ramp: flip a
    domain to 'auto' once it behaves."""
    mode = memory.get_flag("autonomy_mode", "supervised")
    return mode if mode in ("supervised", "auto") else "supervised"


def set_autonomy_mode(mode: str) -> None:
    memory.set_flag("autonomy_mode", "auto" if mode == "auto" else "supervised")


def is_red(tool_name: str, declared_risk=None) -> bool:
    return declared_risk == "red" or tool_name in RED_LIST


# ── the gate ───────────────────────────────────────────────────────────────--
def gate(tool_name: str, args: dict, agent=None, risk=None, source: str = "user") -> dict:
    """Decide what happens to a tool call.

    source:
      "user"       — a direct, present-human request (most permissive).
      "autonomous" — JARVIS acting on its own (proactive runner / scheduled).
      "external"   — triggered by inbound content (email/WhatsApp/Telegram) —
                     treated as untrusted: red-list always needs confirmation.

    Policy (fail-closed):
      1. paused  → deny every non-user action (the kill-switch).
      2. red-list tool + (away-mode OR external source) → confirm (enqueue +
         hand to Telegram). NEVER executes here.
      3. otherwise → execute.
    """
    red = is_red(tool_name, risk)

    if is_paused() and source != "user":
        return {"action": "deny",
                "reason": "JARVIS is paused — the kill-switch is active. Resume to allow actions.",
                "confirm_id": None}

    # Shakeout: in supervised mode every autonomous action proposes for approval.
    if source == "autonomous" and get_autonomy_mode() == "supervised":
        cid = memory.enqueue_confirmation(tool_name, args, agent=agent,
                                          risk=(risk or "supervised"),
                                          reason="supervised autonomous action")
        return {"action": "confirm",
                "reason": f"Supervised mode — '{tool_name}' queued for your approval (#{cid}).",
                "confirm_id": cid}

    if red and (is_away() or source == "external"):
        cid = memory.enqueue_confirmation(
            tool_name, args, agent=agent, risk="red",
            reason=f"{source} requested '{tool_name}'",
        )
        return {"action": "confirm",
                "reason": f"Red-list action '{tool_name}' needs your approval (#{cid}).",
                "confirm_id": cid}

    return {"action": "execute", "reason": "ok", "confirm_id": None}


# ── resolving confirmations (called from Telegram / UI) ───────────────────────
def approve(confirm_id) -> str:
    """Execute a pending red-list action the user approved."""
    c = memory.get_confirmation(confirm_id)
    if not c:
        return f"No pending action #{confirm_id}."
    if c.get("status") != "pending":
        return f"Action #{confirm_id} is already {c.get('status')}."
    from brain.tools.registry import execute_tool  # guarded: avoid circular import
    try:
        result = execute_tool(c["tool_name"], json.loads(c.get("args") or "{}"),
                              agent=c.get("agent"), _bypass_gate=True)
        memory.set_confirmation_status(confirm_id, "executed", result=str(result)[:500])
        return f"✅ Approved & executed '{c['tool_name']}' (#{confirm_id}): {str(result)[:200]}"
    except Exception as e:  # noqa: BLE001 — surface, don't swallow
        memory.set_confirmation_status(confirm_id, "failed", result=str(e)[:500])
        return f"⚠️ Approved '{c['tool_name']}' (#{confirm_id}) but it failed: {e}"


def reject(confirm_id) -> str:
    c = memory.get_confirmation(confirm_id)
    if not c:
        return f"No pending action #{confirm_id}."
    if c.get("status") != "pending":
        return f"Action #{confirm_id} is already {c.get('status')}."
    memory.set_confirmation_status(confirm_id, "rejected")
    return f"🚫 Rejected '{c['tool_name']}' (#{confirm_id}). Nothing was executed."


def pending_summary() -> str:
    """Human-readable list of what's waiting on approval."""
    rows = memory.get_pending_confirmations()
    if not rows:
        return "Nothing is waiting for approval."
    lines = ["Pending approvals:"]
    for c in rows:
        lines.append(f"  #{c['id']} · {c['tool_name']} · {c.get('reason', '')}")
    return "\n".join(lines)
