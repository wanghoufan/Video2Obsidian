# PLAN｜Stage 2 Candidate / Source / Processing Run + AUTO Run Partial UNIQUE + SQLite + Single Instance（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1 CLOSED（HANDOFF 2026-09-11 01:10，supervisor终检PASS，P0-1~P0-9全可证明）。
> Stage1 冻结输入：`src/stage1/` 8文件（ingest/verify/asr/post_verify/prepare/commit/recovery/__init__，job-scoped `data/jobs/<job_id>/` + per-job `job.sqlite` + Raw PREPARE/COMMIT + Repair Forward）——本 Stage 只做加法，不改 `src/stage1/` 任一文件（改了即 FAIL）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage2 only）`——本 Stage 只实现 §69 Stage2 定义的事项，Stage3+ 一律打回。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中数据地基的第二块：在 Stage1 单视频 Raw 可证明闭环之上，建立 Candidate→Source→Processing Run 的 Exactly Once 身份链 + 中央 SQLite + Single Instance，为后续 Stage 提供可信身份与并发地基（不产生任何转写/改写/发布行为）。

## Current Stage

- Stage ID: Stage2 — Candidate / Source / Processing Run + AUTO Run Partial UNIQUE + SQLite + Single Instance（V1.8 §69）
- Goal: 直接 API 发现（不实现 Watch/Scan/Reconcile 真实监听）→ Candidate 生命周期（§5）+ Provisional Identity 活跃期 Partial UNIQUE（§20）→ Stable File 门（§5）→ Strong SHA256 promotion → Logical Source Exactly Once（§3.2/§21/§22，Case 13 历史碰撞产生新 Source）→ AUTO Processing Run Identity（§13）+ Partial UNIQUE + Conflict-safe UPSERT（§15，禁 SELECT-then-INSERT）→ 两层去重（§19：Candidate 层 + AUTO Run 层，Case 2/Case 3 Count=1，§17 重试原 Run，§18 NO_SPEECH 不新增）→ 中央 SQLite 全表 DDL（§31-35，Stage3+ 表只建 schema 零写入）→ Single Instance（§64，`fcntl.flock LOCK_EX|LOCK_NB`，第二实例直接退出）+ Startup Ordering 子集（§62：Static Preflight→Lock→Open SQLite→Volume Preflight→Recovery Bootstrap；不启动 Watcher/Scan/Workers）。

Stage1 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import，不复制不修改）：fstat_capture / sha256_file /
probe_volume（§3.14）/ per-job namespace 语义（§36）
src/stage2/ 新增：candidate.py / source.py / runs.py / store.py（中央 SQLite）/ instance.py（Single Instance）
中央库位置：<data_root>/data/state.db（与 data/jobs/<job_id>/ 同级；per-job job.sqlite 原地不动，不回写）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照）

- [ ] P0-1 中央 SQLite 落盘可用：`<data_root>/data/state.db` 创建 §31-35 全表 DDL（含 `discovery_candidates/sources/processing_runs/artifacts/state_events` 全字段 + `normalization_revisions/render_revisions/publish_records/archive_commits` schema-only 空表零写入）；WAL + foreign_keys ON；任一 Stage2 写操作在无 Lock 持有的进程中执行即 FAIL。
- [ ] P0-2 Candidate 生命周期可证明（§5）：`DISCOVERED→WAITING_FOR_STABLE_FILE→IDENTIFYING_SOURCE→PROMOTED` 主链 + 旁路 `MERGED/REJECTED/SOURCE_MISSING`；Candidate 只做 Discovery/Stable/Provisional/Strong Hash/Promotion，出现 ASR/Normalization/Render/Publish/Archive 任一调用即 FAIL。
- [ ] P0-3 Provisional Identity 活跃期 Partial UNIQUE（§20）：`path_identity_key + size + mtime_ns` 仅对活跃 Candidate（DISCOVERED/WAITING/IDENTIFYING）Partial UNIQUE；终态（PROMOTED/MERGED/REJECTED/SOURCE_MISSING）不占约束；Case 13（历史 PROMOTED 后 same path+size+mtime+different bytes）必须建新 Candidate 并走 Strong Hash 识别为新 Source，吞掉即 FAIL。
- [ ] P0-4 Logical Source Exactly Once（§3.2/§21/§22）：`content_identity=SHA256(bytes)` + `logical_source_identity=path_identity_key+content_identity` UNIQUE；重复发现 UPSERT 收口，`Duplicate Logical Source Count = 0`；`path_identity_key` 保留原始中文/Unicode/大小写/空格/`丨`/括号（§23，不做 NFC/casefold 归一，不 encode/slugify）。
- [ ] P0-5 AUTO Run Partial UNIQUE + Conflict-safe 创建（§13/§15）：`CREATE UNIQUE INDEX ux_auto_processing_run ON processing_runs(source_id, asr_profile_hash) WHERE creation_mode='AUTO'` 逐字落地；创建只用 UPSERT / Conflict-safe Insert，出现 `SELECT→不存在→INSERT` 并发防线即 FAIL；`creation_mode` 仅 `AUTO`（`MANUAL_REPROCESS` 只做模型预留，不实现语义）；`auto_run_identity = source_id + asr_profile_hash`（§13）。
- [ ] P0-6 两层去重可证明（§19 + Case 2/Case 3 + §17/§18）：Triple Discovery Race（Watchdog+Scan+Reconciliation 三路同调直接 API）→ `Logical Source Count = 1, AUTO Run Count = 1`；NO_SPEECH Reconciliation ×10 → Run Count 仍为 1；FAILED_RETRYABLE 的 Reconciliation 重试原 Run（`retry_count+1`，不建新 Run）；任一 Count 偏离即 FAIL。
- [ ] P0-7 Single Instance 可证明（§64/§65/§62 子集）：`fcntl.flock LOCK_EX|LOCK_NB` 落在 `<data_root>/data/.lock`；第二实例直接退出（约定 exit 3，不碰 DB 不写盘）；Static Preflight 只做 Config/路径检查（不碰 DB、不 Repair、不建 Job、不起 Worker）；获锁后才允许 Open SQLite / Volume Probe / Recovery Bootstrap；顺序倒置即 FAIL。
- [ ] P0-8 异常路径全覆盖且可复现（合成副本，禁真实长视频）：Triple Race / Historical Provisional Collision（Case 13）/ NO_SPEECH×10（Case 2）/ FAILED_RETRYABLE 重试原 Run / 第二实例互斥 / iCloud-Remote Root BLOCK（Case 11，`BLOCKED_UNSUPPORTED_ROOT_FOR_V1`），任一缺失即 P0 不闭环。

## In Scope

- Candidate 生命周期（§5 全状态）+ Stable File 门（size/mtime 两轮稳定才放行；缺失→SOURCE_MISSING；§3.5 fast metadata 只做信号，最终裁决只认 SHA256）。
- Provisional Identity（§20：`path_identity_key + size + mtime_ns`，活跃期 Partial UNIQUE）+ Strong Content Identity（§21）+ Logical Source Identity（§22）+ `path_identity_key` 原样保留（§23 记录语义，完整 Unicode/Case 故障套件留 Stage6）。
- Logical Source Exactly Once（§3.2：Candidate Partial UNIQUE + Strong Identity + Source UNIQUE + UPSERT 收口）+ §6 最小字段子集沿 Stage1（`source_id/content_identity/size/mtime_ns/device/inode` + status/first_seen/last_seen 起）。
- AUTO Processing Run Identity（§13）+ creation_mode（§14，AUTO 实现 + MANUAL_REPROCESS 预留）+ Partial UNIQUE（§15）+ 重复发现行为（§16）+ FAILED_RETRYABLE（§17）+ NO_SPEECH（§18）+ 两层去重声明（§19）。
- 中央 SQLite（§31-35）：`discovery_candidates/sources/processing_runs/artifacts/state_events` 全功能 + `normalization_revisions/render_revisions/publish_records/archive_commits` DDL schema-only（零写入，写入即 FAIL，由验收反查行数为 0 证明）。
- Single Instance（§64）+ Startup Ordering 子集（§62 前五步）+ Static Preflight（§63）+ Runtime/Volume Preflight 获锁后执行（§65）+ Local Filesystem Only 门（§61/§3.14，复用 Stage1 `probe_volume` 语义）。
- §72 Implementation Acceptance Gate 中仅属于 Stage2 的断言子集：Candidate Partial UNIQUE / Historical Provisional Collision / Logical Source Exactly Once / Triple Discovery Race / AUTO Run Partial UNIQUE / Triple AUTO Count=1 / NO_SPEECH×10 Count=1 / FAILED_RETRYABLE 重试原 Run / Single Instance / iCloud-Remote Root BLOCK / Duplicate Source=0 / Duplicate AUTO Run=0。
- Stage1 回归：Stage1 per-job happy 路径（T01→T06）在 Stage2 落盘后仍可复现（只读复用，不改 `src/stage1/`）。

## Out of Scope

- Stage3 全部：Normalization Revision / Render Revision / Artifact Lineage 全链（§11/§12/§29/§30；中央库中对应表本 Stage 只建空 schema，不写任何行）。
- Stage4 全部：Canonical Publish + Atomic No-Clobber + Output Ownership（§48-53；`publish_records` 空表）。
- Stage5 全部：Watch First + Startup Scan + Reconciliation 真实实现（本 Stage 的“三路发现”只是同进程/多线程直接调 `discover()` API 的并发模拟，不起 watchdog 线程、不扫真实 Input 目录；Watcher Ready/Startup Scan/Workers 启动一律不实现）。
- Stage6 全部：Obsidian Path Mirror + Unicode/Case 完整故障套件（本 Stage 只保证 `path_identity_key` 原样存，不做归一化比较矩阵）。
- Stage7/8/9 全部：完整 Prompt/Vocabulary/Language（§44）/ 完整 VAD+Chunk+Absolute Timeline+Merge（§42）/ Normalization+Paragraph（§45-47）；ASR Profile 只取 Stage0/Stage1 冻结哈希字符串参与 `asr_profile_hash` 身份计算，不实现 Profile 内容语义、不调用 Whisper（本 Stage Whisper 调用次数恒为 0）。
- Stage10/11/12 全部：Archive A/B/C + `current_path` 更新（§56-59；`archive_commits` 空表）/ LaunchAgent + 完整 Fault Injection Suite（本 Stage 只做指定的 Race/Collision/互斥/Root-BLOCK 单测）/ Menu Bar。
- §26 Archive 前 Strong Verify 的实现（Archive 本身不在本 Stage，该条只读不实现；G3 实现仍留 Stage10/11，只记录）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试（用户明确：真实长视频一律不测直到产品完成；本 Stage 只用合成小文件/副本）。
- 不改 `src/stage1/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S2-T01 中央 SQLite 全表 DDL + 获锁后访问骨架 | P0 | builder | TODO | 输入：Data Root（TM 已定：沿用 H2 外置测试目录，仓库外独立目录）。输出：`src/stage2/store.py` + `<data_root>/data/state.db`（WAL，`PRAGMA foreign_keys=ON`）：`discovery_candidates/sources/processing_runs/artifacts/state_events` 全字段建表 + `normalization_revisions/render_revisions/publish_records/archive_commits` schema-only 空表 + `ux_auto_processing_run` Partial UNIQUE（§15 原文）+ 活跃 Candidate Provisional Partial UNIQUE（§20）+ `open_db()` 获锁断言（无锁即 FAIL，见 T06 锁文件）。验收：`.schema` 含 9 表 + 两 Partial UNIQUE 定义逐字可 grep；Stage3+ 四表行数恒为 0（有行即 FAIL）；无锁进程写 DB 即 FAIL。禁动 `src/stage1/` 与 per-job `job.sqlite`。 |
| S2-T02 Candidate 生命周期 + Stable File 门 | P0 | builder | TODO | 输入：S2-T01 的 DB。输出：`src/stage2/candidate.py`（`discover(path)` 直接 API，不监听文件系统）：DISCOVERED→WAITING_FOR_STABLE_FILE（size/mtime 两轮稳定才放行，抖动则停留）→IDENTIFYING_SOURCE→PROMOTED + MERGED（活跃期 Provisional 冲突并入既有）/REJECTED（显式拒绝）/SOURCE_MISSING（文件消失）；Provisional key = `path_identity_key(abspath 原样)+size+mtime_ns`。验收（含异常路径1/2）：happy（稳定小文件→PROMOTED）+ 重复 discover 同文件→MERGED 且活跃 Candidate 仍为 1 + 文件中途删除→SOURCE_MISSING。Candidate 内出现 ASR/import 即 FAIL。 |
| S2-T03 Logical Source Exactly Once + Promotion | P0 | builder | TODO | 输入：S2-T02 的 IDENTIFYING Candidate。输出：`src/stage2/source.py`：Strong SHA256（复用 `stage1.sha256_file`，只读）→ `content_identity` → `logical_source_identity=path_key\|content` → UPSERT `sources`（冲突返回既有，`Duplicate Logical Source Count=0`）；`path_identity_key` 原样存（中文/大小写/空格/`丨`/括号一字不改，不归一化）。验收（含异常路径3 Case 13）：happy（PROMOTED→1 Source）+ 历史碰撞（PROMOTED 后改 bytes 但保持 size+mtime→新 Candidate 建成→Strong Hash 不同→新 Source 产生，旧 Source 保留；吞掉判 FAIL）。 |
| S2-T04 AUTO Run Identity + Partial UNIQUE + UPSERT | P0 | builder | TODO | 输入：S2-T03 的 Source + `asr_profile_hash`（Stage0/Stage1 冻结值字符串透传，不解析不调用模型）。输出：`src/stage2/runs.py`（`get_or_create_auto_run(source_id, asr_profile_hash)`）：`auto_run_identity=source_id+asr_profile_hash`；只用 `INSERT … ON CONFLICT(source_id, asr_profile_hash) WHERE creation_mode='AUTO' DO NOTHING/UPDATE`（SQLite Partial UPSERT 等价写法，禁 `SELECT→INSERT`）；`creation_mode='AUTO'` 落库，`MANUAL_REPROCESS` 仅模型允许值；Run 初始 `QUEUED`（§9，不推进转写状态机，转写状态机仍归 Stage1）。验收：并发前 SQL 审计无 SELECT-then-INSERT 模式；不同 `asr_profile_hash` 同 Source 可建第二 Run（Profile 改变语义 §28），相同则返回同一 Run。 |
| S2-T05 两层去重 + Race/NO_SPEECH/RETRYABLE | P0 | builder | TODO | 输入：S2-T02–T04。输出：两层去重装配（§19：Candidate 层 MERGED + AUTO Run 层返回既有）+ `reconcile(source_id)`（FAILED_RETRYABLE→原 Run `retry_count+1`，§17；NO_SPEECH_DETECTED→返回既有终态，§18）。验收（含异常路径4/5/6）：Triple Race（三线程同调 `discover()` 同一合成副本→Source=1 且 AUTO Run=1）+ NO_SPEECH×10（同一 Run 返回 10 次，Count=1）+ FAILED_RETRYABLE reconcile（同一 `run_id`，`retry_count` 递增，无新 Run）。任一 Count 偏离即 FAIL。只用合成副本跑并发，不扫真实目录。 |
| S2-T06 Single Instance + Startup Ordering 子集 + Root 门 | P0 | builder | TODO | 输入：S2-T01 的 DB 骨架。输出：`src/stage2/instance.py`（`fcntl.flock LOCK_EX\|LOCK_NB` 于 `<data_root>/data/.lock`，第二实例 exit 3 且零写盘）+ 启动子序列（Static Preflight→Acquire Lock→Open SQLite→Volume Preflight→Recovery Bootstrap；Watcher/Scan/Workers 函数不存在，存在即 FAIL）+ Root 门（复用 `stage1.probe_volume`：Input/Data 任一非 local 即 `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`，Case 11）。验收（含异常路径7/8）：双进程互斥（第二实例 exit 3，DB mtime 不变）+ iCloud/remote 路径 BLOCK（exit 2）+ 无锁写 DB 被拒。 |
| S2-T07 Stage2 验收套件 + §72 子集门 + Stage1 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S2-T01–T06 产物 + `src/stage1/` 只读复用。输出：Stage2 验收报告（happy 链 1 遍：discover→PROMOTED→Source=1→AUTO Run=1 + 异常路径至少 6 个：Triple Race / Case 13 历史碰撞 / NO_SPEECH×10 / FAILED_RETRYABLE 重试原 Run / 第二实例互斥 / iCloud-Remote BLOCK；每个用例：前置/动作/期望 Count 或 exit 码/`Duplicate Source/Run=0` 证据/Stage3+ 四表行数=0 证据/Whisper 调用=0 证据；结论只落 qa 报告，HANDOFF 只记状态）+ Stage1 回归一行（per-job T01→T06 happy 仍 PASS，`src/stage1/` git diff 为空）。验收：任一异常缺失、Count 偏离、Stage3+ 表非空、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S2-T01 → T02 → T03 → T04 → T05 → T06 → T07 严格串行（同一 Candidate→Source→Run→Lock 因果链，Race 用例在 T05 之前跑会污染去重证据）；T06 的锁文件与 T02–T05 的用例文档可并行起草，但互斥验收必须在 S2-T01–T05 全部落盘后串行跑。
- 角色说明：S2-T01–T06 = builder 实现；S2-T07 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 Partial UNIQUE 写错范围导致历史碰撞被吞：`WHERE` 子句若把终态也纳入，Case 13 的新 Candidate 建不出来。缓解：T02/T03 验收强制 Case 13 用例（改 bytes 保 size+mtime→新 Source）；DDL 逐字评审 `WHERE status IN ('DISCOVERED','WAITING_FOR_STABLE_FILE','IDENTIFYING_SOURCE')`。
- R2 SELECT-then-INSERT 抢跑：Triple Race 下两线程同时穿过 SELECT 建出双 Run（Partial UNIQUE 只在 COMMIT 时报错，业务吞错继续跑）。缓解：T04 只许 UPSERT/ON CONFLICT 原子写法，code-reviewer 审计 SQL 文本；T05 用三线程真并发复现，不用串行模拟。
- R3 中央库与 per-job 库分叉：builder 为省事把 Stage2 状态写进 `job.sqlite` 或改 `src/stage1/` 表结构。缓解：T01/T07 硬门——`src/stage1/` git diff 为空 + Stage2 写只认 `<data_root>/data/state.db`；Stage1 回归用例反查。
- R4 锁文件放错位置/忘记获锁后置：锁若放在 `/tmp` 随机子目录，第二实例锁不住；或先 Open SQLite 后获锁（倒置 §62）。缓解：锁路径固定 `<data_root>/data/.lock`；`open_db()` 内置获锁断言；T06 双进程真测（非单进程 mock）。
- R5 真实目录被扫：T05 Race 用例若误配真实视频目录，Stable File 轮询会触碰用户文件。缓解：TM 已定——异常路径只用合成副本；验收前断言所有输入路径位于 Data Root 外置测试目录内。
- R6 Stage3+ 提前实现：builder 可能“顺手”写 `normalization_revisions` 行或推进 Run 到 TRANSCRIBING。缓解：T07 反查 Stage3+ 四表行数恒为 0 + Run 状态不出 `QUEUED`（转写状态机归 Stage1）；出现即 FAIL。
- R7 `path_identity_key` 被归一化：macOS 同名大小写/NFC 差异在 Stage6 前不得“智能”合并。缓解：本 Stage 存原样、比对只认字节相等；Unicode/Case 矩阵明确记为 Stage6，不在本 Stage 展开。

## Human Decisions Needed

- 无，均按 TM 已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① Data Root 沿用 H2 外置测试目录（仓库外独立目录，Stage1 `/tmp/s1t*` 模式延续）；② 异常路径一律用合成副本（原片不动，只动副本）；③ 真实长视频一律不测直到产品完成（用户明确）；④ 沿用 `src/stage1/` 地基做加法（`src/stage1/` 只读复用，新增只进 `src/stage2/`）。
