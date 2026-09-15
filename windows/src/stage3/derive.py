"""S3-T04: derivation assembly — Case 4 / Case 5 paths + engine guard.

Implements STAGE3-PLAN S3-T04 only (V1.8 ``# 3.9`` / Case 4 / Case 5 /
Case 6):

* ``derive_on_correction_change``: a new Normalization profile reuses
  the same ``raw_artifact_id`` and mints a new Normalization Revision
  (new Normalized artifact) plus a downstream new Render Revision
  (new Rendered artifact). Never re-invokes transcription.
* ``derive_on_formatter_change``: a new Render profile reuses the same
  ``normalized_artifact_id`` (zero new Normalization Revisions) and
  mints only a new Render Revision.
* Case 6 falls out by construction: neither path reads the
  Processing Run row for mutation nor writes it — the run keeps
  whatever status it had (COMPLETED stays COMPLETED) while each
  revision maintains only its own status.

Engine guard: this module — like every module in this package —
never imports the Stage1 transcription entry point. The audit is
mechanical: grepping the entry-point symbol across src/stage3/ must
print nothing, and every result dict below carries ``whisper_calls == 0``.
"""

from __future__ import annotations

import sqlite3

from . import normalize as _normalize
from . import render as _render


class DeriveError(ValueError):
    """FAIL: derivation precondition or downstream failure."""


def derive_on_correction_change(
    con: sqlite3.Connection,
    job_dir: str,
    raw_artifact_id: str,
    new_profile: dict,
    render_profile: dict | None = None,
    title: str | None = None,
    canonical_probe_path: str | None = None,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Case 4: correction/profile change => new NormRev + new RenderRev."""
    if render_profile is None:
        render_profile = dict(_render.DEFAULT_PROFILE)
    norm = _normalize.create_normalization_revision(
        con, job_dir, raw_artifact_id, new_profile,
        source_id=source_id, run_id=run_id,
    )
    rend = _render.create_render_revision(
        con, job_dir, norm["normalized_artifact_id"], render_profile,
        title=title, canonical_probe_path=canonical_probe_path,
        source_id=source_id, run_id=run_id,
    )
    return {
        "case": "correction_change",
        "raw_artifact_id": raw_artifact_id,
        "normalization_revision_id": norm["normalization_revision_id"],
        "normalized_artifact_id": norm["normalized_artifact_id"],
        "render_revision_id": rend["render_revision_id"],
        "rendered_artifact_id": rend["rendered_artifact_id"],
        "render_verdict": rend["verdict"],
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def derive_on_formatter_change(
    con: sqlite3.Connection,
    job_dir: str,
    normalized_artifact_id: str,
    new_render_profile: dict,
    title: str | None = None,
    canonical_probe_path: str | None = None,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Case 5: formatter change => only a new RenderRev (NormRev count +0)."""
    before = con.execute(
        "SELECT COUNT(*) FROM normalization_revisions"
    ).fetchone()[0]
    rend = _render.create_render_revision(
        con, job_dir, normalized_artifact_id, new_render_profile,
        title=title, canonical_probe_path=canonical_probe_path,
        source_id=source_id, run_id=run_id,
    )
    after = con.execute(
        "SELECT COUNT(*) FROM normalization_revisions"
    ).fetchone()[0]
    if after != before:
        raise DeriveError(
            "formatter change minted %d normalization revision(s); want 0"
            % (after - before,)
        )
    return {
        "case": "formatter_change",
        "normalized_artifact_id": normalized_artifact_id,
        "normalization_revisions_delta": after - before,
        "render_revision_id": rend["render_revision_id"],
        "rendered_artifact_id": rend["rendered_artifact_id"],
        "render_verdict": rend["verdict"],
        "asr_calls": 0,
        "whisper_calls": 0,
    }
