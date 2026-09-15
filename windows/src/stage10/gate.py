"""S10-T04b: Capability split + G3 assembly (A -> B -> C).

Implements the gate arm of STAGE10-PLAN S10-T04 only::

    probe_archive_capability(source_path, archive_final_path):
      只读复用 stage4.volume_probe 语义 (local 卷 + dest exclusive-create
      + hardlink link-commit 能力 + 源/目的同 device) 后判定:
      A = 同 device 且 link 可用; B = O_EXCL 可用; 否则 C.

    archive_source(source_id, con, archive_root, ...):
      verify (T01) -> G3 publish 重确认 + 诱饵 canonical 未改 (T01) ->
      目标预检 (已存在即 BLOCK, cover 计数恒 0) -> 按 Capability
      A/B/C 分流执行. 本函数不写中央库任何行 (Source 四列更新只在
      commit.commit_archive_success), 以便三表快照口径举证.

Path guards: archive Final 必须落在 archive_root 内, 源必须落在
input_root 内 (给出时); 前缀外路径拒收 (FAIL, 不动任何字节).
"""

from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage10 import level_a as _a  # noqa: E402
from stage10 import level_b as _b  # noqa: E402
from stage10 import level_c as _c  # noqa: E402
from stage10 import verify_archive as _v  # noqa: E402

CODE_PATH_ESCAPE = "ARCHIVE_PATH_ESCAPE"
CODE_UNKNOWN_SOURCE = "ARCHIVE_UNKNOWN_SOURCE"
CODE_ALREADY = "ALREADY_ARCHIVED"
PASS_ARCHIVED = "ARCHIVE_COMMITTED"


def _commonpath_inside(root_abs: str, candidate_abs: str) -> bool:
    try:
        return os.path.commonpath([root_abs, candidate_abs]) == root_abs
    except (ValueError, OSError):
        return False


def probe_archive_capability(source_path: str, archive_final_path: str) -> dict:
    """Measure the archive route (read-only probes, no byte staged)."""
    from stage4 import volume_probe as _vp  # noqa: PLC0415 (read-only reuse)

    source_abs = os.path.abspath(source_path)
    final_abs = os.path.abspath(archive_final_path)
    dest_dir = os.path.dirname(final_abs)
    os.makedirs(dest_dir, exist_ok=True)
    probe = _vp.probe_volume(final_abs)
    try:
        same_device = os.stat(source_abs).st_dev == os.stat(dest_dir).st_dev
    except OSError:
        same_device = False
    local = probe.get("local_or_remote") == "local"
    link_ok = bool(probe.get("supports_hardlink"))
    xcre_ok = bool(probe.get("supports_exclusive_create"))
    if local and same_device and link_ok:
        level, reason = "A", "same device + link commit available"
    elif local and xcre_ok:
        level, reason = "B", "exclusive-create reservation available"
    else:
        level, reason = (
            "C",
            "no reliable no-cover path (local=%r same_device=%r"
            " link=%r xcre=%r)" % (local, same_device, link_ok, xcre_ok),
        )
    return {
        "level": level,
        "reason": reason,
        "same_device": same_device,
        "local_or_remote": probe.get("local_or_remote"),
        "supports_hardlink": link_ok,
        "supports_exclusive_create": xcre_ok,
        "supports_atomic_rename": bool(probe.get("supports_atomic_rename")),
        "filesystem_type": probe.get("filesystem_type"),
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def archive_source(
    source_id: str,
    con,
    archive_root: str,
    input_root: str | None = None,
    archive_final_path: str | None = None,
    archive_relpath: str | None = None,
    capability_override: str | None = None,
) -> dict:
    """Run Verify -> G3 -> target pre-check -> A/B/C for one source."""
    archive_root_abs = os.path.abspath(archive_root)
    if archive_final_path is not None:
        final_abs = os.path.abspath(archive_final_path)
    elif archive_relpath is not None:
        rel = archive_relpath.strip().strip(os.sep)
        if not rel or rel in (".", "..") or rel.startswith(".." + os.sep):
            return _fail(source_id, None, "empty or escaping archive_relpath")
        final_abs = os.path.abspath(os.path.join(archive_root_abs, rel))
    else:
        return _fail(source_id, None, "archive target required")
    if not _commonpath_inside(archive_root_abs, final_abs):
        return _fail(source_id, final_abs, "final outside archive_root")
    row = _v.read_source_row(con, source_id)
    if row is None:
        return _fail(source_id, final_abs, "unknown source_id")
    source_abs = os.path.abspath(row["current_path"])
    discovered_abs = os.path.abspath(row["path_identity_key"] or source_abs)
    if input_root is not None and not _commonpath_inside(
        os.path.abspath(input_root), discovered_abs
    ):
        return _fail(source_id, final_abs, "source outside input_root")
    content_identity = row["content_identity"]
    if (
        row.get("status") == "ARCHIVED"
        and os.path.abspath(row.get("current_path") or "") == final_abs
        and os.path.isfile(final_abs)
        and "sha256:" + _sha256_file_hex(final_abs) == content_identity
    ):
        return {
            "verdict": "PASS",
            "code": CODE_ALREADY,
            "level": None,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": "source already archived at this final; no byte moved",
            "receipt": None,
            "idempotent_retry": True,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    verify = _v.verify_source_for_archive(source_id, con)
    if verify["verdict"] != "PASS":
        return {
            "verdict": "BLOCK",
            "code": verify["code"],
            "level": None,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": verify["reason"],
            "verify": verify,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    publish = _v.assert_publish_present(source_id, con)
    if publish["verdict"] != "PASS":
        return {
            "verdict": "BLOCK",
            "code": publish["code"],
            "level": None,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": publish["reason"],
            "publish": publish,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    if os.path.lexists(final_abs):
        proof = {"target_exists": True}
        if os.path.isfile(final_abs) and not os.path.islink(final_abs):
            proof["target_hash"] = "sha256:" + _sha256_file_hex(final_abs)
        return {
            "verdict": "BLOCK",
            "code": _a.BLOCK_ARCHIVE_EXISTS,
            "level": None,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": "archive target already owned; source kept",
            "target_cover_count": 0,
            "source_kept": True,
            **proof,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    capability = None
    if capability_override in ("A", "B", "C"):
        level = capability_override
    else:
        capability = probe_archive_capability(source_abs, final_abs)
        level = capability["level"]
    try:
        if level == "A":
            receipt = _a.archive_level_a(
                source_abs, final_abs, expected_hash=content_identity
            )
        elif level == "B":
            receipt = _b.archive_level_b(
                source_abs, final_abs, content_identity, source_id
            )
        else:
            receipt = _c.archive_level_c(
                source_abs, final_abs, expected_hash=content_identity
            )
    except (_a.ArchiveBlocked, _b.ArchiveBlocked, _c.ArchiveBlocked) as exc:
        return {
            "verdict": "BLOCK",
            "code": exc.status,
            "level": level,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": str(exc),
            "detail": exc.detail,
            "capability": capability,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    except (_a.ArchiveError, _b.ArchiveError, _v.ArchiveSourceError) as exc:
        return {
            "verdict": "FAIL",
            "code": "ARCHIVE_FAIL",
            "level": level,
            "source_id": source_id,
            "source_path": source_abs,
            "archive_final_path": final_abs,
            "reason": str(exc),
            "capability": capability,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    return {
        "verdict": "PASS",
        "code": PASS_ARCHIVED,
        "level": level,
        "source_id": source_id,
        "source_path": source_abs,
        "archive_final_path": final_abs,
        "reason": "level %s archive committed; DB update left to commit step" % (level,),
        "receipt": receipt,
        "capability": capability,
        "asr_calls": 0,
        "whisper_calls": 0,
    }


def _fail(source_id: str, final_abs: str | None, reason: str) -> dict:
    code = CODE_PATH_ESCAPE if "outside" in reason or "escap" in reason else (
        CODE_UNKNOWN_SOURCE if "unknown" in reason else "ARCHIVE_FAIL"
    )
    return {
        "verdict": "FAIL",
        "code": code,
        "level": None,
        "source_id": source_id,
        "source_path": None,
        "archive_final_path": final_abs,
        "reason": reason,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
