#!/usr/bin/env python3
"""V2O 本地 Web 控制台（只读状态 + 后台启动 + 转写 worker）。

只用 stdlib（http.server / json / threading / urllib / os / sys）。
复用（只读 import，不改 src 任何文件）：
  - src/stage12/status_snapshot.collect：只读状态快照
  - src/stage5/startup.run_startup：后台线程启动监听
  - 转写 worker 内按需懒加载（无 hard 依赖，缺 mlx 时只记 verdict）：
    stage1.asr / stage7.transcribe / stage7.prompt_builder /
    stage8.transcribe_chunks / stage8.chunk_planner /
    stage1.prepare / stage3.normalize / stage3.render /
    stage3.lineage / stage4.publish / stage6.mirror / stage2.store

API：
  GET  /              -> index.html
  GET  /api/status?data_root=&limit= -> collect() 原样
  POST /api/start     -> 后台 run_startup（data_root/input_root/ob_vault_root），已在跑则 409
  GET  /api/start     -> 本进程监听状态（running/data_root/input_root/ob_vault_root/worker/error）
  GET  /api/browse?path= -> {path, parent, dirs[]}（只列目录，按名排序）
  POST /api/vocab/candidates/apply        -> 202 {job_id}（异步导入并按需重跑）
  GET  /api/vocab/candidates/apply/status -> 最近一次错词重跑进度（刷新可续看）

P0-5：默认 data_root 指向外置测试目录（/tmp 下，不写真实库）；
input_root 默认空，由用户在页面填写绝对路径后启动。
ob_vault_root 默认空：为空则 worker 只跑到 Render，不 Publish。
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(APP_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from stage12.status_snapshot import collect  # noqa: E402  (只读复用)
from stage5.startup import run_startup  # noqa: E402  (后台启动复用)

HOST = "127.0.0.1"
PORT = 8765

DEFAULT_DATA_ROOT = os.path.join(tempfile.gettempdir(), "v2o-console-data")
DEFAULT_PROFILE_HASH = "local-console-v1"

CODE_MLX_MISSING = "PRECHECK_MLX_MISSING"

_state_lock = threading.Lock()
_listener = {
    "running": False,
    "data_root": None,
    "input_root": None,
    "ob_vault_root": None,
    "error": None,
    "error_code": None,
    "suggested_data_root": None,
    "started_at": None,
    # V2.2补修 P0-1/P0-3：全终态放行计数+人话（绿条用，BLOCK时为0/空）
    "skipped_terminal": 0,
    "skipped_terminal_rows": 0,
    "startup_note": None,
}
# P0-3 后端记忆：内存记 last_config，前端 localStorage 为主、后端为辅
_last_config = {
    "last_input_root": None,
    "last_data_root": None,
    "last_ob_vault_root": None,
}
_handle = {"box": None}
_worker = {
    "running": False,
    "processed": [],  # 每项 {run_id, state, verdict, whisper_calls, ...}
    "last_error": None,
    "current": None,  # {run_id, filename, stage, stage_started_at} 或 None
}
_worker_done: set = set()

# 错词重跑异步任务状态：后端唯一真源（刷新页面可续看），只保留最近一次。
# 结构见 _handle_vocab_candidates_apply；None 表示本次进程还没跑过。
_vocab_apply_job: dict | None = None
_vocab_apply_seq = 0

# P0-2 阶段文案（中文动词，人话五步，禁标准化/渲染裸词）
STAGE_DISCOVER = "发现"
STAGE_TRANSCRIBING = "听写中"
STAGE_NORMALIZING = "整理中"
STAGE_RENDERING = "成稿中"
STAGE_PUBLISHING = "入库中"
DONE_STATES = ("PUBLISHED", "RENDER_ONLY")
FAIL_STATES = ("FAIL", "PUBLISH_BLOCKED")
# 步骤序号：发现1→听写中2→整理中3→成稿中4→入库中5
STAGE_STEP = {
    "发现": 1,
    "听写中": 2,
    "整理中": 3,
    "成稿中": 4,
    "入库中": 5,
}
STAGE_FLOW_LABEL = "发现→听写→整理→成稿→入库"
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".m4a", ".mp3", ".wav")


# ---------------------------------------------------------------- 路径归一

def normalize_path(raw) -> str:
    """粘贴自动去引号：strip 首尾空白后去一层配对首尾引号。

    苹果复制/访达拷贝常带 '...' 或 "..." 包裹；只去最外一层且首尾
    须为同种引号。非 str 输入一律归为空串。
    """
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    return text


def _mlx_available() -> bool:
    """probe import，不 hard 依赖：缺 mlx_whisper 时返回 False。"""
    try:
        __import__("mlx_whisper")
        return True
    except Exception:
        return False


def _is_under_root(src_path: str, input_root: str) -> bool:
    """P0-1：realpath 后按前缀判定源是否在当前 input_root 内。"""
    try:
        if not src_path or not input_root:
            return False
        src_real = os.path.realpath(src_path)
        input_real = os.path.realpath(input_root)
        return os.path.commonpath([input_real, src_real]) == input_real
    except (ValueError, OSError):
        return False


# ------------------------------------------- P0-1 启动门按目录隔离（V2.2）
#
# 根因：src/stage2/store.assert_stage3_tables_empty 是全局断言（任一
# Stage3+ 表有行即 AssertionError），而 app worker 成功转写一次就会写
# normalization_revisions / render_revisions / publish_records。于是换
# input_root（同 data_root）必被他 input 的历史行卡 STOP。
# 约束 src 零碰，故不在 src 落字，改在 app 启动前做运行时限定：
#   _install_scoped_gates(input_root) 把 store 上的两个断言替换为按
#   当前 input 过滤的版本（只查 sources.current_path 归属当前 input 的
#   行；他 input 的历史行不再计数），run_startup 返回后立即恢复原断言。
# 同目录重入（本目录自己的旧行挡住）仍按门规则失败，走人话引导 +
# 一键换新数据目录（_humanize_startup_error），如实二选一中的后者。
# fail-closed：过滤链上任何解不出的归属一律计为挡住，不静默放行。

_STARTUP_SCOPE = {"input_root": None, "skipped_terminal_rows": 0,
                  "skipped_terminal_runs": 0}
_ORIG_ASSERTS: dict = {}
NOTE_MAX_CHARS = 6000

# V2.2补修 P0-1：终态集合（全终态旧账放行，仅半截拦；未知状态fail-closed计拦）。
# src零碰，此处硬编码与src枚举对齐（normalize/render/publish_commit/commit）：
#   norm: PENDING/NORMALIZING/COMMITTING -> 半截；COMPLETED/FAILED_* -> 终态
#   rend: PUBLISH_EVALUATION/FAILED_* -> 终态，其余（含ARTIFACT_COMPLETED）半截
#   pub: PUBLISHED/BLOCKED_*/CANONICAL_OUTPUT_EXISTS/PENDING_PUBLISH -> 终态
#   arch: ARCHIVE_COMMITTED/ARCHIVED/COMMITTED -> 终态
#   art: COMMITTED -> 终态（PREPARED为半截）
_NORM_TERMINAL = frozenset({"COMPLETED", "FAILED_RETRYABLE",
                            "FAILED_FINAL", "FAILED"})
_REND_TERMINAL = frozenset({"PUBLISH_EVALUATION", "FAILED_RETRYABLE",
                            "FAILED_FINAL", "FAILED"})
_PUB_TERMINAL = frozenset({
    "PUBLISHED",
    "BLOCKED_OUTPUT_EXISTS", "BLOCKED_OUTPUT_CONFLICT",
    "BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM",
    "BLOCKED_UNSUPPORTED_ROOT_FOR_V1",
    "CANONICAL_OUTPUT_EXISTS", "PENDING_PUBLISH",
    "BLOCKED",
})
_ARCH_TERMINAL = frozenset({"ARCHIVE_COMMITTED", "ARCHIVED", "COMMITTED"})
_ART_TERMINAL = frozenset({"COMMITTED"})


def _is_norm_terminal(s) -> bool:
    try:
        t = str(s or "").strip()
    except Exception:
        return False
    if t in _NORM_TERMINAL:
        return True
    return t.startswith("FAILED")


def _is_rend_terminal(s) -> bool:
    try:
        t = str(s or "").strip()
    except Exception:
        return False
    if t in _REND_TERMINAL:
        return True
    return t.startswith("FAILED")


def _is_pub_terminal(s) -> bool:
    try:
        t = str(s or "").strip()
    except Exception:
        return False
    if t in _PUB_TERMINAL:
        return True
    return t.startswith("BLOCKED")


def _is_arch_terminal(s) -> bool:
    try:
        t = str(s or "").strip()
    except Exception:
        return False
    return t in _ARCH_TERMINAL


def _is_art_terminal(s) -> bool:
    try:
        t = str(s or "").strip()
    except Exception:
        return False
    return t in _ART_TERMINAL


def _db_success_run_ids_ro(data_root: str, input_root: str) -> set:
    """DB成功旧账run_id（norm COMPLETED归属当前input，只读fail-open）。

    P0-2缺口补齐：磁盘manifest缺失但DB已COMPLETED时仍跳过，不得重转
    （whisper不再跑）。失败/半截不在此集，走正常转写/重试。
    """
    try:
        con = _open_ro(str(data_root))
        if con is None:
            return set()
        try:
            scoped = _scoped_source_ids(con, str(input_root))
            if not scoped:
                return set()
            try:
                run2src = {r[0]: r[1] for r in con.execute(
                    "SELECT run_id, source_id FROM processing_runs").fetchall()}
            except Exception:
                return set()
            out: set = set()
            try:
                rows = con.execute(
                    "SELECT raw_artifact_id, status"
                    " FROM normalization_revisions").fetchall()
            except Exception:
                return set()
            for r in rows:
                try:
                    raw, st = r[0], (r[1] if len(r) > 1 else None)
                except Exception:
                    continue
                if str(st or "").strip() != "COMPLETED":
                    continue
                rid = None
                try:
                    if isinstance(raw, str) and raw.startswith("raw_"):
                        rid = raw[len("raw_"):]
                except Exception:
                    rid = None
                if not rid:
                    continue
                try:
                    if run2src.get(rid) in scoped:
                        out.add(rid)
                except Exception:
                    continue
            return out
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return set()


def _scoped_source_ids(con, input_root: str) -> set:
    """归属当前 input 的 source_id 全集（current_path 为主，path_identity_key 兜底）。"""
    out: set = set()
    try:
        rows = con.execute(
            "SELECT source_id, current_path, path_identity_key FROM sources"
        ).fetchall()
    except Exception:
        return out
    for r in rows:
        try:
            sid, cur, pik = r[0], r[1], r[2]
        except Exception:
            continue
        if (cur and _is_under_root(str(cur), input_root)) or (
            not cur and pik and _is_under_root(str(pik), input_root)
        ):
            out.add(sid)
    return out


def _unattributable_source_ids(con) -> set:
    """空归属 source_id 全集（current_path 与 path_identity_key 均空）。

    P1-1 fail-closed 补洞：空路径源的坏 run/Stage3 行此前被当他 input
    放行；空归属一律计挡住（门侧），清理侧同步可清（见 _handle_clear_post）。
    """
    out: set = set()
    try:
        rows = con.execute(
            "SELECT source_id, current_path, path_identity_key FROM sources"
        ).fetchall()
    except Exception:
        return out
    for r in rows:
        try:
            sid, cur, pik = r[0], r[1], r[2]
        except Exception:
            continue
        cur_s = str(cur).strip() if cur else ""
        pik_s = str(pik).strip() if pik else ""
        if not cur_s and not pik_s:
            out.add(sid)
    return out


def _scoped_assert_stage3_tables_empty(con):
    """按当前 input 过滤的 Stage3+ 半截断言（签名/异常文本与 src 原版一致）。

    V2.2补修 P0-1：只拦非终态半截行，全终态旧账放行。
      norm: 非COMPLETED/FAILED_* 才拦；rend: 非PUBLISH_EVALUATION/FAILED_* 才拦；
      pub: 非PUBLISHED/BLOCKED_*/终态才拦；art: 非COMMITTED才拦；
      arch: 非ARCHIVE_COMMITTED/ARCHIVED/COMMITTED才拦。
    终态旧行计入 _STARTUP_SCOPE skipped（verdict 注明“旧X条已完成记录，本次跳过”，
    fail-closed：归属解不出/状态未知一律计拦，不静默放行）。
    """
    orig = _ORIG_ASSERTS.get("stage3")
    scope_root = _STARTUP_SCOPE.get("input_root")
    if not scope_root or orig is None:
        from stage2 import store as _st  # noqa: E402  (读原断言，src 文件不动)

        return _st.assert_stage3_tables_empty(con)
    try:
        scoped = _scoped_source_ids(con, scope_root)
        unatt = _unattributable_source_ids(con)
        run2src = {
            r[0]: r[1]
            for r in con.execute(
                "SELECT run_id, source_id FROM processing_runs"
            ).fetchall()
        }

        def _blocked_run(rid) -> bool:
            # 归属当前 input，或归属解不出（fail-closed 计挡住）；
            # P1-1：空归属源一律计挡住，不当他 input 放行。
            if not rid:
                return True
            src = run2src.get(rid)
            if src is None:
                return True
            if src in unatt:
                return True
            return src in scoped

        def _run_of_raw(raw) -> str | None:
            if isinstance(raw, str) and raw.startswith("raw_"):
                return raw[len("raw_"):]
            return None

        try:
            _norm_rows = con.execute(
                "SELECT normalized_artifact_id, raw_artifact_id, status"
                " FROM normalization_revisions"
            ).fetchall()
        except Exception:
            _norm_rows = []
        norm_map = {}
        for _nr in _norm_rows:
            try:
                norm_map[_nr[0]] = _nr[1]
            except Exception:
                continue
        try:
            _rend_rows = con.execute(
                "SELECT render_revision_id, normalized_artifact_id, status"
                " FROM render_revisions"
            ).fetchall()
        except Exception:
            _rend_rows = []
        rend_map = {}
        for _rr in _rend_rows:
            try:
                rend_map[_rr[0]] = _rr[1]
            except Exception:
                continue
        try:
            _pub_rows = con.execute(
                "SELECT render_revision_id, status FROM publish_records"
            ).fetchall()
        except Exception:
            _pub_rows = []
        try:
            _arch_rows = con.execute(
                "SELECT source_id, status FROM archive_commits"
            ).fetchall()
        except Exception:
            _arch_rows = []
        try:
            _art_rows = con.execute(
                "SELECT source_id, run_id, status FROM artifacts"
            ).fetchall()
        except Exception:
            _art_rows = []
        counts = {}
        skipped_rows = 0
        skipped_runs: set = set()
        # norm：仅非终态计拦
        n_norm = 0
        for _nr in _norm_rows:
            try:
                _raw = _nr[1] if len(_nr) > 1 else None
                _stt = _nr[2] if len(_nr) > 2 else None
            except Exception:
                continue
            _rid = _run_of_raw(_raw)
            if not _blocked_run(_rid):
                continue
            if _is_norm_terminal(_stt):
                skipped_rows += 1
                if _rid:
                    skipped_runs.add(_rid)
                continue
            n_norm += 1
        counts["normalization_revisions"] = n_norm
        # rend：仅非终态计拦
        n_rend = 0
        for _rr in _rend_rows:
            try:
                _nart = _rr[1] if len(_rr) > 1 else None
                _stt = _rr[2] if len(_rr) > 2 else None
            except Exception:
                continue
            _rid = _run_of_raw(norm_map.get(_nart))
            if not _blocked_run(_rid):
                continue
            if _is_rend_terminal(_stt):
                skipped_rows += 1
                if _rid:
                    skipped_runs.add(_rid)
                continue
            n_rend += 1
        counts["render_revisions"] = n_rend
        # pub：仅非终态计拦
        n_pub = 0
        for _pr in _pub_rows:
            try:
                _rendid = _pr[0]
                _stt = _pr[1] if len(_pr) > 1 else None
            except Exception:
                continue
            _rid = _run_of_raw(norm_map.get(rend_map.get(_rendid)))
            if not _blocked_run(_rid):
                continue
            if _is_pub_terminal(_stt):
                skipped_rows += 1
                if _rid:
                    skipped_runs.add(_rid)
                continue
            n_pub += 1
        counts["publish_records"] = n_pub
        # arch：仅非终态计拦（source 级归属）
        n_arch = 0
        for _ar in _arch_rows:
            try:
                _sid = _ar[0]
                _stt = _ar[1] if len(_ar) > 1 else None
            except Exception:
                continue
            if not (_sid is None or _sid in scoped or _sid in unatt):
                continue
            if _is_arch_terminal(_stt):
                skipped_rows += 1
                continue
            n_arch += 1
        counts["archive_commits"] = n_arch
        # art：仅非COMMITTED计拦（新增门：PREPARED半截拦，COMMITTED放行）
        n_art = 0
        for _ar2 in _art_rows:
            try:
                _sid2 = _ar2[0] if len(_ar2) > 0 else None
                _rid2 = _ar2[1] if len(_ar2) > 1 else None
                _stt2 = _ar2[2] if len(_ar2) > 2 else None
            except Exception:
                continue
            _in_scope = False
            try:
                if _sid2 is None and _rid2 is None:
                    _in_scope = True  # 归属解不出 fail-closed 计拦
                elif _sid2 in scoped or _sid2 in unatt:
                    _in_scope = True
                elif _rid2 and _blocked_run(_rid2):
                    _in_scope = True
            except Exception:
                _in_scope = True
            if not _in_scope:
                continue
            if _is_art_terminal(_stt2):
                skipped_rows += 1
                if _rid2:
                    skipped_runs.add(str(_rid2))
                continue
            n_art += 1
        if n_art:
            counts["artifacts"] = n_art
        try:
            _STARTUP_SCOPE["skipped_terminal_rows"] = int(skipped_rows)
            _STARTUP_SCOPE["skipped_terminal_runs"] = int(len(skipped_runs))
        except Exception:
            pass
        nonzero = {t: c for t, c in counts.items() if c != 0}
        if nonzero:
            raise AssertionError(
                "Stage3+ table not empty (STOP EXPANSION): %r" % (nonzero,)
            )
        return counts
    except AssertionError:
        raise
    except Exception:
        # 过滤链异常则回原断言（fail-closed，不静默放行）
        return orig(con)


def _scoped_assert_no_transcription_states(con):
    """按当前 input 过滤的 run 状态断言（只查归属当前 input 的 run）。"""
    orig = _ORIG_ASSERTS.get("runstates")
    scope_root = _STARTUP_SCOPE.get("input_root")
    if not scope_root or orig is None:
        from stage2 import store as _st  # noqa: E402  (读原断言，src 文件不动)

        return _st.assert_no_transcription_states(con)
    try:
        from stage2 import store as _st  # noqa: E402  (只读允许集合)

        allowed = set(_st.ALLOWED_RUN_STATUSES)
        scoped = _scoped_source_ids(con, scope_root)
        unatt = _unattributable_source_ids(con)
        try:
            all_srcs = {
                r[0]
                for r in con.execute("SELECT source_id FROM sources").fetchall()
            }
        except Exception:
            all_srcs = set(scoped)
        hist: dict = {}
        for r in con.execute(
            "SELECT status, source_id FROM processing_runs"
        ).fetchall():
            st, sid = r[0], r[1]
            if sid in scoped or sid is None or sid not in all_srcs or sid in unatt:
                hist[st] = hist.get(st, 0) + 1
        bad = {s: c for s, c in hist.items() if s not in allowed}
        if bad:
            raise AssertionError(
                "Run in transcription-stage status (STOP EXPANSION): %r"
                % (bad,)
            )
        return hist
    except AssertionError:
        raise
    except Exception:
        return orig(con)


def _install_scoped_gates(input_root: str) -> None:
    """启动前安装作用域断言（保存原函数，run_startup 后必须恢复）。"""
    from stage2 import store as _st  # noqa: E402  (运行时限定，src 文件不动)

    if "stage3" not in _ORIG_ASSERTS:
        _ORIG_ASSERTS["stage3"] = _st.assert_stage3_tables_empty
    if "runstates" not in _ORIG_ASSERTS:
        _ORIG_ASSERTS["runstates"] = _st.assert_no_transcription_states
    _STARTUP_SCOPE["input_root"] = input_root
    # V2.2补修：每轮清零旧账计数，避免上轮残留进绿条
    try:
        _STARTUP_SCOPE["skipped_terminal_rows"] = 0
        _STARTUP_SCOPE["skipped_terminal_runs"] = 0
    except Exception:
        pass
    _st.assert_stage3_tables_empty = _scoped_assert_stage3_tables_empty
    _st.assert_no_transcription_states = _scoped_assert_no_transcription_states


def _restore_scoped_gates() -> None:
    """恢复 src 原断言并清空作用域（finally 必调）。"""
    try:
        from stage2 import store as _st  # noqa: E402

        if "stage3" in _ORIG_ASSERTS:
            _st.assert_stage3_tables_empty = _ORIG_ASSERTS["stage3"]
        if "runstates" in _ORIG_ASSERTS:
            _st.assert_no_transcription_states = _ORIG_ASSERTS["runstates"]
    except Exception:
        pass
    _STARTUP_SCOPE["input_root"] = None


def _suggest_data_root(data_root: str) -> str:
    """按时间戳给新数据目录建议路径（只给路径，不建目录）。"""
    import datetime

    base = os.path.abspath(str(data_root or DEFAULT_DATA_ROOT)).rstrip(os.sep)
    stamp = (
        datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    )
    cand = "%s-%s" % (base, stamp)
    i = 2
    while os.path.exists(cand):
        cand = "%s-%s-%d" % (base, stamp, i)
        i += 1
    return cand


def _humanize_startup_error(exc: Exception, data_root: str) -> tuple:
    """启动门失败转人话：返回 (message, code, suggested_data_root)。"""
    text = str(exc)
    if "Stage3+ table not empty" in text:
        return (
            "本目录在这个数据目录下已有转写记录，按规则不能重复启动→"
            "点「一键换新数据目录」换个干净目录重起（源视频文件与笔记不动）：%s" % (text,),
            "GATE_STAGE3_BLOCKED",
            _suggest_data_root(data_root),
        )
    if "transcription-stage status" in text:
        return (
            "本目录在这个数据目录下有未收口的任务状态，按规则不能启动→"
            "点「一键换新数据目录」换个干净目录重起（源视频文件与笔记不动）：%s" % (text,),
            "GATE_RUN_STATE_BLOCKED",
            _suggest_data_root(data_root),
        )
    return ("启动监听失败：%s，请检查路径后重试" % (exc,), None, None)


def _jobs_dir(data_root: str) -> str:
    return os.path.join(os.path.abspath(str(data_root or "")), "data", "jobs")


def _scan_disk_states(data_root: str) -> dict:
    """P1-2：读磁盘 jobs/*/manifest.json 得已完成终态（重启不丢）。

    成功=末个 RENDER_ONLY/PUBLISHED 且输出文件仍存在；
    失败=末个 TRANSCRIBE_FAILED/RAW_FAILED/MIRROR_FAILED/NORM_RENDER_FAILED/
    PUBLISH_BLOCKED（含 FAIL 语义）。只读，不落盘。
    返回 {run_id: {state, verdict, rendered_path, canonical_output_path}}。
    """
    out: dict = {}
    try:
        jd = _jobs_dir(data_root)
        if not os.path.isdir(jd):
            return out
        try:
            names = os.listdir(jd)
        except OSError:
            return out
        for run_id in names:
            mp = os.path.join(jd, run_id, "manifest.json")
            if not os.path.isfile(mp):
                continue
            try:
                with open(mp, "r", encoding="utf-8") as fh:
                    mani = json.load(fh)
                receipts = mani.get("receipts") or []
                if not isinstance(receipts, list) or not receipts:
                    continue
                last = None
                for r in reversed(receipts):
                    if isinstance(r, dict) and r.get("state"):
                        last = r
                        break
                if not last:
                    continue
                st = str(last.get("state") or "")
                verdict = str(last.get("verdict") or "")
                rp = last.get("rendered_path")
                cp = last.get("canonical_output_path")
                if st in ("RENDER_ONLY", "PUBLISHED"):
                    # 输出存在性校验：不存在则不算完成，需重跑
                    cand = cp if st == "PUBLISHED" else rp
                    if isinstance(cand, str) and cand and os.path.isfile(cand):
                        out[run_id] = {"state": st, "verdict": verdict,
                                       "rendered_path": rp,
                                       "canonical_output_path": cp}
                    elif isinstance(cand, str) and cand:
                        # 路径记了但文件没了：不算完成
                        continue
                    else:
                        # 无路径记录（如旧数据）：按完成计，前端显示—由调用方处理
                        out[run_id] = {"state": st, "verdict": verdict,
                                       "rendered_path": rp,
                                       "canonical_output_path": cp}
                elif st in ("PUBLISH_BLOCKED", "TRANSCRIBE_FAILED", "RAW_FAILED",
                            "MIRROR_FAILED", "NORM_RENDER_FAILED"):
                    mapped = "PUBLISH_BLOCKED" if st == "PUBLISH_BLOCKED" else "FAIL"
                    out[run_id] = {"state": mapped, "verdict": verdict,
                                   "rendered_path": rp,
                                   "canonical_output_path": cp}
            except Exception:
                continue
    except Exception:
        return out
    return out


def _is_vault_registered(vault_root) -> bool:
    """V2.3 P0-2：vault注册检测（ob_vault_root/.obsidian是否为目录）。

    未配置/空/不可读一律 False（fail-closed，前端禁用OB按钮）。
    只读判定，不落盘。
    """
    try:
        if not vault_root or not isinstance(vault_root, str):
            return False
        if not vault_root.strip():
            return False
        obs = os.path.join(os.path.abspath(vault_root), ".obsidian")
        return os.path.isdir(obs)
    except Exception:
        return False


def _app_resolve_canonical(input_root: str, vault_root: str,
                           src_abs: str) -> dict:
    """V2.3 P0-3：app侧单扩展名包装（src零碰，只改app）。

    底座 src/stage6.mirror.resolve_canonical 只读复用，不改src文件。
    期望：09.xxx.mp4→09.xxx.md（去源扩展名再加.md，保留点号前缀），
    杜绝 09.xxx.mp4.md 双扩展名。做法：先调底座，再以
    splitext(basename)[0]+".md" 为期望名校对；不一致则保持子目录、
    仅替换文件名为单扩展名。只影响新产出：从不改名/移动已产出旧md。
    """
    from stage6.mirror import resolve_canonical as _base  # noqa: E402 只读复用
    m = _base(os.path.abspath(input_root), os.path.abspath(vault_root),
              os.path.abspath(src_abs))
    try:
        base = os.path.basename(os.path.abspath(src_abs))
        stem, _ext = os.path.splitext(base)
        if not stem:
            stem = base
        exp_name = stem + ".md"
        canon = str(m.get("canonical_output_path") or "")
        out = dict(m)
        if canon and os.path.basename(canon) != exp_name:
            out["canonical_output_path"] = os.path.join(
                os.path.dirname(canon), exp_name)
            out["app_single_ext_fixed"] = True
        else:
            out["app_single_ext_fixed"] = False
        out["app_expected_name"] = exp_name
        return out
    except Exception:
        return m


def _dir_tail(path: str) -> str:
    """目录尾段（“…”＋末段；根/空回“”）：供列表归属显示。"""
    try:
        p = str(path or "").rstrip("/")
        if not p:
            return ""
        base = os.path.basename(p)
        if not base:
            return "/"
        return "…/" + base
    except Exception:
        return ""


def _attach_source_filenames(snap: dict, data_root: str) -> dict:
    """V2.3 P0-1 / UX2-P1-5/P1-7：recent_runs附source_filename＋目录归属。

    联 sources 取 current_path：basename→source_filename，
    dirname→source_dir／source_dir_tail（“…/尾段”，列表归属与来源列用）。
    取不到（映射缺失/空路径）回“未知文件”。只读，不落盘。
    """
    try:
        runs = snap.get("recent_runs") if isinstance(snap, dict) else None
        if not isinstance(runs, list):
            return snap
        mapping = _run_source_path_map(data_root)
        for r in runs:
            try:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("run_id") or "")
                src_path = mapping.get(rid) if mapping else None
                if isinstance(src_path, str) and src_path.strip():
                    sp = src_path.strip()
                    d = os.path.dirname(sp)
                    r["source_path"] = sp
                    r["source_dir"] = d
                    r["source_dir_tail"] = _dir_tail(d)
                    r["source_filename"] = os.path.basename(sp) or "未知文件"
                else:
                    r["source_path"] = None
                    r["source_dir"] = None
                    r["source_dir_tail"] = ""
                    r["source_filename"] = "未知文件"
            except Exception:
                try:
                    if isinstance(r, dict) and "source_filename" not in r:
                        r["source_filename"] = "未知文件"
                except Exception:
                    pass
    except Exception:
        pass
    return snap


def _preview_mapping(input_root: str, vault_root: str | None) -> str:
    """UX-P0-3/V2.3 P0-3：用app侧单扩展名包装做映射预览，不落盘。"""
    try:
        if not input_root:
            return ""
        if not vault_root:
            return ""
        demo = os.path.join(os.path.abspath(input_root), "示例视频.mp4")
        m = _app_resolve_canonical(os.path.abspath(input_root),
                                   os.path.abspath(vault_root), demo)
        canon = str(m.get("canonical_output_path") or "")
        # 只展示库内相对部分，避免绝对路径过长
        try:
            rel = os.path.relpath(canon, os.path.abspath(vault_root))
        except Exception:
            rel = os.path.basename(canon) or "示例视频.md"
        return "视频 示例视频.mp4 → 库内 %s 式样" % (rel,)
    except Exception:
        return ""


def _count_videos_in_dir(dirpath: str) -> dict:
    """UX-P1-4/P1-5：单层只读统计视频数与长视频估算（>500MB 估算注明）。"""
    try:
        names = os.listdir(dirpath)
    except Exception:
        return {"total": 0, "sample": [], "long_estimate": 0}
    total = 0
    sample: list = []
    long_n = 0
    for nm in sorted(names)[:1000]:
        fp = os.path.join(dirpath, nm)
        try:
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(nm)[1].lower()
            if ext in VIDEO_EXTS:
                total += 1
                if len(sample) < 3:
                    sample.append(nm)
                try:
                    if os.path.getsize(fp) > 500 * 1024 * 1024:
                        long_n += 1
                except OSError:
                    pass
        except Exception:
            continue
    return {"total": total, "sample": sample, "long_estimate": long_n}


def _worker_set_current(run_id: str, filename: str, stage: str) -> None:
    with _state_lock:
        _worker["current"] = {
            "run_id": run_id,
            "filename": filename,
            "stage": stage,
            "stage_started_at": _utc_now_iso(),
        }


def _worker_clear_current() -> None:
    with _state_lock:
        _worker["current"] = None


def _count_pending_in_root(data_root: str, input_root: str,
                           exclude: set | None = None) -> int:
    """P0-2 pending=当前input下尚未处理的QUEUED数。

    realpath前缀过滤 + 排除本轮已处理（_worker_done），否则 DB 状态
    保持 QUEUED（P0-4 架构约束）会导致进度条永不到 100%。
    fail-open 记 0。
    """
    try:
        from stage2 import store as _store  # noqa: E402  (只读复用 open_db)
        con = _store.open_db(data_root)
        try:
            rows = con.execute(
                "SELECT pr.run_id, s.current_path FROM processing_runs pr"
                " LEFT JOIN sources s ON pr.source_id=s.source_id"
                " WHERE pr.status='QUEUED' AND pr.creation_mode='AUTO'"
            ).fetchall()
        finally:
            try:
                con.close()
            except Exception:
                pass
        excl = exclude or set()
        n = 0
        for r in rows:
            try:
                rid = r[0]
                cur = r[1] if len(r) > 1 else None
            except Exception:
                continue
            if rid in excl:
                continue
            if cur and _is_under_root(str(cur), input_root):
                n += 1
            elif cur is None:
                # 孤儿 run 交给 worker 记 FAIL，计入 pending 以便可见
                n += 1
        return n
    except Exception:
        return 0


def _listener_snapshot() -> dict:
    with _state_lock:
        snap = dict(_listener)
        try:
            _lc = dict(_last_config)
        except Exception:
            _lc = {}
    # P0-3 回显 last_*：内存为主，当前态兜底（升级前无记忆时仍有值）
    try:
        snap["last_input_root"] = _lc.get("last_input_root") or snap.get("input_root")
        snap["last_data_root"] = _lc.get("last_data_root") or snap.get("data_root")
        snap["last_ob_vault_root"] = _lc.get("last_ob_vault_root") or snap.get("ob_vault_root")
    except Exception:
        pass
    with _state_lock:
        current = dict(_worker["current"]) if _worker["current"] else None
        processed = list(_worker["processed"][-20:])
        mem_all = list(_worker["processed"])
        running = _worker["running"]
        last_error = _worker["last_error"]
    with _state_lock:
        done_ids = set(_worker_done)
    data_root = snap.get("data_root")
    input_root = snap.get("input_root")
    vault_root = snap.get("ob_vault_root")
    # P1-2：磁盘终态合并内存，重启不归零
    disk_states: dict = {}
    try:
        if data_root:
            disk_states = _scan_disk_states(str(data_root))
    except Exception:
        disk_states = {}
    merged: dict = dict(disk_states)
    for p in mem_all:
        try:
            if isinstance(p, dict) and p.get("run_id"):
                rid = str(p.get("run_id"))
                # 内存最新覆盖磁盘（重试后以内存为准）
                merged[rid] = p
        except Exception:
            continue
    # P0-2：监听态下终态按当前 input_root 过滤（他目录历史不再混入计数）
    try:
        if snap.get("running") and input_root:
            mem_ids = set()
            for p in mem_all:
                try:
                    if isinstance(p, dict) and p.get("run_id"):
                        mem_ids.add(str(p.get("run_id")))
                except Exception:
                    continue
            merged = _filter_merged_by_input(merged, mem_ids, str(data_root),
                                             str(input_root))
    except Exception:
        pass
    done_n = sum(1 for v in merged.values()
                 if isinstance(v, dict) and v.get("state") in DONE_STATES)
    failed_n = sum(1 for v in merged.values()
                   if isinstance(v, dict) and v.get("state") in FAIL_STATES)
    # 干掉 SKIP：SKIP 不进 merged（_worker_record 从不记 SKIP，磁盘也不记）
    total = 0
    pending = 0
    if snap.get("running") and data_root and input_root:
        exclude = set(done_ids) | set(merged.keys())
        pending = _count_pending_in_root(str(data_root), str(input_root),
                                         exclude=exclude)
        total = pending + done_n + failed_n
    else:
        # 未监听时 total 仍给已完成数，供重起不归零展示
        total = done_n + failed_n
    # 全量细节供行级映射（≤100+磁盘，防 20 窗口丢失）
    # P1-2：附后端渲染的 finder_url（file:// 全编码），前端直接用，不再手拼
    # file://（#/? 手拼必断）。
    # V2.3 P0-1：details附source_filename（内存优先，磁盘缺失联sources取basename）。
    _fn_map: dict = {}
    try:
        if data_root:
            _fn_map = _run_source_path_map(str(data_root))
    except Exception:
        _fn_map = {}
    details: dict = {}
    try:
        for rid, v in merged.items():
            if isinstance(v, dict):
                _st = v.get("state")
                _rp = v.get("rendered_path")
                _cp = v.get("canonical_output_path")
                _disp = None
                try:
                    if _st == "PUBLISHED" and isinstance(_cp, str) and _cp:
                        _disp = _cp
                    elif isinstance(_rp, str) and _rp:
                        _disp = _rp
                    elif isinstance(_cp, str) and _cp:
                        _disp = _cp
                except Exception:
                    _disp = None
                _furl = None
                try:
                    if isinstance(_disp, str) and _disp:
                        _furl = _finder_url(_disp)
                except Exception:
                    _furl = None
                _fn = v.get("source_filename")
                try:
                    if (not isinstance(_fn, str) or not _fn.strip()) and _fn_map:
                        _sp = _fn_map.get(rid)
                        if isinstance(_sp, str) and _sp.strip():
                            _fn = os.path.basename(_sp.strip()) or "未知文件"
                        else:
                            _fn = "未知文件"
                    if not isinstance(_fn, str) or not _fn.strip():
                        _fn = "未知文件"
                except Exception:
                    _fn = "未知文件"
                details[rid] = {
                    "state": v.get("state"),
                    "verdict": v.get("verdict"),
                    "rendered_path": v.get("rendered_path"),
                    "canonical_output_path": v.get("canonical_output_path"),
                    "whisper_calls": v.get("whisper_calls"),
                    "finder_url": _furl,
                    "source_filename": _fn,
                }
    except Exception:
        details = {}
    preview = ""
    try:
        if snap.get("running") and input_root:
            preview = _preview_mapping(str(input_root),
                                       str(vault_root) if vault_root else None)
    except Exception:
        preview = ""
    worker = {"running": running,
              "processed_n": done_n + failed_n,
              "processed": processed,
              "details_by_run": details,
              "last_error": last_error,
              "current": current,
              "preview": preview,
              "queue": {"pending": pending, "done": done_n,
                        "failed": failed_n, "total": total}}
    snap["worker"] = worker
    # V2.3 P0-2：回显vault注册布尔（未配/无.obsidian均为False）
    try:
        snap["vault_registered"] = _is_vault_registered(
            snap.get("ob_vault_root"))
    except Exception:
        snap["vault_registered"] = False
    # UX2-P2-3：回显默认数据目录（前端空框常驻小字用）
    snap["default_data_root"] = DEFAULT_DATA_ROOT
    return snap


def _send_json(handler: BaseHTTPRequestHandler, code: int, obj: dict) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _serve_index(handler: BaseHTTPRequestHandler) -> None:
    path = os.path.join(APP_DIR, "index.html")
    try:
        with open(path, "rb") as fh:
            body = fh.read()
    except OSError as exc:
        _send_json(handler, 500, {"ok": False, "error": "index.html missing: %s" % (exc,)})
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _open_ro(data_root: str):
    """只读打开中央库（不经锁门 diagnosis 用；失败回 None，fail-open）。"""
    try:
        from urllib.parse import quote as _quote

        from stage2.store import central_db_path as _addr  # noqa: E402 只读复用

        db_path = _addr(os.path.abspath(str(data_root or "")))
    except Exception:
        try:
            db_path = os.path.join(
                os.path.abspath(str(data_root or "")), "data", "state.db"
            )
        except Exception:
            return None
    try:
        if not os.path.isfile(db_path):
            return None
        uri = "file:%s?mode=ro" % _quote(os.path.abspath(db_path))
        con = sqlite3.connect(uri, uri=True, timeout=30.0,
                              check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        return None


def _run_source_path_map(data_root: str) -> dict:
    """{run_id: current_path}（只读；sources 缺失/不可读回空，fail-open）。"""
    con = _open_ro(data_root)
    if con is None:
        return {}
    try:
        rows = con.execute(
            "SELECT pr.run_id, s.current_path, s.path_identity_key"
            " FROM processing_runs pr LEFT JOIN sources s"
            " ON pr.source_id=s.source_id"
        ).fetchall()
        out = {}
        for r in rows:
            try:
                out[str(r[0])] = r[1] or r[2]
            except Exception:
                continue
        return out
    except Exception:
        return {}
    finally:
        try:
            con.close()
        except Exception:
            pass


def _filter_status_runs(snap: dict, data_root: str, input_root: str) -> dict:
    """P0-2：recent_runs 只留归属当前 input 的行（孤儿 run 可见，fail-open）。"""
    try:
        runs = snap.get("recent_runs") or []
        mapping = _run_source_path_map(data_root)
        if not mapping:
            snap["input_root"] = input_root
            snap["filtered"] = False
            return snap
        kept = []
        for r in runs:
            try:
                rid = str(r.get("run_id"))
            except Exception:
                continue
            if rid not in mapping:
                kept.append(r)  # 映射缺失时可见，不静默丢
                continue
            if _is_under_root(str(mapping[rid] or ""), input_root):
                kept.append(r)
        snap["recent_runs"] = kept
        snap["input_root"] = input_root
        snap["filtered"] = True
        return snap
    except Exception:
        try:
            snap["filtered"] = False
        except Exception:
            pass
        return snap


def _filter_merged_by_input(merged: dict, mem_ids: set, data_root: str,
                            input_root: str) -> dict:
    """P0-2：worker 终态按当前 input 过滤（磁盘孤儿排除，内存孤儿保留）。"""
    try:
        mapping = _run_source_path_map(data_root)
        if not mapping:
            return merged
        out = {}
        for rid, v in merged.items():
            if rid in mapping:
                if _is_under_root(str(mapping[rid] or ""), input_root):
                    out[rid] = v
            elif rid in mem_ids:
                out[rid] = v  # 本 session 内存真相保留
        return out
    except Exception:
        return merged


def _count_job_dirs(data_root: str, run_ids) -> int:
    """本 data_root 下 jobs/<run_id> 目录计数（清空代价预览用，只读）。"""
    try:
        base = _jobs_dir(data_root)
        n = 0
        for rid in run_ids:
            try:
                if os.path.isdir(os.path.join(base, str(rid))):
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


CLEAR_AVG_SEC_PER_VIDEO = 120  # 清空代价估算：每条视频重转均耗时（秒，估算值）


def _est_retranscribe_minutes(n_runs) -> int:
    """按条数估重转分钟（ceil；估算值，前端明示“约”）。"""
    try:
        n = int(n_runs or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return 0
    return int((n * CLEAR_AVG_SEC_PER_VIDEO + 59) // 60)


def _clear_plan(con, data_root: str, input_root: str,
                only_failed: bool = False) -> dict:
    """UX2-P0-2：只读计算清空计划（不写库、不删盘），预览与实清共用。

    返回 exists=False 表示本目录无任何可清记录；否则给出去重后的待删 id：
      run_ids / srcs_to_del / cand_ids / norm_ids / rend_ids / pub_ids /
      art_ids / null_arch_ids / entity_ids，以及
      total/success/failed/pending/fail_run_ids/kept_success 计数。
    only_failed=True 时只圈失败 run 及其修订链；同日录源若另有成功 run，
    该源保留（成功记录与产物不动）。
    """
    out = {"exists": False, "run_ids": [], "srcs_to_del": set(),
           "cand_ids": [], "norm_ids": [], "rend_ids": [], "pub_ids": [],
           "art_ids": [], "null_arch_ids": [], "entity_ids": set(),
           "total": 0, "success": 0, "failed": 0, "pending": 0,
           "fail_run_ids": [], "kept_success": 0}
    try:
        path_rows = con.execute(
            "SELECT source_id, current_path, path_identity_key FROM sources"
        ).fetchall()
    except Exception:
        return out
    scope_srcs: set = set()
    unatt_srcs: set = set()
    for r in path_rows:
        try:
            cur, pik = r[1], r[2]
            if (cur and _is_under_root(str(cur), input_root)) or (
                    not cur and pik and _is_under_root(str(pik), input_root)):
                scope_srcs.add(r[0])
            cur_s = str(cur).strip() if cur else ""
            pik_s = str(pik).strip() if pik else ""
            if not cur_s and not pik_s:
                unatt_srcs.add(r[0])
        except Exception:
            continue
    eff_srcs = set(scope_srcs) | set(unatt_srcs)
    try:
        all_src_ids = {rr[0] for rr in con.execute(
            "SELECT source_id FROM sources").fetchall()}
    except Exception:
        all_src_ids = set(eff_srcs)
    try:
        run_rows = con.execute(
            "SELECT run_id, source_id, status FROM processing_runs").fetchall()
    except Exception:
        run_rows = []
    run_status: dict = {}
    source_runs: dict = {}
    orphan_run_ids: list = []
    for rr in run_rows:
        try:
            rid = str(rr[0])
            sid = rr[1] if len(rr) > 1 else None
            status = str(rr[2] or "") if len(rr) > 2 else ""
        except Exception:
            continue
        run_status[rid] = status
        if sid is None or sid not in all_src_ids:
            orphan_run_ids.append(rid)
        else:
            source_runs.setdefault(sid, []).append(rid)
    try:
        disk = _scan_disk_states(str(data_root))
    except Exception:
        disk = {}

    def _run_failed(rid: str) -> bool:
        d = disk.get(rid)
        if isinstance(d, dict) and str(d.get("state") or "") in FAIL_STATES:
            return True
        s = run_status.get(rid, "")
        return s.startswith("FAILED") or s == "NO_SPEECH_DETECTED"

    def _run_done(rid: str) -> bool:
        d = disk.get(rid)
        return bool(isinstance(d, dict)
                    and str(d.get("state") or "") in DONE_STATES)

    scope_run_ids: list = []
    for sid in eff_srcs:
        scope_run_ids.extend(source_runs.get(sid, []))
    scope_run_ids.extend(orphan_run_ids)
    fail_set = {rid for rid in scope_run_ids if _run_failed(rid)}
    done_set = {rid for rid in scope_run_ids if _run_done(rid)}
    out["total"] = len(scope_run_ids)
    out["success"] = len(done_set)
    out["failed"] = len(fail_set)
    _pend = len(scope_run_ids) - len(fail_set) - len(done_set)
    out["pending"] = _pend if _pend > 0 else 0
    out["fail_run_ids"] = [rid for rid in scope_run_ids if rid in fail_set]
    out["kept_success"] = len(done_set)
    if only_failed:
        out["run_ids"] = list(out["fail_run_ids"])
        failed_srcs = {sid for sid, rids in source_runs.items()
                       if sid in eff_srcs and any(rid in fail_set for rid in rids)}
        keep_srcs = {sid for sid in failed_srcs
                     if any(rid not in fail_set for rid in source_runs.get(sid, []))}
        out["srcs_to_del"] = failed_srcs - keep_srcs
    else:
        out["run_ids"] = list(scope_run_ids)
        out["srcs_to_del"] = set(eff_srcs)
    runs_del = set(out["run_ids"])
    if not runs_del and not out["srcs_to_del"]:
        return out
    # 修订链归属：raw_artifact_id = raw_<run_id>
    try:
        norm_rows = con.execute(
            "SELECT normalization_revision_id, normalized_artifact_id,"
            " raw_artifact_id FROM normalization_revisions").fetchall()
    except Exception:
        norm_rows = []
    norm_ids: list = []
    norm_artifacts: list = []
    for r in norm_rows:
        try:
            raw = r[2]
            rid = (raw[len("raw_"):]
                   if isinstance(raw, str) and raw.startswith("raw_") else None)
        except Exception:
            rid = None
        if rid in runs_del:
            norm_ids.append(r[0])
            norm_artifacts.append(r[1])
    out["norm_ids"] = norm_ids
    try:
        rend_rows = con.execute(
            "SELECT render_revision_id FROM render_revisions"
            " WHERE normalized_artifact_id IN (%s)"
            % ",".join("?" for _ in norm_artifacts),
            norm_artifacts).fetchall() if norm_artifacts else []
    except Exception:
        rend_rows = []
    out["rend_ids"] = [r[0] for r in rend_rows]
    try:
        pub_rows = con.execute(
            "SELECT publish_record_id FROM publish_records"
            " WHERE render_revision_id IN (%s)"
            % ",".join("?" for _ in out["rend_ids"]),
            out["rend_ids"]).fetchall() if out["rend_ids"] else []
    except Exception:
        pub_rows = []
    out["pub_ids"] = [r[0] for r in pub_rows]
    # artifacts：全清按源或 run 归属；只清失败只按 run 归属（不误伤成功源产物）
    try:
        if only_failed:
            art_rows = con.execute(
                "SELECT artifact_id FROM artifacts WHERE run_id IN (%s)"
                % ",".join("?" for _ in out["run_ids"]),
                list(out["run_ids"])).fetchall() if out["run_ids"] else []
        elif eff_srcs:
            qmarks = ",".join("?" for _ in eff_srcs)
            art_rows = con.execute(
                "SELECT artifact_id FROM artifacts WHERE source_id IN (%s)%s"
                % (qmarks,
                   (" OR run_id IN (%s)" % ",".join("?" for _ in out["run_ids"]))
                   if out["run_ids"] else ""),
                list(eff_srcs) + list(out["run_ids"])).fetchall()
        elif out["run_ids"]:
            art_rows = con.execute(
                "SELECT artifact_id FROM artifacts WHERE run_id IN (%s)"
                % ",".join("?" for _ in out["run_ids"]),
                list(out["run_ids"])).fetchall()
        else:
            art_rows = []
    except Exception:
        art_rows = []
    out["art_ids"] = [r[0] for r in art_rows]
    # discovery_candidates：全清按源或路径归属；只清失败只按待删源归属（保守）
    try:
        cand_rows = con.execute(
            "SELECT candidate_id, path_identity_key, source_id"
            " FROM discovery_candidates").fetchall()
    except Exception:
        cand_rows = []
    cand_ids: list = []
    for r in cand_rows:
        try:
            sid, pik = r[2], r[1]
        except Exception:
            continue
        if only_failed:
            if sid in out["srcs_to_del"]:
                cand_ids.append(r[0])
        elif sid in eff_srcs or (pik and _is_under_root(str(pik), input_root)):
            cand_ids.append(r[0])
    out["cand_ids"] = cand_ids
    # NULL archive：仅全清带走（门清一致）；只清失败不动
    null_arch_ids: list = []
    if not only_failed:
        try:
            null_arch_rows = con.execute(
                "SELECT archive_commit_id FROM archive_commits"
                " WHERE source_id IS NULL").fetchall()
            null_arch_ids = [rr[0] for rr in null_arch_rows]
        except Exception:
            null_arch_ids = []
    out["null_arch_ids"] = null_arch_ids
    out["entity_ids"] = (set(cand_ids) | set(out["srcs_to_del"])
                         | set(out["run_ids"]) | set(norm_ids)
                         | set(out["rend_ids"]) | set(out["pub_ids"])
                         | set(out["art_ids"]) | set(null_arch_ids))
    out["exists"] = bool(out["run_ids"] or out["srcs_to_del"]
                         or out["cand_ids"] or null_arch_ids)
    return out


def _scoped_runs_summary(data_root: str, input_root: str) -> dict:
    """UX2-P0-1：全量（不受 limit 限制）任务分桶 + 分目录，供列表头。

    total=当前范围全部任务数；done/failed/pending 按磁盘终态优先、DB
    状态兜底分桶；groups 按输入目录尾段分组（未监听展示归属用）。
    与 _filter_status_runs 同口径：孤儿/映射缺失的 run 视为可见（不静默丢）。
    只读 fail-open：任何异常回空壳（total=0），不拦接口。
    """
    out = {"total": 0, "done": 0, "failed": 0, "pending": 0,
           "groups": [], "shown": 0, "truncated": False}
    con = None
    try:
        mapping = _run_source_path_map(data_root)
        con = _open_ro(data_root)
        if con is None:
            return out
        rows = con.execute(
            "SELECT run_id, source_id, status FROM processing_runs").fetchall()
        try:
            disk = _scan_disk_states(data_root)
        except Exception:
            disk = {}
        allow_all = not input_root
        groups: dict = {}
        total = done = failed = pending = 0
        for r in rows:
            try:
                rid = str(r[0])
                status = str(r[2] or "")
            except Exception:
                continue
            path = mapping.get(rid) if mapping else None
            if (not allow_all and path is not None
                    and not _is_under_root(str(path or ""), input_root)):
                continue
            total += 1
            st = None
            d = disk.get(rid)
            if isinstance(d, dict):
                st = str(d.get("state") or "")
            if st in DONE_STATES:
                bucket = "done"
            elif st in FAIL_STATES:
                bucket = "failed"
            elif st is None and (status.startswith("FAILED")
                                 or status == "NO_SPEECH_DETECTED"):
                bucket = "failed"
            else:
                bucket = "pending"
            if bucket == "done":
                done += 1
            elif bucket == "failed":
                failed += 1
            else:
                pending += 1
            dt = (_dir_tail(os.path.dirname(str(path)))
                  if path else "（无归属目录）")
            g = groups.get(dt)
            if g is None:
                g = {"dir_tail": dt, "total": 0, "done": 0,
                     "failed": 0, "pending": 0}
                groups[dt] = g
            g["total"] += 1
            g[bucket] += 1
        out.update({"total": total, "done": done, "failed": failed,
                    "pending": pending, "groups": list(groups.values())})
        return out
    except Exception:
        return out
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def _finder_url(abs_path: str) -> str:
    """P0-4：在访达中打开（file:// + 全编码，复制路径兜底由前端做）。"""
    return "file://" + urllib.parse.quote(os.path.abspath(abs_path), safe="/:")


def _obsidian_url(vault_root: str | None,
                  abs_path: str | None) -> tuple:
    """P0-4：在 OB 中打开。返回 (url|None, reason|None)。

    obsidian://open?vault={vault名}&file={相对路径}，vault 名取
    ob_vault_root basename；未配 vault / 非入库输出均回 reason。
    """
    if not vault_root:
        return None, "未配置笔记库，在上方填入笔记库目录后重起即用"
    if not abs_path:
        return None, "该任务还没有可打开的笔记"
    try:
        vault_real = os.path.realpath(vault_root)
        path_real = os.path.realpath(abs_path)
        if os.path.commonpath([vault_real, path_real]) != vault_real:
            return None, "该稿尚未入库（还在数据目录），入库后可用"
        rel = os.path.relpath(path_real, vault_real)
        vault_name = os.path.basename(os.path.abspath(vault_real))
        url = ("obsidian://open?vault=%s&file=%s"
               % (urllib.parse.quote(vault_name, safe=""),
                  urllib.parse.quote(rel, safe="")))
        return url, None
    except (ValueError, OSError) as exc:
        return None, "路径不在同一本机盘：%s" % (exc,)


def _note_entry_for_run(run_id: str, data_root: str | None) -> tuple:
    """P0-3：找该 run 的终态条目。返回 (entry|None, from_mem: bool)。"""
    with _state_lock:
        mem_all = list(_worker["processed"])
        cur = dict(_worker["current"]) if _worker["current"] else None
    for p in reversed(mem_all):
        try:
            if isinstance(p, dict) and str(p.get("run_id")) == run_id:
                return dict(p), True
        except Exception:
            continue
    if data_root:
        try:
            disk = _scan_disk_states(str(data_root))
            if run_id in disk:
                return dict(disk[run_id]), False
        except Exception:
            pass
    return None, False


def _stage_text_zh(run_id: str, entry: dict | None,
                   data_root: str | None) -> str:
    """P0-3：无 md 时的所处阶段人话。"""
    with _state_lock:
        cur = dict(_worker["current"]) if _worker["current"] else None
    if cur and cur.get("run_id") == run_id:
        stage = str(cur.get("stage") or "")
        if stage == "发现":
            return "正在发现这个视频，稍等即开始听写"
        if stage in ("听写中", "整理中", "成稿中", "入库中"):
            return "正在%s：%s（第 %s 步/共 5 步：发现→听写→整理→成稿→入库）" % (
                stage, cur.get("filename") or run_id,
                STAGE_STEP.get(stage, "?"))
        return "正在处理这个视频：%s" % (stage or "排队")
    if entry and isinstance(entry, dict):
        st = str(entry.get("state") or "")
        if st == "FAIL":
            return "转写失败：%s" % (entry.get("verdict") or "点重试再试一次")
        if st == "PUBLISH_BLOCKED":
            return "初稿已保留，入库未完成：%s" % (
                entry.get("verdict") or "检查笔记库权限后点重试")
    # DB 行级状态兜底
    if data_root:
        con = _open_ro(data_root)
        if con is not None:
            try:
                row = con.execute(
                    "SELECT status FROM processing_runs WHERE run_id=?",
                    (run_id,)).fetchone()
                if row is not None:
                    s = str(row[0] or "")
                    if s == "FAILED_RETRYABLE":
                        return "失败可重试：点重试只重跑这一个"
                    if s == "NO_SPEECH_DETECTED":
                        return "未检测到语音：换一个有声音的视频再试"
                    return "排队等待处理：监听中会自动开始"
            except Exception:
                pass
            finally:
                try:
                    con.close()
                except Exception:
                    pass
    return "排队等待处理：监听中会自动开始"


# ------------------------------------------------- V2.5 用户自定义词库
#
# 用户词库文件：<data_root>/vocab-user.json（[{"wrong":错词,"right":正词}]）。
# 后端内存注册进 stage3.normalize.CORRECTION_RULES（与 stage9.register_rules
# 同 pattern：只改内存映射，不写 src 任何文件），revision 按内容哈希
# "s9-corr-v2-user-<sha8>"（空词库回落 "s9-corr-v2"）。新转写用该 profile
# 自动应用（Case4 语义：规则变 -> 新 NormRev/新 Render，Whisper 不重跑）。
# 校验比 stage9 形状门更松：ASR 错词（如"点env local"->".env.local"）两侧
# 长度差大是常态，只要求非空/限长/不相等/不撞基表。

VOCAB_FILENAME = "vocab-user.json"
VOCAB_MAX_ENTRIES = 500
VOCAB_MAX_SIDE_CHARS = 128
VOCAB_MAX_PROMPT_TERMS = 20
VOCAB_CANDIDATES_FILENAME = "vocab-candidates.json"
VOCAB_DOMAIN_STATE_FILENAME = "vocab-domains.json"


def _vocab_path(data_root: str) -> str:
    return os.path.join(os.path.abspath(str(data_root or "")), VOCAB_FILENAME)


def _vocab_domain_state_path(data_root: str) -> str:
    return os.path.join(os.path.abspath(str(data_root or "")),
                        VOCAB_DOMAIN_STATE_FILENAME)


def _load_vocab_entries(data_root: str) -> list:
    """读用户词库（只读；文件缺失/损坏回空列表，fail-open）。"""
    try:
        path = _vocab_path(data_root)
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            wrong = item.get("wrong")
            right = item.get("right")
            if isinstance(wrong, str) and isinstance(right, str):
                wrong, right = wrong.strip(), right.strip()
                if wrong and right and wrong != right:
                    source = item.get("source")
                    source = source.strip() if isinstance(source, str) else "user"
                    out.append({"wrong": wrong, "right": right,
                                "source": source or "user"})
        return out[:VOCAB_MAX_ENTRIES]
    except Exception:
        return []


def _save_vocab_entries(data_root: str, entries: list) -> None:
    """原子写用户词库（tmp + rename；只写 data_root 下）。"""
    root = os.path.abspath(str(data_root or ""))
    os.makedirs(root, exist_ok=True)
    path = _vocab_path(root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump([{"wrong": e["wrong"], "right": e["right"],
                    "source": str(e.get("source") or "user")}
                   for e in entries],
                  fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def _validate_vocab_pair(wrong, right, existing_wrongs: set,
                         base_patterns: set) -> str | None:
    """校验一对用户词；通过回 None，否则回人话错误。

    V2.5 P1-2：wrong 最小长度≥2写死（CJK≥2 / 拉丁建议≥3二选一取≥2，
    单字 a→b 会血洗全文已实证）；单字/纯标点/纯空格直接拒收。
    2-3字短词放行但由调用方二次确认+回显预警（见 _handle_vocab_add
    与前端 confirm）；大小写变体疑似重复由调用方提示（非阻塞）。
    """
    if not isinstance(wrong, str) or not wrong.strip():
        return "错词不能为空（填转写里听错的样子，如iste）"
    if not isinstance(right, str) or not right.strip():
        return "正词不能为空（填你想要的样子，如.env.local）"
    wrong, right = wrong.strip(), right.strip()
    if wrong == right:
        return "错词和正词一样，无需添加"
    if len(wrong) > VOCAB_MAX_SIDE_CHARS or len(right) > VOCAB_MAX_SIDE_CHARS:
        return "单条超 %d 字，请拆短再加" % (VOCAB_MAX_SIDE_CHARS,)
    # P1-2 最小长度门：单字直接拒收（a→b 血洗 7 处已实证）。
    if len(wrong) < 2:
        return "错词至少2个字（单字替换会误伤全文，如a→b，请加长后再试）"
    # 纯标点/纯空格拒收（strip 后全标点即无检索意义）。
    try:
        import string as _string
        _punct = set(_string.punctuation) | set(
            "，。、；：！？…「」『』（）【】《》〈〉·—–・、。,.!?;:\"'()[]{}<>~@#$%^&*-+=|\\/…")
        if wrong and all((ch in _punct or ch.isspace()) for ch in wrong):
            return "纯标点/空格不能作错词（无检索意义，请填转写里听错的词）"
    except Exception:
        pass
    if wrong in existing_wrongs:
        return "该错词已在词库里，重复添加会覆盖为新正词（已覆盖）"
    if wrong in base_patterns:
        return "该错词已被内置词库收录（%s），无需重复添加" % (wrong,)
    return None


def _user_rules_revision(entries: list) -> str:
    """按词库内容哈希算 revision（纯函数；空词库回落 s9 基线）。"""
    import hashlib as _hl

    from stage9 import rules_v2 as _r9  # noqa: E402  (只读复用基线)

    if not entries:
        return _r9.RULES_REVISION
    pairs = sorted((e["wrong"], e["right"]) for e in entries)
    canonical = json.dumps(pairs, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return "s9-corr-v2-user-%s" % (_hl.sha256(canonical).hexdigest()[:8],)


def _register_user_rules(entries: list) -> dict:
    """内存注册用户合并表（基表 s9 全量 + 用户对子，用户在后）。

    只改内存映射，不写 src 文件；同 revision 同内容幂等，同 revision
    异内容（哈希碰撞级）拒收。返回 {rules_revision, rules, user_added}。
    """
    from stage3 import normalize as _nm  # noqa: E402  (内存注册，只读复用表)
    from stage9 import rules_v2 as _r9  # noqa: E402  (基表来源)

    base = list(_r9.full_table())  # 冻结基行 + Github/Vscode（内存读）
    _r9.register_rules()  # 基线 revision 先就位（幂等）
    pairs = [(e["wrong"], e["right"]) for e in entries]
    base_patterns = {p for p, _ in base}
    for wrong, _ in pairs:
        if wrong in base_patterns:
            raise ValueError("错词 %r 已被内置词库收录，无需重复添加" % (wrong,))
    revision = _user_rules_revision(entries)
    table = tuple(base + pairs)
    live = _nm.CORRECTION_RULES.get(revision)
    if live is not None:
        if tuple(live) != table:
            raise ValueError("内存词表 %r 内容冲突，拒绝替换" % (revision,))
        return {"rules_revision": revision, "rules": len(table),
                "user_added": len(pairs), "idempotent_retry": True}
    _nm.CORRECTION_RULES[revision] = table
    return {"rules_revision": revision, "rules": len(table),
            "user_added": len(pairs), "idempotent_retry": False}


def _load_vocab_domain_state(data_root: str) -> dict:
    """读取预置域启用状态；缺失/损坏时所有域默认启用。"""
    try:
        with open(_vocab_domain_state_path(data_root), "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        enabled = raw.get("enabled") if isinstance(raw, dict) else None
        if not isinstance(enabled, dict):
            return {}
        return {str(k): bool(v) for k, v in enabled.items()}
    except (OSError, ValueError, UnicodeDecodeError):
        return {}


def _save_vocab_domain_state(data_root: str, enabled: dict) -> None:
    root = os.path.abspath(str(data_root or ""))
    os.makedirs(root, exist_ok=True)
    path = _vocab_domain_state_path(root)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"enabled": {str(k): bool(v)
                                    for k, v in enabled.items()}},
                      fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _active_vocab_entries(data_root: str, entries: list | None = None) -> list:
    """停用预置域只影响新规则；用户/候选来源始终保留。"""
    entries = _load_vocab_entries(data_root) if entries is None else entries
    state = _load_vocab_domain_state(data_root)
    preset_domains = {p["domain"] for p in _load_vocab_presets()}
    return [e for e in entries
            if e.get("source") not in preset_domains
            or state.get(e.get("source"), True)]


def _effective_vocab_revision(data_root: str, entries: list | None = None) -> str:
    """当前真正会组装进新转写规则的 active 词条 revision。"""
    return _user_rules_revision(_active_vocab_entries(data_root, entries))


def _norm_profile_for_new_jobs(data_root: str) -> dict:
    """新转写用 Norm profile：用户词库 revision（自动应用，Case4 语义）。"""
    from stage3 import normalize as _nm  # noqa: E402  (只读复用 DEFAULT)

    entries = _active_vocab_entries(data_root)
    reg = _register_user_rules(entries)
    profile = dict(_nm.DEFAULT_PROFILE)
    profile["correction_rules_revision"] = reg["rules_revision"]
    return profile


def _render_profile_for_new_jobs() -> dict:
    """新转写用 Render profile：stage9 分段参数单源头（para-v2.7 目标220/
    封顶450/防碎80），与生产后处理同读 PARA_PARAMS_V2。"""
    from stage9 import formatter_v2 as _fv9  # noqa: E402  (只读复用)

    return _fv9.new_render_profile()


def _apply_v25_postpass(job_dir: str, norm_final_path: str | None,
                        rend_final_path: str, title: str,
                        render_profile: dict) -> dict:
    """生产后处理：冻结引擎已 mint revision 不断链，app 侧用
    ``render_with_v2``（引擎+hard_max封顶+min防碎同一纯函数，阈值全取
    stage9.PARA_PARAMS_V2 单源头）重算并覆写 md。para-v2.7：450/80。

    - 只改 app/ + 复用 stage9 纯函数与 stage3 assemble（只读复用），
      不碰 src 他 stage 文件，不自创 mechanics（选 review 三选一之②
      段侧思想的生产收敛：不断链，whisper0/Raw/No-Clobber 全保留）。
    - 失败 fail-open（回 fixed False，生产继续走引擎原稿，不炸 worker；
      QA 以 fixed True + 段长断言）。
    """
    try:
        from stage3 import render as _rend  # noqa: E402  (只读复用 assemble)
        from stage9 import formatter_v2 as _fv9  # noqa: E402
    except Exception as exc:
        return {"fixed": False, "error": "postpass import 失败：%s" % (exc,)}
    try:
        if not norm_final_path or not os.path.isfile(str(norm_final_path)):
            return {"fixed": False, "error": "normalized 缺失，不覆写"}
        if not rend_final_path or not os.path.isfile(str(rend_final_path)):
            return {"fixed": False, "error": "rendered 缺失，不覆写"}
        with open(str(norm_final_path), "r", encoding="utf-8") as fh:
            import json as _json
            payload = _json.load(fh)
        segments = payload.get("segments") if isinstance(payload, dict) else None
        if not isinstance(segments, list) or not segments:
            return {"fixed": False, "error": "segments 为空，不覆写"}
        try:
            want_paras = _fv9.render_with_v2(segments)
        except Exception as exc:
            return {"fixed": False, "error": "render_with_v2 失败：%s" % (exc,)}
        try:
            want_md = _rend.assemble_markdown(
                want_paras, title or "untitled", render_profile)
        except Exception as exc:
            return {"fixed": False, "error": "assemble 失败：%s" % (exc,)}
        try:
            with open(str(rend_final_path), "r", encoding="utf-8") as fh:
                cur_md = fh.read()
        except OSError as exc:
            return {"fixed": False, "error": "读稿失败：%s" % (exc,)}
        if cur_md == want_md:
            return {"fixed": False, "already_ok": True,
                    "paras": len(want_paras),
                    "max_len": max((len(p) for p in want_paras), default=0)}
        # 提交物为 444 只读（No-Clobber 信号）：先加写权限再覆写，
        # 写完恢复 444，保持与 stage3 提交态一致。
        try:
            os.chmod(str(rend_final_path), 0o644)
        except Exception:
            pass
        with open(str(rend_final_path), "w", encoding="utf-8") as fh:
            fh.write(want_md)
        try:
            os.chmod(str(rend_final_path), 0o444)
        except Exception:
            pass
        return {"fixed": True, "paras": len(want_paras),
                "max_len": max((len(p) for p in want_paras), default=0),
                "lengths": [len(p) for p in want_paras]}
    except Exception as exc:
        return {"fixed": False, "error": "后处理异常：%s" % (exc,)}


def _user_prompt_terms(data_root: str) -> list:
    """用户正词作弱引导进 prompt（prompt 术语弱引导层；失败回空）。"""
    try:
        terms = [e["right"] for e in _active_vocab_entries(data_root)
                 if isinstance(e.get("right"), str) and e["right"].strip()]
        seen: list = []
        for term in terms:
            if term not in seen:
                seen.append(term)
        return seen[:VOCAB_MAX_PROMPT_TERMS]
    except Exception:
        return []


def _handle_vocab_get(query: dict) -> tuple[int, dict]:
    data_root = (query.get("data_root") or [DEFAULT_DATA_ROOT])[0] or DEFAULT_DATA_ROOT
    data_root = normalize_path(data_root) or DEFAULT_DATA_ROOT
    entries = _load_vocab_entries(data_root)
    return 200, {"ok": True, "data_root": data_root,
                 "vocab": entries, "count": len(entries),
                 "revision": _user_rules_revision(entries),
                 "effective_revision": _effective_vocab_revision(data_root, entries)}


def _vocab_base_patterns() -> set:
    """读取冻结基表的 pattern；失败时回空，后续注册链路仍会二次兜底。"""
    try:
        from stage9 import rules_v2 as _r9  # noqa: E402  (只读复用基表)

        return {p for p, _ in _r9.full_table()}
    except Exception:
        return set()


def _vocab_candidates_path(data_root: str) -> str:
    return os.path.join(os.path.abspath(str(data_root or "")),
                        VOCAB_CANDIDATES_FILENAME)


def _load_vocab_candidates(data_root: str) -> list:
    """读 AI 审查候选；文件缺失、损坏或不是数组时返回空清单。"""
    try:
        with open(_vocab_candidates_path(data_root), "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    return raw if isinstance(raw, list) else []


def _mark_vocab_candidates_imported(data_root: str, indices: set) -> None:
    """原子标记候选；失败时不替换原候选文件。"""
    path = _vocab_candidates_path(data_root)
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("候选文件不是数组")
    marked = []
    for index, item in enumerate(raw):
        if index in indices and isinstance(item, dict):
            item = dict(item)
            item["imported"] = True
        marked.append(item)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(marked, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _candidate_confidence(value) -> str:
    value = str(value or "").strip().lower()
    return {"high": "high", "medium": "medium", "low": "low",
            "高": "high", "中": "medium", "低": "low"}.get(value, "low")


def _candidate_view(index: int, item) -> dict:
    item = item if isinstance(item, dict) else {}
    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    return {"index": index, "wrong": item.get("wrong")
            if isinstance(item.get("wrong"), str) else "",
            "right": item.get("right")
            if isinstance(item.get("right"), str) else "",
            "confidence": _candidate_confidence(item.get("confidence")),
            "evidence": [str(x) for x in evidence]}


def _handle_vocab_candidates_get(query: dict) -> tuple[int, dict]:
    data_root = (query.get("data_root") or [DEFAULT_DATA_ROOT])[0] or DEFAULT_DATA_ROOT
    data_root = normalize_path(data_root) or DEFAULT_DATA_ROOT
    groups = {"high": [], "medium": [], "low": []}
    for index, item in enumerate(_load_vocab_candidates(data_root)):
        if isinstance(item, dict) and item.get("imported"):
            continue
        view = _candidate_view(index, item)
        groups[view["confidence"]].append(view)
    return 200, {"ok": True, "data_root": data_root,
                 "candidates": groups,
                 "count": sum(len(items) for items in groups.values()),
                 "has_candidates": bool(sum(len(items) for items in groups.values())),
                 "source_exists": os.path.isfile(_vocab_candidates_path(data_root))}


def _candidate_detail(index, item, accepted: bool, reason: str = "") -> dict:
    view = _candidate_view(index, item)
    view.update({"accepted": accepted, "decision": "保留" if accepted else "拒收"})
    if reason:
        view["reason"] = reason
    return view


def _run_vocab_candidates_apply(params: dict,
                                progress_cb=None) -> tuple[int, dict]:
    """导入选中的 AI 候选，然后复用现有 all=true 重跑（语义与旧同步版一致）。

    progress_cb 仅用于页面进度回传（(ev) -> None）；为 None 时不改变任何行为。
    本函数本身仍是同步阻塞的，异步外壳见 _handle_vocab_candidates_apply。
    """
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    vault = params.get("ob_vault_root")
    vault_s = vault.strip() if isinstance(vault, str) and vault.strip() else None
    # 新前端显式传 false 表示只入库；缺字段沿用旧 API 的全量重跑行为。
    rerun_old = params.get("rerun_old", True) is True
    indices = params.get("indices")
    if not isinstance(indices, list):
        return 400, {"ok": False, "error": "请传 indices 数组（勾选要导入的候选）"}
    candidates = _load_vocab_candidates(data_root)
    details = []
    selected = []
    seen_indices = set()
    for raw_index in indices:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            details.append({"index": raw_index, "accepted": False,
                            "decision": "拒收", "reason": "候选索引无效"})
            continue
        if index in seen_indices:
            details.append({"index": index, "accepted": False,
                            "decision": "拒收", "reason": "候选索引重复"})
            continue
        seen_indices.add(index)
        if index < 0 or index >= len(candidates):
            details.append({"index": index, "accepted": False,
                            "decision": "拒收", "reason": "候选索引不存在"})
            continue
        if isinstance(candidates[index], dict) and candidates[index].get("imported"):
            details.append(_candidate_detail(
                index, candidates[index], False, "该候选已导入，清单已标记"))
            continue
        selected.append((index, candidates[index]))
    entries = _load_vocab_entries(data_root)
    entries_before = list(entries)
    existing = {e["wrong"] for e in entries}
    base_patterns = _vocab_base_patterns()
    accepted_entries = []
    for index, item in selected:
        item = item if isinstance(item, dict) else {}
        wrong = item.get("wrong")
        right = item.get("right")
        err = _validate_vocab_pair(wrong, right, existing, base_patterns)
        if err is not None:
            details.append(_candidate_detail(index, item, False, err))
            continue
        if len(entries) + len(accepted_entries) >= VOCAB_MAX_ENTRIES:
            details.append(_candidate_detail(
                index, item, False, "词库已满（%d 条），请先删一些再导入" % VOCAB_MAX_ENTRIES))
            continue
        accepted_entries.append({"wrong": wrong.strip(), "right": right.strip(),
                                 "source": "candidate"})
        existing.add(wrong.strip())
        details.append(_candidate_detail(index, item, True))
    imported = len(accepted_entries)
    revision = _user_rules_revision(entries)
    if imported:
        entries.extend(accepted_entries)
        try:
            _save_vocab_entries(data_root, entries)
        except OSError as exc:
            return 500, {"ok": False, "data_root": data_root,
                         "error": "词库保存失败，未生效：%s→检查磁盘空间/目录权限后重试" % exc,
                         "details": details}
        try:
            reg = _register_user_rules(entries)
            revision = reg["rules_revision"]
        except ValueError as exc:
            try:
                _save_vocab_entries(data_root, entries_before)
            except Exception:
                pass
            return 400, {"ok": False, "data_root": data_root,
                         "error": "词库注册失败，已回滚未生效：%s" % exc,
                         "details": details}
        except Exception as exc:
            try:
                _save_vocab_entries(data_root, entries_before)
            except Exception:
                pass
            return 500, {"ok": False, "data_root": data_root,
                         "error": "词库注册失败，已回滚未生效：%s" % exc,
                         "details": details}
    if not imported:
        return 200, {"ok": True, "data_root": data_root, "imported": 0,
                     "revision": revision, "details": details,
                     "effective_revision": _effective_vocab_revision(data_root, entries),
                     "codesummary": "导入0条/重跑成功0篇/跳过0篇/失败0篇",
                     "message": "没有候选通过校验，未导入；未执行重跑"}
    candidate_mark_error = ""
    try:
        _mark_vocab_candidates_imported(
            data_root, {d["index"] for d in details if d.get("accepted")})
    except Exception as exc:
        candidate_mark_error = "候选清单标记失败，原文件未改动：%s" % exc
    if not rerun_old:
        message = "已导入%d条；未重跑老稿，老稿未动" % imported
        if candidate_mark_error:
            message += "。" + candidate_mark_error
        return 200, {"ok": not candidate_mark_error, "data_root": data_root,
                     "imported": imported, "rerun_old": False,
                     "revision": revision, "details": details,
                     "effective_revision": _effective_vocab_revision(data_root, entries),
                     "reapply": None,
                     "summary": {"success": 0, "skipped": 0, "failed": 0},
                     "candidate_mark_error": candidate_mark_error,
                     "codesummary": "导入%d条/重跑成功0篇/跳过0篇/失败0篇；老稿未动"
                     % imported,
                     "message": message}
    try:
        reapply_params = {"data_root": data_root, "all": True}
        if vault_s:
            reapply_params["ob_vault_root"] = vault_s
        reapply_body = json.dumps(reapply_params, ensure_ascii=False).encode("utf-8")
        reapply_code, reapply = _handle_reapply_post(reapply_body,
                                                     progress_cb=progress_cb)
    except Exception as exc:
        reapply_code, reapply = 500, {"ok": False, "error": "重跑接口异常：%s" % exc}
    summary = reapply.get("summary") if isinstance(reapply, dict) else None
    results = reapply.get("results") if isinstance(reapply, dict) else []
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(results, list):
        results = []
    success = sum(1 for item in results
                  if isinstance(item, dict) and item.get("ok")
                  and not item.get("skipped") and not item.get("skipped_user_edited"))
    skipped = sum(1 for item in results
                  if isinstance(item, dict)
                  and (item.get("skipped") or item.get("skipped_user_edited")))
    failed = sum(1 for item in results
                 if isinstance(item, dict) and not item.get("ok")
                 and not item.get("skipped"))
    if not results and isinstance(summary.get("total"), int):
        success = int(summary.get("ok") or 0)
        skipped = int(summary.get("skipped_user_edited") or 0)
        failed = int(summary.get("failed") or 0)
    rerun_ok = reapply_code == 200 and bool(reapply.get("ok")) and failed == 0
    message = "已导入%d条；重跑成功%d篇，跳过%d篇" % (imported, success, skipped)
    if failed:
        message += "，失败%d篇" % failed
    if not rerun_ok:
        message += "。词已入库，但重跑失败，请检查失败明细后重试"
    if candidate_mark_error:
        message += "。" + candidate_mark_error
    if not vault_s:
        message += "。未给笔记库，库内笔记未更新"
    operation_ok = rerun_ok and not candidate_mark_error
    codesummary = "导入%d条/重跑成功%d篇/跳过%d篇/失败%d篇" % (
        imported, success, skipped, failed)
    return 200, {"ok": operation_ok, "data_root": data_root, "imported": imported,
                 "rerun_old": True,
                 "revision": revision, "effective_revision":
                 _effective_vocab_revision(data_root, entries),
                 "details": details,
                 "reapply": reapply, "summary": {"success": success,
                 "skipped": skipped, "failed": failed},
                 "candidate_mark_error": candidate_mark_error,
                 "codesummary": codesummary,
                 "message": message}


def _vocab_apply_worker(job_id: str, params: dict) -> None:
    """后台线程：跑 _run_vocab_candidates_apply，并把结果落回 _vocab_apply_job。

    只更新状态；异常一律转 failed 人话，不炸进程。
    """

    def _on_progress(ev: dict) -> None:
        try:
            with _state_lock:
                job = _vocab_apply_job
                if not isinstance(job, dict) or job.get("job_id") != job_id:
                    return
                job["stage"] = "rerunning"
                if isinstance(ev.get("total"), int):
                    job["total"] = ev["total"]
                if isinstance(ev.get("done"), int):
                    job["done"] = ev["done"]
                if ev.get("filename"):
                    job["current_filename"] = ev["filename"]
        except Exception:
            pass

    try:
        code, obj = _run_vocab_candidates_apply(params, progress_cb=_on_progress)
    except Exception as exc:  # noqa: BLE001  (兜底转 failed，不炸线程)
        code, obj = 500, {"ok": False, "error": "错词重跑异常：%s" % (exc,)}
    obj = obj if isinstance(obj, dict) else {}
    with _state_lock:
        job = _vocab_apply_job
        if not isinstance(job, dict) or job.get("job_id") != job_id:
            return
        job["finished_at"] = _utc_now_iso()
        job["result"] = obj
        try:
            job["imported"] = int(obj.get("imported") or 0)
        except (TypeError, ValueError):
            job["imported"] = 0
        s = obj.get("summary")
        if isinstance(s, dict):
            job["summary"] = {
                "success": int(s.get("success") or 0),
                "skipped": int(s.get("skipped") or 0),
                "failed": int(s.get("failed") or 0),
            }
        job["current_filename"] = None
        if code == 200:
            job["state"] = "done"
            job["message"] = str(obj.get("message") or obj.get("codesummary")
                                 or "处理完成")
            if not job.get("rerun_old"):
                job["total"] = job.get("total") or 0
                job["done"] = job.get("total")
        else:
            job["state"] = "failed"
            job["error"] = str(obj.get("error") or "处理失败，请刷新后重试")
            job["message"] = job["error"]


def _handle_vocab_candidates_apply(body: bytes) -> tuple[int, dict]:
    """异步入口：请求级校验后立即返回 202 + job_id，后台线程做导入＋按需重跑。

    进度由 GET /api/vocab/candidates/apply/status 读取（状态存后端，
    刷新页面可续看）。导入/幂等/No-Clobber/词库三铁律语义全部沿用
    _run_vocab_candidates_apply，未改动。
    """
    global _vocab_apply_job, _vocab_apply_seq
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params.get("indices"), list):
        return 400, {"ok": False, "error": "请传 indices 数组（勾选要导入的候选）"}
    with _state_lock:
        cur = _vocab_apply_job
        if isinstance(cur, dict) and cur.get("state") == "running":
            return 409, {"ok": False, "running": True,
                         "job_id": cur.get("job_id"),
                         "error": "已有一次错词重跑在进行中，请等它跑完再试"}
        _vocab_apply_seq += 1
        job_id = "vocab-apply-%d-%d" % (_vocab_apply_seq,
                                        int(threading.get_ident() % 100000))
        _vocab_apply_job = {
            "job_id": job_id,
            "state": "running",
            "stage": "importing",
            "data_root": normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT,
            "rerun_old": params.get("rerun_old", True) is True,
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "total": 0,
            "done": 0,
            "current_filename": None,
            "imported": 0,
            "summary": {"success": 0, "skipped": 0, "failed": 0},
            "error": None,
            "message": "正在导入错词…",
            "result": None,
        }
    try:
        # M3：构造与 start 同保护，任一步失败都落 failed 终态，不悬挂单例
        thread = threading.Thread(
            target=_vocab_apply_worker, args=(job_id, params),
            name="v2o-vocab-apply", daemon=True,
        )
        thread.start()
    except Exception as exc:  # noqa: BLE001  起线程失败不得悬挂单例
        reason = "后台任务启动失败：%s，请重试或重启服务" % (exc,)
        with _state_lock:
            cur2 = _vocab_apply_job
            if isinstance(cur2, dict) and cur2.get("job_id") == job_id:
                cur2.update({"state": "failed", "finished_at": _utc_now_iso(),
                             "error": reason, "message": reason})
        return 500, {"ok": False, "error": reason}
    return 202, {"ok": True, "job_id": job_id, "state": "running",
                 "message": "已开始处理，进度见页面"}


def _handle_vocab_apply_status(query: dict) -> tuple[int, dict]:
    """只读：返回最近一次错词重跑任务进度（results 明细不在这里，避免响应过大）。"""
    with _state_lock:
        job = dict(_vocab_apply_job) if isinstance(_vocab_apply_job, dict) else None
    if job is None:
        return 200, {"ok": True, "job": None}
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    return 200, {"ok": True, "job": {
        "job_id": job.get("job_id"),
        "state": job.get("state"),
        "stage": job.get("stage"),
        "data_root": job.get("data_root"),
        "rerun_old": job.get("rerun_old"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "total": job.get("total"),
        "done": job.get("done"),
        "current_filename": job.get("current_filename"),
        "imported": job.get("imported"),
        "summary": job.get("summary"),
        "error": job.get("error"),
        "message": job.get("message"),
        "codesummary": result.get("codesummary"),
        "details": result.get("details"),
    }}


def _handle_vocab_add(body: bytes) -> tuple[int, dict]:
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    wrong = params.get("wrong")
    right = params.get("right")
    wrong_s = wrong.strip() if isinstance(wrong, str) else ""
    right_s = right.strip() if isinstance(right, str) else ""
    try:
        from stage9 import rules_v2 as _r9  # noqa: E402  (基表 patterns)

        base_patterns = {p for p, _ in _r9.full_table()}
    except Exception:
        base_patterns = set()
    entries = _load_vocab_entries(data_root)
    existing = {e["wrong"] for e in entries}
    err = _validate_vocab_pair(wrong_s, right_s, existing, base_patterns)
    # 重复错词视为覆盖更新（ upsert），其余非法直接拒收
    # P1-2：单字/纯标点已在 _validate 直接 400（wrong_s not in existing
    # 即拒收，覆盖路径不绕过长度门：单字覆盖同样拒收）。
    if err is not None and wrong_s not in existing:
        return 400, {"ok": False, "error": err}
    if not wrong_s or not right_s or wrong_s == right_s:
        return 400, {"ok": False, "error": err or "错词/正词不合法"}
    if len(wrong_s) > VOCAB_MAX_SIDE_CHARS or len(right_s) > VOCAB_MAX_SIDE_CHARS:
        return 400, {"ok": False, "error": err or "单条超长"}
    if len(wrong_s) < 2:
        return 400, {"ok": False,
                     "error": err or "错词至少2个字（单字替换会误伤全文，请加长后再试）"}
    if wrong_s in base_patterns:
        return 400, {"ok": False, "error": err or "已被内置词库收录"}
    entries_before = list(entries)
    if wrong_s in existing:
        entries = [e for e in entries if e["wrong"] != wrong_s]
    if len(entries) >= VOCAB_MAX_ENTRIES and wrong_s not in existing:
        return 400, {"ok": False,
                     "error": "词库已满（%d 条），删一些再加" % (VOCAB_MAX_ENTRIES,)}
    entries.append({"wrong": wrong_s, "right": right_s, "source": "user"})
    # P1-2 短词预警 + 大小写变体提示（非阻塞，随成功回显；前端 2-3 字
    # 二次 confirm 复用 delVocab 口径；命中数>50 警告待新转写验证，
    # 后端此处回显 needs_confirm + hint，QA 以此断言预览存在）。
    _preview_warnings: list = []
    if 2 <= len(wrong_s) <= 3:
        _preview_warnings.append(
            "短词（%d字）易命中多处：添加后新转写与重跑会自动应用全文替换，"
            "如命中超50处请及时删除" % (len(wrong_s),))
    try:
        _lower_base = {str(p).lower() for p in base_patterns}
        if wrong_s not in base_patterns and wrong_s.lower() in _lower_base:
            _preview_warnings.append(
                "疑似重复（仅大小写差异，内置已有同名不同大小写），仍要加吗？"
                "确认无误再点添加")
    except Exception:
        pass
    # P1-3：先落盘后注册。落盘 OSError → 500 JSON“词库保存失败，未生效”
    # （内存未动，旧文件原子保留）；注册失败则回滚文件到 entries_before
    # （二选一取“删回文件”以保内存文件一致，重启无需自愈），并注释。
    try:
        _save_vocab_entries(data_root, entries)
    except OSError as exc:
        return 500, {"ok": False,
                     "error": "词库保存失败，未生效：%s→检查磁盘空间/目录权限后重试"
                              % (exc,)}
    try:
        reg = _register_user_rules(entries)
    except ValueError as exc:
        # 注册失败（撞基表/内存冲突）：删回文件保一致。
        try:
            _save_vocab_entries(data_root, entries_before)
        except Exception:
            pass
        return 400, {"ok": False, "error": str(exc)}
    _msg = (("已覆盖更新：%s→%s" % (wrong_s, right_s))
            if err is not None else
            ("已添加：%s→%s，新转写自动应用" % (wrong_s, right_s)))
    if _preview_warnings:
        _msg += "（注意：" + "；".join(_preview_warnings) + "）"
    return 200, {"ok": True, "data_root": data_root, "vocab": entries,
                 "count": len(entries), "revision": reg["rules_revision"],
                 "effective_revision": _effective_vocab_revision(data_root, entries),
                 "message": _msg,
                 "preview": {"wrong_len": len(wrong_s),
                             "needs_confirm": 2 <= len(wrong_s) <= 3,
                             "warnings": _preview_warnings}}


def _handle_vocab_del(body: bytes) -> tuple[int, dict]:
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    wrong = params.get("wrong")
    wrong_s = wrong.strip() if isinstance(wrong, str) else ""
    if not wrong_s:
        return 400, {"ok": False, "error": "缺少要删除的错词 wrong"}
    entries = _load_vocab_entries(data_root)
    kept = [e for e in entries if e["wrong"] != wrong_s]
    if len(kept) == len(entries):
        return 404, {"ok": False, "error": "词库里没有该错词：%s" % (wrong_s,)}
    try:
        _save_vocab_entries(data_root, kept)
    except OSError as exc:
        return 500, {"ok": False,
                     "error": "词库保存失败，未生效：%s→检查磁盘空间/目录权限后重试"
                              % (exc,)}
    return 200, {"ok": True, "data_root": data_root, "vocab": kept,
                 "count": len(kept), "revision": _user_rules_revision(kept),
                 "effective_revision": _effective_vocab_revision(data_root, kept),
                 "message": "已删除：%s（新转写不再应用）" % (wrong_s,)}


# ------------------------------------------------- V2.6 预置词库（三域一键导入）
#
# 预置词库文件：app/presets/vocab/*.json（随仓库只读，运行时绝不改写）。
# 每个文件 {"domain","label","version","source","entries":[{"wrong","right"}]}；
# 目录扫描发现域 => 新增一个 json 即新增一域（可扩展），无需改 server。
# 导入 = 合并进 <data_root>/vocab-user.json：已存在的错词跳过（保留用户自定，
# 不覆盖），撞内置基表（stage9 full_table patterns）的整条拒收并回报，
# 非法/超长/错词<2字同样拒收；内容变化 => _user_rules_revision 哈希变 =>
# revision bump，新转写自动应用（Case4 语义，whisper 不重跑）。

VOCAB_PRESET_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "presets", "vocab")
VOCAB_PRESET_REPORT_MAX = 20


def _read_vocab_preset(path: str) -> dict | None:
    """读单个预置词库文件（只读；缺失/损坏/结构不符回 None）。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("entries")
    if not isinstance(raw, list):
        return None
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        wrong = item.get("wrong")
        right = item.get("right")
        if not isinstance(wrong, str) or not isinstance(right, str):
            continue
        wrong, right = wrong.strip(), right.strip()
        if len(wrong) >= 2 and right and wrong != right:
            entries.append({"wrong": wrong, "right": right})
    stem = os.path.splitext(os.path.basename(path))[0]
    domain = str(data.get("domain") or stem).strip() or stem
    label = str(data.get("label") or domain).strip() or domain
    return {"domain": domain, "label": label,
            "file": os.path.basename(path),
            "version": data.get("version"),
            "source": data.get("source"),
            "entries": entries}


def _load_vocab_presets() -> list:
    """扫描预置目录（新增文件即新增域，可扩展；坏文件跳过不炸）。"""
    try:
        names = sorted(os.listdir(VOCAB_PRESET_DIR))
    except OSError:
        return []
    out = []
    for name in names:
        if not name.lower().endswith(".json"):
            continue
        preset = _read_vocab_preset(os.path.join(VOCAB_PRESET_DIR, name))
        if preset is not None and preset["entries"]:
            out.append(preset)
    return out


def _handle_vocab_presets_get(query: dict | None = None) -> tuple[int, dict]:
    """预置词库清单（只读条目、启用状态，不修改预置文件）。"""
    query = query or {}
    data_root = (query.get("data_root") or [DEFAULT_DATA_ROOT])[0] or DEFAULT_DATA_ROOT
    data_root = normalize_path(data_root) or DEFAULT_DATA_ROOT
    enabled = _load_vocab_domain_state(data_root)
    presets = _load_vocab_presets()
    return 200, {"ok": True, "presets": [
        {"domain": p["domain"], "label": p["label"], "count": len(p["entries"]),
         "version": p["version"], "source": p["source"], "file": p["file"],
         "enabled": enabled.get(p["domain"], True),
         "entries": p["entries"]}
        for p in presets]}


def _handle_vocab_presets_domains_post(body: bytes) -> tuple[int, dict]:
    """保存预置域启用开关；停用只影响新转写/重跑，不改老稿。"""
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    raw = params.get("enabled")
    if not isinstance(raw, dict):
        return 400, {"ok": False, "error": "请传 enabled 对象（每个预置域 true/false）"}
    known = {p["domain"] for p in _load_vocab_presets()}
    enabled = {domain: bool(raw.get(domain, True)) for domain in known}
    try:
        _save_vocab_domain_state(data_root, enabled)
    except OSError as exc:
        return 500, {"ok": False, "error": "启用状态保存失败：%s" % exc}
    disabled = [domain for domain, value in enabled.items() if not value]
    return 200, {"ok": True, "data_root": data_root, "enabled": enabled,
                 "disabled": disabled,
                 "message": "预置词库开关已保存；停用域只影响新转写，老稿需重跑才会更新"}


def _handle_vocab_presets_import(body: bytes) -> tuple[int, dict]:
    """预置域一键导入：合并进用户词库并 bump revision（撞基表拒收）。"""
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    want_raw = params.get("domains")
    if not isinstance(want_raw, list):
        return 400, {"ok": False, "error": "请传 domains 数组（勾选的领域）"}
    want = [str(d).strip() for d in want_raw if str(d).strip()]
    if not want:
        return 400, {"ok": False, "error": "先勾选至少一个领域再导入"}
    by_domain = {p["domain"]: p for p in _load_vocab_presets()}
    unknown = [d for d in want if d not in by_domain]
    if len(unknown) == len(want):
        return 400, {"ok": False,
                     "error": "未知领域：%s（刷新后重试）" % (",".join(unknown),)}
    try:
        from stage9 import rules_v2 as _r9  # noqa: E402  (基表 patterns)

        base_patterns = {p for p, _ in _r9.full_table()}
    except Exception:
        base_patterns = set()
    entries = _load_vocab_entries(data_root)
    entries_before = list(entries)
    existing = {e["wrong"] for e in entries}
    added = 0
    skipped_dup = 0
    rejected_base: list = []
    rejected_invalid: list = []
    dropped_overflow = 0
    for domain in want:
        preset = by_domain.get(domain)
        if preset is None:
            continue
        for cand in preset["entries"]:
            wrong, right = cand["wrong"], cand["right"]
            if wrong in base_patterns:
                rejected_base.append(wrong)
                continue
            if wrong in existing:
                skipped_dup += 1
                continue
            err = _validate_vocab_pair(wrong, right, existing, base_patterns)
            if err is not None:
                rejected_invalid.append(wrong)
                continue
            if len(entries) >= VOCAB_MAX_ENTRIES:
                dropped_overflow += 1
                continue
            entries.append({"wrong": wrong, "right": right, "source": domain})
            existing.add(wrong)
            added += 1
    if added:
        # 先落盘后注册；注册撞内存冲突则删回文件保一致（同 _handle_vocab_add）。
        try:
            _save_vocab_entries(data_root, entries)
        except OSError as exc:
            return 500, {"ok": False,
                         "error": "词库保存失败，未生效：%s→检查磁盘空间/目录权限后重试"
                                  % (exc,)}
        try:
            reg = _register_user_rules(entries)
        except ValueError as exc:
            try:
                _save_vocab_entries(data_root, entries_before)
            except Exception:
                pass
            return 400, {"ok": False, "error": str(exc)}
        revision = reg["rules_revision"]
    else:
        revision = _user_rules_revision(entries)
    labels = "/".join(by_domain[d]["label"] for d in want if d in by_domain)
    parts = ["已导入 %s 共 %d 条" % (labels or "-", added)]
    if skipped_dup:
        parts.append("跳过已存在 %d 条" % (skipped_dup,))
    if rejected_base:
        parts.append("撞内置词库拒收 %d 条" % (len(rejected_base),))
    if rejected_invalid:
        parts.append("非法拒收 %d 条" % (len(rejected_invalid),))
    if dropped_overflow:
        parts.append("词库已满丢弃 %d 条" % (dropped_overflow,))
    if unknown:
        parts.append("未知领域忽略：%s" % (",".join(unknown),))
    return 200, {"ok": True, "data_root": data_root, "domains": want,
                 "added": added, "skipped_duplicate": skipped_dup,
                 "rejected_base": rejected_base[:VOCAB_PRESET_REPORT_MAX],
                 "rejected_base_count": len(rejected_base),
                 "rejected_invalid": rejected_invalid[:VOCAB_PRESET_REPORT_MAX],
                 "rejected_invalid_count": len(rejected_invalid),
                 "dropped_overflow": dropped_overflow,
                 "unknown_domains": unknown,
                 "vocab": entries, "count": len(entries),
                 "revision": revision,
                 "effective_revision": _effective_vocab_revision(data_root, entries),
                 "message": "；".join(parts) + "。新转写自动应用。"}


def _handle_status(query: dict) -> tuple[int, dict]:
    data_root = (query.get("data_root") or [DEFAULT_DATA_ROOT])[0] or DEFAULT_DATA_ROOT
    data_root = normalize_path(data_root) or DEFAULT_DATA_ROOT
    try:
        limit = int((query.get("limit") or ["20"])[0])
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(limit, 200))
    snap = collect(data_root, limit=limit)
    # P0-2：默认只返回当前 input_root 的 runs（传参优先，监听态兜底）
    eff = ""
    try:
        raw_ir = (query.get("input_root") or [""])[0]
        eff = normalize_path(raw_ir)
        if not eff:
            with _state_lock:
                if _listener.get("running") and _listener.get("input_root"):
                    eff = str(_listener.get("input_root"))
        if eff and isinstance(snap, dict) and snap.get("ok"):
            snap = _filter_status_runs(snap, data_root, eff)
    except Exception:
        pass
    # V2.3 P0-1：runs附source_filename（取不到回“未知文件”）
    try:
        if isinstance(snap, dict) and snap.get("ok"):
            snap = _attach_source_filenames(snap, data_root)
    except Exception:
        pass
    # UX2-P0-1：全量分桶 + 截断明示（列表头 共N/成功/失败/排队，禁静默截断）
    try:
        if isinstance(snap, dict) and snap.get("ok"):
            summary = _scoped_runs_summary(data_root, eff)
            summary["shown"] = len(snap.get("recent_runs") or [])
            summary["truncated"] = (int(summary.get("total") or 0)
                                    > int(summary["shown"]))
            summary["limit"] = limit
            snap["run_summary"] = summary
    except Exception:
        pass
    return 200, snap


def _handle_browse(query: dict) -> tuple[int, dict]:
    """页面内目录浏览：只列目录，按名排序；越界/无权限/非本地盘 400（人话）。

    成功时附带视频计数：当前目录 videos{total,sample,long_estimate} +
    每子目录 counts{name: N}（单层只读，1000 上限）。
    """
    raw = (query.get("path") or [""])[0]
    path = normalize_path(raw)
    if not path:
        # 空则从用户主目录起步（本地盘，可列）
        path = os.path.expanduser("~")
    if not os.path.isabs(path):
        return 400, {"ok": False, "error": "所填路径须为绝对路径：%r，请点浏览重选" % (raw,)}
    real = os.path.realpath(path)
    if os.path.isfile(real):
        return 400, {"ok": False, "error": "所选路径须为目录（当前是文件）：%s，请点浏览重选" % (real,)}
    if not os.path.isdir(real):
        return 400, {"ok": False, "error": "所选路径不存在：%s，请点浏览重选" % (real,)}
    try:
        from stage1.ingest import probe_volume  # noqa: E402  (只读复用)
        verdict = probe_volume(real).get("verdict")
    except Exception:
        return 400, {"ok": False, "error": "所选目录不在本机硬盘上，仅支持本机硬盘，请点浏览重选"}
    if verdict != "ALLOW":
        return 400, {"ok": False, "error": "仅支持本机硬盘目录：%s，请点浏览重选" % (real,)}
    try:
        names = sorted(
            name for name in os.listdir(real)
            if os.path.isdir(os.path.join(real, name))
            and name not in (".", "..")
        )
    except PermissionError:
        return 400, {"ok": False, "error": "所选目录无权限列出：%s，请检查权限后点浏览重选" % (real,)}
    except OSError as exc:
        return 400, {"ok": False, "error": "所选目录列出失败：%s，请点浏览重选" % (exc,)}
    parent = os.path.dirname(real)
    dirs = names[:1000]
    # 当前目录视频统计
    try:
        videos = _count_videos_in_dir(real)
    except Exception:
        videos = {"total": 0, "sample": [], "long_estimate": 0}
    # 每子目录视频数（单层只读）
    counts: dict = {}
    try:
        for d in dirs:
            try:
                sub = os.path.join(real, d)
                st = _count_videos_in_dir(sub)
                counts[d] = int(st.get("total") or 0)
            except Exception:
                counts[d] = 0
    except Exception:
        counts = {}
    return 200, {"ok": True, "path": real, "parent": parent, "dirs": dirs,
                 "videos": videos, "counts": counts}


# ------------------------------------------------------- 转写 worker（P0-5）

def _utc_now_iso() -> str:
    import datetime

    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _worker_record(item: dict) -> None:
    with _state_lock:
        _worker["processed"].append(item)
        _worker["processed"] = _worker["processed"][-100:]


def _worker_note_error(message: str) -> None:
    with _state_lock:
        _worker["last_error"] = message


def _transcribe_audio(job_asr_dir: str, src_path: str,
                      prompt_terms: list | None = None) -> dict:
    """转写 stage7/8（只读复用公开 API），返回 {text, segments, engine_calls}。

    短音频（<=600s）走 stage7 单文件；长音频走 stage8 分块。
    stage7/8 失败则回退 stage1 单文件直调；mlx 缺失则抛错由上层记 verdict。
    prompt_terms：用户正词弱引导（V2.5，进 topic 层，失败忽略不拦转写）。
    """
    from stage1.asr import extract_temp_wav  # noqa: E402  (只读复用)

    os.makedirs(job_asr_dir, exist_ok=True)
    wav_path = os.path.join(job_asr_dir, "asr_16k.wav")
    audio = extract_temp_wav(src_path, wav_path)
    duration = float(audio.get("audio_duration_s") or 0.0)

    if duration <= 600:
        try:
            from stage7.prompt_builder import build_initial_prompt  # noqa: E402
            from stage7.transcribe import run_single_file_with_prompt  # noqa: E402

            try:
                _topics = ["本地", "中文"] + [t for t in (prompt_terms or [])
                                              if isinstance(t, str) and t.strip()]
                prompt = build_initial_prompt(["视频", "转写"], _topics,
                                              ["用户", "记录"])["initial_prompt"]
            except Exception:
                prompt = "视频转写，中文记录。"
            out = run_single_file_with_prompt(wav_path, prompt)
            return {"text": out.get("text", ""), "segments": out.get("segments", []),
                    "engine_calls": int(out.get("engine_calls") or 1)}
        except Exception:
            pass  # 回退 stage1 直调
    else:
        try:
            from stage8.chunk_planner import plan_chunks  # noqa: E402
            from stage8.transcribe_chunks import run_chunks  # noqa: E402

            chunks = plan_chunks(duration)
            _extra = {"global": ["视频"], "topic": ["转写"], "creator": ["记录"]}
            try:
                _pts = [t for t in (prompt_terms or [])
                        if isinstance(t, str) and t.strip()]
                if _pts:
                    _extra = {"global": ["视频"], "topic": ["转写"] + _pts,
                              "creator": ["记录"]}
            except Exception:
                pass
            term_sets = [dict(_extra) for _ in chunks]
            out = run_chunks(wav_path, term_sets)
            merged = out.get("merged") or {}
            text = merged.get("text")
            if not isinstance(text, str):
                text = "".join(
                    str(seg.get("text", "")) for seg in (merged.get("segments") or [])
                )
            return {"text": text, "segments": merged.get("segments") or [],
                    "engine_calls": int(out.get("engine_calls") or len(chunks))}
        except Exception:
            pass  # 回退 stage1 直调

    from stage1.asr import transcribe_wav_file  # noqa: E402  (只读复用)

    out = transcribe_wav_file(wav_path)
    return {"text": out.get("text", ""), "segments": out.get("segments", []),
            "engine_calls": int(out.get("asr_calls") or 1)}


def _process_one_run(data_root: str, input_root: str, ob_vault_root: str | None,
                     run_id: str, profile_hash: str) -> dict:
    """单个 QUEUED AUTO run 端到端：转写→Norm/Render→Publish（vault 为空则停 Render）。"""
    from stage2 import store  # noqa: E402  (只读复用 open_db)

    con = store.open_db(data_root)
    try:
        run = con.execute(
            "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None:
            return {"run_id": run_id, "state": "SKIP", "verdict": "run vanished"}
        run = dict(run)
        if run.get("status") != "QUEUED" or run.get("creation_mode") != "AUTO":
            return {"run_id": run_id, "state": "SKIP", "verdict": "not QUEUED/AUTO"}
        source_id = run.get("source_id")
        src = con.execute(
            "SELECT * FROM sources WHERE source_id=?", (source_id,)
        ).fetchone()
        if src is None:
            out = {"run_id": run_id, "state": "FAIL",
                   "source_filename": "未知文件",
                   "verdict": "视频记录找不到了→请重新把视频放进文件夹再试"}
            _worker_record(out)
            return out
        src = dict(src)
    finally:
        con.close()

    src_path = src.get("current_path") or ""
    src_real = os.path.realpath(src_path)
    input_real = os.path.realpath(input_root)
    vault_real = os.path.realpath(ob_vault_root) if ob_vault_root else None
    # V2.3 P0-1：面向用户文案用文件名（取不到回“未知文件”，run_id只留详情区）
    try:
        _src_fn = os.path.basename(str(src_path).strip()) or "未知文件"
        if not _src_fn.strip():
            _src_fn = "未知文件"
    except Exception:
        _src_fn = "未知文件"
    if not os.path.isfile(src_real):
        out = {"run_id": run_id, "state": "FAIL",
               "source_filename": _src_fn,
               "verdict": "源视频文件找不到了：%s→检查视频是否被移动或删除，补回后点重试" % (_src_fn,)}
        _worker_record(out)
        return out
    # P0-1 防守：worker 已按视频文件夹前缀过滤才调用；此处命中说明是旧文件夹
    # 残留，直接忽略（不计数、不记 processed、不打扰），由调用方不再传入。
    if not _is_under_root(src_real, input_real):
        return {"run_id": run_id, "state": "SKIP",
                "verdict": "源不在当前视频文件夹内，已忽略"}

    filename = os.path.basename(src_real) or run_id
    _worker_set_current(run_id, filename, STAGE_DISCOVER)

    job_dir = os.path.join(os.path.abspath(data_root), "data", "jobs", run_id)
    os.makedirs(os.path.join(job_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(job_dir, "asr"), exist_ok=True)
    manifest_path = os.path.join(job_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump({"job_id": run_id, "source_id": source_id, "run_id": run_id,
                       "stage": "app-worker", "state": "WORKING", "receipts": [],
                       "created_at": _utc_now_iso()}, fh, ensure_ascii=False, indent=2)

    def _receipt(state: str, verdict: str, extra: dict | None = None) -> dict:
        from stage3 import lineage as _lineage  # noqa: E402  (只读复用)

        entry = {"stage": "app-worker", "state": state, "run_id": run_id,
                 "source_id": source_id, "verdict": verdict,
                 "created_at": _utc_now_iso()}
        if extra:
            entry.update(extra)
        try:
            _lineage.record_lineage_manifest(manifest_path, receipts=[entry])
        except Exception:
            pass
        return entry

    # 1. 转写（阻塞调用：进前先写 current，出后推进到下一阶段；终态统一清）
    _worker_set_current(run_id, filename, STAGE_TRANSCRIBING)
    try:
        # V2.5：用户正词弱引导进 prompt（失败回空，不拦转写）
        try:
            _prompt_terms = _user_prompt_terms(data_root)
        except Exception:
            _prompt_terms = []
        tres = _transcribe_audio(os.path.join(job_dir, "asr"), src_real,
                                 prompt_terms=_prompt_terms)
    except Exception as exc:
        verdict = "听写这段视频失败了：%s→换一个有声音的视频再试，或点重试" % (exc,)
        _receipt("TRANSCRIBE_FAILED", verdict, {"whisper_calls": 0})
        out = {"run_id": run_id, "state": "FAIL", "source_filename": _src_fn,
               "verdict": verdict, "whisper_calls": 0}
        _worker_record(out)
        _worker_clear_current()
        return out
    engine_calls = int(tres.get("engine_calls") or 0)
    text = tres.get("text") or ""
    segments = tres.get("segments") or []
    segments_n = len(segments)
    if not segments:
        segments = [{"text": "（本段无语音内容，转写为空）", "start": 0.0, "end": 0.0}]

    # 2. 组 Raw（过 stage1 schema 门）并落盘
    from stage1.asr import FROZEN_MODEL_REPO, FROZEN_MODEL_REVISION  # noqa: E402
    from stage1.prepare import build_raw_content, validate_raw_artifact  # noqa: E402

    content_identity = src.get("content_identity") or ""
    raw_artifact_id = "raw_" + run_id
    post_verify = {"verdict": "PASS", "code": "COMMITTING_RAW_ASR",
                   "current_hash": content_identity, "hash_match": True,
                   "commit_authorized": True}
    asr_profile = {
        "actual": {"model": FROZEN_MODEL_REPO, "model_revision": FROZEN_MODEL_REVISION,
                   "audio_mode": "temp", "word_timestamps": False,
                   "no_speech_threshold": 0.6},
        "frozen": {"model": FROZEN_MODEL_REPO, "model_revision": FROZEN_MODEL_REVISION,
                   "audio": "temp-wav 16k mono (FFmpeg on-disk, re-runnable)"},
    }
    try:
        raw_content = build_raw_content(
            run_id, {"source_id": source_id, "content_identity": content_identity},
            text, segments, asr_profile, post_verify)
        validate_raw_artifact(raw_content)
    except Exception as exc:
        verdict = "整理初稿时数据异常：%s→换一个视频再试，或点重试" % (exc,)
        _receipt("RAW_FAILED", verdict, {"whisper_calls": engine_calls})
        out = {"run_id": run_id, "state": "FAIL", "source_filename": _src_fn,
               "verdict": verdict,
               "whisper_calls": engine_calls}
        _worker_record(out)
        _worker_clear_current()
        return out
    raw_path = os.path.join(job_dir, "raw", "raw.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw_content, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    # 3. Norm / Render（stage3 公开 API）
    # Norm 用用户词库 profile（新转写自动应用，Case4 语义），
    # Render 用 stage9 分段 profile（para-v2.7 目标220/封顶450/防碎80，单源头）。
    from stage3 import normalize as _norm  # noqa: E402  (只读复用)
    from stage3 import render as _rend  # noqa: E402  (只读复用)

    if ob_vault_root:
        try:
            # V2.3 P0-3：app侧单扩展名包装（src零碰；只影响新产出，旧md不动）
            mapping = _app_resolve_canonical(input_real, vault_real, src_real)
            canonical_probe = mapping["canonical_output_path"]
            source_rel = mapping["source_relative_path"]
        except Exception as exc:
            verdict = "笔记库路径映射失败：%s→检查库目录是否存在与可写，修正后点重试" % (exc,)
            _receipt("MIRROR_FAILED", verdict, {"whisper_calls": engine_calls})
            out = {"run_id": run_id, "state": "FAIL", "source_filename": _src_fn,
                   "verdict": verdict,
                   "whisper_calls": engine_calls}
            _worker_record(out)
            _worker_clear_current()
            return out
    else:
        canonical_probe = None
        source_rel = None

    _worker_set_current(run_id, filename, STAGE_NORMALIZING)
    con = store.open_db(data_root)
    try:
        norm = _norm.create_normalization_revision(
            con, job_dir, raw_artifact_id,
            _norm_profile_for_new_jobs(data_root),
            source_id=source_id, run_id=run_id)
        _worker_set_current(run_id, filename, STAGE_RENDERING)
        stem = os.path.splitext(os.path.basename(src_real))[0] or run_id
        _render_profile = _render_profile_for_new_jobs()
        rend = _rend.create_render_revision(
            con, job_dir, norm["normalized_artifact_id"],
            _render_profile,
            title=stem, canonical_probe_path=canonical_probe,
            source_id=source_id, run_id=run_id)
        # 生产后处理（新转写入口）：冻结引擎已 mint 不断链，app 侧用
        # render_with_v2 重算覆写，阈值取 stage9.PARA_PARAMS_V2 单源头
        # （para-v2.7：目标220/封顶450/防碎80）。
        try:
            _fix = _apply_v25_postpass(
                job_dir, norm.get("final_path"), rend.get("final_path"),
                stem, _render_profile)
            try:
                _receipt("V25_POSTPASS",
                         "后处理 fixed=%s paras=%s max=%s" % (
                             _fix.get("fixed"), _fix.get("paras"),
                             _fix.get("max_len")),
                         {"whisper_calls": engine_calls,
                          "render_revision_id": rend.get("render_revision_id"),
                          "v25_fixed": bool(_fix.get("fixed"))})
            except Exception:
                pass
        except Exception:
            pass
        con.execute(
            "UPDATE processing_runs SET raw_artifact_id=?,"
            " initial_normalization_revision_id=?, initial_render_revision_id=?,"
            " updated_at=? WHERE run_id=?",
            (raw_artifact_id, norm["normalization_revision_id"],
             rend["render_revision_id"], store.utc_now_iso(), run_id),
        )
        con.commit()
    except Exception as exc:
        try:
            con.rollback()
        except Exception:
            pass
        con.close()
        verdict = "整理成稿失败：%s→点重试再试一次，或换一个视频" % (exc,)
        _receipt("NORM_RENDER_FAILED", verdict, {"whisper_calls": engine_calls})
        out = {"run_id": run_id, "state": "FAIL", "source_filename": _src_fn,
               "verdict": verdict,
               "whisper_calls": engine_calls}
        _worker_record(out)
        _worker_clear_current()
        return out

    # 4. 入库（笔记库为空则只存数据目录）
    # P0-4：DB processing_runs.status 保持 Stage2 枚举（QUEUED/FAILED_RETRYABLE/
    # NO_SPEECH_DETECTED），不直接写 PUBLISHED/RENDER_ONLY（会触发
    # assert_no_transcription_states FAIL）；终态由 worker.processed 透出，
    # 页面做终态映射显示，保证 runs 表不再全 QUEUED 误导。
    if not ob_vault_root:
        verdict = ("未填笔记库，已生成初稿→初稿在数据目录：%s" % (rend.get("final_path"),))
        _receipt("RENDER_ONLY", verdict,
                 {"whisper_calls": engine_calls,
                  "render_revision_id": rend.get("render_revision_id"),
                  "rendered_path": rend.get("final_path"),
                  "render_verdict": rend.get("verdict")})
        con.close()
        out = {"run_id": run_id, "state": "RENDER_ONLY", "source_filename": _src_fn,
               "verdict": verdict,
               "whisper_calls": engine_calls,
               "rendered_path": rend.get("final_path")}
        _worker_record(out)
        _worker_clear_current()
        return out

    _worker_set_current(run_id, filename, STAGE_PUBLISHING)
    try:
        from stage4.publish import initial_publish  # noqa: E402  (只读复用)
        pub = initial_publish(con, job_dir, rend["render_revision_id"],
                              vault_real, source_rel)
        status = pub.get("status")
        # V2.3 P0-3：新产出单扩展名（09.xxx.mp4→09.xxx.md），旧md不动不改名，如实注明。
        _naming_note = "（命名：去扩展名单.md，如 09.xxx.mp4→09.xxx.md；旧文件不动）"
        if status == "PUBLISHED":
            verdict = "已存入你的笔记库：%s%s" % (
                pub.get("canonical_output_path"), _naming_note)
            state = "PUBLISHED"
        else:
            verdict = "入库未完成，初稿已保留%s→检查笔记库权限后点重试" % (_naming_note,)
            state = "PUBLISH_BLOCKED"
        _receipt(state, verdict,
                 {"whisper_calls": engine_calls,
                  "render_revision_id": rend.get("render_revision_id"),
                  "rendered_path": rend.get("final_path"),
                  "publish_record_id": pub.get("publish_record_id"),
                  "canonical_output_path": pub.get("canonical_output_path"),
                  "publish_status": status})
        out = {"run_id": run_id, "state": state, "source_filename": _src_fn,
               "verdict": verdict,
               "whisper_calls": engine_calls,
               "rendered_path": rend.get("final_path"),
               "canonical_output_path": pub.get("canonical_output_path")}
        _worker_record(out)
        _worker_clear_current()
        return out
    except Exception as exc:
        # 入库受阻等：字节未动，初稿保留，记 verdict 不炸 worker
        verdict = "笔记库不可写：%s→检查库路径权限后点重试" % (exc,)
        _receipt("PUBLISH_BLOCKED", verdict,
                 {"whisper_calls": engine_calls,
                  "render_revision_id": rend.get("render_revision_id"),
                  "rendered_path": rend.get("final_path")})
        out = {"run_id": run_id, "state": "PUBLISH_BLOCKED",
               "source_filename": _src_fn,
               "verdict": verdict,
               "whisper_calls": engine_calls,
               "rendered_path": rend.get("final_path")}
        _worker_record(out)
        _worker_clear_current()
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass


def _transcribe_worker(data_root: str, input_root: str, ob_vault_root: str | None,
                       profile_hash: str) -> None:
    """单 worker 串行：只取源在当前视频文件夹内的 QUEUED AUTO run。

    查询时按 source.current_path realpath 前缀过滤；不在当前
    文件夹的直接忽略（不计数、不记 processed、不进 done、不打扰）。
    每轮只处理新增（_worker_done 去重），未见新 run 则 sleep 等待。
    P1-2：磁盘已有成功输出直接跳过（不重转），失败可重试。
    V2.2补修 P0-2：DB已COMPLETED旧账同步跳过（磁盘缺口补齐，不得重转；
    whisper不再跑；显式重试可经 /api/retry 重排）。
    P1-1：未知异常补 FAIL 记录再进 done，不静默丢任务。
    """
    from stage2 import store  # noqa: E402  (只读复用)

    with _state_lock:
        _worker["running"] = True
    try:
        input_real = os.path.realpath(input_root)
        while True:
            with _state_lock:
                keep = _listener["running"]
            if not keep:
                break
            # 每轮读一次磁盘成功集，供跳过已完成（重启不重转）
            try:
                disk_ok = _scan_disk_states(str(data_root))
                disk_done_ids = {k for k, v in disk_ok.items()
                                 if isinstance(v, dict) and v.get("state") in DONE_STATES}
            except Exception:
                disk_done_ids = set()
            # V2.2补修 P0-2：DB成功旧账（norm COMPLETED）缺口补齐
            try:
                db_done_ids = _db_success_run_ids_ro(str(data_root), str(input_root))
            except Exception:
                db_done_ids = set()
            skip_old = set(disk_done_ids) | set(db_done_ids)
            try:
                con = store.open_db(data_root)
                try:
                    rows = con.execute(
                        "SELECT pr.run_id, s.current_path FROM processing_runs pr"
                        " LEFT JOIN sources s ON pr.source_id=s.source_id"
                        " WHERE pr.status='QUEUED' AND pr.creation_mode='AUTO'"
                        " ORDER BY pr.created_at"
                    ).fetchall()
                    run_ids = []
                    for r in rows:
                        run_id = r[0]
                        cur = r[1] if len(r) > 1 else None
                        if cur is None:
                            # 孤儿 run：保留给 _process_one_run 记 FAIL
                            run_ids.append(run_id)
                            continue
                        if _is_under_root(str(cur), input_real):
                            run_ids.append(run_id)
                        # 不在当前文件夹：直接忽略，不计数不记录
                finally:
                    con.close()
            except Exception as exc:
                _worker_note_error("轮询待处理任务失败：%s" % (exc,))
                run_ids = []
            for run_id in run_ids:
                with _state_lock:
                    keep = _listener["running"]
                if not keep:
                    break
                if run_id in _worker_done:
                    continue
                # P1-2 + V2.2 P0-2：磁盘/DB已有成功输出则跳过（记 done，不重转）
                if run_id in skip_old:
                    with _state_lock:
                        _worker_done.add(run_id)
                    continue
                res = None
                try:
                    res = _process_one_run(data_root, input_root, ob_vault_root,
                                           run_id, profile_hash)
                    # 防守回来的 SKIP（旧文件夹残留）：不进 done，下轮
                    # 查询过滤已会忽略，此处不计数不记录。
                    if isinstance(res, dict) and res.get("state") == "SKIP":
                        continue
                except Exception as exc:  # noqa: BLE001  (单 run 失败不炸 worker)
                    # V2.3 P0-1：面向用户文案用文件名（查不到回未知文件，不暴露裸run_id）
                    try:
                        _fm = _run_source_path_map(str(data_root)).get(run_id)
                        _ffn = (os.path.basename(str(_fm).strip())
                                if isinstance(_fm, str) and str(_fm).strip()
                                else "未知文件") or "未知文件"
                    except Exception:
                        _ffn = "未知文件"
                    _worker_note_error("任务 %s 处理时遇到意外：%s" % (_ffn, exc))
                    _worker_clear_current()
                    # P1-1：未知异常补 FAIL 记录再进 done
                    try:
                        res = {"run_id": run_id, "state": "FAIL",
                               "source_filename": _ffn,
                               "verdict": "处理时遇到意外：%s→点重试再试一次" % (exc,)}
                        _worker_record(dict(res))
                    except Exception:
                        try:
                            res = {"run_id": run_id, "state": "FAIL",
                                   "source_filename": "未知文件",
                                   "verdict": "处理时遇到意外→点重试再试一次"}
                        except Exception:
                            res = None
                # 统一收口：非 SKIP 才记 done；SKIP 已 continue
                try:
                    is_skip = isinstance(res, dict) and res.get("state") == "SKIP"
                except Exception:
                    is_skip = False
                if not is_skip:
                    with _state_lock:
                        _worker_done.add(run_id)
            for _ in range(50):  # 5s 间隔，可被停机打断
                with _state_lock:
                    keep = _listener["running"]
                if not keep:
                    break
                threading.Event().wait(0.1)
    finally:
        with _state_lock:
            _worker["running"] = False
            _worker["current"] = None


def _launch(data_root: str, input_root: str, ob_vault_root: str | None,
            profile_hash: str) -> None:
    """后台线程目标：run_startup 成功后起转写 worker；跑完即更新状态。

    V2.2补修 P0-1/P0-3：全终态放行记 skipped（verdict/绿条用）；
    GATE_STAGE3_BLOCKED 只在真半截时由 _humanize_startup_error 产出。
    """
    import datetime

    with _state_lock:
        _listener["started_at"] = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    try:
        # P0-1：启动前按当前 input 安装作用域断言（他 input 历史行不再卡门）
        _install_scoped_gates(input_root)
        try:
            handle = run_startup(data_root, input_root, profile_hash)
        finally:
            _restore_scoped_gates()
    except Exception as exc:  # noqa: BLE001  (错误进状态，不炸进程)
        msg, code, sugg = _humanize_startup_error(exc, data_root)
        with _state_lock:
            _listener["running"] = False
            _listener["error"] = msg
            _listener["error_code"] = code
            _listener["suggested_data_root"] = sugg
            # 真半截才 BLOCK：失败时清旧账计数，避免绿条残留
            _listener["skipped_terminal"] = 0
            _listener["skipped_terminal_rows"] = 0
            _listener["startup_note"] = None
        return
    # 全终态放行：门内 skipped 落 _STARTUP_SCOPE，换算成人话进 _listener
    try:
        _rows = int(_STARTUP_SCOPE.get("skipped_terminal_rows") or 0)
    except Exception:
        _rows = 0
    try:
        _runs = int(_STARTUP_SCOPE.get("skipped_terminal_runs") or 0)
    except Exception:
        _runs = 0
    # P0-2 缺口：DB成功旧账预进 done，首轮 pending 即排除旧完成（不重转）
    try:
        _pre_skip = _db_success_run_ids_ro(str(data_root), str(input_root))
    except Exception:
        _pre_skip = set()
    try:
        _disk_pre = _scan_disk_states(str(data_root))
        _pre_disk = {k for k, v in _disk_pre.items()
                     if isinstance(v, dict) and v.get("state") in DONE_STATES}
    except Exception:
        _pre_disk = set()
    try:
        _pre_all = set(_pre_skip) | set(_pre_disk)
    except Exception:
        _pre_all = set()
    # 绿条 N 取旧完成视频数（run 去重；无 run 但有终态行时回落行数）
    _n = len(_pre_all) if _pre_all else (_runs if _runs else _rows)
    try:
        _note = ("旧%d条已完成记录，本次跳过" % (_n,)) if _n > 0 else None
    except Exception:
        _note = None
    with _state_lock:
        _listener["error"] = None
        _handle["box"] = handle
        _listener["skipped_terminal"] = int(_n or 0)
        _listener["skipped_terminal_rows"] = int(_rows or 0)
        _listener["startup_note"] = _note
        try:
            for _rid in _pre_all:
                _worker_done.add(_rid)
        except Exception:
            pass
    # run_startup 返回后 watcher/workers 常驻（daemon 线程）；running 保持 True。
    # P0-5：转写 worker 单线程串行，常驻轮询 QUEUED 的 AUTO run。
    worker = threading.Thread(
        target=_transcribe_worker,
        args=(data_root, input_root, ob_vault_root, profile_hash),
        name="v2o-transcribe-worker", daemon=True,
    )
    worker.start()


def _handle_start_post(body: bytes) -> tuple[int, dict]:
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    with _state_lock:
        if _listener["running"]:
            return 409, {"ok": False, "error": "已经在监听同一文件夹，无需重复操作"}

    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    input_root = normalize_path(params.get("input_root"))
    ob_vault_root = normalize_path(params.get("ob_vault_root"))
    profile_hash = str(params.get("asr_profile_hash") or DEFAULT_PROFILE_HASH)

    if not os.path.isabs(data_root):
        return 400, {"ok": False, "error": "数据目录须为绝对路径，请点浏览重选"}
    if not input_root:
        return 400, {"ok": False, "error": "请填写视频文件夹绝对路径"}
    if not os.path.isabs(input_root):
        return 400, {"ok": False, "error": "视频文件夹须为绝对路径：%s，请点浏览重选" % (input_root,)}
    if not os.path.isdir(input_root):
        return 400, {"ok": False, "error": "视频文件夹路径不存在：%s，请点浏览重选" % (input_root,)}
    vault: str | None = ob_vault_root or None
    if vault is not None:
        if not os.path.isabs(vault):
            return 400, {"ok": False, "error": "笔记库目录须为绝对路径：%s，请点浏览重选" % (vault,)}
        if not os.path.isdir(vault):
            return 400, {"ok": False, "error": "笔记库目录不存在：%s，请点浏览重选" % (vault,)}
    try:
        os.makedirs(os.path.join(os.path.abspath(data_root), "data"), exist_ok=True)
    except OSError as exc:
        return 400, {"ok": False, "error": "数据目录不可用：%s，请检查权限" % (exc,)}

    # 人话预检：转写必须在就绪的 python 下跑（probe，不 hard 依赖）
    if not _mlx_available():
        return 400, {"ok": False, "code": CODE_MLX_MISSING,
                     "error": "转写环境没就绪：请用自带一键启动重开，再点开始监听"}

    with _state_lock:
        _listener.update(
            {"running": True, "data_root": data_root,
             "input_root": input_root, "ob_vault_root": vault, "error": None,
             "error_code": None, "suggested_data_root": None,
             "skipped_terminal": 0, "skipped_terminal_rows": 0,
             "startup_note": None}
        )
        _last_config.update(
            {"last_input_root": input_root, "last_data_root": data_root,
             "last_ob_vault_root": vault}
        )
        _worker_done.clear()
        _worker["processed"] = []
        _worker["current"] = None
        _worker["last_error"] = None
    thread = threading.Thread(
        target=_launch, args=(data_root, input_root, vault, profile_hash), daemon=True
    )
    thread.start()
    return 202, {"ok": True, "running": True,
                 "data_root": data_root, "input_root": input_root,
                 "ob_vault_root": vault}


def _handle_stop_post(body: bytes) -> tuple[int, dict]:
    """UX-P0-2/UX2-P1-6：停监听＋停 worker 轮询；当前任务会跑完收尾。

    实现真相（写死）：停在“接新任务”这一层——正在转的这一个会跑完收尾
    （不清 current、不假报 worker 停），worker 线程收尾后自行清 current 并退出。
    因此这里不立即清 _worker["current"]，由前端据 current 显示“正在收尾…”，
    current 清空即为真停（重起后已完成跳过、半截重转）。
    """
    with _state_lock:
        was = bool(_listener.get("running"))
        _listener["running"] = False
        _listener["error"] = None
        _listener["error_code"] = None
        _listener["suggested_data_root"] = None
        box = _handle.get("box")
    # 停 watcher/workers（best-effort，不炸）；app 自己的 worker 线程按 listener 标志退出
    try:
        if isinstance(box, dict):
            try:
                from stage5.startup import shutdown as _shutdown  # noqa: E402
                _shutdown(box)
            except Exception:
                try:
                    w = box.get("watcher")
                    if w is not None:
                        w.stop()
                except Exception:
                    pass
                try:
                    ws = box.get("workers")
                    if ws is not None:
                        ws.stop()
                except Exception:
                    pass
    except Exception:
        pass
    with _state_lock:
        _handle["box"] = None
        cur = dict(_worker["current"]) if _worker.get("current") else None
    finishing = bool(cur and cur.get("run_id"))
    if finishing:
        msg = ("已停止接新任务，当前这个（%s）会跑完收尾；"
               "重起后已完成跳过、半截重转。" % (cur.get("filename") or "当前任务",))
    else:
        msg = "已停止接新任务；重起后已完成跳过、半截重转。"
    return 200, {"ok": True, "running": False, "was_running": was,
                 "finishing": finishing, "current": cur, "message": msg}


def _handle_retry_post(body: bytes) -> tuple[int, dict]:
    """UX-P0-4/P1-1：单 run 重跑，幂等（同 run 去重，不产生重复任务）。"""
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象，点重试再试一次"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象，点重试再试一次"}
    run_id = str(params.get("run_id") or "").strip()
    if not run_id:
        return 400, {"ok": False, "error": "缺少任务编号，请刷新后点重试"}
    with _state_lock:
        running = bool(_listener.get("running"))
        cur = dict(_worker["current"]) if _worker.get("current") else None
        data_root = _listener.get("data_root")
    if not running:
        return 400, {"ok": False, "error": "监听未启动，先点开始监听再点重试"}
    if cur and cur.get("run_id") == run_id:
        return 202, {"ok": True, "run_id": run_id, "state": "RUNNING",
                     "message": "该任务正在处理，无需重复操作"}
    # 已在排队（不在 done）则幂等直接回
    with _state_lock:
        already_queued = run_id not in _worker_done
    # 查 DB 是否存在该 run（只读校验，不写库）
    try:
        if data_root:
            from stage2 import store as _store  # noqa: E402
            con = _store.open_db(str(data_root))
            try:
                row = con.execute(
                    "SELECT run_id FROM processing_runs WHERE run_id=?", (run_id,)
                ).fetchone()
            finally:
                try:
                    con.close()
                except Exception:
                    pass
            if row is None:
                return 404, {"ok": False, "error": "任务不存在，请刷新后重试"}
    except Exception:
        # DB 暂时不可读则仍允许重试（worker 下轮会记原因），不拦
        pass
    with _state_lock:
        if run_id in _worker_done:
            _worker_done.discard(run_id)
            # 删掉旧终态，下轮新结果覆盖，计数不翻倍
            _worker["processed"] = [p for p in _worker["processed"]
                                    if not (isinstance(p, dict) and p.get("run_id") == run_id)]
            return 202, {"ok": True, "run_id": run_id, "state": "QUEUED",
                         "message": "已重新排队，只重跑这一个"}
        else:
            return 202, {"ok": True, "run_id": run_id, "state": "QUEUED",
                         "message": "该任务已在排队，无需重复操作"}


def _handle_clear_post(body: bytes) -> tuple[int, dict]:
    """UX2-P0-2/P1-3：清空本目录任务（先明示代价、可只清失败、给撤销指引）。

    删当前 input 的 discovery_candidates + processing_runs 记录级联
    （artifacts / Stage3+ 修订 / publish_records / archive / state_events
    中归属本 input 的行 + 本 input run 的 data/jobs/<run_id> 目录 +
    内存 worker 痕迹）。源视频文件不动、vault md 不动、他 input 的行不动、
    其他 data_root 不动。删完后重起监听会把文件当新任务重新发现（可重转）。

    - dry_run=true：只读算代价（将删 DB N 条＋jobs M 个 / 成功A失败B排队C /
      预计重转约 X 分钟），不写库、不删盘，供“清空前明示代价”。
    - only_failed=true：只删失败 run 及其修订链与 jobs，成功记录保留。
    - P1-3：运行中拒清（409人话，需先停止）；空归属/NULL archive 纳入清理
      （门侧 fail-closed 计挡住，清理侧同步可清，否则清不掉却挡门不一致）。
    """
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    input_root = normalize_path(params.get("input_root"))
    dry_run = bool(params.get("dry_run"))
    only_failed = bool(params.get("only_failed"))
    if not os.path.isabs(data_root):
        return 400, {"ok": False, "error": "数据目录须为绝对路径，请点浏览重选"}
    if not input_root:
        return 400, {"ok": False, "error": "请填写要清空的视频文件夹绝对路径"}
    if not os.path.isabs(input_root):
        return 400, {"ok": False, "error": "视频文件夹须为绝对路径，请点浏览重选"}
    db_path = os.path.join(os.path.abspath(data_root), "data", "state.db")
    if not os.path.isfile(db_path):
        return 404, {"ok": False,
                     "error": "该数据目录下还没有任务库，无需清空：%s" % (db_path,)}

    # ---- dry_run：只读算代价，不写库、不删盘 ----
    if dry_run:
        con = _open_ro(data_root)
        if con is None:
            return 500, {"ok": False,
                         "error": "任务库暂时读不出，请稍后重试或检查数据目录"}
        try:
            plan = _clear_plan(con, data_root, input_root, only_failed=False)
        except Exception as exc:
            return 500, {"ok": False,
                         "error": "核对清空代价失败：%s，稍后重试" % (exc,)}
        finally:
            try:
                con.close()
            except Exception:
                pass
        if not plan.get("exists"):
            return 200, {"ok": True, "dry_run": True, "no_tasks": True,
                         "data_root": data_root, "input_root": input_root,
                         "message": "本目录下没有任务记录，无需清空"}
        full_runs = len(plan["run_ids"])
        full_jobs = _count_job_dirs(data_root, plan["run_ids"])
        of_runs = len(plan["fail_run_ids"])
        of_jobs = _count_job_dirs(data_root, plan["fail_run_ids"])
        preview = {
            "db_runs": full_runs, "jobs": full_jobs,
            "total": plan["total"], "success": plan["success"],
            "failed": plan["failed"], "pending": plan["pending"],
            "est_retranscribe_minutes": _est_retranscribe_minutes(full_runs),
            "avg_sec_per_video": CLEAR_AVG_SEC_PER_VIDEO,
            "only_failed": {
                "db_runs": of_runs, "jobs": of_jobs,
                "est_retranscribe_minutes": _est_retranscribe_minutes(of_runs),
                "kept_success": plan["success"],
            },
            "vault_note": "笔记库 md 与源视频不动",
        }
        msg = ("将删DB %d条＋jobs %d个；vault md 与源视频不动；"
               "重起需重转约%d分钟（按每条约%d秒估算）。"
               % (full_runs, full_jobs,
                  preview["est_retranscribe_minutes"],
                  CLEAR_AVG_SEC_PER_VIDEO))
        if plan["failed"] > 0:
            msg += ("失败%d条建议先在失败行逐条点「重试」，确需清空再清。"
                    % (plan["failed"],))
        return 200, {"ok": True, "dry_run": True, "data_root": data_root,
                     "input_root": input_root, "preview": preview,
                     "message": msg}

    # ---- 实清：运行中拒清（P1-3），需先停止 ----
    with _state_lock:
        if _listener.get("running"):
            return 409, {"ok": False,
                         "error": "正在监听/转写中，请先点停止再清空（运行中清空会丢任务）"}

    # 开库：锁在手则走 store 门，否则直连读写（同进程，busy 等待），禁碰他库
    con = None
    try:
        from stage2 import store as _st  # noqa: E402

        if _st.is_held(data_root):
            con = _st.open_db(data_root)
    except Exception:
        con = None
    if con is None:
        try:
            con = sqlite3.connect(db_path, timeout=30.0,
                                  check_same_thread=False)
            con.execute("PRAGMA busy_timeout=30000")
            con.execute("PRAGMA foreign_keys=ON")
            con.row_factory = sqlite3.Row
        except Exception as exc:
            return 500, {"ok": False,
                         "error": "任务库打开失败：%s，稍后重试" % (exc,)}
    cleared = {"sources": 0, "runs": 0, "candidates": 0, "artifacts": 0,
               "normalization_revisions": 0, "render_revisions": 0,
               "publish_records": 0, "archive_commits": 0, "state_events": 0,
               "job_dirs": 0}
    plan = None
    run_ids = []
    try:
        plan = _clear_plan(con, data_root, input_root,
                           only_failed=only_failed)
        if not plan.get("exists"):
            try:
                con.close()
            except Exception:
                pass
            return 200, {"ok": True, "data_root": data_root,
                         "input_root": input_root, "cleared": cleared,
                         "only_failed": only_failed,
                         "message": "本目录下没有任务记录，无需清空"}
        eff_srcs = set(plan["srcs_to_del"])
        run_ids = list(plan["run_ids"])
        cand_ids = plan["cand_ids"]
        norm_ids = plan["norm_ids"]
        rend_ids = plan["rend_ids"]
        pub_ids = plan["pub_ids"]
        art_ids = plan["art_ids"]
        entity_ids = set(plan["entity_ids"])
        qmarks = ",".join("?" for _ in eff_srcs) if eff_srcs else None
        s_list = list(eff_srcs)
        rmarks = ",".join("?" for _ in run_ids) if run_ids else None
        con.execute("BEGIN IMMEDIATE")
        try:
            if entity_ids:
                el = list(entity_ids)
                em = ",".join("?" for _ in el)
                cleared["state_events"] = con.execute(
                    "DELETE FROM state_events WHERE entity_id IN (%s)" % em,
                    el).rowcount or 0
            if pub_ids:
                pm = ",".join("?" for _ in pub_ids)
                cleared["publish_records"] = con.execute(
                    "DELETE FROM publish_records WHERE publish_record_id IN (%s)"
                    % pm, pub_ids).rowcount or 0
            if rend_ids:
                rm = ",".join("?" for _ in rend_ids)
                cleared["render_revisions"] = con.execute(
                    "DELETE FROM render_revisions WHERE render_revision_id IN (%s)"
                    % rm, rend_ids).rowcount or 0
            if norm_ids:
                nm = ",".join("?" for _ in norm_ids)
                cleared["normalization_revisions"] = con.execute(
                    "DELETE FROM normalization_revisions"
                    " WHERE normalization_revision_id IN (%s)" % nm,
                    norm_ids).rowcount or 0
            if art_ids:
                am = ",".join("?" for _ in art_ids)
                cleared["artifacts"] = con.execute(
                    "DELETE FROM artifacts WHERE artifact_id IN (%s)" % am,
                    art_ids).rowcount or 0
            if run_ids:
                cleared["runs"] = con.execute(
                    "DELETE FROM processing_runs WHERE run_id IN (%s)" % rmarks,
                    run_ids).rowcount or 0
            if cand_ids:
                cm = ",".join("?" for _ in cand_ids)
                cleared["candidates"] = con.execute(
                    "DELETE FROM discovery_candidates WHERE candidate_id IN (%s)"
                    % cm, cand_ids).rowcount or 0
            if eff_srcs:
                cleared["archive_commits"] = con.execute(
                    "DELETE FROM archive_commits WHERE source_id IN (%s)" % qmarks,
                    s_list).rowcount or 0
            else:
                cleared["archive_commits"] = 0
            # P1-3：NULL archive 门侧计 BLOCK，全清时同步删掉（清不掉却挡门）；
            # UX2-P0-2 只清失败路径不带走 NULL archive（避免误伤其他目录）。
            if not only_failed:
                try:
                    cleared["archive_commits"] += con.execute(
                        "DELETE FROM archive_commits WHERE source_id IS NULL"
                    ).rowcount or 0
                except Exception:
                    pass
            if eff_srcs:
                cleared["sources"] = con.execute(
                    "DELETE FROM sources WHERE source_id IN (%s)" % qmarks,
                    s_list).rowcount or 0
            else:
                cleared["sources"] = 0
            con.commit()
        except Exception:
            try:
                con.rollback()
            except Exception:
                pass
            raise
    except Exception as exc:
        try:
            con.close()
        except Exception:
            pass
        return 500, {"ok": False,
                     "error": "清空失败已回滚：%s，稍后重试" % (exc,)}
    try:
        con.close()
    except Exception:
        pass
    # 本 input run 的 jobs 目录 + 内存痕迹（他 run 不动）
    if run_ids:
        jobs_base = os.path.join(os.path.abspath(data_root), "data", "jobs")
        for rid in run_ids:
            jd = os.path.join(jobs_base, str(rid))
            # 防守：只删 jobs/<run_id> 一层，防路径穿越
            if os.path.abspath(jd).startswith(os.path.abspath(jobs_base) + os.sep):
                try:
                    if os.path.isdir(jd):
                        shutil.rmtree(jd, ignore_errors=True)
                        cleared["job_dirs"] += 1
                except Exception:
                    continue
        with _state_lock:
            doomed = set(str(r) for r in run_ids)
            _worker_done.difference_update(doomed)
            _worker["processed"] = [
                p for p in _worker["processed"]
                if not (isinstance(p, dict)
                        and str(p.get("run_id")) in doomed)]
            try:
                cur = _worker.get("current")
                if isinstance(cur, dict) and str(cur.get("run_id")) in doomed:
                    _worker["current"] = None
            except Exception:
                pass
    kept_success = int((plan or {}).get("kept_success") or 0)
    if only_failed:
        msg = ("已清 %d 条失败记录（成功 %d 条保留），源视频与笔记未动"
               % (cleared["runs"], kept_success))
    else:
        msg = ("已清空本目录 %d 个任务记录（源视频与笔记未动）"
               % (cleared["runs"],))
    undo = ("撤销指引：本次只删本数据目录下的任务记录与 jobs 中间文件，"
            "vault 笔记 md 与源视频未动。清空前若用的是另一个数据目录，"
            "把「数据目录」换回旧路径即可看到旧记录；本目录已删记录无法自动恢复，"
            "但源视频还在，随时可重起重新生成。")
    return 200, {"ok": True, "data_root": data_root, "input_root": input_root,
                 "cleared": cleared, "only_failed": only_failed,
                 "kept_success": kept_success,
                 "message": msg, "undo": undo}


def _handle_reveal_post(body: bytes) -> tuple[int, dict]:
    """V2.4 P0-1：在访达中定位（macOS open -R，后端直开）。

    前端 file:// 导航会被浏览器静默拦截，故改后端直调 open -R。
    normalize + 文件存在校验，失败人话 400。open 子进程仅此处使用。
    """
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    raw = params.get("path")
    path = normalize_path(raw)
    if not path:
        return 400, {"ok": False, "error": "缺少文件路径，请刷新后重试"}
    if not os.path.isabs(path):
        return 400, {"ok": False, "error": "路径须为绝对路径：%s，请刷新后重试" % (raw,)}
    real = os.path.realpath(path)
    if not os.path.exists(real):
        return 400, {"ok": False, "error": "文件找不到了：%s→检查文件是否被移动或删除" % (real,)}
    try:
        import subprocess  # noqa: E402  (open 子进程仅 reveal 一处)

        res = subprocess.run(["open", "-R", real],
                             capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            err = (res.stderr or "").strip()
            return 400, {"ok": False,
                         "error": "在访达中定位失败：%s→检查文件是否存在" % (err or real,)}
        return 200, {"ok": True, "path": real}
    except FileNotFoundError:
        return 400, {"ok": False,
                     "error": "在访达中定位失败：系统 open 命令不可用→检查是否在 macOS 上运行"}
    except Exception as exc:
        return 400, {"ok": False,
                     "error": "在访达中定位失败：%s→检查文件是否存在" % (exc,)}


def _note_user_edited(data_root: str, run_id: str) -> bool:
    """UX2-P1-4：读 jobs/<run_id>/manifest.json 判定 No-Clobber 跳过（只读）。

    命中 publish_status=BLOCKED_OUTPUT_CONFLICT 或 verdict 含“库内…改过/
    跳过”即视为“库内你改过，重跑会跳过”。任何异常回 False（fail-open）。
    """
    try:
        mp = os.path.join(_jobs_dir(data_root), str(run_id), "manifest.json")
        if not os.path.isfile(mp):
            return False
        with open(mp, "r", encoding="utf-8") as fh:
            mani = json.load(fh)
        for r in reversed(mani.get("receipts") or []):
            if not isinstance(r, dict):
                continue
            if str(r.get("publish_status") or "") == "BLOCKED_OUTPUT_CONFLICT":
                return True
            v = str(r.get("verdict") or "")
            if "BLOCKED_OUTPUT_CONFLICT" in v:
                return True
            if "改过" in v and ("跳过" in v or "未覆盖" in v):
                return True
        return False
    except Exception:
        return False


def _handle_note(query: dict) -> tuple[int, dict]:
    """P0-3/V2.3：右侧笔记预览。点行后返回该 run 输出 md 正文（超长截断+注明）。

    无 md 则回所处阶段人话。附 P0-4 两链接（访达 file:// + OB obsidian://）。
    V2.3 P0-2：回显vault_registered布尔（.obsidian是否为目录）。
    """
    run_id = str((query.get("run_id") or [""])[0] or "").strip()
    if not run_id:
        return 400, {"ok": False, "error": "缺少任务编号 run_id，点行后重试"}
    data_root = normalize_path((query.get("data_root") or [""])[0] or "")
    with _state_lock:
        listener_running = bool(_listener.get("running"))
        listener_data = _listener.get("data_root")
        vault_root = _listener.get("ob_vault_root")
    if not data_root:
        data_root = str(listener_data or DEFAULT_DATA_ROOT)
    try:
        _vault_registered = _is_vault_registered(vault_root)
    except Exception:
        _vault_registered = False
    entry, _from_mem = _note_entry_for_run(run_id, data_root)
    state = str((entry or {}).get("state") or "")
    verdict = str((entry or {}).get("verdict") or "")
    md_path = None
    if entry and isinstance(entry, dict):
        if state == "PUBLISHED":
            md_path = entry.get("canonical_output_path") or entry.get("rendered_path")
        elif state in ("RENDER_ONLY", "PUBLISH_BLOCKED", "FAIL"):
            md_path = entry.get("rendered_path") or entry.get("canonical_output_path")
    # UX2-P1-4：No-Clobber 预览状态行（复用后端判定，只读不落盘）
    user_edited = False
    try:
        user_edited = _note_user_edited(data_root, run_id)
    except Exception:
        user_edited = False
    note_hint = None
    try:
        if state == "PUBLISHED":
            note_hint = ("库内你改过，重跑会跳过不覆盖，新稿只留数据目录"
                         if user_edited else "库内未改，重跑会更新")
        elif state == "PUBLISH_BLOCKED" and user_edited:
            note_hint = "库内你改过，重跑会跳过不覆盖，新稿只留数据目录"
    except Exception:
        note_hint = None
    if isinstance(md_path, str) and md_path and os.path.isfile(md_path):
        try:
            with open(md_path, "r", encoding="utf-8", errors="replace") as fh:
                full = fh.read()
        except OSError as exc:
            return 200, {"ok": True, "run_id": run_id, "state": state or "UNKNOWN",
                         "verdict": verdict, "path": md_path,
                         "stage_text": "笔记文件读不出来：%s→检查文件权限" % (exc,),
                         "text": None, "truncated": False, "total_chars": 0,
                         "finder_url": _finder_url(md_path),
                         "ob_url": None,
                         "ob_reason": "笔记文件不可读",
                         "user_edited": user_edited, "note_hint": note_hint,
                         "vault_configured": bool(vault_root),
                         "vault_registered": _vault_registered}
        total = len(full)
        truncated = total > NOTE_MAX_CHARS
        text = full[:NOTE_MAX_CHARS]
        if truncated:
            text += "\n\n…（已截断，全文 %d 字，点「在访达中打开」看完整笔记）" % (total,)
        ob_url, ob_reason = _obsidian_url(vault_root, md_path)
        # V2.3 P0-2：未注册时OB链接不可用，前端禁用+注明先开库
        if not _vault_registered:
            ob_url = None
            ob_reason = "先在OB中把该文件夹打开为仓库后再点"
        return 200, {"ok": True, "run_id": run_id, "state": state,
                     "verdict": verdict, "path": md_path,
                     "stage_text": None, "text": text, "truncated": truncated,
                     "total_chars": total, "finder_url": _finder_url(md_path),
                     "ob_url": ob_url, "ob_reason": ob_reason,
                     "user_edited": user_edited, "note_hint": note_hint,
                     "vault_configured": bool(vault_root),
                     "vault_registered": _vault_registered}
    # 无 md：回阶段人话
    stage_text = _stage_text_zh(run_id, entry, data_root)
    ob_url, ob_reason = _obsidian_url(vault_root, None)
    if not _vault_registered and vault_root:
        # 已配库但未注册：覆盖为注册引导（未配库保持原“未配置笔记库”人话）
        ob_reason = "先在OB中把该文件夹打开为仓库后再点"
    return 200, {"ok": True, "run_id": run_id,
                 "state": state or "QUEUED", "verdict": verdict,
                 "path": (md_path if isinstance(md_path, str) else None),
                 "stage_text": stage_text, "text": None,
                 "truncated": False, "total_chars": 0,
                 "finder_url": (_finder_url(md_path)
                                if isinstance(md_path, str) and md_path else None),
                 "ob_url": ob_url, "ob_reason": ob_reason,
                 "user_edited": user_edited, "note_hint": note_hint,
                 "vault_configured": bool(vault_root),
                 "vault_registered": _vault_registered}


# ------------------------------------------------- V2.5 存量一键重跑
#
# 复用 Case4 语义（Whisper 调用 0、Raw 不变、新 NormRev/新 Render）：
#   derive = stage3.derive.derive_on_correction_change（用户词库 profile
#   + V2.5 render profile；与 stage9 derive_case4 同一 stage3 入口）。
# No-Clobber 延续：已入库任务的新 Render 经 stage4 initial_publish /
# publish_or_block（present canonical 永不覆盖，#51）；用户改过的库内
# md 命中 BLOCKED_OUTPUT_CONFLICT 即跳过并注明，新稿只留数据目录。

REAPPLY_ELIGIBLE = ("RENDER_ONLY", "PUBLISHED", "PUBLISH_BLOCKED")


def _open_rw(data_root: str):
    """读写开中央库：锁在手走 store 门，否则直连（同进程，busy 等待）。

    V2.5 P1-1：缺父目录/缺库文件先抛人话 OSError/FileNotFoundError，
    由 _reapply_one 接管转 JSON（不断连接），不直连抛裸错。
    """
    try:
        from stage2 import store as _st  # noqa: E402

        if _st.is_held(data_root):
            return _st.open_db(data_root)
    except Exception:
        pass
    root = os.path.abspath(str(data_root or ""))
    db_path = os.path.join(root, "data", "state.db")
    parent = os.path.dirname(db_path)
    if not os.path.isdir(parent):
        raise FileNotFoundError(
            "状态库不可读：数据目录不存在（%s），请检查数据目录后刷新重试"
            % (parent,))
    if not os.path.isfile(db_path):
        raise FileNotFoundError(
            "状态库不可读：尚未初始化（%s 缺失），请先开始一次监听或检查数据目录"
            % (db_path,))
    try:
        con = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA foreign_keys=ON")
        con.row_factory = sqlite3.Row
        return con
    except (sqlite3.Error, OSError) as exc:
        raise OSError("状态库不可读：%s，请检查数据目录后刷新重试" % (exc,))


def _append_manifest_receipt(job_dir: str, entry: dict) -> None:
    from stage3 import lineage as _lineage  # noqa: E402  (只读复用记法)

    try:
        _lineage.record_lineage_manifest(
            os.path.join(os.path.abspath(job_dir), "manifest.json"),
            receipts=[entry])
    except Exception:
        pass


def _sha256_file(path: str) -> str | None:
    try:
        import hashlib as _hl

        digest = _hl.sha256()
        with open(path, "rb") as fh:
            while True:
                part = fh.read(8 * 1024 * 1024)
                if not part:
                    break
                digest.update(part)
        return "sha256:" + digest.hexdigest()
    except OSError:
        return None


def _reapply_one(data_root: str, run_id: str,
                 ob_vault_root: str | None = None) -> dict:
    """单个已完成任务应用新词库重跑（Case4：whisper 0、Raw 不变）。

    V2.5 P1-1：_open_rw 与 SELECT 全接管，人话 JSON 不掉线。
    V2.5 P0-1：derive 后经 _apply_v25_postpass 重算覆写（200/MIN 生效）。
    """
    from stage3 import derive as _derive  # noqa: E402  (Case4 同一入口)

    data_root = os.path.abspath(str(data_root or ""))
    run_id = str(run_id or "").strip()
    if not run_id:
        return {"ok": False, "run_id": run_id, "error": "缺少任务编号"}
    try:
        con = _open_rw(data_root)
    except (sqlite3.Error, OSError) as exc:
        return {"ok": False, "run_id": run_id, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "run_id": run_id,
                "error": "状态库不可读：%s，请检查数据目录后刷新重试" % (exc,)}
    try:
        try:
            row = con.execute(
                "SELECT * FROM processing_runs WHERE run_id=?", (run_id,)).fetchone()
        except (sqlite3.Error, OSError) as exc:
            return {"ok": False, "run_id": run_id,
                    "error": "状态库不可读：%s，请检查数据目录后刷新重试" % (exc,)}
        if row is None:
            return {"ok": False, "run_id": run_id,
                    "error": "任务不存在，请刷新后重试"}
        run = dict(row)
        raw_artifact_id = run.get("raw_artifact_id") or ""
        source_id = run.get("source_id")
        if not raw_artifact_id:
            return {"ok": False, "run_id": run_id, "skipped": True,
                    "reason": "该任务没有原文记录，无法重跑（点重试重新转写）"}
        job_dir = os.path.join(data_root, "data", "jobs", run_id)
        raw_path = os.path.join(job_dir, "raw", "raw.json")
        if not os.path.isfile(raw_path):
            return {"ok": False, "run_id": run_id, "skipped": True,
                    "reason": "原文文件找不到了，无法重跑（点重试重新转写）"}
        try:
            disk = _scan_disk_states(data_root).get(run_id)
        except Exception:
            disk = None
        prev_state = str((disk or {}).get("state") or "")
        if prev_state not in REAPPLY_ELIGIBLE:
            return {"ok": False, "run_id": run_id, "skipped": True,
                    "reason": "该任务尚未完成（%s），监听中会自动处理"
                              % (prev_state or "排队中",)}
        try:
            fn_map = _run_source_path_map(data_root)
        except Exception:
            fn_map = {}
        src_path = fn_map.get(run_id) or ""
        try:
            src_fn = os.path.basename(str(src_path).strip()) or "未知文件"
        except Exception:
            src_fn = "未知文件"
        stem = os.path.splitext(src_fn)[0] or run_id
        probe = None
        prev_canon = (disk or {}).get("canonical_output_path")
        if isinstance(prev_canon, str) and prev_canon:
            probe = prev_canon
        raw_before = _sha256_file(raw_path)
        try:
            norm_profile = _norm_profile_for_new_jobs(data_root)
            render_profile = _render_profile_for_new_jobs()
        except ValueError as exc:
            return {"ok": False, "run_id": run_id, "error": str(exc)}
        try:
            out = _derive.derive_on_correction_change(
                con, job_dir, raw_artifact_id, norm_profile,
                render_profile=render_profile, title=stem,
                canonical_probe_path=probe, source_id=source_id,
                run_id=run_id)
        except Exception as exc:
            try:
                con.rollback()
            except Exception:
                pass
            return {"ok": False, "run_id": run_id,
                    "error": "重跑失败已回滚：%s，稍后重试" % (exc,)}
        if int(out.get("whisper_calls") or 0) != 0:
            return {"ok": False, "run_id": run_id,
                    "error": "重跑触碰了转写引擎（whisper!=0），已拦截"}
        raw_after = _sha256_file(raw_path)
        raw_unchanged = (raw_before is not None and raw_before == raw_after)
        if not raw_unchanged:
            return {"ok": False, "run_id": run_id,
                    "error": "原文被改动（Raw 不变断言失败），已拦截"}
        new_rend_rev = str(out.get("render_revision_id") or "")
        new_rendered = os.path.join(job_dir, "render", "%s.md" % (new_rend_rev,))
        if not os.path.isfile(new_rendered):
            return {"ok": False, "run_id": run_id,
                    "error": "新稿文件未生成，请稍后重试"}
        # 生产后处理（重跑入口）：冻结 derive 已 mint 不断链，此处用
        # render_with_v2 重算覆写，阈值取 stage9.PARA_PARAMS_V2 单源头
        # （para-v2.7：目标220/封顶450/防碎80），与 append 入口同源。
        try:
            _norm_rev = str(out.get("normalization_revision_id") or "")
            _norm_path = os.path.join(
                job_dir, "normalized", "%s.json" % (_norm_rev,)) \
                if _norm_rev else None
            _fix = _apply_v25_postpass(
                job_dir, _norm_path, new_rendered, stem, render_profile)
            _postpass = {"applied": bool(_fix.get("fixed")),
                         "already_ok": bool(_fix.get("already_ok")),
                         "paras": _fix.get("paras"),
                         "max_len": _fix.get("max_len")}
            if _fix.get("error") and not _fix.get("fixed") \
                    and not _fix.get("already_ok"):
                _postpass["note"] = str(_fix.get("error"))
        except Exception as exc:
            _postpass = {"applied": False, "note": "后处理异常：%s" % (exc,)}
        result = {"ok": True, "run_id": run_id,
                  "source_filename": src_fn, "prev_state": prev_state,
                  "whisper_calls": 0, "raw_unchanged": True,
                  "normalization_revision_id":
                      out.get("normalization_revision_id"),
                  "render_revision_id": new_rend_rev,
                  "rendered_path": os.path.abspath(new_rendered),
                  "norm_rules_revision":
                      norm_profile.get("correction_rules_revision"),
                  "v25_postpass": _postpass}
        # 入库分支（No-Clobber）：之前已入库且给了笔记库才尝试 publish；
        # present canonical 永不覆盖，BLOCK 即跳过注明。
        vault = (str(ob_vault_root).strip()
                 if isinstance(ob_vault_root, str) and ob_vault_root.strip()
                 else None)
        if prev_state == "PUBLISHED" and vault and isinstance(prev_canon, str):
            try:
                vault_real = os.path.realpath(vault)
                canon_real = os.path.realpath(prev_canon)
                under = (os.path.commonpath([vault_real, canon_real])
                         == vault_real)
            except (ValueError, OSError):
                under = False
            if under and os.path.isdir(vault):
                try:
                    from stage4.publish import initial_publish  # noqa: E402

                    source_rel = os.path.relpath(canon_real, vault_real)
                    pub = initial_publish(con, job_dir, new_rend_rev,
                                          vault_real, source_rel)
                    status = str(pub.get("status") or "")
                    if status == "PUBLISHED":
                        verdict = ("已应用新词库重跑并更新入库：%s"
                                   % (pub.get("canonical_output_path"),))
                        _append_manifest_receipt(job_dir, {
                            "stage": "app-worker", "state": "PUBLISHED",
                            "run_id": run_id, "source_id": source_id,
                            "verdict": verdict,
                            "created_at": _utc_now_iso(),
                            "whisper_calls": 0,
                            "render_revision_id": new_rend_rev,
                            "rendered_path": os.path.abspath(new_rendered),
                            "canonical_output_path":
                                pub.get("canonical_output_path")})
                        result.update({
                            "new_state": "PUBLISHED", "note": verdict,
                            "canonical_output_path":
                                pub.get("canonical_output_path")})
                    else:
                        unchanged = bool(pub.get("canonical_bytes_unchanged",
                                                 True))
                        writes = int(pub.get("canonical_writes") or 0)
                        if not unchanged or writes != 0:
                            result.update({
                                "ok": False, "error":
                                "库内文件被改动（No-Clobber 断言失败），已拦截"})
                            return result
                        if status == "BLOCKED_OUTPUT_CONFLICT":
                            note = ("已跳过：库内笔记你改过，未覆盖；"
                                    "新稿在数据目录：%s"
                                    % (os.path.abspath(new_rendered),))
                        else:
                            note = ("内容一致，无需更新；库内未动；"
                                    "新稿在数据目录：%s"
                                    % (os.path.abspath(new_rendered),))
                        _append_manifest_receipt(job_dir, {
                            "stage": "app-worker",
                            "state": "PUBLISH_BLOCKED",
                            "run_id": run_id, "source_id": source_id,
                            "verdict": note, "created_at": _utc_now_iso(),
                            "whisper_calls": 0,
                            "render_revision_id": new_rend_rev,
                            "rendered_path": os.path.abspath(new_rendered),
                            "canonical_output_path": prev_canon,
                            "publish_status": status})
                        result.update({
                            "new_state": "PUBLISH_BLOCKED",
                            "skipped_user_edited":
                                (status == "BLOCKED_OUTPUT_CONFLICT"),
                            "note": note, "publish_status": status,
                            "canonical_unchanged": True})
                except Exception as exc:
                    result.update({
                        "new_state": prev_state,
                        "note": ("新稿已生成在数据目录：%s；入库未试：%s"
                                 % (os.path.abspath(new_rendered), exc))})
                    _append_manifest_receipt(job_dir, {
                        "stage": "app-worker", "state": prev_state,
                        "run_id": run_id, "source_id": source_id,
                        "verdict": result["note"],
                        "created_at": _utc_now_iso(), "whisper_calls": 0,
                        "render_revision_id": new_rend_rev,
                        "rendered_path": os.path.abspath(new_rendered),
                        "canonical_output_path": prev_canon})
            else:
                note = ("新稿已生成在数据目录：%s；库内文件未动"
                        "（未给笔记库或不在库内，不覆盖）"
                        % (os.path.abspath(new_rendered),))
                _append_manifest_receipt(job_dir, {
                    "stage": "app-worker", "state": prev_state,
                    "run_id": run_id, "source_id": source_id,
                    "verdict": note, "created_at": _utc_now_iso(),
                    "whisper_calls": 0, "render_revision_id": new_rend_rev,
                    "rendered_path": os.path.abspath(new_rendered),
                    "canonical_output_path": prev_canon})
                result.update({"new_state": prev_state, "note": note})
        else:
            verdict = "已应用新词库重跑（转写0次，原文未动）：%s" % (
                os.path.abspath(new_rendered),)
            _append_manifest_receipt(job_dir, {
                "stage": "app-worker", "state": prev_state,
                "run_id": run_id, "source_id": source_id,
                "verdict": verdict, "created_at": _utc_now_iso(),
                "whisper_calls": 0, "render_revision_id": new_rend_rev,
                "rendered_path": os.path.abspath(new_rendered),
                "canonical_output_path": prev_canon})
            result.update({"new_state": prev_state, "note": verdict})
        # 内存终态同步（本 session 页面即时可见，不等重启）
        try:
            with _state_lock:
                _worker["processed"] = [
                    p for p in _worker["processed"]
                    if not (isinstance(p, dict)
                            and str(p.get("run_id")) == run_id)]
                mem_state = str(result.get("new_state") or prev_state)
                _worker["processed"].append({
                    "run_id": run_id, "state": mem_state,
                    "source_filename": src_fn,
                    "verdict": str(result.get("note") or ""),
                    "whisper_calls": 0,
                    "rendered_path": result.get("rendered_path"),
                    "canonical_output_path": result.get(
                        "canonical_output_path", prev_canon)})
                _worker["processed"] = _worker["processed"][-100:]
        except Exception:
            pass
        return result
    except (sqlite3.Error, OSError) as exc:
        return {"ok": False, "run_id": run_id,
                "error": "状态库不可读：%s，请检查数据目录后刷新重试" % (exc,)}
    finally:
        try:
            con.close()
        except Exception:
            pass


def _reapply_all(data_root: str, vault_s, progress_cb=None) -> tuple[int, dict]:
    """重跑全部已完成任务（all=true 路径）。

    progress_cb 仅供页面进度回传（(ev) -> None），每篇开跑前/跑完后各回调一次；
    为 None 时行为与旧版逐字一致。
    """
    try:
        disk = _scan_disk_states(data_root)
    except Exception:
        disk = {}
    targets = [rid for rid, v in disk.items()
               if isinstance(v, dict) and v.get("state") in REAPPLY_ELIGIBLE]
    if not targets:
        return 200, {"ok": True, "data_root": data_root, "results": [],
                     "summary": {"total": 0, "ok": 0,
                                 "skipped_user_edited": 0, "failed": 0},
                     "message": "没有可重跑的已完成任务"}
    # R3：只在需要回传进度时查一次 run→文件名 映射；None 时保持旧路径零多余查询
    fn_map = {}
    if progress_cb is not None:
        try:
            fn_map = _run_source_path_map(data_root)
        except Exception:
            fn_map = {}

    def _name(rid: str) -> str:
        try:
            return os.path.basename(str(fn_map.get(rid) or "").strip()) or "未知文件"
        except Exception:
            return "未知文件"

    total = len(targets)
    results = []
    for pos, rid in enumerate(targets):
        if progress_cb is not None:
            try:
                progress_cb({"total": total, "done": pos, "run_id": rid,
                             "filename": _name(rid)})
            except Exception:
                pass
        try:
            results.append(_reapply_one(data_root, rid, vault_s))
        except (sqlite3.Error, OSError) as exc:
            results.append({"ok": False, "run_id": rid,
                            "error": "状态库不可读：%s，请检查数据目录后刷新重试"
                                     % (exc,)})
        except Exception as exc:
            results.append({"ok": False, "run_id": rid,
                            "error": "重跑失败：%s，稍后重试" % (exc,)})
        if progress_cb is not None:
            try:
                last = results[-1] if isinstance(results[-1], dict) else {}
                progress_cb({"total": total, "done": pos + 1, "run_id": rid,
                             "filename": str(last.get("source_filename")
                                             or _name(rid))})
            except Exception:
                pass
    summary = {"total": len(results),
               "ok": sum(1 for r in results if r.get("ok")),
               "skipped_user_edited": sum(
                   1 for r in results if r.get("skipped_user_edited")),
               "failed": sum(1 for r in results if not r.get("ok"))}
    return 200, {"ok": True, "data_root": data_root, "results": results,
                 "summary": summary,
                 "message": "重跑 %d 个：成功 %d，库内你改过跳过 %d，失败 %d"
                            % (summary["total"], summary["ok"],
                               summary["skipped_user_edited"],
                               summary["failed"])}


def _handle_reapply_post(body: bytes, progress_cb=None) -> tuple[int, dict]:
    """存量一键重跑：单个 run_id 或 all=true（全部已完成）。"""
    try:
        params = json.loads(body.decode("utf-8")) if body.strip() else {}
    except (ValueError, UnicodeDecodeError):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    if not isinstance(params, dict):
        return 400, {"ok": False, "error": "请求体须为 JSON 对象"}
    data_root = normalize_path(params.get("data_root")) or DEFAULT_DATA_ROOT
    vault = params.get("ob_vault_root")
    vault_s = vault.strip() if isinstance(vault, str) and vault.strip() else None
    if params.get("all"):
        return _reapply_all(data_root, vault_s, progress_cb=progress_cb)
    run_id = str(params.get("run_id") or "").strip()
    if not run_id:
        return 400, {"ok": False, "error": "缺少任务编号 run_id（或传 all=true 全跑）"}
    try:
        res = _reapply_one(data_root, run_id, vault_s)
    except (sqlite3.Error, OSError) as exc:
        return 500, {"ok": False, "run_id": run_id,
                     "error": "状态库不可读：%s，请检查数据目录后刷新重试" % (exc,)}
    except Exception as exc:
        return 500, {"ok": False, "run_id": run_id,
                     "error": "重跑失败：%s，稍后重试" % (exc,)}
    if not res.get("ok") and not res.get("skipped") and "error" in res \
            and "任务不存在" in str(res.get("error")):
        return 404, {"ok": False, **res}
    return 200, {"ok": res.get("ok", False), **res}


class Handler(BaseHTTPRequestHandler):
    server_version = "V2OConsole/1.1"

    def log_message(self, fmt, *args):  # noqa: N802  (保持控制台安静)
        sys.stderr.write("v2o-console: %s\n" % (fmt % args,))

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            _serve_index(self)
            return
        if parsed.path == "/api/status":
            code, obj = _handle_status(urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/start":
            _send_json(self, 200, {"ok": True, **_listener_snapshot()})
            return
        if parsed.path == "/api/browse":
            code, obj = _handle_browse(urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/note":
            code, obj = _handle_note(urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/vocab":
            code, obj = _handle_vocab_get(urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/vocab/candidates":
            code, obj = _handle_vocab_candidates_get(
                urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/vocab/candidates/apply/status":
            code, obj = _handle_vocab_apply_status(
                urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        if parsed.path == "/api/vocab/presets":
            code, obj = _handle_vocab_presets_get(
                urllib.parse.parse_qs(parsed.query))
            _send_json(self, code, obj)
            return
        _send_json(self, 404, {"ok": False, "error": "未知路径，请刷新后重试"})

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        # V2.5 P1-1：外层接管，未预见异常回 500 JSON 不掉线。
        try:
            if parsed.path == "/api/start":
                code, obj = _handle_start_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/stop":
                code, obj = _handle_stop_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/retry":
                code, obj = _handle_retry_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/clear":
                code, obj = _handle_clear_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/reveal":
                code, obj = _handle_reveal_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/vocab":
                code, obj = _handle_vocab_add(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/vocab/candidates/apply":
                code, obj = _handle_vocab_candidates_apply(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/vocab/delete":
                code, obj = _handle_vocab_del(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/vocab/presets/import":
                code, obj = _handle_vocab_presets_import(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/vocab/presets/domains":
                code, obj = _handle_vocab_presets_domains_post(body)
                _send_json(self, code, obj)
                return
            if parsed.path == "/api/reapply":
                code, obj = _handle_reapply_post(body)
                _send_json(self, code, obj)
                return
            _send_json(self, 404, {"ok": False, "error": "未知路径，请刷新后重试"})
        except BrokenPipeError:
            pass
        except Exception as exc:
            try:
                _send_json(self, 500, {"ok": False,
                                       "error": "服务开小差：%s，稍后重试" % (exc,)})
            except Exception:
                pass


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("V2O 本机控制台：http://%s:%d/（data_root 默认 %s）" % (HOST, PORT, DEFAULT_DATA_ROOT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
