"""S9-T02: Stage9 new-edition Paragraph formatter (V1.8 #47 / #30; V2.7 tuned).

Implements STAGE9-PLAN S9-T02, formatter half (V1.8 ``# 47`` Natural
Paragraph rule order + ``# 30`` render profile layering):

* ``FORMATTER_VERSION`` (``para-v2.7``) + ``PARA_PARAMS_V2`` (versioned
  fixed values) land only in the ``# 30`` ``paragraph_formatter_
  version`` / ``paragraph_parameters`` profile fields (new profile hash
  => new Render Revision via the stage3 derive API = Case 5). The other
  three profile fields are inherited unchanged, so the bump stays in
  the render layer.
* The ``# 47`` rule order (Long Pause > Strong Punctuation > Target
  Length > Hard Max) is frozen: this module holds no paragraphing
  engine of its own and every call below runs the untouched
  ``stage3.render.render_paragraphs``. ``RULE_ORDER`` names that order
  for audit, and ``check_rule_order`` probes each rule behaviourally.
* Pure deterministic formatting only: no network, no hosted model, no
  text-generation service, no rewording, no guessing. Segment text
  passes through byte-identical except for paragraph joins/splits and
  CJK de-spacing (spaces between two CJK chars are removed; all other
  characters are untouched).

V2.7 tuning (params/rules only, no architecture change, no LLM):

* ``PARA_PARAMS_V2`` is the single source of truth for the thresholds.
  Both production paths read it and nothing re-hardcodes the numbers:
  the engine wrapper (``render_with_v2`` -> ``_engine_params``) and the
  app-side production post-pass (``app._apply_v25_postpass`` calls
  ``render_with_v2``) share the same dict, so one edit moves both.
* ``target_chars`` 80 -> 220: long whole paragraphs (the engine only
  breaks at punctuation once ~220 chars are accumulated).
* ``hard_max_chars`` 120 -> 450 (X=450): paragraphs may grow to ~450
  chars. The frozen engine only breaks *between* segments, so
  ``render_with_v2`` adds a pure post-pass that splits any over-long
  paragraph *inside* at weak punctuation, else at a word-safe boundary
  (never inside an ASCII word such as ``Deepseek``), else hard-cut.
* ``min_paragraph_chars`` 30 -> 80: a pure post-pass merges sub-80-char
  fragments with a neighbour (never exceeding the 450 hard cap) so
  pause-split single sentences join back into whole paragraphs.
* History: para-v1 {1.5, 180, 400}; para-v2 {1.5, 240, 400};
  para-v2.5 {1.5, 120, 200, 40}; para-v2.6 {1.5, 80, 120, 30};
  para-v2.7 {1.5, 220, 450, 80}.
* Both post-passes are pure functions on strings; ``RULE_ORDER`` stays
  frozen (engine priority untouched).

Every function here is pure (no IO, no handle, no row effects).
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage3 import render as _render  # noqa: E402 (read-only reuse)

# New-edition formatter version. Lives only in src/stage9/ + central-DB
# rows minted through the stage3 derive API; stage3 files untouched.
FORMATTER_VERSION = "para-v2.7"

# The frozen formatter this edition supersedes.
BASE_FORMATTER_VERSION = "para-v1"

# Versioned fixed values (V2.7 tuned; X=450 hard cap, MIN=80 anti-shatter).
# Single source of truth: the engine wrapper (render_with_v2 /
# _engine_params) and the production post-pass (_enforce_hard_cap /
# _merge_shorts, reached by app._apply_v25_postpass) all read this dict,
# so no threshold is repeated anywhere else.
# Versus para-v2.6 {1.5, 80, 120, 30}: target 80 -> 220 (long whole
# paragraphs), hard_max 120 -> 450, MIN 30 -> 80 (pause-split single
# sentences merge back). pause stays put. min_paragraph_chars rides
# inside the profile so a MIN change also mints a new Render Revision
# (Case 5); the frozen engine ignores the extra key (it reads only the
# three above).
PARA_PARAMS_V2 = {
    "pause_threshold_s": 1.5,
    "target_chars": 220,
    "hard_max_chars": 450,
    "min_paragraph_chars": 80,
}

# Weak sentence punctuation preferred as intra-paragraph split points
# for the V2.6 hard-cap post-pass (covers，。、；：plus the strong set).
WEAK_SPLIT_PUNCT = (
    "。", "！", "？", "…", "，", "、", "；", "：",
    "!", "?", ".", ",", ";", ":",
)

# Frozen #47 priority, highest first (names for audit; the engine
# itself stays inside stage3.render).
RULE_ORDER = (
    "long_pause",
    "strong_punctuation",
    "target_length",
    "hard_max",
)


class FormatterError(ValueError):
    """FAIL: bad formatter params / empty paragraphing input."""


def new_render_profile() -> dict:
    """A ``# 30`` profile carrying only the new formatter version."""
    if BASE_FORMATTER_VERSION != _render.DEFAULT_PROFILE.get(
        "paragraph_formatter_version"
    ):
        raise FormatterError(
            "frozen base formatter moved; refusing to invent a new base"
        )
    profile = copy.deepcopy(_render.DEFAULT_PROFILE)
    profile["paragraph_formatter_version"] = FORMATTER_VERSION
    profile["paragraph_parameters"] = copy.deepcopy(PARA_PARAMS_V2)
    return profile


def _engine_params() -> dict:
    """The three keys the frozen engine reads (MIN is wrapper-only)."""
    return {
        "pause_threshold_s": PARA_PARAMS_V2["pause_threshold_s"],
        "target_chars": PARA_PARAMS_V2["target_chars"],
        "hard_max_chars": PARA_PARAMS_V2["hard_max_chars"],
    }


def _is_cjk(ch: str) -> bool:
    """True for CJK / kana / hangul chars (de-spacing only touches these)."""
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0xF900 <= o <= 0xFAFF
        or 0x3040 <= o <= 0x30FF
        or 0xAC00 <= o <= 0xD7AF
        or 0xFF00 <= o <= 0xFFEF
    )


def _is_ascii_word_char(ch: str) -> bool:
    """True for [A-Za-z0-9] (cutting inside such a run splits a word)."""
    return ch.isascii() and ch.isalnum()


def _despace_cjk(text: str) -> str:
    """Remove spaces between two CJK chars (engine joins segments with " ").

    Only CJK-SPACES-CJK runs are collapsed; spaces next to ASCII words
    (e.g. ``给 App 接入``) are kept. Pure, deterministic, no rewording.
    """
    if " " not in text:
        return text
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        if ch == " " and out and i + 1 < n:
            if _is_cjk(out[-1]) and _is_cjk(text[i + 1]):
                continue
        out.append(ch)
    return "".join(out).strip()


def _smart_join(left: str, right: str) -> str:
    """Join two fragments: no space between two CJK chars, else one space."""
    left, right = left.strip(), right.strip()
    if not left:
        return right
    if not right:
        return left
    if _is_cjk(left[-1]) and _is_cjk(right[0]):
        return left + right
    return left + " " + right


def _split_overlong(text: str, hard_max: int,
                    min_keep: int | None = None) -> list:
    """Split one over-long paragraph into <= hard_max pieces (pure).

    Priority: (1) cut after the last weak-punctuation char within the
    first hard_max chars, provided the head keeps >= min_keep chars
    (no tiny heads); (2) extend forward (at most +200 chars past
    hard_max) to the next weak punctuation so a sentence is never cut
    mid-sentence when its end is near; (3) cut at a word-safe boundary
    inside the window (never inside an ASCII word run such as
    ``Deepseek`` — the cut walks back at most 30 chars to a boundary);
    (4) hard-cut exactly at hard_max as the last resort (e.g. uniform
    no-punctuation input). Deterministic, no guessing, no rewording.
    """
    keep = int(min_keep) if min_keep is not None else int(
        PARA_PARAMS_V2["min_paragraph_chars"])
    out: list[str] = []
    rest = text.strip()
    while len(rest) > hard_max:
        window = rest[:hard_max]
        cut = -1
        for i, ch in enumerate(window):
            if ch in WEAK_SPLIT_PUNCT:
                cut = i + 1
        if cut >= keep:
            out.append(rest[:cut].strip())
            rest = rest[cut:].strip()
            continue
        # No usable punctuation in window: look ahead for a near end.
        fwd_limit = min(len(rest), hard_max + 200)
        fwd_cut = -1
        for i in range(hard_max, fwd_limit):
            if rest[i] in WEAK_SPLIT_PUNCT:
                fwd_cut = i + 1
                break
        if fwd_cut > 0:
            out.append(rest[:fwd_cut].strip())
            rest = rest[fwd_cut:].strip()
            continue
        # Word-safe fallback: walk back at most 30 chars out of an
        # ASCII word run; uniform-word input keeps the hard cut.
        cut = hard_max
        steps = 0
        while (
            steps < 30
            and cut > keep
            and cut < len(rest)
            and _is_ascii_word_char(rest[cut - 1])
            and _is_ascii_word_char(rest[cut])
        ):
            cut -= 1
            steps += 1
        out.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return [p for p in out if p]


def _enforce_hard_cap(paragraphs: list, hard_max: int) -> list:
    """Post-pass 1 (V2.7): keep paragraphs within hard_max (sentence-safe)."""
    out: list[str] = []
    for para in paragraphs:
        if len(para) <= hard_max:
            out.append(para)
        else:
            out.extend(_split_overlong(para, hard_max))
    return out


def _merge_shorts(paragraphs: list, min_chars: int,
                  hard_max: int) -> list:
    """Post-pass 2 (V2.7): merge sub-min fragments, anti-shatter.

    Short fragments join the following paragraph (last one joins the
    previous); a merge that would exceed hard_max is refused so the
    cap guarantee survives. A lone short paragraph with nothing to
    join stays as-is. Joins use ``_smart_join`` (no space between two
    CJK chars) instead of a blanket English space.
    """
    if not paragraphs:
        return []
    # Engine joins segments with English spaces; drop the ones between
    # two CJK chars first so length accounting sees the real text.
    paragraphs = [_despace_cjk(p) for p in paragraphs]
    out: list[str] = []
    pending = ""
    for para in paragraphs:
        if pending:
            joined = _smart_join(pending, para)
            if len(joined) <= hard_max:
                para = joined
                pending = ""
            else:
                out.append(pending)
                pending = ""
                if len(para) < min_chars:
                    pending = para
                    continue
                out.append(para)
                continue
        if len(para) < min_chars:
            pending = _smart_join(pending, para) if pending else para
        else:
            out.append(para)
    if pending:
        if out and len(_smart_join(out[-1], pending)) <= hard_max:
            out[-1] = _smart_join(out[-1], pending)
        else:
            out.append(pending)
    return [_despace_cjk(p) for p in out]


def split_segments_for_engine(segments: list,
                              hard_max: int | None = None) -> list:
    """Pre-split over-long segment texts for the frozen engine (pure).

    Production helper (option ② segment-side): any single
    segment text longer than ``hard_max`` (default X=PARA_PARAMS_V2
    hard_max, 450) is cut with the same ``_split_overlong``
    sentence-safe rule into <=hard_max pieces, preserving all other
    keys and fanning ids as ``<id>#p<i>``. Short segments pass through
    untouched (same object content, new list). The frozen engine only
    breaks *between* segments, so this guarantees the single-long-
    segment case without touching
    stage3 files. Multi-segment accumulation overflow + crumbs still
    need ``postprocess_paragraphs`` after render (production applies
    both via ``render_with_v2`` recompute in app).
    """
    cap = int(hard_max) if hard_max is not None else int(
        PARA_PARAMS_V2["hard_max_chars"])
    out: list = []
    for seg in segments:
        try:
            text = str(seg.get("text", "")) if isinstance(seg, dict) else ""
        except Exception:
            out.append(seg)
            continue
        if len(text.strip()) <= cap:
            out.append(seg)
            continue
        pieces = _split_overlong(text, cap)
        base_id = str(seg.get("id", "")) if isinstance(seg, dict) else ""
        for i, piece in enumerate(pieces):
            if isinstance(seg, dict):
                nxt = dict(seg)
                nxt["text"] = piece
                if base_id:
                    nxt["id"] = "%s#p%d" % (base_id, i)
                out.append(nxt)
            else:
                out.append(piece)
    return out


def postprocess_paragraphs(paragraphs: list,
                           hard_max: int | None = None,
                           min_chars: int | None = None) -> list:
    """Apply the two V2.7 post-passes to engine paragraphs (pure).

    ``_enforce_hard_cap`` (X=PARA_PARAMS_V2 hard_max, 450) then
    ``_merge_shorts`` (MIN=PARA_PARAMS_V2 min, 80).
    Production calls this indirectly via ``render_with_v2`` recompute
    (app overwrites the committed render md); exposed separately so
    app/tests can post-process without re-running the engine.
    """
    cap = int(hard_max) if hard_max is not None else int(
        PARA_PARAMS_V2["hard_max_chars"])
    floor = int(min_chars) if min_chars is not None else int(
        PARA_PARAMS_V2["min_paragraph_chars"])
    return _merge_shorts(_enforce_hard_cap(list(paragraphs), cap),
                         floor, cap)


def render_with_v2(segments: list) -> list:
    """Run the frozen paragraphing engine with the new params (pure).

    V2.7: frozen engine (target 220 / hard_max 450, both read from
    ``PARA_PARAMS_V2`` via ``_engine_params``) + hard-cap post-pass
    (X=450, sentence-safe intra splits, never inside an ASCII word) +
    short merge post-pass (MIN=80, pause-split single sentences merge
    back into whole paragraphs) + CJK de-spacing.
    """
    paras = _render.render_paragraphs(segments, _engine_params())
    hard_max = int(PARA_PARAMS_V2["hard_max_chars"])
    min_chars = int(PARA_PARAMS_V2["min_paragraph_chars"])
    paras = _enforce_hard_cap(paras, hard_max)
    paras = _merge_shorts(paras, min_chars, hard_max)
    if not paras:
        raise FormatterError("paragraphing produced no output")
    return paras


def check_rule_order() -> dict:
    """Probe each ``# 47`` rule behaviourally (pure, no IO).

    Returns ``{"order": RULE_ORDER, "probes": {...}, "all_pass": bool}``.
    Thresholds come from ``PARA_PARAMS_V2`` so the probes test the
    edition under test; the priority itself is inherited from the
    untouched stage3 engine. Two wrapper probes (hard cap X=hard_max,
    MIN anti-shatter) run over ``render_with_v2``.
    """
    pause_thr = float(PARA_PARAMS_V2["pause_threshold_s"])
    target = int(PARA_PARAMS_V2["target_chars"])
    hard_max = int(PARA_PARAMS_V2["hard_max_chars"])
    min_chars = int(PARA_PARAMS_V2["min_paragraph_chars"])
    engine = _engine_params()
    probes: dict[str, bool] = {}

    # 1. Long Pause: an 8s gap breaks even plain text.
    paras = _render.render_paragraphs(
        [
            {"id": "p1", "text": "alpha", "start": 0.0, "end": 1.0},
            {"id": "p2", "text": "beta", "start": 1.0 + pause_thr + 7.0,
             "end": 1.0 + pause_thr + 8.0},
        ],
        engine,
    )
    probes["long_pause"] = paras == ["alpha", "beta"]

    # 2. Strong Punctuation: accumulated text past target ending with a
    #    strong stop breaks at the next boundary.
    paras = _render.render_paragraphs(
        [
            {"id": "s1", "text": "x" * target + "。", "start": 0.0, "end": 5.0},
            {"id": "s2", "text": "tail", "start": 5.2, "end": 6.0},
        ],
        engine,
    )
    probes["strong_punctuation"] = (
        len(paras) == 2 and paras[0].endswith("。")
    )

    # 3. Target Length: past target with only weak punctuation still
    #    breaks; past target with no punctuation does not (control).
    paras = _render.render_paragraphs(
        [
            {"id": "w1", "text": "y" * target + "，", "start": 0.0, "end": 5.0},
            {"id": "w2", "text": "tail", "start": 5.2, "end": 6.0},
        ],
        engine,
    )
    control = _render.render_paragraphs(
        [
            {"id": "c1", "text": "z" * (target + 10), "start": 0.0, "end": 5.0},
            {"id": "c2", "text": "tail", "start": 5.2, "end": 6.0},
        ],
        engine,
    )
    probes["target_length"] = len(paras) == 2 and len(control) == 1

    # 4. Hard Max: past the cap breaks even with no punctuation at all.
    paras = _render.render_paragraphs(
        [
            {"id": "h1", "text": "w" * (hard_max + 20),
             "start": 0.0, "end": 5.0},
            {"id": "h2", "text": "tail", "start": 5.2, "end": 6.0},
        ],
        engine,
    )
    probes["hard_max"] = len(paras) == 2

    # 5. V2.7 hard cap (X=hard_max): a single over-long segment with no
    #    punctuation at all still yields no paragraph over the cap.
    paras = render_with_v2(
        [
            {"id": "x1", "text": "甲" * (hard_max * 2 + 50),
             "start": 0.0, "end": 9.0},
        ]
    )
    probes["hard_cap_v27"] = (
        len(paras) >= 2 and all(len(p) <= hard_max for p in paras)
    )

    # 5b. V2.7 never splits inside an ASCII word: a cut falling inside
    #    ``Deepseek`` must move to the word boundary.
    long_head = "甲" * (hard_max - 10)
    paras = render_with_v2(
        [
            {"id": "w1", "text": long_head + "Deepseek很好",
             "start": 0.0, "end": 9.0},
        ]
    )
    joined = "".join(paras)
    probes["no_midword_cut"] = (
        "Deepseek" in joined and all(len(p) <= hard_max for p in paras)
    )

    # 6. V2.7 anti-shatter (MIN): pause-split crumbs merge back instead
    #    of staying碎渣.
    paras = render_with_v2(
        [
            {"id": "m%d" % i, "text": "ab",
             "start": float(i * 10), "end": float(i * 10 + 1)}
             for i in range(3)
        ]
    )
    probes["min_merge_v27"] = len(paras) == 1

    # 6b. V2.7 CJK de-spacing: spaces between two CJK chars collapse.
    probes["cjk_despace"] = _despace_cjk("寄到哪里 也就是") == "寄到哪里也就是"

    return {
        "order": list(RULE_ORDER),
        "formatter_version": FORMATTER_VERSION,
        "params": dict(PARA_PARAMS_V2),
        "probes": probes,
        "all_pass": all(probes.values()),
    }
