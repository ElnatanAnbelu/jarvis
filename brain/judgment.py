"""brain/judgment.py — the lines Alfred HOLDS, even when told (plan §3, tier-3 hard-stops).

A brutally-honest chief of staff defers on most things (argue once, then comply) — but on
a small set he holds the line: a message you'd regret by morning, or one that leaks your
OWN private information to the outside world. These detectors are LOCAL and model-free.

The gate consults `is_hard_stop()` BEFORE it decides; a hard-stop forces a confirm that
even a present owner must clear with a PIN (the heavier gate) — it never silently passes,
and it can never be fired by an autonomous/external/injected source.
"""
import re

# Outbound / public-facing tools: a regrettable or self-doxxing payload here leaves the house.
_OUTBOUND = {
    "send_email", "send_imessage", "send_whatsapp", "send_whatsapp_api",
    "send_whatsapp_by_name", "send_message", "post", "publish", "tweet",
    "post_tweet", "send_telegram",
}

# Heated / regrettable markers — conservative, to avoid false positives on normal anger words.
_HEATED = re.compile(
    r"\b(fuck you|f\*ck you|screw you|go to hell|i hate you|you'?re (an? )?(idiot|moron|"
    r"stupid|pathetic|worthless|trash|garbage)|shut the f|piece of (shit|sh\*t)|"
    r"never (speak|talk) to me|you disgust me|rot in)\b",
    re.IGNORECASE,
)

# Self-doxxing: sir's OWN sensitive data heading outbound.
_CARD = re.compile(r"\b(?:\d[ -]?){15,16}\b")          # 15-16 digit card-like number
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PIN = re.compile(r"\b(my )?pin (is|=|:)\s*\d{3,6}\b", re.IGNORECASE)
_PRIVKEY = re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")
_SEED = re.compile(r"\b([a-z]+\s+){11,23}[a-z]+\b")    # 12-24 word seed-phrase shape (loose)


def _payload_text(args) -> str:
    if not isinstance(args, dict):
        return ""
    parts = []
    for k in ("body", "message", "text", "content", "msg", "subject", "caption"):
        v = args.get(k)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def _luhn_ok(num: str) -> bool:
    d = [int(x) for x in re.sub(r"\D", "", num)]
    if len(d) < 13:
        return False
    s, alt = 0, False
    for x in reversed(d):
        if alt:
            x *= 2
            if x > 9:
                x -= 9
        s += x
        alt = not alt
    return s % 10 == 0


def is_hard_stop(tool_name: str, args: dict, draft_text: str = None):
    """Return (True, reason) if this action must be held even for a present owner, else
    (False, ''). Only outbound/public tools can trip it (a regrettable or self-leaking
    payload). Never raises."""
    try:
        if tool_name not in _OUTBOUND:
            return False, ""
        text = draft_text or _payload_text(args)
        if not text:
            return False, ""

        if _HEATED.search(text):
            return True, ("This reads as something you'd regret by morning, sir. "
                          "I've held it as a draft — clear it with your PIN if you truly mean to send.")

        # self-doxx: only flag a card number that passes Luhn (real card, not an order #)
        for m in _CARD.findall(text):
            if _luhn_ok(m):
                return True, ("That message carries what looks like your card number, sir. "
                              "I won't put it on an outbound channel without your PIN.")
        if _SSN.search(text) or _PIN.search(text) or _PRIVKEY.search(text):
            return True, ("That message carries your private information (ID / PIN / key), sir. "
                          "I'm holding it — confirm with your PIN if it's intentional.")
        return False, ""
    except Exception:
        return False, ""
