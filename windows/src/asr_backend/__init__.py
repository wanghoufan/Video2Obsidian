"""Windows 端 ASR 后端：**单一发布后端** faster-whisper / CTranslate2。

依据 ``docs/pm/WINDOWS-MIGRATION-PLAN.md`` §1、§5、§6：

- 只有这一个实现（不同时维护第二个后端，也不为假想后端留工厂接口），
  stage1 / stage7 / stage8 / 分词器四处绑定点都从这里出。
- 默认 ``device="cuda"`` + ``compute_type="int8_float16"``、``batch_size=1``、
  ``num_workers=1``；fp16 与 batch>1 **必须先同样本 A/B 通过**（文本、时间轴、
  prompt、峰值显存四样全过）才放行，没通行证一律拦下。
- 模型以**绝对路径**加载，先过 Manifest 的 来源/revision/许可/SHA-256 校验；
  离线由 ``HF_HUB_OFFLINE=1`` / ``TRANSFORMERS_OFFLINE=1`` 兜死（缺了在代码里
  补设，被人显式关成就报错），**绝不静默联网下载**。
- GPU 不可用 / 缺 DLL / CUDA OOM → 明确 BLOCK（人话 + 不泄漏本机路径），
  **绝不自动切 CPU**；``cpu/int8`` 只在**显式指定**时才走。

本机是 macOS，没有 CUDA 也装不了 faster-whisper，所以真实调用路径（``from
faster_whisper``、``ctranslate2``、``tokenizers``）**没有在本机跑过**；注入点
``_import`` / ``_load`` / ``gpu_probe`` 是给桩测留的，Windows 真机必须按
Stage 4 清单复核一次真实行为。
"""

from __future__ import annotations

import os
import re
import time
from importlib import import_module

from . import manifest as _manifest

# ---- 身份（对外口号） ---------------------------------------------------
BACKEND_ID = "faster-whisper"
LIBRARY_ID = "ctranslate2"
MODEL_ID = "Systran/faster-whisper-large-v3-turbo"
MODEL_ARCH = "whisper-large-v3-turbo (CTranslate2 checkpoint)"
# revision 的真值只在 manifest 里（Windows 端不沿用任何 Mac 端的版本标识），
# 这个 token 只用来标记「还没从清单里取到值」。
MANIFEST_REVISION_TOKEN = "<pinned-by-manifest>"

ENGINE_LANGUAGE = "zh"
PROMPT_BUDGET_TOKENS = 200
TEXT_JOINER = ""  # 与 Mac 端同口径：整篇文本就是各段文本顺序拼接，不额外加工

# ---- 默认运行档位（§1） --------------------------------------------------
DEFAULT_DEVICE = "cuda"
GPU_COMPUTE_TYPE = "int8_float16"
CPU_DEVICE = "cpu"
CPU_COMPUTE_TYPE = "int8"
CPU_COMPUTE_TYPES = frozenset({"int8"})
DEFAULT_BATCH_SIZE = 1
DEFAULT_NUM_WORKERS = 1
SUPPORTED_DEVICES = frozenset({"cuda", "cpu"})
DEFAULT_CLIP = "0"
DEFAULT_NO_SPEECH_THRESHOLD = 0.6
DEFAULT_WORD_TIMESTAMPS = False
DECODE_LIBRARY_DEFAULTS = {
    "beam_size": 5,
    "best_of": 5,
    "patience": 1,
    "length_penalty": 1,
    "repetition_penalty": 1,
    "no_repeat_ngram_size": 0,
    "temperature": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    "compression_ratio_threshold": 2.4,
    "log_prob_threshold": -1.0,
    "no_speech_threshold": DEFAULT_NO_SPEECH_THRESHOLD,
    "condition_on_previous_text": True,
    "clip_timestamps": DEFAULT_CLIP,
    "word_timestamps": DEFAULT_WORD_TIMESTAMPS,
    "vad_filter": False,
}

# ---- 开关（显式才生效） --------------------------------------------------
OFFLINE_ENV_KEYS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
AB_ENV = "V2O_ASR_AB_APPROVED"      # fp16 / batch>1 的 A/B 通行证
FORCE_CPU_ENV = "V2O_ASR_FORCE_CPU"  # 显式 CPU int8 兜底
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSY = frozenset({"0", "false", "no", "off"})

# Mac 端 MLX 的旧 revision：撞上就是「没换干净」，必须拦。
MLX_REVISION = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"

# ---- 人话（无本机路径） --------------------------------------------------
MSG_DOWNLOAD_ENABLED = (
    "本程序离线才能用（不许偷偷联网下载模型），但 %s 被改成了允许联网："
    "请把该环境变量改回 1 或删掉后重试。"
)
MSG_GPU_UNAVAILABLE = (
    "这台机器的 GPU 现在用不了（没有可用显卡 / 驱动或 CUDA 运行库没装好），"
    "所以没有开始转写：本程序不会自己偷偷降级到 CPU。"
    "要用 CPU 兜底请在页面上显式勾选「CPU int8 兜底」（会明显变慢），"
    "或修好驱动后重试。"
)
MSG_GPU_PROBE_FAILED = (
    "GPU 状态查不出来（CTranslate2 没能报告可用显卡数量），不猜、不降级："
    "请把驱动/CUDA 运行库装好后重试，或显式选择 CPU int8 兜底。"
)
MSG_CT2_IMPORT = (
    "转写引擎没装好：faster-whisper / CTranslate2 在这个 Python 环境里不可用。"
    "请用仓库根的一键启动（它会按锁好的依赖清单重建环境）后重试。"
)
MSG_AB_REQUIRED = (
    "%s 与默认档位不一样：按规矩必须先在同一样本上做完 A/B（文本、时间轴、"
    "提示词、峰值显存四项全过），并把通行证 %s=1 打开后才能启用。"
)
MSG_CPU_COMPUTE = (
    "CPU 兜底只支持 int8 一种计算精度：要用别的精度必须先完成 A/B 对比。"
)
MSG_DEVICE_UNSUPPORTED = (
    "Windows 端只支持 GPU（cuda）与显式 CPU（cpu）两种设备，别的值不用。"
)
MSG_ENGINE_LOAD_FAILED = (
    "转写引擎没能加载起来（%s）：没有开始转写，也没有悄悄换成别的设备。"
    "请检查显卡驱动、CUDA 运行库与模型文件是否完好。"
)
MSG_GPU_OOM = (
    "显存不够，模型没能加载/跑完：已停，没有产出半成品。"
    "请先关掉占用显卡的程序重试；仍不行请显式选择 CPU int8 兜底（会明显变慢）。"
)
MSG_TRANSCRIBE_FAILED = (
    "转写过程出错（%s）：本段没有产出，也没有用别的方式顶替。"
)
MSG_SEGMENT_TIME = (
    "引擎返回的片段时间轴不合规矩（结束时间早于开始时间）：不猜、不改数字，已停。"
)
MSG_TOKENIZER_LOAD = (
    "模型自带的分词器读不出来：不能用这台机器上的其他分词器顶替（字数限制会"
    "算错），请确认模型目录完整。"
)
MSG_PRECHECK_BACKEND = (
    "转写引擎没就绪：这台机器缺 faster-whisper / CTranslate2（Windows 端不再"
    "使用 Mac 端那套引擎）。请用仓库根的一键脚本按锁好的依赖清单装好后重试。"
)
MSG_PRECHECK_FROZEN = (
    "转写模型还没在这台机器上按规矩登记好（%s）：请先冻结模型再启动监听。"
)

_OOM_RE = re.compile(
    r"out of memory|oom|allocate|failed to allocate|cublas|cudnn|hipblas", re.I
)
_CUDA_RE = re.compile(
    r"cuda|cudnn|cublas|nvidia|dll not found|cannot open shared|could not load",
    re.I,
)


class AsrBlock(RuntimeError):
    """转写链路上任何一个不确定性：调用方必须 BLOCK 并把 ``message`` 给人类。"""

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.detail = dict(detail or {})


def _env(environ: dict | None = None) -> dict:
    return os.environ if environ is None else environ


def _truthy(value: str | None, fallback: bool = False) -> bool:
    low = str(value or "").strip().lower()
    if low in _TRUTHY:
        return True
    if low in _FALSY:
        return False
    return fallback


# ---- 离线 ================================================================
def enforce_offline(environ: dict | None = None) -> dict:
    """离线门禁（fail-closed）。

    环境变量没设 → 在代码里补设成 1（自己把门关上）；被人显式设成 0/false →
    直接 BLOCK（说明有人想开下载口子，不做猜测）。
    """
    env = _env(environ)
    closed: list[str] = []
    for key in OFFLINE_ENV_KEYS:
        value = str(env.get(key) or "").strip()
        low = value.lower()
        if low in _FALSY:
            raise AsrBlock("BLOCKED_ONLINE_DOWNLOAD_ENABLED",
                           MSG_DOWNLOAD_ENABLED % (key,))
        if value == "" or low not in _TRUTHY:
            env[key] = "1"
            closed.append(key)
    return {
        "offline": True,
        "closed_in_code": closed,
        "env": {key: env.get(key) for key in OFFLINE_ENV_KEYS},
    }


# ---- 运行档位 ============================================================
def default_gpu_probe() -> bool:
    """真机默认探测：问 CTranslate2 有几张可用显卡（本机跑不了这段）。"""
    try:
        import ctranslate2  # noqa: PLC0415 (运行时依赖，Windows 才有)
    except Exception as exc:  # 缺 CUDA wheel / 装错环境都在这里落地成 BLOCK
        raise AsrBlock("BLOCKED_CT2_IMPORT", MSG_CT2_IMPORT,
                       {"error": "%s: %s" % (type(exc).__name__, exc)}) from exc
    try:
        return int(ctranslate2.get_cuda_device_count()) > 0
    except Exception as exc:
        raise AsrBlock("BLOCKED_GPU_PROBE_FAILED", MSG_GPU_PROBE_FAILED,
                       {"error": "%s: %s" % (type(exc).__name__, exc)}) from exc


def resolve_runtime(
    device: str | None = None,
    compute_type: str | None = None,
    batch_size: int | None = None,
    num_workers: int | None = None,
    explicit_cpu: bool = False,
    gpu_probe=None,
    environ: dict | None = None,
    ab_approved: bool | None = None,
) -> dict:
    """解析这一跑要用什么档位；拿不准就抛 :class:`AsrBlock`，**不降级**。

    ``explicit_cpu``/``V2O_ASR_FORCE_CPU=1``/``device="cpu"`` 三种写法都认作
    「显式指定 CPU」，只有这时才走 ``cpu/int8``；其余一律按 GPU 档位，探测
    不到显卡就 BLOCK，绝不自作主张切 CPU。
    """
    env = _env(environ)
    approved = _truthy(env.get(AB_ENV)) if ab_approved is None else bool(ab_approved)
    want_cpu = bool(explicit_cpu) or (str(device or "").lower() == CPU_DEVICE)
    if not want_cpu:
        want_cpu = _truthy(env.get(FORCE_CPU_ENV))

    if want_cpu:
        ct = str(compute_type or CPU_COMPUTE_TYPE).lower()
        if ct not in CPU_COMPUTE_TYPES and not approved:
            raise AsrBlock("BLOCKED_COMPUTE_TYPE_LOCKED", MSG_CPU_COMPUTE)
        return {
            "device": CPU_DEVICE, "compute_type": ct,
            "batch_size": int(batch_size or DEFAULT_BATCH_SIZE),
            "num_workers": int(num_workers or DEFAULT_NUM_WORKERS),
            "explicit_cpu": True, "gpu_available": None,
            "ab_approved": bool(approved),
            "fallback": "explicit-cpu",
        }

    dev = str(device or DEFAULT_DEVICE).lower()
    if dev not in SUPPORTED_DEVICES:
        raise AsrBlock("BLOCKED_DEVICE_UNSUPPORTED", MSG_DEVICE_UNSUPPORTED)
    ct = str(compute_type or GPU_COMPUTE_TYPE).lower()
    if ct != GPU_COMPUTE_TYPE and not approved:
        raise AsrBlock("BLOCKED_COMPUTE_TYPE_NOT_APPROVED",
                       MSG_AB_REQUIRED % ("计算精度 " + ct, AB_ENV))
    batch = int(batch_size or DEFAULT_BATCH_SIZE)
    if batch > DEFAULT_BATCH_SIZE and not approved:
        raise AsrBlock("BLOCKED_BATCH_NOT_APPROVED",
                       MSG_AB_REQUIRED % ("批次 batch_size=%d" % (batch,), AB_ENV))

    probe = gpu_probe or default_gpu_probe
    available = bool(probe())
    if dev == DEFAULT_DEVICE and not available:
        # 红线：GPU 不可用只能明确报错，绝不自动切 CPU。
        raise AsrBlock("BLOCKED_GPU_UNAVAILABLE", MSG_GPU_UNAVAILABLE,
                       {"device": dev, "compute_type": ct})
    return {
        "device": dev, "compute_type": ct, "batch_size": batch,
        "num_workers": int(num_workers or DEFAULT_NUM_WORKERS),
        "explicit_cpu": False, "gpu_available": available,
        "ab_approved": bool(approved), "fallback": None,
    }


def model_identity(config: dict | None = None) -> dict:
    """这一跑的身份卡（写进 ASR profile）：后端/库/模型/版本/档位。

    这里**不碰 GPU**（跑身份登记不需要显卡），版本刷新自 manifest；manifest
    尚不可用时如实记 ``revision_pinned=False`` 并带 code。
    """
    try:
        pin = _manifest.verify_model(environ=None)
        revision = pin.get("revision")
        revision_ok = bool(pin.get("ok"))
        pin_code = pin.get("code")
    except _manifest.ManifestBlock as exc:
        revision, revision_ok, pin_code = None, False, exc.code
    cfg = dict(config or {})
    return {
        "backend": BACKEND_ID,
        "library": LIBRARY_ID,
        "model": MODEL_ID,
        "model_arch": MODEL_ARCH,
        "model_revision": revision,
        "revision_pinned": revision_ok,
        "pin_code": pin_code,
        "device": cfg.get("device", DEFAULT_DEVICE),
        "compute_type": cfg.get("compute_type", GPU_COMPUTE_TYPE),
        "batch_size": int(cfg.get("batch_size", DEFAULT_BATCH_SIZE)),
        "num_workers": int(cfg.get("num_workers", DEFAULT_NUM_WORKERS)),
        "fallback": cfg.get("fallback"),
        "load_mode": "absolute-path",
        "offline_env": list(OFFLINE_ENV_KEYS),
    }


def require_pinned_model(environ: dict | None = None) -> dict:
    """过不了供应链校验就抛 :class:`AsrBlock`（沿用 manifest 的人话）。"""
    try:
        result = _manifest.require_model(environ=environ)
    except _manifest.ManifestBlock as exc:
        raise AsrBlock(exc.code, exc.message, exc.detail) from exc
    return result


# ---- 引擎加载 ============================================================
def _import_engine(_import=None):
    if _import is not None:
        return _import()
    try:
        return import_module("faster_whisper")
    except Exception as exc:
        raise AsrBlock("BLOCKED_ENGINE_IMPORT", MSG_CT2_IMPORT,
                       {"error": "%s: %s" % (type(exc).__name__, exc)}) from exc


def _map_load_error(exc: Exception, config: dict) -> AsrBlock:
    text = "%s: %s" % (type(exc).__name__, exc)
    if _OOM_RE.search(text):
        return AsrBlock("BLOCKED_GPU_OOM", MSG_GPU_OOM,
                        {"error": text, "config": dict(config)})
    if _CUDA_RE.search(text.lower()):
        return AsrBlock("BLOCKED_CUDA_BACKEND", MSG_ENGINE_LOAD_FAILED % ("显卡运行库不可用",),
                        {"error": text, "config": dict(config)})
    return AsrBlock("BLOCKED_ENGINE_LOAD", MSG_ENGINE_LOAD_FAILED % (text,),
                    {"error": text, "config": dict(config)})


def load_model(config: dict | None = None, environ: dict | None = None,
               _import=None):
    """加载 faster-whisper 模型：先验货（manifest）→ 再离线 → 绝对路径加载。"""
    cfg = config or resolve_runtime(environ=environ)
    pin = require_pinned_model(environ=environ)
    enforce_offline(environ=environ)
    local_path = pin["local_path"]
    fw = _import_engine(_import)
    try:
        model = fw.WhisperModel(
            local_path,
            device=cfg["device"],
            device_index=0,
            compute_type=cfg["compute_type"],
            num_workers=int(cfg["num_workers"]),
            local_files_only=True,
        )
    except AsrBlock:
        raise
    except Exception as exc:
        raise _map_load_error(exc, cfg) from exc
    return model


# ---- 片段归一化（输出契约） ==============================================
def _field(seg, name: str, default=None):
    """兼容 namedtuple（faster-whisper 的 Segment）与 dict 两种返回形态。"""
    if isinstance(seg, dict):
        return seg.get(name, default)
    return getattr(seg, name, default)


def _to_float(value, label: str, idx: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AsrBlock("BLOCKED_SEGMENT_SHAPE",
                       MSG_SEGMENT_TIME, {"segment": idx, "field": label})
    return float(value)


def normalize_segments(raw) -> list:
    """把引擎片段规整成 ``{start, end, text}``（+开字时间戳时的 words）。

    契约：按 ``start`` 单调不减（引擎偶发乱序时排序修好并记 ``reordered``），
    ``end >= start``；时间原样保留相对秒（转绝对时间是 stage8 的事）。
    """
    if not isinstance(raw, (list, tuple)):
        raise AsrBlock("BLOCKED_SEGMENT_SHAPE", MSG_SEGMENT_TIME, {})
    items = []
    for idx, seg in enumerate(raw):
        text = _field(seg, "text", "")
        if not isinstance(text, str):
            raise AsrBlock("BLOCKED_SEGMENT_SHAPE", MSG_SEGMENT_TIME,
                           {"segment": idx})
        start = _to_float(_field(seg, "start", 0.0), "start", idx)
        end = _to_float(_field(seg, "end", 0.0), "end", idx)
        if start < 0 or end < 0 or end < start:
            raise AsrBlock("BLOCKED_SEGMENT_TIME", MSG_SEGMENT_TIME,
                           {"segment": idx, "start": start, "end": end})
        item = {"start": start, "end": end, "text": text}
        words = _field(seg, "words", None)
        if words:
            item["words"] = [
                {"start": _to_float(_field(w, "start", 0.0), "word.start", idx),
                 "end": _to_float(_field(w, "end", 0.0), "word.end", idx),
                 "word": str(_field(w, "word", "") or "")}
                for w in words
            ]
        items.append(item)
    ordered = sorted(items, key=lambda s: (s["start"], s["end"]))
    before = [(s["start"], s["end"]) for s in items]
    reordered = before != [(s["start"], s["end"]) for s in ordered]
    if reordered:
        items = ordered
    return items


def is_monotonic(segments: list) -> bool:
    """时间轴单调判定（stage8 merge 之后的最后一道自检口径一致）。"""
    prev = None
    for seg in segments or []:
        start = float(seg["start"])
        prev_start = prev if prev is not None else start
        if start < prev_start - 1e-9:
            return False
        prev = max(prev_start, start)
    return True


def join_text(segments: list) -> str:
    """整篇文本：各片段文本顺序拼接，不加不改（同 Mac 端口径）。"""
    return TEXT_JOINER.join(str(seg.get("text", "")) for seg in segments or [])


def _info_dict(info) -> dict:
    if info is None:
        return {"language": None, "language_probability": None, "duration": None}
    return {
        "language": _field(info, "language", None),
        "language_probability": _field(info, "language_probability", None),
        "duration": _field(info, "duration", None),
        "duration_after_vad": _field(info, "duration_after_vad", None),
    }


def _engine_kwargs(decode: dict | None, initial_prompt: str | None,
                   language: str | None, word_timestamps: bool,
                   no_speech_threshold: float) -> dict:
    """把 stage1 记录的 decode 默认值翻译成 faster-whisper 的入参名。"""
    src = dict(decode or {})
    kwargs = dict(DECODE_LIBRARY_DEFAULTS)
    if src.get("temperature_schedule"):
        kwargs["temperature"] = tuple(src["temperature_schedule"])
    for key in ("compression_ratio_threshold", "condition_on_previous_text"):
        if key in src:
            kwargs[key] = src[key]
    if "logprob_threshold" in src:  # stage 侧的旧字段名 → 库里的 log_prob
        kwargs["log_prob_threshold"] = src["logprob_threshold"]
    if src.get("clip") is not None:
        kwargs["clip_timestamps"] = src["clip"]
    kwargs["word_timestamps"] = bool(word_timestamps)
    kwargs["no_speech_threshold"] = float(no_speech_threshold)
    kwargs["language"] = language or ENGINE_LANGUAGE
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt
    return kwargs


def transcribe_file(
    wav_path: str,
    model=None,
    initial_prompt: str | None = None,
    language: str | None = None,
    word_timestamps: bool = DEFAULT_WORD_TIMESTAMPS,
    no_speech_threshold: float = DEFAULT_NO_SPEECH_THRESHOLD,
    decode: dict | None = None,
    config: dict | None = None,
    environ: dict | None = None,
    _import=None,
) -> dict:
    """一次音频一次调用：返回 ``{text, segments, info, ...}``。

    ``model`` 为空时按当前档位自行加载（仍走同一道供应链校验）。片段一定会
    过 :func:`normalize_segments`，调用方拿到的时间轴必然单调。
    """
    if not isinstance(wav_path, str) or not os.path.isfile(wav_path):
        raise AsrBlock("BLOCKED_AUDIO_MISSING",
                       "这段音频不存在或读不到：没有调用引擎。")
    cfg = config or resolve_runtime(environ=environ)
    engine = model if model is not None else load_model(
        cfg, environ=environ, _import=_import)
    kwargs = _engine_kwargs(decode, initial_prompt, language, word_timestamps,
                            no_speech_threshold)
    t0 = time.time()
    try:
        raw_segments, info = engine.transcribe(str(wav_path), **kwargs)
        raw = list(raw_segments)
    except AsrBlock:
        raise
    except Exception as exc:
        text = "%s: %s" % (type(exc).__name__, exc)
        if _OOM_RE.search(text):
            raise AsrBlock("BLOCKED_GPU_OOM", MSG_GPU_OOM, {"error": text}) from exc
        raise AsrBlock("BLOCKED_TRANSCRIBE_FAILED",
                       MSG_TRANSCRIBE_FAILED % (text,), {"error": text}) from exc
    elapsed = round(time.time() - t0, 3)
    segments = normalize_segments(raw)
    return {
        "text": join_text(segments),
        "segments": segments,
        "info": _info_dict(info),
        "engine": BACKEND_ID,
        "library": LIBRARY_ID,
        "model": MODEL_ID,
        "config": cfg,
        "decode": dict(kwargs),
        "initial_prompt": initial_prompt,
        "prompt_chars": len(initial_prompt or ""),
        "word_timestamps": bool(word_timestamps),
        "no_speech_threshold": float(no_speech_threshold),
        "monotonic": is_monotonic(segments),
        "asr_calls": 1,
        "engine_calls": 1,
        "transcribe_s": elapsed,
    }


# ---- 分词器（prompt 预算，200 token 口径） ===============================
_TOKENIZER_CACHE: dict = {}


def load_tokenizer(local_path: str | None = None, environ: dict | None = None,
                   _load=None):
    """取模型自带的 tokenizer（Windows 端不再用 Mac 端那套分词器）。

    真机路径读到模型目录里的 ``tokenizer.json``（faster-whisper 自带的分词器
    就是它）；``_load`` 是桩测注入点。
    """
    if _load is not None:
        return _load(local_path)
    path = local_path or require_pinned_model(environ=environ)["local_path"]
    key = os.path.abspath(path)
    if key in _TOKENIZER_CACHE:
        return _TOKENIZER_CACHE[key]
    if not os.path.isdir(key):
        raise AsrBlock("BLOCKED_MODEL_FILES_MISSING",
                       _manifest.MSG_FILES_MISSING, {"model_dir": key})
    tok_file = os.path.join(key, "tokenizer.json")
    if not os.path.isfile(tok_file):
        raise AsrBlock("BLOCKED_MODEL_TOKENIZER_MISSING",
                       _manifest.MSG_TOKENIZER_MISSING, {"tokenizer": tok_file})
    try:
        from tokenizers import Tokenizer  # noqa: PLC0415 (Windows/venv 才装)
        tokenizer = Tokenizer.from_file(tok_file)
    except Exception as exc:
        raise AsrBlock("BLOCKED_TOKENIZER_LOAD", MSG_TOKENIZER_LOAD,
                       {"error": "%s: %s" % (type(exc).__name__, exc)}) from exc
    _TOKENIZER_CACHE[key] = tokenizer
    return tokenizer


def _encode_len(tokenizer, text: str) -> int:
    encoded = tokenizer.encode(text)
    ids = getattr(encoded, "ids", None)
    if ids is None:
        ids = list(encoded)
    return len(ids)


def count_tokens(text: str, tokenizer=None, local_path: str | None = None,
                 environ: dict | None = None, _load=None) -> int:
    """用**模型自带分词器**数 token（和 Mac 端同一口径：``" " + 去空格文本``）。"""
    if not isinstance(text, str):
        raise ValueError("text must be str")
    if text.strip() == "":
        return 0
    tok = tokenizer if tokenizer is not None else load_tokenizer(
        local_path, environ=environ, _load=_load)
    return _encode_len(tok, " " + text.strip())


def clear_tokenizer_cache() -> None:
    """测试与切模型时用：清掉分词器缓存。"""
    _TOKENIZER_CACHE.clear()


# ---- 可用性预检（启动链用，不加载模型） ==================================
def availability(environ: dict | None = None) -> dict:
    """UI 预检：不讲行话——缺什么、为什么不能用，都说清。

    不碰 GPU 探测（那是开跑时的事），也不加载模型；目标只是让人在按下「开始
    监听」前就知道这机器能不能转。
    """
    env = _env(environ)
    out = {
        "ok": True, "code": None, "message": "",
        "backend": BACKEND_ID, "library": LIBRARY_ID, "model": MODEL_ID,
        "revision_pinned": False, "offline": True, "checks": [],
    }

    def _fail(code: str, message: str, **detail) -> dict:
        out.update(ok=False, code=code, message=message)
        out["checks"].append({"code": code, "ok": False, "detail": dict(detail)})
        return out

    for module in ("faster_whisper", "ctranslate2"):
        try:
            import_module(module)
        except Exception as exc:
            return _fail("PRECHECK_ASR_BACKEND_NOT_READY", MSG_PRECHECK_BACKEND,
                         error="%s: %s" % (type(exc).__name__, exc))
    out["checks"].append({"code": "PRECHECK_ASR_BACKEND_NOT_READY", "ok": True,
                          "detail": {"modules": ["faster_whisper", "ctranslate2"]}})
    for key in OFFLINE_ENV_KEYS:
        value = str(env.get(key) or "").strip()
        if value.lower() in _FALSY:
            return _fail("PRECHECK_ONLINE_DOWNLOAD_ENABLED",
                         MSG_DOWNLOAD_ENABLED % (key,))
    try:
        pin = _manifest.verify_model(environ=env)
    except _manifest.ManifestBlock as exc:
        pin = {"ok": False, "code": exc.code, "message": exc.message,
               "revision": None}
    out["revision_pinned"] = bool(pin.get("ok"))
    if not pin.get("ok"):
        return _fail(str(pin.get("code") or "PRECHECK_MODEL_NOT_FROZEN"),
                     MSG_PRECHECK_FROZEN % (pin.get("message") or "未知原因"),
                     model=MODEL_ID)
    out["model_revision"] = pin.get("revision")
    out["checks"].append({"code": "PRECHECK_MODEL_FROZEN", "ok": True,
                          "detail": {"revision": pin.get("revision")}})
    return out
