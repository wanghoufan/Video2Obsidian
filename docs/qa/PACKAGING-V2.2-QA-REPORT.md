# QA-REPORT｜PACKAGING-V2.2验收（换目录门隔离/同目录仍挡/列表按目录过滤/清空只删本目录/笔记截断+双链接/失败人话+一键换数据目录）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py`（1931行，81355B，09:52）+ `app/index.html`（882行，44247B，09:55）+ `app/start.sh`（40行，1376B，07:45）（PACKAGING-V2.2增量；`src/` 只读复用）
- 任务目标：验收V2.2四项（换目录启动不再STOP失败/同目录仍挡/列表按目录过滤/清空只删本目录且源文件md不动/笔记正文接口截断/两链接格式/失败人话+一键换数据目录；合成+stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码）
- QA 执行目录（仓库外）：`/tmp/v2o-pkgv22-data`（148K：门隔离主库，A/B双源）+ `/tmp/v2o-pkgv22-inputA`（32K：clipA.mp4 30262B 2.0s 440Hz）+ `/tmp/v2o-pkgv22-inputB`（32K：clipB.mp4 30726B 2.0s 880Hz）+ `/tmp/v2o-pkgv22-vault`（8K：clipA/B.md）+ `/tmp/v2o-pkgv22-data-e2e`（168K：stub端到端库）+ `/tmp/v2o-pkgv22-data-e2e-empty`（空vault分支库）+ `/tmp/v2o-pkgv22-input-e2e`（32K：clipE.mp4）+ `/tmp/v2o-pkgv22-vault-e2e`（出md）+ `/tmp/v2o-pkgv22-runners`（40K：live8766/e2e_stub/gate_runstate/note_test/validate_live/neg+日志）；仓库内零写盘除本报告
- 合成小视频：`ffmpeg testsrc=320x240:rate=10:duration=2+sine=440Hz → clipA.mp4`（30262B）+ `rate=12+sine=880Hz → clipB.mp4`（30726B），ffprobe各2.0s，FF_EXIT=0/PROBE_A_EXIT=0/PROBE_B_EXIT=0
- stub：`server._transcribe_audio` 猴补丁返回固定中文+1 segment+engine_calls=1（E2E用），门/列表/清空/笔记四项直接调函数不碰 `mlx_whisper`/`extract_temp_wav` 真转写
- 端口隔离：8765被常驻实例占用（PID 88460，EADDRINUSE），本轮未kill/未POST/未碰其data/input/vault；live HTTP改走8766独立进程（`live8766.py` + `ThreadingHTTPServer(127.0.0.1,8766)`），测后已停，8766已释（lsof空）；对8765零请求、零写
- **结论：FAIL（P0-1接线FAIL一票否决：`_launch:1404` 用未定义 `input_abs`，真实启动必 `NameError` 走通用失败，无GATE码无一键建议；门逻辑本身/列表过滤/清空隔离/笔记截断+双链接/人话文案全PASS；live 18/18 exit 0+E2E双分支PUBLISHED/RENDER_ONLY whisper_calls=1+NEG exit 1；py_compile/sh-n exit 0；零外部；src零改以mtime 09:52-55早于QA 09:59代证；真实目录/ob库零用；结论只落本报告，打回builder单行修）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| P0-1接线 `_launch` | 直调 `_launch(DATA,INA)`（stub run/worker）查 `_listener` | GATE码或202成功 | `NameError: input_abs` → `启动监听失败：name 'input_abs' is not defined` code=None sugg=None | 直接调用 EXIT=**0**（复现成立，判FAIL） |
| P0-1静态 `input_abs` | AST查 `_launch` args vs `input_abs` 引用/赋值 | 有定义 | args=`[data_root,input_root,ob_vault_root,profile_hash]`，引用有、赋值无 | 审计 FAIL |
| P0-1换目录门隔离 | 种子A链（norm/rend/pub各1）后 `_scoped_stage3(INB)` | PASS `{0,0,0,0}` | PASS一致 | GATE_EXIT=**0** |
| P0-1同目录仍挡 | 同上 `_scoped_stage3(INA)` | FAIL Stage3+ | FAIL一致 `{'normalization_revisions':1,...}` | GATE_EXIT=**0** |
| P0-1运行态换目录 | 坏状态run挂A源后 `_scoped_runstates(INB)` | PASS `{QUEUED:1}` | PASS一致 | GATE2_EXIT=**0** |
| P0-1运行态同目录 | 同上 `_scoped_runstates(INA)` | FAIL transcription-stage | FAIL一致 `{'PUBLISHED':1}` | GATE2_EXIT=**0** |
| P0-1 fail-closed | 孤儿norm `raw_orphanXYZ` 后 `_scoped_stage3(INB)` | FAIL（计挡住） | FAIL一致 | GATE2_EXIT=**0** |
| P0-1恢复 | `_restore_scoped_gates()` 后查原函数+scope | 原断言+scope None | `assert_stage3_tables_empty` 原名+`SCOPE=None` | GATE_EXIT=**0** |
| P0-1人话+GATE码 | `_humanize` Stage3/RunState/NameError三例 | GATE_STAGE3/BLOCKED+GATE_RUN_STATE+sugg路径；NameError走通用None | 全一致；sugg=`/tmp/v2o-pkgv22-data-YYYYMMDD-HHMMSS` 不存在、前缀为data_root | GATE_EXIT=**0** |
| P0-2前缀判定 | `_is_under_root` A∈A/B∉A/A∉B/evil前缀 | True/False/False/False | 全一致 | FILTER_EXIT=**0** |
| P0-2 pending按目录 | `_count_pending(DATA,INA/B/excl)` | 各1；excl runA后A=0 | 1/1/0 | FILTER_EXIT=**0** |
| P0-2列表过滤 | `_filter_status_runs` A/B各调 | A=`[runA,orphan]` B=`[runB,orphan]` filtered True | 一致（孤儿可见fail-open） | FILTER_EXIT=**0** |
| P0-2终态过滤 | `_filter_merged_by_input` | A=`[runA,memOrphan]` B=`[runB,memOrphan]` | 一致（磁盘孤儿排除、内存孤儿保留） | FILTER_EXIT=**0** |
| P0-2限流 | `_handle_status` limit -5/9999/abc/20 | 200+filtered True（`max(1,min(,200))`） | 全200 filtered True | FILTER_EXIT=**0** |
| P0-2清空只删本目录 | `_handle_clear_post({DATA,INA})` | 200 runs=1，他目录不动 | 200 `已清空本目录 1 个任务记录` cleared sources1/runs1/norm1/rend1/pub1/job_dirs1 | CLEAR_EXIT=**0** |
| P0-2清空隔离 | 查DB残留+job盘+内存 | 剩srcB/runB，jobA删/jobB留，done/processed只剩B | 一致 | CLEAR_EXIT=**0** |
| P0-2源与md不动 | 对比清空前后源mp4+vault md | 全存在且内容不变 | clipA/B.mp4在，vault clipA/B.md在 | CLEAR_EXIT=**0** |
| P0-3笔记小正文 | `_handle_note(runSmall)` | 200 text非空 trunc False | 一致 total29 | NOTE_EXIT=**0** |
| P0-3笔记截断 | `_handle_note(runLarge 7000字)` | trunc True total7000+`已截断…在访达中打开` | 一致，尾串含截断 hint | NOTE_EXIT=**0** |
| P0-3两链接 | finder `file://` + ob `obsidian://open?vault=&file=` | finder编码、ob vaultBase+rel编码 | `file:///tmp/...clipB.md` + `obsidian://open?vault=v2o-pkgv22-vault&file=clipB.md`；空格`%20` | NOTE_EXIT=**0** |
| P0-3链接边 | 无vault/无path/库外稿 | 各reason人话 | `未配置笔记库…`/`还没有可打开的笔记`/`尚未入库…` | NOTE_EXIT=**0** |
| P0-3无md人话 | FAIL/BLOCK/QUEUED未知 | `转写失败：…`/`排队等待处理…` | 一致；缺run_id 400 | NOTE_EXIT=**0** |
| P0-4前端双链+笔记 | index.html含 `在访达中打开/在OB中打开/obsidian://open/file:///笔记正文/笔记加载中` | 全含 | 全含 | STATIC_EXIT=**0** |
| P0-4一键+清空 | 含 `一键换新数据目录/btnNewData/suggested_data_root/清空本目录任务/btnClear/再次确认/源视频文件与笔记不动` | 全含 | 全含（`renderLock` 有sugg即显按钮） | STATIC_EXIT=**0** |
| P0-4失败人话 | 含 `转写环境没就绪/重试这个视频/排队/失败` + 进度 `progText/progFill/renderProgress/空闲：暂无排队视频` | 全含 | 全含 | STATIC_EXIT=**0** |
| 零外部 | 正则 `https?://\|<script src\|<link\|@import\|src="http\|href="http` | 0行 | 0行（`grep -c http`=0 rc=1为零命中语义） | 审计 PASS |
| 进口审计 | AST imports | 仅stdlib+stage* | stdlib+json/os/shutil/sqlite3/sys/tempfile/threading/urllib/http/datetime+stage1/2/3/4/5/6/7/8/12 | 审计 PASS |
| E2E vault分支 | stub `_process_one_run(DATA-e2e,INE,VAULTE)` | PUBLISHED whisper1+vault md+receipt | PUBLISHED `clipE.md`存在 manifest末PUBLISHED | E2E_EXIT=**0** |
| E2E空vault分支 | `_process_one_run(DATA2,INE,None)` | RENDER_ONLY+render md | RENDER_ONLY render md存在 | E2E_EXIT=**0** |
| E2E坏例 | vanished run_id | SKIP | SKIP | E2E_EXIT=**0** |
| live 18断言 | `validate_live.py` 经8766（index5/browse2/status2/note4/start1/clear2/precheck2） | 全PASS则exit 0 | 18/18 PASS | **VALIDATE_EXIT=0** |
| 坏例负控 | `neg.py` 故意期望202调合法start（实400） | 应FAIL且exit 1 | FAIL got 400 | **NEG_EXIT=1** |
| 编译 | `py_compile server.py` + `sh -n start.sh` | exit 0 | 均为0 | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |

注：`grep -c http` 对index.html返回0行时grep进程exit=1——这是“零命中”的正确exit语义（审计脚本exit 0，此处直接以0行+rc=1双记，不判FAIL）。E2E中watchdog `already scheduled` 为同input双startup复用所致警告，不影响E2E_EXIT=0。

Runner：直接函数对照（门/过滤/清空/笔记/人话/suggest/fail-closed/恢复）+ stub E2E双分支 + urllib经8766（HTTPError取code断言，不看打印）+ 错期望负控证exit1 + 双编译 + AST进口 + 零外部 + 日志对账；8766起于 `live8766.py`（127.0.0.1:8766），测后已kill端口已释；8765常驻实例零请求零扰动。

## BUGS（照 BUGS.template.md；本轮 P0×1 打回）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| V2.2-P0-1（接线） | P0 | 是 | 任意 `POST /api/start` →后台`_launch`首行 `_install_scoped_gates(input_abs)` 抛 `NameError`→`GET /api/start` 得 `启动监听失败：name 'input_abs' is not defined` code None sugg None；换目录/同目录均同错，门逻辑走不到 | OPEN | builder单行修：`app/server.py:1404` `input_abs`→`input_root`（与`_launch(data_root,input_root,…)`形参同名；`run_startup`内`input_abs`为其局部量，不跨函数），修后重跑本报告P0-1四断言 | AST证引用有赋值无+直调复现+live start仍400 PRECHECK（门未走到） |
| 无（V2.2其余） | — | 否 | 列表过滤/清空隔离/笔记截断+双链接/人话+suggest逻辑全码一致；E2E双分支+live18/18+负控exit1 | CLOSED | 无需修 | 门逻辑PASS仅接线挡路，修线即全绿 |

## Fix Attempt Fingerprint

- Task ID: PACKAGING-V2.2验收（首轮QA，业务零修）
- Root Cause Hypothesis: 不适用（除P0-1接线变量名笔误外全PASS；`__pycache__`若刷新为import产物，`.py` mtime app 09:52-55早于QA 09:59，源零改成立）
- Approach: 外置九目录+ffmpeg双合成2s（440Hz A/880Hz B）+stub快返（engine_calls=1）+同库双源种子（A链norm/rend/pub各1+B空）+scoped双向对照（换PASS/同FAIL）+运行态双向+孤儿fail-closed+恢复+人话三例+suggest前缀+前缀攻击+pending对称+status/merged过滤+limit四例+clear单目录删查（DB+job盘+内存+源/vault不动）+note大小/截断/双链三边/无md人话+前端双链/一键/清空双确认审计+8766隔离live18断言+错期望负控证exit1+双编译+AST进口+零外部+E2E双分支+vanished SKIP+8765零扰动
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-V2.2-QA-REPORT.md`；`src/`+`app/`零改；测试写盘只在 `/tmp/v2o-pkgv22-*`（data148K+e2e168K+inputA/B 64K+e2e32K+vault8K+runners40K，交neat-freak收尾）
- Verification: GATE_EXIT=0（换PASS/同FAIL逻辑）+ GATE2_EXIT=0（运行态双向+fail-closed）+ FILTER/CLEAR/NOTE_EXIT=0 + E2E_EXIT=0（PUBLISHED/RENDER_ONLY/SKIP）+ VALIDATE_EXIT=0（18/18）+ NEG_EXIT=1 + PY_COMPILE/SHN 0 + 8766已释
- Failure Reason: V2.2-P0-1接线FAIL（`input_abs` 未定义，见上表；门逻辑本身PASS，故单行修后可过，无需重构）
- Difference From Previous Attempt: 首轮，无上一轮（PACKAGING-V2/V2.1报告另存，不混；V2.1 P1-1/P1-2已闭为FAIL/failed计数见`queue.failed`，本轮回归正常）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡除P0-1外全绿）

- U-1 真实转写未测（mlx缺，PRECHECK挡202，live start 400 `PRECHECK_MLX_MISSING`；E2E以stub代证链路，whisper冻结模型语义延续V1.8已知限制；需stage0bench venv+长视频一次，用户定时间）。
- U-2 真实目录/ob库零碰以“九目录全`/tmp/v2o-pkgv22-*` + runners/输入/vault/data全外置 + 8765常驻实例零请求（lsof仍PID 88460）+ 仓库内零写盘除本报告”代证；无真实库快照（按禁令不得写）。
- U-3 默认库 `/var/…/T/v2o-console-data` 非本轮所用（全显式data_root指向`/tmp/v2o-pkgv22-data*`）；本轮主库148K+e2e168K残留交收尾。
- U-4 `__pycache__` mtime可能因import刷新（`.py` mtime未动，源零改成立；pyc为构建产物）。
- U-5 非git仓库，`git diff`口径N/A；以app mtime 09:52-55早于QA 09:59+本轮零写代证（同V2/V2.1 U-5 Pattern）。
- U-6 残留待清：`/tmp/v2o-pkgv22-*`（data/e2e/input/vault/runners+live8766.log/pid+large/small/render md），交neat-freak收尾；8766已释无常驻；8765常驻实例非本轮资产，不动。
- U-7 P0口径：`DONE_STATES=(PUBLISHED,RENDER_ONLY)` + `FAIL_STATES=(FAIL,PUBLISH_BLOCKED)` 进度诚实延续V2.1；`started_at`窗口与P2-3直写等延续V2评审，不卡。
- U-8 E2E复用同input双startup致watchdog `already scheduled` 警告一次（E2E_EXIT=0，不影响结论；并发startup避同input可消）。

---
目标：PACKAGING-V2.2验收｜剩 P0：V2.2-P0-1接线（`input_abs`→`input_root`单行，修后重验P0-1）｜下一步：交 builder修线＋product-reviewer验＋supervisor复检（HANDOFF 只记状态，不代写结论）。

## 复验修订（2026-09-11 10:07，qa opencode-go/glm-5.3-flash，只改本报告）

- 被测增量：`app/server.py` 2056行（10:03，`input_abs`计数0，`_install_scoped_gates(input_root)`@1456）+ `app/index.html` 895行（10:04，`finderUrlFor`按段`encodeURIComponent`+`%3A`→`:`，`outCellFor/renderOpenRow`复用）；`src/`只读未动。
- 范围：V2.2打回五项——换目录真实启动成功＋同目录仍挡＋`file://`含`#/?`编码＋运行中clear被拒＋NULL archive清理；合成＋stub；外置目录；用户真实目录与ob库禁碰；坏例看exit码。
- QA执行目录（仓库外，全新建`re-`前缀）：`/tmp/v2o-pkgv22-re-data`（132K，门隔离主库）＋`/tmp/v2o-pkgv22-re-inputA`（64K：clipA.mp4＋`clip A #1?.mp4`）＋`/tmp/v2o-pkgv22-re-inputB`（32K：clipB.mp4）＋`/tmp/v2o-pkgv22-re-data-e2e`（168K）＋`/tmp/v2o-pkgv22-re-input-e2e`（clipE.mp4）＋`/tmp/v2o-pkgv22-re-vault-e2e`（clipE.md）＋`/tmp/v2o-pkgv22-re-runners`（re_verify/re_e2e/re_neg）；仓库内零写盘除本报告。
- 合成：`ffmpeg testsrc+sine → clipA(440Hz 29835B)/clipB(880Hz 30111B)`各2.0s，FF_EXIT=0/PROBE_A/B_EXIT=0；`clip A #1?.mp4`由clipA复制得（HASHCP_EXIT=0），专供`#/?`/空格编码用例。
- stub：`re_verify.py`内stub `run_startup`（调真实被patch门断言后回dummy handle）＋stub `_transcribe_worker`（no-op）；`re_e2e.py`内stub `_transcribe_audio`固定中文`engine_calls=1`。
- **结论：PASS（打回五项全绿：`_launch(INB)` running True无错＋`_launch(INA)` GATE_STAGE3_BLOCKED带sugg＋前后端`file://`双侧`%23/%3F/%20`无裸`#/?`＋clear运行中409＋NULL/archive空归属清后双零；`re_verify` 31断言全PASS；`re_e2e` PUBLISHED whisper1；前端node三例；NEG exit1；双编译0；零外部；8765零扰动；本报告外仓库零写）**

### 复验用例（坏例只看exit码）

| 用例 | 实测 | exit码 |
|---|---|---|
| AST `input_abs`清零 | count 0，`_install_scoped_gates(input_root)`在位 | 审计PASS |
| P1-1空归属fail-closed（stage3/runstate，hole源＋TRANSCRIBING＋NULL下scoped INB） | 双双FAIL计挡住（`archive_commits:1`/`TRANSCRIBING:1`） | RE_VERIFY_EXIT=**0**（31/31） |
| 换目录门隔离（A链norm/rend/pub/arch各1后scoped INB） | PASS `{0,0,0,0}` | 同上 |
| 同目录仍挡（scoped INA） | FAIL四表全1 | 同上 |
| 运行态换/同（TRANSCRIBING挂A后INB/INA） | PASS `{QUEUED:1}` / FAIL含TRANSCRIBING | 同上 |
| 恢复（scope None＋原函数名） | 两轮一致 | 同上 |
| 人话三例 | GATE_STAGE3+GATE_RUNSTATE带sugg（`…-data-YYYYMMDD-HHMMSS`）；NameError走通用None | 同上 |
| 换目录真实启动成功（stub run＋worker，直调`_launch(DATA,INB)`） | running True＋error/code None＋调到run/worker＋scope恢复 | 同上 |
| 同目录仍挡（直调`_launch(DATA,INA)`） | running False＋GATE_STAGE3_BLOCKED＋sugg存在＋scope恢复，无NameError | 同上 |
| 后端`file://`（`clip A #1?.mp4`＋中文） | `clip%20A%20%231%3F.mp4`（`%23/%3F/%20`齐，无裸`#/?`）；中文`%E8…` | 同上 |
| 前端`file://`（node复刻`finderUrlFor`三例） | 同后端一致，无裸`#/?` | FRONTEND_EXIT=**0** |
| 运行中clear被拒 | 409 `正在监听/转写中，请先点停止再清空` | RE_VERIFY_EXIT=0 |
| NULL archive清理（清前BLOCK→`_handle_clear_post(INA)`200→NULL 0/空源0/B留1/源mp4在） | cleared含archive 2/sources 2，他目录不动 | 同上 |
| stub E2E（合成clipE＋stub转写） | PUBLISHED whisper_calls=1，vault md存在 | E2E_EXIT=**0** |
| 坏例负控（故意期望202调合法start，实400 PRECHECK） | assert炸 | **NEG_EXIT=1** |
| 编译 | `py_compile`＋`sh -n` | **PY_COMPILE_EXIT=0/SHN_EXIT=0** |
| 零外部 | `grep -c http`=0行（rc=1系零命中语义） | 审计PASS |
| 真实目录/ob库禁碰 | 全`/tmp/v2o-pkgv22-re-*`；8765仍PID 88460 LISTEN零请求；仓库内除本报告零写（app mtime 10:03-04系builder修线，QA未写业务） | 代证PASS |

### BUGS修订

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| V2.2-P0-1（接线`input_abs`） | P0 | 是 | 首轮直调`_launch`抛NameError | CLOSED | 无需再修（本轮直调双向：INB成功/INA门BLOCK，均无NameError） | builder已修1456行，本轮31断言代证 |
| V2.2-P1-1（空归属fail-closed） | P1 | 否 | hole源此前当他input放行 | CLOSED | `_unattributable_source_ids`＋双门`unatt`分支＋clear `eff_srcs`同步，复验双BLOCK＋清后双零 | 见`server.py:176-198/227-228/282/324/1708-1722` |
| V2.2-P1-2（前端`file://`未编码） | P1 | 否 | `file://'+esc(out)`裸`#/?` | CLOSED | 前端按段`encodeURIComponent`，后端`quote(safe="/:")`，双侧`%23/%3F`复验一致 | `index.html:323-337/454`＋`server.py:835-837` |
| V2.2-P1-3（运行中可清＋NULL清不掉） | P1 | 否 | 运行中无锁＋`IS NULL`漏删 | CLOSED | 运行中409人话＋`DELETE … IS NULL`每清必带，复验409＋NULL 0 | `server.py:1658-1661/1866-1872` |

Runner：`re_verify.py`（门双向＋hole双BLOCK＋launch双向stub＋编解码＋409＋NULL清，31断言）＋`re_e2e.py`（stub单分支PUBLISHED）＋node前端三例＋`re_neg.py`错期望证exit1＋双编译＋零外部；残留`/tmp/v2o-pkgv22-re-*`交neat-freak收尾；8765常驻实例未kill/未POST。

---
目标：PACKAGING-V2.2复验｜剩 P0：无（五项全绿，NEG_EXIT=1，E2E 0）｜下一步：交 product-reviewer验＋supervisor复检（HANDOFF只记状态，不代写结论）。
