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
import os

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
    "write_file",      # can overwrite arbitrary files — confirm when away/external
    "create_file",
    "move_file",
    "run_shell",
    "execute_code",
    "control_screen",  # drives real mouse/keyboard/AppleScript — full OS control
    "git_push",
    # money / payments (wired but confirm-only per spec)
    "transfer_money",
    "make_payment",
    "pay_bill",
}

# Money tools that MOVE money. A payment at/above this threshold ALWAYS confirms
# AND requires a fresh PIN to approve — even for a present user (owner's strictest
# choice: "PIN on any money action ≥ ~$100"). Owner-editable via env.
_MONEY_TOOLS = {"transfer_money", "make_payment", "pay_bill", "send_payment", "wire_money"}
MONEY_CONFIRM_THRESHOLD_USD = float(os.environ.get("JARVIS_MONEY_PIN_USD", "100"))
_ETB_PER_USD = float(os.environ.get("JARVIS_ETB_PER_USD", "130"))
_AMOUNT_KEYS = ("amount", "value", "sum", "total", "usd")


def _amount_usd(args: dict):
    """Best-effort USD amount from a money tool's args → float or None. Converts
    when currency is ETB. Tolerates '$1,200.50'. Unparseable → None (treated as
    PIN-required at the call site, i.e. fail safe)."""
    if not isinstance(args, dict):
        return None
    raw = next((args[k] for k in _AMOUNT_KEYS if args.get(k) is not None), None)
    if raw is None:
        return None
    try:
        amt = float(str(raw).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if str(args.get("currency", "")).strip().upper() in ("ETB", "BIRR"):
        amt = amt / _ETB_PER_USD
    return amt


def needs_pin(tool_name: str, args: dict) -> bool:
    """True if this is a money move at/above the PIN threshold (so approval needs
    a fresh PIN). An unparseable amount on a money tool → True (fail safe)."""
    if tool_name not in _MONEY_TOOLS:
        return False
    amt = _amount_usd(args)
    return True if amt is None else amt >= MONEY_CONFIRM_THRESHOLD_USD


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


# Which arg carries the recipient, per send-type tool (for contact-aware gating).
_RECIPIENT_ARGS = {
    "send_email": ("to", "recipient", "email"),
    "send_imessage": ("to", "recipient", "contact"),
    "send_whatsapp": ("to", "number", "name", "contact"),
    "send_whatsapp_by_name": ("name",),
    "send_whatsapp_api": ("to", "number", "name"),
}


def _recipient_of(tool_name: str, args: dict) -> str:
    for k in _RECIPIENT_ARGS.get(tool_name, ()):
        v = (args or {}).get(k)
        if v:
            return str(v)
    return ""


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
      2. red-list tool, UNLESS it's a present human acting at home → confirm
         (enqueue + hand to Telegram). i.e. red-list ALWAYS confirms for
         autonomous/external sources (even in auto-mode, even at home) and for a
         present user when away. "Full autonomy ≠ a loaded gun." Only a present
         human (source="user", not away) may fire a red-list tool directly.
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

    # Contact-aware: blocked recipients never auto-act; VIP/family confirm unless I'm present.
    recipient = _recipient_of(tool_name, args)
    if recipient:
        from memory import people
        flags = people.match(recipient)
        if flags["blocked"]:
            cid = memory.enqueue_confirmation(tool_name, args, agent=agent, risk="red",
                                              reason=f"BLOCKED contact in '{tool_name}'")
            return {"action": "confirm",
                    "reason": f"'{recipient}' is on your blocklist — needs explicit approval (#{cid}).",
                    "confirm_id": cid}
        if (flags["vip"] or flags["family"]) and (source != "user" or is_away()):
            who = "VIP" if flags["vip"] else "family"
            cid = memory.enqueue_confirmation(tool_name, args, agent=agent, risk="red",
                                              reason=f"{who} recipient in '{tool_name}'")
            return {"action": "confirm",
                    "reason": f"'{recipient}' is {who} — needs your approval (#{cid}).",
                    "confirm_id": cid}

    # Money: a payment at/above the PIN threshold ALWAYS confirms AND requires a
    # fresh PIN to approve — even for a present user at home (owner's strictest
    # choice). Smaller, known amounts fall through to the normal red-list logic.
    if tool_name in _MONEY_TOOLS and needs_pin(tool_name, args):
        amt = _amount_usd(args)
        amt_s = f"${amt:.2f}" if amt is not None else "an unverified amount"
        cid = memory.enqueue_confirmation(
            tool_name, args, agent=agent, risk="red",
            reason=f"money {amt_s} via '{tool_name}' — PIN required",
        )
        return {"action": "confirm",
                "reason": f"Money action ({amt_s}) needs your PIN to approve (#{cid}).",
                "confirm_id": cid}

    # Red-list ALWAYS confirms unless it's a present human at home. A non-user
    # source (autonomous/external) NEVER auto-fires a red-list tool — regardless
    # of auto-mode or away state — and a present user confirms when away.
    if red and (source != "user" or is_away()):
        cid = memory.enqueue_confirmation(
            tool_name, args, agent=agent, risk="red",
            reason=f"{source} requested '{tool_name}'",
        )
        return {"action": "confirm",
                "reason": f"Red-list action '{tool_name}' needs your approval (#{cid}).",
                "confirm_id": cid}

    return {"action": "execute", "reason": "ok", "confirm_id": None}


# ── resolving confirmations (called from Telegram / UI) ───────────────────────
def approve(confirm_id, pin=None) -> str:
    """Execute a pending red-list action the user approved.

    `pin` is required to approve a money move at/above MONEY_CONFIRM_THRESHOLD_USD
    (owner's strictest choice). Surfaces (UI/Telegram) pass it through."""
    c = memory.get_confirmation(confirm_id)
    if not c:
        return f"No pending action #{confirm_id}."
    if c.get("status") != "pending":
        return f"Action #{confirm_id} is already {c.get('status')}."
    # Kill-switch backstop: approve() runs with _bypass_gate=True, so the gate's
    # pause check never fires here. Honor panic/pause explicitly — a halted
    # system must not execute a queued red-list action.
    if is_paused():
        return (f"JARVIS is paused — resume before approving #{confirm_id}. "
                f"(The action stays pending.)")
    # Atomically CLAIM the row (pending → approving). Only the winner proceeds,
    # so two concurrent approvals (UI + Telegram, double-tap, redelivery) can't
    # both fire the same irreversible action.
    if not memory.claim_confirmation(confirm_id):
        return f"Action #{confirm_id} is already being handled."
    from brain.tools.registry import execute_tool  # guarded: avoid circular import
    # get_confirmation already returns args as a parsed dict; tolerate a raw string too.
    args = c.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except Exception:
            args = {}
    elif not isinstance(args, dict):
        args = {}
    # A money move ≥ the threshold needs a fresh PIN even at approval time.
    if needs_pin(c["tool_name"], args):
        from security import identity
        if not pin or not identity.verify_pin(str(pin)):
            memory.set_confirmation_status(confirm_id, "pending")  # un-claim so it can be retried with a PIN
            if not identity.has_pin():
                return (f"#{confirm_id} is a money move ≥ ${MONEY_CONFIRM_THRESHOLD_USD:.0f} and needs a PIN, "
                        f"but no PIN is set — set one first, sir.")
            return f"#{confirm_id} needs your PIN to approve a money move ≥ ${MONEY_CONFIRM_THRESHOLD_USD:.0f}."
    try:
        result = execute_tool(c["tool_name"], args, agent=c.get("agent"), _bypass_gate=True)
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


def panic(minutes: int = 1440) -> str:
    """Emergency stop: halt all autonomy (pause), reject everything queued, and
    revert any reversible actions from the last `minutes`. The 'undo everything' button."""
    set_paused(True)
    rejected = 0
    for c in memory.get_pending_confirmations():
        memory.set_confirmation_status(c["id"], "rejected")
        rejected += 1
    reverted = memory.revert_recent(minutes)
    try:
        from obs.log import log_event
        log_event("autonomy.panic", level="warning", rejected=rejected, window_min=minutes)
    except Exception:
        pass
    return f"🛑 PANIC — paused all autonomy, rejected {rejected} pending action(s), {reverted}."


def pending_summary() -> str:
    """Human-readable list of what's waiting on approval."""
    rows = memory.get_pending_confirmations()
    if not rows:
        return "Nothing is waiting for approval."
    lines = ["Pending approvals:"]
    for c in rows:
        lines.append(f"  #{c['id']} · {c['tool_name']} · {c.get('reason', '')}")
    return "\n".join(lines)
