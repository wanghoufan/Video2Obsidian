"""S6-T01 路径映射与父目录辅助。"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage5.watcher import VIDEO_SUFFIXES


class MirrorEscapeError(ValueError):
    """越界时抛出的错误。"""
    pass


class MirrorBlockedError(RuntimeError):
    """父目录被文件挡住时抛出的错误。"""
    pass


def resolve_canonical(input_root, output_root, abs_source_path):
    """由输入根与源绝对路径算出相对路径与诱饵输出路径；越界抛错；本身不触碰磁盘。"""
    input_abs = os.path.abspath(input_root)
    output_abs = os.path.abspath(output_root)
    src_abs = os.path.abspath(abs_source_path)
    rel = os.path.relpath(src_abs, input_abs)
    if rel != rel.strip():
        raise MirrorEscapeError("首尾空格与Stage4口径冲突BLOCK %r" % (abs_source_path,))
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    if rel == "." or not rel:
        raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    parts = rel.split(os.sep)
    for p in parts:
        if p in ("..", ".") or not p:
            raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    base = parts[-1]
    stem_raw, ext = os.path.splitext(base)
    if ext.lower() in VIDEO_SUFFIXES and stem_raw:
        stem = base[: len(base) - len(ext)]
    else:
        if not stem_raw:
            raise MirrorEscapeError("越界 %r" % (abs_source_path,))
        stem = stem_raw
    if not stem:
        raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    if len(parts) > 1:
        canonical_abs = os.path.abspath(os.path.join(output_abs, *parts[:-1], stem + ".md"))
    else:
        canonical_abs = os.path.abspath(os.path.join(output_abs, stem + ".md"))
    if os.path.commonpath([output_abs, canonical_abs]) != output_abs:
        raise MirrorEscapeError("越界 %r" % (abs_source_path,))
    return {"source_relative_path": rel, "canonical_output_path": canonical_abs}


def ensure_parent_dir(canonical_path):
    """建好父目录；遇文件挡路抛错，不删不替。"""
    target_abs = os.path.abspath(canonical_path)
    parent = os.path.dirname(target_abs)
    if os.path.isfile(parent):
        raise MirrorBlockedError("挡住 %r" % (parent,))
    try:
        os.makedirs(parent, exist_ok=True)
    except OSError as exc:
        raise MirrorBlockedError("挡住 %r" % (parent,)) from exc
    if not os.path.isdir(parent):
        raise MirrorBlockedError("挡住 %r" % (parent,))
    return {"parent": parent, "ready": True}
