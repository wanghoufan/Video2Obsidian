"""S6-T02 矩阵与逐字节断言。"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MATRIX = [
    "测试 中文丨Case (A).mp4",
    "AI 博主A DeepSeek V4 分析.mp4",
    "my doc 丨 test [v1] (final).mp4",
    "Clip.mp4",
    "clip.mp4",
    "UPPER.MP4",
    "my.clip.v2.mp4",
    "caf\u00e9.mp4",
    "cafe\u0301.mp4",
    "空格 前后丨括号 (B) [C].mp4",
    "中文丨空格 (C) [D] Case.MP4",
]


def assert_byte_preserved(abs_path, path_identity_key, source_relative_path, canonical_path,
                           output_root=None):
    """逐字节一致断言；任何一处不同即抛错。

    output_root 为诱饵 Root：提供时加验两条目录门——输出前缀恒为
    Root、父目录逐级保留（顶层文件即等于 Root）。
    """
    if path_identity_key != abs_path:
        raise AssertionError("不一致 %r" % (abs_path,))
    if not source_relative_path or os.path.isabs(source_relative_path):
        raise AssertionError("不一致 %r" % (source_relative_path,))
    for p in source_relative_path.split(os.sep):
        if p in ("..", ".") or not p:
            raise AssertionError("不一致 %r" % (source_relative_path,))
    if not canonical_path.endswith(".md"):
        raise AssertionError("不一致 %r" % (canonical_path,))
    base = os.path.basename(source_relative_path)
    stem_raw, _ext = os.path.splitext(base)
    if not stem_raw:
        raise AssertionError("不一致 %r" % (source_relative_path,))
    want_tail = stem_raw + ".md"
    if not canonical_path.endswith(want_tail):
        raise AssertionError("不一致 %r" % (canonical_path,))
    if output_root is not None:
        root_abs = os.path.abspath(output_root)
        canon_abs = os.path.abspath(canonical_path)
        if os.path.commonpath([root_abs, canon_abs]) != root_abs:
            raise AssertionError("输出前缀非诱饵Root %r" % (canonical_path,))
        want_dir = os.path.abspath(
            os.path.join(root_abs, os.path.dirname(source_relative_path)))
        if os.path.dirname(canon_abs) != want_dir:
            raise AssertionError("目录未逐级保留 %r" % (canonical_path,))
    return {"ok": True}


def entity_key(path):
    """取同一实体判定键。"""
    st = os.stat(path)
    return (st.st_dev, st.st_ino)


def is_same_entity(path_a, path_b):
    """两路径是否指向同一实体。"""
    return entity_key(path_a) == entity_key(path_b)
