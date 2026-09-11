"""S12-T01: read-only status snapshot over the central state.db.

Implements STAGE12-PLAN S12-T01 only:

  collect(data_root, limit=5) returns, on success::

    {"ok": True, "counts_by_state": {...}, "recent_runs": [...],
     "error_count": int, "collected_at": iso8601}

  and on a missing or unreadable DB::

    {"ok": False, "code": str, "message": str, "collected_at": iso8601}

Read path: sqlite3 read-only URI (mode=ro) plus PRAGMA query_only,
addressed via the stage2 central_db_path helper (read-only reuse of a
pure path join; local fallback when stage2 is not importable). This
module opens no read-write handle, creates no file, holds no lock, and
never touches any per-job database.

Aggregate rule (frozen, GROUP BY over real rows, no fixed enum):

  counts_by_state = per-table status GROUP BY counts for sources,
    processing_runs, artifacts, discovery_candidates, archive_commits
    (a key appears only for tables present in the file; at least the
    first two are guaranteed, else a schema-mismatch object returns).
  recent_runs = processing_runs rows ordered by updated_at DESC,
    created_at DESC, capped at LIMIT N, each carrying run_id,
    source_id, status, updated_at (plus created_at).
  error_count = rows in processing_runs with status LIKE 'FAILED%'
    OR status LIKE 'BLOCKED%', plus the same rule over artifacts.

Stdlib only (sqlite3 / os / datetime). Additive-only: no handle to any
write entry point anywhere in this module.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import sys
from urllib.parse import quote as _quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

TABLES = (
    "sources",
    "processing_runs",
    "artifacts",
    "discovery_candidates",
    "archive_commits",
)

CORE_TABLES = ("sources", "processing_runs")

CODE_MISSING = "DB_MISSING"
CODE_UNREADABLE = "DB_UNREADABLE"
CODE_SCHEMA_MISMATCH = "DB_SCHEMA_MISMATCH"

_DEFAULT_LIMIT = 5


class _SchemaMismatch(Exception):
    """Internal: core tables absent from an otherwise readable DB."""


def _utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _db_path(data_root: str) -> str:
    """Locate <data_root>/data/state.db via the stage2 helper when present."""
    data_abs = os.path.abspath(data_root)
    try:
        from stage2.store import central_db_path as _addr  # noqa: E402 read-only reuse

        return _addr(data_abs)
    except Exception:
        return os.path.join(data_abs, "data", "state.db")


def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Open a guaranteed read-only handle (never creates, never alters)."""
    uri = "file:%s?mode=ro" % _quote(os.path.abspath(db_path))
    con = sqlite3.connect(uri, uri=True, timeout=30.0, check_same_thread=False)
    try:
        con.execute("PRAGMA query_only=ON")
        con.row_factory = sqlite3.Row
    except Exception:
        con.close()
        raise
    return con


def _norm_status(value) -> str:
    return "NULL" if value is None else str(value)


def _existing_tables(con: sqlite3.Connection) -> set:
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _collect_open(con: sqlite3.Connection, limit: int) -> dict:
    have = _existing_tables(con)
    missing_core = [t for t in CORE_TABLES if t not in have]
    if missing_core:
        raise _SchemaMismatch(
            "central DB lacks core table(s): %s" % (",".join(missing_core),)
        )
    counts: dict = {}
    for table in TABLES:
        if table not in have:
            continue
        rows = con.execute(
            "SELECT status, COUNT(*) AS c FROM %s GROUP BY status" % table
        ).fetchall()
        counts[table] = {_norm_status(r[0]): int(r[1]) for r in rows}
    rows = con.execute(
        "SELECT run_id, source_id, status, updated_at, created_at"
        " FROM processing_runs ORDER BY updated_at DESC, created_at DESC"
        " LIMIT ?",
        (limit,),
    ).fetchall()
    recent = [
        {
            "run_id": r[0],
            "source_id": r[1],
            "status": r[2],
            "updated_at": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]
    err_runs = con.execute(
        "SELECT COUNT(*) FROM processing_runs"
        " WHERE status LIKE 'FAILED%' OR status LIKE 'BLOCKED%'"
    ).fetchone()[0]
    if "artifacts" in have:
        err_art = con.execute(
            "SELECT COUNT(*) FROM artifacts"
            " WHERE status LIKE 'FAILED%' OR status LIKE 'BLOCKED%'"
        ).fetchone()[0]
    else:
        err_art = 0
    return {
        "ok": True,
        "counts_by_state": counts,
        "recent_runs": recent,
        "error_count": int(err_runs) + int(err_art),
        "collected_at": _utc_now_iso(),
    }


def collect(data_root: str, limit: int = _DEFAULT_LIMIT) -> dict:
    """Read-only aggregate described in the module docstring."""
    data_abs = os.path.abspath(data_root)
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = _DEFAULT_LIMIT
    if n < 0:
        n = 0
    db_path = _db_path(data_abs)
    if not os.path.isfile(db_path):
        return {
            "ok": False,
            "code": CODE_MISSING,
            "message": "central DB file not found: %s" % (db_path,),
            "collected_at": _utc_now_iso(),
        }
    try:
        con = _connect_ro(db_path)
    except Exception as exc:
        return {
            "ok": False,
            "code": CODE_UNREADABLE,
            "message": "cannot open central DB read-only: %s" % (exc,),
            "collected_at": _utc_now_iso(),
        }
    try:
        out = _collect_open(con, n)
    except _SchemaMismatch as exc:
        out = {
            "ok": False,
            "code": CODE_SCHEMA_MISMATCH,
            "message": str(exc),
            "collected_at": _utc_now_iso(),
        }
    except Exception as exc:
        out = {
            "ok": False,
            "code": CODE_UNREADABLE,
            "message": "cannot read central DB: %s" % (exc,),
            "collected_at": _utc_now_iso(),
        }
    finally:
        try:
            con.close()
        except Exception:
            pass
    return out
