"""S1-T03: ASR execution on Stage0 frozen config, single file direct pass.

Implements STAGE1-PLAN S1-T03 only::

    temp-wav 16k mono (FFmpeg, on-disk, re-runnable)
    + faster-whisper/CT2 large-v3-turbo single file transcribe
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

Runtime (Windows 端 Stage 3 起)：引擎统一走 ``asr_backend`` 这层薄适配
（faster-whisper / CTranslate2，见
``docs/pm/WINDOWS-MIGRATION-PLAN.md`` §1）。本模块不再直接 import 任何引擎，
模型标识、加载、调用、片段结构全部从那一层取；FFmpeg 进程一律经
``platform_win.run_ffmpeg``（平台单点）。真实 CUDA 调用只可能在 Windows
真机发生，本机（macOS）只用桩验证。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import wave

if os.path.join(os.path.dirname(__file__), "..") not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asr_backend  # noqa: E402  (Windows 端唯一 ASR 后端适配层)
import platform_win  # noqa: E402  (平台适配单点：FFmpeg 进程)

from .ingest import fstat_capture  # noqa: E402
from .verify import (
    EXIT_BLOCK,
    EXIT_FAIL,
    EXIT_PASS,
    gate_transcription,
    load_source_record,
)

# Windows 端（Stage 3）：模型与调用契约全部出自 asr_backend，
# 这里是同一批值的 stage1 侧名字，方便 stage7/8 沿用。
FROZEN_MODEL_REPO = asr_backend.MODEL_ID
# 版本不再写死在本文件：CT2 的 revision 由 models/MODEL_MANIFEST.json 冻结
# （Windows 端不沿用任何 Mac 端那套模型版本标识）。
FROZEN_MODEL_REVISION = asr_backend.MANIFEST_REVISION_TOKEN
FROZEN_AUDIO_MODE = "temp"  # temp-wav 16k mono on disk, re-runnable
FROZEN_WORD_DEFAULT = asr_backend.DEFAULT_WORD_TIMESTAMPS
FROZEN_NO_SPEECH_THRESHOLD = asr_backend.DEFAULT_NO_SPEECH_THRESHOLD
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
    """Resolve the pinned CT2 model revision through the manifest.

    不再翻 Mac 端那套 HF 缓存，也绝不联网：Windows 端只认
    ``models/MODEL_MANIFEST.json`` 冻结的 revision（来源/许可/SHA-256
    一并校验）。校验不过时 ``revision_match`` 为 False，并带上人话
    ``message`` 与 ``code``，由调用方 BLOCK。
    """
    try:
        check = asr_backend.manifest.verify_model(repo, environ=None)
    except asr_backend.manifest.ManifestBlock as exc:
        check = {
            "ok": False, "code": exc.code, "message": exc.message,
            "revision": None, "verdict": "BLOCK", "detail": exc.detail,
        }
    return {
        "repo": repo,
        "revision_resolved": check.get("revision"),
        "revision_expected": check.get("revision") or FROZEN_MODEL_REVISION,
        "revision_match": bool(check.get("ok")),
        "verdict": check.get("verdict", "BLOCK"),
        "code": check.get("code"),
        "message": check.get("message", ""),
        "backend": asr_backend.BACKEND_ID,
        "library": asr_backend.LIBRARY_ID,
        "detail": check.get("detail", {}),
    }


def extract_temp_wav(source_path: str, wav_path: str) -> dict:
    """Decode source audio to 16k mono wav file on disk (re-runnable).

    File-to-file FFmpeg only: the model input is always a wav path, so a
    failed transcribe can be retried from this file without re-decoding.
    """
    os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)
    # 进程调用一律走平台单点（Windows：随包 ffmpeg.exe 绝对路径 + 参数数组）。
    args = [
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
    proc = platform_win.run_ffmpeg(args, timeout=3600)
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
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # 引擎调用只有这一条路（asr_backend），本模块不直接接触任何引擎库。
    result = asr_backend.transcribe_file(
        wav_path,
        initial_prompt=None,
        language=None,
        word_timestamps=word_timestamps,
        no_speech_threshold=no_speech_threshold,
        decode=DECODE_DEFAULTS,
    )
    text = result["text"]
    segments = result["segments"]
    if not result["monotonic"]:
        raise AsrFail("engine segments broke the monotonic timeline contract")
    return {
        "text": text,
        "segments": segments,
        "transcribe_s": result["transcribe_s"],
        "asr_calls": result["asr_calls"],
        "engine": asr_backend.BACKEND_ID,
        "library": asr_backend.LIBRARY_ID,
        "config": result["config"],
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
