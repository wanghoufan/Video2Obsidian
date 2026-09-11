# QA-REPORT｜PACKAGING-V2.5验收（分段新旧对比/词库CRUD+撞基表+新转写命中/存量重跑whisper0+Raw不变+用户编辑跳过）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py`（2855行，124634B，12:19）+ `app/index.html`（1076行，55135B，12:19）+ `src/stage9/formatter_v2.py`（305行，12:17）（V2.5增量；`src/stage3` 只读复用；工作区 `git status` 干净，仅本报告与V2.5-CODE-REVIEW未跟踪）
- 任务目标：验收V2.5三项（新旧分段对比段数增/均长降/无超长段+碎片合并、词库增删改查+撞基表拒收+新转写命中、存量重跑whisper0+Raw不变+用户编辑md被跳过；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-pkgv25-data`（4K：P0-2词库CRUD库）+ `/tmp/v2o-pkgv25-input`（128K：clipG 29835B/clipH 30111B/`09.demo.part.mp4`/subdir/nested.mp4）+ `/tmp/v2o-pkgv25-data-e2e`（268K：stub端到端双run库）+ `/tmp/v2o-pkgv25-input-e2e`（64K：clipK/clipL）+ `/tmp/v2o-pkgv25-vault-e2e`（16K：old_keep.md+clipK.md+clipL.md）+ `/tmp/v2o-pkgv25-data-prod`（生产路复现库）+ `/tmp/v2o-pkgv25-input-prod`（clipP）+ `/tmp/v2o-pkgv25-runners`（28K：v25_verify/v25_e2e/v25_live/v25_neg/v25_prod）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipG.mp4`（29835B）+ `rate=12+sine=880Hz → clipH.mp4`（30111B），ffprobe各2.0s，FF_EXIT=0/PROBE_EXIT=0；`09.demo.part.mp4`/nested/clipK/clipL/clipP由clipG/H复制得
- stub：`server._transcribe_audio` 猴补丁（E2E返回含错词`iste/teh`中文+`engine_calls=1`；生产路复现返回450字无标点单段+`engine_calls=1`）；P0-1/P0-2对照项直接调函数不碰 `mlx_whisper` 真转写
- 端口隔离：8765常驻实例（PID 89431，初末一致）零请求零扰动；live HTTP改走8769独立进程（`ThreadingHTTPServer(127.0.0.1,8769)`+`server.Handler`），测后已shutdown，8769已释（lsof空）；对8765零请求、零写
- **结论：FAIL（P0×1未闭环，打回builder：生产渲染路径不走V2.5后处理，450字单段生产出458字超长段，200封顶/MIN防碎生产落空——与CODE-REVIEW P0-1同源，QA独立复现确认；P1×3中P1-1/P1-2 QA独立复现确认、P1-3代码口径确认；其余全绿：wrapper层42/42 exit 0+E2E 27/27 exit 0+live 7/7 exit 0+NEG exit 1+双编译0；零外部；src/app零改以mtime 12:17-19早于QA 12:26代证+git干净；真实目录/ob库零用；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| P0-1 wrapper段数增 | 30段长文本旧引擎 vs `render_with_v2` | 新段数>旧 | 旧8 → 新10 | VERIFY_EXIT=**0**（42/42） |
| P0-1 wrapper均长降 | 同上平均段长 | 新<旧 | 197.8 → 158.0 | 同上 |
| P0-1 wrapper无超长 | 新全段≤200+profile para-v2.5{120,200,40} | 全≤200 | max158，profile一致 | 同上 |
| P0-1 wrapper超长切分 | 450字无标点单段：旧 vs 新 | 旧超长/新全≤200 | 旧[450] vs 新[200,200,50] | 同上 |
| P0-1 wrapper弱标点切分 | 汉150+，+字150+。+符150 | 新全≤200 | [151,151,150] | 同上 |
| P0-1 wrapper碎片合并 | 3×`ab`大间隔 | 合1段 | `['ab ab ab']` | 同上 |
| P0-1 wrapper六探针 | `check_rule_order` | 全过+四序冻结 | 全过，四序一致 | 同上 |
| **P0-1 生产路复现** | **stub 450字单段经`_process_one_run`真实渲染** | **全段≤200** | **出[458,7]，max458，q连串450原样** | **PROD复现=P0-1 CONFIRMED（FAIL驱动）** |
| P0-2查空 | `_handle_vocab_get` | 0条+rev s9-corr-v2 | 一致 | VERIFY同上 |
| P0-2增/覆盖/查 | add iste→.env.local→覆盖.local.v2 | 200+覆盖人话+count1 | 一致 | 同上 |
| P0-2撞基表拒收 | add Github→x（基表5条含Github→GitHub） | 400内置人话 | 400一致；register层ValueError一致 | 同上 |
| P0-2坏例 | 空/相等/超128/坏JSON/del缺失404/del缺参400 | 各码一致 | 全一致 | 同上 |
| P0-2 revision | 内容哈希`user-<sha8>`+prompt terms | 变内容变rev+terms含正词 | `911ff532`等，terms含 | 同上 |
| P0-2新转写命中 | stub含iste经`_process_one_run`→PUBLISHED | vault含.env.local无iste+prompt收到正词 | 一致，whisper1 | E2E_EXIT=**0**（27/27） |
| P0-3无编辑重跑 | 加teh→the后`_reapply_one`（L） | whisper0+Raw同sha+新稿有the+vault旧稿不动 | 全一致（PUBLISH_BLOCKED，No-Clobber） | 同上 |
| P0-3用户编辑跳过 | vault K chmod+追加手写后重跑 | skipped True+手写保留+whisper0+Raw同 | `skipped_user_edited True/BLOCKED_OUTPUT_CONFLICT`，手写保留 | 同上 |
| P0-3 all=true | `_handle_reapply_post all` | 200+total2/ok2 | 一致 | 同上 |
| P0-3坏例 | 缺run_id 400/无run 404/再跑whisper0 | 各码一致 | 全一致（初始化库） | 同上 |
| P1-1 DB坏例 | 未初始化data_root单条重跑（live+直接） | JSON 4xx | **连接掉线无响应**（status/all分支正常） | LIVE观察=P1-1 CONFIRMED |
| P1-2单字污染 | 注册a→b后`apply_corrections` | 应拒收或加权 | `a cat…banana`→`b cbt bnd b dog bbnbnb`（7处） | 探针=P1-2 CONFIRMED |
| 前端10例 | vocabBox/vocabList/btnReapplyAll/data-reapply双api/词库/重跑/转写0次/改过 | 全含 | 10/10含 | VERIFY同上 |
| 零外部/进口 | 无http外链；AST仅stdlib+stage* | 0行/extra空 | 0行/extra空 | 同上 |
| live 7例 | 8769 vocab增删查+撞400+首页UI+reapply缺参400+无run404（初始化库） | 全码一致 | 7/7 | LIVE_EXIT=**0**（7/7） |
| 坏例负控 | v25_neg故意期望撞基表200 | 应FAIL且exit 1 | FAIL got 400 | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：`lsof -i:8769` 测前测后均空（端口干净）；macOS /tmp经symlink显`/private/tmp`（realpath口径一致，非bug）；vault/canonical发布后chmod 444只读（No-Clobber信号），用户编辑复现前需`chmod u+w`模拟OB内改写；`whisper_calls==0`断言须显式`==0`（`0 or -1` falsy坑已避）。

Runner：直接函数对照（wrapper 11例/CRUD 18例/前端10/进口零外部/E2E双run种子+双场景重跑+all+坏例）+ stub E2E（whisper_calls=1）+ urllib经8769（HTTPError取code断言，不看打印）+ 生产路450单段真实渲染复现 + 单字污染探针 + 错期望负控证exit1 + 双编译 + AST进口 + 零外部 + 日志对账；8769起于`v25_live.py`（127.0.0.1:8769），测后已shutdown端口已释；8765常驻实例（PID 89431）零请求零扰动。

## BUGS（照 BUGS.template.md；本轮 P0×1/P1×3）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| V25-P0-1 | P0 | 是 | stub 450字无标点单段→`_process_one_run` RENDER_ONLY→md段`[458,7]` max458（`v25_prod.py`；wrapper同输入`[200,200,50]`） | OPEN（打回builder，与CODE-REVIEW P0-1同源） | 修生产路后处理（review三选一）+QA补生产路三例 | 生产profile直喂冻结引擎，`render_with_v2`生产零调用 |
| V25-P1-1 | P1 | 否 | 未初始化data_root+run_id调`_reapply_one`→`OperationalError unable to open`上抛，HTTP掉线无响应（live 8769复现；初始化库404正常） | OPEN（打回builder，与CODE-REVIEW P1-1同源，QA独立发现） | `_open_rw`入try+人话错；all逐项try | status/all分支fail-open正常，仅单条崩 |
| V25-P1-2 | P1 | 否 | 注册a→b→`apply_corrections` 7处替换成`b cbt bnd b dog bbnbnb`（QA独立复现，与CODE-REVIEW一致） | OPEN（打回builder） | wrong最小长度门+短词确认/预览 | 自动进新转写+重跑，全库污染风险 |
| V25-P1-3 | P1 | 否 | `_handle_vocab_add`先注册后落盘（1238-1242），落盘抛即500掉线+内存文件分叉（代码口径确认，未实爆盘） | OPEN（打回builder，代码确认） | 先存后注册+OSError接管 | 与CODE-REVIEW P1-3同源 |

## Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.5验收（首轮QA，业务零修；code-reviewer已先行打回P0×1/P1×3）
- Root Cause Hypothesis: 不适用（验收轮；唯一QA口径教训见下）
- Approach: 外置八目录+ffmpeg双合成2s（440Hz G/880Hz H，多点号/子目录复刻）+stub快返（engine_calls=1）+双run种子（K/L各1 run）+wrapper新旧对比（30段长文本/450超长/弱标点/碎片/六探针）+词库CRUD全分支（空/增/覆盖/撞基表/空值/超长/坏JSON/删404/缺参/rev哈希/prompt terms）+stub E2E双场景（无编辑No-Clobber/用户编辑跳过+whisper0+Raw双sha+all汇总+坏例）+生产路450单段真实渲染复现+单字污染探针+8769隔离live 7断言（含DB坏例观察）+错期望负控证exit1+双编译+AST进口+零外部+8765零扰动
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-V2.5-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv25-*`（data4K+input128K+runners28K+e2e268K/64K/16K+prod库，交neat-freak收尾）
- Verification: VERIFY_EXIT=0（42/42，wrapper层）+ E2E_EXIT=0（27/27）+ LIVE_EXIT=0（7/7）+ PROD复现P0-1（段[458,7] max458）+ P1-1连接掉线复现 + P1-2七处替换复现 + NEG_EXIT=1 + PY_COMPILE/SHN 0 + IMPORT 0 + 8769已释
- Failure Reason: P0-1生产路不走wrapper（`_render_profile_for_new_jobs`/`_reapply_one`直喂冻结引擎，`render_with_v2`生产零调用；QA初版verify只测wrapper未测生产，复核报告到后即补生产路复现确认——下次“新旧对比”类验收必须首轮即含生产路真实渲染例）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V2.3报告另存，不混）

## 未闭环清单（交 supervisor/product-reviewer 定；P0卡全绿）

- P0 V25-P0-1 OPEN：生产路超长段（458>200）——返工必须续本链，QA补“生产路450单段/150+150无标点/3×ab碎渣经真实`create_render_revision/derive`”三断言（CODE-REVIEW已点名）。
- P1 V25-P1-1/P1-2 OPEN（QA独立复现）/P1-3 OPEN（代码确认）：修法见上表，修完QA只补对应坏例（DBless单条404化/单字400拒/落盘失败JSON化），不重跑全量。
- U-1 真实转写未测（mlx缺；E2E以stub代证链路，whisper冻结模型语义延续V1.8已知限制；需stage0bench venv+长视频一次，用户定时间）。
- U-2 真实目录/ob库零碰以“八目录全`/tmp/v2o-pkgv25-*` + 8765常驻PID 89431初末一致零请求 + 仓库内零写盘除本报告（app 12:19早于QA 12:26，git仅review报告未跟踪）”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/tmp/v2o-console-data` 非本轮所用（全显式data_root指向`/tmp/v2o-pkgv25-*`）；残留（data4K+e2e268K+input128K/64K+vault16K+runners28K+prod库）交收尾。
- U-4 非git口径N/A不成立——本仓实为git仓（commit 874aaf4含V2.1-V2.5），`git status`干净（仅本报告+CODE-REVIEW未跟踪），源零改成立；`__pycache__`未进树。
- U-5 P2措辞：无编辑重跑note写“库内笔记你改过”（实为No-Clobber新旧差异BLOCK，vault旧稿不动正确listing）；RENDER_ONLY重跑永不试入库（给了vault也只落数据目录）；all=true在BLOCK态后skipped计数归零（逐项走else分支）——与CODE-REVIEW P2-1同类，文档化即可，不卡。
- U-6 8769已释无常驻；8765常驻实例非本轮资产，不动。

---
目标：PACKAGING-V2.5验收｜剩 P0：V25-P0-1×1（生产路超长段，返builder）｜下一步：builder修P0-1（review三选一）+P1×3后，QA续本链补生产路三例+三坏例（HANDOFF只记状态，不代写结论）。

## 复验（V2.5补修，2026-09-11）

- QA：qa（真源主用 opencode/mimo-v2.5-free，本窗口 subagent；业务零改，只改本报告）
- 被测：`app/server.py`（147676B，13:26，V2.5补修：`_apply_v25_postpass`+双入口调用+P1-1接管+P1-2门+P1-3先存后注册）+ `src/stage9/formatter_v2.py`（13770B，13:22，新增`split_segments_for_engine`/`postprocess_paragraphs`）+ `src/stage9/__init__.py`（导出2函数）+ `app/index.html`（标题2字门+短词confirm+preview回显）；`git status`仅builder五改+本报告/review未跟踪，QA仓库内零写盘除本报告
- 任务目标：复验V2.5补修（生产路450字→[200,200,50]三例+DB坏例人话+单字拒收+注册落盘顺序；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-fix-input`（96K：clipP/Q/R各29854B合成2s）+ `/tmp/v2o-fix-data-prod`（244K：三run生产库）+ `/tmp/v2o-fix-data-dbless`（0B：空坏例库）+ `/tmp/v2o-fix-data-dbless-bad`（8K：坏表库）+ `/tmp/v2o-fix-data-vocab`（4K：词库）+ `/tmp/v2o-fix-vault`（4K：clipP.md）+ `/tmp/v2o-fix-runners`（28K：prod/vocab_db/live/neg四脚本）；残留交收尾
- 合成小视频：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipP.mp4`（29854B，ffprobe 2.0s），Q/R由P复制得；FF_EXIT=0
- stub：`server._transcribe_audio`猴补丁按文件名快返（P：450字`测`*450单段；Q：150+150双段gap0.1；R：3×`ab` gap10s；各`engine_calls=1`）
- 端口隔离：8765常驻（PID 63252）初末一致零扰动；live改走8771独立进程（`ThreadingHTTPServer(127.0.0.1,8771)`+`server.Handler`），测后已shutdown，8771已释（lsof空）；对8765零请求、零写
- **结论：PASS（V25-P0-1/P1-1/P1-2/P1-3全CLOSED：生产三例全≤200且450精确[200,200,50]，DB坏例全人话JSON不断线，单字400+短词preview，落盘先存后注册+双故障注入；PROD/PART2/LIVE各EXIT 0+NEG_EXIT 1+双编译0；零外部；真实目录/ob库零碰；结论只落本报告）**

### 复验用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| PROD-450生产路 | stub 450单段经`_process_one_run`（vault，PUBLISHED） | 全≤200且[200,200,50] | rendered与vault均[200,200,50] max200 | PROD_EXIT=**0** |
| PROD-150+150 | stub双150经`_process_one_run`（无vault，RENDER_ONLY） | 全≤200（裸引擎应301） | [200,101] max200，2段 | 同上 |
| PROD-3×ab | stub 3×ab大间隔经`_process_one_run`（RENDER_ONLY） | 合1段 | `['ab ab ab']` len8 | 同上 |
| REAPPLY-450 | `_reapply_one`（PUBLISHED→BLOCKED） | whisper0+Raw不变+`v25_postpass`+仍[200,200,50] | whisper0+raw_unchanged True+already_ok+`[200,200,50]` | 同上 |
| P1-1直接 | 未初始化库`_reapply_one` | 不抛+人话JSON | `ok False+状态库不可读：数据目录不存在` | PART2_EXIT=**0** |
| P1-1 handler | `_handle_reapply_post`单条坏库 | JSON不掉线 | code200+`ok False+状态库不可读` | 同上 |
| P1-1 open | `_open_rw`缺父目录 | FileNotFoundError人话 | `状态库不可读：数据目录不存在` | 同上 |
| P1-1坏表 | 空库缺表`_reapply_one` | 人话 | `状态库不可读：no such table` | 同上 |
| P1-2校验 | `_validate a→b/。。` | 拒收人话 | `至少2个字/纯标点不能作错词` | 同上 |
| P1-2 handler | `_handle_vocab_add a→b` | 400 | 400+`至少2个字`，文件无`"wrong": "a"` | 同上 |
| P1-2短词 | `ab→cd` | 200+preview | 200+`needs_confirm True+短词警告` | 同上 |
| P1-2基表 | `Github→x` | 400 | 400内置人话 | 同上 |
| P1-3顺序 | 源码序`_save`在`_register`前+人话/回滚 | 先存后注册 | save2815<reg3040+`保存失败未生效`+`entries_before` | 同上 |
| P1-3存爆 | `_save`注OSError | 500人话+内存不动 | 500+`词库保存失败，未生效` | 同上 |
| P1-3注册爆 | `_register`注ValueError | 400+文件回滚 | 400+文件空无`qqq123` | 同上 |
| 前端 | 标题/门/confirm/preview | 全含 | 4/4含（`错词至少2字/w.length<2/confirm(短词/preview.warnings`） | 同上 |
| 编译 | `py_compile server.py`+`sh -n app/start.sh` | exit 0 | 均为0 | **PY0/SHN0** |
| 进口 | AST仅stdlib+stage* | 无mlx/外调 | `http.server/urllib.parse`系stdlib，仅1行打印`http://`非外调 | 同上 |
| LIVE-DB | 8771 POST reapply坏库 | JSON不断线 | code200+`状态库不可读` | LIVE_EXIT=**0**（5/5） |
| LIVE单字 | 8771 POST vocab a→b | 400 | 400+`至少2个字` | 同上 |
| LIVE短词 | 8771 POST vocab zz→yy | 200+preview | 200+`needs_confirm True` | 同上 |
| LIVE查/缺参 | GET vocab+POST缺run_id | 200/400 | 200 count1/400缺编号 | 同上 |
| wrapper抽 | `render_with_v2` 450 | [200,200,50] | 一致 | WRAPPER_EXIT=**0** |
| 坏例负控 | 故意期望Github 200 | 应FAIL且exit 1 | FAIL got 400 | **NEG_EXIT=1** |

注：Q裸引擎301（150+1+150累积，`acc_len>=hard_max`仅下边界前检查）由代码口径+实测[200,101]反证（无fix应单段301超200）；R裸引擎3段`ab`由pause规则+实测合1段反证MIN生效；P重跑`already_ok True`系幂等（首跑已覆写，derive同rev），仍断言段长+whisper0。

Runner：三run种子（`upsert_source+get_or_create_auto_run`，hash `local-console-v1`，锁内）+按文件名stub+双分支（vault PUBLISHED/无vault RENDER_ONLY）+derive重跑+四坏例（空库/坏表/存爆/注册爆）+8771 urllib（HTTPError取code，不看打印）+错期望负控证exit1+双编译+AST+零外部+日志对账；8765（PID 63252）零请求零扰动。

### BUGS更新（本轮全CLOSED）

| Bug ID | Priority | Status | 复验证据一句 |
|---|---|---|---|
| V25-P0-1 | P0 | CLOSED | 生产三例经真实渲染：450→[200,200,50]（render+vault双≤200），150+150→[200,101]，3×ab→单段，重跑幂等仍[200,200,50] |
| V25-P1-1 | P1 | CLOSED | 空库/坏表直接+handler+8771全人话JSON不断线（`状态库不可读…检查数据目录`），`_open_rw`先验目录 |
| V25-P1-2 | P1 | CLOSED | `a→b`校验+handler双400（`至少2个字`），`。。`纯标点拒，2字`needs_confirm+短词警告`，文件无单字污染 |
| V25-P1-3 | P1 | CLOSED | 源码先存后注册，存爆500（`保存失败未生效`）内存不动，注册爆400文件回滚空 |

### Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.5补修复验（续首轮FAIL链，业务已修；builder五改未提交）
- Root Cause Hypothesis: 不适用（复验轮；首轮教训已收：wrapper自证漏生产路，本轮首即生产路三例）
- Approach: 外置七目录+ffmpeg单合成2s（440Hz P，三文件名复刻）+按名stub（450/150+150/3×ab，engine_calls=1）+双分支生产跑（vault/无vault）+derive重跑（whisper0+`v25_postpass`）+四坏例（空/坏表/存爆/注册爆）+8771隔离live 5断言+错期望负控证exit1+双编译+AST+零外部+8765零扰动
- Files Changed: 仅追加本报告复验节；`src/`+`app/`零改（builder五改保持M态，QA未碰）；测试写盘只在`/tmp/v2o-fix-*`（input96K+prod244K+runners28K+vault4K，交收尾）
- Verification: PROD_EXIT=0（三例+重跑）+ PART2_EXIT=0（DB4/单字4/顺序3/前端4/编译2）+ LIVE_EXIT=0（5/5）+ NEG_EXIT=1 + WRAPPER 0 + PY/SHN 0 + 8771已释
- Failure Reason: 无（全绿；`_handle_reapply_post`坏库回200+`ok False`非4xx/5xx，但JSON人话不断线满足“不掉线”口径，记U-7）
- Difference From Previous Attempt: 首轮FAIL（生产458+掉线+血洗+先注册）→本轮PASS（三例精确长度+全人话+双拒+双注入全绿）

### 未闭环清单（复验后；P0全绿）

- V25-P0-1/P1-1/P1-2/P1-3全CLOSED（上表）。
- U-1 真实转写未测延续（mlx缺；本轮stub代链路，whisper语义延V1.8；需长视频一次，用户定）。
- U-2 真实目录/ob库零碰以“七目录全`/tmp/v2o-fix-*`+8765 PID 63252初末一致+仓库内零写盘除本报告（builder五改保持M态，QA未动src/app）”代证；无真实快照（禁令）。
- U-3 默认库`/tmp/v2o-console-data`未用（全显式data_root指`/tmp/v2o-fix-*`）；残留（prod244K+input96K+runners28K+vault4K+dbless空/bad8K）交收尾。
- U-4 git口径：本仓实git仓（874aaf4），`git status`六M/未跟踪二（builder五改+本报告+CODE-REVIEW），源零改系QA口径（builder改保持）。
- U-5 P2延续（RENDER_ONLY不入库/all BLOCK计数/措辞），文档化不卡。
- U-6 8771已释无常驻；8765非本轮资产不动。
- U-7 新增P3：坏库单条回200+`ok False`（非4xx/5xx，JSON不断线已满足P1-1，改4xx需TM拍板，不卡PASS）。

---
目标：PACKAGING-V2.5补修复验｜剩 P0：无（P0-1/P1×3全CLOSED）｜下一步：交supervisor复检+product验（HANDOFF只记状态，不代写结论）。
