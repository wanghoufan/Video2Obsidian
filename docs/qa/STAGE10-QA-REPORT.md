# QA-REPORT｜Stage10 S10-T05 验收套件 + §72/§73 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage10/`（verify_archive.py/level_a.py/level_b.py/level_c.py/gate.py/commit.py/__init__.py）+ `src/stage1/2/3/4/5/6/7/8/9` 只读复用（回归探针）
- 计划：`docs/pm/STAGE10-PLAN.md` S10-T05（P0-1~P0-7；happy A/B 各 1 + 异常/边界 8 个 + 三表快照 + 列级 diff；外置合成 Input/Archive 双 Root + 外置 Data Root + 诱饵 Output Root；合成小文件；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage10 子集 8 断言：Same-FS Archive / Cross-FS Level A / O_EXCL Reservation Copy / Cross-FS Mid-copy Kill / Archive Conflict / Unsupported Archive Filesystem Block / Archive 后 `current_path` 更新 / Source Mis-delete=0）+ §73-37/38/39/40/41/42/43/52 + §73-12（Archive 前无条件 Strong SHA256）+ §56/57/58（A/B/C 三级）+ §59/§7（Source 四列更新 + Case 7）+ G3（Publish 重确认 + 用户编辑优先）
- QA 执行目录（仓库外）：`/tmp/s10qa/`（happy_a/happy_ax/happy_b/e_tamper/e_exists/e_levelc/e_midcopy/e_nopub/e_edited/e_idem/e_escape/reg_s2/reg_s5 各独立 data_root + 合成 `clip.bin` 896B + 诱饵 `note.md` + `s10qa_results.json`）+ `/tmp/s10qa_run.py`（仓库外 Runner，`--bad` 八子进程取 exit 码）；仓库内零写盘除本报告
- **结论：PASS（happy A/B 各 1 + Cross-FS 强制分支腿 + 异常/边界 8 个全过 + 回归九行，64/64 断言三轮稳定，Runner exit 0；坏例只看 exit 码：八坏例 exit 1 符合预期；Whisper 恒 0；三表零新增（archive 仅四成功路径各 +1，逐行披露）；`sources` 成功路径恰四列、BLOCK 路径零写；诱饵字节不变；最大合成文件 896B；结论只落本报告）**

## 1. 输入复核（src/stage10 落盘 7 文件，只读消费 + 黑盒调用）

- `verify_archive.py`（S10-T01）：`verify_source_for_archive` 无条件重算 SHA256 + 前后 fstat 对比，`==content_identity` 才放行 else `BLOCKED_SOURCE_CHANGED`（零写库零删文件）；`assert_publish_present` 走 runs→norms→renders→PUBLISHED 链 + 诱饵 canonical 存在性/未编辑双查（无记录 `BLOCKED_ARCHIVE_NO_PUBLISH`，被改 `BLOCKED_ARCHIVE_CANONICAL_EDITED`，缺失 `BLOCKED_ARCHIVE_CANONICAL_MISSING`，覆盖计数恒 0）。QA 实测：篡改夹具（同 size＋同 mtime＋同 inode＋异字节）必 BLOCK 且源保留。
- `level_a.py`（S10-T02）：目标存在即 `BLOCKED_ARCHIVE_EXISTS`（源保留、目标 intact、cover 恒 0）；同盘 `link(2)` 提交＋删源，跨盘目的端 tmp＋`link` 提交＋哈希验＋双删。成功必 `ARCHIVE_COMMITTED` Receipt。QA 实测：Same-FS 真 link 路径成功；跨盘分支同盘强制模拟成功（U-6 声明）。
- `level_b.py`（S10-T03）：Strong Verify → O_EXCL 独占建 Final → PREPARED sidecar → copy → fsync → SHA256 → Receipt → 再验源 → 删源；`recover_midcopy` 无归属 sidecar 直接 `ArchiveRefused`（未知 Final 永不动），PREPARED＋半截截断重拷，PREPARED＋完整 Repair Forward 补 Receipt。QA 实测：注入式 kill（U-7 声明）后源保留、无 Receipt、`archive_commits` 为 0，真 `recover_midcopy` Repair Forward 成功。
- `level_c.py`＋`gate.py`＋`commit.py`（S10-T04）：C 恒 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`（零拷贝零删除，结构上无写删调用）；`gate.archive_source` 装配 verify→G3→目标预检→A/B/C 分流（`capability_override` 仅 QA 定 paths 用，A→B→C 顺序可证），前后缀双 guard（archive 外拒收 `ARCHIVE_PATH_ESCAPE`，input 外拒收）；`commit.commit_archive_success` 为全 Stage 唯一写点（持锁＋Final 双算＋`archive_commits` 插一行＋`sources` 恰四列＋列级自证＋`resolve_current_path` Case 7 演示）。QA 实测：四列外任一被写即回滚（代码内断言，QA 列级 diff 双证）。
- 上轮 builder 计数基线与异常清单：HANDOFF 仍停在 Stage2 CLOSED，未登记 Stage10 builder 自验入口/计数值；`docs/review/` 无 STAGE10 复核报告；QA 按 S10-T05 口径独立合成（896B 确定性 `.bin`＋诱饵 md＋预置 runs→norm→rend→PUBLISHED 链），happy A/B 各 1＋8 异常全覆盖；builder 摆动无——三表预置行数与链关系和 PLAN 一致，未发现口径分叉。

## 2. 用例简表（坏例只看 exit 码；三表=norm/rend/pub；Whisper=真调次数）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 三表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY-A Same-FS Level A | 新 root＋合成源＋PUBLISHED 诱饵链 | gate(A)→commit→resolve | PASS＋Receipt＋源消失＋Final 哈希等＋archive＋1＋恰四列＋双算 | 一致（capability `same device + link commit available`） | Runner exit 0；arch＋1 | 1/1/1→arch＋1 | 0 |
| HAPPY-A-X Cross-FS 分支 | 同上（`_same_device` 强制 False，单盘模拟声明 U-6） | gate(A)→commit | 同 A（receipt `same_device=False`）＋archive＋1 | 一致 | Runner exit 0；arch＋1 | 1/1/1→arch＋1 | 0 |
| HAPPY-B Reservation Copy | 新 root＋合成源＋PUBLISHED 诱饵链 | gate(B)→commit | PASS＋PREPARED/Receipt sidecar＋archive＋1＋恰四列 | 一致 | Runner exit 0；arch＋1 | 1/1/1→arch＋1 | 0 |
| E1 篡改源 BLOCK | 合成源（同 size＋同 mtime＋同 inode＋异字节） | gate(A) | `BLOCKED_SOURCE_CHANGED`＋源保留＋零写 | 一致 | — | 零新增 | 0 |
| E2 目标已存在 BLOCK | Final 预置未知文件 | gate(A) | `BLOCKED_ARCHIVE_EXISTS`＋cover 0＋双 intact＋零写 | 一致 | — | 零新增 | 0 |
| E3 Level C BLOCK | 新链 | gate(C) | `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`＋零触碰＋零写 | 一致 | — | 零新增 | 0 |
| E4 Mid-copy Kill＋Repair Forward | PREPARED＋半截 Final（注入，U-7） | 存在≠完成断言→recover→commit | 源保留＋无 Receipt＋archive 0→Repair Forward Receipt＋archive＋1 | 一致（`prepared_partial_recopy`） | — | 0→arch＋1（仅 commit 后） | 0 |
| E5 无 Publish BLOCK | 无 publish 行链 | gate(A) | `BLOCKED_ARCHIVE_NO_PUBLISH`＋源保留＋零写 | 一致 | — | 零新增 | 0 |
| E6 诱饵被改 BLOCK | 诱饵追加用户编辑 | gate(B) | `BLOCKED_ARCHIVE_CANONICAL_EDITED`＋canonical 零写＋零表写 | 一致 | — | 零新增 | 0 |
| E7 同源重入幂等 | HAPPY 后同 Final | gate 重入＋commit 重入 | `ALREADY_ARCHIVED`＋receipt None＋commit `idempotent_retry`＋archive 仍 1 | 一致 | — | archive 仍 1 | 0 |
| E8 前缀外拒收 | 双腿 | archive 外 Final＋input 外源 | 双 `FAIL`（`ARCHIVE_PATH_ESCAPE`／outside）＋零字节动 | 一致 | — | 零新增 | 0 |
| STOP 门 | 全量输入＋全仓 stage10 | 外置前缀＋最大文件＋Whisper 0＋双 grep＋asr 入口 | 全在 /tmp/s10qa＋max 896B＋banned 零命中＋SQL 逐行披露＋无引擎 import | 一致 | rg rc=1（零命中） | arch 仅四成功＋1 | 0 |
| REG-S1 | 合成门 | probe_volume | ALLOW | 一致 | exit 0 | — | 0 |
| REG-S2 | 新 root | startup＋discover＋AUTO Run 双调 | Source=1＋同 run_id（AUTO Run=1） | 一致 | exit 0 | — | 0 |
| REG-S3 | 合成 2 段 | corr-v1＋para-v1＋双 profile hash | `VIP COIN→Vibe Coding`＋段落非空＋双 64 hex | 一致 | — | — | 0 |
| REG-S4 | happy_a 库 | probe＋gate＋PUBLISHED 重查 | local＋ALLOW＋PUBLISHED 1 行可查 | 一致 | — | — | 0 |
| REG-S5 | 合成 mp4 | iter_video_files＋STARTUP_ORDER＋shutdown | 含 s5clip＋11 步尾 RUNNING＋shutdown dict | 一致 | — | — | 0 |
| REG-S6 | 嵌套 Unicode | resolve＋越界 | `AI/x/DeepSeek V4 test.md`＋`/etc/passwd` 拒收 | 一致 | — | — | 0 |
| REG-S7 | 合成词项 | vocab 快照翻转＋精确词＋language | 快照分歧＋has_exact＋strategy str | 一致 | — | — | 0 |
| REG-S8 | 合成夹具 | plan→to_absolute→merge | 2 chunk 起点 [0.0, 598.0]＋透传＋合并保留 | 一致 | — | — | 0 |
| REG-S9 | 纯层（U-8） | v2 profile/规则序/LLM 拒收/空 ID 拒收 | s9-corr-v2＋RulesError＋DeriveV2Error | 一致 | — | — | 0 |
| B-八坏例 | 各合成前置 | --bad 八子进程 | 期望 BLOCK/错误未吞，exit 1 | 一致（八 exit 1，见§3） | 八 exit **1** | — | 0 |

Runner：`/tmp/s10qa_run.py`（仓库外）→ `/tmp/s10qa/s10qa_results.json`（64 断言 JSON 已落盘，可复算；三轮 `TOTAL 64/64 FAILS=[] exit=0`）；坏例子进程八 exit **1**（判据只用 exit 码，不看打印，直跑复验八 exit 1）；最大合成文件 896B（`clip.bin`，合成小文件门内，真实长视频零触碰）；Whisper 调用全链=0（全部 verdict `whisper_calls==0/asr_calls==0`＋`sys.modules` 无引擎模块）；`archive_commits` 仅 happy_a/happy_ax/happy_b/e_midcopy 各＋1（四行与四源一一对应，见§3）。

## 3. 每用例明细（前置/动作/期望；Count 或 exit 码＋三表＋current_path＋Whisper 0＋外置路径）

- HAPPY-A：前置新 `happy_a/{root,input,archive,decoy}`＋合成源（896B）＋诱饵 md＋预置 runs(QUEUED)→norm→rend→PUBLISHED 链；动作 `probe_archive_capability`（实测 level A，`same device + link commit available`）→ `archive_source(capability_override="A")` → `commit_archive_success` → `resolve_current_path`；期望 PASS＋`ARCHIVE_COMMITTED`、Receipt（`hash_match/source_removed` 真、双 0 调用）、源消失、Final 哈希==原 `content_identity`、PREPARED/Receipt 由 B 独有（A 无 sidecar）、`archive_commits`＋1、三表零新增、runs 仍 QUEUED、`sources` 恰四列（`current_path/location/status/archived_at`，`ARCHIVE/ARCHIVED`）、诱饵不变、Case 7 `exists＋hash_match`；实测全中（12/12）。
- HAPPY-A-X：同前，动作前将 `level_a._same_device` 强制 False（单盘无第二 device，跨盘分支模拟，U-6），完后恢复；期望 receipt `same_device=False`＋其余同 A；实测全中（2/2）。
- HAPPY-B：前置新 `happy_b` 链；动作 gate(B)→commit；期望 PASS＋level B、PREPARED＋Receipt sidecar 双在、Final 哈希等、archive＋1、三表零新增、恰四列；实测全中（5/5）。
- E1：前置新链＋快照；动作同字节篡改（`same_size/same_mtime/same_inode` 全真，exit 码证据见 `--bad tamper` 输出）→ gate(A)；期望 `BLOCKED_SOURCE_CHANGED`（`hash_recomputed` 真）＋源在＋Final 未建＋快照全等＋列 diff 空；实测全中。
- E2：前置新链＋Final 预置 `unknown-owner×64`；动作 gate(A)；期望 `BLOCKED_ARCHIVE_EXISTS`＋`target_cover_count==0`＋源哈希与目标哈希双 intact＋快照全等＋列 diff 空；实测全中。
- E3：前置新链；动作 gate(C)；期望 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`＋源 intact＋Final 未建＋快照全等；另 `verdict_unsupported(... )["target_touched"] is False` 结构性举证；实测全中。
- E4：前置新链；动作手写半截 Final（前半字节）＋PREPARED sidecar（`archive_commit_id_for` 确定性 ID，无 Receipt）→ “存在≠完成”三断言（Final 在＋Receipt 缺＋archive 0）→ `recover_midcopy` → commit(B)；期望 `prepared_partial_recopy` Repair Forward Receipt（`repair_forward` 真）＋源删＋Final 全哈希等＋archive 1＋publish 零新增；实测全中。Kill 为注入式半截（U-7）。
- E5：前置无 publish 行链；动作 gate(A)；期望 `BLOCKED_ARCHIVE_NO_PUBLISH`＋源保留＋快照全等；实测全中。
- E6：前置新链；动作诱饵追加用户编辑行（新哈希≠`published_hash`）→ gate(B)；期望 `BLOCKED_ARCHIVE_CANONICAL_EDITED`＋诱饵哈希==编辑后值（archive 零写）＋源保留＋快照全等；实测全中。
- E7：前置新链走完 happy(A)＋commit；动作同参 gate 重入＋commit 重入；期望 `ALREADY_ARCHIVED`（`idempotent_retry` 真、`receipt` None、零字节动）＋commit 重入 `idempotent_retry` 真＋`archive_commits` 仍 1；实测全中。
- E8：前置新链；动作双腿（`/tmp/s10qa_outside/f.mp4` 落 archive_root 外；`input_root=/tmp/s10qa_elsewhere` 源在外）；期望双 FAIL（`ARCHIVE_PATH_ESCAPE`／outside 源）＋源在＋外路径未建；实测全中。
- B-八坏例（判据只用 exit 码，直跑复验一致）：`tamper exit 1=BLOCKED_SOURCE_CHANGED（same_size/mtime/inode 全真）`＋`exists exit 1=BLOCKED_ARCHIVE_EXISTS（源留＋目标 intact）`＋`levelc exit 1=BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM（源 intact＋Final 未建）`＋`midkill exit 1=注入 kill 中断（源留＋PREPARED 在＋Receipt 缺＋archive 0）`＋`nopub exit 1=BLOCKED_ARCHIVE_NO_PUBLISH`＋`edited exit 1=BLOCKED_ARCHIVE_CANONICAL_EDITED（canonical_writes=0）`＋`escape exit 1=双 FAIL`＋`noreceipt exit 1=无 Receipt 拒写（archive 0）`；任一吞错即非 1 项未触发。
- STOP 外置/冻结：输入全在 `/tmp/s10qa/*/…`（与真实视频目录/真实 Obsidian 库/真实 Archive 目录无交集，外路径断言＋残留仅 /tmp/s10qa 2.9M）；最大合成文件 896B；Whisper 全链=0（全 verdict 双 0＋`sys.modules` 无 `mlx_whisper/faster_whisper/whisper/openai_whisper`）；PLAN 原 rg（`run_asr_single_file|launchagent|menu|golden|cer|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber`）`src/stage10/` 零命中（rg rc=1）；SQL 逐行披露：`sqlite3/INSERT/UPDATE/DELETE` 命中仅 `commit.py`（`INSERT INTO archive_commits` 一行＋`UPDATE sources SET current_path…` 四列一行＋SELECT 只读），其余五文件含 SELECT 只读或零命中；`run_asr_single_file` 六文件零命中；`git diff` 口径 N/A（U-5）。
- 回归：REG-S1 `probe_volume→ALLOW`；REG-S2 `instance.startup`＋`discover`（Source=1）＋`get_or_create_auto_run` 双调同 ID（AUTO Run=1）；REG-S3 `corr-v1` 纠正＋`para-v1` 分段＋双 profile 64 hex；REG-S4 decoy 盘 local＋`gate_output_root` ALLOW＋happy_a 库 PUBLISHED 1 行可查；REG-S5 `iter_video_files` 含合成 mp4＋`STARTUP_ORDER` 11 步尾 RUNNING＋`shutdown(None)` dict（live watcher 未起，U-9）；REG-S6 嵌套 `AI/x/DeepSeek V4 test.mp4→…md`＋`/etc/passwd` 拒收；REG-S7 vocab 快照一字节翻转分歧＋精确词＋`get_language_strategy` str；REG-S8 `plan_chunks(601)` 2 chunk 起点 [0.0, 598.0]＋`to_absolute` 透传＋`merge_chunks` 保留；REG-S9 v2 纯层（`s9-corr-v2`＋长改写 `RulesError`＋空 ID `DeriveV2Error`＋规则序 dict，全链 Case4/5 由 Stage9 套件覆盖，U-8）；`src/stage1-9/` 本轮 QA 未触碰。

## 4. §72 子集门（Stage10 8 断言逐项）＋ §73 联动

- [x] Same-FS Archive（HAPPY-A 真 link 路径：源消失＋Final 哈希等＋Receipt；`happy_a.bytes_moved/receipt`）
- [x] Cross-FS Level A（HAPPY-A-X 强制分支模拟：`same_device=False`＋同断言集；U-6）
- [x] O_EXCL Reservation Copy（HAPPY-B：独占建 Final＋PREPARED＋Receipt＋双 sidecar；`happy_b.sidecars`）
- [x] Cross-FS Mid-copy Kill（E4：存在≠完成三断言＋`prepared_partial_recopy` Repair Forward；注入式半截，U-7）
- [x] Archive Conflict（E2：`BLOCKED_ARCHIVE_EXISTS`＋cover 0＋双 intact；`e2.no_cover_no_loss`）
- [x] Unsupported Archive Filesystem Block（E3：C 恒 BLOCK＋零触碰；`e3.zero_touch/levelc_pure`）
- [x] Archive 后 `current_path` 更新（HAPPY-A/B：恰四列＋双算＋Case 7 `resolve_current_path`；`happy_a.case7_reprocess`）
- [x] Source Mis-delete=0（E1/E2/E3/E5/E6/E8 全部 BLOCK 路径源哈希不变；`e*_source_kept/zero_touch`）
- §73 联动：37→HAPPY-A/A-X；38→HAPPY-B；39→E3；40→E4；41→E2（Overwrite=0）＋E6（覆盖 0）；42＋12→E1（无条件重算，不认 size/mtime）；43→HAPPY 四列＋Case 7；52→E5/E6（G3 双腿）。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | 64/64 三轮 exit 0；八坏例 exit 1 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s10qa/s10qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S10-T05 Stage10 验收套件＋§72/§73 子集门＋Stage1~9 回归（首轮 QA 执行，Runner 修 2 次，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；2 处均为 Runner 自身问题：①`merge_chunks` 手造 chunk 缺 `index/core_*` 键（业务校验正确，改用 `plan_chunks(601)` 真 plan 项后一致）；②`setup_chain` 跨进程重跑撞 UNIQUE（首轮 suite 内自洽，`--bad` 直跑复验时旧行残留致 exit 2，加 tag 级 `rmtree` 幂等后八 exit 1））
- Approach: 仓库外 `/tmp/s10qa` 各用例独立 data_root＋确定性 896B 合成源＋诱饵 md＋预置 runs→norm→rend→PUBLISHED 链；Count/行数/SQLite 直查为正常路径判据；篡改/冲突/C/无发布/被改/越界/无 Receipt 走 `gate/level/commit` 真路径（BLOCK/FAIL 断言）＋`--bad` 八子进程只看 exit 码；mid-copy 注入半截＋真 `recover_midcopy`；三表快照＋archive 成功路径＋1逐行披露＋`sources` 列级 diff＋诱饵不变；回归 S1 门/S2 链/S3 冻结/S4 探针＋PUBLISHED 重查/S5 文件＋常量/S6 映射＋越界/S7 纯层/S8 planner-timeline-merge/S9 v2 纯层
- Files Changed: 仅新增本报告 `docs/qa/STAGE10-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s10qa`（H2 外置目录约束延续）；Runner `/tmp/s10qa_run.py` 在仓库外
- Verification: 三轮 `TOTAL 64/64 FAILS=[] exit=0`（`s10qa_results.json` 可复算，`max_synth_bytes=896/whisper_modules=[]`）；八坏例 exit 1 已取（suite 内断言＋直跑复验双证）；happy 三链＋E4 archive 各＋1（四行与四源一一对应，其余用例 archive 0）；诱饵/真实库零触碰；`src/stage1-10/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）；Runner 首轮 2 项系形状/幂等，修 Runner 后 64/64（`--bad` 子进程同修）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 Runner 修 2 次：merge 用真 plan 1 处＋tag 级清理 1 处）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 896B；跨盘/长时语义只用合成小文件＋分支模拟证明）。
- U-2 文本/ASR 内容不断言词准确率（PLAN 已定：Golden/CER 属 Stage11+；本报告仅验哈希/计数/ verdict/列 diff）。
- U-3 Runner 在仓库外（`/tmp/s10qa_run.py`＋`--bad` 八子进程＋`s10qa_results.json`），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage9 U-3 同 Pattern）。
- U-4 残留待清：`/tmp/s10qa`（本轮新增，2.9M：11 链 data_root＋input＋archive＋decoy）＋更早 Stage 残留（Stage9 U-4 所列），交 neat-freak 收尾。
- U-5 `src/stage1-9/ git diff 为空`口径 N/A（当前目录非 git 仓库；以九回归 PASS＋QA 零改代证，未改业务代码；同 Stage9 U-5 Pattern）。
- U-6 Cross-FS Level A 为同盘强制分支模拟（本机单盘无第二 device；`_same_device` 强制 False 走真跨盘代码径，Same-FS 为真 link 路径；若需真双盘，挂第二卷重跑 HAPPY-A-X 即可）。
- U-7 Mid-copy Kill 为注入式半截（手写半截 Final＋PREPARED sidecar，非 SIGKILL 真杀；kill 后状态＋真 `recover_midcopy`＋真 commit 全链实测；另 `--bad midkill` 用真 `on_chunk` 注入中断举证源保留）。
- U-8 REG-S9 为纯层回归（v2 profile/规则序/拒收三件；全链 Case4/5 派生由 Stage9 套件覆盖，本轮不重跑长链）。
- U-9 REG-S5 未起 live watcher/worker 线程（验文件发现＋`STARTUP_ORDER` 常量＋`shutdown` 幂等，语义不断链；同 Stage9 U-7 Pattern）。
- U-10 HANDOFF 滞后：根 HANDOFF 仍停在 Stage2 CLOSED，未登记 Stage10 builder 计数基线与异常清单；本报告输入复核以 `src/stage10/` 落盘 7 文件＋PLAN S10-T05 为准，基线缺失不卡 QA（已独立覆盖）。

---
目标：Stage10验收S10-T05｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
