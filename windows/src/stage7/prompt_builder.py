"""S7-T02 prompt assembly with real tokenizer count first.

Windows 端 Stage 3：分词器统一走 ``asr_backend``（模型自带的
``tokenizer.json``，不联网、不用 Mac 端那套分词器）；计数口径与
Mac 端一致：``" " + 去空格文本``，预算 200 token。
"""

from __future__ import annotations

import os
import sys

if os.path.join(os.path.dirname(__file__), "..") not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asr_backend  # noqa: E402  (Windows 端唯一 ASR 后端适配层)

PROMPT_BUDGET_TOKENS = 200
PROMPT_ORDER = "Global->Topic->Creator"
PROMPT_BUILDER_VERSION = "pb-v1"

JOINER = "\uFF0C"


class PromptBuilderError(ValueError):
    """Raised when term input is missing or malformed."""


def _check_terms(terms, label: str) -> list:
    if not isinstance(terms, (list, tuple)):
        raise PromptBuilderError("level %r must be a list of str" % (label,))
    out = list(terms)
    for item in out:
        if not isinstance(item, str) or item == "":
            raise PromptBuilderError("level %r holds only non-empty str" % (label,))
    return out


def _get_tokenizer(_load=None):
    """Tokenizer comes from asr_backend (model-shipped tokenizer.json only)."""
    return asr_backend.load_tokenizer(_load=_load)


def count_tokens(text: str, _load=None) -> int:
    """Token count with the real model tokenizer (via asr_backend).

    口径同 Mac 端：``" " + 去空格文本`` 计数，预算 200 token。
    ``_load`` 是桩测注入点，透传给 asr_backend。
    """
    if not isinstance(text, str):
        raise PromptBuilderError("text must be str")
    if text.strip() == "":
        return 0
    return asr_backend.count_tokens(text, _load=_load)


def build_initial_prompt(
    global_terms,
    topic_terms,
    creator_terms,
    budget_tokens: int = PROMPT_BUDGET_TOKENS,
) -> dict:
    """Assemble initial_prompt in Global, Topic, Creator order.

    Count first with the real tokenizer, then join. When over
    budget, drop leading terms first so tail Creator entries stay.
    Each call is pure: no audio, no model, no IO.
    """
    if budget_tokens != PROMPT_BUDGET_TOKENS:
        raise PromptBuilderError("budget stays 200, got %r" % (budget_tokens,))
    g_terms = _check_terms(global_terms, "global")
    t_terms = _check_terms(topic_terms, "topic")
    c_terms = _check_terms(creator_terms, "creator")
    if not g_terms or not t_terms or not c_terms:
        raise PromptBuilderError("three levels required, one is empty")

    ordered = list(g_terms) + list(t_terms) + list(c_terms)
    full_text = JOINER.join(ordered)
    full_count = count_tokens(full_text)

    kept = list(ordered)
    dropped_terms = 0
    # Drop from head while over budget; tail stays intact.
    while kept and count_tokens(JOINER.join(kept)) > budget_tokens:
        kept = kept[1:]
        dropped_terms += 1
    if not kept:
        raise PromptBuilderError("budget too small for one term")

    text = JOINER.join(kept)
    # Last guard: a single giant term still over budget gets head
    # chars cut until it fits, tail chars stay.
    dropped_chars = 0
    while text and count_tokens(text) > budget_tokens:
        text = text[1:]
        dropped_chars += 1
    final_count = count_tokens(text)
    if final_count > budget_tokens:
        raise PromptBuilderError("unable to fit budget")

    truncated = bool(dropped_terms or dropped_chars or (full_count > budget_tokens))
    return {
        "initial_prompt": text,
        "token_count": final_count,
        "truncated_head": truncated,
        "truncated_head_tokens": int(full_count - final_count) if truncated else 0,
        "truncated_head_chars": int(len(full_text) - len(text)) if truncated else 0,
        "dropped_leading_terms": int(dropped_terms),
        "dropped_leading_chars": int(dropped_chars),
        "prompt_builder_version": PROMPT_BUILDER_VERSION,
        "budget_tokens": PROMPT_BUDGET_TOKENS,
        "order": PROMPT_ORDER,
    }


def build_for_chunks(term_sets: list) -> list:
    """Rebuild one prompt per chunk; each entry stands alone.

    Each item is a dict with global/topic/creator lists, or a
    (global, topic, creator) triple. A chunk never reuses the
    output of another chunk.
    """
    if not isinstance(term_sets, (list, tuple)) or not term_sets:
        raise PromptBuilderError("term_sets must be a non-empty list")
    out = []
    for idx, item in enumerate(term_sets):
        if isinstance(item, dict):
            g = item.get("global")
            t = item.get("topic")
            c = item.get("creator")
        elif isinstance(item, (list, tuple)) and len(item) == 3:
            g, t, c = item[0], item[1], item[2]
        else:
            raise PromptBuilderError("chunk %d malformed" % (idx,))
        built = build_initial_prompt(g, t, c)
        out.append(built)
    return out
