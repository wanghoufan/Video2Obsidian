"""S2-T01: central SQLite + lock-gated access skeleton.

Implements STAGE2-PLAN S2-T01 only:
  - central DB at <data_root>/data/state.db (WAL, PRAGMA foreign_keys=ON)
  - 9 tables: discovery_candidates / sources / processing_runs / artifacts /
    state_events (full function) + normalization_revisions / render_revisions /
    publish_records / archive_commits (DDL schema-only, zero writes — any row
    in those four tables is FAIL, enforced by assert_stage3_tables_empty()).
  - ux_auto_processing_run Partial UNIQUE (§15 verbatim) + active-candidate
    provisional Partial UNIQUE (§20, R1 verbatim scope).
  - open_db() lock assertion: any Stage2 write without a held Single Instance
    lock (see stage2.instance) raises LockNotHeldError (FAIL gate, P0-1/P0-7).

STOP EXPANSION: no Watch/Scan/Reconcile, no transcription-engine invocation
(count == 0 in this module and in the whole Stage2 chain), no Stage3+
semantics. Does not touch src/stage1/ or any per-job job.sqlite (read-only
reuse only, via imports in sibling modules).
"""

from __future__ import annotations

import datetime
import os
import sqlite3
import uuid

STATE_DB_RELPATH = os.path.join("data", "state.db")
LOCK_RELPATH = os.path.join("data", ".lock")

# Stage3+ tables: schema-only in Stage2. Any row == FAIL (see P0-1, R6).
STAGE3_TABLES = (
    "normalization_revisions",
    "render_revisions",
    "publish_records",
    "archive_commits",
)

ALL_TABLES = (
    "discovery_candidates",
    "sources",
    "processing_runs",
    "artifacts",
    "state_events",
) + STAGE3_TABLES

# Stage2 run statuses only. Transcription/publish/archive progression states
# (TRANSCRIBING / COMMITTING_* / NORMALIZING_* / RENDERING_* / ARCHIVING /
# COMPLETED ...) belong to later Stages — see assert_no_transcription_states.
ALLOWED_RUN_STATUSES = frozenset(
    {"QUEUED", "FAILED_RETRYABLE", "NO_SPEECH_DETECTED"}
)

# Stage2 candidate statuses (§5). Terminal states never occupy the
# provisional Partial UNIQUE (R1).
ACTIVE_CANDIDATE_STATUSES = (
    "DISCOVERED",
    "WAITING_FOR_STABLE_FILE",
    "IDENTIFYING_SOURCE",
)
TERMINAL_CANDIDATE_STATUSES = ("PROMOTED", "MERGED", "REJECTED", "SOURCE_MISSING")

ALLOWED_CREATION_MODES = ("AUTO", "MANUAL_REPROCESS")


class LockNotHeldError(RuntimeError):
    """Raised when a Stage2 DB access happens without the instance lock."""


class Stage3WriteBlocked(RuntimeError):
    """Raised when anything tries to write a Stage3+ schema-only table."""


# Process-local registry of data_roots whose fcntl lock is held by us.
# instance.acquire() marks, instance.release() unmarks. Same-process threads
# share the entry (flock is held once per process).
_HELD_LOCKS = set()


def mark_held(data_root: str) -> None:
    _HELD_LOCKS.add(os.path.abspath(data_root))


def mark_released(data_root: str) -> None:
    _HELD_LOCKS.discard(os.path.abspath(data_root))


def is_held(data_root: str) -> bool:
    return os.path.abspath(data_root) in _HELD_LOCKS


def require_lock(data_root: str) -> None:
    if not is_held(data_root):
        raise LockNotHeldError(
            "Stage2 DB write without Single Instance lock held for "
            "%r (acquire via stage2.instance.acquire() first)" % (data_root,)
        )


def central_db_path(data_root: str) -> str:
    return os.path.join(os.path.abspath(data_root), STATE_DB_RELPATH)


def lock_path(data_root: str) -> str:
    return os.path.join(os.path.abspath(data_root), LOCK_RELPATH)


def utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


DDL = """
CREATE TABLE IF NOT EXISTS discovery_candidates (
  candidate_id TEXT PRIMARY KEY,
  path_identity_key TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  device INTEGER,
  inode INTEGER,
  status TEXT NOT NULL,
  content_identity TEXT,
  source_id TEXT REFERENCES sources(source_id),
  merged_into TEXT,
  observed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  source_relative_path TEXT,
  path_identity_key TEXT NOT NULL,
  content_identity TEXT NOT NULL,
  logical_source_identity TEXT NOT NULL UNIQUE,
  current_path TEXT NOT NULL,
  current_location_type TEXT NOT NULL,
  source_size INTEGER NOT NULL,
  source_mtime_ns INTEGER NOT NULL,
  source_device_id INTEGER,
  source_inode_or_file_id INTEGER,
  status TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  archived_at TEXT
);
CREATE TABLE IF NOT EXISTS processing_runs (
  run_id TEXT PRIMARY KEY,
  job_id TEXT,
  source_id TEXT NOT NULL REFERENCES sources(source_id),
  creation_mode TEXT NOT NULL CHECK (creation_mode IN ('AUTO', 'MANUAL_REPROCESS')),
  auto_run_identity TEXT NOT NULL,
  asr_profile_hash TEXT NOT NULL,
  engine TEXT,
  engine_version TEXT,
  model TEXT,
  model_revision TEXT,
  language_strategy TEXT,
  raw_artifact_id TEXT,
  initial_normalization_revision_id TEXT,
  initial_render_revision_id TEXT,
  initial_publish_record_id TEXT,
  status TEXT NOT NULL,
  retry_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES sources(source_id),
  run_id TEXT REFERENCES processing_runs(run_id),
  artifact_type TEXT NOT NULL,
  expected_hash TEXT,
  status TEXT NOT NULL,
  path TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS state_events (
  event_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  reason TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS normalization_revisions (
  normalization_revision_id TEXT PRIMARY KEY,
  raw_artifact_id TEXT,
  normalization_profile_hash TEXT,
  normalized_artifact_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS render_revisions (
  render_revision_id TEXT PRIMARY KEY,
  normalized_artifact_id TEXT,
  render_profile_hash TEXT,
  rendered_artifact_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS publish_records (
  publish_record_id TEXT PRIMARY KEY,
  render_revision_id TEXT,
  canonical_output_path TEXT,
  expected_hash TEXT,
  publish_mode TEXT,
  status TEXT NOT NULL,
  published_hash TEXT,
  created_at TEXT NOT NULL,
  published_at TEXT
);
CREATE TABLE IF NOT EXISTS archive_commits (
  archive_commit_id TEXT PRIMARY KEY,
  source_id TEXT REFERENCES sources(source_id),
  archive_path TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_auto_processing_run ON processing_runs(source_id, asr_profile_hash) WHERE creation_mode='AUTO';
CREATE UNIQUE INDEX IF NOT EXISTS ux_candidate_provisional_active ON discovery_candidates(path_identity_key, size, mtime_ns) WHERE status IN ('DISCOVERED','WAITING_FOR_STABLE_FILE','IDENTIFYING_SOURCE');
CREATE UNIQUE INDEX IF NOT EXISTS ux_sources_logical ON sources(logical_source_identity);
"""


def open_db(data_root: str, require_lock_held: bool = True) -> sqlite3.Connection:
    """Open the central DB. Refuses when the instance lock is not held.

    require_lock_held=True is the default (P0-1/P0-7 FAIL gate). Pass False
    only for lock-free diagnostics that never write.
    """
    if require_lock_held:
        require_lock(data_root)
    db_path = central_db_path(data_root)
    if not os.path.isfile(db_path):
        raise FileNotFoundError("central DB not initialized: %s" % (db_path,))
    con = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        con.row_factory = sqlite3.Row
    except Exception:
        con.close()
        raise
    return con


def init_db(data_root: str) -> str:
    """Create the central DB skeleton. Lock must be held (P0-1). Idempotent."""
    require_lock(data_root)
    data_dir = os.path.join(os.path.abspath(data_root), "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = central_db_path(data_root)
    con = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(DDL)
        con.commit()
    finally:
        con.close()
    return db_path


def record_event(
    con: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    from_status: str | None,
    to_status: str | None,
    reason: str | None = None,
) -> None:
    con.execute(
        "INSERT INTO state_events "
        "(event_id, entity_type, entity_id, from_status, to_status, reason, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (new_id("evt"), entity_type, entity_id, from_status, to_status, reason, utc_now_iso()),
    )


def table_counts(con: sqlite3.Connection) -> dict:
    return {
        t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ALL_TABLES
    }


def assert_stage3_tables_empty(con: sqlite3.Connection) -> dict:
    """Stage3+ schema-only gate: any row in the four tables is FAIL (P0-1, R6)."""
    counts = {
        t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        for t in STAGE3_TABLES
    }
    nonzero = {t: c for t, c in counts.items() if c != 0}
    if nonzero:
        raise AssertionError("Stage3+ table not empty (STOP EXPANSION): %r" % (nonzero,))
    return counts


def assert_no_transcription_states(con: sqlite3.Connection) -> dict:
    """Run-state gate: only QUEUED / FAILED_RETRYABLE / NO_SPEECH_DETECTED.

    Transcription/publish/archive progression belongs to later Stages; any
    such status here is FAIL (R6). Returns observed status histogram.
    """
    rows = con.execute("SELECT status, COUNT(*) FROM processing_runs GROUP BY status").fetchall()
    hist = {r[0]: r[1] for r in rows}
    bad = {s: c for s, c in hist.items() if s not in ALLOWED_RUN_STATUSES}
    if bad:
        raise AssertionError("Run in transcription-stage status (STOP EXPANSION): %r" % (bad,))
    return hist


def count_sources(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]


def count_auto_runs(con: sqlite3.Connection) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM processing_runs WHERE creation_mode='AUTO'"
    ).fetchone()[0]
