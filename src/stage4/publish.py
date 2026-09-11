"""S4-T03: Initial Publish lifecycle (# 12 Initial branch, first use).

Implements STAGE4-PLAN S4-T03 only (V1.8 ``# 12`` / ``# 35`` / ``# 48``)::

    initial_publish(con, job_dir, render_revision_id, output_root,
                    source_relative_path)

* the Output gate runs first; a BLOCK refusal stages nothing.
* the ``# 48`` mapping fixes the ``canonical_output_path``.
* a missing canonical travels ``PENDING -> PUBLISHING -> PUBLISHED``
  through ``publish_commit`` (``publish_mode=INITIAL``; every hop
  lands in ``state_events``; ``published_at`` is set only with
  ``PUBLISHED``).
* a present canonical never travels this module: it is handed to
  ``conflict.publish_or_block`` (the S4-T04 no-cover branch) with
  zero Output-root writes on this path.
* on success exactly one Processing Run row gains its
  ``initial_publish_record_id`` (plus the timestamp column); every
  other column keeps its value and the run status is untouched
  (Stage4 neither advances nor retreats any Run).

This module holds no second branch: when the canonical side exists
there is no path here that stages bytes. That absence is structural
— the exists-branch delegates before any staging call.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3

from . import publish_commit as _pc
from . import volume_probe as _vp


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def _find_run_for_render(con: sqlite3.Connection,
                         render_revision_id: str) -> dict:
    """Walk render_rev -> normalized -> raw -> the owning run row."""
    rev = con.execute(
        "SELECT normalized_artifact_id FROM render_revisions"
        " WHERE render_revision_id = ?",
        (render_revision_id,),
    ).fetchone()
    if rev is None:
        raise _pc.PublishError("unknown render_revision_id %r" % (
            render_revision_id,))
    norm_id = rev[0]
    nrev = con.execute(
        "SELECT raw_artifact_id FROM normalization_revisions"
        " WHERE normalized_artifact_id = ?",
        (norm_id,),
    ).fetchone()
    if nrev is None:
        raise _pc.PublishError("no normalization revision for %r" % (
            norm_id,))
    raw_id = nrev[0]
    run = con.execute(
        "SELECT * FROM processing_runs WHERE raw_artifact_id = ?"
        " ORDER BY created_at LIMIT 1",
        (raw_id,),
    ).fetchone()
    if run is None:
        raise _pc.PublishError(
            "no processing run owns raw %r; refusing backfill-blind"
            " publish" % (raw_id,))
    return dict(run)


def _backfill_run(con: sqlite3.Connection, run_id: str,
                  publish_record_id: str) -> dict:
    """Write the single allowed column pair; prove the rest is intact."""
    from stage2 import store as _store  # noqa: PLC0415 (timestamp helper)

    before = con.execute(
        "SELECT * FROM processing_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if before is None:
        raise _pc.PublishError("run vanished before backfill: %r" % (run_id,))
    before_map = dict(before)
    con.execute(
        "UPDATE processing_runs SET initial_publish_record_id = ?,"
        " updated_at = ? WHERE run_id = ?",
        (publish_record_id, _store.utc_now_iso(), run_id),
    )
    con.commit()
    after = con.execute(
        "SELECT * FROM processing_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    after_map = dict(after)
    drifted = [
        key for key in after_map
        if key not in ("initial_publish_record_id", "updated_at")
        and after_map.get(key) != before_map.get(key)
    ]
    if drifted:
        raise _pc.PublishError(
            "run backfill drifted beyond the allowed columns: %r" % (
                drifted,))
    return {
        "run_id": run_id,
        "column": "initial_publish_record_id",
        "before": before_map.get("initial_publish_record_id"),
        "after": after_map.get("initial_publish_record_id"),
        "run_status": after_map.get("status"),
    }


def _run_initial_publish(con: sqlite3.Connection, job_dir: str,
                         render_revision_id: str, output_root: str,
                         canonical_abs: str, expected_hash: str,
                         rendered_final_path: str,
                         on_tmp_ready=None) -> dict:
    """The missing-canonical Initial flow (no exists-branch inside)."""
    publish_record_id = _pc.publish_record_id_for(
        render_revision_id, canonical_abs, expected_hash)
    _pc.prepare_publish(con, rendered_final_path, canonical_abs,
                        publish_record_id,
                        render_revision_id=render_revision_id)
    committed = _pc.commit_publish(con, job_dir, publish_record_id,
                                   on_tmp_ready=on_tmp_ready)
    run = _find_run_for_render(con, render_revision_id)
    backfill = _backfill_run(con, run["run_id"], publish_record_id)
    committed.update({
        "run_backfill": backfill,
        "canonical_writes": 0,
    })
    return committed


def _refuse_gated(con: sqlite3.Connection, render_revision_id: str,
                  canonical_abs: str, exc: Exception) -> None:
    """Turn a gate refusal into a BLOCK verdict row, then raise."""
    try:
        _, _, rendered_bytes = _pc._resolve_rendered(con,
                                                      render_revision_id)
    except _pc.PublishError:
        raise exc
    expected_hash = "sha256:" + _sha256_hex(rendered_bytes)
    verdict = _pc.record_verdict_row(con, render_revision_id,
                                     canonical_abs, expected_hash,
                                     exc.code, str(exc))
    raise _pc.PublishBlocked(
        str(exc), exc.code, canonical_output_path=canonical_abs,
        publish_record_id=verdict["publish_record_id"])


def initial_publish(con: sqlite3.Connection, job_dir: str,
                    render_revision_id: str, output_root: str,
                    source_relative_path: str,
                    on_tmp_ready=None) -> dict:
    """Publish one Render Revision to its Initial Canonical file."""
    job_dir = os.path.abspath(job_dir)
    canonical_abs = _pc.canonical_path_for(output_root,
                                           source_relative_path)
    try:
        _vp.gate_output_root(output_root)
    except (_vp.BlockedUnsupportedOutputFilesystem,
            _vp.BlockedUnsupportedRoot) as exc:
        _refuse_gated(con, render_revision_id, canonical_abs, exc)
    rendered_artifact_id, rendered_final_path, rendered_bytes = \
        _pc._resolve_rendered(con, render_revision_id)
    _ = rendered_artifact_id
    expected_hash = "sha256:" + _sha256_hex(rendered_bytes)

    if os.path.isfile(canonical_abs):
        from . import conflict as _cf  # noqa: PLC0415 (exists-branch owner)

        return _cf.publish_or_block(
            con, job_dir, render_revision_id, output_root,
            source_relative_path, on_tmp_ready=on_tmp_ready)

    return _run_initial_publish(con, job_dir, render_revision_id,
                                output_root, canonical_abs, expected_hash,
                                rendered_final_path,
                                on_tmp_ready=on_tmp_ready)
