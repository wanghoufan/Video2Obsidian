# QA-REPORT｜PACKAGING-V2.1验收（旧run过滤/新run处理/阻塞转写中/结束None/queue pending-done/空闲文案+进度条）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py`（809行，33626B，08:09）+ `app/index.html`（362行，18629B，08:08）+ `app/start.sh`（40行，1376B，07:45）（PACKAGING-V2.1增量；`src/` 只读复用）
- 任务目标：验收V2.1（旧run不再计数+新run被处理+阻塞期间current.stage=转写中+结束current=None+queue pending/done+页面空闲文案与进度条；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-pkgv21-data`（168K：R1主库，旧+新双run）+ `/tmp/v2o-pkgv21-data-block`（168K：R2阻塞库）+ `/tmp/v2o-pkgv21-data-worker`（168K：R4轮询库）+ `/tmp/v2o-pkgv21-input-old`（32K：clip_old.mp4）+ `/tmp/v2o-pkgv21-input-new`（32K：clip_new.mp4）+ `/tmp/v2o-pkgv21-vault`（4K：R1出md）+ `/tmp/v2o-pkgv21-vault-worker`（4K：R4出md）+ `/tmp/v2o-pkgv21-runners`（60K：R1/R2/R3B/NEG/R4/live8766各脚本+日志）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clip_old.mp4`（29835B）+ `testsrc rate=12+sine=880Hz → clip_new.mp4`（30111B），ffprobe各2.0s，FF_EXIT=0/PROBE_OLD_EXIT=0/PROBE_NEW_EXIT=0
- stub：`server._transcribe_audio` 猴补丁三档——R1/R4快返固定中文+1 segment+engine_calls=1；R2阻塞档先`entered.set()`再`sleep 4s`后同文回包，全程不碰 `mlx_whisper`/`extract_temp_wav` 真转写
- 端口隔离：8765被常驻实例占用（EADDRINUSE），本轮未kill/未POST/未碰其data/input/vault；live HTTP改走8766独立进程（`live8766.py` + `ThreadingHTTPServer(127.0.0.1,8766)`），测后已停，8766已释（lsof空）；初诊时对8765仅2次只读GET（`/` + `/api/start`）确认占用，无写
- **结论：PASS（旧SKIP不计数+新PUBLISHED+阻塞转写中+结束None+queue pending/done+空闲文案/进度条全PASS；R1 23/23+R2 13/13+R3B 31/31+R4 11/11 exit 0+NEG exit 1；py_compile/sh-n exit 0；零外部；browse fail-open已改400；src零改以mtime 01:02-03:10早于QA 08:11代证；真实目录/ob库零用；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| 旧run不再计数-SKIP | `_process_one_run(DATA,NEW_IN,VAULT,run_old)`（NEW监听下调OLD） | `SKIP`“源不在当前input_root内，已忽略” | 一致，见R1 log | R1_EXIT=**0** |
| 旧SKIP不进processed | 对比调用前后 `len(processed)` | 不变（0→0） | 0 vs 0 | R1_EXIT=**0** |
| 旧SKIP不进done/queue | `snapshot queue` + `_worker_done` | pending仍1/done仍0 | `{'pending':1,'done':0}` | R1_EXIT=**0** |
| pending按input过滤 | `_count_pending_in_root(NEW)` vs `(OLD)` | 各1（互不可见，对称） | NEW=1 OLD=1 | R1_EXIT=**0** |
| `_is_under_root` | old∉new / new∈new | False/True | False/True | R1_EXIT=**0** |
| 新run被处理 | `_process_one_run(DATA,NEW_IN,VAULT,run_new)` | `PUBLISHED` + vault md | PUBLISHED `/private/tmp/v2o-pkgv21-vault/clip_new.md` + stub文本落md | R1_EXIT=**0** |
| 新whisper_calls | `out.whisper_calls` | 1 | 1 | R1_EXIT=**0** |
| queue done+pending收口 | 手动`_worker_done.add(new)`后snapshot | pending 0/done 1 | `{'pending':0,'done':1}` | R1_EXIT=**0** |
| manifest收口 | `data/jobs/<new>/manifest.json` 末receipt | PUBLISHED n=5 | PUBLISHED n=5 | R1_EXIT=**0** |
| 阻塞current=转写中 | stub sleep 4s线程中轮询 `_worker.current` | stage=`转写中`+run/filename/started_at | `{'run_id':run_1c7b…, 'filename':'clip_new.mp4', 'stage':'转写中', 'stage_started_at':…Z}` 线程alive | R2_EXIT=**0** |
| snapshot同步current | 阻塞窗内 `_listener_snapshot().worker.current` | 同上 | 一致（queue pending1/done0） | R2_EXIT=**0** |
| 结束current=None | join后查 `_worker.current` + snapshot | 均为None | None+None | R2_EXIT=**0**（R1/R4同） |
| worker轮询只取新 | `_transcribe_worker(DATA,NEW_IN,…)` 6s后停 | done={new}，proc仅new PUBLISHED，无SKIP | done=`{run_1c7b…}` proc=`[(new,PUBLISHED)]` | R4_EXIT=**0** |
| worker旧残留仍在库 | `_count_pending(OLD_IN,exclude=∅)` | 1（未删，仅对NEW不可见） | 1 | R4_EXIT=**0** |
| 页面空闲文案 | GET 8766 `/` 含 `空闲：暂无排队视频` | 含 | 含（初值+`pending==0→空闲…已完成done`分支） | R3B_EXIT=**0** |
| 页面进度条 | 含 `progText/progFill/renderProgress` + `q.pending/q.done/cur.stage/cur.filename` + `width=pct%` | 全含 | 31/31（含`正在/排队/已完成/等待新视频`） | R3B_EXIT=**0** |
| 零外部 | 正则 `https?://\|<script src\|<link\|@import\|src="http\|href="http` | 0行 | 0行（`grep -c http`=0，见下注） | 审计 PASS |
| 快照shape | GET 8766 `/api/start` | 含 `worker.current/queue.pending/done`，闲时pending0/currentNone | 全含，`queue={'pending':0,'done':0}` | R3B_EXIT=**0** |
| 三路径/PRECHECK回归 | POST空/相对/合法三路径 | 各400（PRECHECK_MLX_MISSING） | 全命中（mlx缺，本机复现） | R3B_EXIT=**0** |
| browse回归 | old/new/相对/不存在 | 200 `[]`/200 `[]`/400/400 | 一致（old/new仅文件故`dirs==[]`） | R3B_EXIT=**0** |
| 坏例负控 | 故意期望202调合法start | 应FAIL且exit 1 | FAIL got 400 PRECHECK | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |
| 进口审计 | AST imports | 仅stdlib+stage*，无pip第三方 | stdlib+json/os/sys/tempfile/threading/urllib/http/datetime+stage1/2/3/4/5/6/7/8/12 | 审计 PASS |
| browse fail-open回归 | `except→400 卷判定失败拒绝浏览` + 非ALLOW 400 | fail-closed | server.py:252-253回400（V2 P2-1已闭） | 审计 PASS |
| DB状态门 | `processing_runs.status` 终态仍QUEUED，终态由`worker.processed`透出 | 无TRANSCRIBING落库 | R1/R4后DB仍QUEUED（pending靠exclude去重），页面worker映射显示 | PASS |

注：`grep -c http` 对index.html返回0行时grep进程exit=1——这是“零命中”的正确exit语义（同V2 `EXT_EXIT=0`系指审计脚本exit 0，此处直接以0行+rc=1双记，不判FAIL）。R3B脚本内`TOTAL 24`为硬编码文案误写，实际31断言全PASS，以**R3B_EXIT=0**为准（坏例只看exit码，反向亦然：打印错不改exit结论）。

Runner：R1直接调`_process_one_run`证SKIP/pending/queue（mlx bypass靠stub）+ R2 sleep-stub线程证阻塞窗current + R4真`_transcribe_worker`轮询证只取新 + R3B urllib直调8766（HTTPError取code断言，不看打印）+ NEG错期望证exit1 + 双编译 + AST进口 + 零外部 + 日志对账；8766 server起于 `live8766.py`（127.0.0.1:8766），测后已kill，端口已释；8765常驻实例零扰动。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（V2.1侧） | — | 否 | 旧SKIP/新PUBLISHED/阻塞转写中/结束None/queue/空闲+进度条全码一致；负控exit 1 | CLOSED | 无需builder修 | R1 23+R2 13+R3B 31+R4 11 exit 0 + NEG 1 |
| OBS-1（观察） | P3 | 否 | R2复用vault跨DATA库撞名→第二遍`PUBLISH_BLOCKED（BLOCKED_OUTPUT_CONFLICT）`，`DONE_STATES=(PUBLISHED,RENDER_ONLY)`不含BLOCKED故done不增；属vault幂等保护正确语义，非BUG | CLOSED | 无需修（vault去重语义） | R2末state=BLOCKED但current=None成立；R1/R4 PUBLISHED已证done=1链路 |
| OBS-2（观察） | P3 | 否 | `_count_pending` fail-open记0（server.py:168-169）；DB不可读时进度条回0/0而非报错，延续V2静默语义 | CLOSED | 无需修（进度可见性取舍） | 与转写主链路无关，报告备查 |
| OBS-3（观察） | P3 | 否 | R3B脚本`TOTAL 24`硬编码与实际31断言不符（打印错，exit 0正确）；`grep -c http`零命中rc=1易误读为FAIL | CLOSED | 无需修（QA侧脚本cosmetic） | 结论以exit码为准，已在本表注记 |

## Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.1验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（旧过滤/新处理/阻塞转写中/结束None/queue/页面全PASS；`__pycache__`若刷新为import产物，`.py` mtime app 08:08-09/src 01:02-03:10均早于QA 08:11-14，源零改成立）
- Approach: 外置七目录+ffmpeg双合成2s（440Hz旧/880Hz新）+stub三档（快返/阻塞sleep4s/轮询0.3s）+同库双run种子（old/new）+直接SKIP对照+pending对称计数+snapshot队列断言+阻塞窗current三字段轮询+真worker轮询6s+8766隔离live 31断言+错期望负控证exit1+双编译+AST进口+零外部+fail-closed审计+8765零扰动
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-V2.1-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv21-*`（data×3 504K+input×2 64K+vault×2 8K+runners 60K，交neat-freak收尾）
- Verification: R1_EXIT=0（23/23）+ R2_EXIT=0（13/13，stage=转写中快照一致）+ R3B_EXIT=0（31/31）+ NEG_EXIT=1 + R4_EXIT=0（11/11，done={new}无SKIP）+ PY_COMPILE/SHN 0 + 8766已释
- Failure Reason: 无FAIL项（V2.1侧；NEG系故意FAIL以证exit1）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V2报告另存，不混；V2 P2-1 fail-open本轮已闭为400）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实转写未测（mlx缺，PRECHECK挡202；全链以stub代证，whisper冻结模型语义延续V1.8已知限制；需stage0bench venv+长视频一次，用户定时间）。
- U-2 真实目录/ob库零碰以“七目录全`/tmp/v2o-pkgv21-*` + runners/输入/vault/data全外置 + 8765常驻实例未kill未POST + 仓库内零写盘除本报告”代证；初诊对8765仅2次只读GET（`/`+`/api/start`）确认占用，无写；无真实库快照（按禁令不得写）。
- U-3 默认库 `/var/…/T/v2o-console-data` 非本轮所用（R1/R2/R4全显式data_root指向`/tmp/v2o-pkgv21-data*`三库）；本轮三库各168K残留交收尾。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，源零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app/src mtime早于QA+本轮零写代证（同V2 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv21-data*`（504K）+ input×2/vault×2/runners（132K）+ live8766.log/pid，交neat-freak收尾；8766已释无常驻；8765常驻实例非本轮资产，不动。
- U-7 P0口径：DONE_STATES仅计PUBLISHED/RENDER_ONLY，PUBLISH_BLOCKED/FAIL不计done（进度条语义，见OBS-1）；`started_at`窗口与P2-3直写等延续V2评审，不卡。
- U-8 R2 vault跨库撞名致BLOCKED系测试资产复用所致，非产品回归；R1/R4已用独立vault证PUBLISHED主链路。

---
目标：PACKAGING-V2.1验收｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
