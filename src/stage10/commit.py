"""S10-T04c: Archive 成功后 Source 更新 (V1.8 §59/§7 + Case 7).

Implements the commit arm of STAGE10-PLAN S10-T04 only — the single
DB write point of the whole Stage::

    commit_archive_success(con, data_root, source_id, archive_final_path,
                           receipt, level):
      持单实例锁 (无锁即 LockNotHeldError) -> Final 真实性双算
      (DB 值 == 磁盘真实路径 + isfile + hash 一致) -> archive_commits
      新增一行 ARCHIVE_COMMITTED -> sources 只写四列
      (current_path / current_location_type=ARCHIVE / status=ARCHIVED /
      archived_at) -> 列级 diff 自证其余列零写 -> 未来 Reprocess 可从
      current_path 解析 (resolve_current_path).

archive_commits 为本 Stage 唯一允许新增行的表 (state_events 不写,
normalization_revisions / render_revisions / publish_records 零新增,
processing_runs 状态零推进零回滚). 其余列任一被写即回滚 + FAIL.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage10 import verify_archive as _v  # noqa: E402

RECEIPT_STATUS = "ARCHIVE_COMMITTED"
LOCATION_ARCHIVE = "ARCHIVE"
STATUS_ARCHIVED = "ARCHIVED"

SOURCES_WRITABLE = frozenset(
    {"current_path", "current_location_type", "status", "archived_at"}
)

_SOURCES_COLS = (
    "source_id", "source_relative_path", "path_identity_key",
    "content_identity", "logical_source_identity", "current_path",
    "current_location_type", "source_size", "source_mtime_ns",
    "source_device_id", "source_inode_or_file_id", "status",
    "first_seen_at", "last_seen_at", "archived_at",
)


class ArchiveCommitError(ValueError):
    """FAIL: commit refused (fail-closed, DB rolled back)."""


def _utc_now_iso() -> str:
    from stage2 import store as _store  # noqa: PLC0415 (timestamp shape)

    return _store.utc_now_iso()


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def _read_archive_row(con: sqlite3.Connection, archive_commit_id: str):
    return con.execute(
        "SELECT archive_commit_id, source_id, archive_path, status,"
        " created_at, completed_at FROM archive_commits"
        " WHERE archive_commit_id = ?",
        (archive_commit_id,),
    ).fetchone()


def resolve_current_path(source_id: str, con) -> dict:
    """Case 7: 未来 Reprocess 从 current_path 解析真实位置 (只读演示)."""
    row = _v.read_source_row(con, source_id)
    if row is None:
        raise ArchiveCommitError("unknown source_id %r" % (source_id,))
    current = os.path.abspath(row["current_path"])
    exists = os.path.isfile(current)
    current_hash = ("sha256:" + _sha256_file_hex(current)) if exists else None
    return {
        "source_id": source_id,
        "current_path": current,
        "current_location_type": row["current_location_type"],
        "status": row["status"],
        "exists": exists,
        "current_hash": current_hash,
        "hash_match": current_hash == row["content_identity"],
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def commit_archive_success(
    con: sqlite3.Connection,
    data_root: str,
    source_id: str,
    archive_final_path: str,
    receipt: dict,
    level: str,
) -> dict:
    """Persist one ARCHIVE_COMMITTED row + the four Source columns."""
    from stage2 import store as _store  # noqa: PLC0415 (lock + timestamps)

    _store.require_lock(data_root)
    final_abs = os.path.abspath(archive_final_path)
    if level not in ("A", "B"):
        raise ArchiveCommitError("commit only for Level A/B receipts: %r" % (level,))
    if not isinstance(receipt, dict) or receipt.get("status") != RECEIPT_STATUS:
        raise ArchiveCommitError("commit refused: no ARCHIVE_COMMITTED receipt")
    if os.path.abspath(receipt.get("archive_final_path") or "") != final_abs:
        raise ArchiveCommitError("commit refused: receipt final mismatch")
    expected_hash = receipt.get("final_hash")
    if not expected_hash or receipt.get("hash_match") is not True:
        raise ArchiveCommitError("commit refused: receipt hash not matched")
    if not os.path.isfile(final_abs):
        raise ArchiveCommitError("commit refused: final missing at %s" % (final_abs,))
    disk_hash = "sha256:" + _sha256_file_hex(final_abs)
    if disk_hash != expected_hash:
        raise ArchiveCommitError(
            "commit refused: disk hash %s != receipt %s" % (disk_hash, expected_hash)
        )
    before = _v.read_source_row(con, source_id)
    if before is None:
        raise ArchiveCommitError("unknown source_id %r" % (source_id,))
    if before["content_identity"] != expected_hash:
        raise ArchiveCommitError("commit refused: receipt not for this source")
    commit_id = receipt.get("archive_commit_id") or (
        "arc_"
        + hashlib.sha256(
            "|".join((source_id, final_abs, expected_hash)).encode("utf-8")
        ).hexdigest()[:12]
    )
    existing = _read_archive_row(con, commit_id)
    if existing is not None:
        cols = (
            "archive_commit_id", "source_id", "archive_path", "status",
            "created_at", "completed_at",
        )
        found = dict(zip(cols, list(existing)))
        if found["source_id"] == source_id and os.path.abspath(
            found["archive_path"]
        ) == final_abs:
            return {
                "status": RECEIPT_STATUS,
                "archive_commit_id": commit_id,
                "source_id": source_id,
                "idempotent_retry": True,
                "columns_updated": [],
                "asr_calls": 0,
                "whisper_calls": 0,
            }
        raise ArchiveCommitError(
            "archive_commit_id %s owned by another archive" % (commit_id,)
        )
    now = _utc_now_iso()
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "INSERT INTO archive_commits (archive_commit_id, source_id,"
            " archive_path, status, created_at, completed_at)"
            " VALUES (?,?,?,?,?,?)",
            (commit_id, source_id, final_abs, RECEIPT_STATUS, now, now),
        )
        con.execute(
            "UPDATE sources SET current_path = ?, current_location_type = ?,"
            " status = ?, archived_at = ? WHERE source_id = ?",
            (final_abs, LOCATION_ARCHIVE, STATUS_ARCHIVED, now, source_id),
        )
        after_row = con.execute(
            "SELECT %s FROM sources WHERE source_id = ?" % (",".join(_SOURCES_COLS),),
            (source_id,),
        ).fetchone()
        after = dict(zip(_SOURCES_COLS, list(after_row)))
        changed = [key for key in _SOURCES_COLS if after.get(key) != before.get(key)]
        bad = [key for key in changed if key not in SOURCES_WRITABLE]
        if bad:
            raise ArchiveCommitError(
                "sources write beyond the four columns: %r" % (bad,)
            )
        if sorted(changed) != sorted(SOURCES_WRITABLE):
            raise ArchiveCommitError(
                "sources must move exactly the four columns, saw %r" % (changed,)
            )
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    dual = resolve_current_path(source_id, con)
    if dual["current_path"] != final_abs or not dual["hash_match"]:
        raise ArchiveCommitError("post-commit dual proof failed: %r" % (dual,))
    after_db = _v.read_source_row(con, source_id)
    return {
        "status": RECEIPT_STATUS,
        "archive_commit_id": commit_id,
        "source_id": source_id,
        "level": level,
        "archive_final_path": final_abs,
        "columns_updated": sorted(SOURCES_WRITABLE),
        "before_four": {key: before[key] for key in sorted(SOURCES_WRITABLE)},
        "after_four": {key: after_db[key] for key in sorted(SOURCES_WRITABLE)},
        "dual_proof": dual,
        "idempotent_retry": False,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
