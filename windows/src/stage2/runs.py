"""S2-T04: AUTO Run identity + Partial UNIQUE + conflict-safe creation.

Implements STAGE2-PLAN S2-T04 only:
  - auto_run_identity = source_id + asr_profile_hash (§13; joined with '|'
    as an unambiguous separator, recorded in the row).
  - The §15 Partial UNIQUE lands verbatim in store.DDL
    (ux_auto_processing_run); creation here is a single atomic
    INSERT ... ON CONFLICT(source_id, asr_profile_hash)
    WHERE creation_mode='AUTO' DO NOTHING — never SELECT-then-INSERT
    (the SELECT below runs AFTER the atomic INSERT only to return the row).
  - asr_profile_hash is an opaque frozen hash string passed through from
    Stage0/Stage1: never parsed, never executed, zero model invocations.
  - creation_mode='AUTO' is persisted; MANUAL_REPROCESS is only a model
    allowlist value (CHECK constraint) with no implemented semantics —
    create_manual_reprocess() raises NotImplementedError (reserved).
  - New runs start at QUEUED (§9 head). Transcription progression states are
    never written here (STOP EXPANSION, R6).

STOP EXPANSION: no transcription-engine invocations (count == 0), no
Stage3+ writes.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import store  # noqa: E402

STATUS_QUEUED = "QUEUED"
STATUS_FAILED_RETRYABLE = "FAILED_RETRYABLE"
STATUS_NO_SPEECH = "NO_SPEECH_DETECTED"

AUTO = "AUTO"


def _run_id_for(source_id: str, asr_profile_hash: str) -> str:
    return "run_" + hashlib.sha256(
        (source_id + "|" + asr_profile_hash).encode("utf-8")
    ).hexdigest()[:16]


def _retry_locked(fn, *args, **kwargs):
    last = None
    for _ in range(80):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last = exc
            time.sleep(0.05)
    raise last  # type: ignore[misc]


def get_or_create_auto_run(
    source_id: str,
    asr_profile_hash: str,
    data_root: str,
    _con: sqlite3.Connection | None = None,
) -> dict:
    """Conflict-safe ensure of the AUTO run for (source, profile hash).

    Returns the row dict; repeated calls with the same pair return the same
    run_id, a different hash mints a second run (§28 profile-change
    semantics). Raises ValueError for unknown source (FK).
    """
    store.require_lock(data_root)
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")

    def _once(con: sqlite3.Connection) -> dict:
        run_id = _run_id_for(source_id, asr_profile_hash)
        now = store.utc_now_iso()
        # Conflict-safe single-statement creation: no SELECT-then-INSERT.
        try:
            con.execute(
                "INSERT INTO processing_runs (run_id, job_id, source_id,"
                " creation_mode, auto_run_identity, asr_profile_hash, engine,"
                " engine_version, model, model_revision, language_strategy,"
                " raw_artifact_id, initial_normalization_revision_id,"
                " initial_render_revision_id, initial_publish_record_id,"
                " status, retry_count, created_at, updated_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(source_id, asr_profile_hash)"
                " WHERE creation_mode='AUTO' DO NOTHING",
                (
                    run_id, None, source_id, AUTO,
                    source_id + "|" + asr_profile_hash, asr_profile_hash,
                    None, None, None, None, None, None, None, None, None,
                    STATUS_QUEUED, 0, now, now, None,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("unknown source_id: %r (%s)" % (source_id, exc))
        row = con.execute(
            "SELECT * FROM processing_runs WHERE source_id=?"
            " AND asr_profile_hash=? AND creation_mode='AUTO'",
            (source_id, asr_profile_hash),
        ).fetchone()
        if row is None:  # pragma: no cover — defensive; UNIQUE makes this unreachable
            raise AssertionError("AUTO run vanished right after conflict-safe insert")
        if _con is None:
            con.commit()
        return dict(row)

    if _con is not None:
        return _once(_con)

    def _own():
        con = store.open_db(data_root)
        try:
            return _once(con)
        finally:
            con.close()

    return _retry_locked(_own)


def create_manual_reprocess(*args, **kwargs):
    """Reserved model value only — semantics NOT implemented (§14, T04)."""
    raise NotImplementedError(
        "MANUAL_REPROCESS is a reserved creation_mode value in Stage2; "
        "only AUTO creation is implemented"
    )


def get_run(run_id: str, data_root: str) -> dict:
    store.require_lock(data_root)
    con = store.open_db(data_root)
    try:
        row = con.execute(
            "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise KeyError("run not found: %r" % (run_id,))
    return dict(row)


def mark_failed_retryable(run_id: str, data_root: str, reason: str = "setup") -> dict:
    """Test/setup transition QUEUED -> FAILED_RETRYABLE (§17 state only)."""
    store.require_lock(data_root)

    def _once():
        con = store.open_db(data_root)
        try:
            row = con.execute(
                "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError("run not found: %r" % (run_id,))
            if row["status"] != STATUS_QUEUED:
                raise ValueError("only QUEUED can be marked retryable (is %r)" % (row["status"],))
            con.execute(
                "UPDATE processing_runs SET status='FAILED_RETRYABLE',"
                " updated_at=? WHERE run_id=?", (store.utc_now_iso(), run_id),
            )
            store.record_event(con, "run", run_id, STATUS_QUEUED, STATUS_FAILED_RETRYABLE, reason)
            con.commit()
            return get_run(run_id, data_root)
        finally:
            con.close()

    return _retry_locked(_once)


def mark_no_speech(run_id: str, data_root: str, reason: str = "setup") -> dict:
    """Test/setup transition QUEUED -> NO_SPEECH_DETECTED (§18 state only)."""
    store.require_lock(data_root)

    def _once():
        con = store.open_db(data_root)
        try:
            row = con.execute(
                "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError("run not found: %r" % (run_id,))
            if row["status"] != STATUS_QUEUED:
                raise ValueError("only QUEUED can be marked no-speech (is %r)" % (row["status"],))
            con.execute(
                "UPDATE processing_runs SET status='NO_SPEECH_DETECTED',"
                " updated_at=? WHERE run_id=?", (store.utc_now_iso(), run_id),
            )
            store.record_event(con, "run", run_id, STATUS_QUEUED, STATUS_NO_SPEECH, reason)
            con.commit()
            return get_run(run_id, data_root)
        finally:
            con.close()

    return _retry_locked(_once)


def reconcile_source(
    source_id: str, asr_profile_hash: str, data_root: str, reason: str = "reconciliation"
) -> dict:
    """T05 assembly: resolve the AUTO run for (source, hash), then converge.

    Two-layer dedup (§19): the Candidate layer folds duplicate discoveries
    (MERGED, candidate.py) and this Run layer returns the existing run —
    Triple Race therefore ends at Source=1 / AUTO Run=1 (Case 3), ten
    NO_SPEECH reconciliations stay at Run=1 (Case 2), and a FAILED_RETRYABLE
    run is retried in place (§17).
    """
    store.require_lock(data_root)
    existing = get_or_create_auto_run(source_id, asr_profile_hash, data_root)
    return reconcile_run(existing["run_id"], data_root, reason)


def reconcile_run(run_id: str, data_root: str, reason: str = "reconciliation") -> dict:
    """Reconciliation convergence (§17/§18, T05):

    - FAILED_RETRYABLE -> same run_id, retry_count+1 (no new run), stays
      FAILED_RETRYABLE (Stage2 never executes; later Stages consume it).
    - NO_SPEECH_DETECTED -> same terminal row back, nothing new (§18).
    - QUEUED -> returned unchanged.
    """
    store.require_lock(data_root)

    def _once():
        con = store.open_db(data_root)
        try:
            row = con.execute(
                "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError("run not found: %r" % (run_id,))
            status = row["status"]
            if status == STATUS_FAILED_RETRYABLE:
                con.execute(
                    "UPDATE processing_runs SET retry_count=retry_count+1,"
                    " updated_at=? WHERE run_id=?", (store.utc_now_iso(), run_id),
                )
                store.record_event(
                    con, "run", run_id, STATUS_FAILED_RETRYABLE,
                    STATUS_FAILED_RETRYABLE,
                    "reconcile retry original run (%s)" % (reason,),
                )
                con.commit()
            elif status in (STATUS_NO_SPEECH, STATUS_QUEUED):
                store.record_event(con, "run", run_id, status, status,
                                   "reconcile returns existing (%s)" % (reason,))
                con.commit()
            else:  # pragma: no cover — guarded by assert_no_transcription_states
                raise ValueError("reconcile refuses transcription-stage status %r" % (status,))
            out = con.execute(
                "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            return dict(out)
        finally:
            con.close()

    return _retry_locked(_once)
