"""S8-T04 per-chunk engine wiring: one call per chunk, prompt rebuilt.

Frozen alignment: model/revision/temp-wav 16k mono/word OFF default/
nst 0.6/serial worker from stage1; prompt per chunk rebuilt through
stage7 (never shared across chunks); language explicit-zh; VAD stays
advisory only. Stop expansion: no canonical write, no store contact.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asr_backend  # noqa: E402  (Windows 端唯一 ASR 后端适配层)
import platform_win  # noqa: E402  (平台适配单点：FFmpeg 进程一律经此)

from stage1.asr import (  # noqa: E402 (read-only reuse, Stage8 addition only)
    DECODE_DEFAULTS,
    FROZEN_MODEL_REPO,
    FROZEN_MODEL_REVISION,
    FROZEN_NO_SPEECH_THRESHOLD,
    FROZEN_WORD_DEFAULT,
    resolve_model_revision,
)
from stage7.language import (  # noqa: E402 (read-only reuse)
    ENGINE_LANGUAGE,
    LANGUAGE_STRATEGY,
)
from stage7.prompt_builder import build_for_chunks  # noqa: E402 (read-only reuse)
from stage7.transcribe import (  # noqa: E402 (read-only reuse)
    check_wav_mono_16k,
)
from stage8.chunk_planner import (  # noqa: E402
    CHUNK_OVERLAP_S,
    CHUNK_SIZE_S,
    chunking_profile,
    plan_chunks,
)
from stage8.merge import PRIORITY as MERGE_PRIORITY  # noqa: E402
from stage8.merge import merge_chunks  # noqa: E402
from stage8.timeline import check_monotonic, to_absolute  # noqa: E402
from stage8.vad import (  # noqa: E402
    VAD_THRESHOLDS,
    is_advisory_only,
    observe_vad_all,
    vad_profile,
)

WORKER = 1
AUDIO_NOTE = "temp-wav 16k mono (FFmpeg on-disk)"


class ChunkTranscribeError(RuntimeError):
    """Raised on wiring input errors or engine run errors."""


def frozen_alignment() -> dict:
    """Stage1/Stage7 frozen values this wiring aligns with, field by field."""
    return {
        "model": FROZEN_MODEL_REPO,
        "model_revision": FROZEN_MODEL_REVISION,
        "audio": AUDIO_NOTE,
        "word_default": FROZEN_WORD_DEFAULT,
        "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
        "language_strategy": LANGUAGE_STRATEGY,
        "language": ENGINE_LANGUAGE,
        "vad_mode": "advisory-only",
        "vad_thresholds": list(VAD_THRESHOLDS),
        "chunk_size_s": CHUNK_SIZE_S,
        "chunk_overlap_s": CHUNK_OVERLAP_S,
        "worker": WORKER,
        "decode_defaults": dict(DECODE_DEFAULTS),
    }


def _wav_duration(wav_path: str) -> float:
    info = check_wav_mono_16k(wav_path)
    return float(info["duration_s"])


def _check_chunks(chunks) -> list:
    if not isinstance(chunks, list) or not chunks:
        raise ChunkTranscribeError("chunks must be a non-empty list")
    for pos, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ChunkTranscribeError("chunk %d must be a dict" % (pos,))
        if chunk.get("index") != pos:
            raise ChunkTranscribeError("chunk index order broken at %d" % (pos,))
        for key in ("start_s", "end_s", "core_start_s", "core_end_s"):
            value = chunk.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ChunkTranscribeError("chunk %d %r must be a number" % (pos, key))
        if chunk["end_s"] <= chunk["start_s"]:
            raise ChunkTranscribeError("chunk %d empty span refused" % (pos,))
        if chunk["start_s"] < 0:
            raise ChunkTranscribeError("chunk %d negative start refused" % (pos,))
        if chunk["core_start_s"] < chunk["start_s"] - 1e-9:
            raise ChunkTranscribeError("chunk %d core below start refused" % (pos,))
        if chunk["core_end_s"] > chunk["end_s"] + 1e-9:
            raise ChunkTranscribeError("chunk %d core above end refused" % (pos,))
    return chunks


def _cut_chunk_wav(source_wav: str, chunk: dict, out_path: str) -> dict:
    # FFmpeg 进程一律走平台单点（随包 ffmpeg.exe / V2O_FFMPEG / PATH 兜底
    # 全部在 platform_win.ffmpeg_resolve 收口），超时与错误语义不变。
    args = [
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        source_wav,
        "-ss",
        str(chunk["start_s"]),
        "-to",
        str(chunk["end_s"]),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        out_path,
    ]
    proc = platform_win.run_ffmpeg(args, timeout=600)
    if proc.returncode != 0:
        raise ChunkTranscribeError(
            "ffmpeg chunk cut failed for chunk %r: %s"
            % (chunk.get("index"), proc.stderr[-500:])
        )
    info = check_wav_mono_16k(out_path)
    return {"wav_path": os.path.abspath(out_path), "bytes": info["bytes"]}


def _call_engine_once(
    wav_path: str,
    initial_prompt: str,
    word_timestamps: bool,
    no_speech_threshold: float,
    model=None,
    model_info: dict | None = None,
    config: dict | None = None,
) -> dict:
    """Single real engine call; mirrors the stage1 call shape plus prompt.

    Windows 端 Stage 3：引擎统一走 asr_backend.transcribe_file（离线门禁、
    GPU 档位、manifest 校验、片段归一化全部在那层 fail-closed），本模块
    不再直接 import 任何引擎库。``model_info``（manifest 校验结果）与
    ``config``（运行档位）是 run 级解析一次的产物（run_chunks 加载模型时
    留存），为空时现场解析兜底，保证 chunk 循环内不重算。
    """
    if no_speech_threshold != FROZEN_NO_SPEECH_THRESHOLD:
        raise ChunkTranscribeError("no_speech_threshold drift refused")
    info = model_info if model_info is not None else resolve_model_revision()
    if not info.get("revision_match"):
        raise ChunkTranscribeError(
            "model revision drift: resolved %r != frozen %r"
            % (info.get("revision_resolved"), FROZEN_MODEL_REVISION)
        )
    result = asr_backend.transcribe_file(
        wav_path,
        model=model,
        initial_prompt=initial_prompt,
        language=ENGINE_LANGUAGE,
        word_timestamps=word_timestamps,
        no_speech_threshold=no_speech_threshold,
        decode=DECODE_DEFAULTS,
        config=config,
    )
    if not result.get("monotonic"):
        raise ChunkTranscribeError(
            "engine segments broke the monotonic timeline contract"
        )
    return {
        "text": result.get("text", ""),
        "segments": result.get("segments", []),
        "detected": (result.get("info") or {}).get("language"),
    }


def build_chunk_asr_profile(
    dictionary_snapshot: str,
    prompt_builder_version: str,
    per_chunk_prompts: list,
    vad_prof: dict | None = None,
    chunking_prof: dict | None = None,
    word_timestamps: bool = FROZEN_WORD_DEFAULT,
) -> dict:
    """Assemble the ASR layer profile for chunked runs.

    vad/chunking entries land only in this ASR dict, never in
    normalization/render dicts (this module never builds those).
    """
    if not isinstance(dictionary_snapshot, str) or not dictionary_snapshot:
        raise ChunkTranscribeError("dictionary_snapshot must be a non-empty str")
    if not isinstance(prompt_builder_version, str) or not prompt_builder_version:
        raise ChunkTranscribeError("prompt_builder_version must be a non-empty str")
    if not isinstance(per_chunk_prompts, list) or not per_chunk_prompts:
        raise ChunkTranscribeError("per_chunk_prompts must be a non-empty list")
    chunks = []
    for pos, item in enumerate(per_chunk_prompts):
        if not isinstance(item, dict):
            raise ChunkTranscribeError("prompt %d must be a dict" % (pos,))
        prompt = item.get("initial_prompt")
        tokens = item.get("token_count")
        if not isinstance(prompt, str) or prompt.strip() == "":
            raise ChunkTranscribeError("prompt %d initial_prompt bad" % (pos,))
        if not isinstance(tokens, int) or tokens <= 0:
            raise ChunkTranscribeError("prompt %d token_count bad" % (pos,))
        chunks.append(
            {
                "chunk_index": pos,
                "prompt_chars": len(prompt),
                "token_count": tokens,
            }
        )
    return {
        "layer": "asr",
        "model": FROZEN_MODEL_REPO,
        "model_revision": FROZEN_MODEL_REVISION,
        "language_strategy": LANGUAGE_STRATEGY,
        "language": ENGINE_LANGUAGE,
        "dictionary_snapshot": dictionary_snapshot,
        "prompt_builder_version": prompt_builder_version,
        "chunks": chunks,
        "vad_profile": dict(vad_prof) if vad_prof is not None else vad_profile(),
        "chunking_profile": (
            dict(chunking_prof) if chunking_prof is not None else chunking_profile()
        ),
        "prompt_profile": {
            "budget_tokens": 200,
            "order": "Global->Topic->Creator",
            "rebuilt_per_chunk": True,
        },
        "decode": {
            "word_timestamps": word_timestamps,
            "no_speech_threshold": FROZEN_NO_SPEECH_THRESHOLD,
            **DECODE_DEFAULTS,
        },
    }


def chunk_asr_profile_hash_input(profile: dict) -> dict:
    """Canonical hash input: vad/chunking entries included, none missed."""
    if not isinstance(profile, dict):
        raise ChunkTranscribeError("profile must be a dict")
    for field in (
        "model",
        "model_revision",
        "language_strategy",
        "language",
        "dictionary_snapshot",
        "prompt_builder_version",
        "chunks",
        "vad_profile",
        "chunking_profile",
        "decode",
    ):
        if field not in profile:
            raise ChunkTranscribeError("asr profile missing %r" % (field,))
    decode = profile["decode"]
    return {
        "model": profile["model"],
        "model_revision": profile["model_revision"],
        "language_strategy": profile["language_strategy"],
        "language": profile["language"],
        "dictionary_snapshot": profile["dictionary_snapshot"],
        "prompt_builder_version": profile["prompt_builder_version"],
        "chunks": profile["chunks"],
        "vad_profile": profile["vad_profile"],
        "chunking_profile": profile["chunking_profile"],
        "decode": {
            "word_timestamps": decode.get("word_timestamps"),
            "no_speech_threshold": decode.get("no_speech_threshold"),
        },
    }


def chunk_asr_profile_hash(profile: dict) -> str:
    """Identity digest over the canonical ASR input (vad/chunk aware)."""
    canonical = json.dumps(
        chunk_asr_profile_hash_input(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def assert_asr_layer_only(
    asr_profile: dict, normalization_profile: dict, render_profile: dict
) -> dict:
    """Assert vad/chunking entries sit only in the ASR layer."""
    for field in ("vad_profile", "chunking_profile"):
        if field not in asr_profile:
            raise ChunkTranscribeError("asr profile missing %r" % (field,))
    leaked = []
    for name, other in (
        ("normalization", normalization_profile),
        ("render", render_profile),
    ):
        if not isinstance(other, dict):
            raise ChunkTranscribeError("%s profile must be a dict" % (name,))
        for field in ("vad_profile", "chunking_profile"):
            if field in other:
                leaked.append("%s.%s" % (name, field))
    if leaked:
        raise ChunkTranscribeError("new field in wrong layer: %s" % (", ".join(leaked),))
    return {"layering": "asr-only", "checked": ["vad_profile", "chunking_profile"]}


def run_chunks(
    source_wav_path: str,
    term_sets: list,
    work_dir: str | None = None,
    word_timestamps: bool = FROZEN_WORD_DEFAULT,
    no_speech_threshold: float = FROZEN_NO_SPEECH_THRESHOLD,
    engine=None,
    chunks: list | None = None,
    dictionary_snapshot: str = "synth-no-dictionary",
    prompt_builder_version: str = "pb-v1",
) -> dict:
    """Run chunked transcription: cut, one engine call per chunk, merge.

    ``term_sets`` holds one ``{global, topic, creator}`` entry per
    chunk; prompts are rebuilt per chunk through stage7 and never
    shared. ``chunks``, when given, drives multi-chunk wiring from a
    synthetic short-chunk list (no long audio needed); otherwise the
    planner derives chunks from the wav duration. ``engine``, when
    given, is a ``(wav_path, initial_prompt) -> {text, segments}``
    callable used in place of the real call at the same single choke
    point (counting logic identical); None means the real engine.
    Text content is returned, never asserted here.
    """
    if not isinstance(source_wav_path, str) or not os.path.isfile(source_wav_path):
        raise ChunkTranscribeError("wav not readable: %r" % (source_wav_path,))
    check_wav_mono_16k(source_wav_path)
    if no_speech_threshold != FROZEN_NO_SPEECH_THRESHOLD:
        raise ChunkTranscribeError("no_speech_threshold drift refused")
    if not is_advisory_only():
        raise ChunkTranscribeError("VAD advisory gate broken")

    vad_observations = observe_vad_all(source_wav_path)
    bytes_equal = all(
        rec.get("audio_bytes_equal") for rec in vad_observations.values()
    )

    duration = _wav_duration(source_wav_path)
    chunk_list = _check_chunks(list(chunks)) if chunks is not None else plan_chunks(duration)

    prompts = build_for_chunks(term_sets)
    if len(prompts) != len(chunk_list):
        raise ChunkTranscribeError(
            "term_sets %d vs chunks %d: one prompt entry per chunk"
            % (len(term_sets), len(chunk_list))
        )

    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix="s8chunks_")
    os.makedirs(work_dir, exist_ok=True)

    call_count = 0
    per_chunk = []
    absolute_lists = []
    # 真实路径：run 级状态只在加载时解析一次——档位（含 GPU probe）、
    # manifest 校验、模型加载全部 run 级一次，chunk 循环内复用，不再每
    # chunk 重算（large-v3-turbo ~1.6GB，逐 chunk 全量哈希是无谓 IO/CPU；
    # 档位也锁死为 load 时那一份，杜绝中途环境变量变更的不一致窗口）；
    # engine 桩路径不解析、不加载任何引擎。
    real_model = None
    model_info = None
    run_config = None
    if engine is None:
        run_config = asr_backend.resolve_runtime()
        model_info = resolve_model_revision()
        real_model = asr_backend.load_model(run_config)
    t0 = time.time()
    for pos, chunk in enumerate(chunk_list):
        prompt = prompts[pos]["initial_prompt"]
        cut_path = os.path.join(work_dir, "chunk_%02d.wav" % (pos,))
        cut = _cut_chunk_wav(source_wav_path, chunk, cut_path)
        if engine is None:
            raw = _call_engine_once(
                cut["wav_path"], prompt, word_timestamps, no_speech_threshold,
                model=real_model, model_info=model_info, config=run_config,
            )
        else:
            raw = engine(cut["wav_path"], prompt)
            if not isinstance(raw, dict):
                raise ChunkTranscribeError("engine result %d must be a dict" % (pos,))
            if "text" not in raw or "segments" not in raw:
                raise ChunkTranscribeError("engine result %d malformed" % (pos,))
        call_count += 1
        absolute = to_absolute(raw["segments"], chunk["start_s"])
        absolute_lists.append({"chunk": chunk, "segments": absolute})
        per_chunk.append(
            {
                "chunk_index": pos,
                "chunk_start_s": chunk["start_s"],
                "wav_path": cut["wav_path"],
                "wav_bytes": cut["bytes"],
                "initial_prompt": prompt,
                "token_count": prompts[pos]["token_count"],
                "text": raw["text"],
                "segments_n": len(absolute),
                "absolute": absolute,
            }
        )
    if call_count != len(chunk_list):
        raise ChunkTranscribeError("engine call count drift refused")

    merged = merge_chunks(absolute_lists)
    monotonic = check_monotonic(merged["segments"])

    asr_profile = build_chunk_asr_profile(
        dictionary_snapshot,
        prompt_builder_version,
        prompts,
        word_timestamps=word_timestamps,
    )
    layering = assert_asr_layer_only(asr_profile, {}, {})
    digest = chunk_asr_profile_hash(asr_profile)

    return {
        "source_wav": os.path.abspath(source_wav_path),
        "duration_s": duration,
        "chunks": chunk_list,
        "vad": {
            "observations": vad_observations,
            "bytes_equal": bool(bytes_equal),
            "advisory_only": is_advisory_only(),
        },
        "prompts": prompts,
        "per_chunk": per_chunk,
        "merged": merged,
        "monotonic": monotonic,
        "merge_priority": list(MERGE_PRIORITY),
        "asr_profile": asr_profile,
        "asr_profile_hash": digest,
        "layering": layering,
        "alignment": frozen_alignment(),
        "decode": {
            "word_timestamps": word_timestamps,
            "no_speech_threshold": no_speech_threshold,
            **DECODE_DEFAULTS,
        },
        "engine_calls": call_count,
        "word_timestamps": word_timestamps,
        "elapsed_s": round(time.time() - t0, 1),
    }
