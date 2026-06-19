"""Biometric enrollment: capturing references sets the flags, and verification stays
HONEST — face verify never false-accepts without a strong encoding, voice stays graceful.
PIN remains the reliable factor. (Hardware capture isn't exercised here.)"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import memory, migrations
from security import identity


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = str(tmp_path / "id.db")
    monkeypatch.setattr(memory, "DB_PATH", p)
    monkeypatch.setattr(migrations, "DB_PATH", p)
    memory.init_db()
    monkeypatch.setattr(identity, "_enroll_dir", lambda: tmp_path)   # don't touch ~/.alfred
    yield p


def test_enroll_face_sets_flag_and_writes_reference(db, tmp_path):
    out = identity.enroll_face(np.zeros((120, 120, 3), dtype=np.uint8))
    assert "enrolled" in out.lower()
    assert memory.get_flag("face_enrolled", False)
    assert (tmp_path / "face_ref.png").exists()


def test_enroll_voice_sets_flag(db):
    out = identity.enroll_voice(["/tmp/a.wav", "/tmp/b.wav"])
    assert "enrolled" in out.lower()
    assert memory.get_flag("voice_enrolled", False)
    assert int(memory.get_flag("voice_ref_count", 0)) == 2


def test_face_verify_never_false_accepts_without_strong_encoding(db):
    identity.enroll_face(np.zeros((120, 120, 3), dtype=np.uint8))   # no real face → no encoding
    assert identity.verify_face() is False   # presence alone must NOT count as identity


def test_voice_verify_is_graceful_false(db):
    identity.enroll_voice(["/tmp/a.wav"])
    assert identity.verify_voice() is False


def test_pin_remains_the_reliable_factor(db):
    identity.set_pin("4321")
    assert identity.has_pin()
    assert identity.verify_pin("4321") and not identity.verify_pin("0000")
