"""S7-T03 single-file engine wiring with real initial_prompt."""

from __future__ import annotations

import os
import sys
import time
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asr_backend  # noqa: E402  (Windows 端唯一 ASR 后端适配层)

from stage1.asr import (  # noqa: E402 (read-only reuse, Stage7 addition only)
    DECODE_DEFAULTS,
    FROZEN_MODEL_REPO,
    FROZEN_MODEL_REVISION,
    FROZEN_NO_SPEECH_THRESHOLD,
    FROZEN_PROMPT_BUDGET_TOKENS,
    FROZEN_WORD_DEFAULT,
    resolve_model_revision,
    vad_observe_only,
)
from stage7.language import (  # noqa: E402
    ENGINE_LANGUAGE,
    LANGUAGE_STRATEGY,
    record_detected_language,
)
from stage7.prompt_builder import count_tokens  # noqa: E402


class TranscribeError(RuntimeError):
    """Raised when wiring input or engine run is invalid."""


def check_wav_mono_16k(wav_path: str) -> dict:
    """Read header of a wav file; require 1 channel 16k."""
    if not isinstance(wav_path, str) or not os.path.isfile(wav_path):
        raise TranscribeError("wav not readable: %r" % (wav_path,))
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.getnframes()
    if (channels, rate) != (1, 16000):
        raise TranscribeError(
            "wav shape drift: want 1ch/16k, got %dch/%dHz" % (channels, rate)
        )
    return {
        "wav_path": os.path.abspath(wav_path),
        "channels": channels,
        "rate": rate,
        "duration_s": round(frames / float(rate), 2) if rate else 0.0,
        "bytes": os.path.getsize(wav_path),
    }


def run_single_file_with_prompt(wav_path: str, initial_prompt: str) -> dict:
    """Run one file with one engine call using the given prompt.

    Shape mirrors stage1 frozen call (model, revision, temp-wav
    16k mono, word OFF, nst 0.6, single call, clip 0) plus explicit
    language zh and the assembled initial_prompt. This module never
    imports the stage1 single-file body (its prompt is None by design);
    it copies the call shape with new prompt semantics. VAD stays
    advisory only and never trims audio.
    """
    if not isinstance(initial_prompt, str) or initial_prompt.strip() == "":
        raise TranscribeError("initial_prompt must be a non-empty str")
    tokens = count_tokens(initial_prompt)
    if tokens <= 0 or tokens > FROZEN_PROMPT_BUDGET_TOKENS:
        raise TranscribeError("initial_prompt tokens out of range: %r" % (tokens,))

    wav_info = check_wav_mono_16k(wav_path)

    model_info = resolve_model_revision()
    if not model_info.get("revision_match"):
        raise TranscribeError(
            "model revision drift: resolved %r != frozen %r"
            % (model_info.get("revision_resolved"), FROZEN_MODEL_REVISION)
        )

    # 引擎调用只有这一条路（asr_backend，Windows 端不再 import 任何 Mac 端引擎；
    # 离线门禁 / GPU 档位 / manifest 校验全部在 asr_backend 内 fail-closed）。
    t0 = time.time()
    result = asr_backend.transcribe_file(
        wav_info["wav_path"],
        initial_prompt=initial_prompt,
        language=ENGINE_LANGUAGE,
        word_timestamps=FROZEN_WORD_DEFAULT,
        no_speech_threshold=FROZEN_NO_SPEECH_THRESHOLD,
        decode=DECODE_DEFAULTS,
    )
    call_s = round(time.time() - t0, 1)
    if not result.get("monotonic"):
        raise TranscribeError(
            "engine segments broke the monotonic timeline contract"
        )

    vad = vad_observe_only(wav_info["wav_path"])
    detected = (result.get("info") or {}).get("language")
    lang_record = record_detected_language(detected)

    text = result.get("text", "")
    segments = result.get("segments", [])
    return {
        "wav": wav_info,
        "text": text,
        "segments": segments,
        "detected_language": detected,
        "language_record": lang_record,
        "language_strategy": LANGUAGE_STRATEGY,
        "language": ENGINE_LANGUAGE,
        "initial_prompt": initial_prompt,
        "prompt_chars": len(initial_prompt),
        "token_count": tokens,
        "model": FROZEN_MODEL_REPO,
        "model_revision": model_info.get("revision_resolved")
        or FROZEN_MODEL_REVISION,
        "word_timestamps": FROZEN_WORD_DEFAULT,
        "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
        "clip": "0",
        "decode": {
            "word_timestamps": FROZEN_WORD_DEFAULT,
            "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
            "initial_prompt": initial_prompt,
            "prompt_chars": len(initial_prompt),
            "clip": "0",
            **DECODE_DEFAULTS,
        },
        "prompt_executed": True,
        "vad": vad,
        "asr_calls": 1,
        "engine_calls": 1,
        "call_s": call_s,
    }
