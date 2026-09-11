
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（最大合成源896B；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage10闭环） | STAGE10-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本/ASR内容不断言词准确率（Golden/CER属Stage11+；仅验哈希/计数/verdict/列diff） | P3 | 否（PLAN已定，不卡门） | STAGE10-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s10qa_run.py`＋`--bad`八子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE10-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s10qa`约2.9M＋Stage9及更早旧账，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE10-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`~`src/stage9/` git diff口径N/A（当前目录非git仓库；以九回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE10-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | Cross-FS Level A为同盘强制分支模拟（单盘无第二device；`_same_device`强制False走真跨盘代码径） | P3 | 否（Same-FS为真link路径；需真双盘挂卷重跑一行即可） | STAGE10-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Mid-copy Kill为注入式半截（手写半截Final＋PREPARED，非SIGKILL真杀；后接真recover＋真commit） | P3 | 否（kill后状态＋Repair Forward全链实测，另有on_chunk注入举证） | STAGE10-QA-REPORT §未闭环U-7 | OPEN |
| U-8 | REG-S9为纯层回归（v2 profile/规则序/拒收三件；全链Case4/5由Stage9套件覆盖） | P3 | 否（口径与PLAN一致，不卡门） | STAGE10-QA-REPORT §未闭环U-8 | OPEN |
| U-9 | REG-S5未起live watcher/worker线程（验文件发现＋STARTUP_ORDER常量＋shutdown幂等，语义不断链） | P3 | 否（全量常驻属Stage5门，不卡门） | STAGE10-QA-REPORT §未闭环U-9 | OPEN |
| U-10 | HANDOFF滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage10 builder计数基线；QA以落盘7文件＋PLAN为准独立覆盖） | P3 | 否（不卡QA PASS，交TM/supervisor补记） | STAGE10-QA-REPORT §未闭环U-10 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage10闭环，P0-1~P0-7可证明，A/B/C＋current_path＋G3＋Case7/10可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE10-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE10-QA-REPORT.md`（PASS，happy A/B各1＋Cross-FS分支腿＋异常/边界8个＋回归九行，64/64三轮exit 0，坏例只看exit码八exit 1）＋`src/stage10/`（verify_archive.py/level_a.py/level_b.py/level_c.py/gate.py/commit.py/__init__.py共7文件，只读直读已验）＋QA证据`/tmp/s10qa/s10qa_results.json`（product已复读：`total=64 passed=64 failed=[] max_bytes=896 whisper=[]`，`happy_a.dual_proof/hash_match`＋`column_diff_four`＋`case7_reprocess`＋`e4.exists_is_not_done`＋八`bad_*.exit1`键已复读）＋Runner`/tmp/s10qa_run.py`（仓库外，在盘已确认）＋八坏例子进程（tamper/exists/levelc/midkill/nopub/edited/escape/noreceipt全exit 1，results键已复读）。
- 用户只关心五句话：归档前会不会不看内容就搬——不会（Strong Verify无条件重算SHA256＋前后fstat对比，同size＋同mtime＋异字节篡改夹具必`BLOCKED_SOURCE_CHANGED`且源保留，product独立复核`verify_source_for_archive`无快捷放行分支＋QA计数`hash_recomputed`真）；目标有人了会不会覆盖——不会（A/B双路＋gate预检双重No-Cover，预置未知文件必`BLOCKED_ARCHIVE_EXISTS`＋cover 0＋双intact，product独立复核`_link_no_cover EEXIST`＋`O_EXCL`两处拒覆盖）；半路断了会不会丢片/把半截当成功——不会（B路PREPARED ownership＋Receipt才算成功，注入半截后“存在≠完成”三断言＋真`recover_midcopy` Repair Forward补Receipt，Case10可证明，product独立复核`_finish_after_valid_final`双验＋删源前复算）；笔记被改了还归不归——不归（G3预门：无PUBLISHED记录即BLOCK，诱饵canonical被改即`BLOCKED_ARCHIVE_CANONICAL_EDITED`且`canonical_writes=0`，product独立复核`assert_publish_present` runs→norms→renders→PUBLISHED链＋哈希比对）；归完旧位置还能不能找到片——能（成功路径恰四列`current_path/location/status/archived_at`＋`archive_commits`＋1＋`resolve_current_path`双算`exists＋hash_match`，Case7可证明，product独立复核`SOURCES_WRITABLE`恰四列＋列级diff回滚门）。另加一句定心丸：真实长视频一律没测（最大合成源896B合成小文件门内，Whisper全链0），延续到产品完成。
- 打回条件均未触发：P0-1~P0-7任一项不可证明即打回——本轮7项全部有代码＋Count/exit码/hash复算三证据；LLM/转写越权/覆盖/直写DB越权/Stage11+关键词任一命中即打回——product独立`rg -g '*.py'` banned串RC=1已确认＋`run_asr_single_file/mlx_whisper`零命中＋SQL命中仅`commit.py`两行（INSERT archive一行＋UPDATE四列一行）逐行对应；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-7可证明逐项（口径=STAGE10-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Archive前Strong Verify可证明（无条件重算＋fstat对比＋篡改必BLOCK） | `verify_archive.py::verify_source_for_archive`（前后`fstat_capture`＋`sha256_file`只读复用，无size/mtime快捷分支；`==content_identity`放行else `BLOCKED_SOURCE_CHANGED`，零写库零删文件）＋`FSTAT_FIELDS`四字段＋mid-verify漂移门；QA：E1（同size＋同mtime＋同inode＋异字节必BLOCK，源保留，快照全等）＋`--bad tamper exit 1`（三同全真）；独立抽验：源码走读确认重算无条件＋results `bad_tamper.exit1 code=BLOCKED_SOURCE_CHANGED`已复读 | 可证明 |
| P0-2 | Level A Atomic No-Clobber可证明（Same-FS＋Cross-FS＋冲突不覆盖） | `level_a.py::archive_level_a`（目标存在即`BLOCKED_ARCHIVE_EXISTS`源保留目标intact；同盘`link`提交＋删源，跨盘目的端tmp＋`link`提交＋哈希验＋双删；成功必`ARCHIVE_COMMITTED`）＋`_link_no_cover EEXIST`拒覆盖；QA：HAPPY-A（真link，源消失＋Final哈希等＋Receipt＋archive＋1＋恰四列＋双算）＋HAPPY-A-X（强制False跨盘分支模拟，receipt `same_device=False`）＋E2（cover 0＋双intact）＋`bad_exists exit 1`；独立抽验：results `happy_a.bytes_moved/receipt/capability_probed(A)`＋`e2.block_exists/no_cover_no_loss`已复读 | 可证明 |
| P0-3 | Level B Reservation Copy＋Mid-copy可证明（全序＋Kill不丢＋Repair Forward＋存在≠完成） | `level_b.py::archive_level_b`（Strong Verify→O_EXCL独占建Final→PREPARED sidecar落盘→copy→fsync→SHA256→Receipt→再验源→删源）＋`recover_midcopy`（无归属`ArchiveRefused`永不动未知Final；PREPARED＋缺失INCOMPLETE；完整Repair Forward补Receipt；半截截断重拷`prepared_partial_recopy`）＋Receipt/ sidecar双文件；QA：HAPPY-B（双sidecar＋archive＋1＋恰四列）＋E4（存在≠完成三断言→Repair Forward Receipt，源删＋Final全哈希等）＋`bad_midkill exit 1`（源留＋PREPARED在＋Receipt缺＋archive 0）；独立抽验：`recover_midcopy/archive_level_b`存在＋results `e4.exists_is_not_done`已复读 | 可证明 |
| P0-4 | Level C正确Block＋Conflict/Overwrite=0＋G3可证明（C恒BLOCK＋双G3腿＋Mis-delete=0） | `level_c.py::archive_level_c`恒拒（结构上仅`open(rb)`读哈希，无任何写删调用，`target_touched False`）＋`gate.py`目标预检（lexists即BLOCK cover 0）＋`verify_archive.assert_publish_present`（runs→norms→renders→PUBLISHED链，无记录`BLOCKED_ARCHIVE_NO_PUBLISH`；诱饵哈希偏离`BLOCKED_ARCHIVE_CANONICAL_EDITED`，缺失对应MISSING，覆盖恒0）；QA：E3（C零触碰零写）＋E2/E5/E6/E8（BLOCK路径源哈希不变）＋`bad_levelc/nopub/edited exit 1`（`canonical_writes=0`）；独立抽验：level_c `os.unlink/os.remove`零命中（仅读）＋results `e3.levelc_pure/e6.block_edited`已复读 | 可证明 |
| P0-5 | Archive成功后Source更新可证明（恰四列＋archive行＋双算＋Case7） | `commit.py::commit_archive_success`（全Stage唯一写点：持锁＋Final双算＋`archive_commits`插一行＋`sources`恰四列＋列级自证＋`resolve_current_path`；`SOURCES_WRITABLE`恰四列，四列外任一被写回滚＋恰四列否则拒交；幂等`idempotent_retry`）＋`resolve_current_path`（Case7读盘演示）；QA：HAPPY-A/B `column_diff_four`恰`[archived_at,current_location_type,current_path,status]`＋`dual_proof(exists＋hash_match)`＋`case7_reprocess ARCHIVED`＋E7（重入`ALREADY_ARCHIVED`＋archive仍1）；独立抽验：`SOURCES_WRITABLE`四列已复跑＋results `happy_a.dual_proof/column_diff_four/archive_plus_one`已复读 | 可证明 |
| P0-6 | STOP EXPANSION门可证明（九目录不动＋三表零新增＋runs冻结＋无越权＋SQL逐行对应） | QA：九回归全PASS＋三表happy库1/1/1→archive仅四成功路径各＋1＋runs仍QUEUED＋banned串`rg`零命中（rc=1）＋SQL逐行披露（命中仅commit.py两行）＋`run_asr_single_file`六文件零命中；独立抽验：product自跑三重`rg`（banned串RC=1空＋asr-import RC=1空；SQL命中`commit.py:165 INSERT archive_commits`＋`:171 UPDATE sources四列`＋类型引用三行，无多余写）＋`ls src/`十目录齐＋`src/stage1-9/`零触碰声明（非git仓库N/A见U-5） | 可证明 |
| P0-7 | 外置合成验收门可证明（外置三Root＋合成副本＋真实长视频零触碰） | QA：全用例在`/tmp/s10qa`内（happy/异常/回归各独立data_root＋合成`clip.bin` 896B＋诱饵md）＋最大合成源896B＋Whisper全链0（全verdict双0＋`sys.modules`无引擎模块）＋真实库零触碰＋诱饵不变；独立抽验：`/tmp/s10qa/`在盘＋`s10qa_results.json max_bytes=896/whisper=[]`已复读＋`stop.whisper_zero`已复读＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. 任务目标重点：A/B/C＋current_path＋G3＋Case7/10

- Level A：同盘真link已证（HAPPY-A `same device + link commit available`）；跨盘分支腿已证（HAPPY-A-X强制False走真跨盘代码径，U-6声明单盘模拟，挂第二卷重跑一行即可转真双盘）。
- Level B：Reservation Copy全序已证（HAPPY-B双sidecar）； Ownership语义已证（无归属未知Final永不动；有归属可重入/补Receipt）。
- Level C：恒BLOCK零触碰已证（E3＋`verdict_unsupported target_touched False`结构性举证；product确认模块无写删调用）。
- current_path：成功路径恰四列＋`archive_commits`各＋1（四行与四源一一对应）＋`resolve_current_path`双算（DB值==磁盘真实路径＋isfile＋哈希一致），Case7可证明。
- G3：Publish重确认（无PUBLISHED即BLOCK，E5）＋用户编辑优先（被改即BLOCK且canonical零写，E6 `canonical_writes=0`），覆盖计数恒0。
- Case10：Mid-copy Kill源保留＋存在≠完成＋Repair Forward已证（E4 `prepared_partial_recopy`；U-7注入式声明接受，另有`on_chunk`注入中断举证源保留）。
- §72子集8断言（QA §4逐项，product复读results键＋代码走读）：Same-FS☑／Cross-FS A☑／O_EXCL Reservation☑／Mid-copy Kill☑／Conflict☑／Unsupported Block☑／current_path更新☑／Mis-delete=0☑。§73联动37→A/A-X、38→B、39→C、40→E4、41→E2＋E6、42＋12→E1、43→四列＋Case7、52→E5/E6。

## 3. U-1~U-10接受为非阻塞的理由（长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言归档语义（哈希/计数/verdict/列diff/双算），不认语音语义；跨盘/长时语义只用合成小文件＋分支模拟证明。延续债：产品完成后再拿1个真实视频走Archive一遍，不断言速度/准确率只断言源消失＋Final哈希等＋四列＋双算＋诱饵不变。长视频不测延续。
- U-2（不断言词准确率）：接受。PLAN明示文本内容不断言（Golden/CER属Stage11+）；本轮以哈希一致＋调用计数＋verdict＋列diff为判据，质量门后移不卡本门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s10qa_run.py`＋`--bad`八子进程＋结果`/tmp/s10qa/s10qa_results.json`已记录，本轮product已复读`64/64 fails=[]`＋八exit1键，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s10qa`约2.9M＋Stage9及更早旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——九回归全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）；建议进git后恢复diff硬门。
- U-6（Cross-FS模拟）：接受。本机单盘无第二device，强制False走的是真跨盘代码径（含目的端tmp＋link提交＋哈希验），不是跳过；Same-FS为真link路径；真双盘只需挂卷重跑HAPPY-A-X一行，不卡本PASS。
- U-7（注入式Kill）：接受。真SIGKILL易flake且难复算；本套件kill后状态（源留＋PREPARED在＋Receipt缺＋archive 0）＋真`recover_midcopy`＋真commit全链实测，另有`on_chunk`注入中断举证；语义覆盖成立。
- U-8（REG-S9纯层）：接受。全链Case4/5派生由Stage9套件覆盖，本轮回归v2 profile/规则序/拒收三件不断链即可，口径与PLAN一致。
- U-9（REG-S5未起常驻线程）：接受。live watcher/worker易flake属Stage5全量门；本套件验文件发现＋`STARTUP_ORDER`常量＋`shutdown`幂等，语义不断链声明成立。
- U-10（HANDOFF滞后）：接受。根HANDOFF仍停Stage2 CLOSED是TM记账问题，不影响本轮可证明性；QA已以`src/stage10/`落盘7文件＋PLAN S10-T05为准独立覆盖64断言，builder自验入口缺失不卡QA。建议TM/supervisor补记Stage3~10链状态。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑Archive一遍，不断言速度/准确率只断言源消失＋哈希等＋四列＋双算＋诱饵不变；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s10qa`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s10qa_run.py`＋`s10qa_results.json`＋八坏例路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-10＋缺席项）：supervisor确认HANDOFF补记Stage3~10链；Stage10 code-reviewer报告缺席（docs/review下无STAGE10-CODE-REVIEW）按AGENTS不可跳，建议supervisor复检时点名补审三处（No-Cover双路＋四列白名单＋SQL两行对应），非P0，不卡本PASS。

---
目标：Stage10闭环产品验收｜剩 P0：无（P0 Blocking以STAGE10-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
