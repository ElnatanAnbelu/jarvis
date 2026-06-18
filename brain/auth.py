"""Single source of truth for cloud-LLM auth (Anthropic).

Why this exists: the auth detector was copy-pasted into ~6 modules and drifted —
several call sites passed the ``(key, is_oauth)`` tuple straight into
``api_key=``, which (a) never matched the ``if not auth_key`` guard since a
2-tuple is always truthy and (b) crashed the Anthropic client. That broke
vision, document Q&A, briefings, and computer-use. This module is the one
correct implementation; every consumer imports from here.

Note: the JARVIS *brain* goes fully-local in P1 (see the plan). This cloud path
remains only so cloud-capable features degrade gracefully (a clean "no key"
message) instead of crashing when no Anthropic credential is present.
"""
import os


def get_auth_key():
    """Return ``(key, is_oauth)``.

    OAuth bearer tokens (``sk-ant-oat...`` / ``CLAUDE_CODE_OAUTH_TOKEN``) must be
    passed as ``auth_token=``; plain API keys as ``api_key=``. Returns
    ``(None, False)`` when no credential is configured.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key and not api_key.startswith("sk-ant-oat"):
        return api_key, False
    oauth = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if oauth:
        return oauth, True
    return None, False


def make_client(key=None, is_oauth=False):
    """Build an Anthropic client with the correct auth method.

    Returns ``None`` when no credential is available, so callers can degrade
    gracefully instead of constructing a broken client.
    """
    import anthropic
    if key is None:
        key, is_oauth = get_auth_key()
    if not key:
        return None
    if is_oauth:
        return anthropic.Anthropic(auth_token=key)
    return anthropic.Anthropic(api_key=key)
