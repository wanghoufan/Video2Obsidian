"""S10-T02: Level A Atomic No-Cover archive (V1.8 §56).

Implements STAGE10-PLAN S10-T02 only::

    archive_level_a(source_path, archive_final_path):
      target present -> BLOCKED_ARCHIVE_EXISTS, source kept, target
      bytes intact (target cover count恒为 0);
      same filesystem -> link(2) commit + unlink source (atomic, the
      link fails with EEXIST when the target side is owned, so a racing
      writer can never lose a byte to us — same rationale as the
      Stage4 publish commit);
      cross filesystem -> stage tmp in the destination dir + link(2)
      commit + hash verify + unlink tmp + unlink source (the commit
      point stays a no-cover link; no O_EXCL reservation of the Final
      path on this route — that mechanism belongs to Level B).

Every success returns an ARCHIVE_COMMITTED receipt (hash_match True,
source_removed True). This module writes no DB row and never enters
transcription (whisper_calls == 0, asr_calls == 0 on every path).

STOP EXPANSION: no B-route reservation copy here, no C-route verdict
here, no Source column write (T04 owns it), no publish/revision write.
"""

from __future__ import annotations

import errno
import hashlib
import os
import uuid

RECEIPT_STATUS = "ARCHIVE_COMMITTED"
BLOCK_ARCHIVE_EXISTS = "BLOCKED_ARCHIVE_EXISTS"
LEVEL = "A"

_TMP_TAG = "tmp.s10a"


class ArchiveError(ValueError):
    """FAIL: evidence unusable (fail-closed, nothing moved)."""


class ArchiveBlocked(ArchiveError):
    """BLOCK: the target side is owned or the FS refused; source kept."""

    def __init__(self, message: str, status: str, **detail):
        super().__init__(message)
        self.status = status
        self.detail = detail


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


def _same_device(source_path: str, dest_dir: str) -> bool:
    return os.stat(source_path).st_dev == os.stat(dest_dir).st_dev


def _target_proof(final_abs: str) -> dict:
    if not os.path.lexists(final_abs):
        return {"target_exists": False}
    if os.path.isfile(final_abs) and not os.path.islink(final_abs):
        return {
            "target_exists": True,
            "target_hash": "sha256:" + _sha256_file_hex(final_abs),
        }
    return {"target_exists": True, "target_hash": None}


def _link_no_cover(source_abs: str, final_abs: str) -> None:
    """Atomic no-cover commit; a owned target raises ArchiveBlocked."""
    try:
        os.link(source_abs, final_abs)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise ArchiveBlocked(
                "%s: archive target %r already owned;"
                " refusing without touching it" % (BLOCK_ARCHIVE_EXISTS, final_abs),
                BLOCK_ARCHIVE_EXISTS,
                archive_final_path=final_abs,
                **_target_proof(final_abs),
            )
        raise ArchiveError("atomic link commit refused: %s" % (exc,))


def _receipt(
    source_abs: str,
    final_abs: str,
    source_hash: str,
    final_hash: str,
    same_device: bool,
) -> dict:
    return {
        "status": RECEIPT_STATUS,
        "level": LEVEL,
        "source_path": source_abs,
        "archive_final_path": final_abs,
        "source_hash": source_hash,
        "final_hash": final_hash,
        "hash_match": final_hash == source_hash,
        "source_removed": True,
        "same_device": same_device,
        "repair_forward": False,
        "recovery_path": "level_a_atomic_link",
        "committed_at": _utc_now_iso(),
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _move_same_device(source_abs: str, final_abs: str, source_hash: str) -> dict:
    _link_no_cover(source_abs, final_abs)
    final_hash = "sha256:" + _sha256_file_hex(final_abs)
    if final_hash != source_hash:
        raise ArchiveError(
            "linked final hash %s != source %s: NEVER valid" % (final_hash, source_hash)
        )
    os.unlink(source_abs)
    _fsync_parent(os.path.dirname(final_abs))
    _fsync_parent(os.path.dirname(source_abs))
    return _receipt(source_abs, final_abs, source_hash, final_hash, True)


def _move_cross_device(source_abs: str, final_abs: str, source_hash: str) -> dict:
    dest_dir = os.path.dirname(final_abs)
    tmp_abs = None
    for _ in range(8):
        candidate = "%s.%s.%s" % (final_abs, _TMP_TAG, uuid.uuid4().hex[:8])
        if not os.path.lexists(candidate):
            tmp_abs = candidate
            break
    if tmp_abs is None:
        raise ArchiveError("no free tmp name beside %r" % (final_abs,))
    with open(source_abs, "rb") as src_fh, open(tmp_abs, "wb") as tmp_fh:
        while True:
            part = src_fh.read(8 * 1024 * 1024)
            if not part:
                break
            tmp_fh.write(part)
        tmp_fh.flush()
        os.fsync(tmp_fh.fileno())
    try:
        tmp_hash = "sha256:" + _sha256_file_hex(tmp_abs)
        if tmp_hash != source_hash:
            raise ArchiveError("staged tmp diverged from source: refusing commit")
        _link_no_cover(tmp_abs, final_abs)
        final_hash = "sha256:" + _sha256_file_hex(final_abs)
        if final_hash != source_hash:
            raise ArchiveError("final hash mismatch after commit: NEVER valid")
    except Exception:
        try:
            os.unlink(tmp_abs)
        except OSError:
            pass
        raise
    try:
        os.unlink(tmp_abs)
    except OSError:
        pass
    fresh_source = "sha256:" + _sha256_file_hex(source_abs)
    if fresh_source != source_hash:
        try:
            os.unlink(tmp_abs)
        except OSError:
            pass
        raise ArchiveError(
            "source changed during copy (%s != %s): final kept,"
            " source kept, refusing unlink" % (fresh_source, source_hash)
        )
    os.unlink(source_abs)
    _fsync_parent(dest_dir)
    _fsync_parent(os.path.dirname(source_abs))
    return _receipt(source_abs, final_abs, source_hash, final_hash, False)


def archive_level_a(
    source_path: str, archive_final_path: str, expected_hash: str | None = None
) -> dict:
    """Archive one source file with atomic no-cover semantics (§56)."""
    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)
    if not os.path.isfile(source_abs) or os.path.islink(source_abs):
        raise ArchiveError("archive source missing at %s" % (source_abs,))
    if os.path.lexists(final_abs):
        raise ArchiveBlocked(
            "%s: archive target %r already owned;"
            " source kept, target intact" % (BLOCK_ARCHIVE_EXISTS, final_abs),
            BLOCK_ARCHIVE_EXISTS,
            archive_final_path=final_abs,
            source_hash="sha256:" + _sha256_file_hex(source_abs),
            source_kept=True,
            **_target_proof(final_abs),
        )
    source_hash = "sha256:" + _sha256_file_hex(source_abs)
    if expected_hash is not None and source_hash != expected_hash:
        raise ArchiveError(
            "source hash %s != expected %s: refusing to move" % (source_hash, expected_hash)
        )
    os.makedirs(os.path.dirname(final_abs), exist_ok=True)
    if os.path.lexists(final_abs):
        raise ArchiveBlocked(
            "%s: archive target %r appeared during makedirs;"
            " source kept" % (BLOCK_ARCHIVE_EXISTS, final_abs),
            BLOCK_ARCHIVE_EXISTS,
            archive_final_path=final_abs,
            source_kept=True,
            **_target_proof(final_abs),
        )
    if _same_device(source_abs, os.path.dirname(final_abs)):
        return _move_same_device(source_abs, final_abs, source_hash)
    return _move_cross_device(source_abs, final_abs, source_hash)
