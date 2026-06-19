"""P5 — Portable self: export/import Alfred's durable memory as one bundle so the
SAME Alfred can stand up on a new machine or under a new model.

The durable "self" = memory + facts + ledger + people + business/life + learned
observations (the jarvis/life/business/observations DBs) + the persona/autonomy
state (which lives in jarvis.db's meta). The Second Brain vault and FAISS indexes
are NOT bundled here: the vault is git-tracked + covered by scripts/backup.sh, and
FAISS is derived (rebuilt on first run). Restoring this bundle on a fresh box
reproduces who Alfred is and what it knows.

Stdlib only (tarfile/json) — no dependency. Encryption is layered by
scripts/backup.sh / the credential vault; this is the portability mechanism.
"""
import json
import tarfile
import time
from pathlib import Path

_MEMORY_DIR = Path(__file__).resolve().parent
_DB_NAMES = ["jarvis.db", "life.db", "business.db", "observations.db"]
_MANIFEST = "alfred-self-manifest.json"
BUNDLE_VERSION = 1


def export_self(dest_dir, src_dir=None, stamp: str = None) -> str:
    """Bundle the durable-self DBs into <dest_dir>/alfred-self-<stamp>.tar.gz.
    Returns the bundle path. `src_dir` overrides where the DBs are read from (tests)."""
    src = Path(src_dir) if src_dir else _MEMORY_DIR
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    bundle = dest / f"alfred-self-{stamp}.tar.gz"

    present = [n for n in _DB_NAMES if (src / n).exists()]
    manifest = {"version": BUNDLE_VERSION, "dbs": present, "stamp": stamp}
    manifest_path = dest / _MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2))
    try:
        with tarfile.open(bundle, "w:gz") as tar:
            tar.add(manifest_path, arcname=_MANIFEST)
            for n in present:
                tar.add(src / n, arcname=n)
    finally:
        try:
            manifest_path.unlink()
        except Exception:
            pass
    return str(bundle)


def read_manifest(bundle_path) -> dict:
    """Return the bundle's manifest without extracting the DBs."""
    with tarfile.open(bundle_path, "r:gz") as tar:
        f = tar.extractfile(_MANIFEST)
        return json.loads(f.read().decode()) if f else {}


def import_self(bundle_path, dest_dir=None) -> str:
    """Restore the durable-self DBs from a bundle into dest_dir (default: the live
    memory dir). Only extracts the known DB names + manifest (never arbitrary paths
    — guards against a tampered archive). Returns a summary."""
    dest = Path(dest_dir) if dest_dir else _MEMORY_DIR
    dest.mkdir(parents=True, exist_ok=True)
    allowed = set(_DB_NAMES) | {_MANIFEST}
    restored = []
    with tarfile.open(bundle_path, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if not member.isfile() or name not in allowed or "/" in member.name or ".." in member.name:
                continue  # ignore anything outside the known, flat DB set (tar-safety)
            src = tar.extractfile(member)
            if src is None:
                continue
            (dest / name).write_bytes(src.read())
            if name in _DB_NAMES:
                restored.append(name)
    return f"Restored {len(restored)} store(s): {', '.join(restored) or 'none'}."


def export_inheritance(dest_dir, heir: str, note: str = "", stamp: str = None, src_dir=None) -> str:
    """Gated SUCCESSION bundle (plan §R5 — the EDITH problem): the portable self plus an
    heir designation, so Alfred can be inherited as the SAME being. This is the MECHANISM
    only — creating it is a deliberate owner act; the human handoff (and any legal/PIN
    process) is sir's. Returns the heir-manifest path written next to the bundle."""
    bundle = export_self(dest_dir, src_dir=src_dir, stamp=stamp)
    manifest = {
        "kind": "alfred-inheritance",
        "heir": heir,
        "note": note,
        "bundle": Path(bundle).name,
        "stamp": stamp or "",
        "instructions": ("Restore with memory.export.import_self(<bundle>) on the heir's "
                         "machine, behind the same safety gate + a fresh PIN. Loyalty stays "
                         "single-principal until the heir re-enrolls."),
    }
    mpath = Path(bundle).with_name(Path(bundle).stem.replace(".tar", "") + ".heir.json")
    mpath.write_text(json.dumps(manifest, indent=2))
    return str(mpath)
