
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮最大合成32768B小文件；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage5闭环） | STAGE5-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | Runner脚本归档（`/tmp/s5qa_run.py`＋`--bad ready/lock/second`三子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE5-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | 残留清理（`/tmp/s5qa` 13 data_root新增＋`/tmp/s5_builder_selfcheck`＋`/tmp/s5dbg{,2,3}`＋Stage4/3/2/1旧账＋$TMPDIR，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE5-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | `src/stage1/`/`src/stage2/`/`src/stage3/`/`src/stage4/` git diff口径N/A（当前目录非git仓库；以四回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE5-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | builder自验harness未在工作区落盘（`/tmp/s5_builder_selfcheck/run.py` 25 cases；QA以独立Runner 56断言覆盖，exit码对账一致） | P3 | 否（覆盖已闭环，不卡门） | STAGE5-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | 三路真并发调度非确定性（哪一路赢PROMOTED不保证；判据只用中央库Count＋dup 0＋exit码，不依赖胜者） | P3 | 否（判据已规避竞态，不卡门） | STAGE5-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Stage5无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0/1/2/3/4-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE5-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage5闭环，P0-1~P0-8可证明，Case3三路真并发Source=1/Run=1＋Watch First顺序硬门可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE5-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE5-QA-REPORT.md`（PASS，happy 1遍＋异常7个＋Triple Race真三路并发＋回归四行，56/56双轮exit 0，坏例只看exit码）＋`src/stage5/`（watcher/scan/reconcile/startup/__init__共5文件）＋QA证据`/tmp/s5qa/s5qa_results.json`（56 case全ok=true已复读，`fails=[]`）＋Runner`/tmp/s5qa_run.py`＋三坏例子进程（ready/lock/second）。
- 用户只关心五句话：我把视频丢进文件夹，工具能不能自己看见——能（HAPPY放1个`clip.mp4`经Watcher投递即PROMOTED，Source=1/Run=1/四表0）；我关机时丢进去的三个，开机后会不会丢——不会（停机放`off0~2`→同库重启→Scan补回Source=4/Run=4，Lost=0）；监听偶尔漏掉一个，会不会永远丢——不会（屏蔽投递后放`leak.mp4`→Source=0漏成立→periodic一次即补回，initial同语义）；三个渠道同时看见同一个视频，会不会建成三个任务——不会（Case3三路×5轮真并发15 outcomes全ok，中央库实查Source=1/Run=1，dup 0/0）；没写完的文件会不会被提前收走——不会（A5门内append仍`WAITING_FOR_STABLE_FILE`，不提前PROMOTED）。另加一句定心丸：开机顺序不会乱（`run_startup` 11步逐字，Ready前Scan被拒`WatcherNotReadyError`，无锁`start_watch`被拒`LockNotHeldError`，第二实例不吞`SecondInstanceError`＋CLI exit 3），旧地基没动（Stage1门/Stage2五步链/Stage3 verdict/Stage4 PUBLISHED行四回归全PASS，11个Stage5库四表恒0，Whisper调用恒0）。
- 打回条件均未触发：P0-1~P0-8任一项不可证明即打回——本轮8项全部有代码＋Count/exit码双证据；四表行数变动即打回——12库直查Stage5库全0（唯一非0为REG-S3回归库norm=1/rend=1，系Stage3语义预期）；出现`run_asr_single_file`/Stage6＋关键词/stage3-4 import即打回——`src/stage5`三重grep零命中已确认；Scan内出现“同path跳过”即打回——`scan.py`已直读无去重（仅文档行提及禁令）；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-8可证明逐项（口径=STAGE5-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Watch First可证明（watchdog真实监听＋只投递＋Ready门＋stop幂等） | `watcher.py`（Observer递归＋created/moved/modified去抖＋只调`discover()`＋`wait_ready`硬门＋`stop()`幂等＋`VIDEO_SUFFIXES`大小写不敏感＋`canonical()`归一）；QA：HAPPY Watch投递PROMOTED＋A-非视频忽略＋大写MP4照收＋stop×2后零投递；独立抽验：`rg run_asr`空＋`wait_ready`/`WatcherNotReadyError`门已直读 | 可证明 |
| P0-2 | Startup Scan可证明（Ready后全量补扫＋停机补回Lost=0＋无自有去重） | `scan.py`（前置`_resolve_watcher`无Ready即`WatcherNotReadyError`＋递归`iter_video_files`逐个`discover()`＋空目录`[]`）；QA：停机3个→Scan 3/3 PROMOTED＋重复Scan全MERGED计数不变＋Case13保size+mtime→新PROMOTED且`path_sources=2`；独立抽验：`scan.py`全文无skip/seen-set实现（命中仅文档禁令行） | 可证明 |
| P0-3 | Reconciliation可证明（Initial＋Periodic同语义＋§17/§18收敛＋漏事件补回） | `reconcile.py`（枚举现存→`discover()`→`reconcile_source`收口；RETRYABLE同run_id+1；NO_SPEECH返终态；QUEUED原样）；QA：屏蔽期Source=0→periodic一次补回＋initial同语义＋NO_SPEECH×10同run Count=1＋RETRYABLE×2同run retry 0→2；独立抽验：a_reconcile库src=2/runs=2（leak＋retry两跑道）与报告一致 | 可证明 |
| P0-4 | Triple Discovery Race可证明（Case3三路真并发Source=1/Run=1） | `__init__.py::triple_race_deliver`（`ThreadPoolExecutor(3)`三路×多轮真并发，收口仍在`discover`＋AUTO UPSERT）；QA：A1 rounds=5→15 outcomes全ok＋中央库Source=1/Run=1＋dup 0/0；独立抽验：a_race库直查src=1/runs=1＋results `A1-race-15-ok`/`Source1-Run1`/`dup-zero`三键ok | 可证明 |
| P0-5 | §62完整启动顺序可证明（11步逐字＋复用前五步＋delivery-only Workers） | `startup.py`（复用`instance.startup`前五步→Start Watcher→Confirm Ready→Scan→Initial Reconcile→Start Workers→RUNNING；`order!=STARTUP_ORDER`即`AssertionError`；fail-closed停半启动；Workers只调`discover()`）；QA：HAPPY/重启两次order 11逐字＋Workers投递成功＋shutdown×2幂等＋子进程SecondInstance不吞exit 1＋CLI exit 3；独立抽验：`STARTUP_ORDER` 11项已直读 | 可证明 |
| P0-6 | §72子集门可证明（Stage5 10断言） | 见§2表；QA §4十项全☑；独立抽验：results.json 56/56 `fails=[]`已复读＋本轮误触Runner重跑仍全PASS | 可证明 |
| P0-7 | STOP EXPANSION门可证明（四表恒0＋零调Whisper/Stage3+＋无Stage6+） | 代码头注STOP＋Workers delivery-only；QA：13库四表全0＋三重grep空＋四回归PASS；独立抽验：12库直查Stage5库norm/rend/pub/arch全0（reg_s3 norm=1/rend=1为回归预期）＋三重`rg` RC=1三空 | 可证明 |
| P0-8 | 外置合成验收门可证明（合成Input/Data Root＋真实长视频零触碰） | QA：全输入在`/tmp/s5qa`内＋最大32768B＋真实库零触碰；独立抽验：`/tmp/s5qa/happy/input` 4合成mp4在盘＋`GATE-synthetic-small max=32768B` ok＋results `HAPPY-canonical-spelling` ok | 可证明 |

## 2. §72子集门10断言（PLAN P0-6，QA §4逐项）

| §72子集 | QA | 产品抽验 |
|---|---|---|
| Watch First / Scan / Reconcile implementation | ☑ HAPPY Watch投递＋A-scan 3/3＋A4 periodic/initial双证据 | ☑ results `HAPPY-watch-PROMOTED`＋`A-scan-3-PROMOTED`＋`A4-periodic补回` ok |
| Stable File Detection | ☑ A5抖动仍WAITING | ☑ results `A5-jitter-WAITING` ok（第1 attempt即中） |
| Candidate Partial UNIQUE | ☑ 重复Scan全MERGED＋dup 0/0 | ☑ results `A-scan-repeat-MERGED`＋`HAPPY-dup-zero` ok |
| Historical Provisional Collision | ☑ Case13新Source（psrc=2/total=4） | ☑ results `A-case13-new-source` ok |
| Logical Source Exactly Once | ☑ Lost=0＋重复计数不变 | ☑ results `HAPPY-lost-zero`＋`A-scan-repeat-once` ok |
| Triple Discovery Race | ☑ 三路×5真并发Source=1/Run=1 | ☑ a_race库直查1/1＋results `A1-race-Source1-Run1` ok |
| AUTO Run Partial UNIQUE implementation | ☑ dup_run=0＋同对同run | ☑ results `A1-race-dup-zero`＋`REG-S2-discover-1-1` ok |
| Triple AUTO Count=1 | ☑ 中央库实查runs=1 | ☑ 同上a_race直查runs=1 |
| NO_SPEECH×10 Count=1 | ☑ 同run_id Count=1 | ☑ results `A2-nospeech-x10-Count1` ok |
| FAILED_RETRYABLE重试原Run | ☑ 同run_id retry 0→2无新Run | ☑ results `A3-retryable-same-run` ok |

## 3. U-1~U-6接受为非阻塞的理由（＋U-7；长视频不测延续）

- U-1（合成小文件非真实长视频）：接受。PLAN Out of Scope第73行明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage发现门只认Count/dup/exit码/order，不认音视频语义；抖动门内append与Case13保size+mtime翻转恰恰只能用合成字节精确构造，真实视频造不出门内竞态。延续债：产品完成后再拿1个真实视频走放盘→Watch投递→重启补回→Triple收口一遍，不断言速度只断言Source/Run=1/Lost=0。长视频不测延续。
- U-2（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s5qa_run.py`＋三坏例（`--bad ready/lock/second`）＋结果`/tmp/s5qa/s5qa_results.json`已记录，本轮product已复读56断言全ok＋`fails=[]`＋Runner重跑仍全PASS，可复算。建议HANDOFF记一笔路径。
- U-3（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s5qa` 13 data_root＋builder自检/调试＋Stage4/3/2/1旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-4（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1门反证＋Stage2五步有序＋Stage3 verdict＋Stage4 PUBLISHED行四回归全PASS＋QA零改声明（业务代码零改，仅新增本报告）；建议进git后恢复diff硬门。
- U-5（builder harness未落盘）：接受。T01~T05＋reg-lite＋size门25 cases已按S5-T06口径由QA独立Runner 56断言覆盖＋exit码对账一致；若builder后补harness，以本报告`56/56`＋`ready 1`＋`lock 1`＋`second 1`＋`CLI 3`为准对账，不返工产品结论。
- U-6（并发调度非确定性）：接受。判据已规避——只用中央库Count＋dup 0＋exit码，不依赖哪一路赢；Case13活watcher竞态已改确定性门（停gate watcher后scan，QA Fingerprint已记）；`database is locked`未抛到验收层（`_retry_locked`延续）。不卡门。
- U-7（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。Watch First三重门审计（Ready门/持锁门/第二实例不吞）与三路收口审计（无自有持久化语义、收口仍在`discover`＋AUTO UPSERT）两处正是code-reviewer主责，建议supervisor复检时点名补审这两处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑放盘→Watch投递→停机补回→Triple收口，不断言速度只断言Source/Run/Lost/verdict；机器时间分钟级＋人工＜15min。
- 清理（U-3）：neat-freak顺手清`/tmp/s5qa`＋`/tmp/s5_builder_selfcheck`＋`/tmp/s5dbg{,2,3}`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-2）：HANDOFF记一笔`/tmp/s5qa_run.py`＋`s5qa_results.json`＋三坏例（ready/lock/second）路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-7）：supervisor确认Stage5 code-reviewer是否补审（重点：Watch First三重门＋三路收口无自有写路径＋Workers delivery-only），非P0，不卡本PASS。

---
目标：Stage5闭环产品验收｜剩 P0：无（P0 Blocking以STAGE5-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
