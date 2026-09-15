"""S3-T01: shared two-phase commit helper for Normalized/Rendered artifacts.

Implements STAGE3-PLAN S3-T01 only (V1.8 ``# 37`` / ``# 38`` / ``# 39`` /
``# 40`` / ``# 41``, applied to the Stage3 derived artifacts of ``# 36``)::

    artifact.tmp -> flush -> fsync(file) -> parse/schema validation
      -> expected_artifact_hash
      -> central artifacts row (status=PREPARED) -> COMMIT transaction
      -> atomic rename tmp -> final -> fsync(parent)
      -> final hash == expected (mismatch => NEVER valid, ``# 40``)
      -> Manifest COMMITTED Receipt -> SQLite status=COMMITTED

Semantics mirror ``stage1.prepare`` / ``stage1.commit`` (read as the
reference, never modified here) with two deliberate differences:

* the workflow index is the **central** ``<data_root>/data/state.db``
  ``artifacts`` table (Stage2 DDL shape: ``artifact_id / source_id /
  run_id / artifact_type / expected_hash / status / path / created_at /
  completed_at``), because Stage3 revisions are derivation state, not
  per-job Raw evidence (per-job ``job.sqlite`` and the Stage1 manifest
  *state* are left untouched — receipts are only appended);
* the caller-supplied ``con`` MUST come from ``stage2.store.open_db``
  (lock-gated); this module performs no lock handling itself.

Writes (and only these, all under ``<job_dir>``):

* ``<final>.tmp`` (transient), ``<final>`` (via atomic rename only),
* ``<final>.prepare_receipt.json`` (PREPARED evidence),
* ``<final>.commit_receipt.json`` (COMMITTED evidence),
* ``<final>.recover_receipt.json`` (recovery evidence, via recover only),
* appends to ``<job_dir>/manifest.json`` ``receipts`` (never rewrites a
  history entry, never touches top-level ``state``/``stage``),
* central ``artifacts`` row ``PREPARED -> COMMITTED``.

Recovery (``# 40`` / ``# 41``) owns three branches; every success dict
carries ``whisper_calls == 0`` (this module has no transcription
engine import by construction).

STOP EXPANSION: no publish/archive semantics live here; no Stage4+
table is written.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3

STATE_PREPARED = "PREPARED"
STATE_COMMITTED = "COMMITTED"

ARTIFACT_TYPE_NORMALIZED = "normalized"
ARTIFACT_TYPE_RENDERED = "rendered"
ALLOWED_ARTIFACT_TYPES = (ARTIFACT_TYPE_NORMALIZED, ARTIFACT_TYPE_RENDERED)

# Subdir allowlist per artifact type (V1.8 # 36 namespace).
TYPE_SUBDIR = {
    ARTIFACT_TYPE_NORMALIZED: "normalized",
    ARTIFACT_TYPE_RENDERED: "render",
}

TMP_SUFFIX = ".tmp"
PREPARE_RECEIPT_SUFFIX = ".prepare_receipt.json"
COMMIT_RECEIPT_SUFFIX = ".commit_receipt.json"
RECOVER_RECEIPT_SUFFIX = ".recover_receipt.json"

# Read-only mark for committed derived finals (same hint as Raw, # 3.8).
FINAL_MODE = 0o444


class ArtifactError(ValueError):
    """FAIL: stored evidence unusable / DB error (fail-closed)."""


class ArtifactRefused(RuntimeError):
    """REFUSED: no PREPARED evidence — commit/recovery must not proceed."""


class ArtifactInvalid(ArtifactError):
    """FAIL: hash mismatch — NEVER a valid artifact (# 40)."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


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


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ArtifactError("%s is not a JSON object" % (path,))
    return payload


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


def _fsync_parent(dir_path: str) -> None:
    fd = os.open(os.path.abspath(dir_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_normalized_bytes(data: bytes) -> dict:
    """Parse + schema-gate a Normalized artifact (``# 38`` validation)."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArtifactError("normalized bytes are not valid JSON: %s" % (exc,))
    if not isinstance(payload, dict):
        raise ArtifactError("normalized artifact is not a JSON object")
    missing = [
        k
        for k in (
            "artifact",
            "artifact_version",
            "normalization_revision_id",
            "raw_artifact_id",
            "normalization_profile_hash",
            "segments",
        )
        if k not in payload
    ]
    if missing:
        raise ArtifactError(
            "normalized schema validation failed, missing: " + ", ".join(missing)
        )
    if payload.get("artifact") != ARTIFACT_TYPE_NORMALIZED:
        raise ArtifactError("normalized schema: artifact != 'normalized'")
    if payload.get("artifact_version") != 1:
        raise ArtifactError("normalized schema: artifact_version != 1")
    if not isinstance(payload.get("segments"), list):
        raise ArtifactError("normalized schema: segments must be a list")
    return payload


def validate_rendered_bytes(data: bytes) -> str:
    """Decode + non-empty gate for a Rendered Markdown artifact."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError("rendered bytes are not valid UTF-8: %s" % (exc,))
    if not text.strip():
        raise ArtifactError("rendered schema validation failed: empty markdown")
    return text


_DEFAULT_VALIDATORS = {
    ARTIFACT_TYPE_NORMALIZED: validate_normalized_bytes,
    ARTIFACT_TYPE_RENDERED: validate_rendered_bytes,
}


def _resolve_paths(job_dir: str, artifact_type: str, final_relpath: str):
    job_dir = os.path.abspath(job_dir)
    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ArtifactError("unknown artifact_type %r" % (artifact_type,))
    final_path = os.path.abspath(os.path.join(job_dir, final_relpath))
    if os.path.commonpath([job_dir, final_path]) != job_dir:
        raise ArtifactError("final_relpath escapes job_dir: %r" % (final_relpath,))
    want_sub = TYPE_SUBDIR[artifact_type]
    rel = os.path.relpath(final_path, job_dir)
    if rel != final_relpath or not rel.startswith(want_sub + os.sep):
        raise ArtifactError(
            "%s artifact must live under %s/, got %r"
            % (artifact_type, want_sub, final_relpath)
        )
    if artifact_type == ARTIFACT_TYPE_RENDERED and not final_path.endswith(".md"):
        raise ArtifactError("rendered final must end with .md: %r" % (final_relpath,))
    if artifact_type == ARTIFACT_TYPE_NORMALIZED and not final_path.endswith(".json"):
        raise ArtifactError(
            "normalized final must end with .json: %r" % (final_relpath,)
        )
    return job_dir, final_path, final_path + TMP_SUFFIX


def _read_row(con: sqlite3.Connection, artifact_id: str):
    return con.execute(
        "SELECT artifact_id, source_id, run_id, artifact_type, expected_hash,"
        " status, path, created_at, completed_at FROM artifacts"
        " WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()


def _row_get(row, key: str):
    if isinstance(row, sqlite3.Row):
        return row[key]
    cols = (
        "artifact_id",
        "source_id",
        "run_id",
        "artifact_type",
        "expected_hash",
        "status",
        "path",
        "created_at",
        "completed_at",
    )
    return row[cols.index(key)]


def prepare_artifact(
    con: sqlite3.Connection,
    job_dir: str,
    artifact_type: str,
    final_relpath: str,
    content_bytes: bytes,
    artifact_id: str,
    source_id: str | None = None,
    run_id: str | None = None,
    validate=None,
) -> dict:
    """Run the ``# 38`` PREPARE phase for one derived artifact.

    ``con`` must be a lock-gated central-DB connection (see
    ``stage2.store.open_db``). ``content_bytes`` are the exact final
    bytes (canonical JSON for normalized, UTF-8 markdown for rendered).
    """
    if not artifact_id or not isinstance(artifact_id, str):
        raise ArtifactError("artifact_id must be a non-empty string")
    if not isinstance(content_bytes, (bytes, bytearray)) or not content_bytes:
        raise ArtifactError("content_bytes must be non-empty bytes")
    content_bytes = bytes(content_bytes)
    job_dir, final_path, tmp_path = _resolve_paths(
        job_dir, artifact_type, final_relpath
    )
    job_id = os.path.basename(job_dir)
    check = validate or _DEFAULT_VALIDATORS[artifact_type]
    try:
        check(content_bytes)
    except ArtifactError:
        raise
    except (ValueError, TypeError) as exc:
        raise ArtifactError("pre-write validation failed: %s" % (exc,))

    # 0. Pre-write idempotency gate (BEFORE touching tmp): a PREPARED row
    #    whose tmp still hashes to the stored expected_hash is an
    #    idempotent retry; a COMMITTED row refuses re-PREPARE (immutable).
    existing = _read_row(con, artifact_id)
    if existing is not None:
        state = _row_get(existing, "status")
        stored = _row_get(existing, "expected_hash")
        if state == STATE_COMMITTED:
            raise ArtifactError(
                "artifact %s already COMMITTED (immutable); refusing re-PREPARE"
                % (artifact_id,)
            )
        if state == STATE_PREPARED and os.path.isfile(tmp_path):
            with open(tmp_path, "rb") as fh:
                disk = fh.read()
            if "sha256:" + _sha256_hex(disk) == stored:
                check(disk)
                receipt = _write_prepare_receipt(
                    final_path, job_dir, job_id, artifact_id, artifact_type,
                    final_relpath, stored, source_id or _row_get(existing, "source_id"),
                    run_id or _row_get(existing, "run_id"),
                    _row_get(existing, "created_at"), idempotent_retry=True,
                )
                return _result(
                    existing if not isinstance(existing, sqlite3.Row) else tuple(existing),
                    stored, job_dir, job_id, final_path, tmp_path, receipt,
                    idempotent_retry=True,
                )
        raise ArtifactError(
            "artifact %s already PREPARED but tmp is missing/diverged; "
            "refusing overwrite — recovery owns this state" % (artifact_id,)
        )

    # 1-3. tmp write -> flush -> fsync(file).
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    with open(tmp_path, "wb") as fh:
        fh.write(content_bytes)
        fh.flush()
        os.fsync(fh.fileno())

    # 4. Re-parse + mandatory schema validation on the fsync'd bytes.
    try:
        with open(tmp_path, "rb") as fh:
            tmp_bytes = fh.read()
        if tmp_bytes != content_bytes:
            raise ArtifactError("tmp file bytes differ from supplied bytes")
        check(tmp_bytes)
    except ArtifactError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    except (OSError, ValueError) as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ArtifactError("tmp re-parse failed: %s" % (exc,))

    # 5. expected_artifact_hash over the exact tmp bytes.
    expected_hash = "sha256:" + _sha256_hex(tmp_bytes)
    created_at = _utc_now_iso()

    # 6-7. Central artifacts row status=PREPARED -> COMMIT transaction.
    try:
        with con:
            con.execute(
                "INSERT INTO artifacts (artifact_id, source_id, run_id,"
                " artifact_type, expected_hash, status, path, created_at,"
                " completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    artifact_id, source_id, run_id, artifact_type,
                    expected_hash, STATE_PREPARED, final_path, created_at, None,
                ),
            )
        row = _read_row(con, artifact_id)
    except sqlite3.IntegrityError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ArtifactError("SQLite PREPARED write failed: %s" % (exc,))
    except sqlite3.Error as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ArtifactError("SQLite PREPARED write failed: %s" % (exc,))

    if row is None:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ArtifactError("expected hash not persisted: artifacts row missing")

    # 8. Post-COMMIT consistency: row vs tmp must agree; final must not
    #    exist yet (that is the COMMIT phase's job).
    errors = []
    if _row_get(row, "expected_hash") != expected_hash:
        errors.append("stored expected_hash != computed hash")
    if _row_get(row, "status") != STATE_PREPARED:
        errors.append("stored status != PREPARED")
    if os.path.abspath(_row_get(row, "path")) != final_path:
        errors.append("stored path != final_path")
    if not os.path.isfile(tmp_path):
        errors.append("tmp file missing after COMMIT")
    else:
        with open(tmp_path, "rb") as fh:
            if "sha256:" + _sha256_hex(fh.read()) != expected_hash:
                errors.append("tmp file hash != stored expected_hash")
    if os.path.isfile(final_path):
        errors.append("final already exists; PREPARE must not create it")
    if errors:
        raise ArtifactError("SQLite vs tmp inconsistent: " + "; ".join(errors))

    # 9. PREPARED Receipt evidence (NOT the final artifact, NOT manifest).
    receipt = _write_prepare_receipt(
        final_path, job_dir, job_id, artifact_id, artifact_type, final_relpath,
        expected_hash, source_id, run_id, _row_get(row, "created_at"),
        idempotent_retry=False,
    )
    return _result(
        row if not isinstance(row, sqlite3.Row) else tuple(row),
        expected_hash, job_dir, job_id, final_path, tmp_path, receipt,
        idempotent_retry=False,
    )


def _write_prepare_receipt(
    final_path, job_dir, job_id, artifact_id, artifact_type, final_relpath,
    expected_hash, source_id, run_id, created_at, idempotent_retry,
) -> dict:
    receipt = {
        "stage": "Stage3-S3-T01",
        "state": STATE_PREPARED,
        "artifact": final_relpath,
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "expected_artifact_hash": expected_hash,
        "temp_path": os.path.abspath(final_path + TMP_SUFFIX),
        "final_path": os.path.abspath(final_path),
        "job_dir": job_dir,
        "job_id": job_id,
        "source_id": source_id,
        "run_id": run_id,
        "created_at": created_at,
        "idempotent_retry": idempotent_retry,
    }
    _write_fsync_json(final_path + PREPARE_RECEIPT_SUFFIX, receipt)
    return receipt


def _result(row, expected_hash, job_dir, job_id, final_path, tmp_path,
            receipt, idempotent_retry) -> dict:
    cols = (
        "artifact_id", "source_id", "run_id", "artifact_type", "expected_hash",
        "status", "path", "created_at", "completed_at",
    )
    vals = dict(zip(cols, tuple(row)))
    return {
        "artifact_id": vals["artifact_id"],
        "artifact_type": vals["artifact_type"],
        "expected_artifact_hash": expected_hash,
        "temp_path": os.path.abspath(tmp_path),
        "final_path": os.path.abspath(final_path),
        "state": vals["status"],
        "job_dir": job_dir,
        "job_id": job_id,
        "source_id": vals["source_id"],
        "run_id": vals["run_id"],
        "receipt_path": os.path.abspath(final_path + PREPARE_RECEIPT_SUFFIX),
        "receipt": receipt,
        "idempotent_retry": idempotent_retry,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _manifest_has_committed(manifest: dict, artifact_id: str) -> bool:
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        return False
    return any(
        isinstance(r, dict)
        and r.get("state") == STATE_COMMITTED
        and r.get("artifact_id") == artifact_id
        for r in receipts
    )


def _ensure_committed_manifest(
    manifest_path: str, job_id: str, artifact_id: str, artifact_type: str,
    final_relpath: str, expected_hash: str, final_hash: str,
) -> dict:
    """Append the COMMITTED receipt (additive-only).

    Never touches top-level ``state``/``stage`` (those track the Stage1
    Raw); never rewrites an existing history entry.
    """
    if not os.path.isfile(manifest_path):
        raise ArtifactError("manifest.json missing at %s" % (manifest_path,))
    manifest = _load_json(manifest_path)
    if manifest.get("job_id") != job_id:
        raise ArtifactError("manifest job_id mismatch")
    receipts = manifest.get("receipts")
    if not isinstance(receipts, list):
        raise ArtifactError("manifest receipts is not a list")
    if not _manifest_has_committed(manifest, artifact_id):
        receipts.append(
            {
                "stage": "Stage3-S3-T01",
                "state": STATE_COMMITTED,
                "artifact": final_relpath,
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "expected_artifact_hash": expected_hash,
                "final_hash": final_hash,
                "final_path": os.path.abspath(
                    os.path.join(os.path.dirname(manifest_path), final_relpath)
                ),
                "created_at": _utc_now_iso(),
            }
        )
    _write_fsync_json(manifest_path, manifest)
    return manifest


def _transition_sqlite_committed(
    con: sqlite3.Connection, artifact_id: str, expected_hash: str
) -> None:
    with con:
        cur = con.execute(
            "UPDATE artifacts SET status = ?, completed_at = ?"
            " WHERE artifact_id = ? AND status = ? AND expected_hash = ?",
            (STATE_COMMITTED, _utc_now_iso(), artifact_id,
             STATE_PREPARED, expected_hash),
        )
        if cur.rowcount == 0:
            row = _read_row(con, artifact_id)
            if (
                row is not None
                and _row_get(row, "status") == STATE_COMMITTED
                and _row_get(row, "expected_hash") == expected_hash
            ):
                return
            raise ArtifactError(
                "SQLite PREPARED->COMMITTED transition affected 0 rows"
                " (state/hash diverged)"
            )


def _chmod_readonly(final_path: str) -> None:
    try:
        os.chmod(final_path, FINAL_MODE)
    except OSError as exc:
        raise ArtifactError("read-only marking failed: %s" % (exc,))


def _write_commit_receipt(final_path, job_dir, job_id, row, expected_hash,
                          final_hash, manifest_path, idempotent_retry,
                          repair_forward=False) -> dict:
    cols = (
        "artifact_id", "source_id", "run_id", "artifact_type", "expected_hash",
        "status", "path", "created_at", "completed_at",
    )
    vals = dict(zip(cols, tuple(row)))
    receipt = {
        "stage": "Stage3-S3-T01",
        "state": STATE_COMMITTED,
        "artifact": os.path.relpath(os.path.abspath(final_path),
                                    os.path.abspath(job_dir)),
        "artifact_id": vals["artifact_id"],
        "artifact_type": vals["artifact_type"],
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "temp_path": os.path.abspath(final_path + TMP_SUFFIX),
        "final_path": os.path.abspath(final_path),
        "job_dir": job_dir,
        "job_id": job_id,
        "manifest_path": os.path.abspath(manifest_path),
        "created_at": _utc_now_iso(),
        "idempotent_retry": idempotent_retry,
        "repair_forward": repair_forward,
    }
    _write_fsync_json(final_path + COMMIT_RECEIPT_SUFFIX, receipt)
    return receipt


def commit_artifact(con: sqlite3.Connection, job_dir: str,
                    artifact_id: str) -> dict:
    """Run the ``# 39`` COMMIT phase for one PREPARED artifact."""
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)
    manifest_path = os.path.join(job_dir, "manifest.json")

    row = _read_row(con, artifact_id)
    if row is None:
        raise ArtifactRefused(
            "COMMIT refused: artifact %s has no PREPARED row" % (artifact_id,)
        )
    vals = dict(zip(
        ("artifact_id", "source_id", "run_id", "artifact_type", "expected_hash",
         "status", "path", "created_at", "completed_at"),
        tuple(row),
    ))
    if vals["status"] != STATE_PREPARED:
        raise ArtifactRefused(
            "COMMIT refused: artifact %s status %r != PREPARED"
            % (artifact_id, vals["status"])
        )
    expected_hash = vals["expected_hash"]
    if not expected_hash or not expected_hash.startswith("sha256:"):
        raise ArtifactError("stored expected_hash malformed")
    final_path = os.path.abspath(vals["path"])
    if os.path.commonpath([job_dir, final_path]) != job_dir:
        raise ArtifactError("stored path escapes job_dir")
    final_relpath = os.path.relpath(final_path, job_dir)
    tmp_path = final_path + TMP_SUFFIX
    artifact_type = vals["artifact_type"]
    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ArtifactError("stored artifact_type %r unknown" % (artifact_type,))

    # Cross-check the PREPARED receipt when present.
    prep_path = final_path + PREPARE_RECEIPT_SUFFIX
    if os.path.isfile(prep_path):
        try:
            prep = _load_json(prep_path)
            if prep.get("expected_artifact_hash") != expected_hash:
                raise ArtifactError(
                    "prepare receipt hash != SQLite expected_hash"
                )
            if prep.get("artifact_id") != artifact_id:
                raise ArtifactError("prepare receipt artifact_id mismatch")
        except ArtifactError:
            raise
        except (OSError, ValueError) as exc:
            raise ArtifactError("prepare receipt unreadable: %s" % (exc,))

    check = _DEFAULT_VALIDATORS[artifact_type]

    # Final-already-exists path (crash after rename, before manifest):
    # verify hash, then Repair Forward without re-running anything.
    if os.path.isfile(final_path):
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise ArtifactInvalid(
                "final hash %s != expected %s: NEVER valid (# 40); "
                "refusing COMMITTED transition" % (final_hash, expected_hash)
            )
        if os.path.isfile(tmp_path):
            tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
            if tmp_hash != expected_hash:
                raise ArtifactError(
                    "tmp hash diverged while final is valid; refusing to"
                    " paper over divergence"
                )
        with open(final_path, "rb") as fh:
            check(fh.read())
        _ensure_committed_manifest(
            manifest_path, job_id, artifact_id, artifact_type, final_relpath,
            expected_hash, final_hash,
        )
        _transition_sqlite_committed(con, artifact_id, expected_hash)
        row2 = _read_row(con, artifact_id)
        receipt = _write_commit_receipt(
            final_path, job_dir, job_id, tuple(row2), expected_hash,
            final_hash, manifest_path, idempotent_retry=False,
            repair_forward=True,
        )
        _chmod_readonly(final_path)
        return _commit_result(
            row2, expected_hash, final_hash, job_dir, job_id, final_path,
            receipt, repair_forward=True,
        )

    # Normal path: tmp must exist and hash to expected BEFORE rename.
    if not os.path.isfile(tmp_path):
        raise ArtifactError(
            "artifact %s PREPARED but tmp missing and final missing; "
            "refusing to fabricate bytes" % (artifact_id,)
        )
    tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
    if tmp_hash != expected_hash:
        raise ArtifactInvalid(
            "tmp hash %s != expected %s: NEVER valid (# 40); refusing rename"
            % (tmp_hash, expected_hash)
        )
    with open(tmp_path, "rb") as fh:
        check(fh.read())

    try:
        os.rename(tmp_path, final_path)
    except OSError as exc:
        raise ArtifactError("atomic rename tmp->final failed: %s" % (exc,))
    try:
        _fsync_parent(os.path.dirname(final_path))
    except OSError as exc:
        raise ArtifactError("fsync(parent) failed after rename: %s" % (exc,))

    final_hash = "sha256:" + _sha256_file_hex(final_path)
    if final_hash != expected_hash:
        raise ArtifactInvalid(
            "final hash %s != expected %s after rename: NEVER valid (# 40)"
            % (final_hash, expected_hash)
        )

    _ensure_committed_manifest(
        manifest_path, job_id, artifact_id, artifact_type, final_relpath,
        expected_hash, final_hash,
    )
    _transition_sqlite_committed(con, artifact_id, expected_hash)
    row2 = _read_row(con, artifact_id)
    _chmod_readonly(final_path)
    receipt = _write_commit_receipt(
        final_path, job_dir, job_id, tuple(row2), expected_hash, final_hash,
        manifest_path, idempotent_retry=False,
    )

    row3 = _read_row(con, artifact_id)
    if (
        row3 is None
        or _row_get(row3, "status") != STATE_COMMITTED
        or _row_get(row3, "expected_hash") != expected_hash
    ):
        raise ArtifactError("post-COMMIT SQLite consistency failed")
    return _commit_result(
        row3, expected_hash, final_hash, job_dir, job_id, final_path,
        receipt, repair_forward=False,
    )


def _commit_result(row, expected_hash, final_hash, job_dir, job_id,
                   final_path, receipt, repair_forward) -> dict:
    vals = dict(zip(
        ("artifact_id", "source_id", "run_id", "artifact_type", "expected_hash",
         "status", "path", "created_at", "completed_at"),
        tuple(row),
    ))
    return {
        "artifact_id": vals["artifact_id"],
        "artifact_type": vals["artifact_type"],
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "temp_path": os.path.abspath(final_path + TMP_SUFFIX),
        "final_path": os.path.abspath(final_path),
        "state": STATE_COMMITTED,
        "job_dir": job_dir,
        "job_id": job_id,
        "source_id": vals["source_id"],
        "run_id": vals["run_id"],
        "receipt_path": os.path.abspath(final_path + COMMIT_RECEIPT_SUFFIX),
        "receipt": receipt,
        "repair_forward": repair_forward,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def recover_artifact(con: sqlite3.Connection, job_dir: str,
                     artifact_id: str) -> dict:
    """Repair-Forward recovery for one derived artifact (``# 40``/``# 41``).

    Truth Model (``# 41``, never inverted): Valid Filesystem Artifact +
    Expected Hash = Truth; SQLite is always the lagging side and is
    repaired forward. No transcription engine is ever invoked.
    """
    job_dir = os.path.abspath(job_dir)
    job_id = os.path.basename(job_dir)

    row = _read_row(con, artifact_id)
    if row is None:
        raise ArtifactRefused(
            "recovery refused: artifact %s has no artifacts row" % (artifact_id,)
        )
    vals = dict(zip(
        ("artifact_id", "source_id", "run_id", "artifact_type", "expected_hash",
         "status", "path", "created_at", "completed_at"),
        tuple(row),
    ))
    expected_hash = vals["expected_hash"]
    if not expected_hash or not expected_hash.startswith("sha256:"):
        raise ArtifactError("stored expected_hash malformed")
    final_path = os.path.abspath(vals["path"])
    if os.path.commonpath([job_dir, final_path]) != job_dir:
        raise ArtifactError("stored path escapes job_dir")
    tmp_path = final_path + TMP_SUFFIX
    artifact_type = vals["artifact_type"]
    if artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise ArtifactError("stored artifact_type %r unknown" % (artifact_type,))
    check = _DEFAULT_VALIDATORS[artifact_type]

    # Already COMMITTED: idempotent verify (+ manifest repair if lagging).
    if vals["status"] == STATE_COMMITTED:
        if not os.path.isfile(final_path):
            raise ArtifactError(
                "artifact %s SQLite COMMITTED but final missing; "
                "refusing to fabricate bytes" % (artifact_id,)
            )
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise ArtifactInvalid(
                "artifact %s COMMITTED but final hash mismatch: NEVER valid"
                " (# 40)" % (artifact_id,)
            )
        manifest_path = os.path.join(job_dir, "manifest.json")
        final_relpath = os.path.relpath(final_path, job_dir)
        if os.path.isfile(manifest_path):
            manifest = _load_json(manifest_path)
            if not _manifest_has_committed(manifest, artifact_id):
                _ensure_committed_manifest(
                    manifest_path, job_id, artifact_id, artifact_type,
                    final_relpath, expected_hash, final_hash,
                )
        _chmod_readonly(final_path)
        recover_receipt = _write_recover_receipt(
            final_path, job_dir, job_id, vals, expected_hash, final_hash,
            path="already_committed_idempotent",
        )
        out = _commit_result(
            row, expected_hash, final_hash, job_dir, job_id, final_path,
            _load_json(final_path + COMMIT_RECEIPT_SUFFIX)
            if os.path.isfile(final_path + COMMIT_RECEIPT_SUFFIX) else {},
            repair_forward=False,
        )
        out["recover_receipt_path"] = os.path.abspath(
            final_path + RECOVER_RECEIPT_SUFFIX
        )
        out["recover_receipt"] = recover_receipt
        out["recovery_path"] = "already_committed_idempotent"
        return out

    if vals["status"] != STATE_PREPARED:
        raise ArtifactError(
            "artifact %s status %r not PREPARED/COMMITTED; refusing recovery"
            % (artifact_id, vals["status"])
        )

    # PREPARED + Final Exists + Hash Match -> Repair Forward.
    if os.path.isfile(final_path):
        final_hash = "sha256:" + _sha256_file_hex(final_path)
        if final_hash != expected_hash:
            raise ArtifactInvalid(
                "final hash %s != expected %s: NEVER valid (# 40); "
                "refusing COMMITTED transition" % (final_hash, expected_hash)
            )
        if os.path.isfile(tmp_path):
            tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
            if tmp_hash != expected_hash:
                raise ArtifactError(
                    "tmp diverged while final is valid; refusing to paper"
                    " over divergence"
                )
        with open(final_path, "rb") as fh:
            check(fh.read())
        committed = commit_artifact(con, job_dir, artifact_id)
        recover_receipt = _write_recover_receipt(
            final_path, job_dir, job_id, vals, expected_hash,
            committed["final_hash"],
            path="prepared_final_exists_repair_forward",
        )
        committed["recover_receipt_path"] = os.path.abspath(
            final_path + RECOVER_RECEIPT_SUFFIX
        )
        committed["recover_receipt"] = recover_receipt
        committed["recovery_path"] = "prepared_final_exists_repair_forward"
        return committed

    # PREPARED + tmp Exists + Final Missing -> validate tmp, continue Commit.
    if os.path.isfile(tmp_path):
        with open(tmp_path, "rb") as fh:
            tmp_bytes = fh.read()
        tmp_hash = "sha256:" + _sha256_hex(tmp_bytes)
        if tmp_hash != expected_hash:
            raise ArtifactInvalid(
                "tmp hash %s != expected %s: NEVER valid (# 40); "
                "refusing Commit" % (tmp_hash, expected_hash)
            )
        check(tmp_bytes)
        committed = commit_artifact(con, job_dir, artifact_id)
        recover_receipt = _write_recover_receipt(
            final_path, job_dir, job_id, vals, expected_hash,
            committed["final_hash"],
            path="prepared_tmp_only_continue_commit",
        )
        committed["recover_receipt_path"] = os.path.abspath(
            final_path + RECOVER_RECEIPT_SUFFIX
        )
        committed["recover_receipt"] = recover_receipt
        committed["recovery_path"] = "prepared_tmp_only_continue_commit"
        return committed

    # PREPARED + both missing -> cannot fabricate.
    raise ArtifactError(
        "artifact %s PREPARED but tmp and final both missing; "
        "refusing to fabricate bytes" % (artifact_id,)
    )


def _write_recover_receipt(final_path, job_dir, job_id, vals, expected_hash,
                           final_hash, path) -> dict:
    receipt = {
        "stage": "Stage3-S3-T01",
        "state": STATE_COMMITTED,
        "artifact": os.path.relpath(os.path.abspath(final_path),
                                    os.path.abspath(job_dir)),
        "artifact_id": vals["artifact_id"],
        "artifact_type": vals["artifact_type"],
        "expected_artifact_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "recovery_path": path,
        "truth_model": (
            "Filesystem Valid + Expected Hash = Truth;"
            " SQLite lagging side Repair Forward (# 41)"
        ),
        "job_dir": job_dir,
        "job_id": job_id,
        "asr_calls": 0,
        "whisper_calls": 0,
        "created_at": _utc_now_iso(),
    }
    _write_fsync_json(final_path + RECOVER_RECEIPT_SUFFIX, receipt)
    return receipt
