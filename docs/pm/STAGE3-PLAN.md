# PLAN｜Stage 3 Normalization Revision + Render Revision + Artifact Lineage（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage2 CLOSED（HANDOFF 2026-09-11 02:00，supervisor终检PASS，P0-1~P0-8全可证明，直推Stage3）。
> Stage1+Stage2 冻结输入：`src/stage1/`（job-scoped `data/jobs/<job_id>/` + per-job `job.sqlite` + Raw PREPARE/COMMIT + Immutable + Repair Forward）与 `src/stage2/`（Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance 锁）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/` 任一文件（改了即 FAIL；新增只进 `src/stage3/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage3 only）`——本 Stage 只实现 §69 Stage3 定义的事项（Normalization Revision + Render Revision + Artifact Lineage），Stage4+（Publish/Watch/Archive）一律 Out，写了即 FAIL。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中派生链的一块：在 Stage1 COMMITTED Raw 与 Stage2 身份地基之上，建立“改规则不重跑 Whisper”的派生机制——Correction Rules 改变只产生新 Normalization Revision、Paragraph Formatter 改变只产生新 Render Revision（Raw Immutable、Run 不回滚），Rendered 与 Canonical 彻底分离（派生默认不覆盖 Canonical），全链 Lineage 可查（Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→PublishEvaluation）。

## Current Stage

- Stage ID: Stage3 — Normalization Revision + Render Revision + Artifact Lineage（V1.8 §69）
- Goal: 确定性 Correction 纯函数（§45，只修高度确定专业词，无 LLM）+ Normalization Profile 分层（§29）→ Normalization Revision 生命周期（§11：PENDING→NORMALIZING→COMMITTING→COMPLETED + FAILED_RETRYABLE/FAILED_FINAL，复用 Raw，不碰已完成 Run §10）→ Normalized Artifact 两阶段提交（§37-39：PREPARE→FILESYSTEM COMMIT→RECEIPT COMMIT，落 `data/jobs/<job_id>/normalized/<normalization_revision_id>.json` §36）→ 确定性 Paragraph 纯函数（§47：Long Pause > Strong Punctuation > Target Length > Hard Max）+ Render Profile 分层（§30）→ Render Revision 生命周期（§12，走到 PUBLISH_EVALUATION 只做 verdict 记录：已有 canonical 时 `PENDING_PUBLISH` / `CANONICAL_OUTPUT_EXISTS`，零 Canonical 写盘）→ Rendered Artifact 两阶段提交（落 `data/jobs/<job_id>/render/<render_revision_id>.md` §36）→ Recovery Repair-Forward（§40-41：Final+HashMatch 补 Receipt，SQLite 落后前向修复，恢复过程 Whisper 调用恒为 0）→ Artifact Lineage 组装与查询（§4 全链 + Manifest = Receipt + Lineage §41）→ Case 4 / Case 5 / Case 6 可证明（Whisper +0、Raw 不变、按规则只建对应的新 Revision、Canonical 默认不覆盖、Run 保持 COMPLETED）。

Stage1+Stage2 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import，不复制不修改）：COMMITTED raw.json 只读输入 /
  validate_raw_artifact / guarded_open_raw_for_write（Raw 写保护）/
  commit/recovery 的 PREPARE→COMMIT→Receipt 语义（§37-41，本 Stage 为
  Normalized/Rendered 新实现一份，不得把 stage1 的 Raw 专用函数改成通用函数）
src/stage2/ 原样复用（import，不复制不修改）：open_db（持锁断言）/
  init_db 建好的 normalization_revisions/render_revisions/artifacts/state_events
  表（本 Stage 起对 norm/render 两表正式写行）/ instance.acquire 持锁写库 /
  Run 状态只读（Stage3 不推进、不回滚任何 Run 状态）
src/stage3/ 新增：artifact_commit.py / normalize.py / render.py / derive.py / lineage.py
中央库位置：<data_root>/data/state.db（沿用 Stage2；per-job job.sqlite 与 Manifest 原地不动，只追加 Lineage Receipt）
Raw 输入：Stage1 链在合成输入上产出的 COMMITTED Raw（T01→T06 happy 复用，不手写 raw.json 绕过校验）；Stage3 派生阶段 Whisper 调用恒为 0
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Normalization Revision 生命周期可证明（§11/§29）：`PENDING→NORMALIZING→COMMITTING→COMPLETED` 主链 + `FAILED_RETRYABLE/FAILED_FINAL` 旁路；`normalization_profile_hash` = §29 六字段（correction rules revision / hallucination classifier version / duplicate cleanup version / chunk merge normalization rules / mechanical cleanup version / quality threshold profile）规范 JSON 的 SHA256；Correction 纯函数只做高度确定专业词替换（§45，无 LLM、无润色改写总结、无语义猜测，出现 LLM/云调用即 FAIL）；Revision 行写入中央 `normalization_revisions`（§33 全字段），状态变迁记 `state_events`。
- [ ] P0-2 Render Revision 生命周期可证明（§12/§30）：主链走到 `ARTIFACT_COMPLETED→PUBLISH_EVALUATION` 后停止，只记录 verdict（canonical 已存在→`PENDING_PUBLISH` 或 `CANONICAL_OUTPUT_EXISTS`；§12 的 `PUBLISHING→PUBLISHED` 分支不存在，不存在即对——Initial Publish 属 Stage4）；`render_profile_hash` = §30 五字段（paragraph formatter version / paragraph parameters / H1 setting / Frontmatter setting / Markdown renderer version）规范 JSON 的 SHA256；Paragraph 纯函数严格按 §47 规则优先级实现；Revision 行写入中央 `render_revisions`（§34 全字段）。
- [ ] P0-3 Normalized/Rendered 两阶段提交可证明（§37-39 + §72 Artifact 子集）：`artifact.tmp → flush → fsync → schema 校验 → expected_artifact_hash 预持久化（中央 artifacts 表 PREPARED）→ atomic rename → fsync(parent) → final hash 校验 → Manifest COMMITTED Receipt → SQLite COMMITTED`；Normalized PREPARED Receipt / Artifact Hash Validation 任一缺失即 FAIL；半个 Artifact（hash 不等）永不视为成功。
- [ ] P0-4 Recovery 可证明（§40-41）：PREPARED + Final 存在 + Hash Match → Repair Forward（补 Manifest 与 SQLite COMMITTED，不重跑 Whisper）；PREPARED + 仅 tmp → 验证后继续 Commit；Final Hash != Expected → 判无效；SQLite 落后于文件系统时前向修复；恢复全程 Whisper 调用为 0。
- [ ] P0-5 Case 4 可证明（Correction Rules 改变）：profile 变更后 Whisper Calls = 0、Raw Hash 不变、产生新 Normalization Revision（含新 Normalized Artifact）、产生新 Rendered Artifact、预置的 canonical 诱饵文件字节级不变（默认不覆盖 §50/§51）。
- [ ] P0-6 Case 5 可证明（Paragraph Formatter 改变）：Raw 不变、`normalized_artifact_id` 被复用（同一 ID，无新 Norm Revision）、产生新 Render Revision（含新 Rendered Artifact）、canonical 诱饵字节级不变。
- [ ] P0-7 Case 6 + Raw Immutable 可证明（§10/§3.8）：派生前后 Processing Run 状态保持 COMPLETED（Revision 只维护自身状态）；COMMITTED Raw 字节与 hash 全程不变，任何经 Stage3 路径的 Raw 写操作被拒绝（复用 `guarded_open_raw_for_write` 语义）。
- [ ] P0-8 STOP EXPANSION 门可证明：`publish_records` / `archive_commits` 行数恒为 0（有行即 FAIL）；`src/stage1/` 与 `src/stage2/` git diff 为空；异常路径一律合成副本，真实长视频零触碰；Stage3 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`），测试以调用计数 = 0 举证。

## In Scope

- Normalization Profile 分层与哈希（§29 全字段）+ 确定性 Correction 纯函数（§45）+ Normalization Revision 生命周期（§11 全状态）+ `normalization_revisions` 写行（§33 字段：`normalization_revision_id/raw_artifact_id/normalization_profile_hash/normalized_artifact_id/status/created_at/completed_at`）。
- Render Profile 分层与哈希（§30 全字段）+ 确定性 Paragraph 纯函数（§47 规则序）+ Render Revision 生命周期到 PUBLISH_EVALUATION（含 verdict 记录，不含发布执行；§12 Subsequent 分支）+ `render_revisions` 写行（§34 全字段）。
- 两阶段提交新实现（§37 PREPARE / §38 细节 / §39 COMMIT，面向 Normalized JSON 与 Rendered MD，落 job-scoped §36 路径）+ 中央 `artifacts` 行（PREPARED→COMMITTED）+ Manifest Receipt 追加 + `state_events` 变迁记录。
- Recovery（§40 三分支 + §41 Truth Model：文件系统有效 Artifact + expected hash = 真相，SQLite 落后前向修复，零 Whisper）。
- 派生装配（§3.9：Correction 改变→新 Norm Revision；Formatter 改变→新 Render Revision；派生永不触发 ASR）+ Case 4 / Case 5 / Case 6 行为。
- Artifact Lineage（§4 全链：Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→PublishEvaluation verdict；Manifest Lineage Metadata + 中央库可查询组装）。
- §72 Implementation Acceptance Gate 中仅属于 Stage3 的断言子集：Correction Rules Change 不重新调用 Whisper / Raw Hash 不变 / 新 Normalization Revision / Paragraph Formatter Change 只新建 Render Revision / Completed Processing Run 不被 Revision 回滚 / Normalized PREPARED Receipt / Artifact Hash Validation / SQLite Forward Repair / Raw Immutable。
- Stage1 回归（per-job T01→T06 happy 仍可复现）+ Stage2 回归（discover→PROMOTED→Source=1→AUTO Run=1 链仍 PASS，`assert_stage3_tables_empty` 对 publish/archive 子集仍成立——注意：stage2 该 helper 覆盖 norm/render 四表，本 Stage 起 norm/render 正式写行，builder 不得改 `src/stage2/`，Stage3 自带 publish/archive 为空断言，见 S3-T06）。

## Out of Scope

- Stage4 全部：Initial Canonical Publish + Atomic No-Clobber + Output Ownership + Output Conflict（§48-53、§49；`publish_records` 空表零写入；Render Revision 的 `PUBLISHING→PUBLISHED` 分支不存在）。
- Stage5 全部：Watch First + Startup Scan + Reconciliation 真实实现（本 Stage 的 Raw 输入来自 Stage1 指定路径复用，不起监听、不扫 Input 目录）。
- Stage6 全部：Obsidian Path Mirror + Unicode/Case 完整故障套件（本 Stage 不写 Canonical，无路径镜像行为）。
- Stage7 全部：Prompt + Vocabulary + Language Strategy（Correction 只用冻结版确定性规则表，不做 prompt/词典语义升级；规则表版本变更本身即 profile 变更，走 Case 4）。
- Stage8 全部：VAD + Chunk + Absolute Timeline（Render 直接消费 Raw 既有 segments，不重切分、不重排时间线；Word Timestamp 能力沿 Stage1，不扩展）。
- Stage9（阈值调优）：Paragraph 具体阈值由 Benchmark/Golden 决定（§47）——本 Stage 用版本化定值参数实现规则序并记入 `render_profile_hash`，调优本身留 Stage9；参数变更走 Case 5 证明机制。
- Stage10/11/12 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 空表）/ LaunchAgent + 完整 Fault Injection Suite（本 Stage 只做 §40-41 指定的 PREPARE/tmp/hash 三分支恢复单测）/ Menu Bar。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试（用户明确：真实长视频一律不测直到产品完成；本 Stage 只用合成小文件/副本 + canonical 诱饵文件）。
- 不改 `src/stage1/` 与 `src/stage2/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S3-T01 两阶段提交 helper（Normalized/Rendered 共用） | P0 | builder | TODO | 输入：Stage1 `prepare.py/commit.py` 的 §38/§39 语义（只读照抄，不改原文）+ Stage2 `open_db` 持锁写库。输出：`src/stage3/artifact_commit.py`（`prepare_artifact(con, job_dir, artifact_type, final_relpath, content_bytes)`：写 tmp→flush→fsync→schema/类型校验→expected hash→中央 `artifacts` 行 PREPARED→COMMIT 事务；`commit_artifact(...)`：断言 PREPARED→atomic rename→fsync(parent)→final hash 校验→Manifest 写 COMMITTED Receipt→SQLite 置 COMMITTED；`recover_artifact(...)`：§40 三分支；hash 不等永判无效）。验收：PREPARED Receipt 行存在性 + Final hash == expected 证据 + tmp-only 续 Commit 用例 + hash 篡改判无效用例 + 全程 Whisper 调用 0。禁动 `src/stage1/`（不得把 Raw 专用函数改通用）。 |
| S3-T02 Normalization Revision + 纯函数 | P0 | builder | TODO | 输入：S3-T01 + COMMITTED Raw（只读）+ §29/§45。输出：`src/stage3/normalize.py`（`normalization_profile_hash(profile)`：§29 六字段规范 JSON→SHA256；`apply_corrections(raw_segments, rules_rev)` 纯函数：冻结版确定性规则表，只修高度确定专业词，无 LLM/改写/猜测；`create_normalization_revision(con, job_dir, raw_artifact_id, profile)`：建行 PENDING→NORMALIZING→COMMITTING（经 S3-T01 落 `normalized/<rev>.json`）→COMPLETED，变迁记 `state_events`；`FAILED_RETRYABLE/FAILED_FINAL` 旁路）。验收：happy（Raw→1 NormRev COMPLETED + Normalized 文件 hash == 行记录）+ profile 改一字段→hash 变 + 纯函数无 IO/无网络审计 + Run 状态未被触碰。 |
| S3-T03 Render Revision + 纯函数（止于 PUBLISH_EVALUATION） | P0 | builder | TODO | 输入：S3-T01 + S3-T02 的 Normalized Artifact（只读）+ §30/§47/§12。输出：`src/stage3/render.py`（`render_profile_hash(profile)`：§30 五字段规范 JSON→SHA256；`render_paragraphs(normalized, params)` 纯函数：严格 §47 优先级 Long Pause > Strong Punctuation > Target Length > Hard Max，阈值取版本化定值并原样记入 profile；`create_render_revision(...)`：PENDING→RENDERING→ARTIFACT_COMMITTING（经 S3-T01 落 `render/<rev>.md`）→ARTIFACT_COMPLETED→PUBLISH_EVALUATION：canonical 诱饵存在→记 `PENDING_PUBLISH` 或 `CANONICAL_OUTPUT_EXISTS` 并停止，零写盘；模块内不存在 `PUBLISHING/PUBLISHED` 状态常量，存在即 FAIL）。验收：happy（Normalized→1 RenderRev， verdict 已记录，诱饵 md 字节不变）+ Paragraph 规则序单测（长停顿/强标点/目标长/硬上限各一例）。 |
| S3-T04 派生装配（Case 4/5 路径 + Whisper  guard） | P0 | builder | TODO | 输入：S3-T02 + S3-T03。输出：`src/stage3/derive.py`（`derive_on_correction_change(...)`：新 profile→新 NormRev（复用同一 `raw_artifact_id`）→下游新 RenderRev + 新 Rendered；`derive_on_formatter_change(...)`：复用同一 `normalized_artifact_id`（无新 NormRev）→只建新 RenderRev；模块级 Whisper guard：本文件及 S3-T01–T03 永不 import `stage1.asr.run_asr_single_file`，grep 审计 + 测试期调用计数恒 0）。验收：Case 4（Whisper 0、Raw hash 同、新 NormRev、新 Rendered、诱饵不变）+ Case 5（Raw 同、normalized ID 同且 NormRev 数 +0 为 0、新 RenderRev、诱饵不变）+ Case 6（Run 全程 COMPLETED，Revision 自管状态）。 |
| S3-T05 Artifact Lineage 组装与查询 | P0 | builder | TODO | 输入：S3-T02–T04 落盘的行与文件 + §4/§41。输出：`src/stage3/lineage.py`（`record_lineage(manifest, ...)`：Manifest 追加 Norm/Render Receipt + Lineage Metadata，只追加不改写历史条目；`get_lineage(source_id_or_run_id, data_root)`：从中央库组装 §4 全链 Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→PublishEvaluation verdict，缺环显式标缺不编造）。验收：一条完整派生链（1 Raw→2 NormRev→2 Rendered）查询返回全链 ID 与 hash，Manifest 含对应 Receipt 行，缺环构造用例返回缺环标记而非异常。 |
| S3-T06 Stage3 验收套件 + §72 子集门 + Stage1/2 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S3-T01–T05 产物 + `src/stage1/`、`src/stage2/` 只读复用。输出：Stage3 验收报告（happy 链 1 遍：COMMITTED Raw→NormRev COMPLETED→Rendered→verdict + 异常路径至少 6 个：Case 4 / Case 5 / Case 6 / PREPARED+Final Repair Forward / tmp-only 续 Commit / Final hash 篡改判无效；每个用例：前置/动作/期望计数值或 verdict/`publish_records`+`archive_commits` 行数=0 证据/Whisper 调用=0 证据/Raw hash 不变证据/诱饵 md 不变证据/Run=COMPLETED 证据；结论只落 qa 报告，HANDOFF 只记状态）+ 回归两行（Stage1 per-job T01→T06 happy 仍 PASS 且 `src/stage1/` diff 为空；Stage2 discover→AUTO Run=1 仍 PASS 且 `src/stage2/` diff 为空；Stage3 自带 publish/archive 为空断言通过——stage2 原 `assert_stage3_tables_empty` 四表口径已被 norm/render 写行取代，不得要求它通过，不得为此改 `src/stage2/`）。验收：任一异常缺失、计数偏离、publish/archive 非空、有 Raw 写、诱饵被改、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S3-T01 → T02 → T03 → T04 → T05 → T06 严格串行（同一 Raw→Normalized→Rendered→派生→Lineage 因果链；Case 4/5 用例在 T04 之前跑会污染“复用/新建”计数证据；Lineage 查询在派生落盘前跑会缺环）。
- 角色说明：S3-T01–T05 = builder 实现；S3-T06 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 builder“顺手”实现发布：§12 读到 PUBLISHING 就想写 Canonical。缓解：S3-T03 硬门——模块内不得出现 `PUBLISHING/PUBLISHED` 常量 + 验收用诱饵 md 字节比对；出现写盘即 FAIL（Stage4 才实现）。
- R2 为复用改 stage1/stage2 原文：把 Raw 专用 prepare/commit 改成通用函数最省事但违反加法约束。缓解：S3-T01 独立新文件实现；S3-T06 回归硬门——`src/stage1/` 与 `src/stage2/` git diff 为空。
- R3 stage2 四表空断言被 Stage3 写行顶翻：`assert_stage3_tables_empty` 覆盖 norm/render，Stage3 落盘后它必 FAIL，有人会去“修” stage2。缓解：S3-T06 明确——不得改 `src/stage2/`，Stage3 自带 publish/archive 子集断言；qa 报告写清口径变更原因。
- R4 Correction 函数偷偷变智能：规则表越写越大，出现模糊匹配/语义改写。缓解：S3-T02 纯函数审计（无 IO/无网络/无模型 import）+ §45 白名单语义（只修高度确定专业词）；规则表内容变更一律走 profile 版本，即 Case 4。
- R5 Paragraph 阈值争议卡住实现：§47 阈值归 Benchmark/Golden，Stage3 等不到数。缓解：In Scope 已定——版本化定值 + 记入 profile，调优留 Stage9；参数变更即 Case 5，自证机制闭环。
- R6 派生绕过 Raw 跑出新转写：derive 里图方便调了 asr 入口，Case 4 的 Whisper=0 破功。缓解：S3-T04 模块级 import 禁令 + grep 审计 + 测试计数器三重门。
- R7 真实长视频/真实笔记被触碰：用例误配真实目录，诱饵写成真实 md。缓解：TM 已定——一律合成副本 + 诱饵文件；验收前断言所有输入路径位于外置测试目录内，诱饵 md 与真实 Obsidian 库无交集。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical 用诱饵文件，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确）；④ `src/stage1/` + `src/stage2/` 只读加法（新增只进 `src/stage3/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage4+ 不实现：Publish/Watch/Archive 一律 Out，`publish_records`/`archive_commits` 零写入）。
