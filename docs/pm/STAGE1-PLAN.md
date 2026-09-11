# PLAN｜Stage 1 Single Video + Source Provenance + Raw PREPARED/COMMIT（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ `IMPLEMENTATION NOT YET ACCEPTED`（§75）；Stage0 已降级 GO（HANDOFF D6 改：无长视频直接进 Stage1；Q5/Q6 + B 剩 4 格 + C Word ON 转补测债，不卡 Stage1）。
> Stage0 冻结输入：`docs/qa/TECHNICAL_BENCHMARK_REPORT.md §9`（推荐配置只做 Profile 参数输入，不回写架构，不重开 Benchmark）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）——本 Stage 只实现 §69 Stage1 定义的事项，任何参数调优/新模型/新依赖/新架构主张一律打回。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中最小可证明闭环：单个指定视频端到端 ingest + Source Provenance 可证明 + Raw 两阶段安全提交，为后续 Stage 提供可信 Raw 地基。

## Current Stage

- Stage ID: Stage1 — Single Video + Source Provenance + Raw PREPARED/COMMIT（V1.8 §69）
- Goal: 单个指定路径视频端到端跑通 ingest（指定路径输入，不实现 Watch/Scan/Reconcile）；转写前 Fast Verification（§24）+ 转写后 Mandatory Strong SHA256（§25）+ Raw 两阶段提交 PREPARE/COMMIT（§37-39）+ Recovery Truth Model（§40-41，SQLite 落后 Repair Forward）；ASR 执行参数取 Stage0 冻结配置；Raw Immutable（§3.8）；Hash mismatch 只留 diagnostic-only，绝不 Commit。

Stage0 冻结配置（Profile 输入，原样引用 §9，不实现时只记录透传）：

```text
asr.model = mlx-community/whisper-large-v3-turbo @ a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb
asr.audio = temp-wav 16k mono（FFmpeg 落盘，可重跑）
asr.word_timestamps.default = OFF（按需 ON；ON 成本 ×1.4–1.5）
asr.no_speech_threshold = 0.6
vad.profile = silero thr 0.3–0.5，advisory only（禁过滤式 VAD）
chunk.size = 10min；overlap = 2s（本 Stage 按单文件直接转写，不实现 ChunkMerge §42；该值只记入 ASR Profile 待 Stage8 用）
prompt.budget_tokens = 200；order = Global→Topic→Creator（本 Stage 最小可用 prompt，不实现完整 PromptBuilder，Stage7 实现）
worker = 1（单机串行，禁多 worker 假设）
```

Implementation Notes 约束（源自 STAGE0-PLAN 附录 B Guardrail，Stage1 builder 强制遵守）：

- G1 AUTO Run 顺序：`Source → Run` 的 NOT NULL 链不得倒置。Stage1 虽为简化 ingest（指定路径输入），仍必须先完成 Logical Source 最小注册（含 `content_identity` Strong SHA256），再创建 Processing Run；禁止为跑通 happy path 先建 Run 后补 Source。
- G2 Strong Hash 前后 fstat 对比：§25 转写后 Mandatory Strong SHA256 必须附带转写前后 fstat 对比（device / inode / size / mtime_ns），防 Case 8（Same size + same mtime + different bytes）与转写中 Source 被改；fstat 对比是变化检测信号，最终裁决只认 SHA256（§3.5）。
- G3（仅记录，不实现）：Crash Recovery 后、Archive 前重确认 Publish 存在且用户编辑优先——记为 Stage10/11 前置约束，本 Stage 不实现 Archive/Publish，不得提前实现。

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照）

- [ ] P0-1 单视频指定路径 ingest 跑通：给定一个本地视频路径，端到端产出一个 COMMITTED Raw Artifact（含 manifest COMMITTED Receipt + SQLite `COMMITTED`），happy path 可复现。
- [ ] P0-2 转写前 Fast Verification 实现（§24）：`VERIFYING_SOURCE_FOR_TRANSCRIPTION` 检查 device/inode/size/mtime_ns；变化则重算 SHA256；`current_hash != content_identity` 则 `BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION`，不进 ASR。
- [ ] P0-3 ASR 执行参数等于 Stage0 冻结配置：model revision `a4aaeec0`、temp-wav 16k mono、word 默认 OFF、nst 0.6、单文件直接转写、VAD 只观测不参与过滤；任一偏离必须在产物中声明并 FAIL。
- [ ] P0-4 转写后 Mandatory Strong SHA256 实现（§25 + G2）：无论 size/mtime 是否变化，转写完成后正式 Commit 前无条件重算 Source SHA256 并附前后 fstat 对比；只有 `current_sha256 == content_identity` 才允许 `COMMITTING_RAW_ASR`，否则 `BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION`，本次 ASR 不得 Commit/不得进 Normalization/Render/Publish/Archive。
- [ ] P0-5 Raw PREPARE 实现（§38）：`artifact.tmp → flush → fsync(file) → parse/schema validation → expected_artifact_hash → SQLite artifacts 写 PREPARED → COMMIT transaction`；expected hash 在 Final Commit 前已持久化。
- [ ] P0-6 Raw COMMIT 实现（§39）+ Raw Immutable（§3.8）：PREPARED Receipt 已持久化 → atomic tmp→final → fsync(parent) → 验证 final hash → Manifest 写 COMMITTED → SQLite `COMMITTED`；已 COMMITTED 的 Raw 后续只读，任何 Correction/Render 不得改 Raw。
- [ ] P0-7 Recovery Truth Model 实现（§40-41）：PREPARED + Final Exists + Hash Match 则 Repair Forward（补 Manifest COMMITTED + SQLite COMMITTED，不得重跑 Whisper）；PREPARED + tmp Exists + Final Missing 则验 tmp 后继续 Commit；Final Hash != Expected 则永不视为有效 Artifact；SQLite 落后一律 Repair Forward，不重跑昂贵 ASR。
- [ ] P0-8 Hash mismatch 隔离：diagnostic-only 数据可保存但明确标记非正式 Raw Artifact，不进 lineage、不触发下游；`Source Changed During Transcription Raw Commit = 0`（§72 Artifact/Source Provenance 门）。
- [ ] P0-9 异常路径全覆盖且可复现：Source Changed Before / Source Changed During / Same size+mtime 不同 bytes（Case 8）/ PREPARE 后 kill-9 恢复（Case 9 对应 Raw 段 / Case 15 SQLite 落后），任一缺失即 P0 不闭环。

## In Scope

- 单个视频端到端 ingest：调用方指定本地视频路径（Discovery 简化为直接路径输入）；最小 Logical Source 注册（`source_id / content_identity(SHA256) / size / mtime_ns / device / inode` + §6 最小字段子集）；单个 Processing Run（`creation_mode=MANUAL` 或单测专用，AUTO 语义留 Stage2）；单文件直接送 ASR。
- Source Provenance 两段：转写前 Fast Verification（§24）+ 转写后 Mandatory Strong SHA256 + G2 前后 fstat 对比（§25）。
- Raw 两阶段提交：PREPARE（§38）+ COMMIT（§39），namespace 沿 §36 job-scoped（`data/jobs/<job_id>/raw/raw.json + manifest.json + source.json/run.json` 最小集）。
- Recovery Truth Model（§40-41）：Valid Filesystem Artifact + Expected Hash = Truth；Receipt = Commit Evidence；Manifest = Receipt + Lineage；SQLite = Workflow State/Index，落后 Repair Forward。
- ASR 执行：Stage0 冻结配置原样用（temp-wav 落盘可重跑；word 默认 OFF；nst 0.6；VAD advisory 只记录不参与过滤；chunk 单文件直转，ChunkMerge §42 不实现；prompt 最小可用，完整 PromptBuilder 留 Stage7）。
- Raw Immutable（§3.8）与 diagnostic-only 隔离规则（§25）。
- §72 Implementation Acceptance Gate 中仅属于 Stage1 的断言子集：Transcription 前 Verification PASS、转写后 Mandatory SHA256 PASS、Same size+mtime+b不同 bytes PASS、During 变化 Raw Commit=0、Raw PREPARED Receipt PASS、Raw Rename/Manifest Kill Recovery PASS（Raw 段）、Artifact Hash Validation PASS、SQLite Forward Repair PASS（Raw 段）、Raw Immutable PASS。

## Out of Scope

- Stage2 全部：Candidate 生命周期（§5）、Source 去重/Exactly Once（§3.2）、AUTO Run Identity + Partial UNIQUE（§13/15/16/19/20）、SQLite 全表（§31-35 全量字段）、Single Instance（§64）。
- Stage3+ 全部：Normalization Revision / Render Revision / Artifact Lineage 全链（Stage3）、Canonical Publish + No-Clobber + Ownership（Stage4）、Watch/Scan/Reconcile（Stage5）、Obsidian Path Mirror + Unicode/Case（Stage6）、完整 Prompt/Vocabulary/Language（Stage7）、完整 VAD + Chunk + Absolute Timeline + Merge（Stage8）、Normalization + Paragraph（Stage9）、Archive A/B/C（Stage10）、LaunchAgent + Fault 全套件（Stage11）、Menu Bar（Stage12）。
- §26 Archive 前 Strong Verify 的实现（Archive 本身不在本 Stage，该条只读不实现）。
- G3 的实现（只记录为 Stage10/11 前置）。
- 多 worker / 多进程 Worker（§2.2 明确不做）、复杂 UI、Golden Dataset、完整 Fault Injection Suite（本 Stage 只做指定的 kill-9/篡改恢复单测，不搭全套件）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S1-T01 指定路径 ingest 脚手架 + job-scoped 落盘 | P0 | builder | TODO | 输入：用户给定的单测视频绝对路径 + Data Root（见 Human Decisions）。输出：`data/jobs/<job_id>/` 最小 namespace（source.json/run.json/manifest.json/raw/ 占位）+ 最小 Source 注册（含首次 Strong SHA256 即 `content_identity`）+ Run 创建（G1：先 Source 后 Run，NOT NULL 链校验）。验收：Run 无 Source 即 FAIL；namespace 偏离 §36 即 FAIL。只准本地测试目录写，禁动业务/用户真实目录。 |
| S1-T02 转写前 Fast Verification（§24） | P0 | builder | TODO | 输入：S1-T01 的 Source 记录。输出：`VERIFYING_SOURCE_FOR_TRANSCRIPTION` 实现（读 device/inode/size/mtime_ns；变化则重 SHA256；mismatch → `BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION` 不进 ASR）。验收（含异常路径1）：happy path（未变化→放行）+ 异常路径 Source Changed Before（转写前改文件→BLOCK 且 ASR 调用次数=0）。G2 的 fstat 采集函数在此 Task 先行实现，供 T04 复用。 |
| S1-T03 ASR 执行（Stage0 冻结配置，单文件直转） | P0 | builder | TODO | 输入：T02 放行的 Source + Stage0 §9 配置。输出：temp-wav 16k mono 落盘（FFmpeg，可重跑）+ mlx-whisper `large-v3-turbo@a4aaeec0` 单文件转写 + word 默认 OFF + nst 0.6 + VAD advisory 只记录（不参与过滤）+ ASR Profile 实际值记录（含 model_revision/音频方式/word 开关/decode 参数）。验收：revision/音频方式/word 默认任一偏离且无声明即 FAIL；pipe/多 worker/VAD 过滤出现即 FAIL（STOP EXPANSION）。 |
| S1-T04 转写后 Mandatory Strong SHA256 + G2 对比（§25） | P0 | builder | TODO | 输入：T03 产物 + 转写前后 fstat。输出：无条件重算 Source SHA256 + 前后 fstat 对比记录（device/inode/size/mtime_ns）+ 门控：相等才允许 `COMMITTING_RAW_ASR`，不等 → `BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION`（本次 ASR 不 Commit/不进下游；产物转 diagnostic-only 隔离区）。验收（含异常路径2/3）：happy path（不变→放行）+ 异常路径 Source Changed During（转写中改文件→BLOCK 且 Raw Commit=0）+ 异常路径 Same size+mtime 不同 bytes（Case 8：size/mtime 不变但 bytes 变→必须 BLOCK，证明 fstat 之外 SHA256 裁决生效；只看 size/mtime 即 FAIL）。 |
| S1-T05 Raw PREPARE（§38） | P0 | builder | TODO | 输入：T04 放行的 Raw 内容。输出：`raw.json.tmp → flush → fsync(file) → schema validation → expected_artifact_hash → SQLite artifacts 行（artifact_id/owner_id/type/expected_hash/temp_path/final_path/state=PREPARED）→ COMMIT transaction`。验收：expected hash 未持久化即 FAIL；validation 缺失即 FAIL；SQLite 与 tmp 状态不一致即 FAIL。 |
| S1-T06 Raw COMMIT + Immutable（§39 + §3.8） | P0 | builder | TODO | 输入：T05 的 PREPARED Receipt。输出：atomic tmp→final + fsync(parent) + final hash 校验 + Manifest COMMITTED Receipt + SQLite `state=COMMITTED` + Raw 只读标记（后续任何写 Raw 即拒绝）。验收：happy path（PREPARE→COMMIT 闭环，final hash==expected）+ Immutable 检查（试图改已 COMMITTED Raw→拒绝且 hash 不变）。Final Hash != Expected 时永不视为有效（§40），直接 FAIL 该 Commit。 |
| S1-T07 Recovery：PREPARE 后 kill-9 + SQLite 落后 Repair Forward（§40-41，Case 9/15 Raw 段） | P0 | builder + qa | TODO | 输入：T05/T06 中间态。输出：恢复逻辑（PREPARED+Final Exists+Hash Match→补 Manifest/SQLite COMMITTED，不重跑 Whisper，Whisper 调用计数不变；PREPARED+tmp Exists+Final Missing→验 tmp 后继续 Commit）。验收（含异常路径4/5）：异常路径 PREPARE 后 kill-9（rename 后 manifest 前杀进程→重启 Repair Forward 成功，Whisper Calls 不增加）+ 异常路径 SQLite 落后（Artifact 已 COMMITTED 但 SQLite 仍 PREPARED→Repair Forward，不重跑 ASR）。builder 实现，qa 按“坏例看 exit 码”复现 kill-9/落后两用例。 |
| S1-T08 Stage1 验收套件 + §72 子集门 | P0 | qa（执行）+ builder（修） | TODO | 输入：S1-T01–T07 产物。输出：Stage1 验收报告（happy path 端到端 1 遍 + 异常路径至少 4 个：Before / During / Same size+mtime 不同 bytes / PREPARE 后 kill-9（含 SQLite 落后）；每个用例：前置/动作/期望 BLOCK 或 COMMIT 状态/Whisper 调用计数/Raw Commit 计数/final hash 证据；结论只落 qa 报告，HANDOFF 只记状态）。验收：任一异常路径缺失、或 During 变化后 Raw Commit≠0、或 kill-9 后重跑 Whisper、或结论写进 HANDOFF 代替报告，均为 FAIL。 |

- 并行性说明：S1-T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 严格串行（同一 Source→Run→Raw→Receipt 因果链，禁并行抢跑污染 Provenance 证据）；T07 的恢复用例与 T08 的验收设计可与 T02–T06 并行写用例文档，但执行必须在实现完成后串行跑。
- 角色说明：S1-T01–T06 = builder 实现；S1-T07 = builder 实现 + qa 复现；S1-T08 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 测试视频被转写中途改动污染证据：单测视频若放在会被同步/整理工具触碰的目录，mtime/hash 抖动会导致误 BLOCK。缓解：单测视频放本地非同步目录，跑前锁定只读快照说明；误 BLOCK 一律如实记录 fstat+hash，不重跑掩盖。
- R2 Data Root 与源视频同盘/跨盘差异影响后续 Archive 语义：本 Stage 不实现 Archive，但 job-scoped 落盘若选错盘会给 Stage10 留坑。缓解：Human Decisions 先定 Data Root，计划要求记录 volume 类型（local 必须，iCloud/remote 直接 BLOCK 按 §3.14）。
- R3 Stage0 冻结值被“顺手优化”：builder 可能把 word ON、pipe、VAD 过滤、ChunkMerge、Prompt 全量装配提前实现。缓解：T03 验收设硬门——出现任一即 FAIL；STOP EXPANSION 每轮复核。
- R4 kill-9 用例真杀错进程/目录：恢复演练若在错误目录执行会误删证据。缓解：只准 Human Decisions 批准的本地测试目录做 kill-9/篡改演练；演练前要求 manifest+SQLite+tmp/final 四件套先落盘快照。
- R5 diagnostic-only 与正式 Raw 混淆：mismatch 产物若与正式 Raw 同目录同命名会被下游误食。缓解：diagnostic-only 强制隔离目录 + 文件名标记 + 不写 COMMITTED Receipt、不进 lineage；qa 在 T08 反查 lineage 无 diagnostic 引用。
- R6 SQLite 超前/落后判定写反导致重跑 Whisper：Repair 方向错误会浪费数分钟 ASR 并污染计数。缓解：Truth Model 硬编码——Filesystem Valid + Expected Hash = Truth，SQLite 永远是落后方 Repair Forward；kill-9 用例断言 Whisper Calls 不增加。

## Human Decisions Needed

- H1 请给单测视频路径：1 个本地中文真实视频绝对路径（5–25 分钟均可；Stage0 素材如 `01.为什么人人开始Vibe Coding(氛围编程).mp4` 可复用）。是否允许 qa 为造异常路径复制/篡改该视频的副本（原片不动，只动副本）？
- H2 Data Root 落盘位置：`data/jobs/<job_id>/` 的父目录放在哪（默认建议仓库外独立测试目录，避免污染业务仓库）？该盘是否为本地盘（iCloud/网络盘按 §3.14 直接 BLOCK，不开工）？
- H3 是否允许写本地测试目录：builder/qa 可在 H2 目录内创建 job 目录、写 tmp/final/manifest/SQLite、执行 PREPARE 后 kill-9 恢复演练？是否允许安装/复用 Stage0 venv 依赖（mlx/mlx-whisper/ffmpeg，不新增依赖）？
