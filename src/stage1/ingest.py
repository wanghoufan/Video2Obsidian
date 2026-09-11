"""S1-T01: specified-path ingest scaffold + job-scoped landing.

Implements STAGE1-PLAN S1-T01 only:
  - explicit local video path in (no Watch/Scan/Reconcile)
  - volume gate: iCloud / network / remote roots BLOCK (§3.14, §61)
  - fstat capture (device/inode/size/mtime_ns) + first Strong SHA256
    as Logical Source content_identity (§21, §6 subset)
  - G1: Source before Run — Run without a validated Source FAILs
  - job-scoped namespace per §36: data/jobs/<job_id>/
    (source.json / run.json / manifest.json / raw/ placeholder)
  - per-job SQLite proving the NOT NULL chain (sources -> runs)

STOP EXPANSION: no Verification (T02), no ASR (T03), no post-ASR
verify (T04), no PREPARE/COMMIT (T05/T06), no Recovery (T07).
Manifest state is SCAFFOLD — never PREPARED/COMMITTED.

Stdlib only. Never writes to the source video (read-only open).
Writes only under the given data_root (test dir) plus its own
JSON/SQLite outputs.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid

CHUNK_BYTES = 8 * 1024 * 1024

# V1.8 §6 Logical Source minimal subset required by S1-T01.
REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "content_identity",
    "source_size",
    "source_mtime_ns",
    "source_device_id",
    "source_inode_or_file_id",
)

# creation_mode allowlist for Stage1 scaffold (AUTO stays in Stage2).
ALLOWED_CREATION_MODES = ("MANUAL", "STAGE1_TEST")

# Path markers that always mean a non-local root (§3.14 BLOCK).
REMOTE_PATH_MARKERS = (
    "Mobile Documents",
    "com~apple~CloudDocs",
    "iCloud Drive",
)

# fstype values (macOS `stat -f %T`) that mean remote/network.
REMOTE_FSTYPES = frozenset({"nfs", "smbfs", "afpfs", "webdav", "fuse"})


class VolumeBlocked(RuntimeError):
    """Raised when a root is iCloud/network/remote (§3.14)."""


class G1Violation(ValueError):
    """Raised when a Run is created without a validated Source (G1)."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _mount_table() -> list[tuple[str, str, list[str]]]:
    """Parse macOS `mount` into (device, mountpoint, opts) rows."""
    out = subprocess.run(["mount"], capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise OSError(f"`mount` failed: {out.stderr.strip()}")
    rows = []
    for line in out.stdout.splitlines():
        m = re.match(r"^(\S+) on (.*) \(([^)]*)\)\s*$", line)
        if not m:
            continue
        opts = [t.strip() for t in m.group(3).split(",")]
        rows.append((m.group(1), m.group(2), opts))
    return rows


def probe_volume(path: str) -> dict:
    """Probe volume type for a path via the OS mount table.

    ALLOW iff the covering mount carries the OS `local` flag (§61 Local
    Filesystem Only; external local volumes allowed as Archive roots).
    Anything else — iCloud markers, nfs/smbfs/afp fstypes, missing
    `local` flag, unparseable table — BLOCKs fail-closed (§3.13).
    """
    abspath = os.path.abspath(path)
    for marker in REMOTE_PATH_MARKERS:
        if marker in abspath:
            return {
                "path": abspath,
                "fstype": "unknown",
                "local_or_remote": "remote",
                "verdict": "BLOCK",
                "reason": f"path contains iCloud marker {marker!r}",
                "code": "BLOCKED_UNSUPPORTED_ROOT_FOR_V1",
            }
    try:
        rows = _mount_table()
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "path": abspath,
            "fstype": "unknown",
            "local_or_remote": "unknown",
            "verdict": "BLOCK",
            "reason": f"mount table unreadable: {exc}",
            "code": "BLOCKED_UNSUPPORTED_ROOT_FOR_V1",
        }
    best: tuple[str, str, list[str]] | None = None
    for dev, mnt, opts in rows:
        if abspath == mnt or abspath.startswith(mnt.rstrip("/") + "/"):
            if best is None or len(mnt) > len(best[1]):
                best = (dev, mnt, opts)
    if best is None:
        return {
            "path": abspath,
            "fstype": "unknown",
            "local_or_remote": "unknown",
            "verdict": "BLOCK",
            "reason": "no covering mount found",
            "code": "BLOCKED_UNSUPPORTED_ROOT_FOR_V1",
        }
    dev, mnt, opts = best
    fstype = opts[0] if opts else "unknown"
    if "local" in opts and fstype not in REMOTE_FSTYPES:
        return {
            "path": abspath,
            "fstype": fstype,
            "mount_point": mnt,
            "device": dev,
            "local_or_remote": "local",
            "verdict": "ALLOW",
            "reason": f"local mount {mnt!r} fstype {fstype!r}",
            "code": "OK",
        }
    return {
        "path": abspath,
        "fstype": fstype,
        "mount_point": mnt,
        "device": dev,
        "local_or_remote": "remote",
        "verdict": "BLOCK",
        "reason": f"non-local mount {mnt!r} fstype {fstype!r}",
        "code": "BLOCKED_UNSUPPORTED_ROOT_FOR_V1",
    }


def fstat_capture(path: str) -> dict:
    """Capture fstat identity signals (G2-ready; T02/T04 reuse this)."""
    st = os.stat(path)  # follows symlinks: identity of the real bytes
    return {
        "device": st.st_dev,
        "inode": st.st_ino,
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
    }


def sha256_file(path: str) -> str:
    """Strong SHA256 over file bytes, streamed (read-only)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:  # read-only; never mutates the source
        while True:
            chunk = fh.read(CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def validate_source_record(record: dict) -> None:
    """G1 NOT NULL chain check: every required field present and non-null."""
    missing = [f for f in REQUIRED_SOURCE_FIELDS if record.get(f) is None]
    if missing:
        raise G1Violation(
            "G1 NOT NULL chain failed: source fields missing/null: "
            + ", ".join(missing)
        )


def register_source(source_path: str, volume: dict, fstat: dict, content_sha256: str) -> dict:
    """Build the minimal Logical Source record (§6 subset + task fields)."""
    abspath = os.path.abspath(source_path)
    now = _utc_now_iso()
    source_id = "src_" + content_sha256[:16]
    record = {
        "source_id": source_id,
        "path_identity_key": abspath,
        "content_identity": "sha256:" + content_sha256,
        "logical_source_identity": abspath + "|sha256:" + content_sha256,
        "current_path": abspath,
        "current_location_type": "SPECIFIED_PATH",
        "source_size": fstat["size"],
        "source_mtime_ns": fstat["mtime_ns"],
        "source_device_id": fstat["device"],
        "source_inode_or_file_id": fstat["inode"],
        "status": "ACTIVE",
        "hash_algorithm": "SHA256",
        "volume": volume,
        "first_seen_at": now,
        "last_seen_at": now,
    }
    validate_source_record(record)
    return record


def create_run(
    job_id: str,
    source_record: dict | None,
    source_json_path: str | None,
    creation_mode: str = "MANUAL",
) -> dict:
    """Create the single Processing Run. G1: Source first, else FAIL."""
    if creation_mode not in ALLOWED_CREATION_MODES:
        raise G1Violation(
            f"creation_mode {creation_mode!r} not allowed in Stage1 scaffold; "
            f"want one of {ALLOWED_CREATION_MODES} (AUTO stays in Stage2)"
        )
    if not source_record:
        raise G1Violation("G1 violated: Run creation without Source record")
    validate_source_record(source_record)
    if not source_json_path or not os.path.isfile(source_json_path):
        raise G1Violation(
            "G1 violated: source.json evidence missing on disk; "
            "Run must follow persisted Source"
        )
    return {
        "job_id": job_id,
        "run_id": job_id,
        "source_id": source_record["source_id"],
        "creation_mode": creation_mode,
        "status": "SCAFFOLD_CREATED",
        "g1_source_before_run": True,
        "created_at": _utc_now_iso(),
    }


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def init_sqlite(sqlite_path: str, source: dict, run: dict) -> None:
    """Per-job SQLite proving the Source->Run NOT NULL chain."""
    con = sqlite3.connect(sqlite_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute(
            "CREATE TABLE IF NOT EXISTS sources ("
            "source_id TEXT PRIMARY KEY, "
            "content_identity TEXT NOT NULL, "
            "source_size INTEGER NOT NULL, "
            "source_mtime_ns INTEGER NOT NULL, "
            "source_device_id INTEGER NOT NULL, "
            "source_inode_or_file_id INTEGER NOT NULL, "
            "current_path TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "first_seen_at TEXT NOT NULL)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS processing_runs ("
            "job_id TEXT PRIMARY KEY, "
            "source_id TEXT NOT NULL REFERENCES sources(source_id), "
            "creation_mode TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        with con:  # single transaction: Source row first, then Run row
            con.execute(
                "INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    source["source_id"],
                    source["content_identity"],
                    source["source_size"],
                    source["source_mtime_ns"],
                    source["source_device_id"],
                    source["source_inode_or_file_id"],
                    source["current_path"],
                    source["status"],
                    source["first_seen_at"],
                ),
            )
            con.execute(
                "INSERT OR REPLACE INTO processing_runs VALUES (?,?,?,?,?)",
                (
                    run["job_id"],
                    run["source_id"],
                    run["creation_mode"],
                    run["status"],
                    run["created_at"],
                ),
            )
    finally:
        con.close()


def ingest_specified_path(
    source_path: str,
    data_root: str,
    job_id: str | None = None,
    creation_mode: str = "MANUAL",
) -> dict:
    """Run the S1-T01 scaffold. Returns a summary dict; raises on FAIL/BLOCK."""
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"source video not found: {source_path}")

    # Volume gates first (§3.14): either side BLOCKs before any write.
    src_vol = probe_volume(source_path)
    if src_vol["verdict"] != "ALLOW":
        raise VolumeBlocked(f"source root blocked: {src_vol!r}")
    data_vol = probe_volume(data_root)
    if data_vol["verdict"] != "ALLOW":
        raise VolumeBlocked(f"data root blocked: {data_vol!r}")

    # G2-ready fstat + first Strong SHA256 (content_identity).
    fstat = fstat_capture(source_path)
    content_sha256 = sha256_file(source_path)

    source = register_source(source_path, src_vol, fstat, content_sha256)

    if job_id is None:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        job_id = f"job_{stamp}_{uuid.uuid4().hex[:8]}"
    job_dir = os.path.join(os.path.abspath(data_root), "data", "jobs", job_id)
    os.makedirs(os.path.join(job_dir, "raw"), exist_ok=True)

    source_json = os.path.join(job_dir, "source.json")
    _write_json(source_json, source)

    # G1: Run only after the Source record is validated + persisted.
    run = create_run(job_id, source, source_json, creation_mode)
    run["data_root"] = os.path.abspath(data_root)
    run["namespace"] = f"data/jobs/{job_id}/"
    run["source_volume"] = src_vol
    run["data_volume"] = data_vol
    _write_json(os.path.join(job_dir, "run.json"), run)

    manifest = {
        "job_id": job_id,
        "source_id": source["source_id"],
        "stage": "Stage1-S1-T01",
        "state": "SCAFFOLD",
        "receipts": [],
        "lineage": {
            "source": "source.json",
            "run": "run.json",
            "raw": "raw/ (placeholder — no artifact yet; T05/T06 own raw.json)",
        },
        "volume": {"source": src_vol, "data": data_vol},
        "created_at": _utc_now_iso(),
        "notes": "Scaffold only. T02 Verification / T03 ASR / T04 post-verify / "
        "T05 PREPARE / T06 COMMIT / T07 Recovery NOT implemented (STOP EXPANSION).",
    }
    _write_json(os.path.join(job_dir, "manifest.json"), manifest)

    with open(os.path.join(job_dir, "raw", ".placeholder"), "w", encoding="utf-8") as fh:
        fh.write(
            "S1-T01 placeholder: raw/ reserved per §36 namespace; "
            "no raw.json exists until T05 PREPARE / T06 COMMIT.\n"
        )

    sqlite_path = os.path.join(job_dir, "job.sqlite")
    init_sqlite(sqlite_path, source, run)

    return {
        "job_id": job_id,
        "job_dir": job_dir,
        "source_json": source_json,
        "run_json": os.path.join(job_dir, "run.json"),
        "manifest_json": os.path.join(job_dir, "manifest.json"),
        "sqlite": sqlite_path,
        "source": source,
        "run": run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S1-T01 specified-path ingest scaffold")
    parser.add_argument("--source", required=True, help="absolute path of the test video")
    parser.add_argument("--data-root", required=True, help="test Data Root (local disk only)")
    parser.add_argument("--job-id", default=None, help="optional fixed job id")
    parser.add_argument("--creation-mode", default="MANUAL", choices=ALLOWED_CREATION_MODES)
    args = parser.parse_args(argv)
    try:
        result = ingest_specified_path(args.source, args.data_root, args.job_id, args.creation_mode)
    except VolumeBlocked as exc:
        print(f"BLOCK {exc}", file=sys.stderr)
        return 2
    except (G1Violation, FileNotFoundError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"job_id": result["job_id"], "job_dir": result["job_dir"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
