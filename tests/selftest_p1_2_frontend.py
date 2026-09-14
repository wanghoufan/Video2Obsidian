#!/usr/bin/env python3
"""builder 自验（DEVELOP-P1-2 前端任务身份）：抽 `app/index.html` 真源码 + node 桩，
断言「轮询带 data_root+job_id、只渲染本页那次 job、别目录/别任务不串」。
不点真机、不起 8765、不请求线上服务。

做法：从 index.html 里按函数名**逐字抽真源码**（不手抄），拼上 DOM/fetch 桩跑
node；任一断言失败 node 退出码非 0，本脚本随之退出 1。

运行：python3 tests/selftest_p1_2_frontend.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "app", "index.html")

FUNCS = [
    "esc", "el", "dataRoot",
    "vocabApplyStopPoll", "vocabApplySetText", "renderVocabApplyProgress",
    "renderVocabApplyFinal", "vocabApplyStartTimer", "vocabApplyStatusQuery",
    "vocabApplyDropPoll", "vocabApplyNotePollFailure", "pollVocabApplyStatus",
    "vocabJobDataRoot", "refresh", "vocabApplyGiveUp", "vocabApplyFinish",
    "isAbsRoot",
    "resumeVocabApplyPoll", "sameDataRoot", "applyVocabCandidates",
    "reapplyPayload", "setCandidateControls", "candidateCheckboxes",
    "candidateGroupCheckboxes", "syncCandidateSelectAll", "loadVocabCandidates",
]


def extract(src, name):
    """按函数名抓一段真源码（花括号配对，含嵌套）。"""
    marker = "function %s(" % name
    idx = src.find(marker)
    if idx < 0:
        raise AssertionError("index.html 找不到函数 %s（改名了？）" % name)
    start = idx
    brace = src.find("{", idx)
    depth = 0
    i = brace
    while i < len(src):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise AssertionError("函数 %s 花括号不配对" % name)


DRIVER = r"""
// ------------------------------------------------------------------ DOM / fetch 桩
var REC = {text: {}, cls: {}, calls: [], urls: []};
// 真源码里这两个是模块常量，桩里按 index.html 同值复现
var VOCAB_APPLY_MAX_FAIL = 8, VOCAB_APPLY_MAX_MS = 10 * 60 * 1000;
function elStub(id){
  if(id === "candidateList"){
    return {
      innerHTML: "",
      _cb: [{checked: true, getAttribute: function(k){
        return k === "data-candidate-index" ? "0" : "high"; }, onchange: null}],
      querySelectorAll: function(sel){
        return sel === "[data-candidate-index]" ? this._cb : [];
      },
      querySelector: function(){ return null; }
    };
  }
  var o = {value: "", textContent: "", className: "", style: {}, disabled: false,
           checked: false, innerHTML: "", onclick: null, oninput: null};
  Object.defineProperty(o, "textContent", {
    get: function(){ return REC.text[id] || ""; },
    set: function(v){ REC.text[id] = String(v); }});
  Object.defineProperty(o, "className", {
    get: function(){ return REC.cls[id] || ""; },
    set: function(v){ REC.cls[id] = String(v); }});
  return o;
}
var ELS = {};
function el(id){ if(!ELS[id]) ELS[id] = elStub(id); return ELS[id]; }
var STORE = {};
var localStorage = {getItem: function(k){ return STORE[k] || null; },
                    setItem: function(k,v){ STORE[k] = v; },
                    removeItem: function(k){ delete STORE[k]; }};
var TIMERS = 0, TIMER_CB = null;
function setInterval(fn, ms){ TIMERS++; TIMER_CB = fn; return TIMERS; }
function clearInterval(){ TIMERS = 0; }
function confirm(){ return true; }
var FETCH_QUEUE = [], ROUTES = [];
function mkResp(r){ return {status: r.status,
                            json: function(){ return Promise.resolve(r.json); }}; }
function fetch(url, opts){
  var method = (opts && opts.method) || "GET";
  REC.urls.push(url);
  REC.calls.push({url: url, method: method, body: (opts && opts.body) || null});
  var best = null;   // 取“最长匹配”=最具体的路由，避免 /api/vocab 吃掉 /api/vocab/candidates
  for(var i = 0; i < ROUTES.length; i++){
    if(url.indexOf(ROUTES[i].match) >= 0
       && (!ROUTES[i].method || ROUTES[i].method === method)
       && (!best || ROUTES[i].match.length > best.match.length)){
      best = ROUTES[i];
    }
  }
  if(best){ return Promise.resolve(mkResp(best.res)); }
  var nxt = FETCH_QUEUE.shift() || {status: 200, json: {}};
  return Promise.resolve(mkResp(nxt));
}
function route(match, res, method){ ROUTES.push({match: match, res: res, method: method || null}); }
function tick(){ return new Promise(function(r){ setTimeout(r, 0); }); }
// refresh 用到的其它函数：桩里只做最小实现（本测试关心的是它的调用时序与 URL）
var lastLock = null, lastFetchAt = 0, refreshing = false;
function renderTape(){} function renderRuns(){} function renderLock(){}
function say(){} function loadVocab(){} function loadPresets(){}
// pollVocabApplyStatus 不返回 promise（fetch 链自带 .catch），必须显式冲刷微任务
async function poll(){ pollVocabApplyStatus(); await tick(); await tick(); }
async function flush(){ await tick(); await tick(); }
var FAILS = [];
function ck(name, cond, extra){
  if(cond){ console.log("PASS " + name); }
  else { console.log("FAIL " + name + (extra === undefined ? "" : "  << " + JSON.stringify(extra)));
         FAILS.push(name); }
}
function reset(){
  ELS = {}; REC = {text: {}, cls: {}, calls: [], urls: []};
  vocabApplyJobId = null; vocabApplyTimer = null; vocabApplyRunning = false;
  vocabApplyFailStreak = 0; vocabApplyStartedAt = 0; vocabCandidatesRevision = null;
  effectiveDataRoot = "";   // 真源码里的模块变量（P2-新1）
  FETCH_QUEUE = []; TIMERS = 0; ROUTES = [];
}

// ------------------------------------------------------------------ S1 本页 job 全程钉住
async function s1(){
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  FETCH_QUEUE.push({status: 200, json: {ok: true, has_candidates: true, count: 1,
      candidates_revision: "REV-1",
      candidates: {high: [], medium: [], low: []}}});
  loadVocabCandidates();
  await flush();
  ck("S1 候选清单版本被记住", vocabCandidatesRevision === "REV-1",
     vocabCandidatesRevision);

  // 202 + 紧随其后的首次 status（前端 202 后会立刻 poll 一次）
  FETCH_QUEUE.push({status: 202, json: {ok: true, job_id: "job-A"}});
  FETCH_QUEUE.push({status: 200, json: {ok: true, job: {job_id: "job-A",
      state: "running", stage: "importing", rerun_old: true, total: 0, done: 0}}});
  applyVocabCandidates();
  await flush(); await flush();
  ck("S1 提交 202 后钉住本页 job_id", vocabApplyJobId === "job-A", vocabApplyJobId);
  var post = null, k;
  for(k = 0; k < REC.calls.length; k++){
    if(REC.calls[k].method === "POST"){ post = REC.calls[k]; }
  }
  ck("S1 POST 带 candidates_revision",
     !!post && post.body.indexOf('"candidates_revision":"REV-1"') >= 0,
     post && post.body);
  ck("S1 POST 带 data_root",
     !!post && post.body.indexOf('"data_root":"/tmp/p12-fake-rootA"') >= 0,
     post && post.body);
  var u = REC.urls[REC.urls.length - 1];
  ck("S1 轮询带 data_root", u.indexOf("data_root=%2Ftmp%2Fp12-fake-rootA") >= 0, u);
  ck("S1 轮询带 job_id", u.indexOf("job_id=job-A") >= 0, u);
  ck("S1 进行中照常渲染本页进度",
     (REC.text["candidateApplyText"] || "").indexOf("正在导入") >= 0,
     REC.text["candidateApplyText"]);
  ck("S1 进行中保持轮询表", TIMERS > 0);

  // 后端最近任务换成别的 job（另一标签页）→ 不渲染、停表、给人话
  FETCH_QUEUE.push({status: 200, json: {ok: true, job: {job_id: "job-B",
      state: "running", stage: "rerunning", total: 9, done: 4,
      message: "B页的任务", current_filename: "B视频.mp4"}}});
  await poll();
  var txt = REC.text["candidateApplyText"] || "";
  ck("S1 别页 job 不渲染（无 B 的进度）",
     txt.indexOf("B页") < 0 && txt.indexOf("4/9") < 0, txt);
  ck("S1 别页 job 给人话并停表",
     txt.indexOf("不是本页发起") >= 0 && TIMERS === 0, txt);

  // 服务端明确拒绝（跨目录 409）→ 不渲染、给人话、停表
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  vocabApplyJobId = "job-A"; vocabApplyRunning = true;
  FETCH_QUEUE.push({status: 409, json: {ok: false, job: null,
      error: "最近一次任务属于另一个数据目录（零渲染），请核对数据目录后重查"}});
  await poll();
  var txt2 = REC.text["candidateApplyText"] || "";
  ck("S1 跨目录 409 不渲染他人的 job",
     txt2.indexOf("另一个数据目录") >= 0 && txt2.indexOf("正在导入") < 0, txt2);
  ck("S1 跨目录 409 后按钮解禁", el("btnCandidateApply").disabled === false);
}

// ------------------------------------------------------------------ S2 页面重载续看只认本目录
async function s2(){
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  FETCH_QUEUE.push({status: 200, json: {ok: true, job: {job_id: "job-X",
      state: "running", data_root: "/tmp/p12-other-root/data", total: 3, done: 1}}});
  resumeVocabApplyPoll();
  await flush(); await flush();
  ck("S2 别目录的进行中任务不接管", TIMERS === 0 && vocabApplyJobId === null,
     [TIMERS, vocabApplyJobId]);

  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  FETCH_QUEUE.push({status: 200, json: {ok: true, job: {job_id: "job-Y",
      state: "running", data_root: "/tmp/p12-fake-rootA", total: 3, done: 1}}});
  resumeVocabApplyPoll();
  await flush(); await flush();
  ck("S2 本目录进行中任务接管并钉 job_id",
     TIMERS > 0 && vocabApplyJobId === "job-Y", [TIMERS, vocabApplyJobId]);

  reset();
  el("inData").value = "";
  FETCH_QUEUE.push({status: 200, json: {ok: true, job: {job_id: "job-Z",
      state: "running", data_root: "/tmp/p12-fake-rootA"}}});
  resumeVocabApplyPoll();
  await flush(); await flush();
  ck("S2 无 data_root 时不接管（无法判隔离宁可不画）",
     TIMERS === 0 && vocabApplyJobId === null, [TIMERS, vocabApplyJobId]);
}

// ------------------------------------------------------------------ S3 提交前置门
async function s3(){
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  vocabCandidatesRevision = null;
  applyVocabCandidates();
  await flush();
  ck("S3 无候选版本时不提交（提示先刷新）",
     REC.calls.length === 0
     && (REC.text["vCandidate"] || "").indexOf("版本") >= 0,
     [REC.calls.length, REC.text["vCandidate"]]);
}

// ------------------------------------------------------------------ S4 服务端抖动不静默冻结
async function s4(){
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  vocabApplyJobId = "job-A"; vocabApplyRunning = true;
  vocabApplyStartTimer();
  var timers_before = TIMERS;
  FETCH_QUEUE.push({status: 500, json: {ok: false, error: "服务开小差：x，稍后重试"}});
  await poll();
  ck("S4 5xx 不当作“非本页任务”停表",
     TIMERS > 0 && timers_before > 0,
     [TIMERS, timers_before]);
  ck("S4 5xx 走轮询容错口径并给人话",
     (REC.text["candidateApplyText"] || "").indexOf("进度读取失败，正在重试") >= 0,
     REC.text["candidateApplyText"]);
  ck("S4 5xx 不清掉本页 job 身份", vocabApplyJobId === "job-A", vocabApplyJobId);
}

// ------------------------------------------------------------------ S5 候选清单缺失：哨兵版本不当锁用
async function s5(){
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  FETCH_QUEUE.push({status: 200, json: {ok: true, has_candidates: false, count: 0,
      candidates_revision: "absent", candidates: {high: [], medium: [], low: []}}});
  loadVocabCandidates();
  await flush();
  ck("S5 哨兵版本 absent 不当可用版本（前端置空）",
     vocabCandidatesRevision === null, vocabCandidatesRevision);
  var before = REC.calls.length;
  applyVocabCandidates();
  await flush();
  ck("S5 无可用版本时不提交（前置拒绝，不建空 job）",
     REC.calls.length === before
     && (REC.text["vCandidate"] || "").indexOf("版本") >= 0,
     [REC.calls.length - before, REC.text["vCandidate"]]);

  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  FETCH_QUEUE.push({status: 200, json: {ok: true, has_candidates: true, count: 1,
      candidates_revision: "REV-9", candidates: {high: [], medium: [], low: []}}});
  loadVocabCandidates();
  await flush();
  ck("S5 正常版本仍被记住（未误伤）", vocabCandidatesRevision === "REV-9",
     vocabCandidatesRevision);
}

// ------------------------------------------ S6 P2-新1：数据目录框留空（用默认外置测试目录）
var DEFAULT_ROOT = "/tmp/p12-fake-default";

function lastCall(match, method){
  for(var i = REC.calls.length - 1; i >= 0; i--){
    if(REC.calls[i].url.indexOf(match) >= 0
       && (!method || REC.calls[i].method === method)) return REC.calls[i];
  }
  return null;
}
function callsSince(n, match){
  var out = [];
  for(var i = n; i < REC.calls.length; i++){
    if(REC.calls[i].url.indexOf(match) >= 0) out.push(REC.calls[i]);
  }
  return out;
}

async function s6(){
  // 6a 框留空 + 已从同一真源学到生效目录 → 提交带显式 data_root，且轮询同口径
  reset();
  el("inData").value = "";
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-D", state: "running", stage: "importing", rerun_old: false,
      data_root: DEFAULT_ROOT, total: 0, done: 0}}});
  route("/api/vocab/candidates", {status: 200, json: {ok: true, has_candidates: true,
      count: 1, candidates_revision: "REV-1", data_root: DEFAULT_ROOT,
      candidates: {high: [], medium: [], low: []}}});
  loadVocabCandidates();
  await flush();
  ck("S6 框留空时从候选清单回包学到生效目录",
     effectiveDataRoot === DEFAULT_ROOT, effectiveDataRoot);
  ck("S6 vocabJobDataRoot 在框留空时回该生效目录",
     vocabJobDataRoot() === DEFAULT_ROOT, vocabJobDataRoot());

  route("/api/vocab/candidates/apply", {status: 202, json: {ok: true, job_id: "job-D"}},
        "POST");
  applyVocabCandidates();
  await flush(); await flush();
  var post = lastCall("/api/vocab/candidates/apply", "POST");
  ck("S6① 框留空时 apply 仍带显式 data_root",
     !!post && post.body.indexOf('"data_root":"' + DEFAULT_ROOT + '"') >= 0,
     post && post.body);
  var pollUrl = (lastCall("/api/vocab/candidates/apply/status") || {}).url || "";
  ck("S6① 轮询带同一 data_root＋job_id",
     pollUrl.indexOf("data_root=" + encodeURIComponent(DEFAULT_ROOT)) >= 0
     && pollUrl.indexOf("job_id=job-D") >= 0, pollUrl);
  ck("S6① 进度照常渲染（未静默）",
     (REC.text["candidateApplyText"] || "").indexOf("正在导入") >= 0 && TIMERS > 0,
     [REC.text["candidateApplyText"], TIMERS]);

  // 6b 绝无「提交成功但 job:null 静默停表」：即便后端回 job:null 也必须给人话
  reset();
  el("inData").value = "";
  effectiveDataRoot = DEFAULT_ROOT;
  vocabApplyJobId = "job-D"; vocabApplyRunning = true;
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: null}});
  await poll();
  ck("S6② job:null 不再静默停表（给人话、按钮复原）",
     TIMERS === 0 && el("btnCandidateApply").disabled === false
     && (REC.text["candidateApplyText"] || "").indexOf("查不到") >= 0,
     [TIMERS, REC.text["candidateApplyText"]]);

  // 6c 解析不到生效目录 → 人话阻止，绝不提交（不产生“后台跑着但看不到”的任务）
  reset();
  el("inData").value = "";
  vocabCandidatesRevision = "REV-1";   // 版本在手但目录未知
  var before = REC.calls.length;
  applyVocabCandidates();
  await flush();
  ck("S6① 目录未知时不提交（无人话则视为静默）",
     REC.calls.length === before
     && (REC.text["vCandidate"] || "").indexOf("数据目录") >= 0,
     [REC.calls.length - before, REC.text["vCandidate"]]);

  // 6d 续看同口径：框留空但生效目录已知 → 接管；目录未知 → 不接管也不发请求
  reset();
  el("inData").value = "";
  effectiveDataRoot = DEFAULT_ROOT;
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-D2", state: "running", data_root: DEFAULT_ROOT, total: 3, done: 1}}});
  resumeVocabApplyPoll();
  await flush(); await flush();
  var resUrl = (lastCall("/api/vocab/candidates/apply/status") || {}).url || "";
  ck("S6③ 框留空续看：带生效目录并接管",
     TIMERS > 0 && vocabApplyJobId === "job-D2"
     && resUrl.indexOf("data_root=" + encodeURIComponent(DEFAULT_ROOT)) >= 0,
     [TIMERS, vocabApplyJobId, resUrl]);

  reset();
  el("inData").value = "";
  before = REC.calls.length;
  resumeVocabApplyPoll();
  await flush();
  ck("S6③ 目录未知时续看不发请求（不留半状态）",
     REC.calls.length === before && TIMERS === 0, REC.calls.length - before);

  // 6e 框留空 + /api/start 兜底真源（候选清单还没回包时的续看）
  reset();
  el("inData").value = "";
  route("/api/status", {status: 200, json: {ok: true, runs: []}});
  route("/api/start", {status: 200, json: {ok: true, running: false,
      data_root: null, default_data_root: DEFAULT_ROOT}});
  route("/api/vocab", {status: 200, json: {ok: true, vocab: []}});
  route("/api/vocab/presets", {status: 200, json: {ok: true, presets: []}});
  route("/api/vocab/candidates", {status: 200, json: {ok: true, has_candidates: false,
      count: 0, candidates_revision: "absent", data_root: DEFAULT_ROOT,
      candidates: {high: [], medium: [], low: []}}});
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-E", state: "running", data_root: DEFAULT_ROOT, total: 2, done: 0}}});
  refresh(false);
  await flush(); await flush(); await flush();
  ck("S6③ refresh 后继看拿到 /api/start 的默认目录并接管",
     effectiveDataRoot === DEFAULT_ROOT && TIMERS > 0
     && vocabApplyJobId === "job-E", [effectiveDataRoot, TIMERS, vocabApplyJobId]);
  var rUrls = callsSince(0, "/api/vocab/candidates/apply/status");
  ck("S6③ 该次续看请求带显式 data_root",
     rUrls.length >= 1
     && rUrls[rUrls.length - 1].url.indexOf("data_root=" + encodeURIComponent(DEFAULT_ROOT)) >= 0,
     rUrls.map(function(c){ return c.url; }));

  // 6f 框有值时不受生效目录影响（真源优先级：框 > 学到值）
  reset();
  el("inData").value = "/tmp/p12-fake-typed";
  effectiveDataRoot = DEFAULT_ROOT;
  ck("S6 框有值时以框为准（不误用生效目录）",
     vocabJobDataRoot() === "/tmp/p12-fake-typed", vocabJobDataRoot());
}

// ------------------------------- S7 P2-三1：提交遇 409 running 的接管路径不许静默停滞
async function s7(){
  var ROOT_A = "/tmp/p12-fake-rootA";
  // 场景 C：正在跑的任务属于另一个 data_root（status 回 409）
  reset();
  el("inData").value = ROOT_A;
  effectiveDataRoot = ROOT_A;
  vocabCandidatesRevision = "REV-1";
  route("/api/vocab/candidates/apply", {status: 409, json: {ok: false, running: true,
      job_id: "job-other", error: "已有一次错词重跑在进行中，请等它跑完再试"}}, "POST");
  route("/api/vocab/candidates/apply/status", {status: 409, json: {ok: false, job: null,
      error: "最近一次任务属于另一个数据目录（零渲染），请核对数据目录后重查"}});
  applyVocabCandidates();
  await flush(); await flush(); await flush();
  var txtC = REC.text["candidateApplyText"] || "";
  ck("S7(C) 跨目录接管失败：有人话（不留“正在导入…”假象）",
     txtC.indexOf("另一个数据目录") >= 0, txtC);
  ck("S7(C) 跨目录接管失败：停表且按钮复原（不卡死）",
     TIMERS === 0 && el("btnCandidateApply").disabled === false,
     [TIMERS, el("btnCandidateApply").disabled]);

  // 场景 D：409 之后任务已跑完（status 回终态）→ 直接落终态，不是静默丢
  reset();
  el("inData").value = ROOT_A;
  effectiveDataRoot = ROOT_A;
  vocabCandidatesRevision = "REV-1";
  route("/api/vocab/candidates/apply", {status: 409, json: {ok: false, running: true,
      error: "已有一次错词重跑在进行中，请等它跑完再试"}}, "POST");
  route("/api/vocab/candidates", {status: 200, json: {ok: true, has_candidates: true,
      count: 1, candidates_revision: "REV-1", data_root: ROOT_A,
      candidates: {high: [], medium: [], low: []}}});
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-F", state: "done", data_root: ROOT_A, imported: 2,
      rerun_old: false, summary: {success: 0, skipped: 0, failed: 0},
      message: "已导入2条；未重跑老稿，老稿未动"}}});
  applyVocabCandidates();
  await flush(); await flush(); await flush();
  var txtD = REC.text["candidateApplyText"] || "";
  ck("S7(D) 接管时任务已跑完：直接落终态并显示结果",
     txtD.indexOf("已导入2条") >= 0, txtD);
  ck("S7(D) 终态后按钮复原、无计时器",
     TIMERS === 0 && el("btnCandidateApply").disabled === false,
     [TIMERS, el("btnCandidateApply").disabled]);

  // 场景 G：409 后确实接管成功（同目录在跑）→ 落人话且进入进度
  reset();
  el("inData").value = ROOT_A;
  effectiveDataRoot = ROOT_A;
  vocabCandidatesRevision = "REV-1";
  route("/api/vocab/candidates/apply", {status: 409, json: {ok: false, running: true,
      error: "已有一次错词重跑在进行中，请等它跑完再试"}}, "POST");
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-G", state: "running", data_root: ROOT_A, stage: "importing",
      rerun_old: false, total: 0, done: 0}}});
  applyVocabCandidates();
  await flush(); await flush(); await flush();
  ck("S7(G) 接管成功：钉住对方的 job_id 并继续显示进度",
     vocabApplyJobId === "job-G" && TIMERS > 0
     && (REC.text["candidateApplyText"] || "").indexOf("正在导入") >= 0,
     [vocabApplyJobId, TIMERS, REC.text["candidateApplyText"]]);

  // 场景 E：P3-三1 相对路径 -> 本地拦（不发请求）
  reset();
  el("inData").value = "relative/x";
  effectiveDataRoot = "";
  vocabCandidatesRevision = "REV-1";
  var n0 = REC.calls.length;
  applyVocabCandidates();
  await flush();
  ck("S7(E) 相对数据目录：本地人话拦住、不发请求",
     REC.calls.length === n0
     && (REC.text["vCandidate"] || "").indexOf("绝对路径") >= 0,
     [REC.calls.length - n0, REC.text["vCandidate"]]);

  // 场景 F：P3-三1 续看遇相对目录 -> 人话＋复原按钮（不静默）
  reset();
  el("inData").value = "relative/x";
  effectiveDataRoot = "";
  vocabApplyRunning = true;
  el("btnCandidateApply").disabled = true;
  n0 = REC.calls.length;
  resumeVocabApplyPoll();
  await flush();
  ck("S7(F) 续看遇相对目录：不发请求、给人话、按钮复原",
     REC.calls.length === n0 && TIMERS === 0
     && el("btnCandidateApply").disabled === false
     && (REC.text["candidateApplyText"] || "").indexOf("绝对路径") >= 0,
     [REC.calls.length - n0, REC.text["candidateApplyText"],
      el("btnCandidateApply").disabled]);
}

(async function(){
  await s1(); await s2(); await s3(); await s4(); await s5(); await s6(); await s7();
  if(FAILS.length){ console.log("FRONT FAIL " + FAILS.length + ": " + FAILS.join(" | "));
                    process.exit(1); }
  console.log("FRONT ALL PASS");
})();
"""


def main():
    src = open(HTML, encoding="utf-8").read()
    parts = []
    for name in FUNCS:
        parts.append(extract(src, name))
    js = "\n\n".join(parts) + "\n" + DRIVER
    tmp = tempfile.mkdtemp(prefix="p12_front_")
    path = os.path.join(tmp, "harness.js")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(js)
        node = shutil.which("node")
        if not node:
            print("SKIP：本机没有 node，前端桩未跑（如实记账，不冒充通过）")
            return 0
        proc = subprocess.run([node, path], capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        if proc.stderr.strip():
            sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            print("FRONT SELFTEST FAIL（node rc=%d）" % proc.returncode)
            return 1
        print("FRONT SELFTEST PASS")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
