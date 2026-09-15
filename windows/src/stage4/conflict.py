"""S4-T04: Subsequent no-cover policy + Output Conflict branches.

Implements STAGE4-PLAN S4-T04 only (V1.8 ``# 50`` / ``# 51`` / ``# 53``
+ ``# 52`` Ownership)::

    publish_or_block(con, job_dir, render_revision_id, output_root,
                     source_relative_path, publish_record_id=None)

* canonical missing -> the S4-T03 Initial flow (first bytes land).
* canonical present + Ownership + Hash prove the Final side is the
  current unfinished Initial publish (the open ``PUBLISHING`` row is
  ours and ``expected_hash == sha256(final)``) -> Recovery Forward
  through ``recover_publish`` (receipt restored, row ``PUBLISHED``,
  no tmp rebuild).
* canonical present + same bytes but no open row of ours ->
  ``BLOCKED_OUTPUT_EXISTS`` (a matching twin is still never adopted
  silently).
* canonical present + differing or unowned bytes ->
  ``BLOCKED_OUTPUT_CONFLICT``.
* every BLOCK branch leaves the canonical bytes bit-identical
  (``canonical_sha_before == canonical_sha_after``,
  ``canonical_writes == 0``).

# 51 verdict-row rule (documented choice): a BLOCK attempt lands
exactly one ``publish_records`` verdict row carrying the BLOCK
status — S4-T06 accepts against this same rule, and the Initial
race collision inside ``commit_publish`` updates the open row in
place instead of minting a second one. ``# 52`` Ownership (the five
items ``render_revision_id`` / ``rendered_artifact_id`` /
``publish_record_id`` / ``expected_output_hash`` / ``published_hash``
in SQLite plus the Manifest receipt) exists for crash recovery and
conflict diagnosis only; it never authorizes a Subsequent cover.

Whether or not the store can prove an old Canonical came from this
tool, a present canonical is never staged over (``# 51``: the user
may have hand-edited it).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3

from . import publish_commit as _pc
from . import volume_probe as _vp


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _open_publishing_rows(con: sqlite3.Connection,
                         canonical_abs: str) -> list:
    return list(con.execute(
        "SELECT publish_record_id, render_revision_id, canonical_output_path,"
        " expected_hash, publish_mode, status, published_hash, created_at,"
        " published_at FROM publish_records"
        " WHERE canonical_output_path = ? AND status = ?"
        " ORDER BY created_at",
        (canonical_abs, _pc.ST_PUBLISHING),
    ).fetchall())


def _verdict_row(con: sqlite3.Connection, render_revision_id: str,
                 canonical_abs: str, expected_hash: str,
                 status: str) -> dict:
    return _pc.record_verdict_row(con, render_revision_id, canonical_abs,
                                  expected_hash, status,
                                  "subsequent publish met an owned final side")


def publish_or_block(con: sqlite3.Connection, job_dir: str,
                     render_revision_id: str, output_root: str,
                     source_relative_path: str,
                     publish_record_id: str | None = None,
                     on_tmp_ready=None) -> dict:
    """Publish when the Final side is free; BLOCK when it is owned."""
    job_dir = os.path.abspath(job_dir)
    canonical_abs = _pc.canonical_path_for(output_root,
                                           source_relative_path)
    try:
        _vp.gate_output_root(output_root)
    except (_vp.BlockedUnsupportedOutputFilesystem,
            _vp.BlockedUnsupportedRoot) as exc:
        from . import publish as _pub_gate  # noqa: PLC0415 (verdict writer)

        _pub_gate._refuse_gated(con, render_revision_id, canonical_abs,
                                exc)
    _, _, rendered_bytes = _pc._resolve_rendered(con, render_revision_id)
    expected_hash = "sha256:" + _sha256_hex(rendered_bytes)

    if os.path.isfile(canonical_abs):
        with open(canonical_abs, "rb") as fh:
            present = fh.read()
        sha_before = "sha256:" + _sha256_hex(present)

        candidates = _open_publishing_rows(con, canonical_abs)
        if publish_record_id is not None:
            claimed = _pc._read_publish_row(con, publish_record_id)
            if claimed is not None and _pc._row_get(claimed, "status") \
                    == _pc.ST_PUBLISHING:
                candidates = [claimed] + [
                    row for row in candidates
                    if _pc._row_get(row, "publish_record_id")
                    != publish_record_id
                ]
        for row in candidates:
            owned = (
                publish_record_id is not None
                and _pc._row_get(row, "publish_record_id")
                == publish_record_id
            ) or (
                _pc._row_get(row, "render_revision_id")
                == render_revision_id
            )
            if owned and _pc._row_get(row, "expected_hash") == sha_before:
                recovered = _pc.recover_publish(
                    con, job_dir, _pc._row_get(row, "publish_record_id"))
                with open(canonical_abs, "rb") as fh:
                    sha_after = "sha256:" + _sha256_hex(fh.read())
                recovered.update({
                    "canonical_sha_before": sha_before,
                    "canonical_sha_after": sha_after,
                    "canonical_writes": 0,
                })
                return recovered

        status = _pc.ST_BLOCKED_EXISTS \
            if sha_before == expected_hash else _pc.ST_BLOCKED_CONFLICT
        verdict = _verdict_row(con, render_revision_id, canonical_abs,
                               expected_hash, status)
        with open(canonical_abs, "rb") as fh:
            sha_after = "sha256:" + _sha256_hex(fh.read())
        return {
            "publish_record_id": verdict["publish_record_id"],
            "render_revision_id": render_revision_id,
            "canonical_output_path": canonical_abs,
            "expected_output_hash": expected_hash,
            "canonical_sha_before": sha_before,
            "canonical_sha_after": sha_after,
            "canonical_bytes_unchanged": sha_before == sha_after,
            "status": verdict["status"],
            "idempotent_retry": verdict["idempotent_retry"],
            "repair_forward": False,
            "canonical_writes": 0,
            "asr_calls": 0,
            "whisper_calls": 0,
        }

    from . import publish as _pub  # noqa: PLC0415 (absent-branch owner)

    rendered_artifact_id, rendered_final_path, _ = _pc._resolve_rendered(
        con, render_revision_id)
    _ = rendered_artifact_id
    return _pub._run_initial_publish(
        con, job_dir, render_revision_id, output_root, canonical_abs,
        expected_hash, rendered_final_path, on_tmp_ready=on_tmp_ready)
