"""S10-T04a: Level C Unsupported-block (V1.8 §58).

Implements the Level C arm of STAGE10-PLAN S10-T04 only::

    archive_level_c(source_path, archive_final_path):
      无可靠 Exclusive Create / No-Cover 原语即
      BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM — 零拷贝、零删除、
      源保留. 本模块结构上没有任何写字节/删文件的调用.

The refusal carries a proof that the source is intact (exists +
optional hash) so QA can assert Mis-delete == 0 on this path.
"""

from __future__ import annotations

import hashlib
import os

BLOCK_UNSUPPORTED = "BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM"
LEVEL = "C"


class ArchiveBlocked(RuntimeError):
    """BLOCK: the archive filesystem offers no reliable no-cover path."""

    def __init__(self, message: str, status: str, **detail):
        super().__init__(message)
        self.status = status
        self.detail = detail


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def verdict_unsupported(
    source_path: str, archive_final_path: str, expected_hash: str | None = None
) -> dict:
    """Build the Level C BLOCK verdict (no byte moved, none removed)."""
    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)
    exists = os.path.isfile(source_abs) and not os.path.islink(source_abs)
    source_hash = ("sha256:" + _sha256_file_hex(source_abs)) if exists else None
    intact = exists and (expected_hash is None or source_hash == expected_hash)
    return {
        "verdict": "BLOCK",
        "code": BLOCK_UNSUPPORTED,
        "level": LEVEL,
        "reason": "archive volume offers no reliable exclusive-create"
        " no-cover path; source kept, nothing staged, nothing removed",
        "source_path": source_abs,
        "archive_final_path": final_abs,
        "source_exists": exists,
        "source_hash": source_hash,
        "source_intact": intact,
        "target_touched": False,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def archive_level_c(
    source_path: str, archive_final_path: str, expected_hash: str | None = None
) -> dict:
    """Level C always refuses (raises); the verdict helper holds detail."""
    verdict = verdict_unsupported(source_path, archive_final_path, expected_hash)
    raise ArchiveBlocked(
        "%s: refusing archive of %r (source intact=%r)"
        % (BLOCK_UNSUPPORTED, verdict["source_path"], verdict["source_intact"]),
        BLOCK_UNSUPPORTED,
        **{k: v for k, v in verdict.items() if k not in ("verdict", "reason")},
    )
