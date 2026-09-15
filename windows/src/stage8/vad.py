"""S8-T01 VAD advisory observation (silero thr 0.3-0.5, record only).

Observation reads the wav file and records speech spans per frozen
档位. Audio bytes are never trimmed and chunk boundaries never follow
VAD output (the only split source is chunk_planner).
"""

from __future__ import annotations

import hashlib
import os
import wave

VAD_ENGINE = "silero"
VAD_MODE = "advisory-only"
VAD_THRESHOLDS = (0.3, 0.5)


class VadError(ValueError):
    """Raised on illegal threshold, unreadable wav, or refused trimming."""


def is_advisory_only() -> bool:
    """Machine-checkable hard gate: Stage8 VAD stays advisory only."""
    return True


def vad_profile() -> dict:
    """Frozen VAD档位 record for the ASR profile layer."""
    return {
        "engine": VAD_ENGINE,
        "mode": VAD_MODE,
        "thresholds": list(VAD_THRESHOLDS),
        "filtering": False,
        "drives_chunking": False,
        "drives_audio_choice": False,
    }


def _wav_info(wav_path: str) -> dict:
    if not isinstance(wav_path, str) or not os.path.isfile(wav_path):
        raise VadError("wav not readable: %r" % (wav_path,))
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.getnframes()
    if (channels, rate) != (1, 16000):
        raise VadError(
            "wav shape drift: want 1ch/16k, got %dch/%dHz" % (channels, rate)
        )
    return {
        "channels": channels,
        "rate": rate,
        "frames": frames,
        "duration_s": round(frames / float(rate), 3) if rate else 0.0,
    }


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _skipped(threshold: float, sha_before: str, exc: Exception) -> dict:
    return {
        "mode": VAD_MODE,
        "status": "SKIPPED",
        "reason": "%s: %s" % (type(exc).__name__, exc),
        "threshold": threshold,
        "wav_sha256": sha_before,
        "audio_bytes_equal": True,
        "filtering_applied": False,
    }


def observe_vad(wav_path: str, threshold: float, filtering=False) -> dict:
    """Observe speech spans at one frozen档位; audio stays untouched.

    ``filtering`` is the hard gate: anything but False is refused with
    VadError (fail-closed). ``threshold`` must be 0.3 or 0.5; anything
    else is refused without tuning.
    """
    if filtering:
        raise VadError("advisory path refuses trimming (filtering stays False)")
    if threshold not in VAD_THRESHOLDS:
        raise VadError(
            "threshold frozen to %r, got %r" % (list(VAD_THRESHOLDS), threshold)
        )
    info = _wav_info(wav_path)
    sha_before = _sha256_file(wav_path)
    try:
        import numpy as np  # noqa: PLC0415 (venv-only, lazy)

        from silero_vad import (  # noqa: PLC0415 (venv-only, lazy)
            get_speech_timestamps,
            load_silero_vad,
        )
    except Exception as exc:
        return _skipped(threshold, sha_before, exc)
    try:
        with wave.open(wav_path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        model = load_silero_vad()
        spans = get_speech_timestamps(
            audio, model, threshold=threshold, return_seconds=True
        )
        norm = [
            {"start": round(float(s["start"]), 3), "end": round(float(s["end"]), 3)}
            for s in spans
        ]
        speech = sum(s["end"] - s["start"] for s in norm)
        dur = info["duration_s"]
        record = {
            "mode": VAD_MODE,
            "status": "OK",
            "threshold": threshold,
            "audio_s": dur,
            "spans": norm,
            "n_spans": len(norm),
            "speech_s": round(speech, 3),
            "speech_ratio": round(speech / dur, 4) if dur else None,
            "wav_sha256": sha_before,
            "audio_bytes_equal": sha_before == _sha256_file(wav_path),
            "filtering_applied": False,
        }
        return record
    except Exception as exc:
        return _skipped(threshold, sha_before, exc)


def observe_vad_all(wav_path: str) -> dict:
    """Observe both frozen档位; returns {str(threshold): record}."""
    return {str(thr): observe_vad(wav_path, thr) for thr in VAD_THRESHOLDS}
