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
    # P1-3 新增/被新断言用到的函数（缺一个就会 ReferenceError → rc=1）
    "vocabApplyPct", "vocabApplyElapsedText", "vocabApplyStatsText",
    "vocabApplyLockText", "retryBody",
    # P1-3/CANDIDATE-UI2 P3-2 范围二选一（安全默认）
    "recScopeVal", "recScopeLabel", "syncRecScope", "recoverHint",
    # P1-3/RERUN-PROGRESS P3-4 主进度条无目标不画满
    "renderProgress", "stageStep",
    # P1-3 返工（P2-1/P2-2）：批量重试的文案与失败原因透传
    "retryRootHint", "retryRun", "retryAllFailed", "failedRuns", "isFailedRun",
    "filenameForRunId",
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
var longInInput = 0;   // 真源码里的模块变量（renderProgress 读它）
function renderTape(){} function renderRuns(){} function renderLock(){}
function loadVocab(){} function loadPresets(){}
// P1-3：say 要能验（人话提示＝验收点），不再空实现
var SAYS = [];
function say(t){ SAYS.push(String(t == null ? "" : t)); }
// P1-3/P2-2：toast 也记一份（批量重试收尾会 toast）；真实现要 document.body，桩里不做
var TOASTS = [];
function toast(t){ TOASTS.push(String(t == null ? "" : t)); }
// failedRuns / filenameForRunId 读的模块变量（真源码里是 var cache={runs:[]} /
// var detailsByRun={}，桩里按同结构复现）
var cache = {runs: []};
var detailsByRun = {};
// P1-3/CANDIDATE-UI2 P3-2：recScope 单选桩（只实现被测函数用到的那几种选择器）
var RADIOS = [{value: "sel", checked: true}, {value: "all", checked: false}];
var document = {
  querySelector: function(sel){
    if(sel.indexOf('input[name="recScope"]:checked') >= 0){
      for(var i = 0; i < RADIOS.length; i++){ if(RADIOS[i].checked) return RADIOS[i]; }
      return null;
    }
    if(sel.indexOf('input[name="recScope"][value="sel"]') >= 0) return RADIOS[0];
    return null;
  },
  querySelectorAll: function(){ return []; }
};
// pollVocabApplyStatus 不返回 promise（fetch 链自带 .catch），必须显式冲刷微任务
async function poll(){ pollVocabApplyStatus(); await tick(); await tick(); }
async function flush(){ await tick(); await tick(); }
// 递归 .then 链（批量重试逐个 fetch→then→advance→step）要多轮冲刷；
// await 一次 tick 会排空微任务队列，这里多给几轮，避免 node 时序差异
async function settle(n){ for(var i = 0; i < n; i++){ await tick(); } }
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
  SAYS = []; RADIOS = [{value: "sel", checked: true}, {value: "all", checked: false}];
  TOASTS = []; cache = {runs: []}; detailsByRun = {};
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

// ---------------- S8 P1-3：无目标不画满 / 运行中参数锁定 / 双空安全默认 / retry 带目录
async function s8(){
  // 8a 无目标终态（零目标）：进度条不画满、不画绿满，文案点明零目标
  reset();
  renderVocabApplyFinal({state: "done", total: 0, done: 0, imported: 2,
    rerun_old: false,
    message: "已导入2条；本次没有可重跑的已完成任务（零目标，未重跑任何稿件）",
    summary: {success: 0, skipped: 0, failed: 0, total: 0, needs_human: 0, interrupted: 0},
    stats: {total: 0, done: 0, success: 0, failed: 0, skipped: 0, needs_human: 0,
            interrupted: 0, counted: 0, balanced: true}});
  ck("S8a 零目标终态不画满（宽度 0%，旧形态是 100%）",
     el("candidateApplyFill").style.width === "0%",
     el("candidateApplyFill").style.width);
  ck("S8a 零目标终态文案点明「零目标／不画满」",
     (REC.text["candidateApplyText"] || "").indexOf("零目标") >= 0,
     REC.text["candidateApplyText"]);
  ck("S8a 汇总按后端同一口径展示（重跑目标 0 篇）",
     (REC.text["candidateApplyText"] || "").indexOf("重跑目标 0 篇") >= 0,
     REC.text["candidateApplyText"]);

  // 8b 对照：真有目标且跑完 → 才允许 100%（证明 8a 不是「永远 0%」的恒真断言）
  reset();
  renderVocabApplyFinal({state: "done", total: 4, done: 4, imported: 1,
    rerun_old: true, message: "已导入1条；重跑成功3篇，跳过1篇",
    summary: {success: 3, skipped: 1, failed: 0, total: 4, needs_human: 0, interrupted: 0},
    stats: {total: 4, done: 4, success: 3, failed: 0, skipped: 1, needs_human: 0,
            interrupted: 0, counted: 4, balanced: true}});
  ck("S8b 有目标跑完才 100%（对照）",
     el("candidateApplyFill").style.width === "100%",
     el("candidateApplyFill").style.width);
  ck("S8b 失败统计逐条可复算（4=3+1+0+0+0）",
     (REC.text["candidateApplyText"] || "").indexOf("可复算：4=3+1+0+0+0") >= 0,
     REC.text["candidateApplyText"]);

  // 8c 运行中：真实进度＋已用时＋可离开＋本次锁定的参数（页面＝实际执行）
  reset();
  renderVocabApplyProgress({state: "running", stage: "rerunning", rerun_old: true,
    total: 4, done: 1, elapsed_seconds: 65, indices_count: 3,
    current_filename: "a.mp4"});
  var t8c = REC.text["candidateApplyText"] || "";
  ck("S8c 运行中按真实进度画 25%",
     el("candidateApplyFill").style.width === "25%",
     el("candidateApplyFill").style.width);
  ck("S8c 显示已用时", t8c.indexOf("已用时 65s") >= 0, t8c);
  ck("S8c 提示可离开且回来仍能看到进度", t8c.indexOf("可离开本页面") >= 0, t8c);
  ck("S8c 显示本次锁定的参数（rerun_old＋目标候选数）",
     t8c.indexOf("本次锁定") >= 0 && t8c.indexOf("目标候选 3 条") >= 0, t8c);

  // 8d 运行中锁定：控件禁用＋写原因；别的批量链跑完（显式 lock=false）也解不开本页的锁
  reset();
  vocabApplyRunning = true;
  setCandidateControls(true, false);
  ck("S8d 运行中策略/范围/批量入口一律禁用",
     el("candidateRerunOld").disabled === true
     && el("candidateOnlyNew").disabled === true
     && el("candidateSelectAll").disabled === true
     && el("recScopeSel").disabled === true && el("recScopeAll").disabled === true
     && el("btnRecTranscribe").disabled === true && el("btnRecReuse").disabled === true
     && el("btnRecPublish").disabled === true,
     [el("candidateRerunOld").disabled, el("recScopeSel").disabled]);
  ck("S8d 运行中就地说清为什么不能改",
     (REC.text["batchLockHint"] || "").indexOf("已锁定") >= 0,
     REC.text["batchLockHint"]);
  ck("S8d lock=false 也解不开运行中的锁（不白等一次后端 409）",
     el("btnCandidateApply").disabled === true);

  // 8e 终态解除锁定（跑完才能改下一次的参数）
  reset();
  vocabApplyRunning = false;
  setCandidateControls(true, false);
  ck("S8e 跑完后控件放开、锁定提示清空",
     el("candidateRerunOld").disabled === false && el("recScopeAll").disabled === false
     && el("btnRecTranscribe").disabled === false
     && (REC.text["batchLockHint"] || "") === "",
     [el("candidateRerunOld").disabled, REC.text["batchLockHint"]]);

  // 8f 策略二选一（重跑老稿／只入库）双空 → 提交前回到安全一侧（只入库）
  reset();
  el("inData").value = "/tmp/p13-fake-root";
  vocabCandidatesRevision = "REV-1";
  el("candidateRerunOld").checked = false;
  el("candidateOnlyNew").checked = false;
  route("/api/vocab/candidates/apply",
        {status: 202, json: {ok: true, job_id: "job-P"}}, "POST");
  route("/api/vocab/candidates/apply/status", {status: 200, json: {ok: true, job: {
      job_id: "job-P", state: "running", stage: "importing", rerun_old: false,
      data_root: "/tmp/p13-fake-root", total: 0, done: 0}}});
  applyVocabCandidates();
  await flush(); await flush();
  var post8f = lastCall("/api/vocab/candidates/apply", "POST");
  ck("S8f 双空不提交空语义：明确回到安全一侧（只入库）",
     el("candidateOnlyNew").checked === true && el("candidateRerunOld").checked === false,
     [el("candidateOnlyNew").checked, el("candidateRerunOld").checked]);
  ck("S8f 页面显示与实际执行一致（提交体 rerun_old:false）",
     !!post8f && post8f.body.indexOf('"rerun_old":false') >= 0, post8f && post8f.body);
  ck("S8f 双空给人话原因（不静默换语义）",
     SAYS.join(" | ").indexOf("不能都不选") >= 0, SAYS);

  // 8g 409 锁定回显：把「本次锁住的参数」解析成人话（页面参数＝后台那次）
  ck("S8g 409 锁定回显解析（rerun_old＋目标候选数）",
     vocabApplyLockText({locked_params: {rerun_old: true, indices: [0, 1]}})
       .indexOf("重跑老稿") >= 0
     && vocabApplyLockText({locked_params: {rerun_old: true, indices: [0, 1]}})
       .indexOf("目标候选 2 条") >= 0,
     vocabApplyLockText({locked_params: {rerun_old: true, indices: [0, 1]}}));
  ck("S8g 没有锁定信息时不编造（回空串）", vocabApplyLockText({}) === "",
     vocabApplyLockText({}));

  // 8h 范围二选一（recScope）双空 → 回到安全一侧并写人话
  reset();
  RADIOS[0].checked = false; RADIOS[1].checked = false;
  var v8h = recScopeVal();
  ck("S8h 范围双空回到安全一侧（当前所选任务）",
     v8h === "sel" && RADIOS[0].checked === true, [v8h, RADIOS[0].checked]);
  ck("S8h 范围双空给人话原因",
     (REC.text["recoverHint"] || "").indexOf("不能为空") >= 0,
     REC.text["recoverHint"]);
  ck("S8h 范围选定后不被改写（不误伤已有选择）",
     (function(){ RADIOS[1].checked = true; RADIOS[0].checked = false;
                  return recScopeVal() === "all"; })());

  // 8i P2-7：/api/retry 必须带本页数据目录（框优先，其次生效目录，都没有才不带）
  reset();
  el("inData").value = "/tmp/p12-fake-rootA";
  var b8i = retryBody("run-1");
  ck("S8i 重试请求带本页数据目录（旧形态不带）",
     b8i.data_root === "/tmp/p12-fake-rootA" && b8i.run_id === "run-1", b8i);
  reset();
  el("inData").value = "";
  effectiveDataRoot = DEFAULT_ROOT;
  ck("S8i 框留空时用生效目录（与 apply 同口径）",
     retryBody("run-1").data_root === DEFAULT_ROOT, retryBody("run-1"));
  reset();
  el("inData").value = "";
  effectiveDataRoot = "";
  ck("S8i 两处都没有时不发 data_root（后端按监听目录走旧行为）",
     !("data_root" in retryBody("run-1")), retryBody("run-1"));

  // 8j 主进度条：无目标（total=0）不画满——哪怕「正在跑这一个」
  reset();
  renderProgress({current: {run_id: "r1", filename: "a.mp4", stage: "听写",
                            stage_started_at: new Date().toISOString()},
                  queue: {pending: 0, done: 0, failed: 0, total: 0}});
  ck("S8j 无目标三段全 0%（旧的灰条会满格＝画满）",
     el("progFillOk").style.width === "0%" && el("progFillFail").style.width === "0%"
     && el("progFillPending").style.width === "0%",
     [el("progFillOk").style.width, el("progFillFail").style.width,
      el("progFillPending").style.width]);
  ck("S8j 无目标但正在跑：文案仍说明在跑什么（不静默）",
     (REC.text["progText"] || "").indexOf("正在") >= 0, REC.text["progText"]);
  // 8j2 对照：真有目标才按实际推进（证明 8j 不是恒 0%）
  reset();
  renderProgress({current: null, queue: {pending: 0, done: 3, failed: 1, total: 4}});
  ck("S8j2 有目标按实际推进（成功 75%／失败 25%）",
     el("progFillOk").style.width === "75%" && el("progFillFail").style.width === "25%",
     [el("progFillOk").style.width, el("progFillFail").style.width]);
}

// ------------- S9 P1-3 返工：批量重试的「能不能离开」文案＋失败原因不再被静默吞掉
// P2-1 对应 9a/9b（反向证伪：把文案改回「可离开本页面，稍后回来仍能看到结果」→ rc=1）
// P2-2 对应 9c/9d/9e/9f（反向证伪：noteBad 退回只 badN++、retryBody 去掉本地门 → rc=1）
var S9_ROOT_A = "/tmp/p12-fake-rootA", S9_ROOT_B = "/tmp/p12-fake-rootB";
function retryCalls(){
  var out = [];
  for(var i = 0; i < REC.calls.length; i++){
    if(REC.calls[i].method === "POST"
       && REC.calls[i].url.indexOf("/api/retry") === 0) out.push(REC.calls[i]);
  }
  return out;
}
function twoFailed(){
  cache.runs = [{run_id: "run-1", status: "FAILED", source_filename: "a.mp4"},
                {run_id: "run-2", status: "FAILED", source_filename: "b.mp4"}];
}
async function s9(){
  // 9a 批量重试是**页面内循环**：不许承诺「可离开/后台继续」，必须说「保持本页打开」
  reset();
  el("inData").value = S9_ROOT_A;
  twoFailed();
  route("/api/retry", {status: 202, json: {ok: true}}, "POST");
  retryAllFailed();
  var first = SAYS[SAYS.length - 1] || "";
  ck("9a 首条文案不承诺可离开（旧形态：可离开本页面，稍后回来仍能看到结果）",
     first.indexOf("可离开") < 0, first);
  ck("9a 首条文案明说需保持本页打开（与真实行为逐字对得上）",
     first.indexOf("需保持本页打开") >= 0 && first.indexOf("不会继续重试") >= 0, first);
  await settle(6);
  var all9a = SAYS.join(" | ");
  ck("9a 逐条进度文案同样不提可离开",
     all9a.indexOf("可离开") < 0, SAYS);
  ck("9a 逐条进度文案说清离开的后果（剩余不再排队）",
     all9a.indexOf("离开则剩余任务不会再排队") >= 0, SAYS);
  ck("9a 真发出两条重试并报 2/2（文案没换掉实际行为）",
     retryCalls().length === 2 && all9a.indexOf("已排队 2/2") >= 0,
     [retryCalls().length, SAYS]);

  // 9b 共用锁定提示（错词重跑/重新成稿/批量重试三链同用）不得替用户承诺能离开
  reset();
  vocabApplyRunning = true;
  setCandidateControls(true, false);
  var hint9b = REC.text["batchLockHint"] || "";
  ck("9b 共用锁定提示仍写明锁定范围（三链都成立的真话，不许删）",
     hint9b.indexOf("已锁定") >= 0 && hint9b.indexOf("本次不改") >= 0
     && hint9b.indexOf("跑完再改") >= 0, hint9b);
  ck("9b 共用锁定提示不再代办「可离开」（两条链结论相反）",
     hint9b.indexOf("可离开") < 0, hint9b);
  // 9b1 P3-新1：尾句「进度条会显示已用时」只对**错词重跑**成立——重新成稿是同步
  //      fetch（无进度条）、批量重试只在 say 行里报 n/N（也无已用时），属越界指针。
  ck("9b1 共用锁定提示不得再指进度条/已用时（只对单链成立的越界指针）",
     hint9b.indexOf("进度条") < 0 && hint9b.indexOf("已用时") < 0, hint9b);
  // 9b2 对照：错词重跑那条是**服务端后台任务**（202＋job_id，重载可接管），
  //     「可离开」属实 → 必须仍在，证明 9a/9b 不是一刀切删掉真话
  reset();
  renderVocabApplyProgress({state: "running", stage: "rerunning", rerun_old: true,
    total: 2, done: 1, elapsed_seconds: 5});
  ck("9b2 对照：错词重跑进度条仍保留「可离开」（服务端任务，属实）",
     (REC.text["candidateApplyText"] || "").indexOf("可离开本页面") >= 0,
     REC.text["candidateApplyText"]);

  // 9c P2-2：跨目录 409（本页新增的拒绝出口）必须把人话原因透出来
  reset();
  el("inData").value = S9_ROOT_B;
  twoFailed();
  route("/api/retry", {status: 409, json: {ok: false,
    error: "这次重试针对的是另一个数据目录（零执行，未重排任何任务）；"
         + "请先核对页面上方的数据目录与当前监听的目录是否一致，避免误操作别的目录"}},
    "POST");
  retryAllFailed();
  await settle(6);
  var say9c = SAYS.join(" | "), hint9c = REC.text["recoverHint"] || "";
  ck("9c 失败不再只显示一个数字（收尾说「失败 N 个」并指向原因）",
     say9c.indexOf("失败 2 个") >= 0 && say9c.indexOf("原因见下方提示") >= 0, SAYS);
  ck("9c 后端人话原因落到首屏恢复区（旧形态零回显）",
     hint9c.indexOf("另一个数据目录") >= 0, hint9c);
  ck("9c 回显不含真实数据目录（D-12，前后端都不吐路径）",
     hint9c.indexOf(S9_ROOT_B) < 0 && say9c.indexOf(S9_ROOT_B) < 0,
     [hint9c, say9c]);

  // 9d 404（任务不存在）同样透出，不因代码不同而静默
  reset();
  el("inData").value = S9_ROOT_A;
  cache.runs = [{run_id: "run-1", status: "FAILED"}];
  route("/api/retry", {status: 404, json: {ok: false, error: "任务不存在，请刷新后重试"}},
        "POST");
  retryAllFailed();
  await settle(6);
  ck("9d 404 也回显原因（不是只看到「失败请求 1」）",
     (REC.text["recoverHint"] || "").indexOf("任务不存在") >= 0,
     REC.text["recoverHint"]);

  // 9e 部分成功：成功的照常计入已排队，失败的原因照样透出（互不顶掉）
  reset();
  el("inData").value = S9_ROOT_A;
  cache.runs = [{run_id: "run-1", status: "FAILED"},
                {run_id: "run-2", status: "FAILED"},
                {run_id: "run-3", status: "FAILED"}];
  FETCH_QUEUE.push({status: 202, json: {ok: true}});
  FETCH_QUEUE.push({status: 409, json: {ok: false,
    error: "这次重试针对的是另一个数据目录（零执行，未重排任何任务）"}});
  FETCH_QUEUE.push({status: 202, json: {ok: true}});
  retryAllFailed();
  await settle(8);
  ck("9e 部分成功：已排队 2/3 且失败原因仍回显",
     SAYS.join(" | ").indexOf("已排队 2/3") >= 0
     && (REC.text["recoverHint"] || "").indexOf("另一个数据目录") >= 0,
     [SAYS, REC.text["recoverHint"]]);

  // 9f P2-2 本地前置门：框里是相对路径 → 整批零请求（旧形态 N 条都白撞后端 400）
  reset();
  el("inData").value = "relative/x";
  effectiveDataRoot = "";
  twoFailed();
  retryAllFailed();
  await settle(4);
  ck("9f 非法目录：一个请求都不发（白跑被本地拦下）",
     retryCalls().length === 0, retryCalls().length);
  ck("9f 非法目录：人话口径与后端 400 同句（数据目录须为绝对路径）",
     SAYS.join(" | ").indexOf("数据目录须为绝对路径") >= 0
     && (REC.text["recoverHint"] || "").indexOf("数据目录须为绝对路径") >= 0,
     [SAYS, REC.text["recoverHint"]]);
  ck("9f retryBody 非法目录回 null（不被当成「不带 data_root」放行）",
     retryBody("run-1") === null, retryBody("run-1"));

  // 9g 单条重试同一道门；9h 对照：目录合法时照常发，不误伤正常路径
  reset();
  el("inData").value = "relative/x";
  effectiveDataRoot = "";
  var n9g = REC.calls.length;
  retryRun("run-1");
  await settle(2);
  ck("9g 单条重试遇相对目录：不发请求且给人话",
     REC.calls.length === n9g && SAYS.join(" | ").indexOf("重试未发起") >= 0,
     [REC.calls.length - n9g, SAYS]);

  reset();
  el("inData").value = S9_ROOT_A;
  route("/api/retry", {status: 202, json: {ok: true}}, "POST");
  retryRun("run-1");
  await settle(3);
  ck("9h 对照：目录合法时单条重试照常 POST 且带 data_root",
     retryCalls().length === 1
     && retryCalls()[0].body.indexOf('"data_root":"' + S9_ROOT_A + '"') >= 0,
     retryCalls().map(function(c){ return c.body; }));
}

(async function(){
  await s1(); await s2(); await s3(); await s4(); await s5(); await s6(); await s7();
  await s8(); await s9();
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
