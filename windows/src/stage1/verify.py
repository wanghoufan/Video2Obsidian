"""S1-T02: pre-transcription Fast Verification (V1.8 §24).

Implements STAGE1-PLAN S1-T02 only::

    VERIFYING_SOURCE_FOR_TRANSCRIPTION:
      read device/inode/size/mtime_ns -> any change -> recompute SHA256 ->
      current_hash != content_identity ->
      BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION (never enters ASR).

Reuses ``fstat_capture`` / ``sha256_file`` from ``ingest.py`` (the G2-ready
fstat helper first built in S1-T01; T04 reuses this module, no Sinneue
duplication). Read-only on the source bytes: ``fstat_capture`` uses
``os.stat`` and ``sha256_file`` opens ``rb`` — the source video is never
written.

STOP EXPANSION: no ASR (T03), no post-ASR verify (T04), no PREPARE/COMMIT
(T05/T06), no Recovery (T07). Verification itself never calls ASR; the
``gate_transcription`` helper takes a caller-supplied callable and invokes
it only on PASS so tests can prove ``asr_calls == 0`` on BLOCK with a
counting stub (no real transcription inside this module).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .ingest import fstat_capture, sha256_file

STATE = "VERIFYING_SOURCE_FOR_TRANSCRIPTION"
BLOCK_CODE = "BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION"
PASS_UNCHANGED = "OK_SOURCE_UNCHANGED"
PASS_FSTAT_CHANGED_HASH_MATCH = "OK_SOURCE_FSTAT_CHANGED_HASH_MATCH"

# CLI exit codes (consistent with ingest.py: 2 == BLOCK, 1 == FAIL).
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCK = 2

_FSTAT_FIELDS = ("device", "inode", "size", "mtime_ns")


class SourceRecordError(ValueError):
    """Raised when the stored Source record is missing/invalid (FAIL, not BLOCK)."""


def load_source_record(source_json_path: str) -> dict:
    """Load a persisted Source record (source.json)."""
    with open(source_json_path, "r", encoding="utf-8") as fh:
        record = json.load(fh)
    if not isinstance(record, dict):
        raise SourceRecordError("source record is not a JSON object")
    return record


def _stored_fstat(record: dict) -> dict:
    """Project the stored Source record back to fstat-shaped signals."""
    mapping = {
        "device": "source_device_id",
        "inode": "source_inode_or_file_id",
        "size": "source_size",
        "mtime_ns": "source_mtime_ns",
    }
    missing = [f for f, k in mapping.items() if record.get(k) is None]
    if missing:
        raise SourceRecordError(
            "source record missing NOT NULL fstat fields: " + ", ".join(missing)
        )
    if record.get("content_identity") is None:
        raise SourceRecordError("source record missing content_identity")
    return {f: record[k] for f, k in mapping.items()}


def _resolve_source_path(record: dict, source_path: str | None) -> str:
    if source_path:
        return source_path
    for key in ("current_path", "path_identity_key"):
        candidate = record.get(key)
        if candidate:
            return candidate
    raise SourceRecordError("source record has no current_path/path_identity_key")


def verify_source_for_transcription(
    source_record: dict, source_path: str | None = None
) -> dict:
    """Fast-verify a Source right before transcription (§24).

    Returns a verdict dict; never raises on source drift (drift == BLOCK,
    fail-closed). Raises :class:`SourceRecordError` only when the *stored
    record itself* is unusable (FAIL). ``asr_calls`` is always 0 here:
    verification never enters ASR — see :func:`gate_transcription`.
    """
    path = _resolve_source_path(source_record, source_path)
    stored = _stored_fstat(source_record)
    content_identity = source_record["content_identity"]
    base = {
        "state": STATE,
        "source_id": source_record.get("source_id"),
        "source_path": path,
        "content_identity": content_identity,
        "fstat_stored": stored,
    }

    try:
        current = fstat_capture(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_CODE,
            "reason": f"source unreadable before transcription: {exc}",
            "fstat_current": None,
            "fstat_changed_fields": list(_FSTAT_FIELDS),
            "hash_recomputed": False,
            "current_hash": None,
            "asr_calls": 0,
        }

    changed = [f for f in _FSTAT_FIELDS if current[f] != stored[f]]
    if not changed:
        return {
            **base,
            "verdict": "PASS",
            "code": PASS_UNCHANGED,
            "reason": "fstat unchanged; content_identity stands without rehash",
            "fstat_current": current,
            "fstat_changed_fields": [],
            "hash_recomputed": False,
            "current_hash": None,
            "asr_calls": 0,
        }

    try:
        current_hash = "sha256:" + sha256_file(path)
    except (FileNotFoundError, OSError) as exc:
        return {
            **base,
            "verdict": "BLOCK",
            "code": BLOCK_CODE,
            "reason": f"source vanished during rehash: {exc}",
            "fstat_current": current,
            "fstat_changed_fields": changed,
            "hash_recomputed": False,
            "current_hash": None,
            "asr_calls": 0,
        }

    if current_hash == content_identity:
        return {
            **base,
            "verdict": "PASS",
            "code": PASS_FSTAT_CHANGED_HASH_MATCH,
            "reason": f"fstat changed {changed} but bytes identical (SHA256 match)",
            "fstat_current": current,
            "fstat_changed_fields": changed,
            "hash_recomputed": True,
            "current_hash": current_hash,
            "asr_calls": 0,
        }
    return {
        **base,
        "verdict": "BLOCK",
        "code": BLOCK_CODE,
        "reason": f"source changed before transcription (fstat {changed}, hash mismatch)",
        "fstat_current": current,
        "fstat_changed_fields": changed,
        "hash_recomputed": True,
        "current_hash": current_hash,
        "asr_calls": 0,
    }


def gate_transcription(
    source_record: dict, source_path: str | None, asr_callable
) -> dict:
    """Gate an ASR call behind verification; the ASR callable runs iff PASS.

    ``asr_callable`` receives the resolved source path and is invoked at
    most once. Returns the verdict dict plus ``asr_calls`` (0/1) and
    ``asr_result`` (None on BLOCK). Production ASR lives in T03; tests pass
    a counting stub here to prove BLOCK never enters ASR.
    """
    verdict = verify_source_for_transcription(source_record, source_path)
    if verdict["verdict"] != "PASS":
        return {**verdict, "asr_calls": 0, "asr_result": None}
    result = asr_callable(verdict["source_path"])
    return {**verdict, "asr_calls": 1, "asr_result": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T02 pre-transcription Fast Verification (§24)"
    )
    parser.add_argument("--source-json", required=True, help="path to source.json")
    parser.add_argument(
        "--source-path",
        default=None,
        help="override source path (default: current_path in source.json)",
    )
    args = parser.parse_args(argv)
    try:
        record = load_source_record(args.source_json)
        verdict = verify_source_for_transcription(record, args.source_path)
    except (SourceRecordError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return EXIT_PASS if verdict["verdict"] == "PASS" else EXIT_BLOCK


if __name__ == "__main__":
    raise SystemExit(main())
