# QA-REPORT｜外部提交 b22c464 影响面冒烟（只读+合成，不碰8765/真实目录/OB库）

- QA：qa（本窗口 subagent；业务零改，只写本报告）
- 被测：`app/server.py`（3943行，171724B，09-11 17:55）+ `app/index.html`（1429行）+ `src/stage9/formatter_v2.py`（376行，14451B）+ `src/stage9/__init__.py`（60行）+ `tests/selftest_v26_presets.py`（231行）；HEAD `5a34a40`（UX2-P0/P1+V26）含 b22c464（`merge-base --is-ancestor b22c464 HEAD` EXIT=0）；b22c464 本体 13文件 +1259/-164，其中 `app/server.py` +728（V2.2全终态放行+V2.5生产后处理/词库门）、`src/stage9/*`（`split_segments_for_engine`/`postprocess_paragraphs`+导出）、`app/index.html` +23（词库2字门/短词confirm/绿条旧账）
- 任务目标：冒烟 b22c464 影响面（服务正跑含它的代码，PID 86342 cwd即本仓）；只读+合成：py_compile全仓库py、关键接口契约抽查（status/reveal400/note/vocab/retry/stop/clear dry_run，只用外置/tmp+合成，禁碰用户真实目录与OB库、禁碰8765用高位端口或直调函数）、与已PASS报告口径一致性（UX2-P0/P1、V26行为未被外部增量破坏；V2.5复验口径亦未被后续增量破坏）。坏例看exit码，结论只落本报告
- QA 执行目录（仓库外）：`/tmp/ext_b22c464_qa.py`（runner）+ `TMPBASE /tmp/ext-b22c464-qa_*`（data-status/input-status 2源2run种子库、data-note、data-vocab、data-preset、data-live、data-clear/input-clear；跑后已rmtree，残留仅 `neg_*`/`dbg_*`/`ext-empty-*` 空壳交收尾）+ `/tmp/v2o-console-data`（默认库，全程未用，全显式data_root指TMPBASE）；仓库内零写盘除本报告（`__pycache__`为gitignored不进树，`git status`仅预存 `M docs/handoff/HANDOFF.md` + 未跟踪 `docs/review/EXT-B22C464-CODE-REVIEW.md`，QA未动）
- 合成：input-status内 `a.mp4/b.mp4`（`fake-video-N`字节级伪视频，仅喂source/upsert不做转写）+ note jobs合成manifest（BLOCKED_OUTPUT_CONFLICT判黄条）+ vocab合成错词（`a/ab/Github/iste`）+ 450字`甲`*450分段合成；无ffmpeg、无whisper、无stub（直调函数不经转写引擎，`engine_calls`不涉及）
- 端口隔离：8765常驻实例（PID 86342，`venv/bin/python app/server.py`，前后一致）零请求零扰动；live HTTP改走18765独立进程（`ThreadingHTTPServer(127.0.0.1,18765)`+`server.Handler`，GET status/vocab + POST reveal400各1），测后已shutdown+server_close，`lsof -i:18765`空；对8765零请求、零写
- **结论：PASS（b22c464影响面未见破坏：py_compile 72/72 EXIT 0 + 合成契约83/83 EXIT 0 + V26自测 ALL PASS EXIT 0 + NEG EXIT 1 + 18765 live 3/3 + 8765零扰动；UX2-P0/P1/V26/V2.5复验口径一致；OPEN bug 0，无打回；约束全遵守；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| py_compile全仓 | 72 py全编译 | EXIT 0 | 72文件全过 | ALL_PY_COMPILE_EXIT=**0** |
| B0空库status | 空data_root直调`_handle_status` | 200不炸fail-open | 200 dict | EXT_QA_EXIT=**0**（83/83） |
| B1种子库status | 2源2run种子库+input过滤 | 200+summary全键+total2 | total2 shown/limit/truncated/groups全 | 同上 |
| B2/B3限流 | limit9999/bad | 钳200/默认20 | 200/20 | 同上 |
| C reveal坏例 | 空体/坏JSON/缺参/相对/不存在 | 全400（不存在含“找不到了”） | 5/5 400 | 同上 |
| D note | 缺run_id400/未知run200/user_edited布尔/manifest判True/缺文件False | 全一致（UX2-P1-4口径） | 400+200 QUEUED+False/True/False | 同上 |
| E vocab门 | `a→b`拒/`。。`拒/`Github`撞基表拒/合法过 | 人话（2个字/标点/内置） | 全一致（V2.5 P1-2口径） | 同上 |
| E handler往返 | 单字400且文件无`"a"`/基表400/短词200+preview/查1/坏JSON400/删缺参400/删404/删200 | 全码一致 | 全一致 | 同上 |
| F retry | 坏JSON400/缺id400/未监听400/done首调202重排队/二调202已在排队 | 幂等不翻倍 | 全一致（UX2-P1-2口径，现场已恢复） | 同上 |
| G stop | 无current finishing假三段文案/有current真+文件名/二次200 | 全一致 | 全一致（UX2-P1-6口径，现场已恢复） | 同上 |
| H clear | 坏JSON400/缺input400/相对400/无库404无需清空 | 全码一致 | 全一致 | 同上 |
| H est/归属 | est67=134/16=32/0=0+尾段+ siblings不串 | 全一致（UX2-P0-2/P1-5口径） | 全一致 | 同上 |
| I1分段 | `甲`*450经`render_with_v2` | 全≤120且join原样（V26 120封顶） | [120,120,120,90] | 同上 |
| I2后处理 | `_apply_v25_postpass`缺norm | fail-open fixed False | `normalized 缺失，不覆写` | 同上 |
| I3/I4引擎 helpers | `split_segments_for_engine`/`postprocess_paragraphs`存在且封顶 | ≤200/≤120 | 3片/全≤120 | 同上 |
| I5 profile | `new_render_profile`+`_render_profile_for_new_jobs` | para-v2.6 80/120/30 | 一致 | 同上 |
| I9 V2.2终态集 | norm/rend/pub/arch/art判定 | COMPLETED等终态真、PENDING/PREPARED假 | 5/5一致（b22c464未被回退） | 同上 |
| I6预置 | 三域只读 | finance66/programming83/crypto68，各≥50/≥2字/≠正词/去重 | 全一致 | 同上 |
| I7导入+命中 | 三域导入+二次幂等+`apply_corrections` | added217+rev用户哈希+二次0+`市盈率/美联储/区块链` | `b24f721b`+命中全 | 同上 |
| I8预置坏例 | 空domains/全未知 | 400 | 2/2 400 | 同上 |
| J live隔离 | 18765 GET status/vocab + POST reveal | 200/200 count0/400 | 3/3 | 同上 |
| V26自测 | `python3 tests/selftest_v26_presets.py` | ALL PASS | 50断言全PASS | V26_SELFTEST_EXIT=**0** |
| NEG负控 | 故意期望Github→x得200 | 应FAIL且exit 1 | FAIL got 400 | **NEG_EXIT=1** |

注：reveal成功路径未测（真调会弹Finder，有副作用，按禁令只测400）；clear全量DB代价预览成功路径以UX2-P0 67条库PASS为准，本轮仅以2run种子库证summary通路+坏例/est/归属，不重跑67规模；真转写未测（mlx缺， slic/stub代链路延续V1.8已知限制）。

Runner：直调函数（保存/恢复`_listener/_worker/_worker_done`，`_handle.box`恒None）+ 种子库（`instance.acquire+store.init_db+upsert_source+get_or_create_auto_run`，锁内，用后release+rmtree）+ urllib经18765（HTTPError取code，不看打印）+ 错期望负控证exit1 + 全仓编译 + 8765零扰动对账；macOS /tmp实为`/private/tmp`经symlink（realpath口径一致，非bug）。

## BUGS（照 BUGS.template.md；本轮 OPEN 0）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| EXT-B22C464-SMOKE 影响面冒烟83断言 | — | 否 | /tmp合成直调+18765隔离live（禁8765/禁真实目录/禁OB库） | PASS | 无打回 | 83/0 EXIT 0；V26自测EXIT 0；NEG EXIT 1；8765 PID 86342初末一致 |

## Fix Attempt Fingerprint

- Task ID: EXT-B22C464-QA-2026-09-11（首轮冒烟，业务零修）
- Root Cause Hypothesis: 无（验收任务；初跑4 FAIL经核查为QA脚本口径过严/签名误用：①空库无summary系collect fail-open正确行为，改种子2run库后全过；②`apply_corrections(segments, revision)`误传`profile=`，按自测正签修正后全过；③种子库con缺`row_factory=Row`致`dict(tuple)`炸，按调试正解修正；④`rev`被坏例复写，改独立变量后全过——业务码无辜）
- Approach: 只用外置/tmp+合成，直调函数（禁碰用户真实目录与OB库、禁碰8765服务、不常驻服务）；先`py_compile`全仓72看exit码，再跑`/tmp/ext_b22c464_qa.py`看exit码（83断言：status/reveal/note/vocab/retry/stop/clear/V2.5/V2.2/V26/18765），另跑V26自测+错期望负控证exit1
- Files Changed: 仅新增本报告 `docs/qa/EXT-B22C464-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在`/tmp/ext-b22c464-qa_*`（已rmtree）+runner（交收尾）
- Verification: ALL_PY_COMPILE_EXIT=0（72/72）+ EXT_QA_EXIT=0（83/83）+ V26_SELFTEST_EXIT=0（50/50 ALL PASS）+ NEG_EXIT=1 + 18765已释 + 8765 PID 86342初末一致零请求
- Failure Reason: 初跑4 FAIL系QA脚本口径/签名/行工厂/变量复写四误（见上），修正后83/0；builder自验（V26）始终全绿
- Difference From Previous Attempt: 首轮外部增量冒烟；此前为UX2-P0/P1/V26三份PASS报告（口径延续见未闭环U-1）

## 未闭环（打回项）

- 无（OPEN 0；P0全绿，无打回）。
- U-1 口径一致性：UX2-P0（总数/截断/dry_run代价/est/归属）、UX2-P1-2~P1-8（重试幂等/单主按钮行模板未重扫但后端语义一致/黄条灰字/尾段分组/停止三段/来源列哈希只进title/三段进度条——前端静态以既有PASS为准，本轮以后端语义+契约码覆盖，未发现回退）、V26（450双路/重跑守卫fail-safe/三域/导入幂等/命中/撞基表/单字）、V2.5复验（生产450精确[200,200,50]以I1同引擎+postpass fail-open覆盖，未重跑450生产全链；DB人话/单字400/先存后注册以本轮坏例+源码序覆盖）——均未见b22c464被后续5a34a40破坏。
- U-2 真实目录/OB库零碰以“全显式data_root指TMPBASE + 默认库未用 + 8765零请求 + 仓内零写盘除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 残留交收尾：`/tmp/ext_b22c464_qa.py` + `neg_*/dbg_*/ext-empty-*` 空壳 + `__pycache__`（ignored）+ 预存 `M docs/handoff/HANDOFF.md` 与未跟踪code-review（非QA资产，不动）。
- U-4 18765已释无常驻；8765常驻实例非本轮资产，不动。

---
目标：外部b22c464影响面冒烟｜剩 P0：无（83/83+V26自测全绿，无打回）｜下一步：交supervisor复检（HANDOFF只记状态，不代写结论）。
