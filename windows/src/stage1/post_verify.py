"""S1-T04: post-transcription Mandatory Strong SHA256 + G2 compare (V1.8 §25).

Implements STAGE1-PLAN S1-T04 only::

    VERIFYING_SOURCE_AFTER_TRANSCRIPTION:
      unconditionally recompute Source SHA256 (even when fstat unchanged)
      + record before/after fstat compare (device/inode/size/mtime_ns)
      + current_sha256 == content_identity -> COMMITTING_RAW_ASR
      + else -> BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION
        (this ASR never Commits, never enters downstream; the would-be
        Raw product is quarantined diagnostic-only).

G2 semantics (§25 + STAGE1-PLAN Implementation Notes): fstat compare is
the *change-detection signal*, SHA256 is the *sole verdict* (§3.5). A
Case 8 file (same size + same mtime_ns, different bytes) MUST BLOCK —
an implementation that only looks at size/mtime FAILs.

Reuses ``fstat_capture`` / ``sha256_file`` from ``ingest.py`` (read-only
on the source bytes: ``os.stat`` + ``rb`` open — the source video is
never written; abnormal-path tests mutate copies only).

STOP EXPANSION: no PREPARE/COMMIT (T05/T06), no Recovery (T07), no
manifest/SQLite writes at all. This module writes at most:

  - ``<job_dir>/asr/post_verify.json`` (verification evidence, NOT a
    Raw artifact, NOT a COMMITTED receipt, NOT lineage), and
  - on BLOCK, one file under ``<job_dir>/diagnostic_only/`` with the
    BLOCK code in its name (diagnostic-only quarantine).

It never creates ``raw/raw.json``, never touches ``manifest.json``,
never touches ``job.sqlite``. ``raw_commit_count`` in every verdict
counts *formal* Raw commits only (diagnostic files excluded by
construction), so a During-change BLOCK always reports
``Raw Commit = 0`` (§72 gate, P0-8).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

from .ingest import fstat_capture, sha256_file

STATE = "VERIFYING_SOURCE_AFTER_TRANSCRIPTION"
PASS_NEXT = "COMMITTING_RAW_ASR"
BLOCK_CODE = "BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION"

# CLI exit codes (consistent with ingest.py / verify.py: 2 == BLOCK).
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCK = 2

_FSTAT_FIELDS = ("device", "inode", "size", "mtime_ns")

# Stored Source record (source.json) -> fstat-shaped projection.
_STORED_TO_FSTAT = {
    "device": "source_device_id",
    "inode": "source_inode_or_file_id",
    "size": "source_size",
    "mtime_ns": "source_mtime_ns",
}


class PostVerifyError(ValueError):
    """Raised when the *stored evidence itself* is unusable (FAIL, not BLOCK)."""


def _utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")


def load_json(path: str) -> dict:
    """Load a JSON object from *path* (FAIL on missing/invalid)."""
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise PostVerifyError(f"{path} is not a JSON object")
    return payload


def _stored_fstat(record: dict) -> dict:
    """Project the stored Source record back to fstat-shaped signals."""
    missing = [f for f, k in _STORED_TO_FSTAT.items() if record.get(k) is None]
    if missing:
        raise PostVerifyError(
            "source record missing NOT NULL fstat fields: " + ", ".join(missing)
        )
    if record.get("content_identity") is None:
        raise PostVerifyError("source record missing content_identity")
    return {f: record[k] for f, k in _STORED_TO_FSTAT.items()}


def _resolve_source_path(record: dict, override: str | None) -> str:
    if override:
        return override
    for key in ("current_path", "path_identity_key"):
        candidate = record.get(key)
        if candidate:
            return candidate
    raise PostVerifyError("source record has no current_path/path_identity_key")


def _diff_fields(before: dict, after: dict) -> list:
    return [f for f in _FSTAT_FIELDS if before.get(f) != after.get(f)]


def resolve_fstat_before(
    asr_profile: dict | None, source_record: dict
) -> tuple[dict, str]:
    """Resolve the pre-transcription fstat baseline + its provenance.

    Preference: T03 ``asr_profile["fstat"]["before"]`` (the exact bytes
    the model read); fallback: the stored Source record projection.
    Returns ``(fstat_before, provenance)``.
    """
    if isinstance(asr_profile, dict):
        fstat = asr_profile.get("fstat")
        if isinstance(fstat, dict) and isinstance(fstat.get("before"), dict):
            before = fstat["before"]
            if all(f in before for f in _FSTAT_FIELDS):
                return (
                    {f: before[f] for f in _FSTAT_FIELDS},
                    "asr_profile.fstat.before",
                )
    return _stored_fstat(source_record), "source_record_projection"


def count_formal_raw_commits(job_dir: str) -> int:
    """Count *formal* Raw commits in *job_dir* (diagnostic files excluded).

    A formal commit exists iff ``raw/raw.json`` exists AND the manifest
    carries a COMMITTED receipt referencing it. Anything under
    ``diagnostic_only/`` is ignored by construction (P0-8).
    """
    raw_path = os.path.join(job_dir, "raw", "raw.json")
    manifest_path = os.path.join(job_dir, "manifest.json")
    if not os.path.isfile(raw_path):
        return 0
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError):
        return 0
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        return 0
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("state") == "COMMITTED" and receipt.get("artifact") == "raw/raw.json":
            return 1
    return 0


def _base_verdict(
    record: dict,
    path: str,
    fstat_before: dict,
    baseline_provenance: str,
    asr_profile_path: str | None,
    job_dir: str | None,
) -> dict:
    return {
        "state": STATE,
        "source_id": record.get("source_id"),
        "source_path": path,
        "content_identity": record.get("content_identity"),
        "fstat_stored": _stored_fstat(record),
        "fstat_before": fstat_before,
        "fstat_baseline_provenance": baseline_provenance,
        "asr_profile": os.path.abspath(asr_profile_path) if asr_profile_path else None,
        "job_dir": os.path.abspath(job_dir) if job_dir else None,
        "hash_recomputed": True,  # §25: unconditional, set False only below
        "raw_commit_count": count_formal_raw_commits(job_dir) if job_dir else 0,
    }


def verify_source_after_transcription(
    source_record: dict,
    source_path: str | None = None,
    fstat_before: dict | None = None,
    baseline_provenance: str = "caller_supplied",
    asr_profile_path: str | None = None,
    job_dir: str | None = None,
) -> dict:
    """Mandatory post-transcription Strong verification (§25).

    ALWAYS recomputes ``sha256_file(source)`` when the source is
    readable — even when fstat is unchanged. The verdict is derived
    from ``current_hash == content_identity`` alone; fstat diffs are
    recorded as the G2 change signal but never decide PASS/FAIL.
    Drift (or unreadable source) is BLOCK, fail-closed; only an
    unusable *stored record* raises :class:`PostVerifyError` (FAIL).
    """
    path = _resolve_source_path(source_record, source_path)
    content_identity = source_record.get("content_identity")
    if content_identity is None:
        raise PostVerifyError("source record missing content_identity")
    if fstat_before is None:
        fstat_before = _stored_fstat(source_record)
        if baseline_provenance == "caller_supplied":
            baseline_provenance = "source_record_projection"

    base = _base_verdict(
        source_record, path, dict(fstat_before), baseline_provenance,
        asr_profile_path, job_dir,
    )

    try:
        fstat_after = fstat_capture(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_CODE,
            "next_state": BLOCK_CODE,
            "commit_authorized": False,
            "reason": f"source unreadable after transcription (fail-closed): {exc}",
            "fstat_after": None,
            "fstat_changed_before_after": list(_FSTAT_FIELDS),
            "fstat_changed_stored_after": list(_FSTAT_FIELDS),
            "hash_recomputed": False,
            "current_hash": None,
            "hash_match": False,
        }

    try:
        # Unconditional Strong hash — the §25 MUST, never skipped on
        # "fstat unchanged" (that shortcut is exactly what Case 8 kills).
        current_hash = "sha256:" + sha256_file(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_CODE,
            "next_state": BLOCK_CODE,
            "commit_authorized": False,
            "reason": f"source vanished during post rehash (fail-closed): {exc}",
            "fstat_after": fstat_after,
            "fstat_changed_before_after": _diff_fields(fstat_before, fstat_after),
            "fstat_changed_stored_after": _diff_fields(base["fstat_stored"], fstat_after),
            "hash_recomputed": False,
            "current_hash": None,
            "hash_match": False,
        }

    hash_match = current_hash == content_identity
    changed_ba = _diff_fields(fstat_before, fstat_after)
    changed_sa = _diff_fields(base["fstat_stored"], fstat_after)
    if hash_match:
        return {
            **base,
            "verdict": "PASS",
            "code": PASS_NEXT,
            "next_state": PASS_NEXT,
            "commit_authorized": True,
            "reason": (
                "post-transcription Strong SHA256 match; "
                f"fstat before->after changed={changed_ba} (signal only, verdict=SHA256)"
            ),
            "fstat_after": fstat_after,
            "fstat_changed_before_after": changed_ba,
            "fstat_changed_stored_after": changed_sa,
            "current_hash": current_hash,
            "hash_match": True,
        }
    return {
        **base,
        "verdict": "BLOCK",
        "code": BLOCK_CODE,
        "next_state": BLOCK_CODE,
        "commit_authorized": False,
        "reason": (
            "source changed during transcription "
            f"(SHA256 mismatch; fstat before->after changed={changed_ba}, "
            f"stored->after changed={changed_sa}; verdict=SHA256 per §3.5)"
        ),
        "fstat_after": fstat_after,
        "fstat_changed_before_after": changed_ba,
        "fstat_changed_stored_after": changed_sa,
        "current_hash": current_hash,
        "hash_match": False,
    }


def quarantine_to_diagnostic(
    job_dir: str,
    verdict: dict,
    payload: dict | None = None,
) -> str:
    """Quarantine a BLOCKED ASR product as diagnostic-only (P0-8).

    Writes exactly one file under ``<job_dir>/diagnostic_only/`` whose
    name carries the BLOCK code + ``DIAGNOSTIC-ONLY`` marker. Never
    writes ``raw/``, ``manifest.json`` or ``job.sqlite`` — callers (and
    qa) can assert those paths are untouched. Returns the file path.
    """
    if verdict.get("verdict") != "BLOCK":
        raise PostVerifyError("quarantine applies to BLOCK verdicts only")
    diag_dir = os.path.join(os.path.abspath(job_dir), "diagnostic_only")
    os.makedirs(diag_dir, exist_ok=True)
    job_id = os.path.basename(os.path.abspath(job_dir))
    name = (
        f"{BLOCK_CODE}_{job_id}_{_utc_stamp()}_raw_asr.DIAGNOSTIC-ONLY.json"
    )
    diag_path = os.path.join(diag_dir, name)
    _write_json(
        diag_path,
        {
            "is_formal_raw_artifact": False,
            "committed_receipt_written": False,
            "lineage_ref": None,
            "warning": (
                "diagnostic-only: quarantined post-verify BLOCK product; "
                "NOT a formal Raw Artifact, MUST NOT enter lineage or downstream "
                "(Normalization/Render/Publish/Archive). Raw Commit = 0."
            ),
            "block_code": BLOCK_CODE,
            "verdict": verdict,
            "quarantined_asr_payload": payload or {},
        },
    )
    return diag_path


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def run_job(
    source_json_path: str,
    job_dir: str,
    source_path: str | None = None,
    asr_profile_path: str | None = None,
    quarantined_payload: dict | None = None,
) -> dict:
    """Verify one job post-transcription; persist evidence; quarantine on BLOCK.

    Writes ``<job_dir>/asr/post_verify.json`` (verification evidence,
    never a COMMITTED receipt). On BLOCK additionally quarantines to
    ``diagnostic_only/``. Never touches ``raw/``, ``manifest.json``,
    ``job.sqlite``. Returns ``{"verdict": ..., "post_verify_json": ...,
    "diagnostic_path": ...|None}``.
    """
    record = load_json(source_json_path)
    profile = load_json(asr_profile_path) if asr_profile_path else None
    fstat_before, provenance = resolve_fstat_before(profile, record)
    verdict = verify_source_after_transcription(
        record,
        source_path=source_path,
        fstat_before=fstat_before,
        baseline_provenance=provenance,
        asr_profile_path=asr_profile_path,
        job_dir=job_dir,
    )
    asr_dir = os.path.join(os.path.abspath(job_dir), "asr")
    os.makedirs(asr_dir, exist_ok=True)
    post_verify_json = os.path.join(asr_dir, "post_verify.json")
    _write_json(post_verify_json, verdict)
    diagnostic_path = None
    if verdict["verdict"] == "BLOCK":
        diagnostic_path = quarantine_to_diagnostic(
            job_dir, verdict, quarantined_payload
        )
    return {
        "verdict": verdict,
        "post_verify_json": post_verify_json,
        "diagnostic_path": diagnostic_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T04 post-transcription Mandatory Strong SHA256 (§25)"
    )
    parser.add_argument("--source-json", required=True, help="path to source.json")
    parser.add_argument("--job-dir", required=True, help="job dir (H2 test root)")
    parser.add_argument(
        "--source-path", default=None,
        help="override source path (default: current_path in source.json)",
    )
    parser.add_argument(
        "--asr-profile", default=None,
        help="path to asr_profile.json (provides fstat.before baseline)",
    )
    args = parser.parse_args(argv)
    try:
        outcome = run_job(args.source_json, args.job_dir, args.source_path, args.asr_profile)
    except (PostVerifyError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    verdict = outcome["verdict"]
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return EXIT_PASS if verdict["verdict"] == "PASS" else EXIT_BLOCK


if __name__ == "__main__":
    raise SystemExit(main())
