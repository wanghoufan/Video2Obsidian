"""S10-T01: Archive 前 Mandatory Strong Verification + G3 预门.

Implements STAGE10-PLAN S10-T01 only (V1.8 §26 + G2 + G3)::

    verify_source_for_archive(source_id, con):
      无条件重算 Source SHA256（never a size/mtime shortcut）+
      前后 fstat 对比（device/inode/size/mtime_ns）+
      current_hash == sources.content_identity 才放行，
      否则 BLOCKED_SOURCE_CHANGED（Raw 不 Commit、不 Publish、
      不 Archive、不删源；本模块零写库、零删文件）.

    assert_publish_present(source_id, con):
      G3 预门前半：沿 processing_runs -> normalization_revisions ->
      render_revisions -> publish_records 链找到 status=PUBLISHED 的行；
      无行即 BLOCKED_ARCHIVE_NO_PUBLISH；再核诱饵 canonical 存在性与
      published_hash 一致性（用户已编辑即 BLOCKED_ARCHIVE_CANONICAL_EDITED，
      缺失即 BLOCKED_ARCHIVE_CANONICAL_MISSING；用户编辑优先，覆盖计数恒 0）.

Read-only reuse (never amended here): stage1.ingest fstat_capture /
sha256_file (Strong Hash mechanics) + stage2.store sources DDL shape.
This module never writes the DB, never removes any file, never stages
bytes, and never enters transcription (every verdict carries
asr_calls == 0 and whisper_calls == 0).

STOP EXPANSION: no Level A/B/C move (T02/T03), no Unsupported verdict
beyond the G3 door (T04 owns the split), no Source column write
(T04 owns the four columns), no auto-start daemon, no desktop UI,
no dataset-metric path.
"""

from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

STATE_VERIFYING = "VERIFYING_SOURCE_FOR_ARCHIVE"
BLOCK_SOURCE_CHANGED = "BLOCKED_SOURCE_CHANGED"
BLOCK_NO_PUBLISH = "BLOCKED_ARCHIVE_NO_PUBLISH"
BLOCK_CANONICAL_MISSING = "BLOCKED_ARCHIVE_CANONICAL_MISSING"
BLOCK_CANONICAL_EDITED = "BLOCKED_ARCHIVE_CANONICAL_EDITED"
PASS_ARCHIVE_VERIFY = "OK_SOURCE_VERIFIED_FOR_ARCHIVE"
PASS_PUBLISH_PRESENT = "OK_PUBLISH_PRESENT_UNEDITED"

FSTAT_FIELDS = ("device", "inode", "size", "mtime_ns")

# sources row -> fstat-shaped signals (central DB column names, read-only).
_STORED_FSTAT_MAP = {
    "device": "source_device_id",
    "inode": "source_inode_or_file_id",
    "size": "source_size",
    "mtime_ns": "source_mtime_ns",
}


class ArchiveSourceError(ValueError):
    """FAIL: the stored Source row is missing or unusable (fail-closed)."""


def _sha256_file_hex(path: str) -> str:
    from stage1.ingest import sha256_file  # noqa: PLC0415 (read-only reuse)

    return sha256_file(path)


def _fstat_capture(path: str) -> dict:
    from stage1.ingest import fstat_capture  # noqa: PLC0415 (read-only reuse)

    return fstat_capture(path)


def read_source_row(con, source_id: str) -> dict | None:
    """Read one sources row as a plain dict (None when absent)."""
    row = con.execute(
        "SELECT source_id, source_relative_path, path_identity_key,"
        " content_identity, logical_source_identity, current_path,"
        " current_location_type, source_size, source_mtime_ns,"
        " source_device_id, source_inode_or_file_id, status,"
        " first_seen_at, last_seen_at, archived_at"
        " FROM sources WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    if row is None:
        return None
    keys = (
        "source_id", "source_relative_path", "path_identity_key",
        "content_identity", "logical_source_identity", "current_path",
        "current_location_type", "source_size", "source_mtime_ns",
        "source_device_id", "source_inode_or_file_id", "status",
        "first_seen_at", "last_seen_at", "archived_at",
    )
    if hasattr(row, "keys"):
        return {key: row[key] for key in keys}
    return dict(zip(keys, list(row)))


def _stored_fstat(row: dict) -> dict:
    missing = [f for f, col in _STORED_FSTAT_MAP.items() if row.get(col) is None]
    if missing:
        raise ArchiveSourceError(
            "sources row missing NOT NULL fstat columns: " + ", ".join(missing)
        )
    if row.get("content_identity") is None:
        raise ArchiveSourceError("sources row missing content_identity")
    return {f: row[col] for f, col in _STORED_FSTAT_MAP.items()}


def verify_source_for_archive(
    source_id: str, con, source_path: str | None = None
) -> dict:
    """Unconditional Strong Verify of a Source right before archive (§26).

    Always rehashes the bytes (no size/mtime shortcut: a tamper clip
    with same size + same mtime +异字节 still BLOCKs) and records
    fstat on both sides of the hash. PASS iff the fresh hash equals
    the stored content_identity. Drift == BLOCK (fail-closed); only a
    broken stored row raises (FAIL). No DB write, no file removal.
    """
    row = read_source_row(con, source_id)
    if row is None:
        raise ArchiveSourceError("unknown source_id %r" % (source_id,))
    path = os.path.abspath(source_path or row["current_path"])
    if not row.get("current_path"):
        raise ArchiveSourceError("sources row has no current_path")
    stored = _stored_fstat(row)
    content_identity = row["content_identity"]
    base = {
        "state": STATE_VERIFYING,
        "source_id": source_id,
        "source_path": path,
        "content_identity": content_identity,
        "fstat_stored": stored,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
    try:
        fstat_before = _fstat_capture(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_SOURCE_CHANGED,
            "reason": "source unreadable before archive: %s" % (exc,),
            "fstat_before": None,
            "fstat_after": None,
            "fstat_changed_before": list(FSTAT_FIELDS),
            "fstat_changed_after": list(FSTAT_FIELDS),
            "hash_recomputed": False,
            "current_hash": None,
        }
    try:
        current_hash = "sha256:" + _sha256_file_hex(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_SOURCE_CHANGED,
            "reason": "source vanished during rehash: %s" % (exc,),
            "fstat_before": fstat_before,
            "fstat_after": None,
            "fstat_changed_before": [
                f for f in FSTAT_FIELDS if fstat_before[f] != stored[f]
            ],
            "fstat_changed_after": list(FSTAT_FIELDS),
            "hash_recomputed": False,
            "current_hash": None,
        }
    try:
        fstat_after = _fstat_capture(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_SOURCE_CHANGED,
            "reason": "source vanished after rehash: %s" % (exc,),
            "fstat_before": fstat_before,
            "fstat_after": None,
            "fstat_changed_before": [
                f for f in FSTAT_FIELDS if fstat_before[f] != stored[f]
            ],
            "fstat_changed_after": list(FSTAT_FIELDS),
            "hash_recomputed": True,
            "current_hash": current_hash,
        }
    changed_before = [f for f in FSTAT_FIELDS if fstat_before[f] != stored[f]]
    changed_after = [f for f in FSTAT_FIELDS if fstat_after[f] != stored[f]]
    drifted_during_hash = any(
        fstat_after[f] != fstat_before[f] for f in FSTAT_FIELDS
    )
    if current_hash == content_identity and not drifted_during_hash:
        return {
            **base,
            "verdict": "PASS",
            "code": PASS_ARCHIVE_VERIFY,
            "reason": "unconditional rehash matches content_identity",
            "fstat_before": fstat_before,
            "fstat_after": fstat_after,
            "fstat_changed_before": changed_before,
            "fstat_changed_after": changed_after,
            "hash_recomputed": True,
            "current_hash": current_hash,
        }
    if drifted_during_hash:
        reason = "source moved under the hash (fstat drifted mid-verify)"
    else:
        reason = (
            "source bytes differ from content_identity"
            " (fstat changed %s, hash mismatch)" % (changed_after,)
        )
    return {
        **base,
        "verdict": "BLOCK",
        "code": BLOCK_SOURCE_CHANGED,
        "reason": reason,
        "fstat_before": fstat_before,
        "fstat_after": fstat_after,
        "fstat_changed_before": changed_before,
        "fstat_changed_after": changed_after,
        "hash_recomputed": True,
        "current_hash": current_hash,
    }


def find_published_for_source(source_id: str, con) -> list:
    """Walk runs -> norms -> renders -> PUBLISHED publish rows (read-only)."""
    run_rows = list(
        con.execute(
            "SELECT raw_artifact_id FROM processing_runs WHERE source_id = ?",
            (source_id,),
        ).fetchall()
    )
    raw_ids = sorted({r[0] for r in run_rows if r[0] is not None})
    if not raw_ids:
        return []
    marks = ",".join("?" for _ in raw_ids)
    norm_rows = list(
        con.execute(
            "SELECT normalized_artifact_id FROM normalization_revisions"
            " WHERE raw_artifact_id IN (%s)" % (marks,),
            raw_ids,
        ).fetchall()
    )
    norm_ids = sorted({r[0] for r in norm_rows if r[0] is not None})
    if not norm_ids:
        return []
    marks = ",".join("?" for _ in norm_ids)
    render_rows = list(
        con.execute(
            "SELECT render_revision_id FROM render_revisions"
            " WHERE normalized_artifact_id IN (%s)" % (marks,),
            norm_ids,
        ).fetchall()
    )
    rev_ids = sorted({r[0] for r in render_rows if r[0] is not None})
    if not rev_ids:
        return []
    marks = ",".join("?" for _ in rev_ids)
    pub_rows = list(
        con.execute(
            "SELECT publish_record_id, render_revision_id,"
            " canonical_output_path, expected_hash, publish_mode, status,"
            " published_hash, created_at, published_at FROM publish_records"
            " WHERE status = ? AND render_revision_id IN (%s)" % (marks,),
            ["PUBLISHED"] + rev_ids,
        ).fetchall()
    )
    cols = (
        "publish_record_id", "render_revision_id", "canonical_output_path",
        "expected_hash", "publish_mode", "status", "published_hash",
        "created_at", "published_at",
    )
    pubs = []
    for prow in pub_rows:
        if hasattr(prow, "keys"):
            pubs.append({key: prow[key] for key in cols})
        else:
            pubs.append(dict(zip(cols, list(prow))))
    pubs.sort(key=lambda item: item["publish_record_id"])
    return pubs


def check_canonical_unedited(canonical_path: str, published_hash: str) -> dict:
    """Compare decoy canonical bytes with published_hash (user-edit probe)."""
    digest = hashlib.sha256()
    try:
        with open(canonical_path, "rb") as fh:
            while True:
                part = fh.read(8 * 1024 * 1024)
                if not part:
                    break
                digest.update(part)
    except (FileNotFoundError, OSError) as exc:
        return {
            "canonical_path": os.path.abspath(canonical_path),
            "exists": False,
            "edited": None,
            "canonical_hash": None,
            "published_hash": published_hash,
            "reason": "canonical missing: %s" % (exc,),
        }
    canonical_hash = "sha256:" + digest.hexdigest()
    edited = canonical_hash != published_hash
    return {
        "canonical_path": os.path.abspath(canonical_path),
        "exists": True,
        "edited": edited,
        "canonical_hash": canonical_hash,
        "published_hash": published_hash,
        "reason": "canonical matches published_hash"
        if not edited
        else "canonical differs from published_hash (user edit wins)",
    }


def assert_publish_present(source_id: str, con) -> dict:
    """G3 pre-door: PUBLISHED row must exist and its canonical unedited."""
    base = {
        "source_id": source_id,
        "asr_calls": 0,
        "whisper_calls": 0,
        "canonical_writes": 0,
    }
    pubs = find_published_for_source(source_id, con)
    if not pubs:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_NO_PUBLISH,
            "reason": "no PUBLISHED publish_records row reachable"
            " for source %r; refusing archive" % (source_id,),
            "publish_record_id": None,
        }
    missing = []
    edited = []
    for pub in pubs:
        probe = check_canonical_unedited(
            os.path.abspath(pub["canonical_output_path"]), pub["published_hash"]
        )
        if not probe["exists"]:
            missing.append({**pub, "probe": probe})
        elif probe["edited"]:
            edited.append({**pub, "probe": probe})
        else:
            return {
                **base,
                "verdict": "PASS",
                "code": PASS_PUBLISH_PRESENT,
                "reason": "PUBLISHED row present and canonical unedited",
                "publish_record_id": pub["publish_record_id"],
                "publish_row": pub,
                "probe": probe,
            }
    if edited:
        first = edited[0]
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_CANONICAL_EDITED,
            "reason": "canonical edited by user; publish %r kept,"
            " archive refused with zero canonical writes"
            % (first["publish_record_id"],),
            "publish_record_id": first["publish_record_id"],
            "publish_row": first,
            "probe": first["probe"],
        }
    first = missing[0]
    return {
        **base,
        "verdict": "BLOCK",
        "code": BLOCK_CANONICAL_MISSING,
        "reason": "PUBLISHED row %r present but canonical file missing;"
        " refusing archive" % (first["publish_record_id"],),
        "publish_record_id": first["publish_record_id"],
        "publish_row": first,
        "probe": first["probe"],
    }
