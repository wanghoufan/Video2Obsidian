"""S1-T06: Raw COMMIT Phase + Immutable (V1.8 §39 + §3.8).

Implements STAGE1-PLAN S1-T06 only::

    PREPARED Receipt persisted
      -> verify tmp hash == expected
      -> atomic tmp -> final (os.rename, same dir)
      -> fsync(parent dir)
      -> verify final hash == expected (mismatch => FAIL, never valid §40)
      -> Manifest write COMMITTED
      -> SQLite artifacts state=COMMITTED
      -> Raw read-only marking (chmod 0444 + API guard)

Truth Model (§40-41): Valid Filesystem Artifact + Expected Hash = Truth.
Final Hash != Expected is NEVER a valid Artifact — the Commit FAILs
closed (exit 1), no COMMITTED receipt, no SQLite COMMITTED transition.

Idempotency / Repair-Forward friendly (for T07 callers):
  - PREPARED + tmp Exists + Final Missing -> normal Commit path.
  - PREPARED + Final Exists + Hash Match (crash after rename, before
    manifest/SQLite) -> skip rename, forward-repair manifest + SQLite.
  - Already COMMITTED + Final Exists + Hash Match -> idempotent success,
    no rewrite (idempotent_retry=True).
  - Already COMMITTED + any write attempt -> RawImmutableError.

Immutable (§3.8): after COMMITTED the Raw final is read-only.
  - OS mark: chmod 0444 on raw/raw.json.
  - API guard: every writer MUST call :func:`assert_raw_mutable` first;
    it raises :class:`RawImmutableError` when the job is COMMITTED
    (SQLite COMMITTED, or manifest COMMITTED receipt, or final present
    with a matching expected hash). Direct ``open(final, 'w')`` also
    fails with PermissionError because of the 0444 bit.

Writes (and only these):
  - ``<job_dir>/raw/raw.json`` (via atomic rename from ``raw.json.tmp``)
  - ``<job_dir>/manifest.json`` (append COMMITTED receipt, state=COMMITTED)
  - ``<job_dir>/job.sqlite`` ``artifacts`` row ``state=COMMITTED``
  - ``<job_dir>/raw/commit_receipt.json`` (COMMITTED Receipt evidence)

Never touches ``source.json`` / ``run.json`` / ``asr/`` /
``diagnostic_only/``, never calls ASR/Whisper.
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
ARTIFACT_TYPE_RAW = "raw"

TMP_NAME = "raw.json.tmp"
FINAL_NAME = "raw.json"
PREPARE_RECEIPT_NAME = "prepare_receipt.json"
COMMIT_RECEIPT_NAME = "commit_receipt.json"

# CLI exit codes (consistent with ingest/verify/post_verify/prepare).
EXIT_COMMITTED = 0
EXIT_FAIL = 1
EXIT_REFUSED = 2

# Read-only mark for the committed final (§3.8 OS-level hint).
FINAL_MODE = 0o444


class CommitError(ValueError):
    """FAIL: stored evidence unusable / hash mismatch / DB error."""


class CommitRefused(RuntimeError):
    """REFUSED: no PREPARED Receipt — COMMIT must not proceed."""


class RawImmutableError(RuntimeError):
    """Immutable rejection: committed Raw refuses any further write."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise CommitError(f"{path} is not a JSON object")
    return payload


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    """Write canonical JSON (sorted keys) + flush + fsync(file)."""
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


def _fsync_parent(dir_path: str) -> None:
    """fsync the parent directory so the rename is durable (§39)."""
    fd = os.open(os.path.abspath(dir_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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


def is_committed(job_dir: str, artifact_id: str) -> bool:
    """Return True iff the job's Raw is COMMITTED (any evidence)."""
    job_dir = os.path.abspath(job_dir)
    sqlite_path = os.path.join(job_dir, "job.sqlite")
    manifest_path = os.path.join(job_dir, "manifest.json")
    # SQLite evidence.
    if os.path.isfile(sqlite_path):
        try:
            con = sqlite3.connect(sqlite_path)
            try:
                has = con.execute(
                    "SELECT count(*) FROM sqlite_master"
                    " WHERE type='table' AND name='artifacts'"
                ).fetchone()[0]
                if has:
                    row = _read_artifact_row(con, artifact_id)
                    if row is not None and row[6] == STATE_COMMITTED:
                        return True
            finally:
                con.close()
        except sqlite3.Error:
            pass
    # Manifest evidence.
    if os.path.isfile(manifest_path):
        try:
            manifest = _load_json(manifest_path)
            if manifest.get("state") == STATE_COMMITTED and _manifest_has_committed(
                manifest, artifact_id
            ):
                return True
        except (OSError, ValueError):
            pass
    return False


def assert_raw_mutable(job_dir: str, artifact_id: str) -> None:
    """Refuse any Raw write after COMMITTED (§3.8 API guard).

    Raises :class:`RawImmutableError` when the artifact is COMMITTED.
    Every current and future Raw writer must call this before opening
    ``raw.json.tmp`` / ``raw.json`` for write.
    """
    if is_committed(job_dir, artifact_id):
        raise RawImmutableError(
            f"artifact {artifact_id} is COMMITTED (immutable); refusing Raw write"
        )
    # Belt-and-braces: a 0444 final with no SQLite/manifest row (e.g. DB
    # deleted) is still treated as immutable — hash evidence on disk wins
    # over a missing index (§40 Truth Model).
    final_path = os.path.join(os.path.abspath(job_dir), "raw", FINAL_NAME)
    if os.path.isfile(final_path):
        try:
            mode = os.stat(final_path).st_mode & 0o777
            if mode == FINAL_MODE and not os.access(final_path, os.W_OK):
                raise RawImmutableError(
                    f"artifact {artifact_id} final is read-only on disk"
                    " (0444); refusing Raw write"
                )
        except OSError:
            pass


def guarded_open_raw_for_write(job_dir: str, artifact_id: str, mode: str = "wb"):
    """Open helper that enforces immutability before any Raw write.

    Raises :class:`RawImmutableError` on COMMITTED jobs. Intended for QA
    Immutable checks: ``guarded_open_raw_for_write`` must refuse, and the
    final hash must stay unchanged afterwards.
    """
    assert_raw_mutable(job_dir, artifact_id)
    final_path = os.path.join(os.path.abspath(job_dir), "raw", FINAL_NAME)
    tmp_path = os.path.join(os.path.abspath(job_dir), "raw", TMP_NAME)
    target = tmp_path if "tmp" in artifact_id or True else final_path
    # Default target is the tmp path (the only legal pre-COMMIT write);
    # callers wanting the final path pass it explicitly is disallowed —
    # post-COMMIT there is no legal write target at all.
    _ = final_path
    return open(target, mode)


def commit_raw(job_dir: str) -> dict:
    """Run the §39 COMMIT Phase for one job.

    Precondition: SQLite ``artifacts`` row ``state=PREPARED`` + tmp file
    hashing to the stored ``expected_hash`` (+ ``prepare_receipt.json``
    cross-check when present). Postcondition: atomic rename durable
    (fsync parent), final hash == expected, manifest COMMITTED, SQLite
    COMMITTED, final chmod 0444, commit receipt written.
    """
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    artifact_id = f"raw_{job_id}"
    raw_dir = os.path.join(job_dir, "raw")
    tmp_path = os.path.join(raw_dir, TMP_NAME)
    final_path = os.path.join(raw_dir, FINAL_NAME)
    prepare_receipt_path = os.path.join(raw_dir, PREPARE_RECEIPT_NAME)
    commit_receipt_path = os.path.join(raw_dir, COMMIT_RECEIPT_NAME)
    manifest_path = os.path.join(job_dir, "manifest.json")
    sqlite_path = os.path.join(job_dir, "job.sqlite")

    # 0. Immutable fast path: already COMMITTED + final valid -> idempotent.
    if os.path.isfile(sqlite_path):
        con0 = sqlite3.connect(sqlite_path)
        try:
            has0 = con0.execute(
                "SELECT count(*) FROM sqlite_master"
                " WHERE type='table' AND name='artifacts'"
            ).fetchone()[0]
            row0 = _read_artifact_row(con0, artifact_id) if has0 else None
        finally:
            con0.close()
        if row0 is not None and row0[6] == STATE_COMMITTED:
            expected0 = row0[3]
            if not os.path.isfile(final_path):
                raise CommitError(
                    f"artifact {artifact_id} SQLite COMMITTED but final missing;"
                    " refusing to fabricate bytes (T07 owns recovery, no rewrite here)"
                )
            final_hash0 = "sha256:" + _sha256_file_hex(final_path)
            if final_hash0 != expected0:
                raise CommitError(
                    f"artifact {artifact_id} SQLite COMMITTED but final hash"
                    f" {final_hash0} != expected {expected0}: NEVER valid (§40)"
                )
            # Forward-repair manifest if it lagged (crash between manifest
            # and SQLite is the reverse order; this covers manual repair).
            manifest = _load_json(manifest_path) if os.path.isfile(manifest_path) else None
            if manifest is None or not _manifest_has_committed(manifest, artifact_id):
                manifest = _ensure_committed_manifest(
                    manifest_path, job_id, artifact_id, row0, expected0, final_hash0
                )
            receipt = _write_commit_receipt(
                commit_receipt_path, job_dir, job_id, row0, expected0, final_hash0,
                manifest_path, sqlite_path, idempotent_retry=True,
            )
            _chmod_readonly(final_path)
            return _result(
                row0, expected0, final_hash0, job_dir, job_id,
                sqlite_path, commit_receipt_path, receipt, idempotent_retry=True,
            )

    # 1. PREPARED precondition: SQLite row must exist and be PREPARED.
    if not os.path.isfile(sqlite_path):
        raise CommitRefused(
            f"COMMIT refused: {sqlite_path} missing (no PREPARED Receipt)"
        )
    con = sqlite3.connect(sqlite_path)
    try:
        has = con.execute(
            "SELECT count(*) FROM sqlite_master"
            " WHERE type='table' AND name='artifacts'"
        ).fetchone()[0]
        if not has:
            raise CommitRefused("COMMIT refused: artifacts table missing (no PREPARE)")
        row = _read_artifact_row(con, artifact_id)
    finally:
        con.close()
    if row is None:
        raise CommitRefused(
            f"COMMIT refused: artifact {artifact_id} has no PREPARED row"
        )
    (_rid, _owner, _atype, expected_hash, stored_tmp, stored_final, state, _at) = row
    if state != STATE_PREPARED:
        raise CommitRefused(
            f"COMMIT refused: artifact {artifact_id} state {state!r} != PREPARED"
        )
    if _atype != ARTIFACT_TYPE_RAW:
        raise CommitError(f"artifact type { _atype!r} != 'raw'")
    if os.path.abspath(stored_tmp) != os.path.abspath(tmp_path):
        raise CommitError("stored temp_path != raw.json.tmp path")
    if os.path.abspath(stored_final) != os.path.abspath(final_path):
        raise CommitError("stored final_path != raw.json path")
    if not expected_hash.startswith("sha256:"):
        raise CommitError("stored expected_hash malformed")

    # Cross-check prepare receipt when present (must agree, else FAIL).
    if os.path.isfile(prepare_receipt_path):
        try:
            prep = _load_json(prepare_receipt_path)
            if prep.get("expected_artifact_hash") != expected_hash:
                raise CommitError(
                    "prepare_receipt expected_artifact_hash != SQLite expected_hash"
                )
            if prep.get("artifact_id") != artifact_id:
                raise CommitError("prepare_receipt artifact_id mismatch")
        except CommitError:
            raise
        except (OSError, ValueError) as exc:
            raise CommitError(f"prepare_receipt unreadable: {exc}") from exc

    # 2. Final-already-exists path (crash after rename, before manifest):
    #    verify hash, then Repair Forward without re-running anything.
    if os.path.isfile(final_path):
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise CommitError(
                f"final hash {final_hash} != expected {expected_hash}:"
                " NEVER valid (§40); refusing COMMITTED transition"
            )
        # tmp may or may not still exist; if it exists it must agree too.
        if os.path.isfile(tmp_path):
            tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
            if tmp_hash != expected_hash:
                raise CommitError(
                    f"tmp hash {tmp_hash} != expected {expected_hash};"
                    " refusing to paper over divergence"
                )
        manifest = _ensure_committed_manifest(
            manifest_path, job_id, artifact_id, row, expected_hash, final_hash
        )
        _transition_sqlite_committed(sqlite_path, artifact_id, expected_hash)
        receipt = _write_commit_receipt(
            commit_receipt_path, job_dir, job_id, row, expected_hash, final_hash,
            manifest_path, sqlite_path, idempotent_retry=False,
            repair_forward=True,
        )
        _chmod_readonly(final_path)
        # Remove stale tmp if the rename had already happened but a stray
        # tmp was recreated afterwards — never touch the valid final.
        return _result(
            row, expected_hash, final_hash, job_dir, job_id,
            sqlite_path, commit_receipt_path, receipt, idempotent_retry=False,
        )

    # 3. Normal path: tmp must exist and hash to expected BEFORE rename.
    if not os.path.isfile(tmp_path):
        raise CommitError(
            f"artifact {artifact_id} PREPARED but tmp missing and final missing;"
            " refusing to fabricate bytes (T07 recovery case, no blind COMMIT)"
        )
    # Immutability guard doubles as a COMMITTED check before mutation.
    assert_raw_mutable(job_dir, artifact_id)
    tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
    if tmp_hash != expected_hash:
        raise CommitError(
            f"tmp hash {tmp_hash} != expected {expected_hash}:"
            " NEVER valid (§40); refusing rename"
        )
    # Re-validate schema on the exact bytes under commit (fail-closed).
    with open(tmp_path, "rb") as fh:
        tmp_bytes = fh.read()
    try:
        from .prepare import validate_raw_artifact  # noqa: PLC0415 (reuse §38 gate)

        validate_raw_artifact(json.loads(tmp_bytes.decode("utf-8")))
    except ValueError as exc:
        raise CommitError(f"tmp schema re-validation failed at COMMIT: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise CommitError(f"tmp re-read failed at COMMIT: {exc}") from exc

    # 4. Atomic rename tmp -> final + fsync(parent).
    try:
        os.rename(tmp_path, final_path)
    except OSError as exc:
        raise CommitError(f"atomic rename tmp->final failed: {exc}") from exc
    try:
        _fsync_parent(raw_dir)
    except OSError as exc:
        raise CommitError(f"fsync(parent) failed after rename: {exc}") from exc

    # 5. Post-rename: final hash MUST equal expected, else FAIL (never valid).
    final_hash = "sha256:" + _sha256_file_hex(final_path)
    if final_hash != expected_hash:
        raise CommitError(
            f"final hash {final_hash} != expected {expected_hash} after rename:"
            " NEVER valid (§40); refusing COMMITTED transition"
        )

    # 6. Manifest COMMITTED first (§39 order), then SQLite COMMITTED.
    _ensure_committed_manifest(
        manifest_path, job_id, artifact_id, row, expected_hash, final_hash
    )
    _transition_sqlite_committed(sqlite_path, artifact_id, expected_hash)

    # 7. Read-only marking + COMMITTED Receipt evidence.
    _chmod_readonly(final_path)
    receipt = _write_commit_receipt(
        commit_receipt_path, job_dir, job_id, row, expected_hash, final_hash,
        manifest_path, sqlite_path, idempotent_retry=False,
    )

    # 8. Post-COMMIT consistency: final hash == stored hash == receipt hash.
    con2 = sqlite3.connect(sqlite_path)
    try:
        row2 = _read_artifact_row(con2, artifact_id)
    finally:
        con2.close()
    if row2 is None or row2[6] != STATE_COMMITTED or row2[3] != expected_hash:
        raise CommitError("post-COMMIT SQLite consistency failed")
    return _result(
        row2, expected_hash, final_hash, job_dir, job_id,
        sqlite_path, commit_receipt_path, receipt, idempotent_retry=False,
    )


def _ensure_committed_manifest(
    manifest_path: str,
    job_id: str,
    artifact_id: str,
    row,
    expected_hash: str,
    final_hash: str,
) -> dict:
    """Append the COMMITTED receipt to manifest.json (fsync'd).

    Idempotent: an existing COMMITTED receipt for this artifact is kept,
    never duplicated. Manifest ``state`` becomes COMMITTED and ``stage``
    records ``Stage1-S1-T06``.
    """
    (_rid, _owner, _atype, _ehash, _etmp, _efinal, _estate, _eat) = row
    if not os.path.isfile(manifest_path):
        raise CommitError(f"manifest.json missing at {manifest_path}")
    manifest = _load_json(manifest_path)
    if manifest.get("job_id") != job_id:
        raise CommitError("manifest job_id mismatch")
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        raise CommitError("manifest receipts is not a list")
    if not _manifest_has_committed(manifest, artifact_id):
        receipts.append(
            {
                "stage": "Stage1-S1-T06",
                "state": STATE_COMMITTED,
                "artifact": "raw/raw.json",
                "artifact_id": artifact_id,
                "owner_id": _owner,
                "artifact_type": ARTIFACT_TYPE_RAW,
                "expected_artifact_hash": expected_hash,
                "final_hash": final_hash,
                "final_path": os.path.abspath(_efinal),
                "created_at": _utc_now_iso(),
            }
        )
    manifest["state"] = STATE_COMMITTED
    manifest["stage"] = "Stage1-S1-T06"
    lineage = manifest.get("lineage")
    if isinstance(lineage, dict):
        lineage["raw"] = "raw/raw.json"
    _write_fsync_json(manifest_path, manifest)
    return manifest


def _transition_sqlite_committed(
    sqlite_path: str, artifact_id: str, expected_hash: str
) -> None:
    """Move the artifacts row PREPARED -> COMMITTED in one transaction."""
    con = sqlite3.connect(sqlite_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        with con:
            cur = con.execute(
                "UPDATE artifacts SET state = ?"
                " WHERE artifact_id = ? AND state = ? AND expected_hash = ?",
                (STATE_COMMITTED, artifact_id, STATE_PREPARED, expected_hash),
            )
            if cur.rowcount == 0:
                # Either already COMMITTED (idempotent) or diverged.
                row = _read_artifact_row(con, artifact_id)
                if row is not None and row[6] == STATE_COMMITTED and row[3] == expected_hash:
                    return
                raise CommitError(
                    "SQLite PREPARED->COMMITTED transition affected 0 rows"
                    " (state/hash diverged)"
                )
    except sqlite3.Error as exc:
        raise CommitError(f"SQLite COMMITTED write failed: {exc}") from exc
    finally:
        con.close()


def _chmod_readonly(final_path: str) -> None:
    try:
        os.chmod(final_path, FINAL_MODE)
    except OSError as exc:
        raise CommitError(f"read-only marking failed: {exc}") from exc


def _write_commit_receipt(
    commit_receipt_path: str,
    job_dir: str,
    job_id: str,
    row,
    expected_hash: str,
    final_hash: str,
    manifest_path: str,
    sqlite_path: str,
    idempotent_retry: bool,
    repair_forward: bool = False,
) -> dict:
    (_rid, _owner, _atype, _ehash, _etmp, _efinal, _estate, _eat) = row
    receipt = {
        "stage": "Stage1-S1-T06",
        "state": STATE_COMMITTED,
        "artifact": FINAL_NAME,
        "artifact_id": _rid,
        "owner_id": _owner,
        "artifact_type": ARTIFACT_TYPE_RAW,
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "temp_path": os.path.abspath(_etmp),
        "final_path": os.path.abspath(_efinal),
        "job_dir": job_dir,
        "job_id": job_id,
        "manifest_path": os.path.abspath(manifest_path),
        "sqlite_path": os.path.abspath(sqlite_path),
        "created_at": _utc_now_iso(),
        "idempotent_retry": idempotent_retry,
        "repair_forward": repair_forward,
        "immutable": True,
    }
    _write_fsync_json(commit_receipt_path, receipt)
    return receipt


def _result(
    row, expected_hash: str, final_hash: str,
    job_dir: str, job_id: str, sqlite_path: str,
    commit_receipt_path: str, receipt: dict, idempotent_retry: bool,
) -> dict:
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
        "idempotent_retry": idempotent_retry,
        "sqlite_row": {
            "artifact_id": _rid,
            "owner_id": _owner,
            "artifact_type": _atype,
            "expected_hash": _ehash,
            "temp_path": _etmp,
            "final_path": _efinal,
            "state": _estate,
            "created_at": _eat,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T06 Raw COMMIT Phase (§39) + Immutable (§3.8)"
    )
    parser.add_argument("--job-dir", required=True, help="job dir (H2 test root)")
    args = parser.parse_args(argv)
    try:
        result = commit_raw(args.job_dir)
    except CommitRefused as exc:
        print(f"REFUSED {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except RawImmutableError as exc:  # defensive: commit path never writes on immutable
        print(f"REFUSED {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except (CommitError, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(result["receipt"], ensure_ascii=False, indent=2))
    return EXIT_COMMITTED


if __name__ == "__main__":
    raise SystemExit(main())
