"""Per-domain supervised→auto trust map: flip one domain to auto while others stay
supervised. Backward-compatible — a domain with no explicit setting falls back to
the global autonomy_mode (so existing global-mode behavior is unchanged)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from brain import autonomy
from brain.tools import registry
from memory import memory, migrations


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "dom.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    autonomy.set_paused(False)
    autonomy.set_away(False)
    yield p


def test_domain_of_maps_known_and_defaults():
    assert autonomy.domain_of("send_email") == "comms"
    assert autonomy.domain_of("transfer_money") == "money"
    assert autonomy.domain_of("control_screen") == "system"
    assert autonomy.domain_of("totally_unknown_tool") == "general"


def test_domain_mode_falls_back_to_global(db):
    autonomy.set_autonomy_mode("auto")
    assert autonomy.get_domain_mode("comms") == "auto"      # unset → global
    autonomy.set_domain_mode("comms", "supervised")
    assert autonomy.get_domain_mode("comms") == "supervised"  # explicit override
    assert autonomy.get_domain_mode("web") == "auto"          # still global


def test_per_domain_shakeout_through_the_gate(db, monkeypatch):
    autonomy.set_autonomy_mode("auto")                         # global auto
    autonomy.set_domain_mode("comms", "supervised")            # but comms held back
    monkeypatch.setattr(autonomy, "TOOL_DOMAIN",
                        {**autonomy.TOOL_DOMAIN, "_probe_comms": "comms", "_probe_web": "web"})
    ran = {}

    @registry.tool(description="comms probe", parameters={}, risk="low")
    def _probe_comms():
        ran["comms"] = True
        return "c"

    @registry.tool(description="web probe", parameters={}, risk="low")
    def _probe_web():
        ran["web"] = True
        return "w"

    try:
        out_c = registry.execute_tool("_probe_comms", {}, source="autonomous")
        assert "comms" not in ran                  # supervised domain → proposed, not run
        assert "approval" in out_c.lower() or "supervised" in out_c.lower()
        out_w = registry.execute_tool("_probe_web", {}, source="autonomous")
        assert ran.get("web") is True              # auto (global fallback) → executed
    finally:
        registry.TOOL_REGISTRY.pop("_probe_comms", None)
        registry.TOOL_REGISTRY.pop("_probe_web", None)


def test_domain_control_tools(db):
    # the owner can flip a domain via the tool (routes through the gate as source=user)
    out = registry.execute_tool("tool_set_domain_mode", {"domain": "comms", "mode": "auto"}, source="user")
    assert "comms" in out.lower() and "auto" in out.lower()
    assert autonomy.get_domain_mode("comms") == "auto"
    registry.execute_tool("tool_set_domain_mode", {"domain": "money", "mode": "supervised"}, source="user")
    listing = registry.execute_tool("tool_list_domain_modes", {}, source="user")
    assert "comms" in listing and "money" in listing
