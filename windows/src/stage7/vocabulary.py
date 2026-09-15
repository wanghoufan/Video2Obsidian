"""S7-T01 three-level word list load + snapshot."""

from __future__ import annotations

import hashlib
import json
import os

LEVELS = ("global", "topic", "creator")


class VocabularyError(ValueError):
    """Raised when word list input is missing or malformed."""


def _coerce_terms(src, label: str) -> list:
    """Return a copied list of terms for one level, byte-preserved.

    Accepts a list or tuple of str, or a path to a UTF-8 text file
    (one term per line). Terms are kept exactly as given: no lower,
    no strip of inner bytes, no slug, no dedup, no reorder. Empty
    input raises.
    """
    terms: list
    if isinstance(src, str) and os.path.isfile(src):
        with open(src, "r", encoding="utf-8") as fh:
            raw = fh.read().splitlines()
        # Keep lines exactly, drop only the file framing newline.
        # Skip purely empty lines so file tail newline stays neutral.
        terms = [line for line in raw if line != ""]
    elif isinstance(src, (list, tuple)):
        terms = list(src)
    else:
        raise VocabularyError(
            "level %r must be a list of str or a file path" % (label,)
        )
    if not terms:
        raise VocabularyError("level %r must not be empty" % (label,))
    for item in terms:
        if not isinstance(item, str) or item == "":
            raise VocabularyError(
                "level %r holds only non-empty str" % (label,)
            )
        if item.strip() == "":
            raise VocabularyError(
                "level %r holds only non-blank str" % (label,)
            )
    return list(terms)


def load_vocabulary(global_src, topic_src, creator_src) -> dict:
    """Load three levels, each preserved byte for byte.

    All three levels are required: a missing level raises.
    """
    if global_src is None or topic_src is None or creator_src is None:
        raise VocabularyError("three levels required, one is missing")
    vocab = {
        "global": _coerce_terms(global_src, "global"),
        "topic": _coerce_terms(topic_src, "topic"),
        "creator": _coerce_terms(creator_src, "creator"),
    }
    return vocab


def canonical_serialize(vocab: dict) -> bytes:
    """Canonical bytes of a vocab dict (fixed key order via sort)."""
    if not isinstance(vocab, dict):
        raise VocabularyError("vocab must be a dict")
    for level in LEVELS:
        if level not in vocab:
            raise VocabularyError("vocab missing level %r" % (level,))
        items = vocab[level]
        if not isinstance(items, list) or not items:
            raise VocabularyError("level %r must be a non-empty list" % (level,))
        for item in items:
            if not isinstance(item, str) or item == "":
                raise VocabularyError("level %r holds only str" % (level,))
    subset = {level: list(vocab[level]) for level in LEVELS}
    text = json.dumps(
        subset, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return text.encode("utf-8")


def dictionary_snapshot(vocab: dict) -> str:
    """SHA256 hex over canonical bytes; one byte diff flips it."""
    return hashlib.sha256(canonical_serialize(vocab)).hexdigest()


def terms_of(vocab: dict, level: str) -> list:
    """Return a copy of one level term list."""
    if level not in LEVELS:
        raise VocabularyError("unknown level %r" % (level,))
    return list(vocab[level])


def has_exact_term(vocab: dict, term: str) -> bool:
    """Exact match only: True when term equals a stored entry."""
    if not isinstance(term, str) or term == "":
        raise VocabularyError("term must be a non-empty str")
    for level in LEVELS:
        for entry in vocab.get(level, []):
            if entry == term:
                return True
    return False
