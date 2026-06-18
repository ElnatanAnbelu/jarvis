"""Structured observability for JARVIS.

JSON logs with correlation IDs so you can answer "what did it do, why, did it
fail?" — the black-box recorder that makes autonomy trustworthy. Also a tiny
daemon-heartbeat registry surfaced via /api/status for liveness.

Local-first: logs to a rotating file under ~/Library/Logs/JARVIS by default;
WARN+ also to stderr. Never raises into callers.
"""
import contextvars
import json
import logging
import os
import sys
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(os.environ.get("JARVIS_LOG_DIR", str(Path.home() / "Library" / "Logs" / "JARVIS")))
_corr = contextvars.ContextVar("jarvis_corr", default=None)
_configured = False

# ── correlation id ───────────────────────────────────────────────────────────
def new_correlation(cid: str = None) -> str:
    """Start a new correlation scope (one per request / autonomous task)."""
    cid = cid or uuid.uuid4().hex[:12]
    _corr.set(cid)
    return cid


def correlation_id():
    return _corr.get()


# ── formatting / config ──────────────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def format(self, record):
        d = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "corr": _corr.get(),
        }
        for k, v in getattr(record, "fields", {}).items():
            d[k] = v
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info)
        return json.dumps(d, default=str)


def _configure():
    global _configured
    if _configured:
        return
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        root = logging.getLogger("jarvis")
        root.setLevel(logging.INFO)
        root.propagate = False
        fh = RotatingFileHandler(_LOG_DIR / "jarvis.jsonl", maxBytes=5_000_000, backupCount=5)
        fh.setFormatter(_JsonFormatter())
        root.addHandler(fh)
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(_JsonFormatter())
        sh.setLevel(logging.WARNING)
        root.addHandler(sh)
    except Exception:
        pass  # never let logging setup break the app
    _configured = True


def get_logger(name: str = None):
    _configure()
    return logging.getLogger("jarvis" if not name else f"jarvis.{name}")


def log_event(event: str, level: str = "info", **fields):
    """Emit a structured event. Safe — never raises."""
    try:
        lg = get_logger(fields.pop("logger", None))
        lg.log(getattr(logging, level.upper(), logging.INFO), event, extra={"fields": fields})
    except Exception:
        pass


def log_exception(event: str, **fields):
    """Log a caught exception with traceback at ERROR. Use in place of `except: pass`."""
    try:
        get_logger(fields.pop("logger", None)).error(event, exc_info=True, extra={"fields": fields})
    except Exception:
        pass


# ── daemon heartbeats / liveness ─────────────────────────────────────────────
_HEARTBEATS = {}


def heartbeat(name: str):
    """Record that a daemon (wake / scheduler / tts ...) is alive right now."""
    _HEARTBEATS[name] = time.time()


def liveness(stale_after: float = 180.0) -> dict:
    """Per-daemon {last_tick, stale} for /api/status."""
    now = time.time()
    return {
        name: {"last_tick": round(now - ts, 1), "stale": (now - ts) > stale_after}
        for name, ts in _HEARTBEATS.items()
    }
