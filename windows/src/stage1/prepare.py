"""S1-T05: Raw PREPARE Phase (V1.8 §38).

Implements STAGE1-PLAN S1-T05 only::

    raw.json.tmp -> flush -> fsync(file) -> parse/schema validation
      -> expected_artifact_hash
      -> SQLite artifacts row (state=PREPARED) -> COMMIT transaction

Gate: the T04 ``asr/post_verify.json`` verdict MUST be ``PASS``
(``code == COMMITTING_RAW_ASR``, ``commit_authorized == True``).
Any non-PASS verdict refuses PREPARE (fail-closed, exit 2) — a
BLOCKED source never produces even a ``.tmp`` artifact row.

Writes (and only these):
  - ``<job_dir>/raw/raw.json.tmp`` (canonical bytes, fsync'd file)
  - ``<job_dir>/job.sqlite`` ``artifacts`` row ``state=PREPARED``
    (single transaction COMMIT; table created IF NOT EXISTS so the
    T01 ``sources``/``processing_runs`` chain is preserved)
  - ``<job_dir>/raw/prepare_receipt.json`` (PREPARED Receipt evidence)

Never writes ``raw/raw.json`` (final), never touches
``manifest.json`` (COMMITTED receipt is T06), never touches
``diagnostic_only/``, never calls ASR/Whisper.

Acceptance mapping (FAIL conditions):
  - expected hash not persisted (no SQLite row / hash mismatch) -> FAIL
  - schema validation missing/failed -> FAIL (tmp unlinked, no row)
  - SQLite row vs tmp file inconsistent on re-read -> FAIL
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys

STATE_PREPARED = "PREPARED"
ARTIFACT_TYPE_RAW = "raw"
POST_PASS_CODE = "COMMITTING_RAW_ASR"

TMP_NAME = "raw.json.tmp"
FINAL_NAME = "raw.json"
RECEIPT_NAME = "prepare_receipt.json"

# CLI exit codes (consistent with ingest/verify/post_verify).
EXIT_PREPARED = 0
EXIT_FAIL = 1
EXIT_REFUSED = 2

# Minimal Stage1 Raw Artifact schema: required top-level keys.
REQUIRED_RAW_FIELDS = (
    "artifact",
    "artifact_version",
    "artifact_id",
    "job_id",
    "source_id",
    "content_identity",
    "created_at",
    "transcript",
    "segments",
    "asr",
    "post_verify",
    "lineage",
)


class PrepareError(ValueError):
    """FAIL: stored evidence unusable / validation / hash / DB error."""


class PrepareRefused(RuntimeError):
    """REFUSED: T04 verdict is not PASS — PREPARE must not proceed."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise PrepareError(f"{path} is not a JSON object")
    return payload


def _write_fsync_json(path: str, payload: dict) -> bytes:
    """Write canonical JSON (sorted keys) + flush + fsync(file).

    Returns the exact bytes written so callers hash what is on disk.
    """
    data = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return data


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_raw_artifact(raw: dict) -> None:
    """Strict schema validation for the Stage1 Raw Artifact.

    Raises :class:`PrepareError` (FAIL) on any deviation. This is the
    mandatory parse/schema-validation gate of §38 — it MUST run after
    the tmp file is fsync'd and re-parsed, never skipped.
    """
    missing = [f for f in REQUIRED_RAW_FIELDS if f not in raw]
    if missing:
        raise PrepareError(
            "raw schema validation failed: missing fields: " + ", ".join(missing)
        )
    if raw.get("artifact") != "raw":
        raise PrepareError("raw schema validation failed: artifact != 'raw'")
    if raw.get("artifact_version") != 1:
        raise PrepareError("raw schema validation failed: artifact_version != 1")
    for key in ("artifact_id", "job_id", "source_id", "content_identity"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise PrepareError(
                f"raw schema validation failed: {key} must be a non-empty string"
            )
    if not str(raw["content_identity"]).startswith("sha256:"):
        raise PrepareError(
            "raw schema validation failed: content_identity must start with 'sha256:'"
        )
    tr = raw.get("transcript")
    if not isinstance(tr, dict):
        raise PrepareError("raw schema validation failed: transcript must be an object")
    for key in ("text", "text_sha256", "chars", "segments"):
        if key not in tr:
            raise PrepareError(
                f"raw schema validation failed: transcript.{key} missing"
            )
    if not isinstance(tr["text"], str):
        raise PrepareError("raw schema validation failed: transcript.text not a string")
    expect_sha = _sha256_hex(tr["text"].encode("utf-8"))
    if tr["text_sha256"] != expect_sha:
        raise PrepareError(
            "raw schema validation failed: transcript.text_sha256 mismatch "
            f"(want {expect_sha}, got {tr['text_sha256']!r})"
        )
    if tr["chars"] != len(tr["text"]):
        raise PrepareError("raw schema validation failed: transcript.chars mismatch")
    segs = raw.get("segments")
    if not isinstance(segs, list):
        raise PrepareError("raw schema validation failed: segments must be a list")
    if tr["segments"] != len(segs):
        raise PrepareError(
            "raw schema validation failed: transcript.segments count mismatch"
        )
    asr = raw.get("asr")
    if not isinstance(asr, dict):
        raise PrepareError("raw schema validation failed: asr must be an object")
    for key in ("model", "model_revision", "audio_mode"):
        if not asr.get(key):
            raise PrepareError(f"raw schema validation failed: asr.{key} missing")
    pv = raw.get("post_verify")
    if not isinstance(pv, dict):
        raise PrepareError("raw schema validation failed: post_verify must be an object")
    if pv.get("verdict") != "PASS":
        raise PrepareError("raw schema validation failed: post_verify.verdict != PASS")
    if pv.get("current_hash") != raw["content_identity"]:
        raise PrepareError(
            "raw schema validation failed: post_verify.current_hash != content_identity"
        )
    lin = raw.get("lineage")
    if not isinstance(lin, dict):
        raise PrepareError("raw schema validation failed: lineage must be an object")
    for key in ("source", "asr_profile", "post_verify"):
        if not lin.get(key):
            raise PrepareError(f"raw schema validation failed: lineage.{key} missing")


def _check_post_verify_gate(post_verify: dict) -> None:
    """Refuse PREPARE unless the T04 verdict is an authorizing PASS."""
    if not isinstance(post_verify, dict):
        raise PrepareRefused("post_verify evidence is not a JSON object")
    if post_verify.get("verdict") != "PASS":
        raise PrepareRefused(
            "PREPARE refused: post_verify verdict "
            f"{post_verify.get('verdict')!r} != 'PASS' "
            f"(code={post_verify.get('code')!r})"
        )
    if post_verify.get("code") != POST_PASS_CODE:
        raise PrepareRefused(
            f"PREPARE refused: post_verify code {post_verify.get('code')!r} "
            f"!= {POST_PASS_CODE!r}"
        )
    if post_verify.get("commit_authorized") is not True:
        raise PrepareRefused(
            "PREPARE refused: post_verify commit_authorized is not True"
        )
    if post_verify.get("hash_match") is not True:
        raise PrepareRefused("PREPARE refused: post_verify hash_match is not True")


def _ensure_artifacts_table(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS artifacts ("
        "artifact_id TEXT PRIMARY KEY, "
        "owner_id TEXT NOT NULL, "
        "artifact_type TEXT NOT NULL, "
        "expected_hash TEXT NOT NULL, "
        "temp_path TEXT NOT NULL, "
        "final_path TEXT NOT NULL, "
        "state TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )


def build_raw_content(
    job_id: str,
    source_record: dict,
    transcript_text: str,
    segments: list,
    asr_profile: dict | None,
    post_verify: dict,
) -> dict:
    """Assemble the Raw Artifact dict (pre-write; validated again post-fsync)."""
    source_id = source_record.get("source_id")
    content_identity = source_record.get("content_identity")
    if not source_id or not content_identity:
        raise PrepareError("source record missing source_id/content_identity")
    if post_verify.get("current_hash") != content_identity:
        raise PrepareRefused(
            "PREPARE refused: post_verify current_hash != source content_identity"
        )
    artifact_id = f"raw_{job_id}"
    asr_src = asr_profile if isinstance(asr_profile, dict) else {}
    actual = asr_src.get("actual") if isinstance(asr_src.get("actual"), dict) else {}
    frozen = asr_src.get("frozen") if isinstance(asr_src.get("frozen"), dict) else {}
    return {
        "artifact": "raw",
        "artifact_version": 1,
        "artifact_id": artifact_id,
        "job_id": job_id,
        "source_id": source_id,
        "content_identity": content_identity,
        "created_at": _utc_now_iso(),
        "transcript": {
            "text": transcript_text,
            "text_sha256": _sha256_hex(transcript_text.encode("utf-8")),
            "chars": len(transcript_text),
            "segments": len(segments),
        },
        "segments": segments,
        "asr": {
            "model": frozen.get("model") or actual.get("model") or "unknown",
            "model_revision": frozen.get("model_revision")
            or actual.get("model_revision")
            or "unknown",
            "audio_mode": frozen.get("audio")
            or actual.get("audio_mode")
            or "unknown",
            "word_timestamps": actual.get("word_timestamps"),
            "no_speech_threshold": actual.get("no_speech_threshold"),
        },
        "post_verify": {
            "verdict": post_verify.get("verdict"),
            "code": post_verify.get("code"),
            "current_hash": post_verify.get("current_hash"),
            "hash_match": post_verify.get("hash_match"),
        },
        "lineage": {
            "source": "source.json",
            "asr_profile": "asr/asr_profile.json",
            "post_verify": "asr/post_verify.json",
        },
    }


def prepare_raw(
    job_dir: str,
    source_path_override: str | None = None,
) -> dict:
    """Run the §38 PREPARE Phase for one job.

    Reads ``source.json`` + ``asr/post_verify.json`` (PASS gate) +
    ``asr/transcript.txt`` + ``asr/segments.json`` (+ optional
    ``asr/asr_profile.json``), writes ``raw/raw.json.tmp`` (flush +
    fsync), re-parses + schema-validates the tmp bytes, hashes them as
    ``expected_artifact_hash``, inserts the ``artifacts`` row
    ``state=PREPARED`` in one SQLite transaction, re-verifies
    SQLite-vs-tmp consistency, then writes the PREPARED Receipt.
    """
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    raw_dir = os.path.join(job_dir, "raw")
    tmp_path = os.path.join(raw_dir, TMP_NAME)
    final_path = os.path.join(raw_dir, FINAL_NAME)
    receipt_path = os.path.join(raw_dir, RECEIPT_NAME)
    sqlite_path = os.path.join(job_dir, "job.sqlite")

    source_json = os.path.join(job_dir, "source.json")
    post_verify_json = os.path.join(job_dir, "asr", "post_verify.json")
    transcript_txt = os.path.join(job_dir, "asr", "transcript.txt")
    segments_json = os.path.join(job_dir, "asr", "segments.json")
    asr_profile_json = os.path.join(job_dir, "asr", "asr_profile.json")

    try:
        source_record = _load_json(source_json)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PrepareError(f"source.json unreadable: {exc}") from exc
    try:
        post_verify = _load_json(post_verify_json)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PrepareError(f"post_verify.json unreadable: {exc}") from exc

    # §38 gate BEFORE any write: non-PASS verdicts never reach tmp/SQLite.
    _check_post_verify_gate(post_verify)

    try:
        with open(transcript_txt, "r", encoding="utf-8") as fh:
            transcript_text = fh.read()
    except (FileNotFoundError, OSError) as exc:
        raise PrepareError(f"transcript.txt unreadable: {exc}") from exc
    try:
        segments_payload = _load_json(segments_json)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise PrepareError(f"segments.json unreadable: {exc}") from exc
    segments = segments_payload.get("segments")
    if not isinstance(segments, list):
        raise PrepareError("segments.json must contain a 'segments' list")
    asr_profile = None
    if os.path.isfile(asr_profile_json):
        try:
            asr_profile = _load_json(asr_profile_json)
        except ValueError as exc:
            raise PrepareError(f"asr_profile.json invalid: {exc}") from exc

    if source_path_override is not None:
        _ = source_path_override  # reserved for T06/recovery callers; identity fixed

    raw_content = build_raw_content(
        job_id, source_record, transcript_text, segments, asr_profile, post_verify
    )

    artifact_id = raw_content["artifact_id"]
    owner_id = job_id  # Stage1: the single Processing Run (job) owns its Raw

    # 0. Pre-write idempotency gate (BEFORE touching tmp):
    #    created_at lives inside the hashed bytes, so a blind rewrite would
    #    always diverge from the stored hash. A PREPARED row whose tmp file
    #    still hashes to the stored expected_hash is an idempotent retry:
    #    validate the on-disk tmp and return the stored receipt without
    #    rewriting. Any other pre-existing row state refuses (COMMITTED =
    #    immutable; PREPARED with missing/diverged tmp = T07 recovery case,
    #    never a blind overwrite here).
    if os.path.isfile(sqlite_path):
        _pre = sqlite3.connect(sqlite_path)
        try:
            _has = _pre.execute(
                "SELECT count(*) FROM sqlite_master"
                " WHERE type='table' AND name='artifacts'"
            ).fetchone()[0]
            _existing = None
            if _has:
                _existing = _pre.execute(
                    "SELECT artifact_id, owner_id, artifact_type, expected_hash,"
                    " temp_path, final_path, state, created_at FROM artifacts"
                    " WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
        finally:
            _pre.close()
        if _existing is not None:
            (_eid, _eowner, _eatype, _ehash, _etmp, _efinal, _estate, _eat) = _existing
            if _estate == "COMMITTED":
                raise PrepareError(
                    f"artifact {artifact_id} already COMMITTED (immutable); "
                    "refusing re-PREPARE"
                )
            if _estate == STATE_PREPARED:
                if (
                    os.path.isfile(tmp_path)
                    and os.path.abspath(_etmp) == os.path.abspath(tmp_path)
                    and os.path.abspath(_efinal) == os.path.abspath(final_path)
                    and "sha256:" + _sha256_hex(open(tmp_path, "rb").read()) == _ehash
                ):
                    with open(tmp_path, "rb") as _fh:
                        _disk = _fh.read()
                    validate_raw_artifact(json.loads(_disk.decode("utf-8")))
                    _receipt = {
                        "stage": "Stage1-S1-T05",
                        "state": STATE_PREPARED,
                        "artifact": FINAL_NAME,
                        "artifact_id": _eid,
                        "owner_id": _eowner,
                        "artifact_type": _eatype,
                        "expected_artifact_hash": _ehash,
                        "temp_path": os.path.abspath(tmp_path),
                        "final_path": os.path.abspath(final_path),
                        "job_dir": job_dir,
                        "job_id": job_id,
                        "source_id": source_record.get("source_id"),
                        "content_identity": source_record.get("content_identity"),
                        "post_verify_code": post_verify.get("code"),
                        "sqlite_path": os.path.abspath(sqlite_path),
                        "created_at": _eat,
                        "idempotent_retry": True,
                    }
                    _write_fsync_json(receipt_path, _receipt)
                    return {
                        "artifact_id": _eid,
                        "owner_id": _eowner,
                        "expected_artifact_hash": _ehash,
                        "temp_path": os.path.abspath(tmp_path),
                        "final_path": os.path.abspath(final_path),
                        "state": STATE_PREPARED,
                        "sqlite_path": os.path.abspath(sqlite_path),
                        "receipt_path": os.path.abspath(receipt_path),
                        "receipt": _receipt,
                        "sqlite_row": {
                            "artifact_id": _eid,
                            "owner_id": _eowner,
                            "artifact_type": _eatype,
                            "expected_hash": _ehash,
                            "temp_path": _etmp,
                            "final_path": _efinal,
                            "state": _estate,
                            "created_at": _eat,
                        },
                    }
                raise PrepareError(
                    f"artifact {artifact_id} already PREPARED "
                    f"(stored {_ehash}) but tmp is missing/diverged; "
                    "refusing overwrite — T07 recovery owns this state"
                )

    # 1-3. tmp write -> flush -> fsync(file).
    written_bytes = _write_fsync_json(tmp_path, raw_content)

    # 4. Re-parse + mandatory schema validation on the fsync'd bytes.
    try:
        with open(tmp_path, "rb") as fh:
            tmp_bytes = fh.read()
        if tmp_bytes != written_bytes:
            raise PrepareError("tmp file bytes differ from written bytes")
        parsed = json.loads(tmp_bytes.decode("utf-8"))
        validate_raw_artifact(parsed)
    except PrepareError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise PrepareError(f"tmp re-parse failed: {exc}") from exc

    # 5. expected_artifact_hash over the exact tmp bytes.
    expected_hash = "sha256:" + _sha256_hex(tmp_bytes)
    created_at = _utc_now_iso()

    # 6-7. SQLite artifacts row state=PREPARED -> COMMIT transaction.
    try:
        con = sqlite3.connect(sqlite_path)
        try:
            con.execute("PRAGMA foreign_keys = ON")
            _ensure_artifacts_table(con)
            existing = con.execute(
                "SELECT artifact_id, owner_id, artifact_type, expected_hash,"
                " temp_path, final_path, state FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            if existing is not None:
                _, _, _, old_hash, _, _, old_state = existing
                if old_state == "COMMITTED":
                    raise PrepareError(
                        f"artifact {artifact_id} already COMMITTED (immutable); "
                        "refusing re-PREPARE"
                    )
                if old_state == "PREPARED" and old_hash != expected_hash:
                    raise PrepareError(
                        f"artifact {artifact_id} already PREPARED with a different "
                        f"expected_hash (stored {old_hash} != computed {expected_hash}); "
                        "refusing overwrite"
                    )
                if old_state == "PREPARED" and old_hash == expected_hash:
                    pass  # idempotent re-PREPARE of identical bytes
            with con:  # single transaction COMMIT
                con.execute(
                    "INSERT OR REPLACE INTO artifacts "
                    "(artifact_id, owner_id, artifact_type, expected_hash,"
                    " temp_path, final_path, state, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        artifact_id,
                        owner_id,
                        ARTIFACT_TYPE_RAW,
                        expected_hash,
                        os.path.abspath(tmp_path),
                        os.path.abspath(final_path),
                        STATE_PREPARED,
                        created_at,
                    ),
                )
            row = con.execute(
                "SELECT artifact_id, owner_id, artifact_type, expected_hash,"
                " temp_path, final_path, state, created_at FROM artifacts"
                " WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        finally:
            con.close()
    except PrepareError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    except (sqlite3.Error, OSError) as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise PrepareError(f"SQLite PREPARED write failed: {exc}") from exc

    if row is None:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise PrepareError("expected hash not persisted: artifacts row missing")

    # 8. Post-COMMIT consistency: SQLite row vs tmp file must agree.
    (
        _rid,
        _owner,
        _atype,
        stored_hash,
        stored_tmp,
        stored_final,
        stored_state,
        stored_at,
    ) = row
    consistency_errors: list[str] = []
    if stored_hash != expected_hash:
        consistency_errors.append("stored expected_hash != computed hash")
    if stored_state != STATE_PREPARED:
        consistency_errors.append(f"stored state {stored_state!r} != PREPARED")
    if os.path.abspath(stored_tmp) != os.path.abspath(tmp_path):
        consistency_errors.append("stored temp_path != tmp_path")
    if os.path.abspath(stored_final) != os.path.abspath(final_path):
        consistency_errors.append("stored final_path != final_path")
    if not os.path.isfile(tmp_path):
        consistency_errors.append("tmp file missing after COMMIT")
    else:
        with open(tmp_path, "rb") as fh:
            disk_bytes = fh.read()
        if "sha256:" + _sha256_hex(disk_bytes) != stored_hash:
            consistency_errors.append("tmp file hash != stored expected_hash")
    if os.path.isfile(final_path):
        # T05 must never create the final artifact (that is T06 COMMIT).
        consistency_errors.append("final raw.json already exists; T05 must not create it")
    if consistency_errors:
        raise PrepareError(
            "SQLite vs tmp inconsistent: " + "; ".join(consistency_errors)
        )

    # 9. PREPARED Receipt evidence (NOT the final artifact, NOT manifest).
    receipt = {
        "stage": "Stage1-S1-T05",
        "state": STATE_PREPARED,
        "artifact": FINAL_NAME,
        "artifact_id": artifact_id,
        "owner_id": owner_id,
        "artifact_type": ARTIFACT_TYPE_RAW,
        "expected_artifact_hash": expected_hash,
        "temp_path": os.path.abspath(tmp_path),
        "final_path": os.path.abspath(final_path),
        "job_dir": job_dir,
        "job_id": job_id,
        "source_id": source_record.get("source_id"),
        "content_identity": source_record.get("content_identity"),
        "post_verify_code": post_verify.get("code"),
        "sqlite_path": os.path.abspath(sqlite_path),
        "created_at": stored_at,
    }
    _write_fsync_json(receipt_path, receipt)

    return {
        "artifact_id": artifact_id,
        "owner_id": owner_id,
        "expected_artifact_hash": expected_hash,
        "temp_path": os.path.abspath(tmp_path),
        "final_path": os.path.abspath(final_path),
        "state": STATE_PREPARED,
        "sqlite_path": os.path.abspath(sqlite_path),
        "receipt_path": os.path.abspath(receipt_path),
        "receipt": receipt,
        "sqlite_row": {
            "artifact_id": _rid,
            "owner_id": _owner,
            "artifact_type": _atype,
            "expected_hash": stored_hash,
            "temp_path": stored_tmp,
            "final_path": stored_final,
            "state": stored_state,
            "created_at": stored_at,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T05 Raw PREPARE Phase (§38): tmp+fsync+validate+hash+SQLite PREPARED"
    )
    parser.add_argument("--job-dir", required=True, help="job dir (H2 test root)")
    args = parser.parse_args(argv)
    try:
        result = prepare_raw(args.job_dir)
    except PrepareRefused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except (PrepareError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(result["receipt"], ensure_ascii=False, indent=2))
    return EXIT_PREPARED


if __name__ == "__main__":
    raise SystemExit(main())
