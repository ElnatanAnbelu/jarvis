"""Regression: JARVIS must NEVER be able to modify its own code, safety gate, or
secrets (the P0 'JARVIS can rewrite its own safety gate' finding).

Two layers are pinned here:
  1. control/files.py refuses any write/create/move/delete inside the install
     tree, regardless of the gate — a hard self-write firewall.
  2. write_file/create_file/move_file are on the RED_LIST so they also require
     confirmation when away / from an external source.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import control.files as files
import brain.autonomy as autonomy


SELF_PATHS = [
    "brain/autonomy.py",
    "brain/tools/registry.py",
    "security/identity.py",
    ".env",
    ".session_token",
    "memory/people.py",
]


def test_firewall_blocks_overwriting_own_code():
    for rel in SELF_PATHS:
        out = files.write_file(rel, "RED_LIST=set()")
        assert "Refused" in out, f"write_file was NOT blocked for {rel}: {out}"


def test_firewall_blocks_creating_inside_install():
    out = files.create_file("brain/tools/evil.py", "import os")
    assert "Refused" in out


def test_firewall_blocks_moving_own_code_out():
    out = files.move_file("brain/autonomy.py", "/tmp/exfil.py")
    assert "Refused" in out
    # the file is of course still there
    assert (files._INSTALL_ROOT / "brain" / "autonomy.py").exists()


def test_firewall_blocks_deleting_own_code():
    out = files.delete_file("brain/autonomy.py")
    assert "Refused" in out
    assert (files._INSTALL_ROOT / "brain" / "autonomy.py").exists()


def test_legitimate_external_writes_still_work():
    p = os.path.join(tempfile.gettempdir(), "jarvis_fw_ok.txt")
    try:
        assert "Created" in files.create_file(p, "hi")
        assert "Written" in files.write_file(p, "bye")
        assert open(p).read() == "bye"
    finally:
        if os.path.exists(p):
            os.remove(p)


def test_file_mutating_tools_are_red_list():
    for name in ("write_file", "create_file", "move_file", "delete_file"):
        assert autonomy.is_red(name), f"{name} must be on the RED_LIST"
