"""S4-T02: atomic no-cover publish helper (# 49 six steps).

Implements STAGE4-PLAN S4-T02 only (V1.8 ``# 49``)::

    Rendered Final bytes -> expected_output_hash = SHA256
      -> central publish_records row PENDING (# 35 fields,
         publish_mode=INITIAL) + central artifacts row PREPARED
         (artifact_type=canonical) in one COMMIT transaction
      -> Output gate re-check -> same-dir tmp -> flush -> fsync
      -> atomic no-cover commit via link(2) (EEXIST wins, zero
         truncation, zero window) -> fsync(parent)
      -> Final Hash Verify (published_hash == expected_hash, else
         NEVER valid) -> publish_records PUBLISHED + published_hash /
         published_at + Manifest PUBLISHED receipt + SQLite COMMITTED

Why ``link(2)`` and not ``rename``: POSIX ``rename`` silently
dislodges an existing target, which would fake the no-cover promise
(R4). ``os.link(tmp, final)`` is atomic and fails with ``EEXIST``
when the Final side already exists, so a racing publisher (Case 12)
or a pre-existing user file can never lose a byte to us. The
``O_CREAT | O_EXCL`` capability measured by ``volume_probe`` is the
gate that admits the volume; ``link(2)`` is the commit that keeps
the promise on it.

``os.rename`` never lands on a Final path anywhere in this module.

Recovery (``# 53`` branch 1) owns the crash windows; every success
dict carries ``canonical_writes == 0`` for BLOCK paths (a publish
that lands bytes reports the Final hash instead) and
``whisper_calls == 0`` always (no transcription import exists here).

The ``on_tmp_ready`` argument of :func:`commit_publish` is the
Case-12 fault-injection seam: an optional callable invoked after the
tmp fsync and before the ``link(2)`` commit. It cannot authorize a
cover — the commit still travels the single no-cover path. It is
``None`` in production.
"""

from __future__ import annotations

import datetime
import errno
import hashlib
import os
import sqlite3
import uuid

from . import volume_probe as _vp

ST_PENDING = "PENDING"
ST_PUBLISHING = "PUBLISHING"
ST_PUBLISHED = "PUBLISHED"
ST_PENDING_PUBLISH = "PENDING_PUBLISH"
ST_CANONICAL_EXISTS = "CANONICAL_OUTPUT_EXISTS"
ST_BLOCKED_EXISTS = "BLOCKED_OUTPUT_EXISTS"
ST_BLOCKED_CONFLICT = "BLOCKED_OUTPUT_CONFLICT"
ST_BLOCKED_FS = _vp.BLOCK_CODE_FILESYSTEM
ST_BLOCKED_ROOT = _vp.BLOCK_CODE_ROOT

PUBLISH_MODE_INITIAL = "INITIAL"
ARTIFACT_TYPE_CANONICAL = "canonical"

TERMINAL_BLOCK = frozenset({
    ST_BLOCKED_EXISTS,
    ST_BLOCKED_CONFLICT,
    ST_BLOCKED_FS,
    ST_BLOCKED_ROOT,
    ST_CANONICAL_EXISTS,
    ST_PENDING_PUBLISH,
})


class PublishError(ValueError):
    """FAIL: stored evidence unusable / DB error (fail-closed)."""


class PublishBlocked(PublishError):
    """BLOCK: the Final side exists or the gate refused; nothing staged."""

    def __init__(self, message: str, status: str, **detail):
        super().__init__(message)
        self.status = status
        self.detail = detail


class PublishInvalid(PublishError):
    """FAIL: hash mismatch — NEVER a valid publish (# 49)."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def _fsync_parent(dir_path: str) -> None:
    fd = os.open(os.path.abspath(dir_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def canonical_path_for(output_root: str, source_relative_path: str) -> str:
    """Map # 48: OUTPUT_ROOT/<rel-without-ext>.md, escape-proof."""
    root = os.path.abspath(output_root)
    rel = (source_relative_path or "").strip()
    if not rel:
        raise PublishError("source_relative_path must be non-empty")
    if os.path.isabs(rel):
        raise PublishError("source_relative_path must be relative: %r" % (rel,))
    parts = rel.split(os.sep)
    if any(p in ("..", ".") or not p for p in parts):
        raise PublishError("source_relative_path escapes root: %r" % (rel,))
    stem, _ = os.path.splitext(parts[-1])
    if not stem:
        raise PublishError("source_relative_path has no stem: %r" % (rel,))
    final = os.path.abspath(
        os.path.join(root, *parts[:-1], stem + ".md"))
    if os.path.commonpath([root, final]) != root:
        raise PublishError("canonical path escapes output root: %r" % (final,))
    return final


def publish_record_id_for(render_revision_id: str, canonical_path: str,
                          expected_hash: str) -> str:
    """Deterministic publish id: same (rev, canonical, hash) => same id."""
    if not render_revision_id or not canonical_path or not expected_hash:
        raise PublishError("publish id inputs must be non-empty")
    digest = _sha256_hex(
        "|".join((render_revision_id, os.path.abspath(canonical_path),
                  expected_hash)).encode("utf-8"))[:12]
    return "pub_" + digest


def canonical_artifact_id_for(publish_record_id: str) -> str:
    suffix = publish_record_id.split("_", 1)[1] if "_" in publish_record_id \
        else publish_record_id
    return "canonical_" + suffix


def tmp_path_for(canonical_path: str, publish_record_id: str) -> str:
    suffix = publish_record_id.split("_", 1)[1] if "_" in publish_record_id \
        else publish_record_id
    return os.path.abspath(canonical_path) + ".tmp." + suffix[:8]


def _read_publish_row(con: sqlite3.Connection, publish_record_id: str):
    return con.execute(
        "SELECT publish_record_id, render_revision_id, canonical_output_path,"
        " expected_hash, publish_mode, status, published_hash, created_at,"
        " published_at FROM publish_records WHERE publish_record_id = ?",
        (publish_record_id,),
    ).fetchone()


def _row_get(row, key: str):
    if isinstance(row, sqlite3.Row):
        return row[key]
    cols = (
        "publish_record_id", "render_revision_id", "canonical_output_path",
        "expected_hash", "publish_mode", "status", "published_hash",
        "created_at", "published_at",
    )
    return row[cols.index(key)]


def _record_event(con: sqlite3.Connection, publish_record_id: str,
                  from_status: str | None, to_status: str | None,
                  reason: str | None = None) -> None:
    con.execute(
        "INSERT INTO state_events (event_id, entity_type, entity_id,"
        " from_status, to_status, reason, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            "evt_%s" % (uuid.uuid4().hex[:12]),
            "publish_record",
            publish_record_id,
            from_status,
            to_status,
            reason,
            _utc_now_iso(),
        ),
    )


def _resolve_rendered(con: sqlite3.Connection,
                      render_revision_id: str) -> tuple[str, str, str]:
    """Return (rendered_artifact_id, rendered_final_path, rendered_bytes)."""
    rev = con.execute(
        "SELECT rendered_artifact_id FROM render_revisions"
        " WHERE render_revision_id = ?",
        (render_revision_id,),
    ).fetchone()
    if rev is None:
        raise PublishError("unknown render_revision_id %r" % (
            render_revision_id,))
    artifact_id = rev[0] if not isinstance(rev, sqlite3.Row) else rev[0]
    art = con.execute(
        "SELECT path, status FROM artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    if art is None:
        raise PublishError("no central artifacts row for %r" % (artifact_id,))
    final_path = os.path.abspath(art[0])
    if not os.path.isfile(final_path):
        raise PublishError("rendered final missing at %s" % (final_path,))
    with open(final_path, "rb") as fh:
        content = fh.read()
    from stage3.artifact_commit import (  # noqa: PLC0415 (read-only reuse)
        validate_rendered_bytes,
    )
    try:
        validate_rendered_bytes(content)
    except ValueError as exc:
        raise PublishError("rendered final refused by gate: %s" % (exc,))
    return artifact_id, final_path, content


def prepare_publish(con: sqlite3.Connection, rendered_final_path: str,
                    canonical_path: str, publish_record_id: str,
                    render_revision_id: str | None = None,
                    publish_mode: str = PUBLISH_MODE_INITIAL) -> dict:
    """Run the # 49 PREPARE phase: hash pre-persist, DB-only, zero staging.

    Reads the Rendered Final bytes, persists
    ``expected_output_hash`` in a central ``publish_records`` row
    ``PENDING`` plus a central ``artifacts`` row ``PREPARED`` in one
    transaction. Touches no Output-root byte.
    """
    if publish_mode != PUBLISH_MODE_INITIAL:
        raise PublishError("Stage4 publishes INITIAL only: %r" % (
            publish_mode,))
    if not publish_record_id or not isinstance(publish_record_id, str):
        raise PublishError("publish_record_id must be a non-empty string")
    canonical_abs = os.path.abspath(canonical_path)
    if not os.path.isfile(rendered_final_path):
        raise PublishError("rendered final missing at %s" % (
            rendered_final_path,))
    with open(rendered_final_path, "rb") as fh:
        content = fh.read()
    from stage3.artifact_commit import (  # noqa: PLC0415 (read-only reuse)
        validate_rendered_bytes,
    )
    try:
        validate_rendered_bytes(content)
    except ValueError as exc:
        raise PublishError("rendered final refused by gate: %s" % (exc,))
    expected_hash = "sha256:" + _sha256_hex(content)

    existing = _read_publish_row(con, publish_record_id)
    if existing is not None:
        if (
            _row_get(existing, "expected_hash") == expected_hash
            and os.path.abspath(_row_get(existing, "canonical_output_path"))
            == canonical_abs
        ):
            return _prepare_result(
                existing, canonical_abs, expected_hash, idempotent_retry=True)
        raise PublishError(
            "publish_records row %s exists with different evidence;"
            " refusing to amend" % (publish_record_id,))

    created_at = _utc_now_iso()
    artifact_id = canonical_artifact_id_for(publish_record_id)
    try:
        with con:
            con.execute(
                "INSERT INTO publish_records (publish_record_id,"
                " render_revision_id, canonical_output_path, expected_hash,"
                " publish_mode, status, published_hash, created_at,"
                " published_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    publish_record_id, render_revision_id, canonical_abs,
                    expected_hash, publish_mode, ST_PENDING, None,
                    created_at, None,
                ),
            )
            con.execute(
                "INSERT INTO artifacts (artifact_id, source_id, run_id,"
                " artifact_type, expected_hash, status, path, created_at,"
                " completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    artifact_id, None, None, ARTIFACT_TYPE_CANONICAL,
                    expected_hash, "PREPARED", canonical_abs, created_at, None,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise PublishError("SQLite PREPARE write refused: %s" % (exc,))
    row = _read_publish_row(con, publish_record_id)
    if row is None:
        raise PublishError("expected hash not persisted: row missing")
    art = con.execute(
        "SELECT status, expected_hash FROM artifacts WHERE artifact_id = ?",
        (artifact_id,),
    ).fetchone()
    if (
        art is None or art[0] != "PREPARED"
        or art[1] != expected_hash
    ):
        raise PublishError("artifacts PREPARED row missing/diverged")
    _record_event(con, publish_record_id, None, ST_PENDING,
                  "expected_output_hash pre-persisted for %s" % (
                      canonical_abs,))
    con.commit()
    return _prepare_result(row, canonical_abs, expected_hash,
                           idempotent_retry=False)


def _prepare_result(row, canonical_abs: str, expected_hash: str,
                    idempotent_retry: bool) -> dict:
    publish_record_id = _row_get(row, "publish_record_id")
    return {
        "publish_record_id": publish_record_id,
        "render_revision_id": _row_get(row, "render_revision_id"),
        "canonical_output_path": canonical_abs,
        "expected_output_hash": expected_hash,
        "tmp_path": tmp_path_for(canonical_abs, publish_record_id),
        "publish_mode": _row_get(row, "publish_mode"),
        "state": _row_get(row, "status"),
        "idempotent_retry": idempotent_retry,
        "canonical_writes": 0,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _mark_block(con: sqlite3.Connection, publish_record_id: str,
                from_status: str | None, status: str, reason: str) -> None:
    con.execute(
        "UPDATE publish_records SET status = ? WHERE publish_record_id = ?",
        (status, publish_record_id),
    )
    _record_event(con, publish_record_id, from_status, status, reason)
    con.commit()


def record_verdict_row(con: sqlite3.Connection, render_revision_id: str,
                       canonical_abs: str, expected_hash: str,
                       status: str, reason: str) -> dict:
    """Land one BLOCK verdict row for a refused fresh attempt."""
    verdict_id = "pub_" + _sha256_hex(
        "|".join((render_revision_id, canonical_abs, expected_hash,
                  status)).encode("utf-8"))[:12]
    existing = _read_publish_row(con, verdict_id)
    if existing is not None:
        return {
            "publish_record_id": verdict_id,
            "status": _row_get(existing, "status"),
            "idempotent_retry": True,
        }
    created = _utc_now_iso()
    with con:
        con.execute(
            "INSERT INTO publish_records (publish_record_id,"
            " render_revision_id, canonical_output_path, expected_hash,"
            " publish_mode, status, published_hash, created_at,"
            " published_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                verdict_id, render_revision_id, canonical_abs,
                expected_hash, PUBLISH_MODE_INITIAL, status, None,
                created, None,
            ),
        )
    _record_event(con, verdict_id, None, status, reason)
    con.commit()
    return {
        "publish_record_id": verdict_id,
        "status": status,
        "idempotent_retry": False,
    }


def _block_on_existing(con: sqlite3.Connection, publish_record_id: str,
                       from_status: str, canonical_abs: str,
                       expected_hash: str) -> PublishBlocked:
    """Someone owns the Final side: classify, record, raise. No staging."""
    with open(canonical_abs, "rb") as fh:
        present = fh.read()
    present_hash = "sha256:" + _sha256_hex(present)
    status = ST_BLOCKED_EXISTS if present_hash == expected_hash \
        else ST_BLOCKED_CONFLICT
    _mark_block(con, publish_record_id, from_status, status,
                "final side owned by another writer; present=%s" % (
                    present_hash,))
    return PublishBlocked(
        "%s: canonical %r already owned (present=%s)" % (
            status, canonical_abs, present_hash),
        status,
        canonical_output_path=canonical_abs,
        present_hash=present_hash,
        expected_hash=expected_hash,
        canonical_writes=0,
    )


def _link_and_finish(con: sqlite3.Connection, job_dir: str,
                     publish_record_id: str, canonical_abs: str,
                     expected_hash: str, rendered_artifact_id: str,
                     repair_forward: bool, recovery_path: str) -> dict:
    """The commit tail shared by the normal path and tmp-only recovery."""
    tmp_path = tmp_path_for(canonical_abs, publish_record_id)
    try:
        os.link(tmp_path, canonical_abs)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise PublishError(
                "atomic no-cover commit refused: %s" % (exc,))
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        row = _read_publish_row(con, publish_record_id)
        raise _block_on_existing(
            con, publish_record_id,
            _row_get(row, "status") if row is not None else ST_PUBLISHING,
            canonical_abs, expected_hash)
    try:
        _fsync_parent(os.path.dirname(canonical_abs))
    except OSError as exc:
        raise PublishError("fsync(parent) refused after commit: %s" % (exc,))

    final_hash = "sha256:" + _sha256_file_hex(canonical_abs)
    if final_hash != expected_hash:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise PublishInvalid(
            "final hash %s != expected %s: NEVER valid; refusing"
            " PUBLISHED transition" % (final_hash, expected_hash))

    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    try:
        os.chmod(canonical_abs, 0o444)
    except OSError as exc:
        raise PublishError("read-only marking refused: %s" % (exc,))

    from . import lineage_ext as _lx  # noqa: PLC0415 (single writer keeps order)
    published_at = _utc_now_iso()
    _lx.record_publish_receipt(
        os.path.join(os.path.abspath(job_dir), "manifest.json"),
        publish_record_id=publish_record_id,
        render_revision_id=(
            _row_get(_read_publish_row(con, publish_record_id),
                     "render_revision_id")),
        rendered_artifact_id=rendered_artifact_id,
        canonical_output_path=canonical_abs,
        expected_output_hash=expected_hash,
        published_hash=final_hash,
        status=ST_PUBLISHED,
    )
    with con:
        con.execute(
            "UPDATE artifacts SET status = ?, completed_at = ?"
            " WHERE artifact_id = ? AND status = ? AND expected_hash = ?",
            ("COMMITTED", published_at,
             canonical_artifact_id_for(publish_record_id),
             "PREPARED", expected_hash),
        )
        con.execute(
            "UPDATE publish_records SET status = ?, published_hash = ?,"
            " published_at = ? WHERE publish_record_id = ?",
            (ST_PUBLISHED, final_hash, published_at, publish_record_id),
        )
    _record_event(con, publish_record_id, ST_PUBLISHING, ST_PUBLISHED,
                  "final=%s verified; receipt appended" % (final_hash,))
    con.commit()
    row = _read_publish_row(con, publish_record_id)
    return {
        "publish_record_id": publish_record_id,
        "render_revision_id": _row_get(row, "render_revision_id"),
        "rendered_artifact_id": rendered_artifact_id,
        "canonical_output_path": canonical_abs,
        "expected_output_hash": expected_hash,
        "published_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "status": ST_PUBLISHED,
        "published_at": published_at,
        "repair_forward": repair_forward,
        "recovery_path": recovery_path,
        "canonical_writes": 0,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def commit_publish(con: sqlite3.Connection, job_dir: str,
                   publish_record_id: str,
                   on_tmp_ready=None) -> dict:
    """Run the # 49 COMMIT phase for one PREPAREd publish."""
    job_dir = os.path.abspath(job_dir)
    row = _read_publish_row(con, publish_record_id)
    if row is None:
        raise PublishError(
            "COMMIT refused: publish %s has no PENDING row" % (
                publish_record_id,))
    status = _row_get(row, "status")
    canonical_abs = os.path.abspath(_row_get(row, "canonical_output_path"))
    expected_hash = _row_get(row, "expected_hash")
    render_revision_id = _row_get(row, "render_revision_id")

    if status == ST_PUBLISHED:
        if not os.path.isfile(canonical_abs):
            raise PublishError(
                "publish %s SQLite PUBLISHED but final missing;"
                " refusing to fabricate bytes" % (publish_record_id,))
        final_hash = "sha256:" + _sha256_file_hex(canonical_abs)
        if final_hash != _row_get(row, "published_hash"):
            raise PublishInvalid(
                "publish %s PUBLISHED but final hash mismatch: NEVER"
                " valid" % (publish_record_id,))
        out = _prepare_result(row, canonical_abs, expected_hash,
                              idempotent_retry=True)
        out.update({
            "published_hash": _row_get(row, "published_hash"),
            "status": ST_PUBLISHED,
            "repair_forward": False,
        })
        return out
    if status in TERMINAL_BLOCK:
        raise PublishBlocked(
            "COMMIT refused: publish %s terminal %s" % (
                publish_record_id, status),
            status, canonical_output_path=canonical_abs)
    if status not in (ST_PENDING, ST_PUBLISHING):
        raise PublishError("COMMIT refused: publish %s status %r" % (
            publish_record_id, status))

    try:
        _vp.gate_output_root(os.path.dirname(canonical_abs))
    except (_vp.BlockedUnsupportedOutputFilesystem,
            _vp.BlockedUnsupportedRoot) as exc:
        _mark_block(con, publish_record_id, status, exc.code, str(exc))
        raise PublishBlocked(str(exc), exc.code,
                             canonical_output_path=canonical_abs)

    if render_revision_id is None:
        raise PublishError("publish %s carries no render_revision_id" % (
            publish_record_id,))
    rendered_artifact_id, _, rendered_bytes = _resolve_rendered(
        con, render_revision_id)
    if "sha256:" + _sha256_hex(rendered_bytes) != expected_hash:
        raise PublishInvalid(
            "rendered bytes diverged from expected_output_hash: NEVER valid")

    if status == ST_PENDING:
        con.execute(
            "UPDATE publish_records SET status = ?"
            " WHERE publish_record_id = ? AND status = ?",
            (ST_PUBLISHING, publish_record_id, ST_PENDING),
        )
        _record_event(con, publish_record_id, ST_PENDING, ST_PUBLISHING,
                      "commit opened for %s" % (canonical_abs,))
        con.commit()

    os.makedirs(os.path.dirname(canonical_abs), exist_ok=True)
    tmp_path = tmp_path_for(canonical_abs, publish_record_id)
    if os.path.isfile(canonical_abs):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise _block_on_existing(
            con, publish_record_id, ST_PUBLISHING, canonical_abs,
            expected_hash)
    with open(tmp_path, "wb") as fh:
        fh.write(rendered_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    with open(tmp_path, "rb") as fh:
        staged = fh.read()
    if "sha256:" + _sha256_hex(staged) != expected_hash:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise PublishInvalid(
            "staged tmp hash diverged: NEVER valid; refusing commit")

    if on_tmp_ready is not None:
        on_tmp_ready(tmp_path, canonical_abs, publish_record_id)

    return _link_and_finish(con, job_dir, publish_record_id, canonical_abs,
                            expected_hash, rendered_artifact_id,
                            repair_forward=False,
                            recovery_path="prepared_tmp_commit")


def recover_publish(con: sqlite3.Connection, job_dir: str,
                    publish_record_id: str) -> dict:
    """Repair-Forward recovery for one publish (# 53 branch 1).

    Truth Model (as in # 41, never inverted): Valid Filesystem Final
    + Expected Hash = Truth; SQLite is always the lagging side and is
    repaired forward. This function never stages fresh bytes and never
    dislodges an existing Final.
    """
    job_dir = os.path.abspath(job_dir)
    row = _read_publish_row(con, publish_record_id)
    if row is None:
        raise PublishError(
            "recovery refused: publish %s has no row" % (publish_record_id,))
    status = _row_get(row, "status")
    canonical_abs = os.path.abspath(_row_get(row, "canonical_output_path"))
    expected_hash = _row_get(row, "expected_hash")
    render_revision_id = _row_get(row, "render_revision_id")
    tmp_path = tmp_path_for(canonical_abs, publish_record_id)

    if status in TERMINAL_BLOCK:
        raise PublishBlocked(
            "recovery refused: publish %s terminal %s" % (
                publish_record_id, status),
            status, canonical_output_path=canonical_abs)

    if status == ST_PUBLISHED:
        if not os.path.isfile(canonical_abs):
            raise PublishError(
                "publish %s SQLite PUBLISHED but final missing;"
                " refusing to fabricate bytes" % (publish_record_id,))
        final_hash = "sha256:" + _sha256_file_hex(canonical_abs)
        if final_hash != expected_hash:
            raise PublishInvalid(
                "publish %s PUBLISHED but final hash mismatch: NEVER"
                " valid" % (publish_record_id,))
        out = _prepare_result(row, canonical_abs, expected_hash,
                              idempotent_retry=True)
        out.update({
            "published_hash": _row_get(row, "published_hash"),
            "status": ST_PUBLISHED,
            "recovery_path": "already_published_idempotent",
            "repair_forward": False,
        })
        return out

    if status not in (ST_PENDING, ST_PUBLISHING):
        raise PublishError("recovery refused: status %r" % (status,))

    if render_revision_id is None:
        raise PublishError("publish %s carries no render_revision_id" % (
            publish_record_id,))
    rendered_artifact_id, _, _ = _resolve_rendered(con, render_revision_id)

    if os.path.isfile(canonical_abs):
        final_hash = "sha256:" + _sha256_file_hex(canonical_abs)
        if final_hash != expected_hash:
            raise PublishInvalid(
                "final hash %s != expected %s: NEVER valid; refusing"
                " PUBLISHED transition" % (final_hash, expected_hash))
        if os.path.isfile(tmp_path):
            tmp_hash = "sha256:" + _sha256_file_hex(tmp_path)
            if tmp_hash != expected_hash:
                raise PublishError(
                    "stray tmp diverged while final is valid; refusing to"
                    " paper over divergence")
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        from . import lineage_ext as _lx  # noqa: PLC0415 (repair keeps order)
        _lx.record_publish_receipt(
            os.path.join(job_dir, "manifest.json"),
            publish_record_id=publish_record_id,
            render_revision_id=render_revision_id,
            rendered_artifact_id=rendered_artifact_id,
            canonical_output_path=canonical_abs,
            expected_output_hash=expected_hash,
            published_hash=final_hash,
            status=ST_PUBLISHED,
        )
        published_at = _utc_now_iso()
        with con:
            con.execute(
                "UPDATE artifacts SET status = ?, completed_at = ?"
                " WHERE artifact_id = ? AND expected_hash = ?",
                ("COMMITTED", published_at,
                 canonical_artifact_id_for(publish_record_id),
                 expected_hash),
            )
            con.execute(
                "UPDATE publish_records SET status = ?, published_hash = ?,"
                " published_at = ? WHERE publish_record_id = ?",
                (ST_PUBLISHED, final_hash, published_at, publish_record_id),
            )
        _record_event(con, publish_record_id, status, ST_PUBLISHED,
                      "repair forward: final valid, receipt restored")
        con.commit()
        row2 = _read_publish_row(con, publish_record_id)
        out = _prepare_result(row2, canonical_abs, expected_hash,
                              idempotent_retry=False)
        out.update({
            "rendered_artifact_id": rendered_artifact_id,
            "published_hash": final_hash,
            "hash_match": True,
            "status": ST_PUBLISHED,
            "repair_forward": True,
            "recovery_path": "publishing_final_exists_repair_forward",
        })
        return out

    if os.path.isfile(tmp_path):
        with open(tmp_path, "rb") as fh:
            staged = fh.read()
        if "sha256:" + _sha256_hex(staged) != expected_hash:
            raise PublishInvalid(
                "staged tmp hash mismatch: NEVER valid; refusing commit")
        try:
            _vp.gate_output_root(os.path.dirname(canonical_abs))
        except (_vp.BlockedUnsupportedOutputFilesystem,
                _vp.BlockedUnsupportedRoot) as exc:
            _mark_block(con, publish_record_id, status, exc.code, str(exc))
            raise PublishBlocked(str(exc), exc.code,
                                 canonical_output_path=canonical_abs)
        if status == ST_PENDING:
            con.execute(
                "UPDATE publish_records SET status = ?"
                " WHERE publish_record_id = ? AND status = ?",
                (ST_PUBLISHING, publish_record_id, ST_PENDING),
            )
            _record_event(con, publish_record_id, ST_PENDING, ST_PUBLISHING,
                          "recovery continues tmp-only commit")
            con.commit()
        out = _link_and_finish(con, job_dir, publish_record_id,
                               canonical_abs, expected_hash,
                               rendered_artifact_id, repair_forward=True,
                               recovery_path="prepared_tmp_only_continue_commit")
        return out

    raise PublishError(
        "publish %s %s but tmp and final both missing;"
        " refusing to fabricate bytes" % (publish_record_id, status))
