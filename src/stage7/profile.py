"""S7-T03 ASR profile extension, ASR layer only."""

from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage1.asr import (  # noqa: E402 (read-only reuse, Stage7 addition only)
    DECODE_DEFAULTS,
    FROZEN_MODEL_REPO,
    FROZEN_MODEL_REVISION,
    FROZEN_NO_SPEECH_THRESHOLD,
    FROZEN_PROMPT_BUDGET_TOKENS,
    FROZEN_WORD_DEFAULT,
)

from stage7.language import ENGINE_LANGUAGE, LANGUAGE_STRATEGY  # noqa: E402

ASR_LAYER = "asr"
PROMPT_ORDER = "Global->Topic->Creator"

NEW_FIELDS = (
    "language_strategy",
    "language",
    "dictionary_snapshot",
    "prompt_builder_version",
    "prompt_profile",
)


class ProfileError(ValueError):
    """Raised when profile input is missing or malformed."""


def build_asr_profile(
    dictionary_snapshot: str,
    prompt_builder_version: str,
    initial_prompt: str,
    token_count: int,
) -> dict:
    """Assemble the ASR layer profile dict.

    New Stage7 fields land only in this ASR dict, never in the
    Stage3 correction / render dicts. Prompt is marked executed.
    """
    if not isinstance(dictionary_snapshot, str) or not dictionary_snapshot:
        raise ProfileError("dictionary_snapshot must be a non-empty str")
    if not isinstance(prompt_builder_version, str) or not prompt_builder_version:
        raise ProfileError("prompt_builder_version must be a non-empty str")
    if not isinstance(initial_prompt, str) or initial_prompt.strip() == "":
        raise ProfileError("initial_prompt must be a non-empty str")
    if not isinstance(token_count, int) or token_count <= 0:
        raise ProfileError("token_count must be a positive int")
    if token_count > FROZEN_PROMPT_BUDGET_TOKENS:
        raise ProfileError("token_count over budget 200")
    prompt_chars = len(initial_prompt)
    if prompt_chars <= 0:
        raise ProfileError("prompt_chars must be positive")
    return {
        "layer": ASR_LAYER,
        "model": FROZEN_MODEL_REPO,
        "model_revision": FROZEN_MODEL_REVISION,
        "language_strategy": LANGUAGE_STRATEGY,
        "language": ENGINE_LANGUAGE,
        "dictionary_snapshot": dictionary_snapshot,
        "prompt_builder_version": prompt_builder_version,
        "prompt_profile": {
            "budget_tokens": FROZEN_PROMPT_BUDGET_TOKENS,
            "order": PROMPT_ORDER,
        },
        "prompt": {
            "budget_tokens": FROZEN_PROMPT_BUDGET_TOKENS,
            "order": PROMPT_ORDER,
            "executed": True,
            "recorded_only": False,
            "initial_prompt": initial_prompt,
            "prompt_chars": prompt_chars,
            "token_count": token_count,
        },
        "decode": {
            "word_timestamps": FROZEN_WORD_DEFAULT,
            "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
            **DECODE_DEFAULTS,
        },
    }


def asr_profile_hash(profile: dict) -> str:
    """Identity digest over canonical ASR fields.

    Same input gives same digest; any new field change flips it.
    """
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a dict")
    for field in NEW_FIELDS:
        if field not in profile:
            raise ProfileError("asr profile missing %r" % (field,))
    if profile.get("layer") != ASR_LAYER:
        raise ProfileError("profile layer must be asr")
    subset = {
        "model": profile.get("model"),
        "model_revision": profile.get("model_revision"),
        "language_strategy": profile.get("language_strategy"),
        "language": profile.get("language"),
        "dictionary_snapshot": profile.get("dictionary_snapshot"),
        "prompt_builder_version": profile.get("prompt_builder_version"),
        "prompt_profile": profile.get("prompt_profile"),
        "prompt_chars": (profile.get("prompt") or {}).get("prompt_chars"),
        "token_count": (profile.get("prompt") or {}).get("token_count"),
    }
    try:
        canonical = json.dumps(
            subset, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProfileError("profile not serializable: %s" % (exc,))
    return hashlib.sha256(canonical).hexdigest()


def check_layering(asr_profile: dict, correction_profile: dict, render_profile: dict) -> dict:
    """Assert new Stage7 fields sit only in the ASR layer.

    Returns a pass record; raises when a new field leaks into the
    correction or render dicts.
    """
    for field in NEW_FIELDS:
        if field not in asr_profile:
            raise ProfileError("asr profile missing %r" % (field,))
    leaked = []
    for name, other in (
        ("correction", correction_profile),
        ("render", render_profile),
    ):
        if not isinstance(other, dict):
            raise ProfileError("%s profile must be a dict" % (name,))
        for field in NEW_FIELDS:
            if field in other:
                leaked.append("%s.%s" % (name, field))
    if leaked:
        raise ProfileError("new field in wrong layer: %s" % (", ".join(leaked),))
    return {"layering": "asr-only", "checked": list(NEW_FIELDS), "leaked": []}
