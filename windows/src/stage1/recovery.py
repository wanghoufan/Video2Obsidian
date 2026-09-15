"""S1-T07: Recovery — PREPARE-after-kill-9 + SQLite-lag Repair Forward.

Implements STAGE1-PLAN S1-T07 only (V1.8 §40-41, Case 9 / Case 15 Raw span)::

    PREPARED + Final Exists + Hash Match -> Repair Forward
      (补 Manifest COMMITTED + SQLite COMMITTED, 不重跑 Whisper)
    PREPARED + tmp Exists + Final Missing -> 验 tmp 后继续 Commit
    Final Hash != Expected -> NEVER valid (FAIL, no COMMITTED transition)
    SQLite 落后一律 Repair Forward, 不重跑昂贵 ASR

Truth Model (§41, hard-coded here, never inverted):

    Valid Filesystem Artifact + Expected Hash = Artifact Truth
    PREPARED / COMMITTED Receipt = Commit Evidence
    Manifest = Commit Receipt + Lineage Metadata
    SQLite = Workflow State / Index (永远是落后方, 只许 Repair Forward)

This module NEVER calls ASR/Whisper (no import of ``asr``, no subprocess
to ffmpeg/model). Every success result carries ``asr_calls == 0`` and
``whisper_calls == 0`` so QA can assert the counter is unchanged.

Writes (and only these):
  - ``<job_dir>/raw/raw.json`` (only via tmp->final path reusing commit)
  - ``<job_dir>/manifest.json`` (append COMMITTED receipt, Repair Forward)
  - ``<job_dir>/job.sqlite`` ``artifacts`` row ``PREPARED -> COMMITTED``
  - ``<job_dir>/raw/commit_receipt.json`` (COMMITTED Receipt evidence)
  - ``<job_dir>/raw/recover_receipt.json`` (Recovery evidence, stage S1-T07)

Never touches ``source.json`` / ``run.json`` / ``asr/`` /
``diagnostic_only/``. Never fabricates bytes when both tmp and final
are missing. Never marks hash-mismatched bytes as COMMITTED.
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
STATE_COMMITTED = "COMMITTED"

TMP_NAME = "raw.json.tmp"
FINAL_NAME = "raw.json"
PREPARE_RECEIPT_NAME = "prepare_receipt.json"
COMMIT_RECEIPT_NAME = "commit_receipt.json"
RECOVER_RECEIPT_NAME = "recover_receipt.json"

# CLI exit codes (consistent with prepare/commit: 0 ok, 1 FAIL, 2 REFUSED).
EXIT_RECOVERED = 0
EXIT_FAIL = 1
EXIT_REFUSED = 2


class RecoveryError(ValueError):
    """FAIL: evidence unusable / hash mismatch / DB error (fail-closed)."""


class RecoveryRefused(RuntimeError):
    """REFUSED: no PREPARED evidence — recovery must not proceed."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise RecoveryError(f"{path} is not a JSON object")
    return payload


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_fsync_json(path: str, payload: dict) -> bytes:
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


def _read_artifact_row(con: sqlite3.Connection, artifact_id: str):
    return con.execute(
        "SELECT artifact_id, owner_id, artifact_type, expected_hash,"
        " temp_path, final_path, state, created_at FROM artifacts"
        " WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()


def _manifest_has_committed(manifest: dict, artifact_id: str) -> bool:
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        return False
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        if (
            receipt.get("state") == STATE_COMMITTED
            and receipt.get("artifact") == "raw/raw.json"
            and receipt.get("artifact_id") == artifact_id
        ):
            return True
    return False


def recover_raw(job_dir: str) -> dict:
    """Repair-Forward recovery for one job (S1-T07, §40-41).

    No ASR/Whisper is ever invoked. Truth is established as
    ``Filesystem Valid + Expected Hash``; SQLite is always treated as
    the lagging side and repaired forward, never the reverse.
    """
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    artifact_id = f"raw_{job_id}"
    raw_dir = os.path.join(job_dir, "raw")
    tmp_path = os.path.join(raw_dir, TMP_NAME)
    final_path = os.path.join(raw_dir, FINAL_NAME)
    prepare_receipt_path = os.path.join(raw_dir, PREPARE_RECEIPT_NAME)
    commit_receipt_path = os.path.join(raw_dir, COMMIT_RECEIPT_NAME)
    recover_receipt_path = os.path.join(raw_dir, RECOVER_RECEIPT_NAME)
    manifest_path = os.path.join(job_dir, "manifest.json")
    sqlite_path = os.path.join(job_dir, "job.sqlite")

    # 0. PREPARED precondition: SQLite row must exist (expected hash source).
    #    Truth Model needs the persisted expected_hash; without it there is
    #    no Truth to repair toward -> REFUSED (not FAIL).
    if not os.path.isfile(sqlite_path):
        raise RecoveryRefused(
            f"recovery refused: {sqlite_path} missing (no PREPARED evidence)"
        )
    con = sqlite3.connect(sqlite_path)
    try:
        has = con.execute(
            "SELECT count(*) FROM sqlite_master"
            " WHERE type='table' AND name='artifacts'"
        ).fetchone()[0]
        if not has:
            raise RecoveryRefused(
                "recovery refused: artifacts table missing (no PREPARE)"
            )
        row = _read_artifact_row(con, artifact_id)
    finally:
        con.close()
    if row is None:
        raise RecoveryRefused(
            f"recovery refused: artifact {artifact_id} has no artifacts row"
        )
    (_rid, _owner, _atype, expected_hash, stored_tmp, stored_final,
     state, _at) = row
    if _atype != "raw":
        raise RecoveryError(f"artifact type {_atype!r} != 'raw'")
    if not expected_hash.startswith("sha256:"):
        raise RecoveryError("stored expected_hash malformed")
    if os.path.abspath(stored_tmp) != os.path.abspath(tmp_path):
        raise RecoveryError("stored temp_path != raw.json.tmp path")
    if os.path.abspath(stored_final) != os.path.abspath(final_path):
        raise RecoveryError("stored final_path != raw.json path")

    # Cross-check PREPARED receipt when present (must agree, else FAIL).
    if os.path.isfile(prepare_receipt_path):
        try:
            prep = _load_json(prepare_receipt_path)
            if prep.get("expected_artifact_hash") != expected_hash:
                raise RecoveryError(
                    "prepare_receipt expected_artifact_hash != SQLite expected_hash"
                )
            if prep.get("artifact_id") != artifact_id:
                raise RecoveryError("prepare_receipt artifact_id mismatch")
        except RecoveryError:
            raise
        except (OSError, ValueError) as exc:
            raise RecoveryError(f"prepare_receipt unreadable: {exc}") from exc

    # 1. Already COMMITTED: idempotent verify (Truth still = filesystem+hash).
    if state == STATE_COMMITTED:
        if not os.path.isfile(final_path):
            raise RecoveryError(
                f"artifact {artifact_id} SQLite COMMITTED but final missing;"
                " refusing to fabricate bytes"
            )
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise RecoveryError(
                f"artifact {artifact_id} COMMITTED but final hash {final_hash}"
                f" != expected {expected_hash}: NEVER valid (§40)"
            )
        # Manifest may lag (manual repair case) -> forward-repair it.
        from .commit import (  # noqa: PLC0415 (reuse T06 writers, no ASR)
            _chmod_readonly,
            _ensure_committed_manifest,
            _write_commit_receipt,
        )

        manifest = _load_json(manifest_path) if os.path.isfile(
            manifest_path) else None
        if manifest is None or not _manifest_has_committed(manifest,
                                                           artifact_id):
            if not os.path.isfile(manifest_path):
                raise RecoveryError(
                    f"manifest.json missing at {manifest_path}")
            manifest = _ensure_committed_manifest(
                manifest_path, job_id, artifact_id, row,
                expected_hash, final_hash)
        _chmod_readonly(final_path)
        # Refresh commit receipt (idempotent) + write recovery evidence.
        receipt = _write_commit_receipt(
            commit_receipt_path, job_dir, job_id, row, expected_hash,
            final_hash, manifest_path, sqlite_path, idempotent_retry=True)
        recover_receipt = _write_recover_receipt(
            recover_receipt_path, job_dir, job_id, row, expected_hash,
            final_hash, path="already_committed_idempotent")
        return _result(row, expected_hash, final_hash, job_dir, job_id,
                       sqlite_path, commit_receipt_path, recover_receipt_path,
                       receipt, recover_receipt,
                       path="already_committed_idempotent")

    if state != STATE_PREPARED:
        raise RecoveryError(
            f"artifact {artifact_id} state {state!r} not PREPARED/COMMITTED;"
            " refusing recovery")

    # 2. PREPARED + Final Exists + Hash Match -> Repair Forward (Case 9 /
    #    Case 15). Filesystem Valid + Expected Hash = Truth (§41); SQLite
    #    is the lagging side, repaired forward. No Whisper re-run.
    if os.path.isfile(final_path):
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise RecoveryError(
                f"final hash {final_hash} != expected {expected_hash}:"
                " NEVER valid (§40); refusing COMMITTED transition")
        # A stray diverged tmp must not paper over the valid final.
        if os.path.isfile(tmp_path):
            tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
            if tmp_hash != expected_hash:
                raise RecoveryError(
                    f"tmp hash {tmp_hash} != expected {expected_hash};"
                    " refusing to paper over divergence")
        # Schema re-validation on the Truth bytes (fail-closed).
        try:
            from .prepare import validate_raw_artifact  # noqa: PLC0415
            with open(final_path, "rb") as fh:
                validate_raw_artifact(
                    json.loads(fh.read().decode("utf-8")))
        except ValueError as exc:
            raise RecoveryError(
                f"final schema re-validation failed: {exc}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise RecoveryError(f"final re-read failed: {exc}") from exc
        from .commit import (  # noqa: PLC0415 (reuse T06 writers, no ASR)
            _chmod_readonly,
            _ensure_committed_manifest,
            _transition_sqlite_committed,
            _write_commit_receipt,
        )

        if not os.path.isfile(manifest_path):
            raise RecoveryError(
                f"manifest.json missing at {manifest_path}")
        _ensure_committed_manifest(manifest_path, job_id, artifact_id, row,
                                   expected_hash, final_hash)
        _transition_sqlite_committed(sqlite_path, artifact_id, expected_hash)
        _chmod_readonly(final_path)
        receipt = _write_commit_receipt(
            commit_receipt_path, job_dir, job_id, row, expected_hash,
            final_hash, manifest_path, sqlite_path, idempotent_retry=False,
            repair_forward=True)
        recover_receipt = _write_recover_receipt(
            recover_receipt_path, job_dir, job_id, row, expected_hash,
            final_hash, path="prepared_final_exists_repair_forward")
        # Re-read post-recovery row for evidence.
        con2 = sqlite3.connect(sqlite_path)
        try:
            row2 = _read_artifact_row(con2, artifact_id)
        finally:
            con2.close()
        if row2 is None or row2[6] != STATE_COMMITTED:
            raise RecoveryError("post-recovery SQLite consistency failed")
        return _result(row2, expected_hash, final_hash, job_dir, job_id,
                       sqlite_path, commit_receipt_path, recover_receipt_path,
                       receipt, recover_receipt,
                       path="prepared_final_exists_repair_forward")

    # 3. PREPARED + tmp Exists + Final Missing -> 验 tmp 后继续 Commit.
    #    Delegate the rename+manifest+sqlite tail to the T06 writer so the
    #    commit order (rename -> fsync(parent) -> final verify -> manifest
    #    -> SQLite -> 0444) cannot diverge. Still zero ASR calls.
    if os.path.isfile(tmp_path):
        try:
            from .prepare import validate_raw_artifact  # noqa: PLC0415
            with open(tmp_path, "rb") as fh:
                tmp_bytes = fh.read()
            tmp_hash = "sha256:" + hashlib.sha256(tmp_bytes).hexdigest()
            if tmp_hash != expected_hash:
                raise RecoveryError(
                    f"tmp hash {tmp_hash} != expected {expected_hash}:"
                    " NEVER valid (§40); refusing Commit")
            validate_raw_artifact(json.loads(tmp_bytes.decode("utf-8")))
        except RecoveryError:
            raise
        except ValueError as exc:
            raise RecoveryError(
                f"tmp schema re-validation failed: {exc}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise RecoveryError(f"tmp re-read failed: {exc}") from exc
        from .commit import commit_raw  # noqa: PLC0415 (no ASR inside)
        committed = commit_raw(job_dir)
        recover_receipt = _write_recover_receipt(
            recover_receipt_path, job_dir, job_id, row, expected_hash,
            committed["final_hash"],
            path="prepared_tmp_only_continue_commit")
        return {
            **committed,
            "recover_receipt_path": os.path.abspath(recover_receipt_path),
            "recover_receipt": recover_receipt,
            "recovery_path": "prepared_tmp_only_continue_commit",
            "asr_calls": 0,
            "whisper_calls": 0,
        }

    # 4. PREPARED + tmp Missing + Final Missing -> cannot fabricate.
    raise RecoveryError(
        f"artifact {artifact_id} PREPARED but tmp and final both missing;"
        " refusing to fabricate bytes")


def _write_recover_receipt(recover_receipt_path: str, job_dir: str,
                           job_id: str, row, expected_hash: str,
                           final_hash: str, path: str) -> dict:
    (_rid, _owner, _atype, _ehash, _etmp, _efinal, _estate, _eat) = row
    receipt = {
        "stage": "Stage1-S1-T07",
        "state": STATE_COMMITTED,
        "artifact": FINAL_NAME,
        "artifact_id": _rid,
        "owner_id": _owner,
        "artifact_type": "raw",
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "recovery_path": path,
        "truth_model": ("Filesystem Valid + Expected Hash = Truth;"
                        " SQLite lagging side Repair Forward (§41)"),
        "job_dir": job_dir,
        "job_id": job_id,
        "asr_calls": 0,
        "whisper_calls": 0,
        "created_at": _utc_now_iso(),
    }
    _write_fsync_json(recover_receipt_path, receipt)
    return receipt


def _result(row, expected_hash: str, final_hash: str, job_dir: str,
            job_id: str, sqlite_path: str, commit_receipt_path: str,
            recover_receipt_path: str, receipt: dict,
            recover_receipt: dict, path: str) -> dict:
    (_rid, _owner, _atype, _ehash, _etmp, _efinal, _estate, _eat) = row
    return {
        "artifact_id": _rid,
        "owner_id": _owner,
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "temp_path": os.path.abspath(_etmp),
        "final_path": os.path.abspath(_efinal),
        "state": STATE_COMMITTED,
        "sqlite_path": os.path.abspath(sqlite_path),
        "receipt_path": os.path.abspath(commit_receipt_path),
        "receipt": receipt,
        "recover_receipt_path": os.path.abspath(recover_receipt_path),
        "recover_receipt": recover_receipt,
        "recovery_path": path,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T07 Recovery Repair-Forward (§40-41, no ASR)")
    parser.add_argument("--job-dir", required=True,
                        help="job dir (H2 test root)")
    args = parser.parse_args(argv)
    try:
        result = recover_raw(args.job_dir)
    except RecoveryRefused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except (RecoveryError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(result["recover_receipt"], ensure_ascii=False, indent=2))
    return EXIT_RECOVERED


if __name__ == "__main__":
    raise SystemExit(main())
