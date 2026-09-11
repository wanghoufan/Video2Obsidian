"""S7-T03 language strategy: explicit zh, advisory record only."""

from __future__ import annotations

LANGUAGE_STRATEGY = "explicit-zh"
ENGINE_LANGUAGE = "zh"


class LanguageError(ValueError):
    """Raised when language input is malformed."""


def get_language_strategy() -> str:
    """Frozen strategy value."""
    return LANGUAGE_STRATEGY


def get_engine_language() -> str:
    """Language tag passed to the engine."""
    return ENGINE_LANGUAGE


def record_detected_language(detected: str | None) -> dict:
    """Record engine reported language as advisory; never blocks.

    Returns a record with mismatch flag and blocked=False always.
    """
    if detected is not None and not isinstance(detected, str):
        raise LanguageError("detected must be str or None")
    tag = (detected or "").strip().lower()
    mismatch = bool(tag) and tag not in ("zh", "chinese", "cmn")
    return {
        "strategy": LANGUAGE_STRATEGY,
        "engine_language": ENGINE_LANGUAGE,
        "detected": detected,
        "mismatch": bool(mismatch),
        "blocked": False,
        "action": "record-only",
    }
