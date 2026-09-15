"""S6 装配与集成。"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage6.mirror import MirrorBlockedError, MirrorEscapeError, ensure_parent_dir, resolve_canonical
from stage6.unicode_cases import MATRIX, assert_byte_preserved, entity_key, is_same_entity
from stage4 import publish as _pub
from stage4 import volume_probe as _vp


def case_flag(output_root):
    """只读取回卷大小写标记。"""
    probe = _vp.probe_volume(output_root)
    return {"case_sensitive": probe.get("case_sensitive"), "volume_id": probe.get("volume_id")}


def publish_mirrored(input_root, output_root, abs_source_path, con, job_dir, render_revision_id, on_tmp_ready=None):
    """算路径建父目录后透传调用阶段四首发路径；不自建字节。"""
    input_abs = os.path.abspath(input_root)
    output_abs = os.path.abspath(output_root)
    mapping = resolve_canonical(input_abs, output_abs, abs_source_path)
    rel = mapping["source_relative_path"]
    canonical_abs = mapping["canonical_output_path"]
    if os.path.commonpath([output_abs, canonical_abs]) != output_abs:
        raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    ensure_parent_dir(canonical_abs)
    res = _pub.initial_publish(con, job_dir, render_revision_id, output_abs, rel, on_tmp_ready=on_tmp_ready)
    out = dict(res)
    out["source_relative_path"] = rel
    out["canonical_output_path"] = canonical_abs
    out["whisper_calls"] = 0
    out["asr_calls"] = 0
    return out


__all__ = [
    "MirrorBlockedError",
    "MirrorEscapeError",
    "MATRIX",
    "assert_byte_preserved",
    "case_flag",
    "ensure_parent_dir",
    "entity_key",
    "is_same_entity",
    "publish_mirrored",
    "resolve_canonical",
]
