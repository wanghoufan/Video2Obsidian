"""Stage7 Prompt + Vocabulary + Language Strategy (S7-T01~T03)."""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage7.vocabulary import (
    VocabularyError,
    canonical_serialize,
    dictionary_snapshot,
    has_exact_term,
    load_vocabulary,
    terms_of,
)
from stage7.prompt_builder import (
    PROMPT_BUDGET_TOKENS,
    PROMPT_BUILDER_VERSION,
    PROMPT_ORDER,
    PromptBuilderError,
    build_for_chunks,
    build_initial_prompt,
    count_tokens,
)
from stage7.language import (
    ENGINE_LANGUAGE,
    LANGUAGE_STRATEGY,
    LanguageError,
    get_engine_language,
    get_language_strategy,
    record_detected_language,
)
from stage7.profile import (
    NEW_FIELDS,
    ProfileError,
    asr_profile_hash,
    build_asr_profile,
    check_layering,
)
from stage7.transcribe import (
    TranscribeError,
    check_wav_mono_16k,
    run_single_file_with_prompt,
)

__all__ = [
    "ENGINE_LANGUAGE",
    "LANGUAGE_STRATEGY",
    "NEW_FIELDS",
    "PROMPT_BUDGET_TOKENS",
    "PROMPT_BUILDER_VERSION",
    "PROMPT_ORDER",
    "LanguageError",
    "ProfileError",
    "PromptBuilderError",
    "TranscribeError",
    "VocabularyError",
    "asr_profile_hash",
    "build_asr_profile",
    "build_for_chunks",
    "build_initial_prompt",
    "canonical_serialize",
    "check_layering",
    "check_wav_mono_16k",
    "count_tokens",
    "dictionary_snapshot",
    "get_engine_language",
    "get_language_strategy",
    "has_exact_term",
    "load_vocabulary",
    "record_detected_language",
    "run_single_file_with_prompt",
    "terms_of",
]
