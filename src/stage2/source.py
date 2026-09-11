"""S2-T03: Logical Source Exactly Once + promotion.

Implements STAGE2-PLAN S2-T03 only:
  - Strong SHA256 reused read-only from stage1.sha256_file (no copy, no
    rewrite of src/stage1/).
  - content_identity = 'sha256:' + hex; logical_source_identity =
    path_identity_key + '|' + content_identity (§22).
  - UPSERT into sources (INSERT ... ON CONFLICT(logical_source_identity)
    DO UPDATE ...); conflict returns the existing row, so
    Duplicate Logical Source Count stays 0 (§3.2).
  - path_identity_key keeps the abspath verbatim: full Unicode / case /
    spaces / '丨' / brackets, no NFC, no casefold, no encode/slugify (§23).
    The full Unicode/Case fault matrix stays in Stage6.

STOP EXPANSION: no transcription-engine invocations (count == 0), no runs
creation (runs.py owns that), no Stage3+ writes.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage1 import sha256_file  # noqa: E402  (read-only reuse, S2加法约束)

from stage2 import store  # noqa: E402

CURRENT_LOCATION_TYPE = "DISCOVERED_PATH"
STATUS_ACTIVE = "ACTIVE"


def _source_id_for(logical_identity: str) -> str:
    return "src_" + hashlib.sha256(logical_identity.encode("utf-8")).hexdigest()[:16]


def upsert_source(
    con: sqlite3.Connection,
    path_identity_key: str,
    size: int,
    mtime_ns: int,
    device: int | None,
    inode: int | None,
    content_hex: str,
    current_path: str | None = None,
) -> tuple[dict, bool]:
    """Atomic UPSERT a Logical Source. Returns (row, is_new).

    Conflict-safe: INSERT first, ON CONFLICT returns the existing row.
    No SELECT-then-INSERT anywhere on this path.
    """
    content_identity = "sha256:" + content_hex
    logical_identity = path_identity_key + "|" + content_identity
    source_id = _source_id_for(logical_identity)
    now = store.utc_now_iso()
    cur = con.execute(
        "INSERT INTO sources (source_id, source_relative_path, path_identity_key,"
        " content_identity, logical_source_identity, current_path,"
        " current_location_type, source_size, source_mtime_ns, source_device_id,"
        " source_inode_or_file_id, status, first_seen_at, last_seen_at, archived_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(logical_source_identity) DO UPDATE SET"
        " last_seen_at=excluded.last_seen_at",
        (
            source_id,
            None,
            path_identity_key,
            content_identity,
            logical_identity,
            current_path or path_identity_key,
            CURRENT_LOCATION_TYPE,
            size,
            mtime_ns,
            device,
            inode,
            STATUS_ACTIVE,
            now,
            now,
            None,
        ),
    )
    is_new = cur.rowcount == 1
    row = con.execute(
        "SELECT * FROM sources WHERE logical_source_identity=?", (logical_identity,)
    ).fetchone()
    return dict(row), is_new


def _with_db_retry(fn, *args, **kwargs):
    last = None
    for _ in range(60):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last = exc
            time.sleep(0.05)
    raise last  # type: ignore[misc]


def promote_candidate(candidate_id: str, data_root: str) -> tuple[dict, dict, bool]:
    """Promote an IDENTIFYING_SOURCE candidate via Strong Hash.

    Returns (candidate_row, source_row, source_is_new). Raises on wrong
    candidate state or missing file (caller maps missing file to
    SOURCE_MISSING).
    """
    store.require_lock(data_root)

    def _once():
        con = store.open_db(data_root)
        try:
            cand = con.execute(
                "SELECT * FROM discovery_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if cand is None:
                raise KeyError("candidate not found: %r" % (candidate_id,))
            if cand["status"] != "IDENTIFYING_SOURCE":
                raise ValueError(
                    "candidate %r not IDENTIFYING_SOURCE (is %r)"
                    % (candidate_id, cand["status"])
                )
            path = cand["path_identity_key"]
            st = os.stat(path)
            content_hex = sha256_file(path)  # read-only Strong Hash (§21)
            source, is_new = upsert_source(
                con,
                cand["path_identity_key"],
                st.st_size,
                st.st_mtime_ns,
                st.st_dev,
                st.st_ino,
                content_hex,
            )
            now = store.utc_now_iso()
            con.execute(
                "UPDATE discovery_candidates SET status='PROMOTED',"
                " content_identity=?, source_id=?, updated_at=? WHERE candidate_id=?",
                (source["content_identity"], source["source_id"], now, candidate_id),
            )
            store.record_event(
                con, "candidate", candidate_id, "IDENTIFYING_SOURCE", "PROMOTED",
                "strong-hash promotion -> %s (new=%s)" % (source["source_id"], is_new),
            )
            con.commit()
            cand2 = con.execute(
                "SELECT * FROM discovery_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return dict(cand2), source, is_new
        finally:
            con.close()

    return _with_db_retry(_once)
