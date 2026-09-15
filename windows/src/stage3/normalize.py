"""S3-T02: Normalization Revision lifecycle + deterministic corrections.

Implements STAGE3-PLAN S3-T02 only (V1.8 ``# 11`` / ``# 29`` / ``# 45`` /
``# 3.9``)::

    PENDING -> NORMALIZING -> COMMITTING -> COMPLETED
    (bypass: FAILED_RETRYABLE / FAILED_FINAL)

* ``normalization_profile_hash`` = SHA256 over the canonical JSON of
  the ``# 29`` six fields (``correction rules revision / hallucination
  classifier version / duplicate cleanup version / chunk merge
  normalization rules / mechanical cleanup version / quality threshold
  profile``). Changing any one field changes the hash, which mints a
  new revision (Case 4).
* ``apply_corrections`` is a pure function (no IO, no network, no
  model): exact-substring replacement from a frozen, versioned rule
  table of highly-determined professional terms only (``# 45`` — no
  LLM, no polishing/rewriting/summarizing, no semantic guessing).
* The revision row lands in central ``normalization_revisions``
  (``# 33`` fields); every transition is recorded in ``state_events``.
* The Normalized artifact commits through S3-T01 to
  ``data/jobs/<job_id>/normalized/<normalization_revision_id>.json``
  (``# 36``). The Processing Run row is never touched here (``# 10``).

Every success dict carries ``whisper_calls == 0``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3

from . import artifact_commit as ac

# V1.8 # 29 — the exact six fields, no more, no less.
NORMALIZATION_PROFILE_FIELDS = (
    "correction_rules_revision",
    "hallucination_classifier_version",
    "duplicate_cleanup_version",
    "chunk_merge_normalization_rules",
    "mechanical_cleanup_version",
    "quality_threshold_profile",
)

STATUS_PENDING = "PENDING"
STATUS_NORMALIZING = "NORMALIZING"
STATUS_COMMITTING = "COMMITTING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED_RETRYABLE = "FAILED_RETRYABLE"
STATUS_FAILED_FINAL = "FAILED_FINAL"

# Frozen deterministic correction tables (# 45: highly-determined
# professional terms only; exact-substring replacement, no guessing).
# A table-content change ships as a new rules revision, i.e. a profile
# change, i.e. Case 4 — never an in-place edit of a live revision.
CORRECTION_RULES = {
    # v1: baseline freeze.
    "corr-v1": (
        ("VIP COIN", "Vibe Coding"),
        ("Ai编程", "AI编程"),
    ),
    # v2: one added highly-determined term (drives Case 4 in tests).
    "corr-v2": (
        ("VIP COIN", "Vibe Coding"),
        ("Ai编程", "AI编程"),
        ("Obsidian笔记", "Obsidian 笔记"),
    ),
}

DEFAULT_PROFILE = {
    "correction_rules_revision": "corr-v1",
    "hallucination_classifier_version": "hallu-v1",
    "duplicate_cleanup_version": "dedup-v1",
    "chunk_merge_normalization_rules": "chunknorm-v1",
    "mechanical_cleanup_version": "mech-v1",
    "quality_threshold_profile": "qual-v1",
}


class NormalizationError(ValueError):
    """FAIL: bad profile / bad raw / commit failure (fail-closed)."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def normalization_profile_hash(profile: dict) -> str:
    """SHA256 over the canonical JSON of the ``# 29`` six fields."""
    if not isinstance(profile, dict):
        raise NormalizationError("normalization profile must be a dict")
    missing = [f for f in NORMALIZATION_PROFILE_FIELDS if f not in profile]
    if missing:
        raise NormalizationError(
            "normalization profile missing fields: " + ", ".join(missing)
        )
    subset = {f: profile[f] for f in NORMALIZATION_PROFILE_FIELDS}
    try:
        canonical = json.dumps(
            subset, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NormalizationError("profile not JSON-canonicalizable: %s" % (exc,))
    for key in NORMALIZATION_PROFILE_FIELDS:
        if not isinstance(subset[key], str) or not subset[key]:
            raise NormalizationError(
                "profile field %r must be a non-empty string" % (key,)
            )
    return hashlib.sha256(canonical).hexdigest()


def revision_id_for(raw_artifact_id: str, profile_hash: str) -> str:
    """Deterministic revision id: same (raw, profile) => same revision."""
    if not raw_artifact_id or not profile_hash:
        raise NormalizationError("raw_artifact_id/profile_hash must be non-empty")
    digest = hashlib.sha256(
        (raw_artifact_id + "|" + profile_hash).encode("utf-8")
    ).hexdigest()[:12]
    return "normrev_" + digest


def normalized_artifact_id_for(revision_id: str) -> str:
    suffix = revision_id.split("_", 1)[1] if "_" in revision_id else revision_id
    return "normalized_" + suffix


def apply_corrections(segments: list, rules_revision: str) -> dict:
    """Pure deterministic correction (``# 45``).

    Returns ``{"segments": new_list, "applied": [...]}``. The input list
    (and its dicts) is never mutated. No IO, no network, no model.
    """
    if rules_revision not in CORRECTION_RULES:
        raise NormalizationError(
            "unknown correction rules revision %r" % (rules_revision,)
        )
    if not isinstance(segments, list):
        raise NormalizationError("segments must be a list")
    rules = CORRECTION_RULES[rules_revision]
    new_segments = []
    applied = []
    for seg in segments:
        if not isinstance(seg, dict) or not isinstance(seg.get("text"), str):
            raise NormalizationError("each segment must be a dict with text")
        text = seg["text"]
        out_seg = dict(seg)
        for pattern, replacement in rules:
            if pattern in text:
                count = text.count(pattern)
                text = text.replace(pattern, replacement)
                applied.append(
                    {
                        "segment_id": seg.get("id"),
                        "pattern": pattern,
                        "replacement": replacement,
                        "count": count,
                    }
                )
        out_seg["text"] = text
        new_segments.append(out_seg)
    return {"segments": new_segments, "applied": applied}


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
            "normalization_revision",
            revision_id,
            from_status,
            to_status,
            reason,
            _utc_now_iso(),
        ),
    )


def _set_status(con, revision_id, to_status, reason=None, completed=False) -> None:
    row = con.execute(
        "SELECT status FROM normalization_revisions"
        " WHERE normalization_revision_id = ?",
        (revision_id,),
    ).fetchone()
    from_status = row[0] if row else None
    if completed:
        con.execute(
            "UPDATE normalization_revisions SET status = ?, completed_at = ?"
            " WHERE normalization_revision_id = ?",
            (to_status, _utc_now_iso(), revision_id),
        )
    else:
        con.execute(
            "UPDATE normalization_revisions SET status = ?"
            " WHERE normalization_revision_id = ?",
            (to_status, revision_id),
        )
    _record_event(con, revision_id, from_status, to_status, reason)


def _load_raw_payload(job_dir: str, raw_artifact_id: str) -> tuple[dict, str]:
    """Load the COMMITTED Raw read-only; validate via the Stage1 gate."""
    from stage1.prepare import validate_raw_artifact  # noqa: PLC0415 (read-only reuse)

    job_dir = os.path.abspath(job_dir)
    raw_path = os.path.join(job_dir, "raw", "raw.json")
    if not os.path.isfile(raw_path):
        raise NormalizationError("COMMITTED raw.json missing at %s" % (raw_path,))
    with open(raw_path, "rb") as fh:
        raw_bytes = fh.read()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise NormalizationError("raw.json unreadable: %s" % (exc,))
    try:
        validate_raw_artifact(payload)
    except ValueError as exc:
        raise NormalizationError("raw schema gate refused: %s" % (exc,))
    if payload.get("artifact_id") != raw_artifact_id:
        raise NormalizationError(
            "raw artifact_id %r != requested %r"
            % (payload.get("artifact_id"), raw_artifact_id)
        )
    return payload, raw_path


def create_normalization_revision(
    con: sqlite3.Connection,
    job_dir: str,
    raw_artifact_id: str,
    profile: dict,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Derive one Normalization Revision from a COMMITTED Raw (``# 11``).

    Idempotent for an identical (raw, profile) pair: a COMPLETED row is
    returned as-is (``idempotent_retry=True``). The Processing Run row
    is never read for mutation and never written (``# 10``).
    """
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    profile_hash = normalization_profile_hash(profile)
    rules_revision = profile["correction_rules_revision"]
    revision_id = revision_id_for(raw_artifact_id, profile_hash)
    artifact_id = normalized_artifact_id_for(revision_id)
    final_relpath = "normalized/%s.json" % (revision_id,)

    existing = con.execute(
        "SELECT normalization_revision_id, raw_artifact_id,"
        " normalization_profile_hash, normalized_artifact_id, status,"
        " created_at, completed_at FROM normalization_revisions"
        " WHERE normalization_revision_id = ?",
        (revision_id,),
    ).fetchone()
    if existing is not None and existing[4] == STATUS_COMPLETED:
        final_path = os.path.join(job_dir, final_relpath)
        with open(final_path, "rb") as fh:
            final_hash = "sha256:" + hashlib.sha256(fh.read()).hexdigest()
        return {
            "normalization_revision_id": revision_id,
            "raw_artifact_id": raw_artifact_id,
            "normalization_profile_hash": profile_hash,
            "normalized_artifact_id": existing[3],
            "status": STATUS_COMPLETED,
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
        raise NormalizationError(
            "revision %s already terminal %s; mint a new profile for retry"
            % (revision_id, existing[4])
        )

    if existing is None:
        with con:
            con.execute(
                "INSERT INTO normalization_revisions"
                " (normalization_revision_id, raw_artifact_id,"
                " normalization_profile_hash, normalized_artifact_id, status,"
                " created_at, completed_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    revision_id, raw_artifact_id, profile_hash, artifact_id,
                    STATUS_PENDING, _utc_now_iso(), None,
                ),
            )
        _record_event(con, revision_id, None, STATUS_PENDING,
                      "revision minted for raw %s" % (raw_artifact_id,))
        con.commit()

    try:
        # NORMALIZING: pure correction over the read-only Raw.
        _set_status(con, revision_id, STATUS_NORMALIZING,
                    "applying %s" % (rules_revision,))
        con.commit()
        try:
            raw_payload, _ = _load_raw_payload(job_dir, raw_artifact_id)
            corrected = apply_corrections(
                raw_payload["segments"], rules_revision
            )
        except (NormalizationError, OSError) as exc:
            _set_status(con, revision_id, STATUS_FAILED_FINAL,
                        "normalizing failed: %s" % (exc,))
            con.commit()
            raise

        normalized_payload = {
            "artifact": "normalized",
            "artifact_version": 1,
            "normalization_revision_id": revision_id,
            "raw_artifact_id": raw_artifact_id,
            "normalization_profile_hash": profile_hash,
            "correction_rules_revision": rules_revision,
            "corrections_applied": corrected["applied"],
            "segments": corrected["segments"],
            "created_at": _utc_now_iso(),
        }
        content_bytes = (
            json.dumps(normalized_payload, ensure_ascii=False, indent=2,
                       sort_keys=True) + "\n"
        ).encode("utf-8")

        # COMMITTING: two-phase artifact commit (S3-T01).
        _set_status(con, revision_id, STATUS_COMMITTING,
                    "committing %s" % (final_relpath,))
        con.commit()
        try:
            try:
                ac.prepare_artifact(
                    con, job_dir, ac.ARTIFACT_TYPE_NORMALIZED, final_relpath,
                    content_bytes, artifact_id, source_id=source_id,
                    run_id=run_id,
                )
            except ac.ArtifactError as exc:
                # Idempotent resume: PREPARED row from an earlier attempt
                # (same bytes => same hash) continues into COMMIT.
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
            raise NormalizationError("artifact commit failed: %s" % (exc,))

        _set_status(con, revision_id, STATUS_COMPLETED,
                    "normalized %s hash_match=%s"
                    % (committed["final_path"], committed["hash_match"]),
                    completed=True)
        con.commit()
        return {
            "normalization_revision_id": revision_id,
            "raw_artifact_id": raw_artifact_id,
            "normalization_profile_hash": profile_hash,
            "normalized_artifact_id": artifact_id,
            "status": STATUS_COMPLETED,
            "job_dir": job_dir,
            "final_path": committed["final_path"],
            "final_hash": committed["final_hash"],
            "corrections_applied": len(corrected["applied"]),
            "idempotent_retry": False,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    except NormalizationError:
        raise
    except (sqlite3.Error, OSError, ValueError) as exc:
        try:
            _set_status(con, revision_id, STATUS_FAILED_FINAL,
                        "unexpected: %s" % (exc,))
            con.commit()
        except sqlite3.Error:
            pass
        raise NormalizationError("normalization failed: %s" % (exc,))
