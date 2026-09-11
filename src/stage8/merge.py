"""S8-T03 overlap merge: core ownership, then stamps, then text.

Priority order: core_region > absolute_timestamp > overlap_timestamp
> text_similarity. The text step only pairs neighbours sharing one
identical absolute_start, so segments with unique starts are never
touched and content outside overlap zones stays byte-identical. There
is no whole-list dedup pass.
"""

from __future__ import annotations

PRIORITY = (
    "core_region",
    "absolute_timestamp",
    "overlap_timestamp",
    "text_similarity",
)

_EPS = 1e-9


class MergeError(ValueError):
    """Raised on malformed chunk input."""


def _owns(core_lo: float, core_hi: float, is_last: bool, moment: float) -> bool:
    if moment < core_lo - _EPS:
        return False
    if is_last:
        return moment <= core_hi + _EPS
    return moment < core_hi - _EPS


def _check_chunk(item, pos: int) -> tuple:
    if not isinstance(item, dict):
        raise MergeError("chunk item %d must be a dict" % (pos,))
    chunk = item.get("chunk")
    segs = item.get("segments")
    if not isinstance(chunk, dict):
        raise MergeError("chunk item %d missing chunk plan" % (pos,))
    if not isinstance(segs, list):
        raise MergeError("chunk item %d segments must be a list" % (pos,))
    for key in ("index", "start_s", "end_s", "core_start_s", "core_end_s"):
        if key not in chunk:
            raise MergeError("chunk %d plan missing %r" % (pos, key))
        value = chunk[key]
        if key == "index":
            if chunk[key] != pos:
                raise MergeError("chunk index order broken at %d" % (pos,))
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MergeError("chunk %d plan %r must be a number" % (pos, key))
    for idx, seg in enumerate(segs):
        if not isinstance(seg, dict):
            raise MergeError("chunk %d segment %d must be a dict" % (pos, idx))
        for key in ("absolute_start", "absolute_end", "text"):
            if key not in seg:
                raise MergeError("chunk %d segment %d missing %r" % (pos, idx, key))
        if not isinstance(seg["text"], str):
            raise MergeError("chunk %d segment %d text must be str" % (pos, idx))
    return chunk, segs


def merge_chunks(chunk_items: list) -> dict:
    """Merge per-chunk absolute segments into one absolute timeline.

    Each item is ``{"chunk": planner_dict, "segments": [absolute]}``.
    Priority 1 (core_region): only segments whose absolute_start lands
    in their own chunk core are kept, so overlap double cover leaves
    exactly one copy. Priority 2 (absolute_timestamp): survivors sort
    by absolute_start. Priority 3 (overlap_timestamp): start ties order
    by absolute_end. Priority 4 (text_similarity): neighbours sharing
    one identical absolute_start AND identical text keep one copy.
    """
    if not isinstance(chunk_items, list) or not chunk_items:
        raise MergeError("need a non-empty chunk list")
    kept = []
    last = len(chunk_items) - 1
    for pos, item in enumerate(chunk_items):
        chunk, segs = _check_chunk(item, pos)
        is_last = pos == last
        for seg in segs:
            if _owns(
                float(chunk["core_start_s"]),
                float(chunk["core_end_s"]),
                is_last,
                float(seg["absolute_start"]),
            ):
                kept.append(dict(seg))
    kept.sort(key=lambda d: (d["absolute_start"], d["absolute_end"]))
    out = []
    for seg in kept:
        if (
            out
            and seg["absolute_start"] == out[-1]["absolute_start"]
            and seg.get("text") == out[-1].get("text")
        ):
            continue
        out.append(seg)
    prev = None
    for seg in out:
        moment = float(seg["absolute_start"])
        if prev is not None and moment < prev - _EPS:
            raise MergeError("merged timeline disorder refused")
        prev = moment
    return {
        "segments": out,
        "n": len(out),
        "priority": list(PRIORITY),
        "monotonic": True,
    }
