"""P5 — portable self: export the durable-memory DBs into one bundle and restore
them on a 'fresh machine'. Round-trips a real sqlite payload through a temp scope
so the live memory dir + the Desktop vault are NEVER touched."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import export


def _seed_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE facts (k TEXT, v TEXT)")
    conn.executemany("INSERT INTO facts VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _read_db(path):
    conn = sqlite3.connect(path)
    rows = conn.execute("SELECT k, v FROM facts ORDER BY k").fetchall()
    conn.close()
    return rows


def test_export_import_roundtrip(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    seeded = [("name", "Elnatan"), ("city", "Addis")]
    _seed_db(src / "jarvis.db", seeded)
    _seed_db(src / "life.db", [("habit", "gym")])

    out = tmp_path / "bundles"
    bundle = export.export_self(out, src_dir=src, stamp="testrun")
    assert Path(bundle).exists()
    assert bundle.endswith("alfred-self-testrun.tar.gz")

    manifest = export.read_manifest(bundle)
    assert manifest["version"] == export.BUNDLE_VERSION
    assert "jarvis.db" in manifest["dbs"] and "life.db" in manifest["dbs"]
    # the dbs that don't exist in src are not claimed
    assert "business.db" not in manifest["dbs"]

    # restore onto a 'fresh machine'
    dest = tmp_path / "restored"
    summary = export.import_self(bundle, dest_dir=dest)
    assert "Restored 2" in summary
    assert _read_db(dest / "jarvis.db") == sorted(seeded)
    assert _read_db(dest / "life.db") == [("habit", "gym")]


def test_export_only_bundles_present_dbs(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _seed_db(src / "jarvis.db", [("a", "1")])
    bundle = export.export_self(tmp_path / "out", src_dir=src, stamp="one")
    manifest = export.read_manifest(bundle)
    assert manifest["dbs"] == ["jarvis.db"]


def test_import_ignores_paths_outside_the_known_set(tmp_path):
    """A tampered archive with a traversal/extra entry must not write outside the
    flat, known DB set."""
    import tarfile

    src = tmp_path / "src"
    src.mkdir()
    _seed_db(src / "jarvis.db", [("a", "1")])
    bundle = export.export_self(tmp_path / "out", src_dir=src, stamp="evil")

    # append a hostile member to the gzip'd tar by repacking
    evil = tmp_path / "evil.txt"
    evil.write_text("pwned")
    repacked = tmp_path / "repacked.tar.gz"
    with tarfile.open(bundle, "r:gz") as src_tar, tarfile.open(repacked, "w:gz") as dst_tar:
        for m in src_tar.getmembers():
            dst_tar.addfile(m, src_tar.extractfile(m))
        dst_tar.add(evil, arcname="../escape.txt")

    dest = tmp_path / "restored"
    export.import_self(repacked, dest_dir=dest)
    # the traversal entry must NOT have escaped the dest dir
    assert not (tmp_path / "escape.txt").exists()
    assert (dest / "jarvis.db").exists()
