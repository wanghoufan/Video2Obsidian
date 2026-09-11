
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（最大合成文件0B纯合成行无媒体文件；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage12闭环） | STAGE12-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本/词准确率/Golden/CER/幻觉指标Out（仅验计数/顺序/error/exit码/只读，不断言文本内容） | P3 | 否（PLAN已定，不卡门） | STAGE12-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | 诱饵canonical未建（本Stage不写不断言，仅零触碰成立，无"存在且不变"快照可附） | P3 | 否（PLAN口径不写不断言，不卡门） | STAGE12-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留待清（`/var/folders/.../T/opencode/s12qa-z5hpv84s/`本轮新增KB级＋更早Stage残留，交neat-freak收尾） | P3 | 否（全在仓库外测试区，仓库内零污染） | STAGE12-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | git diff口径N/A（当前目录非git仓库；以QA零改＋回归十二import PASS＋三rg零命中代证） | P3 | 否（代证成立，不卡门） | STAGE12-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | rumps有包路径为mock举证（本机无rumps；try-import旗＋真降级exit 0已证） | P3 | 否（PLAN允许mock或真机二选一举证，不卡门） | STAGE12-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | HANDOFF/复核滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage12 builder自验入口；`docs/review/`无STAGE12-CODE-REVIEW；QA以落盘4文件＋PLAN S12-T04为准独立覆盖） | P3 | 否（不卡QA PASS，交TM/supervisor补记） | STAGE12-QA-REPORT §未闭环U-7 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage12闭环，P0-1~P0-4可证明，只读/降级/动作面三件可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE12-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE12-QA-REPORT.md`（PASS：happy快照GROUP BY实查一致＋recent顺序/LIMIT＋error可复算＋CLI json/text/menu全绿＋rumps有/无双路径＋异常/边界7个全过＋DB mtime/sha不变＋STOP三rg零命中，坏例只看exit码缺库/坏库exit 2）＋`src/stage12/`（`status_snapshot.py/status_cli.py/menu_bar.py/__init__.py`共4文件，只读直读已验）＋QA证据（counts五表逐值等＋recent `[r6,r5,r4,r3,r2]`＋error runs 3＋art 1＝4＋CLI好0/坏2＋降级exit 0＋mock标题`V2O S:3 R:6 E:4`＋动作恰`[Refresh,Quit]`＋三rg rc=1＋回归十二import 12/12）。
- 用户只关心四句话：看状态会不会顺手写库——不会（`sqlite3.connect file:?mode=ro`＋`PRAGMA query_only=ON`＋经`stage2.store.central_db_path`纯寻址不持锁不init不discover不建Run，`collect`×2后mtime/sha前后不变，product独立`rg "INSERT|UPDATE|DELETE" src/stage12/` RC=1空已确认）；没装菜单依赖会不会崩/偷装东西——不会（`menu_bar.py`顶层`try: import rumps / except ImportError: RUMPS_AVAILABLE=False`，本机无rumps真降级`main()`打印CLI指引exit 0且stderr空，product独立`rg "pip install|subprocess.*pip|os.system"` RC=1空已确认）；菜单里会不会多出开始/重试/重跑按钮——不会（CLI菜单仅show/refresh/quit三项，`9→unknown`有提示；rumps下拉为三段只读文本＋仅Refresh（重读快照）/Quit（退菜单），product独立复读`_on_refresh/_on_quit`外无写柄＋禁入串`rg` RC=1空已确认）；旧功能有没有被碰坏——没有（回归`import stage1..stage12` 12/12可导＋DDL表9/9无新增＋`src/`十二目录齐stage1~12，`src/stage1-11/`本轮QA未触碰声明）。另加一句定心丸：真实长视频一律没测（最大合成文件0B纯合成行门内，文本/ASR内容不断言），延续到产品完成。
- 打回条件均未触发：P0-1~P0-4任一项不可证明即打回——本轮4项全部有代码＋Count/exit码/mtime三证据；真实目录/真实库/真实Archive/真实LaunchAgents/云/长视频/控制动作/Reprocess/`enable`/LLM任一触碰即打回——product独立三重`rg -g '*.py'` RC=1三空已确认（SQL直写/pip禁串/禁入禁串）＋`rg rumps status_cli/snapshot` RC=1确认CLI零rumps＋`ls src/`十二目录齐；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-4可证明逐项（口径=STAGE12-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | 只读状态快照可证明（GROUP BY聚合＋recent顺序/LIMIT＋error可复算＋零写＋缺库结构化错） | `status_snapshot.py::collect(data_root,limit=5)`（`_db_path`经`stage2.store.central_db_path`纯寻址、失败回退`data/state.db`拼接；`_connect_ro`以`file:?mode=ro`＋`query_only=ON`开柄；`_collect_open`五表`GROUP BY status`实查＋recent `ORDER BY updated_at DESC, created_at DESC LIMIT ?`＋error `processing_runs LIKE FAILED/BLOCKED ＋ artifacts同口径`冻结定义逐字落地；缺库`DB_MISSING`/打不开`DB_UNREADABLE`/缺核表`DB_SCHEMA_MISMATCH`三结构化码，不建库不修库不抛裸Traceback）＋QA：HAPPY（counts五表逐值等＋recent `[r6..r2]`＋error 4可复算）＋P0-1（`collect`×2 mtime/sha不变＋SQL rg rc=1）＋B-1~B-5（空库error 0/recent空＋缺库/坏库code＋schema码＋LIMIT `[r6,r5]`）；独立抽验：`mode=ro＋query_only＋central_db_path`三行已复读＋`rg INSERT|UPDATE|DELETE src/stage12/` RC=1空 | 可证明 |
| P0-2 | CLI status＋stdlib菜单可证明（json/text/menu三路径＋exit语义＋零rumps） | `status_cli.py`（`status [--data-root][--format json|text][--limit]`：json同构输出/text三段人读`state counts/recent runs/error count`；缺库exit 2＋结构化stderr；`menu/--menu`为stdlib `input()`循环show/refresh/quit三项，`9→unknown`提示，EOF/KeyboardInterrupt干净exit 0；全文件零`import rumps`）＋QA：P0-2（json同构recent 5 error 4＋text三段全含＋menu `1→show 2→refresh 3→quit`＋`9→unknown`＋缺库/坏库stderr结构化，好0/坏2）＋`rg rumps status_cli/snapshot` rc=1；独立抽验：`input()循环＋show/refresh/quit`三项已复读＋全程不import rumps RC=1空＋`py_compile`过 | 可证明 |
| P0-3 | rumps可选显示可证明（有则同口径、无则降级exit 0、动作仅Refresh/Quit） | `menu_bar.py`（顶层try-import＋`RUMPS_AVAILABLE`旗；`build_title`取同数`V2O S:%d R:%d E:%d`＋`build_lines`三段只读文本与CLI同构；有包`V2OApp`下拉＝只读行（callback None）＋`Refresh(_on_refresh`重读快照`)`/`Quit(_on_quit)`恰两动作；无包`main()`打印`python -m stage12.status_cli status …`指引exit 0；无包`V2OApp`占位抛指引错不崩）＋QA：P0-3（真环境无rumps `main`＋子进程双exit 0＋指引含`status_cli`＋stderr空；mock rumps标题`V2O S:3 R:6 E:4`＋下拉24行同口径＋actionable恰`[Refresh,Quit]`＋refresh后标题等）＋pip rg rc=1；独立抽验：`RUMPS_AVAILABLE`分支＋`Refresh/Quit`恰两动作已复读＋`rg pip install…` RC=1空 | 可证明 |
| P0-4 | STOP＋外置合成门可证明（十一目录不动＋DDL无新增＋无越权＋全外置＋长视频零触碰） | QA：STOP三rg（banned/SQL/pip）rc=1＋`mode=ro+query_only`有＋表9/9等＋无`init_db/discover建Run`柄（`discover`命中仅`discovery_candidates`表名）＋`py_compile`过＋REG十二import 12/12＋全用例外置五root（happy/empty/bad/schem/missing独立data_root）＋最大合成文件0B纯合成行＋诱饵不适用零触碰＋真实四目录零触碰＋Whisper不适用；独立抽验：product自跑三重`rg`（SQL直写/pip禁串/禁入禁串含`launchagent|level_a|level_b|commit_archive|run_asr_single_file|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber|reprocess`）RC=1三空＋`ls src/`十二目录齐（stage1~12，无越权目录）＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. 任务目标重点：只读/降级/动作面

- 只读：寻址只经`central_db_path`（`store.py`读到`require_lock_held`存在，QA已举证）；连接恒`mode=ro＋query_only`；零`INSERT/UPDATE/DELETE`（product独立rg空）；DB mtime＋sha双不变（QA快照比对真）；缺库/坏库/schema走结构化`{ok:false,code}`不建库（CLI坏侧exit 2）。
- 降级：无rumps为真环境已证路径（`ModuleNotFoundError`前提＋`main()`＋子进程`-m stage12.menu_bar`双exit 0）；有rumps为mock注入举证（标题/下拉同口径，U-6接受）；禁pip逻辑零命中，不提示安装不崩溃。
- 动作面：CLI菜单`show/refresh/quit`三项之外无入口（`reprocess/discover/start/stop/retry`禁串零命中）；rumps下拉只读行callback None＋动作恰Refresh/Quit两项（QA `actionable`断言＋product源码复读一致）；`status/refresh/quit/menu/snapshot`合法词不误杀已在QA STOP注明。
- qa U-1~U-7非阻塞确认：见§3逐项接受理由；长视频不测延续（U-1）：最大合成0B门内，文本内容不断言（U-2），产品完成后拿1个真实视频走快照→CLI→菜单一遍只断言计数/顺序/exit/只读。

## 3. U-1~U-7接受为非阻塞的理由（长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示"真实长视频一律不测直到产品完成（用户明确）"；本Stage只断言聚合语义（计数/顺序/error/exit/只读），不认语音语义。延续债：产品完成后再拿1个真实视频走`collect→status json/text→menu show→降级指引`一遍，不断言词准确率只断言counts一致＋recent顺序＋error可复算＋mtime不变。长视频不测延续。
- U-2（不断言词准确率）：接受。PLAN明示文本/ASR内容不断言（Golden/CER/幻觉属Stage12 Out）；本轮以GROUP BY复算＋顺序＋LIKE计数＋exit码为判据，质量门后移不卡本门。
- U-3（诱饵未建）：接受。本Stage不写canonical（写了即FAIL），不断言内容；"零触碰成立"即满足PLAN"存在且不变"在本Stage的退化形式（无存在可附快照不算缺证据）。
- U-4（残留待清）：接受。残留全在仓库外测试区（本轮`s12qa-z5hpv84s/` KB级＋更早Stage旧账），仓库内零污染（本轮product亦只写本报告）；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——回归十二import全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）＋product三重rg零命中；建议进git后恢复diff硬门。
- U-6（mock举证）：接受。PLAN明示mock rumps或真机二选一举证，不强制真机常驻；本机无rumps已证`ModuleNotFoundError`＋真降级exit 0方向正确；若需真机常驻，装rumps后重跑mock节即可，不卡本PASS。
- U-7（HANDOFF/复核滞后）：接受。根HANDOFF仍停Stage2 CLOSED是TM记账问题，不影响本轮可证明性；QA已以`src/stage12/`落盘4文件＋PLAN S12-T04为准独立覆盖happy/异常/STOP/回归探针，基线缺失不卡QA。建议TM/supervisor补记Stage3~12链状态。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑快照→CLI→菜单一遍，不断言速度/准确率只断言counts一致＋recent顺序＋error可复算＋mtime不变；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/var/folders/.../T/opencode/s12qa-z5hpv84s/`（删前确认结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 流程确认（U-7＋缺席项）：supervisor确认HANDOFF补记Stage3~12链；Stage12 code-reviewer报告缺席（docs/review下无STAGE12-CODE-REVIEW）按AGENTS不可跳，建议supervisor复检时点名补审三处（只读URI＋query_only双保险／CLI exit 2语义／rumps动作面仅Refresh-Quit），非P0，不卡本PASS。

---
目标：Stage12闭环产品验收｜剩 P0：无（P0 Blocking以STAGE12-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
