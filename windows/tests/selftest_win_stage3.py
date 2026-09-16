#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stage 3 自测：asr_backend 适配层 + stage7/8 接线（全桩注入）。

本机是 macOS，没有 CUDA、装不了 faster-whisper/ctranslate2，所以全部走
asr_backend 预留的注入点（``_import`` / ``_load`` / ``gpu_probe``）与模块
级桩；不装 faster-whisper、不联网、不下载任何模型。测试只用外置 tmp +
合成数据，不碰用户真实目录（首行断言 tmp 根在系统临时目录下）。

跑法（在仓库根）：
    .venv/bin/python windows/tests/selftest_win_stage3.py   # rc=0 即通过

覆盖清单：
  1. 默认档位解析（cuda/int8_float16/batch=1/worker=1）
  2. fp16 / batch>1 无 A/B 通行证被拦；有通行证放行
  3. GPU 探测 False → BLOCK，绝不自动降级 CPU；人话不带本机路径
  4. 显式 CPU（三写法）才走 cpu/int8；CPU 非 int8 无通行证被拦
  5. 离线门：显式设 0 被拦；缺省在代码里补 1
  6. manifest 未冻结 / 缺失 → BLOCK；冻结齐全才放行加载（桩引擎）
  7. normalize_segments：乱序排序修好；倒置时间轴 BLOCK
  8. transcribe_file 双向有牙：音频不存在桩引擎零调用；摘桩后真被调
  9. count_tokens 桩分词器（" " + 去空格文本 口径）
  10. stage7 接线：run_single_file_with_prompt 走 asr_backend.transcribe_file
  11. stage8 接线：_call_engine_once / run_chunks 走 asr_backend
  12. availability 预检：缺引擎 fail-closed
  13. Stage3 返工：run 级 manifest/档位只解析一次（[11c]）；
      _cut_chunk_wav 经 platform_win.run_ffmpeg 单点（[11d]）

反向证伪（teeth）：每条把关键判断改坏，对应断言必须变红；变红=有牙，
仍绿=无牙（无牙按失败计，rc!=0）。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import tempfile
import types
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
WIN_ROOT = os.path.dirname(HERE)          # windows/
SRC = os.path.join(WIN_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import asr_backend  # noqa: E402
import platform_win  # noqa: E402
from asr_backend import manifest as manifest_mod  # noqa: E402
from stage7 import prompt_builder  # noqa: E402
import stage7.transcribe as s7t  # noqa: E402
import stage8.transcribe_chunks as s8tc  # noqa: E402

TMP_ROOT = tempfile.mkdtemp(prefix="v2o-win-stage3-")

# 原始实现引用（teeth 的 restore 用；必须在任何打桩前捕获）
ORIG = {
    "resolve_runtime": asr_backend.resolve_runtime,
    "require_pinned_model": asr_backend.require_pinned_model,
    "is_monotonic": asr_backend.is_monotonic,
    "isfile": os.path.isfile,
    "_encode_len": asr_backend._encode_len,
    "transcribe_file": asr_backend.transcribe_file,
    "_call_engine_once": s8tc._call_engine_once,
    "_cut_chunk_wav_current": s8tc._cut_chunk_wav,
}
ORIG_FALSY = set(asr_backend._FALSY)
ORIG_CPU_CT = set(asr_backend.CPU_COMPUTE_TYPES)


# ---- 计数与断言 ---------------------------------------------------------
class Checker:
    def __init__(self) -> None:
        self.total = 0
        self.failed: list[str] = []
        self.teeth_total = 0
        self.teeth_sharp = 0

    def ok(self, cond: bool, label: str) -> bool:
        self.total += 1
        if cond:
            print("  PASS  %s" % (label,))
        else:
            self.failed.append(label)
            print("  FAIL  %s" % (label,))
        return bool(cond)

    def teeth(self, label: str, mutate, restore, probe) -> bool:
        """改坏实现 → 断言必须变红；变红=有牙，仍绿=无牙（计失败）。"""
        self.teeth_total += 1
        try:
            mutate()
            red = not bool(probe())
        finally:
            restore()
        if red:
            self.teeth_sharp += 1
            print("  牙    [有牙] %s（改坏后断言变红）" % (label,))
        else:
            self.failed.append("无牙: %s" % (label,))
            print("  牙    [无牙] %s（改坏后断言仍绿！）" % (label,))
        return red


T = Checker()


def expect_block(fn, code: str, label: str) -> bool:
    """调用必须抛 AsrBlock 且 code 匹配。"""
    try:
        fn()
    except asr_backend.AsrBlock as exc:
        return T.ok(exc.code == code,
                    "%s（实测 code=%s）" % (label, exc.code))
    except Exception as exc:  # noqa: BLE001
        return T.ok(False, "%s（抛了非 AsrBlock：%s: %s）"
                    % (label, type(exc).__name__, exc))
    return T.ok(False, "%s（没有 BLOCK，静默放行）" % (label,))


@contextlib.contextmanager
def patched(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


# ---- 合成数据与桩引擎 ---------------------------------------------------
def make_wav(name: str, seconds: float = 0.2) -> str:
    """合成 16k 单声道 wav（外置 tmp，非用户目录）。"""
    path = os.path.join(TMP_ROOT, name)
    rate = 16000
    frames = int(rate * seconds)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frames)
    return path


class FakeInfo:
    def __init__(self, language="zh", probability=0.9, duration=0.2) -> None:
        self.language = language
        self.language_probability = probability
        self.duration = duration
        self.duration_after_vad = duration


class FakeFWModule:
    """假 faster_whisper 模块：WhisperModel 记录入参，不真转写。"""

    inits: list = []

    class WhisperModel:
        def __init__(self, path, **kwargs) -> None:
            FakeFWModule.inits.append({"path": path, **kwargs})


class FakeTokenizer:
    def __init__(self) -> None:
        self.seen: list = []

    def encode(self, text):
        self.seen.append(text)
        return [1] * (len(text) + 1)  # 只关心 ids 长度


CPU_CFG = {
    "device": "cpu", "compute_type": "int8", "batch_size": 1,
    "num_workers": 1, "fallback": "explicit-cpu",
}

# =========================================================================
print("[0] 环境自检：tmp 根在系统临时目录下（不碰用户真实目录）")
T.ok(TMP_ROOT.startswith(tempfile.gettempdir()),
     "data_root 在 tmp 下：%s" % (TMP_ROOT,))

# =========================================================================
print("\n[1] 默认档位解析（cuda/int8_float16/batch=1/worker=1）")
rt = asr_backend.resolve_runtime(gpu_probe=lambda: True, environ={})
T.ok(rt["device"] == "cuda" and rt["compute_type"] == "int8_float16",
     "默认 device/compute_type：%s/%s" % (rt["device"], rt["compute_type"]))
T.ok(rt["batch_size"] == 1 and rt["num_workers"] == 1,
     "默认 batch=1 / num_workers=1")
T.ok(rt["gpu_available"] is True and rt["fallback"] is None
     and rt["ab_approved"] is False,
     "GPU 可用、无降级、无 A/B 通行证")

print("\n[2] fp16 / batch>1 无 A/B 通行证被拦；有通行证放行")
expect_block(
    lambda: asr_backend.resolve_runtime(compute_type="float16",
                                        gpu_probe=lambda: True, environ={}),
    "BLOCKED_COMPUTE_TYPE_NOT_APPROVED", "fp16 无通行证 → BLOCK")
expect_block(
    lambda: asr_backend.resolve_runtime(batch_size=4,
                                        gpu_probe=lambda: True, environ={}),
    "BLOCKED_BATCH_NOT_APPROVED", "batch>1 无通行证 → BLOCK")
rt2 = asr_backend.resolve_runtime(compute_type="float16", batch_size=4,
                                  gpu_probe=lambda: True, environ={},
                                  ab_approved=True)
T.ok(rt2["device"] == "cuda" and rt2["compute_type"] == "float16"
     and rt2["batch_size"] == 4 and rt2["ab_approved"] is True,
     "有 A/B 通行证 → fp16/batch=4 放行")


def _cpu_fp16_blocked() -> bool:
    try:
        asr_backend.resolve_runtime(explicit_cpu=True, compute_type="float16",
                                    environ={})
        return False
    except asr_backend.AsrBlock:
        return True


T.teeth("CPU 只认 int8（白名单放宽后 fp16 溜进 CPU 档被测出）",
        lambda: setattr(asr_backend, "CPU_COMPUTE_TYPES",
                        frozenset({"int8", "float16"})),
        lambda: setattr(asr_backend, "CPU_COMPUTE_TYPES",
                        frozenset(ORIG_CPU_CT)),
        _cpu_fp16_blocked)

print("\n[3] GPU 探测 False → BLOCK，绝不自动降级 CPU")
expect_block(
    lambda: asr_backend.resolve_runtime(gpu_probe=lambda: False, environ={}),
    "BLOCKED_GPU_UNAVAILABLE", "GPU 不可用 → BLOCK（不降级）")
try:
    asr_backend.resolve_runtime(gpu_probe=lambda: False, environ={})
except asr_backend.AsrBlock as exc:
    msg = exc.message
    T.ok("CPU" in msg and "降级" in msg, "人话讲明「不会偷偷降级 CPU」")
    T.ok(TMP_ROOT not in msg and "/Users/" not in msg and "\\" not in msg,
         "人话不带本机路径")


def _raises_gpu_block() -> bool:
    try:
        asr_backend.resolve_runtime(gpu_probe=lambda: False, environ={})
        return False
    except asr_backend.AsrBlock as exc:
        return exc.code == "BLOCKED_GPU_UNAVAILABLE"


def _degraded_resolve(*args, **kwargs):
    """假想的「自动降级」实现：GPU BLOCK 后偷偷回 CPU。"""
    try:
        return ORIG["resolve_runtime"](*args, **kwargs)
    except asr_backend.AsrBlock:
        return dict(CPU_CFG)


T.teeth("GPU BLOCK 红线（实现若偷偷降级 CPU，测试立刻抓住）",
        lambda: setattr(asr_backend, "resolve_runtime", _degraded_resolve),
        lambda: setattr(asr_backend, "resolve_runtime",
                        ORIG["resolve_runtime"]),
        _raises_gpu_block)

print("\n[4] 显式 CPU 才走 cpu/int8")
rt3 = asr_backend.resolve_runtime(explicit_cpu=True, environ={})
T.ok(rt3["device"] == "cpu" and rt3["compute_type"] == "int8"
     and rt3["fallback"] == "explicit-cpu",
     "explicit_cpu=True → cpu/int8（不碰 GPU 探测）")
rt4 = asr_backend.resolve_runtime(environ={"V2O_ASR_FORCE_CPU": "1"})
T.ok(rt4["device"] == "cpu" and rt4["compute_type"] == "int8",
     "V2O_ASR_FORCE_CPU=1 → cpu/int8")
rt5 = asr_backend.resolve_runtime(device="cpu", environ={})
T.ok(rt5["device"] == "cpu", "device='cpu' 显式写法 → cpu/int8")
expect_block(
    lambda: asr_backend.resolve_runtime(explicit_cpu=True,
                                        compute_type="float16", environ={}),
    "BLOCKED_COMPUTE_TYPE_LOCKED", "CPU 非 int8 无通行证 → BLOCK")
expect_block(
    lambda: asr_backend.resolve_runtime(device="mps", environ={}),
    "BLOCKED_DEVICE_UNSUPPORTED", "device=mps → BLOCK")

print("\n[5] 离线门：显式设 0 被拦；缺省在代码里补 1")
expect_block(
    lambda: asr_backend.enforce_offline({"HF_HUB_OFFLINE": "0"}),
    "BLOCKED_ONLINE_DOWNLOAD_ENABLED", "HF_HUB_OFFLINE=0 → BLOCK")
expect_block(
    lambda: asr_backend.enforce_offline({"TRANSFORMERS_OFFLINE": "false"}),
    "BLOCKED_ONLINE_DOWNLOAD_ENABLED", "TRANSFORMERS_OFFLINE=false → BLOCK")
env5: dict = {}
off = asr_backend.enforce_offline(env5)
T.ok(off["offline"] is True
     and off["closed_in_code"] == list(asr_backend.OFFLINE_ENV_KEYS)
     and all(env5[k] == "1" for k in asr_backend.OFFLINE_ENV_KEYS),
     "缺省两个离线键都在代码里补成 1")
env6 = {"HF_HUB_OFFLINE": "1"}
off6 = asr_backend.enforce_offline(env6)
T.ok(off6["closed_in_code"] == ["TRANSFORMERS_OFFLINE"],
     "已显式设 1 的键不再补")


def _offline_zero_blocked() -> bool:
    try:
        asr_backend.enforce_offline({"HF_HUB_OFFLINE": "0"})
        return False
    except asr_backend.AsrBlock:
        return True


T.teeth("离线门 fail-closed（falsy 集合清空后 =0 不再被拦被测出）",
        lambda: setattr(asr_backend, "_FALSY", frozenset()),
        lambda: setattr(asr_backend, "_FALSY", frozenset(ORIG_FALSY)),
        _offline_zero_blocked)

print("\n[6] manifest 门：未冻结/缺失 → BLOCK；冻结齐全才放行加载")
missing_manifest = os.path.join(TMP_ROOT, "nope", "MODEL_MANIFEST.json")
expect_block(
    lambda: asr_backend.require_pinned_model(
        environ={"V2O_MODEL_MANIFEST": missing_manifest}),
    "BLOCKED_MANIFEST_MISSING", "清单文件缺失 → BLOCK")
expect_block(
    lambda: asr_backend.require_pinned_model(
        environ={"V2O_MODEL_MANIFEST":
                 os.path.join(WIN_ROOT, "models", "MODEL_MANIFEST.json")}),
    "BLOCKED_MODEL_REVISION_NOT_PINNED", "占位模板（revision 未冻结）→ BLOCK")

model_dir = os.path.join(TMP_ROOT, "fake-ct2-model")
os.makedirs(model_dir, exist_ok=True)
tok_payload = json.dumps({"model": "fake"}).encode("utf-8")
with open(os.path.join(model_dir, "tokenizer.json"), "wb") as fh:
    fh.write(tok_payload)
tok_sha = hashlib.sha256(tok_payload).hexdigest()
frozen_manifest = os.path.join(TMP_ROOT, "MODEL_MANIFEST.frozen.json")
with open(frozen_manifest, "w", encoding="utf-8") as fh:
    json.dump({
        "schema": manifest_mod.SCHEMA,
        "models": [{
            "model_id": asr_backend.MODEL_ID,
            "source": "https://example.invalid/ct2/turbo",
            "revision": "b" * 40,
            "license": "MIT",
            "local_path": model_dir,
            "files": [{"path": "tokenizer.json", "sha256": tok_sha,
                       "bytes": len(tok_payload)}],
        }],
    }, fh, ensure_ascii=False)
env_frozen = {"V2O_MODEL_MANIFEST": frozen_manifest}
FakeFWModule.inits = []
fake_fw = FakeFWModule()
asr_backend.load_model(dict(CPU_CFG), environ=env_frozen,
                       _import=lambda: fake_fw)
T.ok(len(FakeFWModule.inits) == 1, "清单冻结齐全 → 桩引擎被构造一次")
init = FakeFWModule.inits[0]
T.ok(init["path"] == model_dir and init["device"] == "cpu"
     and init["compute_type"] == "int8" and init["local_files_only"] is True,
     "绝对路径加载 + 锁定档位 + local_files_only")
T.ok(all(env_frozen[k] == "1" for k in asr_backend.OFFLINE_ENV_KEYS),
     "加载前离线门已把缺省离线键补成 1")


def _load_model_blocks_on_bad_manifest() -> bool:
    try:
        asr_backend.load_model(
            dict(CPU_CFG),
            environ={"V2O_MODEL_MANIFEST": missing_manifest},
            _import=lambda: fake_fw)
        return False
    except asr_backend.AsrBlock:
        return True


T.teeth("加载前供应链校验（require_pinned_model 被绕过后清单门失守被测出）",
        lambda: setattr(asr_backend, "require_pinned_model",
                        lambda **k: {"local_path": model_dir}),
        lambda: setattr(asr_backend, "require_pinned_model",
                        ORIG["require_pinned_model"]),
        _load_model_blocks_on_bad_manifest)

print("\n[7] normalize_segments：乱序修好；倒置时间轴 BLOCK")
bad_order = [
    {"start": 1.0, "end": 2.0, "text": "乙"},
    {"start": 0.0, "end": 0.5, "text": "甲"},
]
norm = asr_backend.normalize_segments(bad_order)
T.ok([s["text"] for s in norm] == ["甲", "乙"], "乱序片段按 start 排序修好")
T.ok(asr_backend.is_monotonic(norm) is True, "修好后的时间轴单调")
expect_block(
    lambda: asr_backend.normalize_segments(
        [{"start": 1.0, "end": 0.5, "text": "倒置"}]),
    "BLOCKED_SEGMENT_TIME", "end < start（倒置时间轴）→ BLOCK")
expect_block(
    lambda: asr_backend.normalize_segments("not-a-list"),
    "BLOCKED_SEGMENT_SHAPE", "非 list 输入 → BLOCK")
T.ok(asr_backend.join_text(norm) == "甲乙", "整篇文本=各段顺序拼接（同 Mac 口径）")


class Seg:  # namedtuple 形态兼容
    def __init__(self, start, end, text) -> None:
        self.start, self.end, self.text = start, end, text


norm2 = asr_backend.normalize_segments([Seg(0.0, 0.5, "对象形态")])
T.ok(norm2[0]["text"] == "对象形态", "namedtuple 形态片段同样兼容")


def _monotonic_catches_reversed() -> bool:
    return asr_backend.is_monotonic(
        [{"start": 2.0, "end": 2.5}, {"start": 1.0, "end": 1.5}]) is False


T.teeth("单调契约（is_monotonic 被改成恒真后被测出）",
        lambda: setattr(asr_backend, "is_monotonic", lambda segs: True),
        lambda: setattr(asr_backend, "is_monotonic", ORIG["is_monotonic"]),
        _monotonic_catches_reversed)

print("\n[8] transcribe_file 双向有牙：桩引擎零调用 / 摘桩后真被调")


class FakeEngine:
    """桩引擎：记录 transcribe 入参，回放预置片段。"""

    def __init__(self, segments) -> None:
        self.segments = segments
        self.calls: list = []

    def transcribe(self, path, **kwargs):
        self.calls.append({"path": path, **kwargs})
        return iter(self.segments), FakeInfo()


missing_wav = os.path.join(TMP_ROOT, "does-not-exist.wav")
engine0 = FakeEngine([])
expect_block(
    lambda: asr_backend.transcribe_file(missing_wav, model=engine0,
                                        config=dict(CPU_CFG)),
    "BLOCKED_AUDIO_MISSING", "音频不存在 → BLOCK")
T.ok(engine0.calls == [], "BLOCK 时桩引擎零调用（asr_calls=0）")


def _guard_blocks_missing_audio() -> bool:
    eng = FakeEngine([])
    try:
        asr_backend.transcribe_file(missing_wav, model=eng,
                                    config=dict(CPU_CFG))
    except asr_backend.AsrBlock:
        return True  # 闸还在：BLOCK 且引擎零调用
    return eng.calls == []


T.teeth("音频存在性闸（isfile 被改坏后缺失音频直通引擎被测出）",
        lambda: setattr(os.path, "isfile", lambda p: True),
        lambda: setattr(os.path, "isfile", ORIG["isfile"]),
        _guard_blocks_missing_audio)

good_wav = make_wav("good.wav")
engine2 = FakeEngine([
    {"start": 0.5, "end": 1.0, "text": "乙"},
    {"start": 0.0, "end": 0.5, "text": "甲"},
])
res = asr_backend.transcribe_file(good_wav, model=engine2,
                                  initial_prompt="甲乙丙",
                                  config=dict(CPU_CFG))
T.ok(len(engine2.calls) == 1, "摘桩后桩引擎真被调（恰好一次）")
call = engine2.calls[0]
T.ok(call["word_timestamps"] is False and call["no_speech_threshold"] == 0.6,
     "引擎入参：word OFF / nst 0.6（冻结契约）")
T.ok(call["language"] == "zh" and call["clip_timestamps"] == "0",
     "引擎入参：language zh / clip 0")
stub_tok = FakeTokenizer()
T.ok(call["initial_prompt"] == "甲乙丙"
     and asr_backend.count_tokens(call["initial_prompt"],
                                  _load=lambda p: stub_tok) <= 200,
     "initial_prompt 计数 ≤200 token（桩分词器口径）")
T.ok(res["text"] == "甲乙" and res["monotonic"] is True,
     "输出契约：text 顺序拼接 + 时间轴单调")
T.ok(res["segments"][0]["start"] == 0.0 and res["engine_calls"] == 1,
     "输出契约：片段归一化 + engine_calls=1")

print("\n[9] count_tokens 桩分词器（\" \" + 去空格文本 口径）")
tok = FakeTokenizer()
n = prompt_builder.count_tokens("  你好世界  ", _load=lambda p: tok)
T.ok(n == len(" 你好世界") + 1, "桩分词器计数生效（n=%d）" % (n,))
T.ok(tok.seen == [" 你好世界"],
     "口径同 Mac：encode 收到 \" \" + 去空格文本（实测 %r）" % (tok.seen,))
T.ok(prompt_builder.count_tokens("   ", _load=lambda p: tok) == 0,
     "纯空白 → 0（不调分词器）")
T.ok(tok.seen == [" 你好世界"], "纯空白确实没碰分词器")
try:
    prompt_builder.count_tokens(123)  # type: ignore[arg-type]
    T.ok(False, "非 str → PromptBuilderError")
except prompt_builder.PromptBuilderError:
    T.ok(True, "非 str → PromptBuilderError")
try:
    asr_backend.count_tokens(123)  # type: ignore[arg-type]
    T.ok(False, "asr_backend.count_tokens 非 str → ValueError")
except ValueError:
    T.ok(True, "asr_backend.count_tokens 非 str → ValueError")


def _token_count_positive() -> bool:
    return prompt_builder.count_tokens(
        "你好", _load=lambda p: FakeTokenizer()) > 0


T.teeth("token 计数（_encode_len 被改成恒 0 后计数失真被测出）",
        lambda: setattr(asr_backend, "_encode_len", lambda tok_, text: 0),
        lambda: setattr(asr_backend, "_encode_len", ORIG["_encode_len"]),
        _token_count_positive)

print("\n[10] stage7 接线：run_single_file_with_prompt 走 asr_backend")
s7_calls: list = []


def _s7_recorder(wav_path, model=None, initial_prompt=None, language=None,
                 word_timestamps=True, no_speech_threshold=0.6, decode=None,
                 config=None, environ=None, _import=None):
    s7_calls.append({
        "wav": wav_path, "prompt": initial_prompt, "language": language,
        "word": word_timestamps, "nst": no_speech_threshold, "decode": decode,
    })
    return {
        "text": "正文",
        "segments": [{"start": 0.0, "end": 0.2, "text": "正文"}],
        "info": {"language": "zh"}, "monotonic": True,
    }


s7_wav = make_wav("s7.wav")
with patched(asr_backend, "transcribe_file", _s7_recorder), \
        patched(s7t, "count_tokens", lambda text, _load=None: 3), \
        patched(s7t, "resolve_model_revision",
                lambda: {"revision_match": True,
                         "revision_resolved": "cafe123"}), \
        patched(s7t, "vad_observe_only",
                lambda p: {"mode": "advisory-only", "status": "SKIPPED",
                           "filtering_applied": False}):
    out = s7t.run_single_file_with_prompt(s7_wav, "测试提示词")
T.ok(len(s7_calls) == 1, "stage7 恰好一次引擎调用（走 asr_backend）")
c7 = s7_calls[0]
T.ok(c7["word"] is False and c7["nst"] == 0.6 and c7["language"] == "zh",
     "stage7 契约透传：word OFF / nst 0.6 / language zh")
T.ok(c7["prompt"] == "测试提示词" and c7["decode"].get("temperature_schedule"),
     "stage7 透传 initial_prompt 与 decode 默认值")
T.ok(out["text"] == "正文" and out["asr_calls"] == 1
     and out["engine_calls"] == 1, "stage7 输出契约：text/asr_calls/engine_calls")
T.ok(out["model_revision"] == "cafe123",
     "stage7 记录 manifest 解析出的 revision")
T.ok(out["detected_language"] == "zh", "stage7 从 info 取 detected language")
T.ok(out["segments"][0]["text"] == "正文", "stage7 输出 segments 来自归一化片段")
with patched(s7t, "count_tokens", lambda text, _load=None: 201):
    try:
        s7t.run_single_file_with_prompt(s7_wav, "超预算提示词")
        T.ok(False, "prompt 超 200 token → TranscribeError")
    except s7t.TranscribeError:
        T.ok(True, "prompt 超 200 token → TranscribeError")

class _BrokenBackend:
    """teeth 用：把 asr_backend 换成断路的假后端模块。"""

    def transcribe_file(self, *a, **k):
        raise RuntimeError("stage 没走 asr_backend")


s7_flag = {"routed": False}


def _s7_recorder2(wav_path, **kwargs):
    s7_flag["routed"] = True
    return {"text": "", "segments": [], "info": {}, "monotonic": True}


def _s7_probe() -> bool:
    s7_flag["routed"] = False
    try:
        with patched(asr_backend, "transcribe_file", _s7_recorder2), \
                patched(s7t, "count_tokens", lambda text, _load=None: 3), \
                patched(s7t, "resolve_model_revision",
                        lambda: {"revision_match": True,
                                 "revision_resolved": "cafe"}), \
                patched(s7t, "vad_observe_only", lambda p: {}):
            s7t.run_single_file_with_prompt(s7_wav, "提示词")
    except Exception:
        return False
    return s7_flag["routed"]


T.teeth("stage7 接线单点（s7t.asr_backend 被断路后接线失守被测出）",
        lambda: setattr(s7t, "asr_backend", _BrokenBackend()),
        lambda: setattr(s7t, "asr_backend", asr_backend),
        _s7_probe)

print("\n[11] stage8 接线：_call_engine_once / run_chunks 走 asr_backend")
s8_calls: list = []


def _s8_recorder(wav_path, model=None, initial_prompt=None, language=None,
                 word_timestamps=True, no_speech_threshold=0.6, decode=None,
                 config=None, environ=None, _import=None):
    s8_calls.append({"wav": wav_path, "model": model, "prompt": initial_prompt,
                     "word": word_timestamps, "nst": no_speech_threshold})
    return {"text": "块文本", "segments": [], "info": {"language": "zh"},
            "monotonic": True}


with patched(asr_backend, "transcribe_file", _s8_recorder), \
        patched(s8tc, "resolve_model_revision",
                lambda: {"revision_match": True,
                         "revision_resolved": "cafe"}):
    out8 = s8tc._call_engine_once(s7_wav, "块提示词", False, 0.6, model="M")
T.ok(out8 == {"text": "块文本", "segments": [], "detected": "zh"},
     "_call_engine_once 映射 text/segments/detected")
T.ok(s8_calls[0]["model"] == "M" and s8_calls[0]["nst"] == 0.6
     and s8_calls[0]["word"] is False,
     "_call_engine_once 透传 model 与冻结契约")


def _s8_recorder_bad(wav_path, **kwargs):
    return {"text": "x", "segments": [], "info": {}, "monotonic": False}


with patched(asr_backend, "transcribe_file", _s8_recorder_bad), \
        patched(s8tc, "resolve_model_revision",
                lambda: {"revision_match": True,
                         "revision_resolved": "cafe"}):
    try:
        s8tc._call_engine_once(s7_wav, "块提示词", False, 0.6, model="M")
        T.ok(False, "monotonic=False → ChunkTranscribeError")
    except s8tc.ChunkTranscribeError:
        T.ok(True, "monotonic=False → ChunkTranscribeError")

s8_flag = {"routed": False}


def _s8_recorder2(wav_path, **kwargs):
    s8_flag["routed"] = True
    return {"text": "", "segments": [], "info": {}, "monotonic": True}


def _s8_probe() -> bool:
    s8_flag["routed"] = False
    try:
        with patched(asr_backend, "transcribe_file", _s8_recorder2), \
                patched(s8tc, "resolve_model_revision",
                        lambda: {"revision_match": True,
                                 "revision_resolved": "cafe"}):
            s8tc._call_engine_once(s7_wav, "p", False, 0.6, model="M")
    except Exception:
        return False
    return s8_flag["routed"]


T.teeth("stage8 接线单点（s8tc.asr_backend 被断路后接线失守被测出）",
        lambda: setattr(s8tc, "asr_backend", _BrokenBackend()),
        lambda: setattr(s8tc, "asr_backend", asr_backend),
        _s8_probe)


def _fake_cut(source_wav, chunk, out_path):
    with open(out_path, "wb") as fh:
        fh.write(b"")
    return {"wav_path": out_path, "bytes": 1}


s8_engine_calls: list = []


def _s8_fake_engine(wav_path, prompt):
    """run_chunks 的 engine 桩：(wav, prompt) -> {text, segments}。"""
    s8_engine_calls.append({"wav": wav_path, "prompt": prompt})
    return {"text": "块", "segments": [{"start": 0.0, "end": 0.5,
                                        "text": "块"}]}


work_dir = os.path.join(TMP_ROOT, "s8work")
with patched(s8tc, "observe_vad_all", lambda p: {}), \
        patched(s8tc, "_cut_chunk_wav", _fake_cut), \
        patched(s8tc, "build_for_chunks",
                lambda ts: [{"initial_prompt": "p%d" % i, "token_count": 1}
                            for i, _ in enumerate(ts)]):
    out_chunks = s8tc.run_chunks(s7_wav, [("g", "t", "c")],
                                 work_dir=work_dir, engine=_s8_fake_engine)
T.ok(out_chunks["engine_calls"] == 1 and len(s8_engine_calls) == 1,
     "run_chunks（engine 桩路径）：每块一次引擎调用")
T.ok(out_chunks["monotonic"]["monotonic"] is True
     and out_chunks["merged"]["segments"],
     "run_chunks 合并后时间轴单调（check_monotonic 报告）")
T.ok(s8_engine_calls[0]["wav"].startswith(work_dir),
     "分块 wav 落在 work_dir（外置 tmp）")

print("[11b] run_chunks 真实路径（无桩引擎）：缺引擎 fail-closed，不降级")
with patched(s8tc, "observe_vad_all", lambda p: {}), \
        patched(s8tc, "_cut_chunk_wav", _fake_cut), \
        patched(s8tc, "build_for_chunks",
                lambda ts: [{"initial_prompt": "p", "token_count": 1}
                            for _ in ts]):
    try:
        s8tc.run_chunks(s7_wav, [("g", "t", "c")],
                        work_dir=os.path.join(TMP_ROOT, "s8real"))
        T.ok(False, "无引擎真机路径 → AsrBlock（本机无 ctranslate2）")
    except asr_backend.AsrBlock as exc:
        T.ok(exc.code in ("BLOCKED_CT2_IMPORT", "BLOCKED_GPU_UNAVAILABLE",
                          "BLOCKED_GPU_PROBE_FAILED",
                          "BLOCKED_MANIFEST_MISSING",
                          "BLOCKED_MODEL_REVISION_NOT_PINNED"),
             "fail-closed BLOCK（实测 code=%s）" % (exc.code,))

print("\n[11c] P2-1/P2-2：run 级 manifest/档位只解析一次，chunk 循环复用")
s8x_calls: list = []


def _s8x_recorder(wav_path, model=None, initial_prompt=None, language=None,
                  word_timestamps=False, no_speech_threshold=0.6, decode=None,
                  config=None, environ=None, _import=None):
    s8x_calls.append({"model": model, "config": config,
                      "prompt": initial_prompt})
    return {"text": "块", "segments": [], "info": {"language": "zh"},
            "monotonic": True}


s8x_manifest_calls: list = []


def _s8x_manifest():
    s8x_manifest_calls.append(1)
    return {"revision_match": True, "revision_resolved": "cafe"}


s8x_chunks = [
    {"index": 0, "start_s": 0.0, "end_s": 0.1,
     "core_start_s": 0.0, "core_end_s": 0.1},
    {"index": 1, "start_s": 0.1, "end_s": 0.2,
     "core_start_s": 0.1, "core_end_s": 0.2},
]
s8x_wav = make_wav("s8x.wav", seconds=0.2)
with patched(asr_backend, "resolve_runtime", lambda *a, **k: dict(CPU_CFG)), \
        patched(asr_backend, "load_model", lambda cfg=None, **k: "FAKE-MODEL"), \
        patched(asr_backend, "transcribe_file", _s8x_recorder), \
        patched(s8tc, "resolve_model_revision", _s8x_manifest), \
        patched(s8tc, "observe_vad_all", lambda p: {}), \
        patched(s8tc, "_cut_chunk_wav", _fake_cut), \
        patched(s8tc, "build_for_chunks",
                lambda ts: [{"initial_prompt": "p%d" % i, "token_count": 1}
                            for i, _ in enumerate(ts)]):
    s8x_out = s8tc.run_chunks(s8x_wav, [("g", "t", "c"), ("g", "t", "c")],
                              work_dir=os.path.join(TMP_ROOT, "s8x"),
                              chunks=s8x_chunks)
T.ok(len(s8x_calls) == 2 and s8x_out["engine_calls"] == 2,
     "两个 chunk 恰好两次引擎调用")
T.ok(len(s8x_manifest_calls) == 1,
     "run 级 manifest 校验恰好一次（实测 %d 次，不再每 chunk 重算）"
     % (len(s8x_manifest_calls),))
T.ok(all(c["config"] == dict(CPU_CFG) for c in s8x_calls)
     and s8x_calls[0]["config"] is s8x_calls[1]["config"],
     "每 chunk 透传同一 run 级档位 config（不再每 chunk resolve_runtime）")
T.ok(all(c["model"] == "FAKE-MODEL" for c in s8x_calls),
     "每 chunk 复用同一加载好的模型")


def _s8x_manifest_drift():
    return {"revision_match": False, "revision_resolved": "dead"}


with patched(asr_backend, "resolve_runtime", lambda *a, **k: dict(CPU_CFG)), \
        patched(asr_backend, "load_model", lambda cfg=None, **k: "FAKE-MODEL"), \
        patched(asr_backend, "transcribe_file", _s8x_recorder), \
        patched(s8tc, "resolve_model_revision", _s8x_manifest_drift), \
        patched(s8tc, "observe_vad_all", lambda p: {}), \
        patched(s8tc, "build_for_chunks",
                lambda ts: [{"initial_prompt": "p", "token_count": 1}
                            for _ in ts]):
    try:
        s8tc.run_chunks(s8x_wav, [("g", "t", "c")],
                        work_dir=os.path.join(TMP_ROOT, "s8x2"),
                        chunks=s8x_chunks[:1])
        T.ok(False, "run 级 revision 漂移 → ChunkTranscribeError")
    except s8tc.ChunkTranscribeError:
        T.ok(True, "run 级 revision 漂移 → ChunkTranscribeError")


def _s8x_per_chunk_call(wav_path, initial_prompt, word_timestamps,
                        no_speech_threshold, model=None, model_info=None,
                        config=None):
    """变异体：回退到旧的「每 chunk 现场解析 manifest」行为。"""
    s8tc.resolve_model_revision()  # 每 chunk 多算一次（旧 P2-1 行为）
    return ORIG["_call_engine_once"](
        wav_path, initial_prompt, word_timestamps, no_speech_threshold,
        model=model, model_info=model_info, config=config)


def _s8x_zero_manifest_calls() -> bool:
    s8x_calls.clear()
    s8x_manifest_calls.clear()
    try:
        with patched(asr_backend, "resolve_runtime",
                     lambda *a, **k: dict(CPU_CFG)), \
                patched(asr_backend, "load_model",
                        lambda cfg=None, **k: "FAKE-MODEL"), \
                patched(asr_backend, "transcribe_file", _s8x_recorder), \
                patched(s8tc, "resolve_model_revision", _s8x_manifest), \
                patched(s8tc, "observe_vad_all", lambda p: {}), \
                patched(s8tc, "_cut_chunk_wav", _fake_cut), \
                patched(s8tc, "build_for_chunks",
                        lambda ts: [{"initial_prompt": "p", "token_count": 1}
                                    for _ in ts]):
            s8tc.run_chunks(s8x_wav, [("g", "t", "c")],
                            work_dir=os.path.join(TMP_ROOT, "s8x3"),
                            chunks=s8x_chunks[:1])
    except Exception:
        return False
    return len(s8x_calls) == 1 and len(s8x_manifest_calls) == 1


T.teeth("run 级校验一次（_call_engine_once 回退每 chunk 重解析则测出）",
        lambda: setattr(s8tc, "_call_engine_once", _s8x_per_chunk_call),
        lambda: setattr(s8tc, "_call_engine_once",
                        ORIG["_call_engine_once"]),
        _s8x_zero_manifest_calls)

print("\n[11d] P1-1：_cut_chunk_wav 经 platform_win.run_ffmpeg 单点")
cut_calls: list = []


def _fake_run_ffmpeg(args, timeout=None, **kwargs):
    cut_calls.append({"args": list(args), "timeout": timeout})
    out_path = args[-1]
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 1600)
    return types.SimpleNamespace(returncode=0, stderr="")


cut_src = make_wav("cut_src.wav", seconds=0.2)
cut_out = os.path.join(TMP_ROOT, "cut_out.wav")
cut_chunk = {"index": 0, "start_s": 0.0, "end_s": 0.1,
             "core_start_s": 0.0, "core_end_s": 0.1}
with patched(platform_win, "run_ffmpeg", _fake_run_ffmpeg):
    cut_res = s8tc._cut_chunk_wav(cut_src, cut_chunk, cut_out)
T.ok(len(cut_calls) == 1 and cut_calls[0]["timeout"] == 600,
     "切分经 platform_win.run_ffmpeg 单点且超时 600 不变")
T.ok(cut_calls[0]["args"][0] == "-hide_banner"
     and cut_calls[0]["args"][-1] == cut_out,
     "ffmpeg 参数数组原样透传（不经 shell 拼串）")
T.ok(cut_res["bytes"] > 0, "切分产物经 check_wav_mono_16k 校验")


def _failing_run_ffmpeg(args, timeout=None, **kwargs):
    return types.SimpleNamespace(returncode=1, stderr="boom-bad-ffmpeg")


try:
    with patched(platform_win, "run_ffmpeg", _failing_run_ffmpeg):
        s8tc._cut_chunk_wav(cut_src, cut_chunk,
                            os.path.join(TMP_ROOT, "cut_bad.wav"))
    T.ok(False, "ffmpeg rc!=0 → ChunkTranscribeError（错误语义不变）")
except s8tc.ChunkTranscribeError as exc:
    T.ok("boom-bad-ffmpeg" in str(exc),
         "ffmpeg rc!=0 → ChunkTranscribeError 带 stderr（错误语义不变）")


def _cut_direct_subprocess(source_wav, chunk, out_path):
    """变异体：回退直调 subprocess（绕开 platform_win 单点，旧 P1-1 行为）。"""
    import subprocess  # noqa: PLC0415 (仅变异体使用)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i",
           source_wav, "-ss", str(chunk["start_s"]), "-to",
           str(chunk["end_s"]), "-ac", "1", "-ar", "16000",
           "-c:a", "pcm_s16le", out_path]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return {"wav_path": out_path, "bytes": 1}


def _cut_routes_via_platform_win() -> bool:
    """run_ffmpeg 桩没被碰到 = 切分没走单点 = 失败。"""
    cut_calls.clear()
    try:
        with patched(platform_win, "run_ffmpeg", _fake_run_ffmpeg):
            s8tc._cut_chunk_wav(cut_src, cut_chunk,
                                os.path.join(TMP_ROOT, "cut_out2.wav"))
    except Exception:
        return False
    return len(cut_calls) == 1


T.teeth("ffmpeg 单点（_cut_chunk_wav 回退直调 subprocess 绕开单点则测出）",
        lambda: setattr(s8tc, "_cut_chunk_wav", _cut_direct_subprocess),
        lambda: setattr(s8tc, "_cut_chunk_wav",
                        ORIG["_cut_chunk_wav_current"]),
        _cut_routes_via_platform_win)

print("\n[12] availability 预检：缺引擎 fail-closed")
avail = asr_backend.availability({})
T.ok(avail["ok"] is False and avail["code"] == "PRECHECK_ASR_BACKEND_NOT_READY",
     "本机无 faster-whisper/CT2 → 预检 BLOCK（code=%s）" % (avail["code"],))
T.ok("mlx" not in (avail["message"] or ""),
     "预检人话不再提 Mac 端那套引擎")

# =========================================================================
print("\n---- 结果 ----")
print("断言：%d 条，失败 %d 条" % (T.total, len(T.failed)))
print("反向证伪：%d 条，有牙 %d 条" % (T.teeth_total, T.teeth_sharp))
if T.failed:
    print("失败清单：")
    for item in T.failed:
        print("  - %s" % (item,))
    sys.exit(1)
print("SELFTEST PASS")
sys.exit(0)
