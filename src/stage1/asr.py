"""S1-T03: ASR execution on Stage0 frozen config, single file direct pass.

Implements STAGE1-PLAN S1-T03 only::

    temp-wav 16k mono (FFmpeg, on-disk, re-runnable)
    + mlx-whisper large-v3-turbo @ a4aaeec0 single file transcribe
    + word_timestamps default OFF + no_speech_threshold 0.6
    + VAD observe-only record (never filters audio)
    + ASR Profile actual-value record + fstat before/after for T04.

Entry point :func:`run_asr_single_file` is designed to be called through
``verify.gate_transcription`` so a BLOCK verdict never reaches FFmpeg or
the model (``asr_calls == 0`` on BLOCK). The source video is only ever
read (os.stat + FFmpeg read-only input); all products land under the
given job dir inside the H2 test root.

Frozen values (TECHNICAL_BENCHMARK_REPORT §9) are hard constants below.
Any deviation without a declaration FAILs (exit 1): model revision,
audio mode, word default. By construction this module has no file
splitting path, no prompt assembly, no parallel workers, and no
audio filtering driven by VAD — those live in later Stages.

Runtime: Stage0 venv only (mlx-whisper / silero-vad / numpy / FFmpeg
binary). No new dependency. Heavy imports stay inside functions so a
plain ``import src.stage1.asr`` never requires the venv.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

from .ingest import fstat_capture
from .verify import (
    EXIT_BLOCK,
    EXIT_FAIL,
    EXIT_PASS,
    gate_transcription,
    load_source_record,
)

# Stage0 frozen config (§9). Single source of truth for this Task.
FROZEN_MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
FROZEN_MODEL_REVISION = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"
FROZEN_AUDIO_MODE = "temp"  # temp-wav 16k mono on disk, re-runnable
FROZEN_WORD_DEFAULT = False
FROZEN_NO_SPEECH_THRESHOLD = 0.6
FROZEN_VAD_THRESHOLDS = (0.3, 0.5)
FROZEN_CHUNK_SIZE = "10min"  # recorded only, not executed here
FROZEN_CHUNK_OVERLAP = "2s"  # recorded only, not executed here
FROZEN_PROMPT_BUDGET_TOKENS = 200  # recorded only, not executed here
FROZEN_WORKER = 1  # serial single call

# Library decode defaults we rely on without overriding (recorded as-is).
DECODE_DEFAULTS = {
    "condition_on_previous_text": True,
    "compression_ratio_threshold": 2.4,
    "logprob_threshold": -1.0,
    "temperature_schedule": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
}


class AsrFail(RuntimeError):
    """Raised on FAIL (declared deviation missing or execution error)."""


def _write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def resolve_model_revision(
    repo: str = FROZEN_MODEL_REPO,
) -> dict:
    """Resolve the locally cached model revision for *repo*.

    Reads the HF hub cache (refs/main + snapshots dir). Never downloads:
    mismatch against the frozen value FAILs closed.
    """
    cache_root = os.environ.get(
        "HF_HUB_CACHE",
        os.path.expanduser("~/.cache/huggingface/hub"),
    )
    slug = "models--" + repo.replace("/", "--")
    refs_main = os.path.join(cache_root, slug, "refs", "main")
    snaps = os.path.join(cache_root, slug, "snapshots")
    revision = None
    if os.path.isfile(refs_main):
        with open(refs_main, "r", encoding="utf-8") as fh:
            revision = fh.read().strip()
    snap_dirs: list[str] = []
    if os.path.isdir(snaps):
        snap_dirs = sorted(os.listdir(snaps))
    return {
        "repo": repo,
        "revision_resolved": revision,
        "revision_expected": FROZEN_MODEL_REVISION,
        "revision_match": revision == FROZEN_MODEL_REVISION,
        "snapshot_dirs": snap_dirs,
        "cache_root": cache_root,
    }


def extract_temp_wav(source_path: str, wav_path: str) -> dict:
    """Decode source audio to 16k mono wav file on disk (re-runnable).

    File-to-file FFmpeg only: the model input is always a wav path, so a
    failed transcribe can be retried from this file without re-decoding.
    """
    os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        source_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        wav_path,
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    prep_s = time.time() - t0
    if proc.returncode != 0:
        raise AsrFail(f"ffmpeg temp-wav extract failed: {proc.stderr[-1000:]}")
    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        raise AsrFail("ffmpeg temp-wav extract produced no output file")
    with wave.open(wav_path, "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.getnframes()
    if (channels, rate) != (1, 16000):
        raise AsrFail(
            f"temp-wav format drift: want 1ch/16k, got {channels}ch/{rate}Hz"
        )
    return {
        "wav_path": os.path.abspath(wav_path),
        "audio_mode": "temp",
        "audio_note": "16k-mono-wav-file",
        "audio_duration_s": round(frames / float(rate), 2),
        "wav_bytes": os.path.getsize(wav_path),
        "prep_s": round(prep_s, 1),
    }


def transcribe_wav_file(
    wav_path: str,
    model_repo: str = FROZEN_MODEL_REPO,
    word_timestamps: bool = FROZEN_WORD_DEFAULT,
    no_speech_threshold: float = FROZEN_NO_SPEECH_THRESHOLD,
) -> dict:
    """Single file direct transcribe of one wav path (exactly one call)."""
    if word_timestamps != FROZEN_WORD_DEFAULT:
        declared = os.environ.get("S1_T03_WORD_ON_DECLARED") == "1"
        if not declared:
            raise AsrFail(
                "word_timestamps deviates from frozen default OFF "
                "without declaration (set S1_T03_WORD_ON_DECLARED=1 "
                "to declare on-demand ON)"
            )
    if no_speech_threshold != FROZEN_NO_SPEECH_THRESHOLD:
        raise AsrFail(
            "no_speech_threshold deviates from frozen 0.6 without declaration"
        )
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import mlx_whisper  # noqa: PLC0415  (venv-only, lazy)

    t0 = time.time()
    result = mlx_whisper.transcribe(
        wav_path,
        path_or_hf_repo=model_repo,
        word_timestamps=word_timestamps,
        initial_prompt=None,
        clip_timestamps="0",
        no_speech_threshold=no_speech_threshold,
        verbose=False,
    )
    transcribe_s = time.time() - t0
    text = result.get("text", "")
    segments = result.get("segments", [])
    return {
        "text": text,
        "segments": segments,
        "transcribe_s": round(transcribe_s, 1),
        "asr_calls": 1,
        "decode": {
            "word_timestamps": word_timestamps,
            "no_speech_threshold": no_speech_threshold,
            "initial_prompt": None,
            "prompt_chars": 0,
            "clip": "0",
            **DECODE_DEFAULTS,
        },
    }


def vad_observe_only(wav_path: str) -> dict:
    """VAD advisory record on the temp-wav file.

    Observe-only: reads the same wav file, records speech ratios at the
    frozen thresholds, and returns. The returned timestamps are never
    fed back into audio selection — transcription always sees the full
    file (see :func:`transcribe_wav_file` taking the wav path).
    """
    try:
        import numpy as np  # noqa: PLC0415  (venv-only, lazy)
        from silero_vad import (  # noqa: PLC0415  (venv-only, lazy)
            get_speech_timestamps,
            load_silero_vad,
        )
    except Exception as exc:  # advisory: import failure must not BLOCK ASR
        return {
            "mode": "advisory-only",
            "status": "SKIPPED",
            "reason": f"vad stack unavailable: {type(exc).__name__}: {exc}",
            "filtering_applied": False,
        }
    try:
        with wave.open(wav_path, "rb") as wf:
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        dur_s = len(audio) / float(rate)
        model = load_silero_vad()
        cands: dict[str, dict] = {}
        for thr in FROZEN_VAD_THRESHOLDS:
            spans = get_speech_timestamps(
                audio, model, threshold=thr, return_seconds=True
            )
            speech = sum(s["end"] - s["start"] for s in spans)
            cands[str(thr)] = {
                "n_segments": len(spans),
                "speech_s": round(speech, 1),
                "speech_ratio": round(speech / dur_s, 4) if dur_s else None,
            }
        return {
            "mode": "advisory-only",
            "status": "OK",
            "audio_s": round(dur_s, 1),
            "candidates": cands,
            "filtering_applied": False,
        }
    except Exception as exc:  # advisory: runtime failure must not BLOCK ASR
        return {
            "mode": "advisory-only",
            "status": "SKIPPED",
            "reason": f"vad observe failed: {type(exc).__name__}: {exc}",
            "filtering_applied": False,
        }


def run_asr_single_file(
    source_record: dict,
    job_dir: str,
    source_path: str | None = None,
    word_timestamps: bool = FROZEN_WORD_DEFAULT,
) -> dict:
    """Run the frozen single-file ASR for one job.

    Serial flow (worker=1): fstat-before → revision check → temp-wav →
    one transcribe call → VAD observe → fstat-after → profile JSON.
    Returns the artefact summary; raises :class:`AsrFail` on FAIL.
    Products: ``<job_dir>/asr/{asr_16k.wav,transcript.txt,
    segments.json,asr_profile.json}``. Never touches T05/T06 ``raw/``.
    """
    path = source_path or source_record.get("current_path")
    if not path or not os.path.isfile(path):
        raise AsrFail(f"source video not readable: {path!r}")
    asr_dir = os.path.join(os.path.abspath(job_dir), "asr")
    os.makedirs(asr_dir, exist_ok=True)

    fstat_before = fstat_capture(path)

    model_info = resolve_model_revision()
    if not model_info["revision_match"]:
        raise AsrFail(
            "model revision drift without declaration: resolved "
            f"{model_info['revision_resolved']!r} != frozen "
            f"{FROZEN_MODEL_REVISION!r}"
        )

    wav_path = os.path.join(asr_dir, "asr_16k.wav")
    audio = extract_temp_wav(path, wav_path)

    tres = transcribe_wav_file(
        audio["wav_path"],
        word_timestamps=word_timestamps,
    )

    vad = vad_observe_only(audio["wav_path"])

    fstat_after = fstat_capture(path)

    text: str = tres["text"]
    segments: list = tres["segments"]
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rtf = (
        round(tres["transcribe_s"] / audio["audio_duration_s"], 4)
        if audio["audio_duration_s"]
        else None
    )

    transcript_path = os.path.join(asr_dir, "transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    segments_path = os.path.join(asr_dir, "segments.json")
    _write_json(segments_path, {"segments": segments})

    profile = {
        "stage": "Stage1-S1-T03",
        "job_id": os.path.basename(os.path.abspath(job_dir)),
        "job_dir": os.path.abspath(job_dir),
        "source_id": source_record.get("source_id"),
        "source_path": os.path.abspath(path),
        "content_identity": source_record.get("content_identity"),
        "frozen": {
            "model": FROZEN_MODEL_REPO,
            "model_revision": FROZEN_MODEL_REVISION,
            "audio": "temp-wav 16k mono (FFmpeg on-disk, re-runnable)",
            "word_timestamps_default": FROZEN_WORD_DEFAULT,
            "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
            "vad_profile": f"silero thr {list(FROZEN_VAD_THRESHOLDS)}, advisory only",
            "chunk_size_recorded": FROZEN_CHUNK_SIZE,
            "chunk_overlap_recorded": FROZEN_CHUNK_OVERLAP,
            "prompt_budget_tokens_recorded": FROZEN_PROMPT_BUDGET_TOKENS,
            "prompt_order_recorded": "Global->Topic->Creator",
            "worker": FROZEN_WORKER,
        },
        "actual": {
            "model": FROZEN_MODEL_REPO,
            "model_revision": model_info["revision_resolved"],
            "revision_match": True,
            "audio_mode": audio["audio_mode"],
            "audio_note": audio["audio_note"],
            "word_timestamps": tres["decode"]["word_timestamps"],
            "no_speech_threshold": tres["decode"]["no_speech_threshold"],
            "initial_prompt": None,
            "prompt_chars": 0,
            "clip": "0",
            "decode": tres["decode"],
            "worker": 1,
            "serial_single_call": True,
            "vad": vad,
            "chunk": {
                "size": FROZEN_CHUNK_SIZE,
                "overlap": FROZEN_CHUNK_OVERLAP,
                "executed": False,
                "recorded_only": True,
            },
            "prompt": {
                "budget_tokens": FROZEN_PROMPT_BUDGET_TOKENS,
                "order": "Global->Topic->Creator",
                "executed": False,
                "recorded_only": True,
            },
        },
        "artifacts": {
            "temp_wav": audio["wav_path"],
            "transcript": os.path.abspath(transcript_path),
            "segments_json": os.path.abspath(segments_path),
        },
        "timing": {
            "audio_duration_s": audio["audio_duration_s"],
            "prep_s": audio["prep_s"],
            "transcribe_s": tres["transcribe_s"],
            "rtf": rtf,
        },
        "text_stats": {
            "chars": len(text),
            "segments": len(segments),
            "words": None,
            "text_sha256": text_sha,
        },
        "fstat": {
            "before": fstat_before,
            "after": fstat_after,
        },
        "asr_calls": tres["asr_calls"],
        "deviations": [],
    }
    profile_path = os.path.join(asr_dir, "asr_profile.json")
    _write_json(profile_path, profile)
    return {
        **profile,
        "profile_path": os.path.abspath(profile_path),
    }


def run_job(source_json_path: str, job_dir: str) -> dict:
    """Load the Source record and run ASR behind the T02 gate."""
    record = load_source_record(source_json_path)

    def _asr(path: str) -> dict:
        return run_asr_single_file(record, job_dir, source_path=path)

    return gate_transcription(record, None, _asr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="S1-T03 frozen single-file ASR (Stage0 §9)"
    )
    parser.add_argument("--source-json", required=True, help="path to source.json")
    parser.add_argument("--job-dir", required=True, help="job dir (H2 test root)")
    args = parser.parse_args(argv)
    try:
        gated = run_job(args.source_json, args.job_dir)
    except (AsrFail, OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    asr_result = gated.get("asr_result") or {}
    print(
        json.dumps(
            {
                "verdict": gated.get("verdict"),
                "code": gated.get("code"),
                "asr_calls": gated.get("asr_calls"),
                "profile_path": asr_result.get("profile_path"),
                "text_stats": asr_result.get("text_stats"),
                "timing": asr_result.get("timing"),
                "temp_wav": (asr_result.get("artifacts") or {}).get("temp_wav"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if gated.get("verdict") != "PASS":
        return EXIT_BLOCK
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
