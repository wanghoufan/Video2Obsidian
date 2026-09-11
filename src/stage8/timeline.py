"""S8-T03 absolute timeline: relative-to-absolute mapping, dual kept."""

from __future__ import annotations


class TimelineError(ValueError):
    """Raised on malformed segment input or disordered absolute output."""


def _num(value, label: str, idx: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimelineError("segment %d %s must be a number" % (idx, label))
    return float(value)


def _check_seg(seg, idx: int) -> tuple:
    if not isinstance(seg, dict):
        raise TimelineError("segment %d must be a dict" % (idx,))
    for key in ("start", "end", "text"):
        if key not in seg:
            raise TimelineError("segment %d missing %r" % (idx, key))
    start = _num(seg["start"], "start", idx)
    end = _num(seg["end"], "end", idx)
    if start < 0 or end < 0:
        raise TimelineError("segment %d negative time refused" % (idx,))
    if end < start:
        raise TimelineError("segment %d end before start refused" % (idx,))
    if not isinstance(seg["text"], str):
        raise TimelineError("segment %d text must be str" % (idx,))
    return start, end


def _map_words(words, chunk_start: float, idx: int) -> list:
    if not isinstance(words, list):
        raise TimelineError("segment %d words must be a list" % (idx,))
    mapped = []
    for pos, word in enumerate(words):
        if not isinstance(word, dict):
            raise TimelineError("segment %d word %d must be a dict" % (idx, pos))
        if "start" not in word or "end" not in word:
            raise TimelineError("segment %d word %d missing time" % (idx, pos))
        start = _num(word["start"], "word start", idx)
        end = _num(word["end"], "word end", idx)
        if start < 0 or end < start:
            raise TimelineError("segment %d word %d bad time refused" % (idx, pos))
        item = dict(word)
        item["absolute_start"] = round(chunk_start + start, 3)
        item["absolute_end"] = round(chunk_start + end, 3)
        mapped.append(item)
    return mapped


def to_absolute(segments: list, chunk_start_s) -> list:
    """Map one chunk's relative segments to absolute time.

    Relative ``start``/``end`` stay as-is while ``absolute_start`` /
    ``absolute_end`` are added, so both stamps are kept. Word entries,
    when present, keep relative time and gain absolute stamps too
    (word ON/OFF both pass through untouched). Input must already run
    in non-decreasing relative start order, else refused.
    """
    if isinstance(chunk_start_s, bool) or not isinstance(chunk_start_s, (int, float)):
        raise TimelineError("chunk_start_s must be a number")
    chunk_start = float(chunk_start_s)
    if chunk_start < 0:
        raise TimelineError("chunk_start_s must not be negative")
    if not isinstance(segments, list):
        raise TimelineError("segments must be a list")
    out = []
    prev_start = None
    for idx, seg in enumerate(segments):
        start, _ = _check_seg(seg, idx)
        if prev_start is not None and start < prev_start - 1e-9:
            raise TimelineError("relative disorder at segment %d refused" % (idx,))
        prev_start = start
        item = dict(seg)
        item["absolute_start"] = round(chunk_start + seg["start"], 3)
        item["absolute_end"] = round(chunk_start + seg["end"], 3)
        if "words" in seg and seg["words"] is not None:
            item["words"] = _map_words(seg["words"], chunk_start, idx)
        out.append(item)
    return out


def check_monotonic(segments: list, key: str = "absolute_start") -> dict:
    """Fail-closed monotonic check over absolute time."""
    if not isinstance(segments, list):
        raise TimelineError("segments must be a list")
    prev = None
    for idx, seg in enumerate(segments):
        if not isinstance(seg, dict) or key not in seg:
            raise TimelineError("segment %d missing %r" % (idx, key))
        value = _num(seg[key], key, idx)
        if prev is not None and value < prev - 1e-9:
            raise TimelineError("absolute disorder at segment %d refused" % (idx,))
        prev = value
    return {"monotonic": True, "n": len(segments), "key": key}
