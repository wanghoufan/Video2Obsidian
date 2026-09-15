#!/usr/bin/env python3
"""builder 自验（DEVELOP-P1-2 任务身份与 API 契约加固）：严格类型层、data_root
与 job_id 绑定、字段一致、候选版本锁、部分更新安全、错误信息安全（D-12）。

红线口径（照 HANDOFF）：
  - 只用**外置 tmp + 合成数据**；不碰用户真实视频目录与 Obsidian 库；
  - 凡调 handler 的用例，首行断言 data_root 在系统 tmp 下（经验 2026-09-13）；
  - 不起 8765、不请求线上服务、不写真实 data/state.db。

运行：python3 tests/selftest_p1_2_contract.py
全过 EXIT=0；任一断言失败 EXIT=1（坏例只看 exit 码，不看打印）。
"""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

TMP_ROOT = os.path.realpath(tempfile.gettempdir())
FAILS = []
CHECKS = [0]


def check(name, cond, detail=""):
    CHECKS[0] += 1
    print(("PASS " if cond else "FAIL ") + name + (("  << " + str(detail)) if (detail and not cond) else ""))
    if not cond:
        FAILS.append(name)


def assert_tmp(root, who):
    """凡调 handler 的用例首行必须过这道门：data_root 必须在系统 tmp 下。"""
    real = os.path.realpath(str(root))
    ok = real.startswith(TMP_ROOT + os.sep) and real != TMP_ROOT
    if not ok:
        raise AssertionError("用例 %s 的 data_root 不在系统 tmp 下：%s" % (who, real))
    return real


def load_server():
    spec = importlib.util.spec_from_file_location(
        "v2o_server_p12", os.path.join(ROOT, "app", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def tree_snapshot(root):
    out = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            if rel.startswith("data" + os.sep + "state.db"):
                continue  # sqlite 副产物单独用 size 判，不参与字节比对
            try:
                out[rel] = sha(p)
            except OSError:
                out[rel] = "UNREADABLE"
    return out


def body(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


# ------------------------------------------------------------------ 夹具

def add_run(con, run_id, src_path, status, aligned=True, source_size=None,
            content_identity=None, identity_from=None):
    """按真 DDL 落一行（processing_runs 无 raw_error_code/reason 列，诊断只读 status）。

    P2-2：`content_identity` 默认仍是旧的 `"x"*40`（既有断言一个都不放松）；需要走通
    「源文件不在原位＋替代位置身份匹配」那条唯一分支的用例传真 sha256。
    `identity_from` 指定 size/mtime 的取材文件（缺省＝`src_path`）——「登记路径无文件、
    文件在替代位置」时，身份三元组必须按替代位置的真文件算，否则 `_diag_identity`
    在第一道 size 比对上就 MISMATCH，永远到不了 MATCH。
    """
    now = "2026-09-14T00:00:00Z"
    event_at = now if aligned else "2026-09-01T00:00:00Z"
    truth = identity_from or src_path
    size = os.path.getsize(truth) if os.path.isfile(truth) else 0
    mtime = os.stat(truth).st_mtime_ns if os.path.isfile(truth) else 0
    con.execute(
        "INSERT INTO sources (source_id, path_identity_key, content_identity,"
        " logical_source_identity, current_path, current_location_type,"
        " source_size, source_mtime_ns, status, first_seen_at, last_seen_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("src_" + run_id, src_path, content_identity or ("x" * 40), "lsid_" + run_id,
         src_path, "LOCAL", size if source_size is None else source_size, mtime,
         "ACTIVE", now, now))
    con.execute(
        "INSERT INTO processing_runs (run_id, source_id, creation_mode,"
        " auto_run_identity, asr_profile_hash, status, created_at, updated_at)"
        " VALUES (?,?,'AUTO',?,?,?,?,?)",
        (run_id, "src_" + run_id, "auto_" + run_id, "profhash", status,
         now, now))
    con.execute(
        "INSERT INTO state_events (event_id, entity_type, entity_id,"
        " from_status, to_status, reason, created_at) VALUES (?,?,?,?,?,?,?)",
        ("ev_" + run_id, "processing_run", run_id, None, status,
         "synthetic", event_at))


def make_data_root(server, tag, runs):
    """建合成 data_root：DDL 直接复用 src/stage2 真 DDL，不另写一套 schema。"""
    from stage2.store import DDL

    root = tempfile.mkdtemp(prefix="p12_%s_" % tag)
    assert_tmp(root, "make_data_root")
    src_dir = os.path.join(root, "_src")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    db = os.path.join(root, "data", "state.db")
    con = sqlite3.connect(db)
    try:
        con.executescript(DDL)
        for spec in runs:
            src = os.path.join(src_dir, spec["run_id"] + ".mp4")
            if spec.get("with_src", True):
                with open(src, "wb") as fh:
                    fh.write(b"fake-media-" + spec["run_id"].encode())
            # P2-2：替代位置（同一 basename）：登记路径**不落文件**，文件放到
            # `root/<alt_dir>/`，身份三元组（size/mtime/sha256）按替代位置的真文件算——
            # 这样才走得到 `_diagnosis_item` 里 identity=MATCH 那条唯一分支（真 16 条）。
            alt_dir = spec.get("alt_dir")
            identity_from = content_identity = None
            if alt_dir:
                payload_bytes = b"fake-media-" + spec["run_id"].encode()
                alt_path = os.path.join(root, alt_dir, os.path.basename(src))
                os.makedirs(os.path.dirname(alt_path), exist_ok=True)
                with open(alt_path, "wb") as fh:
                    fh.write(payload_bytes)
                identity_from = alt_path
                content_identity = hashlib.sha256(payload_bytes).hexdigest()
            add_run(con, spec["run_id"], src, spec["status"],
                    aligned=spec.get("aligned", True),
                    content_identity=content_identity, identity_from=identity_from)
            manifest = spec.get("manifest")
            if manifest:
                job_dir = os.path.join(root, "data", "jobs", spec["run_id"])
                os.makedirs(job_dir, exist_ok=True)
                payload = dict(manifest)
                rendered = payload.get("rendered_path")
                if rendered == "@render":
                    render_dir = os.path.join(job_dir, "render")
                    os.makedirs(render_dir, exist_ok=True)
                    render_file = os.path.join(render_dir, "rev1.md")
                    with open(render_file, "w", encoding="utf-8") as fh:
                        fh.write("# 合成成稿 %s\n" % spec["run_id"])
                    payload["rendered_path"] = render_file
                with open(os.path.join(job_dir, "manifest.json"), "w",
                          encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False)
        con.commit()
    finally:
        con.close()
    return root


def write_candidates(root, entries):
    with open(os.path.join(root, "vocab-candidates.json"), "w",
              encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


RETRY_SPEC = {"run_id": "run-retry", "status": "TRANSCRIBE_FAILED"}
REUSE_SPEC = {"run_id": "run-reuse", "status": "NORM_RENDER_FAILED",
              "manifest": {"raw_path": "@raw", "normalized_path": "@norm",
                           "rendered_path": "@render", "render_revision_id": "rev1"}}
PUB_SPEC = {"run_id": "run-publish", "status": "PUBLISH_BLOCKED",
            "manifest": {"raw_path": "@raw", "normalized_path": "@norm",
                         "rendered_path": "@render", "render_revision_id": "rev1"}}
OK_SPEC = {"run_id": "run-ok", "status": "SUCCEEDED"}
# P2-2：真 16 条那条分支——登记路径无文件（with_src=False），文件落在替代位置 `_alt/`
# 且身份三元组（size/mtime/sha256）与 sources 行一致 → MATCH
ALT_SPEC = {"run_id": "run-alt", "status": "TRANSCRIBE_FAILED",
            "with_src": False, "alt_dir": "_alt"}
# 对照：同样不在原位，但没有任何替代位置命中（不编造替代路径）
NOALT_SPEC = {"run_id": "run-noalt", "status": "TRANSCRIBE_FAILED", "with_src": False}


def build_root_a(server):
    return make_data_root(server, "A", [RETRY_SPEC, REUSE_SPEC, PUB_SPEC, OK_SPEC])


def plan_token_for(server, root, run_ids):
    code, res = server._handle_retry_plan_post(
        body({"data_root": root, "run_ids": run_ids}))
    assert code == 200 and res.get("ok"), (code, res)
    return res


# ------------------------------------------------------------------ 1 严格类型层

BAD_BOOLS = [1, 0, 1.0, "true", "false", "yes", None, [], {}]
BAD_INTS = [True, False, 1.5, 1.0, "3", "0", None, [], {}]


def part1_strict_types(server):
    assert_tmp(server.DEFAULT_DATA_ROOT, "part1_strict_types(default)")
    root = build_root_a(server)
    assert_tmp(root, "part1_strict_types")
    try:
        write_candidates(root, [
            {"wrong": "严格错词A", "right": "严格正词A", "confidence": "high"},
            {"wrong": "严格错词B", "right": "严格正词B", "confidence": "high"},
        ])
        rev = server._vocab_candidates_revision(root)
        vocab_path = os.path.join(root, "vocab-user.json")
        before = tree_snapshot(root)
        db_before = os.path.getsize(os.path.join(root, "data", "state.db"))

        # 1a 坏 JSON / 非对象 / 空体（三个入口）
        for raw in (b"", b"{bad", b"[1,2]", b"null", b"\"x\""):
            for name, fn in (("retry-plan", server._handle_retry_plan_post),
                             ("retry-batch", server._handle_retry_batch_post),
                             ("vocab-apply", server._handle_vocab_candidates_apply)):
                code, res = fn(raw)
                check("1a 坏体 %s.%r -> 400" % (name, raw[:6]), code == 400)
                check("1a 坏体 %s.%r 有人话错误" % (name, raw[:6]),
                      isinstance(res.get("error"), str) and len(res["error"]) > 2)

        # 1b indices：bool / float / str / None 一律 400 + 零执行 + 零写盘
        for bad in BAD_INTS:
            payload = {"data_root": root, "indices": [bad],
                       "rerun_old": False, "candidates_revision": rev}
            code, res = server._handle_vocab_candidates_apply(body(payload))
            check("1b indices=%r -> 400" % (bad,), code == 400, (code, res))
            check("1b indices=%r 有人话" % (bad,),
                  isinstance(res.get("error"), str) and "indices" in res["error"])
            code2, res2 = server._run_vocab_candidates_apply(payload)
            check("1b(同步) indices=%r -> 400" % (bad,), code2 == 400)
        code, res = server._handle_vocab_candidates_apply(
            body({"data_root": root, "indices": "0", "rerun_old": False,
                  "candidates_revision": rev}))
        check("1b indices 非数组 -> 400", code == 400)

        # 1c rerun_old：非布尔不静默当 False
        for bad in BAD_BOOLS:
            payload = {"data_root": root, "indices": [0], "rerun_old": bad,
                       "candidates_revision": rev}
            code, res = server._handle_vocab_candidates_apply(body(payload))
            check("1c rerun_old=%r -> 400" % (bad,), code == 400, (code, res))
            code2, _ = server._run_vocab_candidates_apply(payload)
            check("1c(同步) rerun_old=%r -> 400" % (bad,), code2 == 400)
        check("1c rerun_old 缺键 -> 默认 True（旧 API 行为保留，只直测取参层）",
              server._take_bool({"indices": [0]}, "rerun_old", True) is True)
        check("1c rerun_old=False 正常取到布尔",
              server._take_bool({"rerun_old": False}, "rerun_old", True) is False)

        # 1d data_root 显式 null/数字 -> 400（不静默当默认目录）
        for bad in (None, 1, True, ["x"]):
            code, res = server._handle_vocab_candidates_apply(
                body({"data_root": bad, "indices": [0], "rerun_old": False,
                      "candidates_revision": rev}))
            check("1d data_root=%r -> 400" % (bad,), code == 400, res)
        code, res = server._handle_retry_plan_post(
            body({"data_root": "relative/dir", "run_ids": ["run-retry"]}))
        check("1d 相对 data_root -> 400", code == 400)

        # 1e confirm：非布尔 confirm -> 400 人话（且不回请求体）
        for bad in BAD_BOOLS + [False]:
            code, res = server._handle_retry_batch_post(body({
                "data_root": root, "confirm": bad,
                "plan_token": "SECRET-TOKEN-SHOULD-NOT-ECHO",
                "run_ids": ["run-retry"]}))
            check("1e confirm=%r -> 400" % (bad,), code == 400, (code, res))
            check("1e confirm=%r 不回请求体/令牌" % (bad,),
                  "SECRET-TOKEN" not in json.dumps(res, ensure_ascii=False))

        # 1f clear / reapply 的布尔字段不再 bool() 兜底
        for bad in ("false", 1, None):
            code, res = server._handle_clear_post(body({
                "data_root": root, "input_root": root, "dry_run": bad}))
            check("1f clear dry_run=%r -> 400" % (bad,), code == 400, res)
            code2, res2 = server._handle_clear_post(body({
                "data_root": root, "input_root": root, "only_failed": bad}))
            check("1f clear only_failed=%r -> 400" % (bad,), code2 == 400)
            code3, res3 = server._handle_reapply_post(body({
                "data_root": root, "all": bad}))
            check("1f reapply all=%r -> 400（不再 truthy 触发全量重跑）" % (bad,),
                  code3 == 400, res3)

        # 1g 严格类型全部零执行零写盘
        check("1g 全程 vocab-user.json 未生成/未变",
              os.path.exists(vocab_path) == ("vocab-user.json" in before))
        check("1g 全程目录字节快照未变", tree_snapshot(root) == before)
        check("1g state.db 未被改写",
              os.path.getsize(os.path.join(root, "data", "state.db")) == db_before)
        check("1g 未建任何后台任务", server._vocab_apply_job is None)
        check("1g 未建任何 recovery job 文件",
              not os.path.isdir(os.path.join(root, "data", "recovery_jobs"))
              or not os.listdir(os.path.join(root, "data", "recovery_jobs")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------------------------ 2 目录绑定 / job_id

def part2_binding(server):
    root_a = build_root_a(server)
    root_b = tempfile.mkdtemp(prefix="p12_B_")
    assert_tmp(root_a, "part2_binding.A")
    assert_tmp(root_b, "part2_binding.B")
    try:
        # 2a /api/status 不得忽略 data_root
        code, snap_b = server._handle_status({"data_root": [root_b]})
        text_b = json.dumps(snap_b, ensure_ascii=False)
        check("2a status(rootB) 200 且人话失败（无库）",
              code == 200 and snap_b.get("ok") is False, (code, snap_b))
        check("2a status(rootB) 不返回 rootA 的任务",
              "run-retry" not in text_b and "run-ok" not in text_b)
        check("2a status(rootB) 不回绝对路径", root_a not in text_b)
        code, snap_a = server._handle_status({"data_root": [root_a], "limit": ["200"]})
        check("2a status(rootA) 200", code == 200, (code, snap_a))
        check("2a status(rootA) 只含 rootA（不含 rootB 绝对路径）",
              root_b not in json.dumps(snap_a, ensure_ascii=False))
        code, res = server._handle_status({"data_root": ["relative/x"]})
        check("2a status(相对 data_root) -> 400", code == 400 and res.get("error"))
        code, res = server._handle_status({"data_root": [root_a], "limit": ["abc"]})
        check("2a status(limit=abc) -> 400", code == 400 and res.get("error"))
        code, res = server._handle_status({"data_root": [root_a], "limit": ["1.5"]})
        check("2a status(limit=1.5) -> 400", code == 400)

        # 2b retry-batch status：缺任一 / 未知 job / 跨目录
        code, res = server._handle_retry_batch_status({"job_id": ["rec-1"]})
        check("2b 缺 data_root -> 400 人话", code == 400 and "data_root" in res.get("error", ""))
        code, res = server._handle_retry_batch_status({"data_root": [root_a]})
        check("2b 缺 job_id -> 400 人话", code == 400 and "job_id" in res.get("error", ""))
        code, res = server._handle_retry_batch_status(
            {"data_root": [root_b], "job_id": ["rec-nope"]})
        check("2b 未知 job -> 404 人话", code == 404, (code, res))

        # 2c 真 job：同目录可取，别目录不给数据
        plan = plan_token_for(server, root_a, ["run-reuse"])
        code, job = server._handle_retry_batch_post(body({
            "data_root": root_a, "confirm": True, "plan_token": plan["plan_token"],
            "run_ids": ["run-reuse"]}))
        check("2c batch 202", code == 202 and job.get("ok"), (code, job))
        job_id = str(job.get("job_id"))
        code, got = server._handle_retry_batch_status(
            {"data_root": [root_a], "job_id": [job_id]})
        check("2c 同目录可读终态", code == 200 and got.get("job_id") == job_id, (code, got))
        check("2c job 目录绑定摘要存在", bool(got.get("data_root_digest")))
        check("2c 别目录不给数据（404）",
              server._handle_retry_batch_status(
                  {"data_root": [root_b], "job_id": [job_id]})[0] in (404, 409))
        check("2c 别目录响应不含 job 内容",
              "results" not in json.dumps(server._handle_retry_batch_status(
                  {"data_root": [root_b], "job_id": [job_id]})[1], ensure_ascii=False))
        # 把 A 的 job 文件人为搬到 B（模拟跨目录/被搬文件）→ 必须 409 零渲染
        b_jobs = os.path.join(root_b, "data", "recovery_jobs")
        os.makedirs(b_jobs, exist_ok=True)
        shutil.copyfile(os.path.join(root_a, "data", "recovery_jobs",
                                     "%s.json" % job_id),
                        os.path.join(b_jobs, "%s.json" % job_id))
        code, moved = server._handle_retry_batch_status(
            {"data_root": [root_b], "job_id": [job_id]})
        check("2c 搬到别目录的 job -> 409", code == 409, (code, moved))
        check("2c 搬到别目录的 job 不返回 results", "results" not in moved)

        # 2d 前端轮询带 job_id + data_root：只渲染匹配 job
        write_candidates(root_a, [
            {"wrong": "绑定错词一", "right": "绑定正词一", "confidence": "high"}])
        code, res = server._handle_vocab_candidates_apply(body({
            "data_root": root_a, "indices": [0], "rerun_old": False,
            "candidates_revision": server._vocab_candidates_revision(root_a)}))
        check("2d 候选 apply 202", code == 202 and res.get("job_id"), (code, res))
        vjob = str(res.get("job_id"))
        deadline = time.time() + 30
        while time.time() < deadline:
            with server._state_lock:
                cur = server._vocab_apply_job
                state = (cur or {}).get("state")
            if state and state != "running":
                break
            time.sleep(0.2)
        code, ok_res = server._handle_vocab_apply_status(
            {"data_root": [root_a], "job_id": [vjob]})
        check("2d 同目录+同 job_id 可读", code == 200 and (ok_res.get("job") or {}).get("job_id") == vjob,
              (code, ok_res))
        code, cross_dir = server._handle_vocab_apply_status(
            {"data_root": [root_b], "job_id": [vjob]})
        check("2d 别目录轮询 -> 409 不渲染", code == 409 and cross_dir.get("job") is None,
              (code, cross_dir))
        code, cross_job = server._handle_vocab_apply_status(
            {"data_root": [root_a], "job_id": ["vocab-apply-999-1"]})
        check("2d 别 job_id 轮询 -> 409 不渲染", code == 409 and cross_job.get("job") is None,
              (code, cross_job))
        check("2d 跨目录/跨 job 响应不含他任务内容",
              "details" not in json.dumps(cross_dir, ensure_ascii=False)
              and vjob not in json.dumps(cross_job, ensure_ascii=False))
        code, res = server._handle_vocab_apply_status({"data_root": ["relative/y"]})
        check("2d 相对 data_root -> 400", code == 400)
        code, bare = server._handle_vocab_apply_status({})
        check("2d 无参查询不回明细（job:null，P1-2 契约不回落）",
              code == 200 and bare.get("job") is None
              and bare.get("ok") is True, (code, bare))
        code, only_root = server._handle_vocab_apply_status({"data_root": [root_a]})
        check("2d 只给 data_root（不给 job_id）仍可读本目录任务",
              code == 200 and (only_root.get("job") or {}).get("job_id") == vjob,
              (code, only_root))
    finally:
        shutil.rmtree(root_a, ignore_errors=True)
        shutil.rmtree(root_b, ignore_errors=True)


# ------------------------------------------------------------------ 3 字段一致

def part3_field_consistency(server):
    root = build_root_a(server)
    assert_tmp(root, "part3_field_consistency")
    try:
        # 3a 候选 details：真候选 / 越界 / 重复 / 已导入 / 校验拒收 全在同一分支集
        write_candidates(root, [
            {"wrong": "字段错词一", "right": "字段正词一", "confidence": "high"},
            {"wrong": "已", "right": "已导入条", "confidence": "low",
             "imported": True},
        ])
        code, res = server._run_vocab_candidates_apply({
            "data_root": root, "indices": [0, 0, 99, 1], "rerun_old": False,
            "candidates_revision": server._vocab_candidates_revision(root)})
        details = res.get("details") or []
        check("3a details 非空且覆盖四种分支", len(details) >= 4, details)
        keysets = {frozenset(d.keys()) for d in details}
        check("3a details 各分支键集合一致", len(keysets) == 1, keysets)
        need = {"index", "wrong", "right", "confidence", "evidence",
                "accepted", "decision", "reason"}
        check("3a details 固定键齐备", need.issubset(set(list(keysets)[0])))
        check("3a index 恒为 int",
              all(isinstance(d.get("index"), int) and not isinstance(d.get("index"), bool)
                  for d in details))
        check("3a reason 恒为字符串（无该字段的分支补空串）",
              all(isinstance(d.get("reason"), str) for d in details))
        check("3a accepted/decision 取值合法",
              all(d.get("accepted") in (True, False)
                  and d.get("decision") in ("保留", "拒收") for d in details))

        # 3b 诊断 items：不同 action_category 的行键集合一致
        code, diag = server._handle_failure_diagnosis({"data_root": [root]})
        items = diag.get("items") or []
        check("3b 诊断覆盖多类", len({i.get("action_category") for i in items}) >= 3,
              {i.get("action_category") for i in items})
        dkeys = {frozenset(i.keys()) for i in items}
        check("3b 诊断 items 键集合一致", len(dkeys) == 1, dkeys)

        # 3c retry-batch results：混合分支（门未过 / 策略执行）键集合一致
        plan = plan_token_for(server, root, ["run-retry", "run-reuse", "run-publish"])
        code, job = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": True, "plan_token": plan["plan_token"],
            "run_ids": ["run-retry", "run-reuse", "run-publish"]}))
        results = job.get("results") or []
        check("3c results 每项都有", len(results) == 3, results)
        rkeys = {frozenset(r.keys()) for r in results}
        check("3c results 键集合一致（不因分支缺键）", len(rkeys) == 1, rkeys)
        check("3c results 固定契约齐备",
              set(server.RECOVERY_RESULT_FIELDS) == set(list(rkeys)[0]))
        check("3c 每项 whisper_calls 恒为 int",
              all(isinstance(r.get("whisper_calls"), int) for r in results))
        check("3c 每项 ok 恒为 bool", all(isinstance(r.get("ok"), bool) for r in results))

        # 3d 老 job 文件（半结构）读回也按同一契约归一
        legacy_path = os.path.join(root, "data", "recovery_jobs", "rec-legacy.json")
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, "w", encoding="utf-8") as fh:
            json.dump({"job_id": "rec-legacy", "state": "SUCCEEDED",
                       "data_root_digest": hashlib.sha256(
                           os.path.abspath(root).encode()).hexdigest()[:16],
                       "results": [{"run_id": "x"}, {"run_id": "y", "state": "FAILED",
                                                     "ok": False}]}, fh)
        code, legacy = server._handle_retry_batch_status(
            {"data_root": [root], "job_id": ["rec-legacy"]})
        lr = legacy.get("results") or []
        check("3d 老 job 读回归一", len(lr) == 2
              and all(set(r.keys()) == set(server.RECOVERY_RESULT_FIELDS)
                      for r in lr), lr)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------------------------ 4 候选版本锁 / 漂移

def part4_candidate_lock(server):
    root = build_root_a(server)
    assert_tmp(root, "part4_candidate_lock")
    try:
        write_candidates(root, [
            {"wrong": "漂移错词一", "right": "漂移正词一", "confidence": "high"},
            {"wrong": "漂移错词二", "right": "漂移正词二", "confidence": "high"},
        ])
        job_before = server._vocab_apply_job
        code, get1 = server._handle_vocab_candidates_get({"data_root": [root]})
        rev1 = get1.get("candidates_revision")
        check("4a GET 回候选版本", code == 200 and isinstance(rev1, str) and rev1,
              (code, get1))

        # 缺版本 -> 400（POST 必须带）
        code, res = server._handle_vocab_candidates_apply(body({
            "data_root": root, "indices": [0], "rerun_old": False}))
        check("4b 缺 candidates_revision -> 400", code == 400, (code, res))

        # 快照漂移：GET 后清单被改写 -> 409 零执行
        cand_path = os.path.join(root, "vocab-candidates.json")
        before_bytes = sha(cand_path)
        write_candidates(root, [
            {"wrong": "新插入错词", "right": "新插入正词", "confidence": "high"},
            {"wrong": "漂移错词一", "right": "漂移正词一", "confidence": "high"},
            {"wrong": "漂移错词二", "right": "漂移正词二", "confidence": "high"},
        ])
        code, res = server._handle_vocab_candidates_apply(body({
            "data_root": root, "indices": [0], "rerun_old": False,
            "candidates_revision": rev1}))
        check("4c 漂移 -> 409", code == 409, (code, res))
        check("4c 漂移 -> 零执行（未建新任务、未写词库）",
              server._vocab_apply_job is job_before
              and not os.path.exists(os.path.join(root, "vocab-user.json")))
        check("4c 漂移 -> 候选文件未被动过", sha(cand_path) != before_bytes)
        code, res2 = server._run_vocab_candidates_apply({
            "data_root": root, "indices": [0], "rerun_old": False,
            "candidates_revision": rev1})
        check("4c(同步) 漂移 -> 409", code == 409)
        stale = res2.get("candidates_revision")
        check("4c 409 回最新版本便于前端刷新", isinstance(stale, str) and stale != rev1)

        # 用最新版本提交：index 0 指向新条目（证明版本锁防错位）
        code, ok = server._run_vocab_candidates_apply({
            "data_root": root, "indices": [0], "rerun_old": False,
            "candidates_revision": stale})
        check("4d 最新版本提交 200", code == 200 and ok.get("ok"), (code, ok))
        vocab = read_json(os.path.join(root, "vocab-user.json"), [])
        check("4d 应用的是新 index 0（防索引漂移串项）",
              any(e.get("wrong") == "新插入错词" for e in vocab), vocab)
        check("4d 未误用旧 index 0 之外的条目",
              not any(e.get("wrong") == "漂移错词二" for e in vocab))

        # 版本再次变化 -> 旧版本继续 409（锁是持续生效的）
        write_candidates(root, [{"wrong": "再改错词", "right": "再改正词",
                                 "confidence": "low"}])
        code, res3 = server._run_vocab_candidates_apply({
            "data_root": root, "indices": [0], "rerun_old": False,
            "candidates_revision": stale})
        check("4e 版本再变 -> 仍 409", code == 409)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------------------------ 5 部分更新安全

def part5_partial_update(server):
    root = build_root_a(server)
    assert_tmp(root, "part5_partial_update")
    try:
        presets = server._load_vocab_presets()
        domains = [p["domain"] for p in presets]
        check("5 预置域至少 2 个（可测部分更新）", len(domains) >= 2, domains)
        if len(domains) < 2:
            return
        d1, d2 = domains[0], domains[1]

        # 先关 d2
        code, res = server._handle_vocab_presets_domains_post(body({
            "data_root": root, "enabled": {d2: False}}))
        check("5a 关闭一个域 200", code == 200 and res["enabled"][d2] is False,
              (code, res))
        check("5a 未提交域保持默认启用", res["enabled"][d1] is True)

        # 只提交 d1 -> d2 必须保持 False（旧实现会回启）
        code, res = server._handle_vocab_presets_domains_post(body({
            "data_root": root, "enabled": {d1: False}}))
        check("5b 部分提交不回启未提交域",
              code == 200 and res["enabled"][d2] is False, (code, res))
        state = read_json(os.path.join(root, "vocab-domains.json"), {})
        check("5b 落盘状态同样保持 d2=False",
              (state.get("enabled") or {}).get(d2) is False, state)

        # 未知域忽略 + 空对象不产生旁路副作用
        code, res = server._handle_vocab_presets_domains_post(body({
            "data_root": root, "enabled": {"NOT_A_DOMAIN": False}}))
        check("5c 未知域忽略、已存在状态不变",
              code == 200 and res["enabled"][d1] is False
              and res["enabled"][d2] is False, (code, res))
        before = sha(os.path.join(root, "vocab-domains.json"))
        code, res = server._handle_vocab_presets_domains_post(body({
            "data_root": root, "enabled": {}}))
        check("5c 空 enabled 不改状态", code == 200
              and sha(os.path.join(root, "vocab-domains.json")) == before)

        # 值必须真布尔：字符串 "false" 不得被 bool() 静默当 True
        for bad in ("false", 0, 1, None, "true"):
            code, res = server._handle_vocab_presets_domains_post(body({
                "data_root": root, "enabled": {d1: bad}}))
            check("5d enabled.%s=%r -> 400" % (d1, bad), code == 400, (code, res))
        check("5d 坏值未改动任何状态",
              sha(os.path.join(root, "vocab-domains.json")) == before)
        check("5d 坏值未误删词库文件",
              not os.path.exists(os.path.join(root, "vocab-user.json")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------------------------ 6 错误信息安全 D-12

SENSITIVE = ["/Users/", "/private/var/", "/var/folders/", "SECRET-TOKEN",
             "transcription-body-marker"]


def err_fields(obj):
    """只取响应里的错误类字段（成功响应回显用户自己填的 data_root 不算泄漏）。"""
    out = {}
    if isinstance(obj, dict):
        for key in ("error", "reason", "message", "stage_text", "verdict"):
            if isinstance(obj.get(key), str):
                out[key] = obj[key]
    return out


def scan_leak(name, obj, extra=()):
    text = json.dumps(obj, ensure_ascii=False)
    hits = [s for s in SENSITIVE if s in text]
    hits += [s for s in extra if s in text]
    check("6 脱敏 " + name, not hits, hits)


def part6_error_redaction(server):
    root = build_root_a(server)
    assert_tmp(root, "part6_error_redaction")
    # 用「data_root 指向一个文件」逼出带绝对路径的 OSError
    blocked = os.path.join(tempfile.mkdtemp(prefix="p12_file_"), "not-a-dir")
    with open(blocked, "w", encoding="utf-8") as fh:
        fh.write("x")
    assert_tmp(blocked, "part6_error_redaction.blocked")
    try:
        code, res = server._handle_vocab_add(body({
            "data_root": blocked, "wrong": "泄漏错词", "right": "泄漏正词"}))
        check("6a 词库落盘失败 -> 5xx", code in (400, 500), (code, res))
        scan_leak("6a 词库保存失败不回绝对路径", res, [blocked])

        code, res = server._handle_reapply_post(body({
            "data_root": blocked, "all": True}))
        scan_leak("6b reapply 坏库不回绝对路径",
                  err_fields(res), [blocked, os.path.dirname(blocked)])
        code, res = server._handle_reapply_post(body({
            "data_root": blocked, "run_id": "run-x"}))
        check("6b reapply 单条坏库 -> 人话失败",
              code == 200 and res.get("ok") is False, (code, res))
        scan_leak("6b reapply 单条坏库不回绝对路径",
                  err_fields(res), [blocked, os.path.dirname(blocked)])
        code, res = server._handle_vocab_presets_import(body({
            "data_root": blocked, "domains": ["programming"]}))
        check("6b 预置导入坏目录 -> 失败", code in (400, 500), (code, res))
        scan_leak("6b 预置导入坏目录不回绝对路径",
                  err_fields(res), [blocked, os.path.dirname(blocked)])

        # 真·无库目录（不是文件）→ clear 打开失败的人话错误
        nolib = tempfile.mkdtemp(prefix="p12_nolib_")
        code, res = server._handle_clear_post(body({
            "data_root": nolib, "input_root": nolib, "dry_run": True}))
        check("6c 无库目录 clear dry_run -> 404 人话", code == 404, (code, res))
        scan_leak("6c 无库目录 clear 不回绝对路径",
                  err_fields(res), [nolib, root])
        shutil.rmtree(nolib, ignore_errors=True)

        code, res = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": "yes",
            "plan_token": "SECRET-TOKEN-ABC", "run_ids": ["run-retry"]}))
        scan_leak("6d 非布尔 confirm 不回请求体", res)
        code, res = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": True,
            "plan_token": "SECRET-TOKEN-ABC", "run_ids": ["run-retry"]}))
        check("6d 未知令牌 -> 409", code == 409, (code, res))
        scan_leak("6d 未知令牌不回令牌原文", res)

        code, res = server._handle_retry_plan_post(body({
            "data_root": root, "run_ids": "not-a-list"}))
        check("6e run_ids 类型错 -> 400", code == 400)
        scan_leak("6e run_ids 类型错不回路径", res, [root])

        code, res = server._handle_retry_plan_post(body({
            "data_root": root, "run_ids": ["run-retry", "run-retry"]}))
        check("6e 重复 run_id -> 400", code == 400, (code, res))
        check("6e 重复 run_id 人话提到 run_ids", "run_ids" in res.get("error", ""))

        code, res = server._handle_status({"data_root": [root],
                                           "limit": ["1 OR 1=1"]})
        check("6e limit 注入串 -> 400", code == 400)
        scan_leak("6e limit 注入串不回请求体", res)

        # 6h 未知 run_id：结构化人话失败、零执行（不进 eligible）
        writer_before = tree_snapshot(root)
        code, res = server._handle_retry_plan_post(body({
            "data_root": root, "run_ids": ["run-不存在"]}))
        check("6h 未知 run_id -> 200 dry-run 且不可恢复", code == 200
              and res.get("eligible") == [], (code, res))
        check("6h 未知 run_id 有人话排除原因",
              (res.get("excluded") or [{}])[0].get("reason"))
        check("6h 未知 run_id 零写盘", tree_snapshot(root) == writer_before)

        # 6i 坏库 / 缺表：结构化失败且不回路径
        bad_db = tempfile.mkdtemp(prefix="p12_baddb_")
        os.makedirs(os.path.join(bad_db, "data"), exist_ok=True)
        with open(os.path.join(bad_db, "data", "state.db"), "w",
                  encoding="utf-8") as fh:
            fh.write("this is not a sqlite database")
        code, res = server._handle_failure_diagnosis({"data_root": [bad_db]})
        check("6i 坏库 -> 结构化失败(ok=false)", code == 200 and res.get("ok") is False,
              (code, res))
        scan_leak("6i 坏库不回绝对路径", res, [bad_db])
        code, res = server._handle_retry_plan_post(body({
            "data_root": bad_db, "run_ids": ["run-x"]}))
        check("6i 坏库 retry-plan -> 结构化失败", code in (400, 409, 500), (code, res))
        scan_leak("6i 坏库 retry-plan 不回绝对路径", res, [bad_db])
        empty_db = tempfile.mkdtemp(prefix="p12_nodb_")
        code, res = server._handle_failure_diagnosis({"data_root": [empty_db]})
        check("6i 缺库 -> ok:false 结构化",
              code == 200 and res.get("ok") is False and res.get("code"),
              (code, res))
        scan_leak("6i 缺库不回绝对路径", res, [empty_db])
        code, res = server._handle_status({"data_root": [empty_db]})
        check("6i 缺库 status -> 不回 state.db 绝对路径",
              code == 200 and empty_db not in json.dumps(res, ensure_ascii=False))
        shutil.rmtree(bad_db, ignore_errors=True)
        shutil.rmtree(empty_db, ignore_errors=True)

        # _err_text 本体：抹路径、压平空白、截断
        msg = server._err_text(OSError(
            "[Errno 28] No space left on device: '%s/data/vocab-user.json'"
            % root))
        check("6f _err_text 抹掉绝对路径",
              root not in msg and "/Users/" not in msg and "No space" in msg, msg)
        check("6f _err_text 压平换行",
              "\n" not in server._err_text(ValueError("a\nb\tc")))
        check("6f _err_text 截断超长",
              len(server._err_text(ValueError("z" * 500))) <= 181)
        check("6f _err_text 空消息回类型名",
              server._err_text(ValueError("")) == "ValueError")

        # 诊断/复制摘要口径：真实路径必须已被打码
        code, diag = server._handle_failure_diagnosis({"data_root": [root]})
        text = json.dumps(diag, ensure_ascii=False)
        check("6g 诊断不回真实绝对路径",
              root not in text and "/Users/" not in text, root)
        check("6g 诊断路径已打码（…/ 形式）",
              all(str(i.get("recorded_path_redacted", "")).startswith("…/")
                  for i in (diag.get("items") or [])))
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(os.path.dirname(blocked), ignore_errors=True)


# ------------------------------------------------------------------ 7 回归（P0-1/P0-2/P0-3）

def part7_regression(server):
    root = build_root_a(server)
    assert_tmp(root, "part7_regression")
    try:
        # 7a retry-plan dry-run：可复算 + eta 未验证 + token TTL
        plan = plan_token_for(server, root, ["run-retry", "run-reuse", "run-publish"])
        check("7a dry_run=true", plan.get("dry_run") is True)
        check("7a eta=未验证", plan.get("eta") == "未验证")
        check("7a token/过期时间在位",
              isinstance(plan.get("plan_token"), str)
              and int(plan["expires_at"]) - int(time.time())
              <= server.RECOVERY_TOKEN_TTL_SEC + 2)
        elig = plan.get("eligible") or []
        ex = plan.get("excluded") or []
        check("7a summary 等于逐项复算",
              plan["summary"]["eligible"] == len(elig)
              and plan["summary"]["excluded"] == len(ex)
              and plan["summary"]["selected"] == 3)
        check("7a 成功项不进可恢复集合", all(e["run_id"] != "run-ok" for e in elig))
        check("7a 三种策略命中",
              {e["strategy"] for e in elig} == {"RETRANSCRIBE", "REUSE_DERIVED",
                                               "PUBLISH_ONLY"}, elig)
        check("7a 诊断快照 id 与计划一致",
              plan["diagnosis_snapshot_id"] == elig[0]["diagnosis_snapshot_id"])
        code, stale = server._handle_retry_plan_post(body({
            "data_root": root, "run_ids": ["run-retry"],
            "diagnosis_snapshot_id": "diag-0000"}))
        check("7a 旧快照 id -> 409 零执行", code == 409, (code, stale))

        # 7b 幂等：同 token 连点只建一个 job
        plan2 = plan_token_for(server, root, ["run-reuse"])
        b1 = body({"data_root": root, "confirm": True,
                   "plan_token": plan2["plan_token"], "run_ids": ["run-reuse"]})
        c1, j1 = server._handle_retry_batch_post(b1)
        c2, j2 = server._handle_retry_batch_post(b1)
        check("7b 首次 202", c1 == 202 and j1.get("ok"))
        check("7b 二次回既有 job（idempotent）",
              c2 == 202 and j2.get("idempotent") is True
              and j2.get("job_id") == j1.get("job_id"), (c2, j2))
        jobs_dir = os.path.join(root, "data", "recovery_jobs")
        job_files = [f for f in os.listdir(jobs_dir) if f.endswith(".json")]
        check("7b 只有一个 job 文件", len(job_files) == 1, job_files)
        check("7b 原子写不留 tmp",
              not [f for f in os.listdir(jobs_dir) if ".tmp" in f])
        check("7b 终态可复算",
              j1.get("total") == len(j1.get("results") or [])
              and j1.get("recovered") == sum(1 for r in j1["results"]
                                             if r["state"] == "SUCCEEDED"))
        check("7b REUSE_DERIVED whisper=0", j1.get("whisper_calls") == 0)

        # 7c 漂移 -> 409 零执行；执行集合不符 -> 409
        plan3 = plan_token_for(server, root, ["run-retry"])
        c3, r3 = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": True,
            "plan_token": plan3["plan_token"], "run_ids": ["run-reuse"]}))
        check("7c 执行集合与预览不一致 -> 409", c3 == 409, (c3, r3))
        c4, r4 = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": True,
            "plan_token": plan3["plan_token"], "run_ids": ["run-retry"]}))
        check("7c 诊断漂移（该 run 已执行过）-> 409 或正常终态",
              c4 in (409, 202), (c4, r4))

        # 7d 过期令牌 -> 409
        plan4 = plan_token_for(server, root, ["run-publish"])
        digest = hashlib.sha256(plan4["plan_token"].encode()).hexdigest()
        with server._RECOVERY_PLAN_LOCK:
            server._RECOVERY_PLANS[digest]["expires_at"] = int(time.time()) - 10
        c5, r5 = server._handle_retry_batch_post(body({
            "data_root": root, "confirm": True,
            "plan_token": plan4["plan_token"], "run_ids": ["run-publish"]}))
        check("7d 过期令牌 -> 409", c5 == 409, (c5, r5))
        check("7d 过期令牌零执行（无新 job）",
              len([f for f in os.listdir(jobs_dir) if f.endswith(".json")]) == len(job_files))

        # 7e 目录不一致 -> 409
        other = tempfile.mkdtemp(prefix="p12_C_")
        try:
            plan5 = plan_token_for(server, root, ["run-publish"])
            c6, r6 = server._handle_retry_batch_post(body({
                "data_root": other, "confirm": True,
                "plan_token": plan5["plan_token"], "run_ids": ["run-publish"]}))
            check("7e 跨目录执行 -> 409 零执行", c6 == 409, (c6, r6))
        finally:
            shutil.rmtree(other, ignore_errors=True)

        # 7h 两线程同 token：只有一个新 job（D-6 并发）
        jobs_before = len([f for f in os.listdir(jobs_dir) if f.endswith(".json")])
        plan6 = plan_token_for(server, root, ["run-reuse"])
        body6 = body({"data_root": root, "confirm": True,
                      "plan_token": plan6["plan_token"], "run_ids": ["run-reuse"]})
        out = {}
        threads = [threading.Thread(target=lambda i=i: out.__setitem__(
            i, server._handle_retry_batch_post(body6))) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        codes = sorted(v[0] for v in out.values())
        check("7h 两线程同 token -> 恰好一个新 job（202/202幂等 或 202/409）",
              codes in ([202, 202], [202, 409]) and len(out) == 2, (codes, out))
        jobs_after = [f for f in os.listdir(jobs_dir) if f.endswith(".json")]
        check("7h 只多出一个 job 文件", len(jobs_after) == jobs_before + 1,
              (jobs_before, jobs_after))
        if codes == [202, 202]:
            check("7h 两线程都 202 时其中一个是幂等回既有 job",
                  any(v[1].get("idempotent") is True for v in out.values()), out)

        # 7f P0-3 _FAIL_SEMANTICS 语义归一化未回退
        code, diag = server._handle_failure_diagnosis({"data_root": [root]})
        by_id = {i["run_id"]: i for i in diag.get("items") or []}
        pub = by_id.get("run-publish") or {}
        check("7f PUBLISH_BLOCKED 不算 mismatch（不降级 NEEDS_HUMAN）",
              pub.get("display_persisted_mismatch") is False
              and pub.get("recovery_eligibility") == "AUTO_PUBLISH", pub)
        retry = by_id.get("run-retry") or {}
        check("7f 可自动重试项资格保持",
              retry.get("recovery_eligibility") == "AUTO_RETRANSCRIBE")
        check("7f 成功项不进诊断", "run-ok" not in by_id)
        check("7f 计数与逐项一致",
              diag["counts"]["incomplete_or_blocked_total"] == len(diag["items"])
              and diag["counts"]["auto_retryable_failure_count"]
              == sum(1 for i in diag["items"]
                     if i["recovery_eligibility"] in
                     {"AUTO_RETRANSCRIBE", "AUTO_REUSE", "AUTO_PUBLISH"}))

        # 7g No-Clobber：目标笔记已存在 -> SKIPPED 且字节不变
        vault = tempfile.mkdtemp(prefix="p12_vault_")
        try:
            assert_tmp(root, "part7_regression.no-clobber")
            job_dir = os.path.join(root, "data", "jobs", "run-publish")
            manifest = read_json(os.path.join(job_dir, "manifest.json"), {})
            rendered = manifest.get("rendered_path")
            target = os.path.join(vault, os.path.basename(rendered))
            with open(target, "w", encoding="utf-8") as fh:
                fh.write("用户在库里手改过的笔记")
            before_hash = sha(target)
            entry = server._exec_publish_only(root, "run-publish",
                                              os.path.join(root, "work"), vault)
            check("7g 目标已存在 -> SKIPPED 未覆盖",
                  entry.get("state") == "SKIPPED" and entry.get("whisper_calls") == 0,
                  entry)
            check("7g 库内笔记字节未变", sha(target) == before_hash)
            check("7g 未新建 canonical 副本",
                  len(os.listdir(vault)) == 1, os.listdir(vault))
            missing = server._exec_publish_only(root, "run-publish",
                                                os.path.join(root, "work"), None)
            check("7g 缺库 -> NEEDS_HUMAN 且不重建库",
                  missing.get("state") == "NEEDS_HUMAN", missing)
        finally:
            shutil.rmtree(vault, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------------------------ 8 真实 HTTP 路由（本进程临时端口，不碰 8765）

def part8_http_contract(server):
    """走真 Handler.do_GET/do_POST：路由、错误结构、坏库不掉线、主题默认浅色。"""
    import threading
    import urllib.error
    import urllib.parse
    import urllib.request
    from http.server import ThreadingHTTPServer

    root = build_root_a(server)
    assert_tmp(root, "part8_http_contract")
    bad = root + "-baddb"
    os.makedirs(os.path.join(bad, "data"), exist_ok=True)
    with open(os.path.join(bad, "data", "state.db"), "w", encoding="utf-8") as fh:
        fh.write("not a sqlite database")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = int(srv.server_address[1])
    check("8 端口不是 8765（不碰线上服务）", port != 8765 and port != 0, port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port

    def req(path, payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        r = urllib.request.Request(
            base + path, data=body,
            method="POST" if payload is not None else "GET",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=30) as fh:
                return fh.status, json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def raw(path):
        with urllib.request.urlopen(base + path, timeout=30) as fh:
            return fh.status, fh.read().decode("utf-8")

    q = urllib.parse.quote
    try:
        code, html = raw("/")
        check("8 首页 200", code == 200)
        check("8 主题默认浅色未回退", 'data-theme="light"' in html)
        code, res = req("/api/status?data_root=%s&limit=200" % q(root))
        check("8 GET /api/status 按 data_root 200", code == 200, (code, res))
        code, res = req("/api/status?data_root=relative")
        check("8 GET /api/status 相对路径 400 人话",
              code == 400 and isinstance(res.get("error"), str), (code, res))
        code, res = req("/api/failures/retry-batch/status?data_root=%s" % q(root))
        check("8 retry-batch status 缺 job_id -> 400",
              code == 400 and "job_id" in res.get("error", ""), (code, res))
        code, res = req("/api/vocab/candidates/apply",
                        {"data_root": root, "indices": [True], "rerun_old": False,
                         "candidates_revision": "x"})
        check("8 POST 布尔索引 -> 400 人话", code == 400, (code, res))
        code, res = req("/api/vocab/candidates/apply",
                        {"indices": [0], "rerun_old": False,
                         "candidates_revision": "x"})
        check("8 POST 缺 data_root -> 400 人话（P2-新1 对称契约）",
              code == 400 and "数据目录" in res.get("error", ""), (code, res))
        code, res = req("/api/vocab/candidates/apply/status")
        check("8 GET status 无参 -> job:null（不放宽查询侧）",
              code == 200 and res.get("job") is None, (code, res))
        code, res = req("/api/failures/retry-plan",
                        {"data_root": root, "run_ids": "nope"})
        check("8 POST run_ids 类型错 -> 400 人话", code == 400, (code, res))
        code, res = req("/api/vocab/presets/domains",
                        {"data_root": root, "enabled": {"programming": "false"}})
        check("8 POST 字符串布尔 -> 400 人话", code == 400, (code, res))
        code, res = req("/nope")
        check("8 未知路径 -> 404 结构化", code == 404 and res.get("ok") is False)
        code, res = req("/api/failures/diagnosis?data_root=%s" % q(bad))
        check("8 坏库诊断 -> 200 ok:false 结构化（不掉线）",
              code == 200 and res.get("ok") is False and res.get("code"),
              (code, res))
        check("8 坏库诊断不回绝对路径", bad not in json.dumps(res, ensure_ascii=False))
        code, res = req("/api/status?data_root=%s" % q(bad))
        check("8 坏库 status -> 200 且不回绝对路径",
              code == 200 and bad not in json.dumps(res, ensure_ascii=False), (code, res))

        # P1-1 出网链路：worker.last_error 经 GET /api/start 出网前必须已脱敏
        leak = ("任务 视频.mp4 处理时遇到意外：打不开 "
                + os.path.join(root, "data", "state.db"))
        # 修复前对照：旧写法（裸 exc）产出的字符串确实逐字带真实绝对路径
        leak_path = os.path.join(root, "data", "state.db")
        old_producer = "任务 %s 处理时遇到意外：%s" % (
            "视频.mp4", OSError("打不开 " + leak_path))
        check("8 对照：旧写法产出串含真实绝对路径（=修复前会出网）",
              leak_path in old_producer and "state.db" in old_producer)
        check("8 修复后同一异常经 _err_text 已无路径",
              leak_path not in server._err_text(OSError("打不开 " + leak_path)))
        with server._state_lock:
            server._worker["last_error"] = leak
        code, res = req("/api/start")
        text = json.dumps(res, ensure_ascii=False)
        check("8 /api/start 200", code == 200, code)
        err_field = str(res.get("worker", {}).get("last_error"))
        check("8 worker.last_error 出网不含 data_root/state.db/绝对路径",
              root not in err_field and "state.db" not in err_field
              and "/Users/" not in err_field and "/private/var" not in err_field
              and "/var/folders" not in err_field, err_field)
        check("8 全响应体内也不含该泄漏串（含 state.db 名）", "state.db" not in text, text[:200])
        check("8 脱敏后仍是人话（保留“遇到意外/打不开”）",
              "遇到意外" in text and "打不开" in text,
              res.get("worker", {}).get("last_error"))
        check("8 注入的原始泄漏串不再逐字出现", leak not in text)
        with server._state_lock:
            server._worker["last_error"] = None

        # ---- P1-三1 复验口径①②（真 Handler + 真 HTTP）：不带 ob_vault_root 键也必须成功
        write_candidates(root, [
            {"wrong": "无库错词", "right": "无库正词", "confidence": "high"}])
        rev_http = server._vocab_candidates_revision(root)
        code, res = req("/api/vocab/candidates/apply",
                        {"data_root": root, "indices": [0], "rerun_old": False,
                         "candidates_revision": rev_http})
        check("8(P1-三1①) POST 不带 ob_vault_root 键 -> 202",
              code == 202 and res.get("job_id"), (code, res))
        jid_http = str(res.get("job_id"))
        term = {}
        deadline = time.time() + 60
        while time.time() < deadline:
            c2, term = req("/api/vocab/candidates/apply/status?data_root=%s&job_id=%s"
                           % (q(root), q(jid_http)))
            st = (term.get("job") or {}).get("state")
            if st and st != "running":
                break
            time.sleep(0.2)
        job_http = term.get("job") or {}
        check("8(P1-三1①) 不填笔记库也能跑成功：终态 done 且 imported>=1",
              job_http.get("state") == "done"
              and int(job_http.get("imported") or 0) >= 1, job_http)
        check("8(P1-三1①) 终态不再出现 ob_vault_root 开发者文案",
              "ob_vault_root" not in json.dumps(job_http, ensure_ascii=False),
              job_http.get("message"))
        check("8(P1-三1①) 词库落到该 tmp 数据目录",
              os.path.isfile(os.path.join(root, "vocab-user.json")))
        # 复验口径②：坏类型仍 400（HTTP 层，契约未放宽）
        for label, bad_vault in (("null", None), ("整数", 1), ("数组", ["x"])):
            c3, r3 = req("/api/vocab/candidates/apply",
                         {"data_root": root, "indices": [0], "rerun_old": False,
                          "candidates_revision": server._vocab_candidates_revision(root),
                          "ob_vault_root": bad_vault})
            check("8(P1-三1②) ob_vault_root=%s -> 400" % label, c3 == 400, (c3, r3))
        # P3-三2：data_root 类型错文案统一成「数据目录」口吻
        for label, bad_root in (("null", None), ("整数", 1), ("数组", ["x"])):
            c4, r4 = req("/api/vocab/candidates/apply",
                         {"data_root": bad_root, "indices": [0], "rerun_old": False,
                          "candidates_revision": "x"})
            check("8(P3-三2) data_root=%s 文案是「数据目录」口吻" % label,
                  c4 == 400 and "数据目录" in r4.get("error", "")
                  and "data_root 须为" not in r4.get("error", ""), (c4, r4))
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(bad, ignore_errors=True)


# ------------------------------------------------------------------ 9 复核返工守卫（P1-1/P1-2/P2-3/P2-4/P2-5/P2-6＋item5/6/7/8）

def _server_source():
    with open(os.path.join(ROOT, "app", "server.py"), encoding="utf-8") as fh:
        return fh.read()


def part9_rework_guards(server):
    """复核 8 项返工的回归守卫：源头无裸 exc ＋ 脱敏本体 ＋ 绑定/锁/回落口子。"""
    root_a = build_root_a(server)
    root_b = tempfile.mkdtemp(prefix="p12_r_b_")
    noroot = make_data_root(server, "NOCAND", [RETRY_SPEC, PUB_SPEC])
    link = os.path.join(os.path.dirname(root_a),
                        os.path.basename(root_a) + "-link")
    assert_tmp(root_a, "part9.A")
    assert_tmp(root_b, "part9.B")
    assert_tmp(noroot, "part9.nocand")
    try:
        src = _server_source()

        # ---- 9a 源头守卫：全仓再无裸 exc 插值（reviewer 的扫描口径）
        bare = re.findall(r"%\s*\(?\s*exc\s*[,)]", src)
        check("9a 源头无裸 exc 插值（漏改处=0）", bare == [], bare[:5])
        calls = [m.start() for m in re.finditer(r"_worker_note_error\(", src)
                 if not src[:m.start()].rstrip().endswith("def")]
        check("9a _worker_note_error 调用点 2 处", len(calls) == 2, len(calls))
        check("9a 每处都带 _err_text（P1-1 源头）",
              all("_err_text" in src[i:i + 200] for i in calls))
        note_path = os.path.join(root_a, "data", "jobs", "run-x", "render", "r.md")
        old_note = ("新稿已生成在数据目录：%s；入库未试：%s"
                    % (note_path, OSError("打不开 " + note_path)))
        check("9a 对照：旧写法 note 含真实绝对路径（=修复前会渲染/进 receipt）",
              note_path in old_note)
        check("9a 修复后 note 里同一异常已无路径",
              note_path not in server._err_text(OSError("打不开 " + note_path)))
        idx = src.find("入库未试：%s")
        window = src[max(0, idx - 200):idx + 200]
        check("9a 新稿 note 分支走 _err_text（P1-2 源头）",
              idx > 0 and "_err_text(exc)" in window
              and not re.search(r",\s*exc\s*\)", window), window[-140:])
        # str(exc) 白名单：只许出现在取参层 400（ParamError）与 _err_text 本体
        str_exc_bad = []
        for _m in re.finditer(r"str\(exc\)", src):
            _before = src[max(0, _m.start() - 170):_m.start()]
            _after = src[_m.start():_m.start() + 70]
            if "except ParamError" in _before or "type(exc).__name__" in _after:
                continue
            str_exc_bad.append(src[:_m.start()].count("\n") + 1)
        check("9a str(exc) 白名单式（只剩取参层 400 与 _err_text 本体）",
              str_exc_bad == [], str_exc_bad)
        check("9a reveal 失败分支不再回 real 路径",
              "(err or real," not in src and not re.search(r"%\s*\(raw,", src))

        # ---- 9b 脱敏本体：含空格/中文/引号路径整段抹掉（P2-6）
        space_path = "/Users/zzy/My Data/vault/note.md"
        got = server._err_text(OSError("打不开 " + space_path))
        check("9b 含空格路径整段抹掉（末段不泄漏）",
              "Data" not in got and "vault" not in got and "note.md" not in got
              and "打不开" in got, got)
        got2 = server._err_text(OSError(space_path + " 打不开"))
        check("9b 路径在前也整段抹掉",
              "note.md" not in got2 and "/" not in got2, got2)
        cjk = "/Users/zzy/需转录视频 葫芦军师/文件.md"
        got3 = server._err_text(OSError(cjk))
        check("9b 中文含空格路径整段抹掉",
              "葫芦军师" not in got3 and "需转录" not in got3, got3)
        got4 = server._err_text(
            OSError("[Errno 2] No such file or directory: '/Users/a/b c/d.md'"))
        check("9b 引号内路径整段抹掉（保留 errno 人话）",
              "/Users" not in got4 and "No such file" in got4, got4)
        spaced_dir = os.path.join(root_b, "My Data", "vault")
        os.makedirs(spaced_dir, exist_ok=True)
        got5 = server._err_text(OSError(
            "No space left on device: '%s/note.md'" % spaced_dir))
        check("9b 真 tmp 含空格目录不泄漏",
              root_b not in got5 and "My Data" not in got5, got5)
        # 人话不被误抹（项目真实文案逐条过一遍）
        for human in ("Stage3+ table not empty (n=3)",
                      "transcription-stage status not terminal",
                      "状态库读不出来：file is not a database，请检查数据目录或先启动一次监听",
                      "该任务状态已漂移（零执行），请重新预览",
                      "批量恢复须在预览后确认（confirm:true），请先预览再确认"):
            check("9b 人话原样保留：%s" % human[:14],
                  server._err_text(human) == human, server._err_text(human))
        check("9b 已打码文案再脱敏仍可读（不重复堆省略号）",
              server._err_text("所选路径不存在：…/Downloads/需转录视频，请点浏览重选")
              == "所选路径不存在：…，请点浏览重选",
              server._err_text("所选路径不存在：…/Downloads/需转录视频，请点浏览重选"))
        check("9b 非路径文本原样保留",
              server._err_text(OSError("file is not a database"))
              == "file is not a database")
        check("9b 纯路径文本回省略号而非类型名",
              server._err_text("/a/b/c") == "…"
              and server._err_text(OSError("/a/b/c")) == "OSError")

        # ---- 9c browse/reveal 失败分支不回原文/不回真实路径（P2-4）
        miss = os.path.join(root_b, "no", "such", "dir", "x")
        code, res = server._handle_browse({"path": [miss]})
        check("9c browse 缺目录 400 且不回完整路径",
              code == 400 and root_b not in res.get("error", "")
              and "…/" in res.get("error", ""), (code, res))
        code, res = server._handle_browse({"path": ["relative/dir"]})
        check("9c browse 相对路径 400 且不回 %r 原文",
              code == 400 and "'relative/dir'" not in res.get("error", ""), (code, res))
        code, res = server._handle_reveal_post(body({"path": miss}))
        check("9c reveal 缺文件 400 且不回完整路径",
              code == 400 and root_b not in res.get("error", "")
              and "…/" in res.get("error", ""), (code, res))
        code, res = server._handle_reveal_post(body({"path": "relative/x"}))
        check("9c reveal 相对路径 400 且不回原文",
              code == 400 and "'relative/x'" not in res.get("error", ""), (code, res))

        # ---- 9d job 绑定摘要缺失/非法一律 409（item 5）
        jobs_b = os.path.join(root_b, "data", "recovery_jobs")
        os.makedirs(jobs_b, exist_ok=True)
        digests = (("缺键", "__MISSING__"), ("null", None), ("空串", ""),
                   ("15位", "0123456789abcde"), ("非hex", "zzzzzzzzzzzzzzzz"),
                   ("大写hex", "ABCDEF0123456789"))
        for label, value in digests:
            payload = {"job_id": "rec-bad", "state": "SUCCEEDED",
                       "results": [{"run_id": "leak-run"}]}
            if value != "__MISSING__":
                payload["data_root_digest"] = value
            with open(os.path.join(jobs_b, "rec-bad.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(payload, fh)
            code, res = server._handle_retry_batch_status(
                {"data_root": [root_b], "job_id": ["rec-bad"]})
            check("9d 摘要%s -> 409" % label, code == 409, (label, code, res))
            check("9d 摘要%s 不回 results" % label, "results" not in res, res)
        # 显式兼容白名单：本改动之前写下的 job（abspath 口径摘要）仍可取
        legacy = server._recovery_root_digest_legacy(root_b)
        real = server._recovery_root_digest(root_b)
        with open(os.path.join(jobs_b, "rec-legacy.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"job_id": "rec-legacy", "state": "SUCCEEDED",
                       "data_root_digest": legacy,
                       "results": [{"run_id": "legacy-run"}]}, fh)
        code, res = server._handle_retry_batch_status(
            {"data_root": [root_b], "job_id": ["rec-legacy"]})
        check("9d 旧 abspath 口径 job 仍可取（显式兼容白名单）",
              code == 200 and res.get("job_id") == "rec-legacy"
              and bool(res.get("results")), (code, res))
        check("9d 两种口径摘要确实不同（兼容分支非恒真）", legacy != real,
              (legacy, real))
        check("9d 摘要校验是白名单式（非法=拒）",
              server._recovery_digest_ok("0123456789abcdef") is True
              and server._recovery_digest_ok("0123456789ABCDEF") is False
              and server._recovery_digest_ok("") is False
              and server._recovery_digest_ok(None) is False)

        # ---- 9e 同一目录多种写法都能取到 job（realpath 口径，item 6）
        plan = plan_token_for(server, root_a, ["run-reuse"])
        code, job = server._handle_retry_batch_post(body({
            "data_root": root_a, "confirm": True,
            "plan_token": plan["plan_token"], "run_ids": ["run-reuse"]}))
        check("9e 基线 202", code == 202 and job.get("job_id"), (code, job))
        jid = str(job.get("job_id"))
        variants = (("尾斜杠", root_a + "/"),
                    ("含..", os.path.join(root_a, "data", "..")),
                    ("末段双斜杠", root_a.replace("/", "//", 1)))
        for label, variant in variants:
            code, res = server._handle_retry_batch_status(
                {"data_root": [variant], "job_id": [jid]})
            check("9e %s 写法能取到 job" % label,
                  code == 200 and res.get("job_id") == jid, (label, code, res))
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(root_a, link)
        code, res = server._handle_retry_batch_status(
            {"data_root": [link], "job_id": [jid]})
        check("9e 符号链接指向同一目录能取到 job",
              code == 200 and res.get("job_id") == jid, (code, res))
        # 对照（证明上面的断言不是恒真）：换回旧 abspath 口径 → 符号链接必被误拒
        orig_digest = server._recovery_root_digest
        try:
            server._recovery_root_digest = server._recovery_root_digest_legacy
            code, res = server._handle_retry_batch_status(
                {"data_root": [link], "job_id": [jid]})
            check("9e 对照：旧 abspath 口径下符号链接确会被 409 误拒（证明修复有牙）",
                  code == 409 and "results" not in res, (code, res))
        finally:
            server._recovery_root_digest = orig_digest
        code, res = server._handle_retry_batch_status(
            {"data_root": [link], "job_id": [jid]})
        check("9e 复原 realpath 口径后符号链接恢复可取", code == 200, (code, res))
        # 大小写变体：realpath 不归一大小写 → 已知边界，但必须 fail-closed 不泄漏
        upper = os.path.join(os.path.dirname(root_a),
                             os.path.basename(root_a).upper())
        case_insensitive = os.path.exists(upper)
        code, res = server._handle_retry_batch_status(
            {"data_root": [upper], "job_id": [jid]})
        check("9e 大小写变体 fail-closed（不回 results）",
              code in (404, 409) and "results" not in res,
              ("本机卷大小写不敏感=%s" % case_insensitive, code, res))

        # ---- 9e2 预览用符号链接路径建、提交用真路径确认（同一目录不得误判）
        plan_link = plan_token_for(server, link, ["run-publish"])
        code, job2 = server._handle_retry_batch_post(body({
            "data_root": root_a, "confirm": True,
            "plan_token": plan_link["plan_token"], "run_ids": ["run-publish"]}))
        check("9e 预览走符号链接、确认走真路径 -> 202（同目录不误判）",
              code == 202 and job2.get("ok"), (code, job2))
        code, back = server._handle_retry_batch_status(
            {"data_root": [link], "job_id": [str(job2.get("job_id"))]})
        check("9e 该 job 反过来用符号链接也能取到",
              code == 200 and back.get("job_id") == job2.get("job_id"),
              (code, back))

        # ---- 9f 候选清单缺失：哨兵版本不可过锁（item 8）
        code, got_get = server._handle_vocab_candidates_get({"data_root": [noroot]})
        check("9f 无清单时版本为哨兵值（不是可用锁）",
              code == 200
              and got_get.get("candidates_revision") == server.RECOVERY_CANDIDATES_ABSENT,
              got_get)
        job_snapshot = server._vocab_apply_job
        before = tree_snapshot(noroot)
        forged = server.RECOVERY_CANDIDATES_ABSENT
        code, res = server._handle_vocab_candidates_apply(body({
            "data_root": noroot, "indices": [0], "rerun_old": False,
            "candidates_revision": forged}))
        check("9f 伪造 absent 过锁 -> 409", code == 409, (code, res))
        check("9f 伪造 absent 人话可读",
              "没有待审清单" in res.get("error", ""), res)
        check("9f 伪造 absent 零执行零写盘",
              server._vocab_apply_job is job_snapshot
              and tree_snapshot(noroot) == before
              and not os.path.exists(os.path.join(noroot, "vocab-user.json"))
              and not os.path.isdir(os.path.join(noroot, "data", "recovery_jobs")))
        code, res = server._run_vocab_candidates_apply({
            "data_root": noroot, "indices": [0], "rerun_old": False,
            "candidates_revision": "deadbeefdeadbeef"})
        check("9f（同步入口）无清单 -> 409", code == 409, (code, res))

        # ---- 9g P2-新1：申请侧必须显式带 data_root（与查询侧对称，杜绝“提交成功但查不到”）
        cand_root = make_data_root(server, "CAND", [RETRY_SPEC])
        assert_tmp(cand_root, "part9.cand")
        try:
            write_candidates(cand_root, [
                {"wrong": "对称错词", "right": "对称正词", "confidence": "high"}])
            rev = server._vocab_candidates_revision(cand_root)
            # 前端解析“生效目录”所依赖的两个真源必须在位
            code, got_c = server._handle_vocab_candidates_get(
                {"data_root": [cand_root]})
            check("9g 候选 GET 回 data_root（前端据此解析生效目录）",
                  code == 200 and got_c.get("data_root") == cand_root, got_c)
            snap = server._listener_snapshot()
            check("9g /api/start 快照带 default_data_root（前端兜底真源）",
                  isinstance(snap.get("default_data_root"), str)
                  and bool(snap.get("default_data_root")),
                  snap.get("default_data_root"))
            check("9g 显式传默认测试目录仍被接受（框留空场景合法）",
                  server._take_required_data_root(
                      {"data_root": server.DEFAULT_DATA_ROOT})
                  == server.DEFAULT_DATA_ROOT)
            check("9g 默认测试目录也在系统 tmp 下（不碰真实目录）",
                  os.path.realpath(server.DEFAULT_DATA_ROOT).startswith(TMP_ROOT))
            job_snap = server._vocab_apply_job
            before = tree_snapshot(cand_root)
            for label, payload in (
                    ("缺键", {"indices": [0], "rerun_old": False,
                              "candidates_revision": rev}),
                    ("空串", {"data_root": "", "indices": [0], "rerun_old": False,
                              "candidates_revision": rev})):
                code, res = server._handle_vocab_candidates_apply(body(payload))
                check("9g 异步入口 data_root %s -> 400" % label, code == 400,
                      (code, res))
                check("9g data_root %s 人话可读" % label,
                      "数据目录" in res.get("error", ""), res)
                code2, res2 = server._run_vocab_candidates_apply(payload)
                check("9g 同步入口 data_root %s -> 400" % label, code2 == 400,
                      (code2, res2))
            check("9g 缺/空 data_root 零执行零写盘",
                  server._vocab_apply_job is job_snap
                  and tree_snapshot(cand_root) == before
                  and not os.path.exists(os.path.join(cand_root, "vocab-user.json")))

            # 正向：显式带目录可提交，且同一目录一定能查到该 job（对称性）
            code, ok = server._handle_vocab_candidates_apply(body({
                "data_root": cand_root, "indices": [0], "rerun_old": False,
                "candidates_revision": rev}))
            check("9g 显式带 data_root 可提交（202）",
                  code == 202 and ok.get("job_id"), (code, ok))
            vjob_id = str(ok.get("job_id"))
            deadline = time.time() + 30
            while time.time() < deadline:
                with server._state_lock:
                    st = (server._vocab_apply_job or {}).get("state")
                if st and st != "running":
                    break
                time.sleep(0.2)
            code, got = server._handle_vocab_apply_status(
                {"data_root": [cand_root], "job_id": [vjob_id]})
            check("9g 提交成功 ⇒ 同目录一定能查到（对称，绝无 job:null）",
                  code == 200 and (got.get("job") or {}).get("job_id") == vjob_id,
                  (code, got))
            # P2-三2：不断言结局的断言会给假信心——这里必须钉终态
            job_term = got.get("job") or {}
            check("9g 不带笔记库键的任务真的跑成功（终态 done、imported>=1）",
                  job_term.get("state") == "done"
                  and int(job_term.get("imported") or 0) >= 1, job_term)
            check("9g 终态文案里没有 ob_vault_root 开发者口吻",
                  "ob_vault_root" not in json.dumps(job_term, ensure_ascii=False),
                  job_term.get("message"))
            check("9g 词库确实落到该 tmp 数据目录",
                  os.path.isfile(os.path.join(cand_root, "vocab-user.json")))
            code, bare_still = server._handle_vocab_apply_status({})
            check("9g 查询侧严格性未被放宽（无参仍 job:null）",
                  code == 200 and bare_still.get("job") is None, (code, bare_still))
            code, other = server._handle_vocab_apply_status(
                {"data_root": [noroot], "job_id": [vjob_id]})
            check("9g 换目录查仍 409 不回明细",
                  code == 409 and other.get("job") is None, (code, other))
            # 复验口径②：坏类型仍 400（不得因本次改法放宽 D-6 契约）
            for label, bad_vault in (("null", None), ("整数", 1), ("布尔", True),
                                    ("数组", ["x"]), ("对象", {}), ("小数", 1.5)):
                for ename, call in (
                        ("异步", lambda p: server._handle_vocab_candidates_apply(body(p))),
                        ("同步", lambda p: server._run_vocab_candidates_apply(p))):
                    c2, r2 = call({"data_root": cand_root, "indices": [0],
                                   "rerun_old": False, "candidates_revision": rev,
                                   "ob_vault_root": bad_vault})
                    check("9h %s入口 ob_vault_root=%s -> 400（未放宽）" % (ename, label),
                          c2 == 400, (ename, label, c2, r2))
                    check("9h %s入口 ob_vault_root=%s 人话含字段名" % (ename, label),
                          "ob_vault_root" in r2.get("error", ""), r2)

            # 正对照：显式给笔记库字符串同样能成功（不因修法误伤该路径）
            # 先换一条未导入的候选（9g 已把上一条标记 imported，否则只会“已导入”拒收）
            write_candidates(cand_root, [
                {"wrong": "带库错词", "right": "带库正词", "confidence": "high"}])
            c3, r3 = server._run_vocab_candidates_apply({
                "data_root": cand_root, "indices": [0], "rerun_old": False,
                "candidates_revision": server._vocab_candidates_revision(cand_root),
                "ob_vault_root": os.path.join(cand_root, "vault")})
            check("9h 显式给笔记库字符串同样成功（正对照）",
                  c3 == 200 and r3.get("ok"), (c3, r3))
            check("9h 正对照确实导入≥1条", int(r3.get("imported") or 0) >= 1, r3)

            # 修复前对照：旧形态（把可选键 None 写回 params）确实 400 → 任务必 failed
            c5, r5 = server._run_vocab_candidates_apply({
                "data_root": cand_root, "indices": [0], "rerun_old": False,
                "candidates_revision": server._vocab_candidates_revision(cand_root),
                "ob_vault_root": None})
            check("9h 对照：旧形态（写回 None）确实 400 开发者文案（=修复前必失败）",
                  c5 == 400 and "ob_vault_root" in r5.get("error", ""), (c5, r5))

            # P1-三1 根因守卫（源头式）：可选键只许在“有值”时补，不许写回 None
            src = _server_source()
            check("9h 源码不再把可选键以 None 写回参数（P1-三1 根因）",
                  '"ob_vault_root": vault_s' not in src, None)
            guarded = True
            for _m in re.finditer(r'\["ob_vault_root"\] = vault_s', src):
                if "if vault_s" not in src[max(0, _m.start() - 90):_m.start()]:
                    guarded = False
            check("9h 每次写 vault_s 都有 if vault_s 守卫（同类扫查结果）",
                  guarded, None)
        finally:
            shutil.rmtree(cand_root, ignore_errors=True)
    finally:
        try:
            if os.path.lexists(link):
                os.remove(link)
        except OSError:
            pass
        shutil.rmtree(root_a, ignore_errors=True)
        shutil.rmtree(root_b, ignore_errors=True)
        shutil.rmtree(noroot, ignore_errors=True)


# ------------------------------------------------------------------ 10 P1-3 语义守卫
#
# 七项：①无目标不画 100%（统计/接口层口径）②运行中参数锁定（后端 fail-closed）
# ③零目标/坏文件提示分开 ④失败统计统一可复算 ⑤长任务 elapsed ⑥范围二选一不得双空
# （前端单选桩在 selftest_p1_2_frontend.py S8h）⑦P2-7 /api/retry 带 data_root。

def part10_p13_semantics(server):
    root_a = build_root_a(server)
    root_b = tempfile.mkdtemp(prefix="p12_p13_b_")
    noroot = make_data_root(server, "P13N", [OK_SPEC])
    assert_tmp(root_a, "part10.A")
    assert_tmp(root_b, "part10.B")
    assert_tmp(noroot, "part10.noroot")
    saved_job = server._vocab_apply_job
    saved_listener = dict(server._listener)
    saved_done = set(server._worker_done)
    try:
        # ---- 10a 失败统计统一可复算（CANDIDATE-APPLY P3-2）
        items = [{"ok": True},
                 {"ok": False, "state": "FAILED"},
                 {"ok": False, "skipped_user_edited": True},
                 {"ok": False, "state": "NEEDS_HUMAN"},
                 {"ok": False, "state": "INTERRUPTED"},
                 {"ok": False, "state": "WEIRD_UNKNOWN"}]
        st = server._reapply_stats(items, total=6)
        check("10a 五桶之和 == total（逐条可复算）",
              st["success"] + st["failed"] + st["skipped"] + st["needs_human"]
              + st["interrupted"] == st["total"] == 6, st)
        check("10a 跳过/待人工/中断各归各桶（不重复计入失败）",
              st["success"] == 1 and st["skipped"] == 1 and st["needs_human"] == 1
              and st["interrupted"] == 1 and st["failed"] == 2, st)
        check("10a 未知 state / 坏条目 fail-closed 记失败（不静默丢弃）",
              st["failed"] == 2
              and server._reapply_result_bucket(None) == "failed"
              and server._reapply_result_bucket("x") == "failed")
        old_failed = sum(1 for it in items if not it.get("ok"))
        check("10a 对照：旧口径 failed=not ok 会算成 5（少 3 桶，汇总对不上）",
              old_failed == 5 and st["failed"] == 2, (old_failed, st))
        check("10a balanced 自检（counted!=total 时为假）",
              st["balanced"] is True
              and server._reapply_stats([{"ok": True}], total=3)["balanced"] is False)

        # ---- 10a3 两链同源（QA-P13-P2-3-UNKNOWN-STATE）
        # 判据只许有**一处真源**：同一 state 在两条链必须落同一语义桶；
        # 且 ok=True ＋ 未知 state 必须 fail-closed 进 failed（旧形态判 success）。
        same_source = True
        for _s in sorted(server.STATE_BUCKET):
            _sem = server._state_bucket(_s)
            if server._RECOVERY_BUCKET_NAMES[_sem] != server._recovery_bucket(_s):
                same_source = False
            if server._reapply_result_bucket({"ok": True, "state": _s}) != _sem:
                same_source = False
        check("10a3 全部已知 state：恢复链与重跑链归类逐字同源（同一张表）",
              same_source, sorted(server.STATE_BUCKET))
        check("10a3 「有牙」①：ok=True ＋ 未知 state 判 failed（fail-closed，不许升成功）",
              server._reapply_result_bucket({"ok": True, "state": "WEIRD_UNKNOWN"})
              == "failed"
              and server._reapply_result_bucket({"ok": True, "state": "TYPO_STATE"})
              == "failed", None)
        check("10a3 「有牙」②：已知合法成功态仍算 success（防过度修正）",
              all(server._reapply_result_bucket({"ok": True, "state": _s}) == "success"
                  for _s in server.DONE_STATES)
              and server._reapply_result_bucket({"ok": True, "state": "SUCCEEDED"})
              == "success", server.DONE_STATES)
        check("10a3 未知 state 在恢复链同为失败桶（两链口径一致，不是各说各话）",
              server._recovery_bucket("WEIRD_UNKNOWN") == "still_failed"
              and server._state_bucket("WEIRD_UNKNOWN") == "failed")
        # 存量重跑结果本身不带 state（真源＝ok 标志＋跳过标记），不许被 fail-closed 误伤
        check("10a3 无 state 的既有条目仍按 ok 标志判（正常成功不被误伤）",
              server._reapply_result_bucket({"ok": True, "run_id": "r"}) == "success"
              and server._reapply_result_bucket({"ok": False, "run_id": "r"}) == "failed")

        # ---- 10a4 P2-三1：判据是「**键在不在**」，不是「值真不真」
        # 旧写法 `if str(item.get("state") or "").strip():` 把「键存在但值为空串/纯空白/None」
        # 与「压根没给 state 键」混为一类 → {"ok":True,"state":""} 落到 success，而
        # `_recovery_bucket("")` 落 still_failed，**两链仍不同源**（review 复核三 P2-三1）。
        check("10a4 {\"ok\":True,\"state\":\"\"} → failed（显式空 state 不许升成成功）",
              server._reapply_result_bucket({"ok": True, "state": ""}) == "failed", None)
        check("10a4 显式空白/None 同样以键为准走表 → failed（不回落 ok）",
              server._reapply_result_bucket({"ok": True, "state": "   "}) == "failed"
              and server._reapply_result_bucket({"ok": True, "state": None}) == "failed", None)
        check("10a4 显式空/坏 state 与恢复链同源（不是各说各话）",
              server._state_bucket("") == "failed"
              and server._recovery_bucket("") == "still_failed"
              and server._RECOVERY_BUCKET_NAMES[server._state_bucket("")]
              == server._recovery_bucket(""), None)
        check("10a4 对照：{\"ok\":True}（**没有** state 键）→ 仍 success（防误伤）",
              server._reapply_result_bucket({"ok": True}) == "success", None)
        st_empty = server._reapply_stats(
            [{"ok": True, "state": ""}, {"ok": True}], total=2)
        check("10a4 掺入显式空 state 后仍可复算（五桶之和==total，balanced 真）",
              st_empty["failed"] == 1 and st_empty["success"] == 1
              and st_empty["counted"] == st_empty["total"] == 2
              and st_empty["balanced"] is True, st_empty)
        st_mix = server._reapply_stats(
            [{"ok": True, "state": "WEIRD_UNKNOWN"}, {"ok": True},
             {"ok": False, "state": "FAILED"}], total=3)
        check("10a3 掺入未知 state 后仍可复算（total==五桶之和，balanced 真）",
              st_mix["success"] == 1 and st_mix["failed"] == 2
              and st_mix["counted"] == st_mix["total"] == 3
              and st_mix["balanced"] is True, st_mix)
        # 出口字段名锁死（前端 app/index.html 已按这些键消费）：只许同源，不许改名
        check("10a3 五桶出口字段名不变（success/failed/skipped/needs_human/interrupted）",
              server._REAPPLY_BUCKETS == ("success", "failed", "skipped",
                                          "needs_human", "interrupted")
              and server.FIVE_BUCKETS == server._REAPPLY_BUCKETS
              and server.RECOVERY_BUCKETS == ("recovered", "still_failed", "skipped",
                                              "needs_human", "interrupted"), None)
        # 源头单点守卫：两个 bucket 函数体内不许再各写一套 state 字面量 if 链
        _src = _server_source()

        def _fn_body(name):
            _i = _src.index("def %s(" % name)
            _j = _src.find("\ndef ", _i + 1)
            return _src[_i:_j if _j > 0 else len(_src)]

        check("10a3 判据单点：两个 bucket 函数都从 `_state_bucket` 派生",
              "_state_bucket(" in _fn_body("_recovery_bucket")
              and "_state_bucket(" in _fn_body("_reapply_result_bucket"), None)
        check("10a3 旧形态特征已清零：bucket 函数体内不再有 state 字面量 if 链",
              all(_tok not in _fn_body("_recovery_bucket")
                  for _tok in ('"SUCCEEDED"', '"SKIPPED"', '"NEEDS_HUMAN"',
                               '"INTERRUPTED"'))
              and '"SKIPPED"' not in _fn_body("_reapply_result_bucket"), None)
        check("10a3 真源只定义一处（STATE_BUCKET 全文唯一赋值）",
              _src.count("STATE_BUCKET = {") == 1, _src.count("STATE_BUCKET = {"))
        # 10a4 源头守卫：判据必须是「state 键在不在」，旧的值真值写法（`or ""`＋strip）已清零
        _body_reapply = _fn_body("_reapply_result_bucket")
        check("10a4 判据单点：函数体按「键存在」判断（值真值写法已清零）",
              '"state" in ' in _body_reapply
              and 'str(item.get("state") or "")' not in _body_reapply, None)

        # ---- 10a2 批量恢复五桶同口径（同一条可复算等式）
        job = {"total": 4, "results": [{"state": "SUCCEEDED"}, {"state": "SKIPPED"},
                                       {"state": "NEEDS_HUMAN"}]}
        server._recovery_apply_counts(job)
        check("10a2 批量恢复五桶可复算（未落盘的剩余目标记中断）",
              job["recovered"] == 1 and job["skipped"] == 1 and job["needs_human"] == 1
              and job["still_failed"] == 0 and job["interrupted"] == 1
              and job["counted"] == job["total"] == 4 and job["balanced"] is True, job)
        check("10a2 done=已落盘逐项数（不被 interrupted 拉到 total，进度不虚满）",
              job["done"] == 3, job)
        check("10a2 未知 state 进失败桶（fail-closed）",
              server._recovery_bucket("WHATEVER") == "still_failed"
              and server._recovery_bucket(None) == "still_failed")
        job2 = {"total": 1, "results": [{"state": "SUCCEEDED"},
                                        {"state": "FAILED"}]}
        server._recovery_apply_counts(job2)
        check("10a2 逐项多于登记总数时 total 抬到可复算之和（绝不小于各桶之和）",
              job2["total"] == 2 and job2["counted"] == 2 and job2["balanced"] is True,
              job2)

        # ---- 10b 批量任务状态：counted/balanced/elapsed 可读
        jobs_dir = os.path.join(root_a, "data", "recovery_jobs")
        os.makedirs(jobs_dir, exist_ok=True)
        digest = server._recovery_root_digest(root_a)
        with open(os.path.join(jobs_dir, "rec-p13run.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"job_id": "rec-p13run", "state": "RUNNING",
                       "data_root_digest": digest, "total": 3,
                       "started_at": "2026-09-15T00:00:00Z",
                       "results": [{"run_id": "r1", "state": "SUCCEEDED"},
                                   {"run_id": "r2", "state": "FAILED"}]}, fh)
        code, res = server._handle_retry_batch_status(
            {"data_root": [root_a], "job_id": ["rec-p13run"]})
        check("10b 未终态 job 仍按既有语义降级中断", code == 200
              and res.get("state") == "INTERRUPTED", (code, res))
        check("10b 汇总恒可复算：total == recovered+still_failed+skipped+needs_human+interrupted",
              res.get("total") == (res.get("recovered", 0) + res.get("still_failed", 0)
                                   + res.get("skipped", 0) + res.get("needs_human", 0)
                                   + res.get("interrupted", 0)), res)
        check("10b 未落盘剩余目标记中断（3=1成功+1失败+1中断）",
              res.get("recovered") == 1 and res.get("still_failed") == 1
              and res.get("interrupted") == 1, res)
        check("10b balanced 自检＋counted==total＋done=逐项数",
              res.get("balanced") is True and res.get("counted") == res.get("total")
              and res.get("done") == 2, res)
        with open(os.path.join(jobs_dir, "rec-p13done.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"job_id": "rec-p13done", "state": "SUCCEEDED",
                       "data_root_digest": digest, "total": 2,
                       "started_at": "2026-09-15T00:00:00Z",
                       "finished_at": "2026-09-15T00:01:30Z",
                       "results": [{"run_id": "r1", "state": "SUCCEEDED"},
                                   {"run_id": "r2", "state": "FAILED"}]}, fh)
        code, res = server._handle_retry_batch_status(
            {"data_root": [root_a], "job_id": ["rec-p13done"]})
        check("10b 终态汇总可复算（2=1+1+0+0+0）",
              res.get("total") == 2 and res.get("recovered") == 1
              and res.get("still_failed") == 1 and res.get("balanced") is True, res)
        check("10b 长任务 elapsed_seconds 可读（90s，由两端时间戳算）",
              res.get("elapsed_seconds") == 90, res.get("elapsed_seconds"))
        check("10b 坏/缺时间戳回 0（不抛异常也不编时长）",
              server._elapsed_seconds("not-a-time") == 0
              and server._elapsed_seconds(None, None) == 0
              and server._elapsed_seconds("2026-09-15T00:00:00Z",
                                          "2026-09-15T00:00:00Z") == 0)

        # ---- 10c 候选清单三态：缺失与腐坏必须分开（CANDIDATE-APPLY P3-4）
        code, g = server._handle_vocab_candidates_get({"data_root": [noroot]})
        missing_msg = str(g.get("candidates_state_message") or "")
        check("10c 无清单 -> missing（不是 corrupt）",
              code == 200 and g.get("candidates_state") == "missing"
              and g.get("source_exists") is False
              and g.get("has_candidates") is False, g)
        cpath = os.path.join(noroot, "vocab-candidates.json")
        with open(cpath, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")
        bad_hash = sha(cpath)
        code, g2 = server._handle_vocab_candidates_get({"data_root": [noroot]})
        corrupt_msg = str(g2.get("candidates_state_message") or "")
        check("10c 腐坏文件 -> corrupt 且 source_exists=True",
              code == 200 and g2.get("candidates_state") == "corrupt"
              and g2.get("source_exists") is True, g2)
        check("10c 腐坏与缺失文案必须不同（腐坏证据不被空态吞掉）",
              missing_msg != corrupt_msg and "损坏" in corrupt_msg,
              (missing_msg, corrupt_msg))
        check("10c 腐坏不冒充空态（文案里没有「暂无待审候选」）",
              "暂无待审候选" not in corrupt_msg, corrupt_msg)
        check("10c 对照：腐坏时 has_candidates=False（旧口径下页面只能显示「暂无」）",
              g2.get("has_candidates") is False)
        check("10c 读坏文件不改文件（No-Clobber）", sha(cpath) == bad_hash)
        with open(cpath, "w", encoding="utf-8") as fh:
            fh.write('{"not": "a list"}')
        code, g3 = server._handle_vocab_candidates_get({"data_root": [noroot]})
        check("10c 内容不是数组也算 corrupt（不是 ok）",
              g3.get("candidates_state") == "corrupt", g3)
        write_candidates(noroot, [{"wrong": "三态错词", "right": "三态正词",
                                   "confidence": "high"}])
        code, g4 = server._handle_vocab_candidates_get({"data_root": [noroot]})
        check("10c 正常清单 -> ok 且有候选",
              g4.get("candidates_state") == "ok"
              and g4.get("has_candidates") is True, g4)

        # ---- 10d 零目标：人话而非裸键名（CANDIDATE-APPLY P3-3）
        rev = server._vocab_candidates_revision(noroot)
        before = tree_snapshot(noroot)
        job_snap = server._vocab_apply_job
        code, res = server._handle_vocab_candidates_apply(body({
            "data_root": noroot, "indices": [], "rerun_old": False,
            "candidates_revision": rev}))
        check("10d 空 indices -> 400 人话（不是「不能为空数组」裸键名）",
              code == 400 and "没有勾选任何待审候选" in res.get("error", "")
              and "不能为空数组" not in res.get("error", ""), (code, res))
        code, res = server._run_vocab_candidates_apply({
            "data_root": noroot, "indices": [], "rerun_old": False,
            "candidates_revision": rev})
        check("10d （同步入口）空 indices -> 400 同口径",
              code == 400 and "没有勾选任何待审候选" in res.get("error", ""),
              (code, res))
        check("10d 零目标零执行零写盘",
              server._vocab_apply_job is job_snap and tree_snapshot(noroot) == before)
        code, res = server._handle_retry_plan_post(body({
            "data_root": noroot, "run_ids": []}))
        check("10d 批量预览空选择 -> 400 人话（不是裸键名）",
              code == 400 and "没有要恢复的任务" in res.get("error", "")
              and "不能为空数组" not in res.get("error", ""), (code, res))

        # ---- 10d2 零目标重跑文案：词入库了但无可重跑稿件，必须说清
        root_nt = make_data_root(server, "P13NT", [{"run_id": "run-queued",
                                                    "status": "QUEUED"}])
        assert_tmp(root_nt, "part10.notarget")
        try:
            write_candidates(root_nt, [{"wrong": "零目标错词", "right": "零目标正词",
                                        "confidence": "high"}])
            code, res = server._run_vocab_candidates_apply({
                "data_root": root_nt, "indices": [0], "rerun_old": True,
                "candidates_revision": server._vocab_candidates_revision(root_nt)})
            check("10d2 入库成功但无可重跑稿件 -> 200",
                  code == 200 and res.get("ok"), (code, res))
            msg = str(res.get("message") or "")
            check("10d2 明说「没有可重跑的已完成任务」",
                  "没有可重跑的已完成任务" in msg, msg)
            check("10d2 不再用「重跑成功0篇」冒充跑过（旧文案）",
                  "重跑成功0篇" not in msg, msg)
            stats = res.get("stats") or {}
            check("10d2 stats.total=0 且五桶之和为 0（不画满的依据）",
                  stats.get("total") == 0
                  and sum(int(stats.get(k) or 0) for k in
                          ("success", "failed", "skipped", "needs_human",
                           "interrupted")) == 0
                  and stats.get("balanced") is True, stats)
        finally:
            shutil.rmtree(root_nt, ignore_errors=True)

        # ---- 10e 运行中参数锁定（RERUN-PROGRESS P3-5）：后端 fail-closed
        root_lock = make_data_root(server, "P13LK", [OK_SPEC])
        assert_tmp(root_lock, "part10.lock")
        try:
            write_candidates(root_lock, [{"wrong": "锁定错词", "right": "锁定正词",
                                          "confidence": "high"}])
            rev_lock = server._vocab_candidates_revision(root_lock)
            server._vocab_apply_job = {
                "job_id": "vocab-apply-lock", "state": "running", "stage": "importing",
                "data_root": root_lock, "rerun_old": True,
                "candidates_revision": rev_lock, "request_indices": [0, 1],
                "started_at": server._utc_now_iso(), "finished_at": None,
                "total": 0, "done": 0, "current_filename": None, "imported": 0,
                "summary": {}, "stats": None, "error": None,
                "message": "", "result": None}
            lock_before = tree_snapshot(root_lock)
            # 故意带「过期版本 + 另一套参数」：旧逻辑会先撞版本锁，新逻辑必须先锁定
            code, res = server._handle_vocab_candidates_apply(body({
                "data_root": root_lock, "indices": [0], "rerun_old": False,
                "candidates_revision": "deadbeefdeadbeef"}))
            check("10e 运行中提交 -> 409 人话（零执行）",
                  code == 409 and res.get("running") is True
                  and "已锁定" in res.get("error", ""), (code, res))
            check("10e 锁定检查先于版本锁（不报「清单已变化」）",
                  "候选清单已变化" not in res.get("error", ""), res)
            lp = res.get("locked_params") or {}
            check("10e 同目录回显冻结参数（rerun_old/目标集合＝那次任务的）",
                  lp.get("rerun_old") is True
                  and list(lp.get("indices") or []) == [0, 1], lp)
            check("10e 运行中变更零执行零写盘",
                  tree_snapshot(root_lock) == lock_before
                  and not os.path.exists(os.path.join(root_lock, "vocab-user.json")))
            code, res_b = server._handle_vocab_candidates_apply(body({
                "data_root": root_b, "indices": [0], "rerun_old": False,
                "candidates_revision": "deadbeefdeadbeef"}))
            check("10e 别目录 409 不回显别处的冻结参数（D-12）",
                  code == 409 and "locked_params" not in res_b
                  and root_lock not in json.dumps(res_b, ensure_ascii=False), res_b)
            code, sres = server._handle_vocab_apply_status(
                {"data_root": [root_lock], "job_id": ["vocab-apply-lock"]})
            jobout = (sres or {}).get("job") or {}
            check("10e 运行中状态回 elapsed_seconds＋indices_count（页面＝实际执行）",
                  code == 200 and isinstance(jobout.get("elapsed_seconds"), int)
                  and jobout.get("indices_count") == 2
                  and jobout.get("rerun_old") is True, jobout)
            server._vocab_apply_job = dict(server._vocab_apply_job, state="done")
            code, res = server._handle_vocab_candidates_apply(body({
                "data_root": root_lock, "indices": [0], "rerun_old": False,
                "candidates_revision": "deadbeefdeadbeef"}))
            check("10e 终态后锁解除（改为命中版本锁，不再是锁定 409）",
                  code == 409 and "候选清单已变化" in (res or {}).get("error", ""),
                  (code, res))
        finally:
            server._vocab_apply_job = saved_job
            shutil.rmtree(root_lock, ignore_errors=True)

        # ---- 10f P2-7 /api/retry 带 data_root：跨目录 fail-closed、同目录不误伤
        server._listener["running"] = True
        server._listener["data_root"] = root_a
        done_before = set(server._worker_done)
        code, res = server._handle_retry_post(body({
            "run_id": "run-retry", "data_root": root_b}))
        check("10f 跨目录重试 -> 409 人话且不回两个真实路径",
              code == 409 and "另一个数据目录" in res.get("error", "")
              and root_a not in json.dumps(res, ensure_ascii=False)
              and root_b not in json.dumps(res, ensure_ascii=False), (code, res))
        check("10f 跨目录重试零执行（未改工作队列）",
              set(server._worker_done) == done_before)
        for label, bad in (("布尔", True), ("相对路径", "relative/x"), ("数组", ["x"])):
            code, res = server._handle_retry_post(body({
                "run_id": "run-retry", "data_root": bad}))
            check("10f data_root=%s -> 400 人话零执行" % label,
                  code == 400 and bool(res.get("error"))
                  and root_a not in res.get("error", ""), (label, code, res))
        # ---- 10g P2-2 前后端一致：前端 retryBody 的本地门只拦「有值但非绝对路径」，
        #      正是因为它复用的这句 400 人话；空串/缺键在后端是合法旧行为，本地不许拦。
        code, res = server._handle_retry_post(body({
            "run_id": "run-retry", "data_root": "relative/x"}))
        check("10g 相对路径 400 文案＝前端本地门同一句（数据目录须为绝对路径）",
              code == 400 and "数据目录须为绝对路径" in res.get("error", ""),
              (code, res))
        code, res = server._handle_retry_post(body({
            "run_id": "run-retry", "data_root": ""}))
        check("10g 空串 data_root 仍按旧行为放行（前端本地门因此不拦空值）",
              code == 202 and res.get("ok"), (code, res))
        code, res = server._handle_retry_post(body({
            "run_id": "run-retry", "data_root": root_a}))
        check("10f 同目录重试 -> 202（正常路径不被误伤）",
              code == 202 and res.get("ok"), (code, res))
        link_lk = os.path.join(os.path.dirname(root_a),
                               os.path.basename(root_a) + "-rlk")
        try:
            if os.path.lexists(link_lk):
                os.remove(link_lk)
            os.symlink(root_a, link_lk)
            code, res = server._handle_retry_post(body({
                "run_id": "run-retry", "data_root": link_lk}))
            check("10f 符号链接指向同一目录不算跨目录（realpath 口径）",
                  code == 202, (code, res))
        finally:
            try:
                if os.path.lexists(link_lk):
                    os.remove(link_lk)
            except OSError:
                pass
        code, res = server._handle_retry_post(body({"run_id": "run-retry"}))
        check("10f 不带 data_root 沿用旧行为（按监听目录，向后兼容）",
              code == 202, (code, res))
        code, res = server._handle_retry_post(body({
            "run_id": "run-does-not-exist", "data_root": root_a}))
        # 合成库里没有 Single Instance 锁 → open_db 抛错被既有 best-effort 分支吞掉
        # （注释明写「DB 暂时不可读则仍允许重试，worker 下轮会记原因，不拦」）；
        # 真库持锁时会先回 404。这里只守「不泄漏路径 + 只回 202/404」。
        check("10f 同目录但 run 不存在：只回 202/404 且错误出口不含真实路径",
              code in (202, 404)
              and root_a not in json.dumps(res, ensure_ascii=False), (code, res))
    finally:
        server._vocab_apply_job = saved_job
        server._listener.clear()
        server._listener.update(saved_listener)
        server._worker_done.clear()
        server._worker_done.update(saved_done)
        shutil.rmtree(root_a, ignore_errors=True)
        shutil.rmtree(root_b, ignore_errors=True)
        shutil.rmtree(noroot, ignore_errors=True)


# ------------------------------------------------------------------ 11 P1-4 脱敏摘要（FR-3/HD-2=A）

# FR-3 允许进一键复制正文的 7 类字段——前端 `FAIL_DIGEST_FIELDS` 白名单的契约来源
DIGEST_SOURCE_FIELDS = ("source_label", "source_dir_tail", "raw_error_code",
                        "action_category", "confidence", "missing_evidence", "next_action")
# HD-2=A/DoD5：只做脱敏摘要，不做完整路径导出
NO_FULLPATH_EXPORT = ("导出全路径", "导出完整路径", "导出绝对路径",
                      "复制完整路径", "复制全路径")


def part11_p14_digest(server):
    """P1-4/FR-3/HD-2=A：一键复制摘要所依赖的字段与脱敏口径，在后端这一侧钉死。

    DoD5「不提供完整绝对路径导出」＝接口只暴露打码后的字段：本用例断言诊断响应里
    既没有真实绝对路径（含 tmp 的 `/var/…` 真形态），也没有任何字段等于真实登记路径。
    """
    root = build_root_a(server)
    assert_tmp(root, "part11_p14_digest")
    try:
        code, diag = server._handle_failure_diagnosis({"data_root": [root]})
        check("11a 诊断接口可得", code == 200 and diag.get("ok") is True, (code, diag))
        items = diag.get("items") or []
        check("11a 有未完成项可诊断", len(items) >= 1, len(items))

        # 11b FR-3 摘要 7 类来源字段逐条齐备且非空（前端白名单字段的契约来源）
        missing = sorted({k for k in DIGEST_SOURCE_FIELDS for i in items if k not in i})
        check("11b 摘要 7 类来源字段逐条齐备", not missing, missing)
        blank = sorted({k for k in DIGEST_SOURCE_FIELDS for i in items
                        if not str(i.get(k) or "").strip()})
        check("11b 7 类字段逐条非空（未知也要写 UNKNOWN/占位，不留空）", not blank, blank)

        # 11c 脱敏：整包零真实绝对路径（复用 6 节同一 SENSITIVE 扫描口径，不另造一套）
        scan_leak("诊断响应零绝对路径/正文/token（P1-4）", diag, [root, TMP_ROOT])
        check("11c 原登记路径逐条已打码（…/ 形态）",
              all(str(i.get("recorded_path_redacted", "")).startswith("…/") for i in items),
              [(i.get("run_id"), i.get("recorded_path_redacted")) for i in items])
        real = {os.path.join(root, "_src", "%s.mp4" % i["run_id"]) for i in items}
        flat = json.dumps(diag, ensure_ascii=False)
        check("11c 无任何字段等于真实登记路径（HD-2=A 不做完整路径导出）",
              not any(p in flat for p in real), sorted(p for p in real if p in flat))

        # 11d 目录尾段与列表侧同源同口径（复用 _dir_tail，不另造第二套尾段写法）
        code_s, snap = server._handle_status({"data_root": [root], "limit": ["200"]})
        by_run = {str(r.get("run_id")): r for r in (snap.get("recent_runs") or [])}
        pairs = [(i["run_id"], i["source_dir_tail"], by_run[i["run_id"]].get("source_dir_tail"))
                 for i in items if i["run_id"] in by_run]
        check("11d 诊断目录尾段与列表 source_dir_tail 逐条一致",
              bool(pairs) and all(a == b for _, a, b in pairs), pairs)
        check("11d 目录尾段逐条是打码形态（…/ 开头）",
              all(str(i.get("source_dir_tail", "")).startswith("…/") for i in items),
              [(i.get("run_id"), i.get("source_dir_tail")) for i in items])

        # 11e 口径单测（HD-2=A 原文例子「…/第七周/xxx.mp4」）
        check("11e _diag_redact_path 只留 basename＋两级父目录标签",
              server._diag_redact_path(
                  "/Users/zzymima0000/Downloads/需转录视频/第七周/样例.mp4")
              == "…/需转录视频/第七周/样例.mp4",
              server._diag_redact_path(
                  "/Users/zzymima0000/Downloads/需转录视频/第七周/样例.mp4"))
        check("11e _dir_tail 只留末段",
              server._dir_tail("/Users/zzymima0000/Downloads/需转录视频/第七周") == "…/第七周",
              server._dir_tail("/Users/zzymima0000/Downloads/需转录视频/第七周"))
        check("11e _strip_paths 含空格路径整段抹掉（宁可多抹不漏尾段）",
              server._strip_paths("打不开 /Users/zzy/My Data/vault/x.md") == "打不开 …",
              server._strip_paths("打不开 /Users/zzy/My Data/vault/x.md"))
        check("11e _strip_paths 遇中文标点收尾（不吃掉后文）",
              server._strip_paths("先看 /Users/a/b，再点重试") == "先看 …，再点重试",
              server._strip_paths("先看 /Users/a/b，再点重试"))

        # 11f 类别/置信度/错误码只许枚举或明确占位，不许编造
        cats = {i["action_category"] for i in items}
        check("11f 类别取值属诊断枚举（不编造）",
              cats.issubset(set(server.DIAGNOSIS_ACTIONS)), sorted(cats))
        check("11f 置信度取值属 {HIGH, UNVERIFIED}",
              {i["confidence"] for i in items}.issubset({"HIGH", "UNVERIFIED"}),
              sorted({i["confidence"] for i in items}))
        check("11f 错误码逐条非空字符串（未知写 UNKNOWN）",
              all(isinstance(i["raw_error_code"], str) and i["raw_error_code"].strip()
                  for i in items), [i["raw_error_code"] for i in items])
        check("11f 缺失证据逐条非空字符串",
              all(str(i["missing_evidence"]).strip() for i in items),
              [i["missing_evidence"] for i in items])
        check("11f 建议（next_action）逐条非空人话",
              all(str(i["next_action"]).strip() for i in items),
              [i["next_action"] for i in items])

        # 11g 前端入口：一键复制的是脱敏摘要；不新增「导出全路径」类按钮（HD-2=A）
        html = open(os.path.join(ROOT, "app", "index.html"), encoding="utf-8").read()
        hits = [k for k in NO_FULLPATH_EXPORT if k in html]
        check("11g 未新增「导出全路径」类入口（HD-2=A/DoD5）", not hits, hits)
        check("11g 复制入口文案标明「脱敏摘要」", "复制脱敏摘要" in html)
        check("11g 摘要只由白名单 7 键出口（无第 8 类字段拼装）",
              'var FAIL_DIGEST_FIELDS=["label","tail","code","category","confidence",'
              '"missing","next"];' in html, "FAIL_DIGEST_FIELDS 声明缺失或字段变了")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def part12_p14_alt_branch(server):
    """P2-2：真 16 条那条唯一分支——「源文件不在原位＋替代位置身份匹配」。

    旧夹具把 `content_identity` 写死 `"x"*40` → `_diag_identity` 恒 MISMATCH →
    `SOURCE_LOCATION_REVIEW`／`MATCH`／`confidence=HIGH`／`alternate_path_redacted!=UNKNOWN`
    在自测里**根本不可达**，于是最敏感的那个字段（替代路径＝用户把文件搬到哪儿）
    **没有任何断言在守**。本用例把该分支跑通，并钉死它必须是脱敏值。
    """
    root = make_data_root(server, "ALT", [ALT_SPEC])
    assert_tmp(root, "part12_p14_alt_branch")
    try:
        code, diag = server._handle_failure_diagnosis({"data_root": [root]})
        check("11h 替代路径用例：诊断接口可得", code == 200 and diag.get("ok") is True, (code, diag))
        items = diag.get("items") or []
        check("11h 替代路径用例：可诊断到 1 条", len(items) == 1, items)
        it = items[0] if items else {}
        # 分支可达性：登记路径无文件（否则不会去扫替代位置）＋身份真 MATCH
        check("11h 分支可达：源不在原位（recorded_path_exists=False）",
              it.get("recorded_path_exists") is False, it.get("recorded_path_exists"))
        check("11h 分支可达：替代位置身份匹配 MATCH（旧夹具恒 MISMATCH，到不了这里）",
              it.get("identity_match") == "MATCH", it.get("identity_match"))
        check("11h 类别＝SOURCE_LOCATION_REVIEW 且置信度＝HIGH",
              it.get("action_category") == "SOURCE_LOCATION_REVIEW"
              and it.get("confidence") == "HIGH",
              (it.get("action_category"), it.get("confidence")))
        check("11h 替代路径确实被检查过（alternate_path_checked=True）",
              it.get("alternate_path_checked") is True, it.get("alternate_path_checked"))

        # 11i 最敏感字段：替代路径必须脱敏（把 server.py 的 _diag_redact_path 拿掉即 rc=1）
        alt_real = os.path.join(root, "_alt", "run-alt.mp4")
        alt = str(it.get("alternate_path_redacted") or "")
        check("11i 替代路径不是 UNKNOWN（真取到了值，不是空跑）",
              alt not in ("", "UNKNOWN"), alt)
        check("11i 替代路径已脱敏（…/ 形态，只留末 3 段）",
              alt.startswith("…/") and "/var/" not in alt and "/private/" not in alt, alt)
        check("11i 替代路径不等于真实替代路径（HD-2=A 不做完整路径导出）",
              alt != alt_real, (alt, alt_real))
        flat = json.dumps(diag, ensure_ascii=False)
        check("11i 响应里不存在真实替代路径明文", alt_real not in flat)
        scan_leak("11i 替代路径分支的响应零绝对路径/正文/token（P1-4）", diag, [root, TMP_ROOT])
        check("11i 原登记路径同样只留打码形态",
              str(it.get("recorded_path_redacted", "")).startswith("…/"),
              it.get("recorded_path_redacted"))

        # 11i2 对照：替代路径不存在时该字段仍是 UNKNOWN（不编造替代路径）
        noroot = make_data_root(server, "NOALT", [NOALT_SPEC])
        assert_tmp(noroot, "part12_p14_alt_branch.noroot")
        try:
            code2, diag2 = server._handle_failure_diagnosis({"data_root": [noroot]})
            items2 = diag2.get("items") or []
            check("11i2 对照：找不到替代位置时 identity 不 MATCH、字段写 UNKNOWN",
                  code2 == 200 and len(items2) == 1
                  and items2[0].get("identity_match") != "MATCH"
                  and items2[0].get("alternate_path_redacted") == "UNKNOWN",
                  [(i.get("identity_match"), i.get("alternate_path_redacted")) for i in items2])
        finally:
            shutil.rmtree(noroot, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------- 13 P1-5 词库展示层的落盘边界

def part13_p15_vocab_display(server):
    """P1-5 词库与候选易用性修整（前端 `index.html`）：把「trim 只做展示层归一化」
    这条边界在后端这一侧钉死。

    本批 12 项全部落在前端展示层（分组标签/trim/空态/筛选计数/组头点击/全选初态），
    后端零改动。这里守两件事：
      ① 落盘语义没被展示层的 trim 波及——保存写入的串与传入逐字一致（不 trim、
         不动 source），读取侧既有归一化只 strip、不改大小写（所以前端 `vocabGroupFor`
         必须自己 trim+小写才归得对组，P3-2 不是多余代码）；
      ② 后端候选导入确实会落 `source:"candidate"`（P3-1 的根因），所以前端必须把它
         映射进四组标签之一、不能原样回显。
    """
    root = make_data_root(server, "P15", [])
    assert_tmp(root, "part13_p15_vocab_display")
    try:
        # 13a 保存逐字落盘：不带任何展示层归一化
        raw = [{"wrong": "  带空格错词  ", "right": "  带空格正词  ",
                "source": " Candidate "}]
        server._save_vocab_entries(root, raw)
        saved = read_json(os.path.join(root, "vocab-user.json"), None)
        check("13a 保存逐字落盘（不 trim、不动 source 原样）", saved == raw, saved)

        # 13b 读取侧只 strip、不改大小写 → 前端不自己 trim+小写就会归错组
        loaded = server._load_vocab_entries(root)
        check("13b 读取只 strip 不改大小写（前端需自行 trim+小写才归得对组）",
              loaded == [{"wrong": "带空格错词", "right": "带空格正词",
                          "source": "Candidate"}], loaded)

        # 13c 候选导入落盘 source 恒为 candidate（前端四组标签必须吸收它）
        write_candidates(root, [{"wrong": "候选错词", "right": "候选正词",
                                 "confidence": "high"}])
        code, get = server._handle_vocab_candidates_get({"data_root": [root]})
        rev = get.get("candidates_revision")
        code, res = server._run_vocab_candidates_apply({
            "data_root": root, "indices": [0], "rerun_old": False,
            "candidates_revision": rev})
        vocab = read_json(os.path.join(root, "vocab-user.json"), [])
        cand = [e for e in vocab if e.get("wrong") == "候选错词"]
        check("13c 候选导入落盘 source=candidate（前端须映射成四组标签之一）",
              code == 200 and res.get("ok") is True and len(cand) == 1
              and cand[0].get("source") == "candidate", (code, vocab))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------- 14 P1-6 完成分页 cursor 与 D-15

P16_COMPLETED_N = 61     # D-15 夹具：61 成功
P16_FAILED_N = 16        # 16 缺源（登记路径无文件）
P16_TS_NONE_N = 5        # 其中 5 条缺 completed_at（回退 updated_at）


def _p16_make_root(server):
    """D-15 夹具：77 条（61 成功＋16 缺源）。

    成功=processing_runs 行＋jobs/<run_id>/manifest.json（receipts 末个
    PUBLISHED，无输出路径 → 按 _scan_disk_states 口径计完成）；时间戳两两并列
    （同分钟成对），run_id 决胜可验；5 条成功缺 completed_at（回退 updated_at，
    且时间最老 → 稳定落在展开末页）；失败行无 manifest、源文件不落盘。
    """
    from stage2.store import DDL

    root = tempfile.mkdtemp(prefix="p16_d15_")
    assert_tmp(root, "part14_p16_completed_cursor")
    src_dir = os.path.join(root, "_src")
    os.makedirs(os.path.join(root, "data"))
    os.makedirs(src_dir)
    con = sqlite3.connect(os.path.join(root, "data", "state.db"))
    con.executescript(DDL)
    specs = []  # (run_id, status, completed_at, updated_at, completed?)
    for i in range(P16_COMPLETED_N - P16_TS_NONE_N):
        rid = "run-c-%03d" % i
        minute = i // 2  # 两两并列：0/1 同分，2/3 同分……
        ts = "2026-09-10T00:%02d:00Z" % minute
        specs.append((rid, "QUEUED", ts, ts, True))
    for i in range(P16_TS_NONE_N):
        rid = "run-n-%d" % i
        ts = "2026-09-08T00:0%d:00Z" % i
        specs.append((rid, "QUEUED", None, ts, True))
    for i in range(P16_FAILED_N):
        rid = "run-f-%02d" % i
        specs.append((rid, "FAILED_RETRYABLE", None,
                      "2026-09-09T10:%02d:00Z" % i, False))
    for rid, status, comp, upd, done in specs:
        src = os.path.join(src_dir, rid + ".mp4")
        if done:
            with open(src, "wb") as fh:
                fh.write(b"fake-media-" + rid.encode())
        con.execute(
            "INSERT INTO sources (source_id, path_identity_key,"
            " content_identity, logical_source_identity, current_path,"
            " current_location_type, source_size, source_mtime_ns, status,"
            " first_seen_at, last_seen_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("src_" + rid, src, "x" * 40, "lsid_" + rid, src, "LOCAL",
             1 if done else 0, 0, "ACTIVE", upd, upd))
        con.execute(
            "INSERT INTO processing_runs (run_id, source_id, creation_mode,"
            " auto_run_identity, asr_profile_hash, status, created_at,"
            " updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, "src_" + rid, "AUTO", "auto_" + rid, "profhash", status,
             upd, upd, comp))
        if done:
            jd = os.path.join(root, "data", "jobs", rid)
            os.makedirs(jd, exist_ok=True)
            with open(os.path.join(jd, "manifest.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"receipts": [{"state": "PUBLISHED",
                                         "verdict": "ok"}]}, fh)
    con.commit()
    con.close()
    return root


def _p16_expected_order():
    """测试侧独立复算排序：eff=completed_at 缺省回退 updated_at，(eff,run_id) DESC。"""
    rows = []
    for i in range(P16_COMPLETED_N - P16_TS_NONE_N):
        rid = "run-c-%03d" % i
        ts = "2026-09-10T00:%02d:00Z" % (i // 2)
        rows.append((rid, ts))
    for i in range(P16_TS_NONE_N):
        rows.append(("run-n-%d" % i, "2026-09-08T00:0%d:00Z" % i))
    rows.sort(key=lambda t: (t[1], t[0]), reverse=True)
    return [r[0] for r in rows], {r[0]: r[1] for r in rows}


def part14_p16_completed_cursor(server):
    """P1-6/FR-12/HD-6=A/D-15：完成列表分层、cursor 历史、完成统计。

    77 条夹具（61 成功＋16 缺源）下：当前/失败始终全量可达；完成默认 20；
    cursor（排序键+校验和，非 offset）展开全 61 无重复遗漏；并列时间戳由
    run_id DESC 决胜；坏/被篡改游标 400；recent_runs 原样（只加 completed 标记）。
    """
    root = _p16_make_root(server)
    expected, eff_of = _p16_expected_order()
    try:
        # 14a 默认页：完成 61、默认 20、失败/当前不受影响（recent_runs 全 77）
        code, snap = server._handle_status({"data_root": [root],
                                            "limit": ["200"]})
        check("14a status 200 且 ok", code == 200 and snap.get("ok") is True,
              (code, snap.get("ok")))
        check("14a completed_total=61（HD-6=A 完成统计）",
              snap.get("completed_total") == P16_COMPLETED_N,
              snap.get("completed_total"))
        check("14a completed_limit 默认 20",
              snap.get("completed_limit") == 20, snap.get("completed_limit"))
        page = snap.get("completed_page") or []
        check("14a 完成首页默认 20 条", len(page) == 20, len(page))
        check("14a next_cursor 存在（还有更早）",
              isinstance(snap.get("next_cursor"), str) and snap["next_cursor"],
              snap.get("next_cursor"))
        runs = snap.get("recent_runs") or []
        check("14a D-15 当前/失败全可达（recent_runs=77）",
              len(runs) == P16_COMPLETED_N + P16_FAILED_N, len(runs))
        flagged = [r["run_id"] for r in runs if r.get("completed") is True]
        unflagged = [r["run_id"] for r in runs if "completed" not in r]
        check("14a 完成行全打 completed 标记（61）", len(flagged) == 61,
              len(flagged))
        check("14a 失败行无 completed 键（非完成不受影响）",
              len(unflagged) == 16 and all(r.startswith("run-f-")
                                           for r in unflagged),
              unflagged[:3])

        # 14b D-15 完成统计与 run_summary 双口径一致
        rs = snap.get("run_summary") or {}
        check("14b run_summary done=61/failed=16/total=77",
              rs.get("done") == 61 and rs.get("failed") == 16
              and rs.get("total") == 77,
              (rs.get("done"), rs.get("failed"), rs.get("total")))
        check("14b completed_total 与 run_summary.done 一致",
              snap.get("completed_total") == rs.get("done"),
              (snap.get("completed_total"), rs.get("done")))

        # 14c 首页顺序＝独立复算排序（含并列 run_id DESC 决胜；offset 实现必挂）
        check("14c 首页顺序＝(eff,run_id) DESC 独立复算",
              [r["run_id"] for r in page] == expected[:20],
              [r["run_id"] for r in page])

        # 14f 并列时间戳由 run_id DESC 决胜（并列对内大 run_id 在前）
        tie_ok = True
        for a, b in zip(page, page[1:]):
            ra = next(x for x in page if x["run_id"] == a["run_id"])
            rb = next(x for x in page if x["run_id"] == b["run_id"])
            ea = ra["completed_at"] or ra["updated_at"]
            eb = rb["completed_at"] or rb["updated_at"]
            if ea == eb and ra["run_id"] < rb["run_id"]:
                tie_ok = False
        check("14f 并列对内 run_id DESC（run-c-001 先于 run-c-000）", tie_ok)
        check("14f 首页确含并列对（夹具覆盖到位：minute=18 那对）",
              "run-c-037" in [r["run_id"] for r in page]
              and "run-c-036" in [r["run_id"] for r in page])

        # 14d cursor 展开全 61：无重复无遗漏，页大小 20/20/20/1
        got = [r["run_id"] for r in page]
        cur = snap["next_cursor"]
        page_sizes = [len(page)]
        for _ in range(10):
            code2, snap2 = server._handle_status(
                {"data_root": [root], "limit": ["200"],
                 "completed_cursor": [cur]})
            check("14d cursor 页请求 200", code2 == 200 and snap2.get("ok"),
                  (code2, snap2.get("error")))
            p2 = snap2.get("completed_page") or []
            page_sizes.append(len(p2))
            got += [r["run_id"] for r in p2]
            cur = snap2.get("next_cursor")
            if not cur:
                break
        check("14d D-15 展开全 61 无重复遗漏（顺序＝独立复算全序）",
              got == expected, (len(got), len(set(got))))
        check("14d 页大小 20/20/20/1 且尽头上游 next_cursor=None",
              page_sizes == [20, 20, 20, 1] and cur is None,
              (page_sizes, cur))
        check("14d 尾页含缺 completed_at 的回退行（updated_at 兜底）",
              all(r["completed_at"] is None
                  for r in (snap2.get("completed_page") or [])
                  if r["run_id"].startswith("run-n-")),
              [(r["run_id"], r["completed_at"])
               for r in (snap2.get("completed_page") or [])])

        # 14e completed_limit 自定义生效（5）
        code3, snap3 = server._handle_status(
            {"data_root": [root], "limit": ["200"], "completed_limit": ["5"]})
        check("14e completed_limit=5 生期且顺序不变",
              code3 == 200 and len(snap3.get("completed_page") or []) == 5
              and [r["run_id"] for r in snap3["completed_page"]]
              == expected[:5],
              [r["run_id"] for r in snap3.get("completed_page") or []])

        # 14g cursor=keyset 非 offset：伪造合法排序键（签名为真）→ 严格取更早
        mid = expected[9]
        forged = server._completed_cursor_encode(eff_of[mid], eff_of[mid], mid)
        code4, snap4 = server._handle_status(
            {"data_root": [root], "limit": ["200"],
             "completed_cursor": [forged]})
        check("14g 合法排序键 cursor 严格取其后一页（keyset 非 offset）",
              code4 == 200
              and [r["run_id"] for r in snap4.get("completed_page") or []]
              == expected[10:30],
              [r["run_id"] for r in snap4.get("completed_page") or []])

        # 14h 反向证伪：篡改 payload／签名／格式坏 → 一律 400 人话，不静默错页
        real_cur = snap["next_cursor"]
        raw, sig = real_cur.rsplit(".", 1)
        import base64 as _b64
        pad = raw + "=" * (-len(raw) % 4)
        payload = _b64.urlsafe_b64decode(pad.encode()).decode()
        evil_payload = _b64.urlsafe_b64encode(
            payload.replace("run", "ofn").encode()).decode("ascii").rstrip("=")
        for tag, evil in [
                ("14h 篡改 payload（改 run_id）",
                 evil_payload + "." + sig),
                ("14h 篡改签名", raw + "." + ("0" * 12)),
                ("14h 无签名格式", raw),
                ("14h 乱码游标", "garbage-cursor"),
                ("14h 空串游标", "")]:
            code5, obj5 = server._handle_status(
                {"data_root": [root], "completed_cursor": [evil]})
            ok400 = (code5 == 400 and obj5.get("ok") is False
                     and "游标" in str(obj5.get("error") or ""))
            if tag == "14h 空串游标":
                ok400 = code5 == 200  # 空=未传，走默认首页，不算坏游标
            check(tag + "（坏游标 400 人话）", ok400,
                  (code5, str(obj5.get("error"))[:60]))

        # 14i 范围过滤：input_root 换别处 → 完成统计归零；回本目录 → 全量回来
        code6, snap6 = server._handle_status(
            {"data_root": [root], "limit": ["200"],
             "input_root": ["/tmp/p16-not-this-input"]})
        check("14i input_root 别处：completed_total=0（范围过滤同口径）",
              code6 == 200 and snap6.get("completed_total") == 0,
              (code6, snap6.get("completed_total")))
        code7, snap7 = server._handle_status(
            {"data_root": [root], "limit": ["200"],
             "input_root": [os.path.join(root, "_src")]})
        check("14i input_root 本目录：completed_total=61（刷新/归档不丢）",
              code7 == 200 and snap7.get("completed_total") == 61,
              (code7, snap7.get("completed_total")))

        # 14j 幂等：同一 cursor 两次请求结果一致（刷新/重试不漂移）
        code8a, s8a = server._handle_status(
            {"data_root": [root], "completed_cursor": [real_cur]})
        code8b, s8b = server._handle_status(
            {"data_root": [root], "completed_cursor": [real_cur]})
        check("14j 同游标两次请求页一致（幂等）",
              code8a == code8b == 200
              and [r["run_id"] for r in s8a["completed_page"]]
              == [r["run_id"] for r in s8b["completed_page"]])

        # 14k 完成行带磁盘终态（state/verdict/输出路径），失败行不带
        check("14k 完成行带 state=PUBLISHED 供详情/输出显示",
              all(r.get("state") == "PUBLISHED" for r in page),
              sorted({r.get("state") for r in page}))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("tmp 根：%s" % TMP_ROOT)
    server = load_server()
    part1_strict_types(server)
    part2_binding(server)
    part3_field_consistency(server)
    part4_candidate_lock(server)
    part5_partial_update(server)
    part6_error_redaction(server)
    part7_regression(server)
    part8_http_contract(server)
    part9_rework_guards(server)
    part10_p13_semantics(server)
    part11_p14_digest(server)
    part12_p14_alt_branch(server)
    part13_p15_vocab_display(server)
    part14_p16_completed_cursor(server)
    if FAILS:
        print("\nSELFTEST FAIL %d/%d：%s" % (len(FAILS), CHECKS[0], FAILS))
        return 1
    print("\nSELFTEST ALL PASS（%d 项断言）" % CHECKS[0])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
