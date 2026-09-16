"""Windows 端 CT2 模型清单：来源 / revision / 许可 / SHA-256（供应链闸门）。

依据 ``docs/pm/WINDOWS-MIGRATION-PLAN.md`` §1、§5：联网机冻结 CT2
checkpoint 的 revision（**不可沿用 Mac 端 MLX 的 revision**），生成包含
来源/revision/许可/SHA-256 的 manifest；交付机加载前校验哈希并以绝对路径
加载，禁静默下载。

本模块只做**读取与校验**（生成为 ``tools/freeze_model_manifest.py`` 的事），
全部判定 fail-closed：不确定即 BLOCK，绝不「算了放行」。

人话约定：抛出的 message 面向用户，**不含本机绝对路径**（绝对/缓存路径只
进 ``detail`` 供人工排障），避免把目录结构泄漏到控制台/网页。
"""

from __future__ import annotations

import hashlib
import json
import ntpath
import os
import posixpath
import re

SCHEMA = "v2o-model-manifest/v1"
MANIFEST_BASENAME = "MODEL_MANIFEST.json"
MANIFEST_ENV = "V2O_MODEL_MANIFEST"
MANIFEST_FIELD_HELP = (
    "清单字段：source（来源 URL 或发布资产名）、revision（联网机冻结的 commit）"
    "、license（许可）、local_path（本机绝对路径）、files[{path,sha256,bytes}]"
)

# Mac（MLX）端旧标识与 revision：Windows 端一律不可沿用（§1「不可沿用 MLX
# revision」）。命中就是「复制粘贴没改」，必须 BLOCK 而不是放行。
BANNED_SOURCE_MARKERS = ("mlx-community",)
BANNED_REVISIONS = frozenset({"a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"})

REVISION_RE = re.compile(r"^[0-9a-f]{7,40}$")
PLACEHOLDER_RE = re.compile(r"^$|^replace|todo|fixme|placeholder", re.I)
_UNKNOWN_SOURCE_RE = re.compile(r"^(unknown|none|n/?a|null)$", re.I)
_UNKNOWN_LICENSE_RE = re.compile(r"^(unknown|none|n/?a|null)$", re.I)

# ---- 人话（无路径）-------------------------------------------------------
MSG_MANIFEST_MISSING = (
    "这台机器上还没有转写模型的登记信息（缺少模型清单），所以没有开始转写："
    "请先在能联网的机器上把 CT2 模型冻结好——下载模型本身、记录它的来源地址、"
    "冻结版本 revision、许可，并算出每个文件的 SHA-256 校验值，写进模型清单，"
    "然后把「模型 + 清单」一起拷到这台机器（本程序不会自动联网下载模型）。"
)
MSG_MANIFEST_INVALID = (
    "模型清单文件读不出来（不是合法的 JSON）：转写已停，不会带着一份看不懂的"
    "清单继续。请在能联网的机器上重新生成清单并拷到本机。"
)
MSG_MANIFEST_SCHEMA = (
    "模型清单的版本标记对不上（需要 %s）：转写已停。请按当前有效的清单格式重新"
    "生成后再拷到本机。" % (SCHEMA,)
)
MSG_NO_ENTRY = (
    "模型清单里没有这台机器要用的模型登记项：转写已停，不能用清单外的模型。"
    "请在能联网的机器上重新生成包含该模型的清单。"
)
MSG_REVISION_NOT_PINNED = (
    "模型清单里的版本 revision 还没冻结（是空的或占位文字）：Windows 端不能用"
    "「最新版」这种不确定版本，必须先冻结到某个 revision。请在能联网的机器上"
    "冻结版本后重新生成清单。"
)
MSG_MLX_REUSE = (
    "模型清单里写的还是 Mac 端的模型来源/版本号：Windows 端用的是另一套 "
    "CTranslate2 模型，两者不能混用（版本不可沿用）。请在能联网的机器上冻结"
    "CT2 模型版本后重新生成清单。"
)
MSG_SOURCE_MISSING = (
    "模型清单没写清模型来源（下载地址或发布资产名）：来源不明即停，不加载。"
    "请补全来源后重新生成清单。"
)
MSG_LICENSE_MISSING = (
    "模型清单没写清许可：许可不明即停，不加载。请补全许可后重新生成清单。"
)
MSG_PATH_NOT_ABSOLUTE = (
    "模型清单里的模型目录不是绝对路径：按规矩必须用绝对路径加载（防止把别的"
    "目录下的东西当模型），已停。请把清单里的路径改成本机绝对路径。"
)
MSG_FILES_MISSING = (
    "模型文件不全（清单登记的文件在本机找不到）：不残缺加载、不联网补文件，"
    "已停。请把完整的模型目录拷到本机。"
)
MSG_HASH_MISMATCH = (
    "模型文件的校验值对不上：文件内容与清单登记的 SHA-256 不一致（可能被替换"
    "或损坏），已停，绝不使用这个文件。请把冻结好的原始模型重新拷到本机。"
)
MSG_TOKENIZER_MISSING = (
    "模型目录里缺 tokenizer.json：分词器就在模型里，缺了就无法按 200 字预算"
    "装配提示词，已停。请确认模型目录完整。"
)


class ManifestBlock(RuntimeError):
    """模型供应链校验失败：调方必须 BLOCK 并把 ``message`` 原样给人看。"""

    def __init__(self, code: str, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.detail = dict(detail or {})


def repo_root() -> str:
    """``windows/`` 根（本文件在 ``<root>/src/asr_backend/`` 下）。"""
    here = os.path.dirname(os.path.abspath(__file__))          # src/asr_backend
    return os.path.dirname(os.path.dirname(here))              # windows/


def manifest_path(environ: dict | None = None) -> str:
    """清单路径：``V2O_MODEL_MANIFEST`` 优先，否则 ``<root>/models/清单``。"""
    env = os.environ if environ is None else environ
    override = str(env.get(MANIFEST_ENV) or "").strip()
    if override:
        return os.path.abspath(override)
    return os.path.join(repo_root(), "models", MANIFEST_BASENAME)


def load_manifest(path: str | None = None, environ: dict | None = None) -> dict:
    """读清单：缺文件/坏 JSON/版本标记不符，一律 BLOCK。"""
    target = path or manifest_path(environ)
    if not os.path.isfile(target):
        raise ManifestBlock("BLOCKED_MANIFEST_MISSING", MSG_MANIFEST_MISSING,
                            {"manifest": target})
    try:
        payload = json.loads(open(target, "r", encoding="utf-8").read())
    except (OSError, ValueError) as exc:
        raise ManifestBlock("BLOCKED_MANIFEST_INVALID", MSG_MANIFEST_INVALID,
                            {"error": "%s: %s" % (type(exc).__name__, exc)}) from exc
    if not isinstance(payload, dict):
        raise ManifestBlock("BLOCKED_MANIFEST_INVALID", MSG_MANIFEST_INVALID,
                            {"type": type(payload).__name__})
    schema = str(payload.get("schema") or "")
    if schema != SCHEMA:
        raise ManifestBlock("BLOCKED_MANIFEST_SCHEMA", MSG_MANIFEST_SCHEMA,
                            {"expected": SCHEMA, "got": schema})
    return payload


def pick_entry(manifest: dict, model_id: str | None = None) -> dict:
    """取一条模型登记：没给 model_id 时取第一条（Windows 端一套模型）。"""
    entries = manifest.get("models")
    if not isinstance(entries, list) or not entries:
        raise ManifestBlock("BLOCKED_MANIFEST_NO_ENTRY", MSG_NO_ENTRY, {})
    if model_id is None:
        entry = entries[0]
    else:
        entry = None
        for item in entries:
            if isinstance(item, dict) and str(item.get("model_id") or "") == model_id:
                entry = item
                break
        if entry is None:
            raise ManifestBlock("BLOCKED_MANIFEST_NO_ENTRY", MSG_NO_ENTRY,
                                {"model_id": str(model_id)})
    if not isinstance(entry, dict):
        raise ManifestBlock("BLOCKED_MANIFEST_NO_ENTRY", MSG_NO_ENTRY, {})
    return entry


def _is_abs(path: str) -> bool:
    return bool(path) and (ntpath.isabs(path) or posixpath.isabs(path))


def _sha256_file(path: str, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_entry(entry: dict, environ: dict | None = None) -> dict:
    """逐项校验一条登记：来源 / revision / 许可 / 绝对路径 / SHA-256。

    返回 ``{"ok", "verdict", "code", "message", "detail", ...}``。任何一项不
    确定就 ``ok=False``；``detail`` 里才有本机路径（给人看的是 message）。
    """
    if not isinstance(entry, dict):
        raise ManifestBlock("BLOCKED_MANIFEST_NO_ENTRY", MSG_NO_ENTRY, {})

    model_id = str(entry.get("model_id") or "").strip()
    source = str(entry.get("source") or "").strip()
    revision = str(entry.get("revision") or "").strip()
    license_ = str(entry.get("license") or "").strip()
    local_path = str(entry.get("local_path") or "").strip()
    files = entry.get("files")

    out = {
        "ok": False, "verdict": "BLOCK", "code": "BLOCKED_MODEL_UNKNOWN",
        "message": "", "detail": {},
        "model_id": model_id or None, "revision": revision or None,
        "source": source or None, "license": license_ or None,
        "local_path": local_path or None, "compute_type": None,
        "verified_files": [],
    }

    def _block(code: str, message: str, **detail) -> dict:
        out.update(ok=False, verdict="BLOCK", code=code, message=message)
        out["detail"] = dict(detail)
        return out

    if not model_id:
        return _block("BLOCKED_MANIFEST_NO_ENTRY", MSG_NO_ENTRY)
    low_id = model_id.lower()
    if any(mark in low_id for mark in BANNED_SOURCE_MARKERS) or revision in BANNED_REVISIONS:
        return _block("BLOCKED_MLX_REVISION_REUSED", MSG_MLX_REUSE,
                      model_id=model_id, revision=revision)
    if PLACEHOLDER_RE.match(revision) or not REVISION_RE.match(revision.lower()):
        return _block("BLOCKED_MODEL_REVISION_NOT_PINNED", MSG_REVISION_NOT_PINNED,
                      model_id=model_id, revision=revision)
    if not source or _UNKNOWN_SOURCE_RE.match(source):
        return _block("BLOCKED_MODEL_SOURCE_MISSING", MSG_SOURCE_MISSING,
                      model_id=model_id)
    if not license_ or _UNKNOWN_LICENSE_RE.match(license_):
        return _block("BLOCKED_MODEL_LICENSE_MISSING", MSG_LICENSE_MISSING,
                      model_id=model_id)
    if not _is_abs(local_path):
        return _block("BLOCKED_MODEL_PATH_NOT_ABSOLUTE", MSG_PATH_NOT_ABSOLUTE,
                      model_id=model_id)
    if not os.path.isdir(local_path):
        return _block("BLOCKED_MODEL_FILES_MISSING", MSG_FILES_MISSING,
                      model_id=model_id, revision=revision)
    if not isinstance(files, list) or not files:
        return _block("BLOCKED_MODEL_FILES_MISSING", MSG_FILES_MISSING,
                      model_id=model_id, revision=revision)

    verified = []
    for item in files:
        if not isinstance(item, dict):
            return _block("BLOCKED_MODEL_FILES_MISSING", MSG_FILES_MISSING,
                          model_id=model_id)
        rel = str(item.get("path") or "").strip()
        want = str(item.get("sha256") or "").strip().lower()
        if not rel or PLACEHOLDER_RE.match(want) or len(want) != 64:
            return _block("BLOCKED_MODEL_HASH_MISMATCH", MSG_HASH_MISMATCH,
                          model_id=model_id,
                          notable="清单里没写真实校验值")
        full = os.path.join(local_path, rel)
        if not os.path.isfile(full):
            return _block("BLOCKED_MODEL_FILES_MISSING", MSG_FILES_MISSING,
                          model_id=model_id, revision=revision)
        got = _sha256_file(full)
        if got != want:
            # 只回「对不上」，不回本机路径。
            return _block("BLOCKED_MODEL_HASH_MISMATCH", MSG_HASH_MISMATCH,
                          model_id=model_id, revision=revision)
        verified.append({"path": rel, "sha256": got, "bytes": os.path.getsize(full)})

    out.update(
        ok=True, verdict="OK", code=None, message="",
        verified_files=verified,
        compute_type=str(entry.get("compute_type") or "").strip() or None,
        local_path=os.path.abspath(local_path),
    )
    return out


def verify_model(model_id: str | None = None,
                 environ: dict | None = None) -> dict:
    """读清单 → 取登记 → 逐项校验，缺清单 Raise 之外全部落到 dict。"""
    manifest = load_manifest(environ=environ)
    return verify_entry(pick_entry(manifest, model_id), environ=environ)


def require_model(model_id: str | None = None,
                  environ: dict | None = None) -> dict:
    """校验通过才返回 dict，否则抛 :class:`ManifestBlock`（人话 + code）。"""
    result = verify_model(model_id, environ=environ)
    if not result["ok"]:
        raise ManifestBlock(result["code"], result["message"], result["detail"])
    return result
