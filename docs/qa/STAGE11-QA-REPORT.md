# QA-REPORT｜Stage11 S11-T05 验收套件 + §67/§72/§73 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage11/`（`__init__.py/launch_plist.py/agent_boot.py/reliability.py/fault_suite.py`）+ `src/stage1~10` 只读复用（回归探针）
- 计划：`docs/pm/STAGE11-PLAN.md` S11-T05（P0-1~P0-6；happy 链 1 遍 + §67 矩阵 7 项 + 异常/边界 ≥10 个 + 故障全套件 11 用例 + 回归十行；外置合成 Input/Data/Archive/诱饵 Output 四 Root + 测试 LaunchAgents 目录；合成小文件；load 后立即 unload；坏例只看 exit 码；结论只落本报告）
- 输入：`src/stage11/` 落盘 5 文件 + 上轮 builder 的 ctx（`{data_root,input_root,work_root,archive_root,output_root,test_agent_dir,profile,boot}`）与 runner 入口（`fault_suite.run_all(ctx)` + `launch_plist.load/unload_test_plist` + `agent_boot.cold_boot/reboot_equivalent` + `reliability.snapshot/relaunch/assert_recovered`）
- QA 执行目录（仓库外）：`/var/folders/.../T/s11qa-*/`（`s11qa-ddk8y2uj` plist 构建/`s11qa-load-md1lxu23` load→unload/`s11qa-boot-8ivjs7kf` cold boot/`s11qa-fault-4plc5pdy` 故障全套件/`s11qa-crash-*` 矩阵/`s11qa-happy-*` happy 小批量/`s11qa-reg*` 回归；各独立 data/input/work/archive/output/agents；合成小文件 deterministic bytes；诱饵 md；仓库内零写盘除本报告）
- **结论：PASS（happy 链 1 遍 + §67 7 项逐项 + 故障 11/11 全绿 + 异常/边界 11 个全过 + 回归十行 + STOP 门全过；Runner exit 0；坏例只看 exit 码：FAIL 侧 exit 1 符合预期；Whisper 恒 0；四表非预期零新增；诱饵覆盖恒 0；最大合成文件 2816B（≤65536 门内）；load 后立即 unload 无残留；真实 LaunchAgents 零触碰；结论只落本报告）**

## 1. 输入复核（src/stage11 落盘 5 文件，只读消费 + 黑盒调用）

- `launch_plist.py`（S11-T01）：`build_plist`（Label 测试域 `com.video2obsidian.test.` 前缀 + ProgramArguments 全绝对路径 + WorkingDirectory + RunAtLoad/KeepAlive 真 + ThrottleInterval + StandardOut/Error 进 `<data_root>/logs/`）+ `write_plist` 路径前缀断言（测试目录内，不在即拒写；真实目录拒写）+ `validate_plist`（`plutil -lint` 过 + 读回绝对路径 + 字段存在）+ `load/unload_test_plist`（只对测试 plist；演练后立即 unload）。QA 实测：构建/写盘/校验 PASS，`plutil -lint` 过，load rc0 可见、unload rc0 不可见无残留，真实目录前后快照一致。
- `agent_boot.py`（S11-T02）：`cold_boot` 装配复用 `stage5.startup.run_startup` 全序，返回 order 数组逐字 11 步（`Static Preflight → … → RUNNING`）+ `reboot_equivalent`（stop-all + relaunch + Bootstrap，`true_reboot_performed=False` 记账）+ `assert_second_instance_blocked`（子进程 `SecondInstanceError` exit 3 + DB mtime 不变）。QA 实测：order 11 步逐字一致、RUNNING 真、第二实例 rc3 + mtime 稳定。
- `reliability.py`（S11-T03）：`snapshot/relaunch/assert_running/assert_recovered`（RUNNING + Lost/Dup 0 + 半截≠成功 + whisper 增量 0 + 四表非预期零动）+ `power_loss_best_effort_note`（Best Effort，不真测）+ `describe_reboot_equivalent`（等价证明，不真 reboot）+ `archive_midcopy_drill`（level-B copy + pre-unlink 切模拟 SIGKILL + `recover_midcopy` Repair）。QA 实测：7 项矩阵逐项 PASS，掉电/reboot 均为记账行（`true_*=False`）。
- `fault_suite.py`（S11-T04）：注册表 11 用例（复用 F-R1~R7 + 新增 F-N1~N4）+ `run_all`（逐用例 verdict + exit 码 + whisper 增量 + DB 快照 + hash + 覆盖计数；任一 FAIL 即套件 exit 1；跑后 RUNNING 可达探针）。QA 实测：11/11 PASS，suite exit 0，`max_file_bytes=2816`，`small_files_only=True`。
- 上轮 builder 口径：HANDOFF 仍停 Stage2 CLOSED，未登记 Stage11 builder 自验计数值；`docs/review/` 无 STAGE11 复核报告；QA 按 S11-T05 口径独立合成（小文件 + 外置五目录 + 诱饵 md），happy/矩阵/故障/回归全覆盖；未发现 plan/qa 口径分叉。

## 2. 用例简表（坏例只看 exit 码；四表=norm/rend/pub/arch；Whisper=真调增量）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 四表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY happy 链 1 遍 | 新五目录 + 合成源 | discover→plist 演练→cold_boot RUNNING→N=3 批量→停机补回→fault 绿→RUNNING | RUNNING + Lost=0 + Dup=0 + load→unload 无残留 | 一致（批量 3 源 3 Run；停机 +1 补回；load 可见→unload 不可见） | Runner exit 0；sources 3→4 | norm/rend/pub 0；arch 0（happy 未归档） | 0 |
| P0-1 plist 演练 | 新 data/agents/input | build→write→validate→load→立即 unload→真实快照 | lint 过 + 绝对路径 + load 可见 + unload 无残留 + 真实稳定 | 一致（lint PASS；load rc0 True；unload rc0 False/residue False） | load exit 0；unload exit 0 | —（零 DB 写） | 0 |
| P0-2 cold boot + 单实例 | 新 data/input | cold_boot→order 比对→第二实例→reboot 等价 | 11 步逐字 + RUNNING + 第二实例 exit 3 + mtime 稳定 + 真 reboot 否 | 一致（11/11；rc3；mtime True） | exit 0 | 全 0 | 0 |
| M1 process crash | 运行中快照 | relaunch→assert_recovered | RUNNING + Lost/Dup 0 + whisper 0 | PASS | exit 0 | delta 全 0 | 0 |
| M2 kill-9 rename/manifest 前 | 同上（F-R2 真 Repair 另证） | relaunch→assert_recovered | 同上 | PASS | exit 0 | delta 全 0 | 0 |
| M3 kill-9 mid-copy | 同上（F-R3 真 drill 另证） | relaunch→assert_recovered | 同上 + 源保留 | PASS | exit 0 | delta 全 0 | 0 |
| M4 application restart | 同上 | relaunch→assert_recovered | 同上 | PASS | exit 0 | delta 全 0 | 0 |
| M5 LaunchAgent restart | 测试 plist unload+load | relaunch→assert_recovered | 同上 + 真实零触碰 | PASS | exit 0 | delta 全 0 | 0 |
| M6 reboot 等价 | stop-all | reboot_equivalent→RUNNING + Lost/Dup 0 | 等价行 + 真 reboot 否 | PASS-BY-EQUIVALENCE | exit 0 | delta 全 0 | 0 |
| M7 SQLite 落后 | 同上（F-R6 真 Repair 另证） | relaunch→assert_recovered | 同上 | PASS | exit 0 | delta 全 0 | 0 |
| F-R1 篡改 BLOCK | 合成源（同 size+同 mtime+异字节） | verify | BLOCKED_SOURCE_CHANGED + 源保留 | PASS | exit 0 | 零新增 | 0 |
| F-R2 rename-kill Repair | job 骨架 PREPARED | rename 落地→recover | COMMITTED + RepairForward + whisper 0 | PASS | exit 0 | job 内 manifest 修 | 0 |
| F-R3 midcopy-kill | 合成源 + work 副本 | pre-unlink 切→recover | 源保留 + Receipt + Final 哈希等 | PASS | exit 0 | 零表写（drill 侧） | 0 |
| F-R4 race BLOCK | 合成源 + Final 预置异主 | gate | BLOCK + cover 0 + 源保留 | PASS | exit 0 | 零新增 | 0 |
| F-R5 碰撞认新源 | 同 path 同 size/mtime 异字节 | discover 双投 | 新 source_id（不静默折叠） | PASS | exit 0 | sources +1（预期） | 0 |
| F-R6 lag Repair | PREPARED+COMMITTED Final | manifest 回退→recover | manifest 补 Receipt + whisper 0 | PASS | exit 0 | job 内修 | 0 |
| F-R7 半截≠成功 | PREPARED tmp 仅 | 存在≠完成三断言 | Final 缺 + Receipt 缺 + tmp 在 = 不成功 | PASS | exit 0 | — | 0 |
| F-N1 commit 前 kill | 合成源 staged bytes | kill（行未动）→booked commit | bytes 安全 + 行不动→四列 + arch +1 | PASS | exit 0 | arch +1（披露） | 0 |
| F-N2 canonical 被改 BLOCK | 合成源 + 诱饵 v1→v2 用户改 | gate | BLOCK + cover 0 + 源保留 | PASS | exit 0 | 零新增 | 0 |
| F-N3 风暴 Run 不新增 | 同文件 8 并发 discover | storm→重投 | Source=1 + Run=1 + run_delta=1 | PASS | exit 0 | run +1（首投） | 0 |
| F-N4 plist 幂等 | 测试 plist | load×2→unload | 双可见 + 卸后不可见 + 真实稳定 | PASS | load 0/unload 0 | — | 0 |
| STOP 门 | 全量 stage11 | 双 rg + 真实快照 + enable 审计 | banned 零命中 + SQL 零命中 + 真实稳定 | 一致（rg rc=1；enable 零） | rg rc=1 | arch 仅 F-N1 +1 | 0 |
| B-坏例 exit | 合成前置 | _fail/_pass + 坏 plist + 真实拒写 | FAIL 侧 exit 1；坏 plist FAIL；真实拒写 | 一致（fail 1/pass 0；坏 7 problems；拒写 ValueError） | FAIL exit **1** | — | 0 |
| REG 十行 | 外置合成 | 见§3 | 不断链 | 10/10 一致（S10 无 publish 正确 BLOCK） | exit 0 | — | 0 |

Runner：`fault_suite.run_all(ctx)`（仓库内 runner，ctx 外置五目录）→ `verdict PASS exit 0 passed 11/11 failed [] running_probe PASS max 2816 small_only True`；happy/矩阵/crash/plist/load-unload/坏例/STOP/回归均为本报告内直跑复验（exit 码见表）；最大合成文件 2816B（F-R3；happy 最大 1800B；上限 65536；真实长视频零触碰；文本内容不断言）；Whisper 全链 0（全 verdict `whisper_delta==0/asr_calls==0/whisper_calls==0`）；`archive_commits` 仅 F-N1 +1（booked commit，四列 `archived_at/current_location_type/current_path/status` + dual hash_match，逐行披露；其余用例 0）；诱饵覆盖恒 0（F-N2 编辑后值稳定，F-R4 目标前后哈希等）。

## 3. 每用例明细（前置/动作/期望；exit 码 + 四表 + 诱饵 + Whisper 0 + 外置路径）

- HAPPY：前置新 `data/input/archive/output/agents` + profile `test-profile-v1`；动作合成源→`discover`→plist build/write/validate→`cold_boot`（11 步 + RUNNING）→N=3 合成（各 1600B）discover（3 源 3 Run）→shutdown→停机加 1（1800B）→`reboot_equivalent` RUNNING→补 discover（MERGED，第 4 源，Lost=0）→`load`（rc0 True）→立即 `unload`（rc0 False/residue False）；期望 RUNNING + Lost=0 + Dup=0 + 无残留 + 真实稳定；实测全中（`sources 3→4`，`norm/rend/pub 0`，诱饵未用，max 1800B，外置五目录，真实快照前后等）。
- P0-1：前置同上；动作 `build_plist(label测试域, sys.executable, data, agents, input)`→`write_plist`→`validate_plist(expect_label/binary/data_root)`→`snapshot_real_agents` 前后→`load`→立即 `unload`→`list | grep label` 空；期望 lint PASS + 全绝对路径 + Label/RunAtLoad/KeepAlive 在 + load 可见 + unload 不可见 + `enable` 零出现 + Whisper 0 + 零 DB 写；实测全中（`lint_ok True problems []`，load/unload 见表，真实 `~/Library/LaunchAgents` 10 项前后等，`/Library/LaunchAgents` 空前后等）。
- P0-2：前置新 data/input；动作 `cold_boot`→order 与 `STARTUP_ORDER` 逐字比→`assert_second_instance_blocked`（子进程 exit 码 + mtime）→`reboot_equivalent`；期望 order 11 步倒置/跳步 FAIL（实测 11/11）+ RUNNING 真 + 第二实例 exit 3 + mtime 稳定 + `true_reboot_performed False` + Archive/转写恒经 gate（`expected_hash` 必填，level_a/b 无直调柄）；实测全中。
- M1~M7：前置运行中 `snapshot`；动作各 `relaunch(old,data,input)`→`snapshot`→`assert_recovered(whisper_delta=0)`→`assert_running`；M2/M3/M7 另有 F-R2/R3/R6 真 Repair drill 举证（见下）；M5 含测试 plist unload+load；M6 用 `reboot_equivalent`；掉电仅 `power_loss_best_effort_note`（`true_power_test False PASS-BY-BOOKING`）；期望每项 RUNNING + Lost/Dup 0 + 半截≠成功 + whisper 0 + 四表零动；实测 7/7 PASS（delta 全 0）。
- F-R1：前置合成 `f-r1.mp4`（1536B）discover；动作同 size 异字节重写 + utime 恢复 mtime→`verify_source_for_archive`；期望 `BLOCKED_SOURCE_CHANGED` + 同 size/mtime 真 + 源保留 + 后恢复原字节；实测 PASS（exit 0，max 1536B）。
- F-R2：前置 job 骨架 + `prepare_raw`（expected hash）；动作 tmp→final 拷贝（kill 介于 rename 与 manifest 之间）→`recover_raw`；期望 COMMITTED + `prepared_final_exists_repair_forward` + whisper 0；实测 PASS（max 963B）。
- F-R3：前置合成 orig（2816B）+ work 副本 discover；动作 `archive_midcopy_drill`（pre-unlink 抛切模拟 SIGKILL→`recover_midcopy`）；期望切可见 + 切时源在 + Receipt COMMITTED + Final 哈希等 + orig 字节等；实测 PASS（max 2816B，全套件最大）。
- F-R4：前置合成 `f-r4.mp4`（2200B）discover + Final 预置异主；动作 `gate.archive_source`；期望 BLOCK + 源在 + `target_cover_count 0`（前后哈希等）；实测 PASS。
- F-R5：前置同 path（1200B）discover；动作同 size/mtime 异字节重写 + utime→二次 discover；期望新 `source_id != 旧`；实测 PASS。
- F-R6：前置 job 骨架 + prepare + commit；动作 manifest receipts 清空 + state 回 PREPARED→`recover_raw`；期望 Final 哈希等 + manifest 补 COMMITTED + whisper 0；实测 PASS。
- F-R7：前置 job 骨架 + prepare；动作三断言（tmp 在 + Final 缺 + Receipt 缺）；期望不成功；实测 PASS。
- F-N1：前置合成 orig（2420B）+ work 副本 discover；动作 `level_b.archive_level_b`（bytes 落 Final，kill 在 commit 前：行不动 arch 不动）→`commit_archive_success`；期望 bytes 安全 + 行不动 + 四列 + dual 真 + arch +1 + orig 在；实测 PASS（唯一 arch +1，逐行披露）。
- F-N2：前置合成（2200B）discover + 诱饵 v1；动作诱饵改 v2（用户编辑）→`gate.archive_source`；期望 changed 真 + BLOCK + 源在 + 诱饵 cover 0（after==edited）；实测 PASS（note：合成 env 无转写链，G3 预门止于 NO_PUBLISH，S52/S53 不变量已断言）。
- F-N3：前置同文件（1760B）；动作 8 并发 discover（ThreadPool）→重投；期望 Source=1 + Run=1 + `run_delta==1`；实测 PASS。
- F-N4：前置测试 plist build/write/validate；动作 load×2→unload→真实快照；期望双可见 + 卸后不可见 + 无残留 + 真实稳定；实测 PASS（max 0B，非文件用例）。
- B-坏例（判据只用 exit 码）：`_fail→exit 1` + `_pass→exit 0` + 坏 plist（Label/路径/字段全错）`validate→FAIL problems 7` + 真实目录 `build/write→ValueError 拒写`；任一吞错即 FAIL；实测全中。
- STOP 外置/冻结：输入全在外置五目录（与真实视频目录/真实 Obsidian 库/真实 Archive 目录/真实 LaunchAgents 目录无交集，外路径断言 + 真实快照前后等）；最大 2816B；Whisper 全 0；`rg "menu|golden|cer|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite" src/stage11/` 零命中（rc=1）；`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage11/` 零命中（rc=1，直写 DB 零行，无需逐行披露；Recovery/Commit 写恒经 stage1/10 既有语义）；`rg "force|overwrite|clobber"` 零命中（rc=1）；`rg "enable"` 零命中；`launchctl enable` 零出现；真实 reboot/真掉电零执行（均为记账行）；`src/stage1-10/` git diff 口径见 U-5。
- 回归（外置合成，Whisper 0）：REG-S1 stage1 骨架 prepare→commit→recover COMMITTED whisper 0；REG-S2 cold_boot 持锁下 discover 双投同 source/run（PROMOTED/MERGED）；REG-S3 stage3 模块 import（冻结零调用）；REG-S4 stage4 conflict/publish 模块 import + Ownership 只读语义（本 Stage 不派生 Revision）；REG-S5 `cold_boot` 11 步 RUNNING + shutdown；REG-S6 stage6 mirror import + 嵌套映射（Stage6 套件覆盖）；REG-S7 stage7 vocab/profile/language import（单文件接线语义只读引用）；REG-S8 stage8 chunk/vad/timeline/merge import；REG-S9 stage9 rules_v2/formatter_v2 import；REG-S10 gate 无 publish 链正确 `BLOCKED_ARCHIVE_NO_PUBLISH`（whisper 0，G3 不断链；happy 归档由 Stage10 套件覆盖，本轮不重跑长链）。

## 4. §72 子集门（Stage11 6 断言逐项）+ §73 联动

- [x] LaunchAgent Cold Boot（P0-1+P0-2：测试域 Label + 绝对路径 + lint + load→unload + 11 步 RUNNING；`happy/plist/boot`）
- [x] Absolute Binary Paths（build/validate 双证：ProgramArguments 非 hash 项全绝对 + WorkingDirectory 绝对 + 日志在 data 内；`plist.validate`）
- [x] Single Instance agent 下重证（第二实例 exit 3 + mtime 稳定；`boot.second-instance` + F-N3 风暴 Run 不新增）
- [x] VolumeCapabilityProbe 复用（Stage5/10 既有语义只读装配；回归不断链）
- [x] iCloud-Remote Root BLOCK 复用（Stage4/10 既有语义；F-R4/F-N2 BLOCK 路径举证源保留 + cover 0）
- [x] Fault Injection Suite（11/11 + 跑后 RUNNING 可达，无永久卡死；`run_all.running_probe PASS`）
- §73 联动：21→F-R2/R6（Repair Forward whisper 0）；22→F-R7/F-R3（半截≠成功 + Receipt 后成功）；45→F-R6（lag Repair）；46/48→P0-2（补回 + 单实例）；52→F-R1/R3/R4/N2（任一 BLOCK 源保留）；53→F-R4/N2（覆盖恒 0）；54→套件后 RUNNING 可达；2→happy 停机补回 Lost=0。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | 11/11 exit 0；坏例 FAIL 侧 exit 1 符合预期 | CLOSED | 无需 builder 修 | runner `fault_suite.run_all` 黑盒直跑 + happy/矩阵/坏例/STOP 直跑复验 |

## Fix Attempt Fingerprint

- Task ID: S11-T05 Stage11 验收套件 + §72/§73 子集门 + Stage1~10 回归（首轮 QA 执行，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；回归探针 1 处为 QA 自身顺序问题：先 discover 后 cold_boot 撞 `LockNotHeldError`，改持锁后 discover 即一致；S10 无 publish 链 gate 正确 BLOCK，非业务 FAIL）
- Approach: 外置五目录各用例独立 data_root + 确定性小文件 + 诱饵 md；happy（discover→plist→boot→批量→补回→load→立即 unload）+ 矩阵 7 项（relaunch + assert_recovered）+ 故障 11（真 verify/recover/gate/commit/discover/plist 路径）+ 坏例只看 exit 码（_fail 1/_pass 0/坏 plist FAIL/真实拒写）+ STOP 双 rg + 真实快照 + enable 审计 + 回归十行（S1 真链 + S2 持锁双投 + S5 真 boot + S3/4/6/7/8/9 import + S10 无链 BLOCK）
- Files Changed: 仅新增本报告 `docs/qa/STAGE11-QA-REPORT.md`；业务代码零改；测试写盘只在 `/var/folders/.../T/s11qa-*`（H2 外置目录约束延续）；Runner 为仓库内 `src/stage11/fault_suite.py` + 本报告内直跑复验
- Verification: 故障 `verdict PASS exit 0 passed 11/11 failed [] running_probe PASS max 2816 small_only True`；happy `sources 3→4 Lost=0 load 0→unload 0 residue False 真实稳定`；矩阵 7/7 PASS；坏例 FAIL 侧 exit 1；STOP rg 三 rc=1 + enable 零；回归 10/10；Whisper 全 0；arch 仅 F-N1 +1；诱饵 cover 0；真实 LaunchAgents 前后等
- Failure Reason: 无 FAIL 项（业务侧）；QA 自修 1 处为锁顺序（改持锁后一致）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 QA 自修 1 处：锁顺序）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大 2816B；20 Video Batch 不做，代之 small-N 批量 Lost/Dup 0；文本/ASR 内容不断言）。
- U-2 文本/词准确率/Golden/CER/幻觉指标 Out（PLAN 已定；本报告仅验哈希/计数/verdict/列/覆盖/exit 码）。
- U-3 真机 reboot/真掉电未做（PLAN 已定：reboot 以 stop-all + relaunch 等价记账，掉电以 Best Effort 记账；`true_*=False` 已断言）。
- U-4 残留待清：`/var/folders/.../T/s11qa-*`（本轮新增约 7 组外置目录，小文件总量 KB 级）+ 更早 Stage 残留（Stage10 U-4 所列），交 neat-freak 收尾。
- U-5 `src/stage1-10/ git diff 为空`口径 N/A（当前目录非 git 仓库；以 QA 零改 + 回归十行 PASS + rg 零命中代证；同 Stage10 U-5 Pattern）。
- U-6 LaunchAgent 未做开机持久化（PLAN 已定：禁 `enable`；本轮 load 后立即 unload，`list` 无残留已证）。
- U-7 HANDOFF 滞后：根 HANDOFF 仍停 Stage2 CLOSED，未登记 Stage11 builder 计数基线与异常清单；本报告输入复核以 `src/stage11/` 落盘 5 文件 + PLAN S11-T05 为准，基线缺失不卡 QA（已独立覆盖）。
- U-8 Stage12 Menu Bar 未碰（STOP EXPANSION；`menu` rg 零命中已证）。

---
目标：Stage11验收S11-T05｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。

## 重跑（2026-09-11，P1-1~P1-5 修复后；只追加节，首轮结论不动）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只改本报告本节）
- 输入：`src/stage11/` 修复版 5 文件 + `docs/review/STAGE11-CODE-REVIEW.md` 复核节（P1-1~P1-5 全 CLOSED，可转 QA 重跑；P2×7 记 backlog 不卡关）
- QA 执行目录（仓库外）：`$TMPDIR/s11rerun-*`（nolock/kill9/r4n2/lockhandoff/badex/plist/regS*/regS10 各独立 data/input/work/archive/output/agents；合成小文件 deterministic bytes；仓库内零写盘除本报告本节）
- **结论：PASS（三例必测全过 + 全套件 11/11 exit 0 + 回归十行 10/10 + 坏例只看 exit 码符合预期；最大合成文件 2816B（≤65536）；Whisper 全 0；load 后立即 unload 无残留；真实 LaunchAgents 前后等；结论只落本报告）**

### 重跑简表（坏例只看 exit 码）

| 必测 | 动作 | 期望 | 实测 | exit 码 / Count |
|---|---|---|---|---|
| P1-1 无锁直调 `run_all` | 新五目录、无 `boot` 直调 `fault_suite.run_all(ctx)` | 自动 `cold_boot` 预持锁后 11/11 PASS（非 7 个散 `LockNotHeldError` FAIL、无 `PRE-BOOT` FAIL-fast） | 一致（`verdict PASS passed 11/11 failed []`，跑后 `ctx["boot"]` 非空，`running_probe PASS`，`small_files_only True`） | suite exit **0**；`max_file_bytes=2816` |
| P1-5 `kill9_child_relaunch` 真信号 | `cold_boot`→子进程 `sleep` 持 job→父 `os.kill(SIGKILL)`→`relaunch`+`assert_recovered`/`assert_running` | `sigkilled True` + `rc -9` + `recovered PASS` + `running PASS` | 一致（`sigkilled True child_returncode -9 kill_sent True recovered PASS running PASS`；头注逐窗声明在 `reliability.py:27-44`） | exit 0（用例 verdict PASS） |
| P1-2 R4 code 回归 | 持锁下 `case_r4_target_race` 孤立重放 | `BLOCKED_ARCHIVE_NO_PUBLISH` 精确 pin + 源留 + cover 0（任一 BLOCK 即过已消除） | 一致（`verdict PASS code BLOCKED_ARCHIVE_NO_PUBLISH cover 0 source_kept True`） | exit 0 |
| P1-2 N2 code 回归 | 持锁下 `case_n2_canonical_race` 孤立重放 | 同上（G3 预门止于 `NO_PUBLISH`，`converged_claim` 已记） | 一致（`verdict PASS code BLOCKED_ARCHIVE_NO_PUBLISH cover 0 source_kept True`） | exit 0 |
| P1-3 重试 | `_discover_ready(tries=5, sleep=0.1)` 存在 + 套件全切 | 无单发 `_discover` 直进 gate 残留；本轮 11/11 无 `ARCHIVE_UNKNOWN_SOURCE` flake | 一致（`has_discover_ready True`，sig `(data_root, path, profile, tries=5, sleep=0.1)`） | — |
| P1-4 锁交接 | `reboot_equivalent` + `relaunch` 均为 shutdown 后显式 `release` 再 `cold_boot` | 双路径 RUNNING + `true_reboot False` | 一致（`reboot_running PASS relaunch_running PASS reboot_flag True true_reboot False`） | exit 0 |
| FULL 全套件 11/11 | 即 P1-1 套件（仓库内 runner，外置 ctx） | `verdict PASS exit 0 passed 11/11 failed [] running_probe PASS` | 一致（`max 2816 small_only True`；逐用例 `whisper_delta/asr/whisper_calls` 全 0） | suite exit **0** |
| B-坏例 exit | `_fail/_pass` + 好/坏 plist + 真实目录拒写 | FAIL 侧 exit 1；好 plist PASS；坏 plist FAIL problems 7；真实拒写 ValueError | 一致（`fail 1/pass 0/good PASS/bad FAIL problems 7/real_build拒写 True/real_write拒写 True`） | FAIL 侧 exit **1** |
| PLIST 演练 | build→write→validate→load×2→立即 unload→真实快照 | lint 过 + 双可见 + 卸后不可见 + 无残留 + 真实稳定 | 一致（`lint_ok True load1_vis True load2_vis True unload_vis False residue False load/unload rc 0 real_stable True`） | load 0/unload 0 |
| REG 十行 | 外置合成（见下） | 10/10 | 10/10 全 PASS | exit 0 |
| STOP 门 | `py_compile` + 四 rg + 真实快照 + enable 审计 | `py_compile` 过 + banned/SQL/force/enable 四 rg 零命中（rc=1） | 一致（`py_compile OK`；四 rg rc=1） | rg rc=1 |

回归十行：REG-S1 stage1 骨架 prepare→commit→lag→recover COMMITTED whisper 0（PASS）/ REG-S2 持锁双投同 source（PASS）/ REG-S3 stage3 import（PASS）/ REG-S4 stage4 import（PASS）/ REG-S5 `cold_boot` 11 步 RUNNING + shutdown（PASS）/ REG-S6 stage6 import（PASS）/ REG-S7 stage7 import（PASS）/ REG-S8 stage8 import（PASS）/ REG-S9 stage9 import（PASS）/ REG-S10 gate 无 publish 链正确 `BLOCKED_ARCHIVE_NO_PUBLISH`（PASS）。

重跑证据：Runner `fault_suite.run_all`（无锁直调）→ `verdict PASS exit 0 passed 11/11 failed [] running_probe PASS max 2816 small_only True`；`kill9` 真信号 `rc -9`；R4/N2 双 pin `BLOCKED_ARCHIVE_NO_PUBLISH`；最大合成文件 2816B（F-R3；上限 65536；真实长视频零触碰；文本内容不断言）；Whisper 全链 0（套件逐用例 `whisper_delta==0/asr==0/whisper==0` + boot/relaunch/kill9 全 0）；诱饵覆盖恒 0（R4 target cover 0 + N2 decoy cover 0）；`archive_commits` 仅 F-N1 booked +1 路径（首轮已披露，本轮套件 PASS 即延续）；真实 LaunchAgents 前后等；`src/stage1-10/` 零改（本轮 QA 只写本报告本节；git 非仓库口径 N/A 延续 U-5）。

### BUGS（重跑增量；首轮表不动）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（重跑新增业务侧） | — | 否 | 11/11 exit 0；三例必测全过；坏例 FAIL 侧 exit 1 符合预期 | CLOSED | 无需 builder 修 | 无锁直调 + kill9 真信号 + R4/N2 pin 黑盒直跑 |

### Fix Attempt Fingerprint（重跑）

- Task ID: S11-T05 修复后重跑（P1-1~P1-5；code-reviewer 复核节 P1×5 CLOSED 后）
- Root Cause Hypothesis: 不适用（修复版 PASS；复核节归因：P1-1 锁排序/P1-2 归因过弱/P1-3 watcher 竞态/P1-4 不断锁/P1-5 真信号缺失，均已按改法(a)/收敛宣称关闭）
- Approach: 外置独立五目录 + 确定性小文件；无锁直调 `run_all`（P1-1）+ `kill9_child_relaunch` 真信号（P1-5）+ R4/N2 孤立 pin（P1-2）+ `_discover_ready`/锁交接 spot（P1-3/P1-4）+ 全套件 + 坏例只看 exit 码 + plist load→立即 unload + STOP 四 rg + 回归十行
- Files Changed: 仅追加本报告本节；业务代码零改；测试写盘只在 `$TMPDIR/s11rerun-*`（KB 级，交 neat-freak 收尾；首轮 `s11qa-*` 仍待清见 U-4）
- Verification: 套件 `PASS exit 0 11/11 running_probe PASS max 2816`；kill9 `sigkilled True rc -9 recovered/running PASS`；R4/N2 双 `BLOCKED_ARCHIVE_NO_PUBLISH` + cover 0 + 源留；坏例 FAIL 侧 exit 1；plist 双可见→卸后不可见无残留 + 真实稳定；回归 10/10；四 rg rc=1；Whisper 全 0
- Failure Reason: 无 FAIL 项
- Difference From Previous Attempt: 首轮 11/11 PASS 后 builder 按 P1-1~P1-5 返工 3 文件；本轮为修复后重跑，三例必测 + 全套件 + 回归十行全绿

---
目标：Stage11修复后重跑｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
