# PLAN｜Stage 10 Archive Level A/B/C + Source current_path update（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage9 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + 确定性 Correction 冻结版规则表 + 版本化定值 Paragraph（§47 规则序） + `src/stage4/` Initial Canonical Publish + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING + `src/stage6/` Path Mirror + Unicode/Case 矩阵 + `src/stage7/` Vocabulary/PromptBuilder/Language Strategy + 单文件接线 + `src/stage8/` VAD advisory + ChunkPlanner（10min/2s）+ Absolute Timeline + Overlap Merge + `src/stage9/` 新版 Correction 规则表 + 新版 Paragraph formatter + Case 4/5/6 延续；Archive A/B/C + `current_path` 更新 + Archive 前 Strong Verify（§26）+ G3 落地均未实现，`archive_commits` 至今零行，`sources.current_path/status/archived_at` 至今零写）。
> Stage1~Stage9 冻结输入：`src/stage1/`（`run_asr_single_file` 单文件直转 + 冻结常量 `FROZEN_*` + word 默认 OFF + nst 0.6 + temp-wav 16k mono + `recovery.py` Repair Forward 语义，只读复用）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `asr_profile_hash` 身份 + `store.py` 中央库 DDL + `archive_commits` 空表 schema，只读复用）与 `src/stage3/`（`normalize`/`render`/`derive`/`lineage` 公开 API + 冻结版 Correction 规则表，只读复用）与 `src/stage4/`（`initial_publish` + `publish_commit` + `conflict.publish_or_block` + `volume_probe.gate_output_root`，只读复用不复制）与 `src/stage5/`（三路发现语义，只读复用）与 `src/stage6/`（`resolve_canonical` 纯映射，只读复用）与 `src/stage7/`（vocabulary/prompt/language，只读复用不复制）与 `src/stage8/`（VAD/Chunk/Timeline/Merge，只读复用不复制）与 `src/stage9/`（`rules_v2`/`formatter_v2`/`derive_v2`，只读复用不复制）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/`、`src/stage9/` 任一文件（改了即 FAIL；新增只进 `src/stage10/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage10 only）`——本 Stage 只实现 §69 Stage10 定义的事项（Archive Level A/B/C + Source `current_path` update，§56/§57/§58 + §59/§7 + §26 Archive 前 Mandatory Strong Verification 本 Stage 实现 + G3 本 Stage 落地：Crash Recovery 后、Archive 前重确认 Publish 存在且用户编辑优先 + §3.12 Archive Target Overwrite=0 + §3.13 Source 不确定保留 + §70 Case 7/Case 10 + §72 Archive 子集 + §73-37/38/39/40/41/42/43/52），Stage11+（LaunchAgent + 完整 Fault Injection Suite + Golden Dataset/CER/词准确率 + 20 Video Batch、Menu Bar）一律 Out，写了即 FAIL；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；Archive 永不覆盖未知目标（出现 `force|overwrite|clobber` 即 FAIL）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“源视频安全归档”的那一块：在 Stage4 已 PUBLISHED 的 Canonical（诱饵 Output Root 内）与 Stage1 Recovery 语义之上，Archive 前无条件 Strong Verify（§26，本 Stage 实现）→ Capability 分流（Level A Atomic No-Clobber / Level B O_EXCL Reservation Copy / Level C 正确 Block，§56/57/58）→ G3 收口（Crash Recovery 后、Archive 前重确认 Publish 记录存在，且用户已编辑 Markdown 覆盖恒为 0）→ 成功后更新 Source（`current_path=archive_final_path` + `current_location_type=ARCHIVE` + `status=ARCHIVED` + `archived_at=now`，§59/§7；未来 Reprocess 从 `current_path` 解析）→ 全程 Whisper 调用恒为 0、Raw/Normalized/Rendered/Canonical 诱饵字节不变（Archive 只动源视频副本，不碰笔记内容）→ `archive_commits` 为本 Stage 唯一允许新增行的表 → Stage1~9 回归（`src/stage1-9/` diff 为空）。

## Current Stage

- Stage ID: Stage 10 — Archive Level A/B/C + Source current_path update（V1.8 §69）
- Goal: §26 Strong Verify 本 Stage 实现（重算 Source SHA256 + 前后 fstat 对比，不符进 `BLOCKED_SOURCE_CHANGED`）→ Level A（Same-FS + Cross-FS Atomic No-Clobber，§56）可证明 → Level B（O_EXCL Reservation Copy + 双 Strong Verify + `ARCHIVE_COMMITTED` Receipt + Mid-copy Kill 不丢 Source，§57/Case 10）可证明 → Level C（无可靠 Exclusive Create 即 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`，§58）可证明 → G3 落地（Recovery 后、Archive 前重确认 Publish PUBLISHED 存在 + 用户编辑覆盖恒 0）可证明 → Archive Conflict/Target Overwrite=0（§3.12/§3.13）可证明 → 成功后 Source 四列更新 + `archive_commits` 行 + 未来 Reprocess 解析（Case 7，§59/§7）可证明 → §72 Archive 子集 + §73-37~43/52 可证明 → Stage1~9 回归（`src/stage1-9/` diff 为空）。

Stage1~Stage9 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（回归只读查）：verify/post_verify 强校验语义 +
  recovery Repair Forward 语义（本 Stage 不转写，不调用
  run_asr_single_file；调用即 FAIL；Stage10 自有 crash 路径复用其
  Truth Model：Filesystem Valid + Expected Hash = Truth，SQLite 落后
  Repair Forward，不重跑 Whisper）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现
  入口）/ runs.get_or_create_auto_run（AUTO UPSERT；本 Stage 不新建 Run；
  Run 状态被推进/回滚即 FAIL）/ store.open_db 持锁断言 / store DDL
  （archive_commits schema 沿用；本 Stage 是首个允许写该表的 Stage，
  其余三表 normalization_revisions/render_revisions/publish_records
  零新增写）/ instance 单实例锁（Archive 写库前必须持锁）
src/stage3/ 零调用（本 Stage 不派生 Revision；回归只读查）
src/stage4/ 只读复用（import，不复制不修改）：publish_records 查询
  （G3 重确认 Publish 存在，只读查）/ conflict 用户编辑优先语义
  （只读复用判断，不复制覆盖逻辑）/ volume_probe.gate 语义
  （Capability 判定只读复用，不重写 Probe；Output Root 仍为诱饵，
  Archive Root 为外置合成 Archive Root）
src/stage5/ 零调用（本 Stage 不起 Watcher/Scan/Reconcile；回归语义不断链）
src/stage6/ 零调用（本 Stage 不做路径映射；回归双算不断链；
  source_relative_path 只读消费，不重算 mirror）
src/stage7/ 零调用（本 Stage 不动 prompt/vocab；回归不断链）
src/stage8/ 零调用（本 Stage 不重切分、不重排时间线；回归不断链）
src/stage9/ 零调用（本 Stage 不换规则/格式；回归不断链）
src/stage10/ 新增：verify_archive.py（§26 Strong Verify + fstat 对比）/
  level_a.py（Atomic No-Clobber）/ level_b.py（Reservation Copy +
  Mid-copy Recovery）/ level_c.py（Unsupported Block）/
  gate.py（Capability 分流 + G3 预门装配）/ commit.py（archive_commits
  行 + Source 四列更新）（命名以实现为准，前缀恒为 stage10，
  禁止 stage11+ 关键词文件名如 launchagent/menu/golden/faultsuite）
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage10 写库仅经
  中央库公开语义：archive_commits 允许新增行 + sources 仅四列
  （current_path/current_location_type/status/archived_at）允许更新，
  其余列（content_identity/path_identity_key/logical_source_identity/
  size/mtime/device/inode）任一被写即 FAIL；
  normalization_revisions/render_revisions/publish_records 零新增写；
  processing_runs 状态零推进零回滚）
输入源视频：外置合成小文件（仓库外独立合成 Input Root；ffmpeg 本地
  合成秒级 mp4/wav，不扫真实视频目录；长视频不测，用例最大文件 ≤
  合成小文件；文本/ASR 内容不断言，词准确率属 Golden，Stage11+）
诱饵 canonical：外置合成目录内诱饵 md（G3 重确认 Publish 存在只查
  publish_records + 诱饵文件存在性/哈希比对，不碰真实笔记；Archive
  全程 canonical 诱饵字节不变）
Archive 输出：外置合成 Archive Root（仓库外独立目录；Same-FS 与
  Cross-FS 用两个合成 Root 证明；真实视频目录/真实 Obsidian 库/
  真实 Archive 目录零触碰）
Stage10 Whisper 调用：全程恒为 0（Archive 不转写；出现任何
  run_asr_single_file import/调用即 FAIL）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Archive 前 Strong Verify 可证明（§26 + G2 + §73-12/42）：进入 `VERIFYING_SOURCE_FOR_ARCHIVE` 后无条件重算 Source SHA256（不许只依赖 size/mtime）+ 前后 fstat 对比（device/inode/size/mtime_ns，防 Case 8 Same size + same mtime + different bytes）→ `current_source_sha256 == source.content_identity` 才放行，否则 `BLOCKED_SOURCE_CHANGED` 且 Raw 不 Commit、不 Publish、不 Archive、不删源；合成篡改夹具（同 size+同 mtime+异字节）必 BLOCK 且 Source 保留。
- [ ] P0-2 Level A Atomic No-Clobber 可证明（§56 + §73-37）：Capability 支持 `RENAME_EXCL` 或等价时走原子归档 → Same-FS 合成源→合成 Archive Root 成功（源消失、目标字节与哈希一致、`ARCHIVE_COMMITTED` Receipt）→ Cross-FS Level A 成功（外置双 Root 跨盘语义，仍原子不覆盖）→ 目标已存在未知文件时不覆盖（Overwrite=0，§3.12，进 `BLOCKED_ARCHIVE_EXISTS/CONFLICT`，源保留）。
- [ ] P0-3 Level B Reservation Copy + Mid-copy Crash 可证明（§57 + Case 10 + §73-38/40）：无 Atomic Exclusive Rename 但有 `O_EXCL` 时走 `Strong Verify → O_EXCL 独占创建 Final → Ownership/PREPARED 持久化 → copy → flush/fsync → SHA256 → ARCHIVE_COMMITTED → 再次 Strong Verify → 删源` 全序 → Mid-copy kill 后 Source 完整保留（未知 Final 不删源，§3.13）→ Ownership 明确时可安全 Repair Forward（复用 Stage1 Truth Model，不重跑 Whisper=0）→ 文件存在≠完成（无 Receipt 不视为成功）。
- [ ] P0-4 Level C 正确 Block + Conflict/Overwrite=0 + G3 落地可证明（§58 + §3.12/§3.13 + G3 + §73-39/41/52）：无可靠 Exclusive Create/No-Clobber 时进 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`（源保留，不删不拷）→ Archive 目标冲突一律 BLOCK（`BLOCKED_ARCHIVE_EXISTS/CONFLICT`，Target Overwrite=0）→ G3 预门：Crash Recovery 后、Archive 前重确认 Publish 记录存在（`publish_records` 对应 render PUBLISHED 可查，无记录即 BLOCK）且用户已编辑 Markdown 覆盖恒为 0（诱饵 canonical 被改即 BLOCK 不覆盖，§50/§51/§53 延续）→ Source Mis-delete=0（任一 BLOCK 路径源字节仍在且哈希不变）。
- [ ] P0-5 Archive 成功后 Source 更新可证明（§59/§7 + Case 7 + §73-43）：仅成功路径写四列（`sources.current_path=archive_final_path` + `current_location_type=ARCHIVE` + `status=ARCHIVED` + `archived_at=now`，列级 diff 举证其余列零写）+ `archive_commits` 新增一行（`ARCHIVE_COMMITTED`，字段完备）→ `current_path` 指向真实 Archive Final（双算一致：DB 值==磁盘真实路径，`os.path.isfile` + 哈希一致）→ 未来 Reprocess 可从 `current_path` 解析真实位置（读盘演示，不实现 Reprocess UI）。
- [ ] P0-6 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/`、`src/stage9/` git diff 为空；`normalization_revisions`/`render_revisions`/`publish_records` 零新增写（有新增即 FAIL；快照对比举证）；`processing_runs` 状态零推进零回滚；Stage10 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`）、LaunchAgent、Menu Bar、Golden/CER、LLM/云/SDK（`rg "run_asr_single_file|launchagent|menu|golden|cer|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage10/` 零命中举证）；直写 DB 仅经中央库语义并逐行披露（`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage10/` 命中必须逐行对应 archive_commits/四列更新并披露，无多余写）；`sources` 四列之外任一被写即 FAIL。
- [ ] P0-7 外置合成验收门可证明（TM 已定）：一切输入位于外置合成目录 + 外置 Data Root + 外置合成 Archive Root 内（验收前断言，与真实视频目录/真实 Obsidian 库/真实 Archive 目录无交集）；异常路径一律合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“存在且不变”，零触碰真实笔记）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告；长时语义不用长音频证明）；任一用例触碰真实目录/发起云调用即 FAIL。

## In Scope

- Archive 前 Mandatory Strong Verification（§26 本 Stage 实现：无条件重算 SHA256 + 前后 fstat 对比 + `BLOCKED_SOURCE_CHANGED`；G2 约束本 Stage 落地）。
- Archive Level A（§56：Same-FS + Cross-FS Atomic No-Clobber Finalization；目标存在不覆盖）。
- Archive Level B（§57：O_EXCL Reservation Copy 全序 + PREPARED/Ownership 持久化 + 双 Verify + `ARCHIVE_COMMITTED` Receipt + Mid-copy Kill 保留源 + Ownership 明确可 Repair Forward）。
- Archive Level C（§58：无可靠 Exclusive 能力即 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`，源保留）。
- G3 落地（Crash Recovery 后、Archive 前重确认 Publish 存在且用户编辑优先：无 PUBLISHED 记录即 BLOCK；诱饵 canonical 被改即 BLOCK 不覆盖；覆盖计数恒 0）。
- Archive 成功后 Source 更新（§59/§7：四列更新 + `archive_commits` 行 + `current_path` 指向真实 Archive + 未来 Reprocess 可解析演示）。
- Archive Conflict/Target Overwrite=0 + Source 不确定保留（§3.12/§3.13：`BLOCKED_ARCHIVE_EXISTS/CONFLICT` + 未知 Final 不删源）。
- §72 Implementation Acceptance Gate 中仅属于 Stage10 的断言子集：Same-FS Archive / Cross-FS Level A / O_EXCL Reservation Copy / Cross-FS Mid-copy Kill / Archive Conflict / Unsupported Archive Filesystem Block / Archive 后 `current_path` 更新 / Source Mis-delete=0。
- §73-37/38/39/40/41/42/43/52 + §73-12 联动（Archive 前无条件 Strong SHA256）。
- Stage1~9 回归（九回归不断链；`src/stage1-9/` diff 为空）。

## Out of Scope

- Stage11 全部：LaunchAgent（Cold Boot/Absolute Binary Paths/开机常驻）+ 完整 Fault Injection Suite（本 Stage 只做 Archive-scoped 的 Mid-copy Kill + 篡改/冲突单测，不做 20 Video Batch/Lost Job/Single Instance 重测/Golden/CER 全套件）+ Golden Dataset/词准确率/幻觉指标（本 Stage 文本内容不断言）。
- Stage12 全部：Menu Bar。
- 转写/派生/发布语义升级（Whisper/Normalization/Paragraph/Publish 只读复用或零调用；Stage10 Whisper 恒 0；`publish_records` 零新增写；为归档改 stage1-9 原文即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- Replace Policy（后续派生自动覆盖 canonical，不属 V1.8 §51；G3 只做 BLOCK 不覆盖，不做自动合并）。
- 永久删除 Archive（§60 默认 never，本 Stage 不删 Archive，只删已归档的 Input Source 成功路径）。
- 真实长视频测试与真实目录扫描/写入/真实 Obsidian 库/真实 Archive 目录触碰（用户明确：真实长视频一律不测直到产品完成；测试一律指向合成 Input Root + 外置 Data Root + 合成 Archive Root + 诱饵 Output Root；canonical 只用诱饵文件）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/`、`src/stage9/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S10-T01 Archive 前 Strong Verify + G3 预门（§26/G2/G3） | P0 | builder | TODO | 输入：stage2 `store/sources` 只读语义 + stage1 `verify/post_verify` 强校验语义（只读复用，不复制 mechanics）+ §26/§24-25 + G2/G3。输出：`src/stage10/verify_archive.py`（`verify_source_for_archive(source_id, con)`：无条件重算 Source SHA256 + 前后 fstat 对比 + `==content_identity` 放行 else `BLOCKED_SOURCE_CHANGED`；`assert_publish_present(source_id, con)`：查 `publish_records` PUBLISHED 存在性 + 诱饵 canonical 存在性，无即 BLOCK；用户编辑优先判断 helper：诱饵 canonical 哈希偏离 published_hash 即 BLOCK 不覆盖）。验收：合成源篡改夹具（同 size+同 mtime+异字节）必 BLOCK 且源保留 + Whisper 0 + 三表零新增（archive 恒 0，本 Task 不写 archive）+ `sources` 零写证据。禁动 `src/stage1-9/`；禁 Whisper/Archive 写/LaunchAgent/Menu/LLM。 |
| S10-T02 Level A Atomic No-Clobber（§56） | P0 | builder | TODO | 输入：S10-T01 的 verify 放行语义（只读装配）+ stage4 `volume_probe` Capability 只读复用 + 外置合成 Input/Archive 双 Root。输出：`src/stage10/level_a.py`（`archive_level_a(source_path, archive_final_path)`：Capability 命中 A 才进；same-directory tmp 不用（源文件整体搬），原子 `rename` No-Clobber 提交 + Final SHA256 + `ARCHIVE_COMMITTED` Receipt 数据）。验收：Same-FS 成功（源消失、目标哈希==源原哈希）+ Cross-FS Level A 成功（双 Root）+ 目标已存在未知文件 BLOCK 且源保留（Overwrite=0）+ 全程 Whisper 0 + `sources` 零写（本 Task 不写 Source，更新留 S10-T04）。禁动 `src/stage1-9/`；禁 O_EXCL 降级混入 A 路径。 |
| S10-T03 Level B Reservation Copy + Mid-copy Crash（§57/Case 10） | P0 | builder | TODO | 输入：S10-T01 verify + S10-T02 Receipt 约定 + Stage1 `recovery` Truth Model（只读复用语义）。输出：`src/stage10/level_b.py`（`archive_level_b(...)` 全序：Strong Verify → O_EXCL 独占创建 Final → Ownership/PREPARED 持久化 → copy → flush/fsync → SHA256 → `ARCHIVE_COMMITTED` → 再次 Strong Verify → 删源；`recover_midcopy(...)`：PREPARED + Final 缺失/半截（hash≠expected）→ 保留源 + 可重入；PREPARED + Final 完整且 hash==expected → Repair Forward 补 Receipt）。验收：Reservation Copy 成功 + Mid-copy kill（copy 半截注入）源完整保留且 Final 未被视为成功 + Ownership 明确重入 Repair Forward 成功 + Whisper 0 + `sources` 零写。禁动 `src/stage1-9/`；禁把 B 写成覆盖式拷贝。 |
| S10-T04 Level C Block + Conflict 收口 + Source 更新（§58/§59/§7/G3） | P0 | builder | TODO | 输入：S10-T01–T03 + `gate.py` Capability 分流（A→B→C 顺序，C 为终态 BLOCK）+ stage2 中央库写语义。输出：`src/stage10/level_c.py`（无可靠 Exclusive 即 `BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM`，零拷贝零删除）+ `src/stage10/gate.py`（Capability 分流 + G3 预门装配：verify→publish 重确认→用户编辑优先→A/B/C）+ `src/stage10/commit.py`（成功路径唯一写点：`archive_commits` 新增一行 + `sources` 四列更新 current_path/location/status/archived_at，列级 diff 自证其余列零写 + `current_path` 真实性双算）。验收：Level C 必 BLOCK 且源保留 + 冲突目标 BLOCK（Overwrite=0）+ 无 Publish 记录 BLOCK + 诱饵被改 BLOCK（覆盖 0）+ 成功路径四列更新 + `current_path==磁盘真实 Final` + 未来 Reprocess 读盘演示 + Whisper 0。禁动 `src/stage1-9/`；禁四列之外写；禁 LaunchAgent/Menu/Golden。 |
| S10-T05 Stage10 验收套件 + §72/§73 子集门 + Stage1~9 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S10-T01–T04 产物 + `src/stage1-9/` 只读复用。输出：Stage10 验收报告（happy 链 1 遍：合成源→discover→PUBLISHED 诱饵（经 stage4 只读语义预置，不新写 publish）→Strong Verify→Level A（Same-FS）→四列更新→`current_path` 双算 + Level B 路径 happy 1 遍 + 异常/边界至少 8 个：篡改源 BLOCK（Case 8 延续）/ 目标已存在 BLOCK / Level C BLOCK / Mid-copy Kill 源保留 + Repair Forward / 无 Publish 记录 BLOCK / 诱饵被改 BLOCK（覆盖 0）/ 同源重入 Archive 幂等或复用证据 / 双 Root 前缀外路径拒收；每个用例：前置/动作/期望 verdict 或 exit 码/Whisper 0 证据/三表快照（norm/render/publish 零新增，archive 只许成功路径新增并逐行披露）证据/`sources` 列级 diff 证据/诱饵 md 不变证据/最大文件 ≤ 合成小文件声明/外置三 Root 路径证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归九行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 冻结版规则链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；Stage7 装配→接线→profile executed 仍 PASS；Stage8 合成 wav→VAD→planner→timeline→merge 仍 PASS；Stage9 Case 4/5 派生仍 PASS（Whisper 0/Raw 同/诱饵不变）；`src/stage1-9/` git diff 为空）。验收：任一异常缺失、计数偏离、archive 非预期新增、四列之外被写、有转写/发布越权写、诱饵被改、真实目录/真实库/真实 Archive/云/长视频被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S10-T01 → T02 → T03 → T04 → T05 严格串行（Verify 放行是 A/B 的前置；Receipt 约定是 B Recovery 的前置；A/B/C 全就绪才是 Gate 分流与 Source 更新的前置；验收在四件未就绪前跑无收口可查）。
- 角色说明：S10-T01–T04 = builder 实现；S10-T05 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 Strong Verify“顺手”用 size/mtime 快捷放行：最省事但违反 §26 无条件重算。缓解：S10-T01 硬门——篡改夹具（同 size+同 mtime+异字节）必 BLOCK + fstat 对比双证据 + grep 快捷路径审计。
- R2 Level A“顺手”覆盖目标：rename 最省事但违反 §3.12 Overwrite=0。缓解：S10-T02 硬门——目标存在必 BLOCK + 源保留 + No-Clobber 原子语义断言。
- R3 Level B 把半截文件当成功：存在即成功最省事但违反 §57 Receipt 语义。缓解：S10-T03 硬门——无 Receipt 不成功 + Mid-copy Kill 源保留 + hash≠expected 不可删源 + Repair Forward 复跑。
- R4 G3 被跳过直归档：Publish 重确认最易省，但违反用户编辑优先。缓解：S10-T01/S10-T04 双硬门——无 PUBLISHED 记录 BLOCK + 诱饵被改 BLOCK + 覆盖计数恒 0。
- R5 Source 更新多写列：顺手刷 size/mtime 最易但破坏 provenance。缓解：S10-T04 硬门——四列白名单 + 列级 diff + 其余列零写断言。
- R6 为归档改 stage1-9 原文：改冻结常量/改 publish 语义最省事但违反加法约束。缓解：S10-T05 回归硬门——`src/stage1-9/` git diff 为空 + stage4 语义只读复用审计。
- R7 真实长视频/真实目录误测：拿真实课程长视频验归档最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件 + 合成副本；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成 Input Root + 独立合成 Archive Root + 独立诱饵 Output Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“存在且不变”，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件，长时语义不用长音频证明，词准确率/Golden 属 Stage11+）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` + `src/stage6/` + `src/stage7/` + `src/stage8/` + `src/stage9/` 只读加法（新增只进 `src/stage10/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage11+ 禁入：LaunchAgent + 完整 Fault Injection Suite + Golden/CER + 20 Video Batch、Menu Bar 一律 Out；Archive 前 Strong Verify §26 本 Stage 实现；G3 本 Stage 落地：Crash Recovery 后、Archive 前重确认 Publish 存在且用户编辑优先；归档三级 A/B/C 语义按基线 §56/57/58，成功后四列更新按 §59/§7）。
