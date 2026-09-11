"""S10-T03: Level B O_EXCL Reservation Copy + Mid-copy Recovery (§57).

Implements STAGE10-PLAN S10-T03 only (V1.8 §57 + Case 10)::

    archive_level_b(source, final, expected_hash, source_id):
      Strong Verify -> O_EXCL 独占创建 Final -> Ownership/PREPARED 落盘
      (sidecar) -> copy -> flush/fsync -> SHA256 ->
      ARCHIVE_COMMITTED Receipt 落盘 -> 再次 Strong Verify 源 ->
      删源. 目标已归他人 (无归属 sidecar) 即 BLOCKED_ARCHIVE_EXISTS,
      源保留.

    recover_midcopy(source, final, expected_hash, source_id):
      无归属 sidecar -> ArchiveRefused (未知 Final 永不动);
      PREPARED + Final 缺失 -> INCOMPLETE (可重入 archive_level_b);
      PREPARED + Final 完整且 hash 一致 -> Repair Forward 补 Receipt
      (复用 Stage1 Truth Model: Filesystem Valid + Expected Hash 为真,
      SQLite 为落后方; 零转写);
      PREPARED + Final 半截 -> 归属明确, 截断重拷后继续走完 Receipt;
      文件存在永不等于完成 (无 Receipt 不视为成功).

Ownership 登记在 Final 同目录 sidecar
``<final>.archive_prepared.json`` 中 (archive_commits 只许成功路径
新增行, PREPARED 不进中央库). Receipt 落
``<final>.archive_receipt.json``. 成功态 sidecar 标记 COMMITTED.

STOP EXPANSION: no A-route link fast path here, no C-route verdict
here, no Source column write (T04 owns it), no publish/revision write.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import uuid

RECEIPT_STATUS = "ARCHIVE_COMMITTED"
PREPARED_STATUS = "PREPARED"
BLOCK_ARCHIVE_EXISTS = "BLOCKED_ARCHIVE_EXISTS"
CODE_RESUME_NEEDED = "ARCHIVE_RESUME_NEEDED"
LEVEL = "B"

_SIDECAR_SUFFIX = ".archive_prepared.json"
_RECEIPT_SUFFIX = ".archive_receipt.json"


class ArchiveError(ValueError):
    """FAIL: evidence unusable (fail-closed, source kept)."""


class ArchiveBlocked(ArchiveError):
    """BLOCK: the target side is owned by another writer; source kept."""

    def __init__(self, message: str, status: str, **detail):
        super().__init__(message)
        self.status = status
        self.detail = detail


class ArchiveRefused(RuntimeError):
    """REFUSED: no ownership sidecar — an unknown Final is never touched."""


def _utc_now_iso() -> str:
    from stage2 import store as _store  # noqa: PLC0415 (timestamp shape)

    return _store.utc_now_iso()


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


def sidecar_path_for(archive_final_path: str) -> str:
    return os.path.abspath(archive_final_path) + _SIDECAR_SUFFIX


def receipt_path_for(archive_final_path: str) -> str:
    return os.path.abspath(archive_final_path) + _RECEIPT_SUFFIX


def archive_commit_id_for(source_id: str, final_abs: str, expected_hash: str) -> str:
    digest = hashlib.sha256(
        "|".join((source_id, final_abs, expected_hash)).encode("utf-8")
    ).hexdigest()[:12]
    return "arc_" + digest


def _write_json_fsync(path: str, payload: dict) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _read_sidecar(final_abs: str) -> dict | None:
    sidecar = sidecar_path_for(final_abs)
    if not os.path.isfile(sidecar):
        return None
    try:
        with open(sidecar, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _sidecar_owned(sidecar: dict | None, source_id: str, expected_hash: str) -> bool:
    return (
        sidecar is not None
        and sidecar.get("source_id") == source_id
        and sidecar.get("expected_hash") == expected_hash
        and sidecar.get("level") == LEVEL
    )


def _target_proof(final_abs: str) -> dict:
    if not os.path.lexists(final_abs):
        return {"target_exists": False}
    if os.path.isfile(final_abs) and not os.path.islink(final_abs):
        return {
            "target_exists": True,
            "target_hash": "sha256:" + _sha256_file_hex(final_abs),
        }
    return {"target_exists": True, "target_hash": None}


def _blocked_owned(final_abs: str, source_abs: str) -> ArchiveBlocked:
    return ArchiveBlocked(
        "%s: archive target %r already owned by another writer;"
        " source kept" % (BLOCK_ARCHIVE_EXISTS, final_abs),
        BLOCK_ARCHIVE_EXISTS,
        archive_final_path=final_abs,
        source_kept=True,
        **_target_proof(final_abs),
    )


def _copy_stream(source_abs: str, fd: int, on_chunk=None) -> int:
    written = 0
    with open(source_abs, "rb") as src_fh:
        while True:
            part = src_fh.read(8 * 1024 * 1024)
            if not part:
                break
            view = memoryview(part)
            while view:
                count = os.write(fd, view)
                written += count
                view = view[count:]
            if on_chunk is not None:
                on_chunk(written)
    os.fsync(fd)
    return written


def _write_receipt(
    final_abs: str,
    commit_id: str,
    source_id: str,
    source_abs: str,
    final_hash: str,
    expected_hash: str,
    same_device: bool,
    repair_forward: bool,
    recovery_path: str,
) -> dict:
    receipt = {
        "status": RECEIPT_STATUS,
        "level": LEVEL,
        "archive_commit_id": commit_id,
        "source_id": source_id,
        "source_path": source_abs,
        "archive_final_path": final_abs,
        "source_hash": expected_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == expected_hash,
        "source_removed": True,
        "same_device": same_device,
        "repair_forward": repair_forward,
        "recovery_path": recovery_path,
        "receipt_path": receipt_path_for(final_abs),
        "committed_at": _utc_now_iso(),
        "asr_calls": 0,
        "whisper_calls": 0,
    }
    _write_json_fsync(receipt_path_for(final_abs), receipt)
    return receipt


def _mark_sidecar_committed(final_abs: str, commit_id: str) -> None:
    sidecar = _read_sidecar(final_abs) or {}
    sidecar.update({"status": RECEIPT_STATUS, "completed_at": _utc_now_iso()})
    _ = commit_id
    _write_json_fsync(sidecar_path_for(final_abs), sidecar)


def _finish_after_valid_final(
    source_abs: str,
    final_abs: str,
    commit_id: str,
    source_id: str,
    expected_hash: str,
    final_hash: str,
    same_device: bool,
    repair_forward: bool,
    recovery_path: str,
    on_pre_unlink=None,
) -> dict:
    receipt = _write_receipt(
        final_abs, commit_id, source_id, source_abs, final_hash,
        expected_hash, same_device, repair_forward, recovery_path,
    )
    _mark_sidecar_committed(final_abs, commit_id)
    fresh_source = "sha256:" + _sha256_file_hex(source_abs)
    if fresh_source != expected_hash:
        raise ArchiveError(
            "source changed during copy (%s != %s): final kept,"
            " source kept, refusing unlink" % (fresh_source, expected_hash)
        )
    if on_pre_unlink is not None:
        on_pre_unlink(receipt)
    os.unlink(source_abs)
    _fsync_parent(os.path.dirname(final_abs))
    _fsync_parent(os.path.dirname(source_abs))
    return receipt


def archive_level_b(
    source_path: str,
    archive_final_path: str,
    expected_hash: str,
    source_id: str,
    archive_commit_id: str | None = None,
    on_chunk=None,
    on_pre_unlink=None,
) -> dict:
    """Reservation-copy one source file (Strong Verify first and last)."""
    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)
    if not os.path.isfile(source_abs) or os.path.islink(source_abs):
        raise ArchiveError("archive source missing at %s" % (source_abs,))
    if not expected_hash or not expected_hash.startswith("sha256:"):
        raise ArchiveError("expected_hash must be a sha256: identity")
    source_hash = "sha256:" + _sha256_file_hex(source_abs)
    if source_hash != expected_hash:
        raise ArchiveError(
            "pre-copy Strong Verify failed (%s != %s): refusing"
            % (source_hash, expected_hash)
        )
    os.makedirs(os.path.dirname(final_abs), exist_ok=True)
    try:
        same_device = os.stat(source_abs).st_dev == os.stat(
            os.path.dirname(final_abs)
        ).st_dev
    except OSError:
        same_device = False
    commit_id = archive_commit_id or archive_commit_id_for(
        source_id, final_abs, expected_hash
    )
    sidecar = _read_sidecar(final_abs)
    owned = _sidecar_owned(sidecar, source_id, expected_hash)
    fd = None
    resume = False
    if os.path.lexists(final_abs):
        if owned and os.path.isfile(final_abs) and not os.path.islink(final_abs):
            resume = True
        else:
            raise _blocked_owned(final_abs, source_abs)
    if resume:
        fd = os.open(final_abs, os.O_WRONLY | os.O_TRUNC)
    else:
        try:
            fd = os.open(final_abs, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                sidecar = _read_sidecar(final_abs)
                if _sidecar_owned(sidecar, source_id, expected_hash):
                    fd = os.open(final_abs, os.O_WRONLY | os.O_TRUNC)
                    resume = True
                else:
                    raise _blocked_owned(final_abs, source_abs)
            else:
                raise ArchiveError("reservation create refused: %s" % (exc,))
    assert fd is not None
    _write_json_fsync(
        sidecar_path_for(final_abs),
        {
            "status": PREPARED_STATUS,
            "level": LEVEL,
            "archive_commit_id": commit_id,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "expected_hash": expected_hash,
            "created_at": _utc_now_iso(),
        },
    )
    try:
        _copy_stream(source_abs, fd, on_chunk=on_chunk)
    finally:
        os.close(fd)
    final_hash = "sha256:" + _sha256_file_hex(final_abs)
    if final_hash != expected_hash:
        raise ArchiveError(
            "post-copy hash %s != expected %s: NEVER valid;"
            " final kept for diagnosis, source kept" % (final_hash, expected_hash)
        )
    return _finish_after_valid_final(
        source_abs, final_abs, commit_id, source_id, expected_hash, final_hash,
        same_device, False, "reservation_copy", on_pre_unlink=on_pre_unlink,
    )


def _read_receipt(final_abs: str) -> dict | None:
    path = receipt_path_for(final_abs)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def recover_midcopy(
    source_path: str,
    archive_final_path: str,
    expected_hash: str,
    source_id: str,
    on_pre_unlink=None,
) -> dict:
    """Continue or repair-forward an interrupted Level B copy (§57)."""
    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)
    sidecar = _read_sidecar(final_abs)
    if not _sidecar_owned(sidecar, source_id, expected_hash):
        raise ArchiveRefused(
            "no owned PREPARED sidecar for %r: unknown Final never touched"
            % (final_abs,)
        )
    commit_id = sidecar.get("archive_commit_id") or archive_commit_id_for(
        source_id, final_abs, expected_hash
    )
    if not os.path.isfile(source_abs) or os.path.islink(source_abs):
        stored = _read_receipt(final_abs)
        if (
            sidecar.get("status") == RECEIPT_STATUS
            and stored is not None
            and stored.get("status") == RECEIPT_STATUS
            and stored.get("final_hash") == expected_hash
            and os.path.isfile(final_abs)
            and "sha256:" + _sha256_file_hex(final_abs) == expected_hash
        ):
            stored = dict(stored)
            stored["recovery_path"] = "already_committed_idempotent"
            stored["repair_forward"] = True
            return stored
        raise ArchiveError("recovery refused: source missing at %s" % (source_abs,))
    try:
        same_device = os.stat(source_abs).st_dev == os.stat(
            os.path.dirname(final_abs)
        ).st_dev
    except OSError:
        same_device = False
    base = {
        "source_id": source_id,
        "archive_commit_id": commit_id,
        "source_path": source_abs,
        "archive_final_path": final_abs,
        "expected_hash": expected_hash,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
    if not os.path.lexists(final_abs):
        return {
            **base,
            "verdict": "INCOMPLETE",
            "code": CODE_RESUME_NEEDED,
            "reason": "PREPARED sidecar owned but Final absent;"
            " source kept, re-run archive_level_b to resume",
            "source_kept": True,
        }
    if not os.path.isfile(final_abs) or os.path.islink(final_abs):
        raise ArchiveRefused(
            "Final side is not a plain file at %r: never touched" % (final_abs,)
        )
    final_hash = "sha256:" + _sha256_file_hex(final_abs)
    if final_hash == expected_hash:
        had_receipt = os.path.isfile(receipt_path_for(final_abs))
        receipt = _finish_after_valid_final(
            source_abs, final_abs, commit_id, source_id, expected_hash,
            final_hash, same_device, True,
            "prepared_final_exists_repair_forward", on_pre_unlink=on_pre_unlink,
        )
        if had_receipt:
            receipt["recovery_path"] = "already_committed_idempotent"
        return receipt
    fd = os.open(final_abs, os.O_WRONLY | os.O_TRUNC)
    try:
        _copy_stream(source_abs, fd)
    finally:
        os.close(fd)
    final_hash = "sha256:" + _sha256_file_hex(final_abs)
    if final_hash != expected_hash:
        raise ArchiveError(
            "resume copy hash %s != expected %s: NEVER valid;"
            " source kept" % (final_hash, expected_hash)
        )
    return _finish_after_valid_final(
        source_abs, final_abs, commit_id, source_id, expected_hash, final_hash,
        same_device, True, "prepared_partial_recopy", on_pre_unlink=on_pre_unlink,
    )


def fresh_commit_id() -> str:
    """Mint a unique archive commit id (used when no deterministic one fits)."""
    return "arc_" + uuid.uuid4().hex[:12]
