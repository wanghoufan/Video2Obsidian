"""S3-T03: Render Revision lifecycle + deterministic paragraphs.

Implements STAGE3-PLAN S3-T03 only (V1.8 ``# 12`` subsequent branch /
``# 30`` / ``# 47`` / ``# 50``)::

    PENDING -> RENDERING -> ARTIFACT_COMMITTING -> ARTIFACT_COMPLETED
      -> PUBLISH_EVALUATION (terminal in Stage3; verdict only)

* ``render_profile_hash`` = SHA256 over the canonical JSON of the
  ``# 30`` five fields (``paragraph formatter version / paragraph
  parameters / H1 setting / Frontmatter setting / Markdown renderer
  version``). Changing any one field mints a new revision (Case 5).
* ``render_paragraphs`` is a pure function implementing the ``# 47``
  rule priority strictly in order: Long Pause > Strong Punctuation >
  Target Length > Hard Max. Thresholds are versioned fixed values
  carried inside the profile (tuning itself stays Stage9).
* The Rendered artifact commits through S3-T01 to
  ``data/jobs/<job_id>/render/<render_revision_id>.md`` (``# 36``).
* At PUBLISH_EVALUATION the module only records a verdict: a present
  canonical decoy yields ``CANONICAL_OUTPUT_EXISTS``, a missing one
  yields ``PENDING_PUBLISH`` (initial publish belongs to Stage4).
  Zero bytes are written to any canonical path on any branch.
* The Stage4-only execution states do not exist in this module — not
  as constants, not as branches, not as strings. Their presence is
  FAIL per the plan's hard gate.

Every success dict carries ``whisper_calls == 0``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3

from . import artifact_commit as ac

# V1.8 # 30 — the exact five fields, no more, no less.
RENDER_PROFILE_FIELDS = (
    "paragraph_formatter_version",
    "paragraph_parameters",
    "h1_setting",
    "frontmatter_setting",
    "markdown_renderer_version",
)

STATUS_PENDING = "PENDING"
STATUS_RENDERING = "RENDERING"
STATUS_ARTIFACT_COMMITTING = "ARTIFACT_COMMITTING"
STATUS_ARTIFACT_COMPLETED = "ARTIFACT_COMPLETED"
STATUS_PUBLISH_EVALUATION = "PUBLISH_EVALUATION"
STATUS_FAILED_RETRYABLE = "FAILED_RETRYABLE"
STATUS_FAILED_FINAL = "FAILED_FINAL"

# Verdicts recorded at PUBLISH_EVALUATION (# 12 subsequent / # 50).
VERDICT_CANONICAL_EXISTS = "CANONICAL_OUTPUT_EXISTS"
VERDICT_PENDING_PUBLISH = "PENDING_PUBLISH"

# Versioned fixed paragraph thresholds (# 47 values live in the
# profile so a threshold change is a Case 5 profile change).
DEFAULT_PARA_PARAMS = {
    "pause_threshold_s": 1.5,
    "target_chars": 180,
    "hard_max_chars": 400,
}

DEFAULT_PROFILE = {
    "paragraph_formatter_version": "para-v1",
    "paragraph_parameters": dict(DEFAULT_PARA_PARAMS),
    "h1_setting": "h1-title-enabled",
    "frontmatter_setting": "frontmatter-enabled",
    "markdown_renderer_version": "mdrender-v1",
}

# Strong sentence punctuation for the # 47 second rule.
STRONG_PUNCT = ("。", "！", "？", "!", "?", "…", ".")
# Any sentence-ish punctuation for the # 47 third rule.
WEAK_PUNCT = STRONG_PUNCT + ("，", "；", "：", "、", ",", ";", ":")


class RenderError(ValueError):
    """FAIL: bad profile / bad normalized input / commit failure."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def render_profile_hash(profile: dict) -> str:
    """SHA256 over the canonical JSON of the ``# 30`` five fields."""
    if not isinstance(profile, dict):
        raise RenderError("render profile must be a dict")
    missing = [f for f in RENDER_PROFILE_FIELDS if f not in profile]
    if missing:
        raise RenderError(
            "render profile missing fields: " + ", ".join(missing)
        )
    subset = {f: profile[f] for f in RENDER_PROFILE_FIELDS}
    for key in RENDER_PROFILE_FIELDS:
        if subset[key] is None or subset[key] == "":
            raise RenderError(
                "profile field %r must be non-empty" % (key,)
            )
    params = subset["paragraph_parameters"]
    if not isinstance(params, dict):
        raise RenderError("paragraph_parameters must be a dict")
    for key in ("pause_threshold_s", "target_chars", "hard_max_chars"):
        if key not in params:
            raise RenderError("paragraph_parameters missing %r" % (key,))
    try:
        canonical = json.dumps(
            subset, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RenderError("profile not JSON-canonicalizable: %s" % (exc,))
    return hashlib.sha256(canonical).hexdigest()


def render_revision_id_for(normalized_artifact_id: str,
                           profile_hash: str) -> str:
    """Deterministic revision id: same (normalized, profile) => same rev."""
    if not normalized_artifact_id or not profile_hash:
        raise RenderError("normalized_artifact_id/profile_hash must be non-empty")
    digest = hashlib.sha256(
        (normalized_artifact_id + "|" + profile_hash).encode("utf-8")
    ).hexdigest()[:12]
    return "rendrev_" + digest


def rendered_artifact_id_for(revision_id: str) -> str:
    suffix = revision_id.split("_", 1)[1] if "_" in revision_id else revision_id
    return "rendered_" + suffix


def render_paragraphs(segments: list, params: dict) -> list:
    """Pure deterministic paragraphing (``# 47`` rule priority).

    Boundary checks run strictly in order at every segment boundary:
    (1) Long Pause — gap after the current segment exceeds
    ``pause_threshold_s``; (2) Strong Punctuation — accumulated text
    ends with strong punctuation and reached ``target_chars``;
    (3) Target Length — accumulated text reached ``target_chars`` and
    ends with any sentence punctuation; (4) Hard Max — accumulated
    text reached ``hard_max_chars`` (forced break). Returns the list
    of paragraph strings. The input is never mutated.
    """
    if not isinstance(segments, list) or not segments:
        raise RenderError("segments must be a non-empty list")
    try:
        pause_thr = float(params["pause_threshold_s"])
        target = int(params["target_chars"])
        hard_max = int(params["hard_max_chars"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RenderError("bad paragraph_parameters: %s" % (exc,))
    if not (0 < target <= hard_max and pause_thr > 0):
        raise RenderError("paragraph_parameters out of range")

    paragraphs = []
    acc_parts: list[str] = []
    acc_len = 0
    acc_end = 0.0

    def _flush():
        if acc_parts:
            paragraphs.append("".join(acc_parts).strip())

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict) or not isinstance(seg.get("text"), str):
            raise RenderError("each segment must be a dict with text")
        text = seg["text"].strip()
        if not text:
            continue
        if acc_parts:
            gap = float(seg.get("start", acc_end)) - acc_end
            acc_text = "".join(acc_parts)
            if gap > pause_thr:
                _flush()
                acc_parts, acc_len = [], 0
            elif acc_text.endswith(STRONG_PUNCT) and acc_len >= target:
                _flush()
                acc_parts, acc_len = [], 0
            elif acc_text.endswith(WEAK_PUNCT) and acc_len >= target:
                _flush()
                acc_parts, acc_len = [], 0
            elif acc_len >= hard_max:
                _flush()
                acc_parts, acc_len = [], 0
        joiner = "" if not acc_parts else " "
        acc_parts.append(joiner + text if joiner else text)
        acc_len = len("".join(acc_parts))
        try:
            acc_end = float(seg.get("end", acc_end))
        except (TypeError, ValueError):
            acc_end = acc_end
    _flush()
    if not paragraphs:
        raise RenderError("paragraphing produced no output")
    return paragraphs


def assemble_markdown(paragraphs: list, title: str, profile: dict) -> str:
    """Pure Markdown assembly (frontmatter + H1 per profile settings)."""
    if not paragraphs:
        raise RenderError("no paragraphs to assemble")
    title = (title or "untitled").strip() or "untitled"
    parts: list[str] = []
    if profile.get("frontmatter_setting") == "frontmatter-enabled":
        parts.append("---\ntitle: %s\nrender: %s\n---\n" % (
            title, profile.get("markdown_renderer_version", "unknown")))
    if profile.get("h1_setting") == "h1-title-enabled":
        parts.append("# %s\n" % (title,))
    parts.extend(paragraphs)
    return "\n\n".join(parts) + "\n"


def _record_event(con, revision_id, from_status, to_status, reason=None) -> None:
    con.execute(
        "INSERT INTO state_events (event_id, entity_type, entity_id,"
        " from_status, to_status, reason, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            "evt_%s" % (hashlib.sha256(
                (revision_id + (from_status or "") + (to_status or "")
                 + _utc_now_iso()).encode("utf-8"),
            ).hexdigest()[:12]),
            "render_revision",
            revision_id,
            from_status,
            to_status,
            reason,
            _utc_now_iso(),
        ),
    )


def _set_status(con, revision_id, to_status, reason=None, completed=False) -> None:
    row = con.execute(
        "SELECT status FROM render_revisions WHERE render_revision_id = ?",
        (revision_id,),
    ).fetchone()
    from_status = row[0] if row else None
    if completed:
        con.execute(
            "UPDATE render_revisions SET status = ?, completed_at = ?"
            " WHERE render_revision_id = ?",
            (to_status, _utc_now_iso(), revision_id),
        )
    else:
        con.execute(
            "UPDATE render_revisions SET status = ?"
            " WHERE render_revision_id = ?",
            (to_status, revision_id),
        )
    _record_event(con, revision_id, from_status, to_status, reason)


def _load_normalized_payload(con, job_dir: str,
                             normalized_artifact_id: str) -> tuple[dict, str]:
    """Load the Normalized artifact read-only via its revision row."""
    row = con.execute(
        "SELECT normalization_revision_id, raw_artifact_id"
        " FROM normalization_revisions WHERE normalized_artifact_id = ?",
        (normalized_artifact_id,),
    ).fetchone()
    if row is None:
        raise RenderError(
            "unknown normalized_artifact_id %r" % (normalized_artifact_id,)
        )
    revision_id = row[0]
    final_path = os.path.join(job_dir, "normalized", "%s.json" % (revision_id,))
    if not os.path.isfile(final_path):
        raise RenderError("normalized final missing at %s" % (final_path,))
    with open(final_path, "rb") as fh:
        data = fh.read()
    payload = ac.validate_normalized_bytes(data)
    if payload.get("normalization_revision_id") != revision_id:
        raise RenderError("normalized revision id mismatch on disk")
    return payload, final_path


def _stored_verdict(con, job_dir: str, revision_id: str,
                    canonical_probe_path: str | None) -> dict:
    """Idempotent verdict read: manifest receipt first, events next.

    Guarantees the same revision_id returns a stable verdict even if the
    canonical decoy is added/removed between calls. Only when neither the
    manifest receipt nor the ``verdict=`` state_event exists do we fall
    back to a live probe (marked ``evidence="re-probed"``).
    """
    manifest_path = os.path.join(job_dir, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            receipts = manifest.get("receipts", [])
            if isinstance(receipts, list):
                for receipt in receipts:
                    if (
                        isinstance(receipt, dict)
                        and receipt.get("render_revision_id") == revision_id
                        and receipt.get("verdict")
                    ):
                        return {
                            "verdict": receipt["verdict"],
                            "canonical_probe": receipt.get("canonical_probe"),
                            "canonical_writes": receipt.get(
                                "canonical_writes", 0),
                            "evidence": "manifest",
                        }
        except (OSError, ValueError):
            pass
    try:
        rows = con.execute(
            "SELECT reason FROM state_events"
            " WHERE entity_type = 'render_revision' AND entity_id = ?"
            " ORDER BY created_at",
            (revision_id,),
        ).fetchall()
        for row in reversed(rows):
            reason = row[0] if row[0] is not None else ""
            if "verdict=" in reason:
                verdict = reason.split("verdict=", 1)[1].split(";", 1)[0].strip()
                return {
                    "verdict": verdict,
                    "reason": reason,
                    "evidence": "state_events",
                }
    except sqlite3.Error:
        pass
    probed = evaluate_publish(canonical_probe_path)
    probed["evidence"] = "re-probed"
    return probed


def evaluate_publish(canonical_probe_path: str | None) -> dict:
    """Verdict-only evaluation (``# 12`` subsequent / ``# 50``).

    Read-only probe; never writes. Present canonical => the rendered
    output must stay internal (``CANONICAL_OUTPUT_EXISTS``); absent
    canonical => wait for the Stage4 initial publish (``PENDING_PUBLISH``).
    """
    if canonical_probe_path and os.path.isfile(canonical_probe_path):
        return {
            "verdict": VERDICT_CANONICAL_EXISTS,
            "canonical_probe": os.path.abspath(canonical_probe_path),
            "canonical_writes": 0,
        }
    return {
        "verdict": VERDICT_PENDING_PUBLISH,
        "canonical_probe": (
            os.path.abspath(canonical_probe_path)
            if canonical_probe_path else None
        ),
        "canonical_writes": 0,
    }


def create_render_revision(
    con: sqlite3.Connection,
    job_dir: str,
    normalized_artifact_id: str,
    profile: dict,
    title: str | None = None,
    canonical_probe_path: str | None = None,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Render one Render Revision, stopping at PUBLISH_EVALUATION."""
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    profile_hash = render_profile_hash(profile)
    revision_id = render_revision_id_for(normalized_artifact_id, profile_hash)
    artifact_id = rendered_artifact_id_for(revision_id)
    final_relpath = "render/%s.md" % (revision_id,)

    existing = con.execute(
        "SELECT render_revision_id, normalized_artifact_id, render_profile_hash,"
        " rendered_artifact_id, status, created_at, completed_at"
        " FROM render_revisions WHERE render_revision_id = ?",
        (revision_id,),
    ).fetchone()
    if existing is not None and existing[4] == STATUS_PUBLISH_EVALUATION:
        final_path = os.path.join(job_dir, final_relpath)
        with open(final_path, "rb") as fh:
            final_hash = "sha256:" + hashlib.sha256(fh.read()).hexdigest()
        stored = _stored_verdict(
            con, job_dir, revision_id, canonical_probe_path
        )
        return {
            "render_revision_id": revision_id,
            "normalized_artifact_id": normalized_artifact_id,
            "render_profile_hash": profile_hash,
            "rendered_artifact_id": existing[3],
            "status": STATUS_PUBLISH_EVALUATION,
            "verdict": stored["verdict"],
            "verdict_evidence": stored.get("evidence"),
            "job_dir": job_dir,
            "final_path": os.path.abspath(final_path),
            "final_hash": final_hash,
            "idempotent_retry": True,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    if existing is not None and existing[4] in (
        STATUS_FAILED_RETRYABLE, STATUS_FAILED_FINAL,
    ):
        raise RenderError(
            "revision %s already terminal %s; mint a new profile for retry"
            % (revision_id, existing[4])
        )
    if existing is not None and existing[4] not in (
        STATUS_PENDING, STATUS_RENDERING,
        STATUS_ARTIFACT_COMMITTING, STATUS_ARTIFACT_COMPLETED,
    ):
        raise RenderError(
            "revision %s already at %s; mint a new profile for retry"
            % (revision_id, existing[4])
        )

    if existing is None:
        with con:
            con.execute(
                "INSERT INTO render_revisions (render_revision_id,"
                " normalized_artifact_id, render_profile_hash,"
                " rendered_artifact_id, status, created_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    revision_id, normalized_artifact_id, profile_hash,
                    artifact_id, STATUS_PENDING, _utc_now_iso(), None,
                ),
            )
        _record_event(con, revision_id, None, STATUS_PENDING,
                      "revision minted for %s" % (normalized_artifact_id,))
        con.commit()

    try:
        # RENDERING: pure paragraph + markdown over read-only Normalized.
        _set_status(con, revision_id, STATUS_RENDERING, "rendering markdown")
        con.commit()
        try:
            normalized_payload, _ = _load_normalized_payload(
                con, job_dir, normalized_artifact_id
            )
            paragraphs = render_paragraphs(
                normalized_payload["segments"],
                profile["paragraph_parameters"],
            )
            markdown = assemble_markdown(
                paragraphs,
                title or normalized_payload.get("raw_artifact_id", "untitled"),
                profile,
            )
        except (RenderError, OSError) as exc:
            _set_status(con, revision_id, STATUS_FAILED_FINAL,
                        "rendering failed: %s" % (exc,))
            con.commit()
            raise RenderError("rendering failed: %s" % (exc,))
        content_bytes = markdown.encode("utf-8")

        # ARTIFACT_COMMITTING: two-phase artifact commit (S3-T01).
        _set_status(con, revision_id, STATUS_ARTIFACT_COMMITTING,
                    "committing %s" % (final_relpath,))
        con.commit()
        try:
            try:
                ac.prepare_artifact(
                    con, job_dir, ac.ARTIFACT_TYPE_RENDERED, final_relpath,
                    content_bytes, artifact_id, source_id=source_id,
                    run_id=run_id,
                )
            except ac.ArtifactError as exc:
                row = ac._read_row(con, artifact_id)
                if row is None or ac._row_get(row, "status") != ac.STATE_PREPARED:
                    raise
                _ = exc
            committed = ac.commit_artifact(con, job_dir, artifact_id)
        except (ac.ArtifactError, ac.ArtifactRefused,
                ac.ArtifactInvalid, OSError) as exc:
            _set_status(con, revision_id, STATUS_FAILED_RETRYABLE,
                        "committing failed: %s" % (exc,))
            con.commit()
            raise RenderError("artifact commit failed: %s" % (exc,))
        _set_status(con, revision_id, STATUS_ARTIFACT_COMPLETED,
                    "rendered %s hash_match=%s"
                    % (committed["final_path"], committed["hash_match"]))
        con.commit()

        # PUBLISH_EVALUATION: verdict record only, zero canonical writes.
        evaluation = evaluate_publish(canonical_probe_path)
        if evaluation["canonical_writes"] != 0:  # pragma: no cover — defensive
            raise RenderError("canonical write detected; refusing evaluation")
        _set_status(
            con, revision_id, STATUS_PUBLISH_EVALUATION,
            "verdict=%s; canonical_probe=%s; canonical_writes=0"
            % (evaluation["verdict"], evaluation["canonical_probe"]),
            completed=True,
        )
        con.commit()
        manifest_path = os.path.join(job_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            from . import lineage as _lineage  # noqa: PLC0415 (append-only)

            _lineage.record_lineage_manifest(
                manifest_path,
                receipts=[{
                    "stage": "Stage3-S3-T03",
                    "state": STATUS_PUBLISH_EVALUATION,
                    "artifact": final_relpath,
                    "artifact_id": artifact_id,
                    "render_revision_id": revision_id,
                    "verdict": evaluation["verdict"],
                    "canonical_probe": evaluation["canonical_probe"],
                    "canonical_writes": 0,
                    "created_at": _utc_now_iso(),
                }],
            )
        return {
            "render_revision_id": revision_id,
            "normalized_artifact_id": normalized_artifact_id,
            "render_profile_hash": profile_hash,
            "rendered_artifact_id": artifact_id,
            "status": STATUS_PUBLISH_EVALUATION,
            "verdict": evaluation["verdict"],
            "job_dir": job_dir,
            "final_path": committed["final_path"],
            "final_hash": committed["final_hash"],
            "paragraphs": len(paragraphs),
            "idempotent_retry": False,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    except RenderError:
        raise
    except (sqlite3.Error, OSError, ValueError) as exc:
        try:
            _set_status(con, revision_id, STATUS_FAILED_FINAL,
                        "unexpected: %s" % (exc,))
            con.commit()
        except sqlite3.Error:
            pass
        raise RenderError("render revision failed: %s" % (exc,))
