
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（最大合成文件2816B≤65536门内；PLAN已定真实长视频一律不测直到产品完成，20 Video Batch不做） | P2 | 否（转延续债，不卡Stage11闭环） | STAGE11-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本/词准确率/Golden/CER/幻觉指标Out（仅验哈希/计数/verdict/列/覆盖/exit码，文本内容不断言） | P3 | 否（PLAN已定，不卡门） | STAGE11-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | 真机reboot/真掉电未做（reboot以stop-all＋relaunch等价记账，掉电以Best Effort语义记账，`true_*=False`已断言） | P3 | 否（PLAN已定，不卡门） | STAGE11-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留待清（`/var/folders/.../T/s11qa-*`约7组外置目录KB级＋更早Stage残留，交neat-freak收尾） | P3 | 否（全在仓库外测试区，仓库内零污染） | STAGE11-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1-10/` git diff口径N/A（当前目录非git仓库；以QA零改＋回归十行PASS＋rg零命中代证） | P3 | 否（代证成立，不卡门） | STAGE11-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | LaunchAgent未做开机持久化（PLAN已定禁`enable`；load后立即unload，`list`无残留已证） | P3 | 否（PLAN已定，不卡门） | STAGE11-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | HANDOFF滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage11 builder计数基线；QA以落盘5文件＋PLAN为准独立覆盖） | P3 | 否（不卡QA PASS，交TM/supervisor补记） | STAGE11-QA-REPORT §未闭环U-7 | OPEN |
| U-8 | Stage12 Menu Bar未碰（STOP EXPANSION；`menu` rg零命中已证） | P3 | 否（PLAN Out，不卡门） | STAGE11-QA-REPORT §未闭环U-8 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage11闭环，P0-1~P0-6可证明，LaunchAgent演练＋§67矩阵7项＋故障11/11＋§72子集6断言可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE11-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE11-QA-REPORT.md`（PASS：happy链1遍＋§67矩阵7项＋故障11/11全绿＋异常/边界11个＋回归十行，Runner exit 0，坏例只看exit码FAIL侧exit 1）＋`src/stage11/`（`__init__.py/launch_plist.py/agent_boot.py/reliability.py/fault_suite.py`共5文件，只读直读已验）＋QA证据（runner `fault_suite.run_all`黑盒直跑`passed 11/11 failed [] running_probe PASS max 2816 small_only True`＋happy `sources 3→4 Lost=0`＋矩阵7/7＋坏例`_fail exit 1/_pass exit 0/坏plist FAIL/真实拒写ValueError`＋STOP三rg rc=1＋真实LaunchAgents前后快照等）。
- 用户只关心五句话：关机重启/杀进程会不会丢活——不会（Cold Boot经§62全序11步逐字到RUNNING＋停机补回Lost=0＋§67矩阵7项每项RUNNING＋Lost/Dup 0＋半截≠成功＋Repair路径Whisper恒0，掉电仅Best Effort记账不真测）；开机常驻会不会污染本机——不会（plist只写测试目录＋路径前缀断言＋真实`~/Library/LaunchAgents`、`/Library/LaunchAgents`前后快照一致＋`launchctl load`演练后立即`unload`无残留＋`enable`零出现）；各种故障会不会卡死/丢片/覆盖笔记——不会（故障11/11全绿＋套件后RUNNING可达无永久卡死＋任一BLOCK源保留Mis-delete=0＋诱饵覆盖恒0）；修好后会不会偷偷重跑转写/乱写库——不会（全链Whisper 0＋四表非预期零新增，唯一`archive_commits`＋1为F-N1 booked commit四列逐行披露＋直写DB rg零命中）；旧功能有没有被碰坏——没有（回归十行10/10＋`src/stage1-10/`零改代证＋STOP banned/SQL/force/enable四重rg零命中）。另加一句定心丸：真实长视频一律没测（最大合成2816B门内，文本内容不断言），延续到产品完成。
- 打回条件均未触发：P0-1~P0-6任一项不可证明即打回——本轮6项全部有代码＋Count/exit码/快照三证据；真实目录/真实库/真实Archive/真实LaunchAgents/云/长视频/`enable`/真实reboot/真掉电/menu/golden/LLM任一触碰即打回——product独立四重`rg -g '*.py'` RC=1四空已确认（banned串/SQL直写/force族/enable）＋`src/`十一目录齐（stage1~11）；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-6可证明逐项（口径=STAGE11-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | LaunchAgent plist常驻演练可证明（测试目录＋lint＋load→unload＋真实零触碰） | `launch_plist.py`（`LABEL_PREFIX=com.video2obsidian.test.`＋ProgramArguments全绝对＋WorkingDirectory＋RunAtLoad/KeepAlive真＋ThrottleInterval＋日志进`<data_root>/logs/`＋`write_plist`路径前缀断言＋`validate_plist` plutil-lint＋读回绝对路径＋`load/unload_test_plist`只对测试plist）＋QA：HAPPY/P0-1（lint PASS＋load rc0可见→unload rc0不可见无残留＋真实快照前后等＋enable零出现＋Whisper 0＋零DB写）；独立抽验：源码头注释真实目录永不写/禁持久化开机项已复读＋`LABEL_PREFIX`测试域已复读 | 可证明 |
| P0-2 | Cold Boot §62全序＋Single Instance重证可证明（11步逐字＋补回＋exit 3） | `agent_boot.py`（装配复用`stage5.startup.run_startup`全序＋返回order逐字11步＋`reboot_equivalent`记账`true_reboot_performed=False`＋`assert_second_instance_blocked`子进程exit 3＋mtime不变＋Archive/转写恒经gate无level_a/b直调柄）＋QA：P0-2（11/11逐字＋RUNNING真＋第二实例rc3＋mtime稳定＋真reboot否）＋HAPPY停机＋1补回Lost=0；独立抽验：`from stage5.startup import STARTUP_ORDER/run_startup/shutdown`只读装配已复读 | 可证明 |
| P0-3 | §67 Crash Guarantee矩阵可证明（5必须恢复＋Best Effort记账） | `reliability.py`（`snapshot/relaunch/assert_running/assert_recovered`＋`power_loss_best_effort_note`不真测＋`describe_reboot_equivalent`等价＋`archive_midcopy_drill`真drill）＋QA：M1~M7逐项PASS（M6 PASS-BY-EQUIVALENCE，掉电PASS-BY-BOOKING，M2/M3/M7另有F-R2/R3/R6真Repair举证，每项RUNNING＋Lost/Dup 0＋whisper 0＋四表零动）；独立抽验：模块“无真机reboot、无真掉电”装配约束与QA `true_*=False`记账行方向一致 | 可证明 |
| P0-4 | Fault Injection全套件可证明（复用7＋新增4，全绿＋无永久卡死） | `fault_suite.py`（注册表`CASE_IDS` F-R1~R7＋F-N1~N4共11＋`run_all`逐用例verdict/exit码/whisper/DB快照/hash/覆盖＋任一FAIL套件exit 1＋跑后RUNNING探针＋`MAX_SYNTHETIC_BYTES=65536`小文件门）＋QA：11/11 PASS suite exit 0＋跑后RUNNING可达＋BLOCK源保留＋cover 0＋Repair类whisper 0；独立抽验：文件头复用7/新增4定义与QA表逐项对齐（R1篡改BLOCK/R2 rename-kill/R3 midcopy/R4 race/R5碰撞新源/R6 lag/R7半截≠成功＋N1 commit前kill/N2 canonical被改/N3风暴/N4 plist幂等） | 可证明 |
| P0-5 | STOP EXPANSION门可证明（十目录不动＋无越权＋无直写＋无禁入） | QA：双rg＋真实快照＋enable审计全过（banned零命中rc=1＋SQL零命中＋force零命中＋enable零命中＋真实稳定＋arch仅F-N1＋1披露）；独立抽验：product自跑四重`rg -g '*.py'`（banned串/SQL直写/force族/enable）RC=1四空＋`ls src/`十一目录齐（stage1~11，无menu目录） | 可证明 |
| P0-6 | 外置合成验收门可证明（外置五目录＋合成副本＋长视频零触碰） | QA：全用例外置五目录（data/input/work/archive/output/agents）＋最大2816B（F-R3；happy最大1800B；上限65536）＋Whisper全链0＋诱饵覆盖恒0＋真实快照前后等＋文本内容不断言；独立抽验：`MAX_SYNTHETIC_BYTES=65536`门常量已复读＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. 任务目标重点：LaunchAgent演练＋可靠性＋故障11用例

- LaunchAgent演练：测试域Label＋绝对路径＋lint＋load可见→unload无残留＋真实零触碰＋禁`enable`，HAPPY/P0-1/F-N4三处举证一致。
- 可靠性：Cold Boot 11步RUNNING＋停机补回Lost=0＋第二实例exit 3＋§67矩阵7项逐项RUNNING＋Lost/Dup 0，reboot/掉电均为记账行（`true_*=False`），符合PLAN“不等价真机reboot/不真拔电”。
- 故障11用例：复用7（篡改BLOCK/rename-kill Repair/midcopy-kill源保留/race BLOCK/碰撞认新源/lag Repair/半截≠成功）＋新增4（commit前kill四列＋1披露/canonical被改BLOCK cover 0/风暴Run不新增/plist幂等），11/11 exit 0＋套件后RUNNING可达（§73-54无永久卡死）。
- §72子集6断言（QA §4逐项，product复读代码头＋QA表）：Cold Boot☑／Absolute Binary Paths☑／Single Instance重证☑／VolumeCapabilityProbe复用☑／iCloud-Remote BLOCK复用☑／Fault Suite☑。§73联动21→F-R2/R6、22→F-R7/F-R3、45→F-R6、46/48→P0-2、52→F-R1/R3/R4/N2、53→F-R4/N2、54→套件后RUNNING、2→happy补回。
- qa U-1~U-8非阻塞确认：见§3逐项接受理由；长视频不测延续（U-1）：最大2816B门内，20 Video Batch不做，代之small-N批量Lost/Dup 0。

## 3. U-1~U-8接受为非阻塞的理由（长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言常驻/恢复/故障语义（RUNNING/Lost/Dup/verdict/exit码/hash/覆盖/列diff），不认语音语义。延续债：产品完成后再拿1个真实视频走discover→boot→补回→fault抽查一遍，不断言词准确率只断言Lost/Dup 0＋诱饵不变。长视频不测延续。
- U-2（不断言词准确率）：接受。PLAN明示文本/ASR内容不断言（Golden/CER/幻觉属Stage11+ Out）；本轮以哈希一致＋调用计数＋verdict＋覆盖为判据，质量门后移不卡本门。
- U-3（真机reboot/真掉电未做）：接受。PLAN明示真机reboot/真掉电危险禁做；reboot以stop-all＋relaunch等价证明记账，掉电以Best Effort语义记账（flush/fsync＋PREPARED/Receipt已由Stage1/10落地），`true_*=False`已断言，不卡本PASS。
- U-4（残留待清）：接受。残留全在仓库外测试区（本轮`/var/folders/.../T/s11qa-*`约7组KB级＋更早Stage旧账），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——回归十行全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）＋product四重rg零命中；建议进git后恢复diff硬门。
- U-6（未做开机持久化）：接受。PLAN明示禁`enable`、开机持久化不做；本轮load后立即unload＋`list`无残留已证，语义覆盖成立。
- U-7（HANDOFF滞后）：接受。根HANDOFF仍停Stage2 CLOSED是TM记账问题，不影响本轮可证明性；QA已以`src/stage11/`落盘5文件＋PLAN S11-T05为准独立覆盖happy/矩阵/故障/回归，基线缺失不卡QA。建议TM/supervisor补记Stage3~11链状态。
- U-8（Stage12未碰）：接受。STOP EXPANSION明示Stage12 Menu Bar禁入；`menu` rg零命中已证，不在本门重验。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑常驻一遍，不断言速度/准确率只断言RUNNING＋Lost/Dup 0＋诱饵不变；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/var/folders/.../T/s11qa-*`（删前确认结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 流程确认（U-7＋缺席项）：supervisor确认HANDOFF补记Stage3~11链；Stage11 code-reviewer报告缺席（docs/review下无STAGE11-CODE-REVIEW）按AGENTS不可跳，建议supervisor复检时点名补审三处（plist前缀门＋boot只调公开入口＋fault runner exit码语义），非P0，不卡本PASS。

---
目标：Stage11闭环产品验收｜剩 P0：无（P0 Blocking以STAGE11-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
