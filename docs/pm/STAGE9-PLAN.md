# PLAN｜Stage 9 Normalization + Paragraph（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage8 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + 确定性 Correction 冻结版规则表 + 版本化定值 Paragraph（§47 规则序） + `src/stage4/` Initial Canonical Publish + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING + `src/stage6/` Path Mirror + Unicode/Case 矩阵 + `src/stage7/` Vocabulary/PromptBuilder/Language Strategy + 单文件接线 + `src/stage8/` VAD advisory + ChunkPlanner（10min/2s）+ Absolute Timeline + Overlap Merge；Normalization 规则内容升级与 Paragraph formatter 版本升级均未发生，Case 4 / Case 5 仅在 Stage3 冻结版规则上证明过一次）。
> Stage1~Stage8 冻结输入：`src/stage1/`（`run_asr_single_file` 单文件直转 + 冻结常量 `FROZEN_*` + word 默认 OFF + nst 0.6 + temp-wav 16k mono）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `asr_profile_hash` 身份）与 `src/stage3/`（`normalize`/`render`/`derive`/`lineage` 公开 API + 冻结版 Correction 规则表 + 版本化定值 Paragraph 参数 + Case 4/5/6 派生 mechanics）与 `src/stage4/`（publish 语义，只读复用）与 `src/stage5/`（三路发现语义，只读复用）与 `src/stage6/`（`resolve_canonical` 纯映射，只读复用）与 `src/stage7/`（vocabulary/prompt/language，只读复用不复制）与 `src/stage8/`（VAD/Chunk/Timeline/Merge，只读复用不复制）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/` 任一文件（改了即 FAIL；新增只进 `src/stage9/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage9 only）`——本 Stage 只实现 §69 Stage9 定义的事项（Normalization + Paragraph：规则替换 + 段落格式化，§45 确定性 Correction + §47 Natural Paragraph 规则序 + §29/§30 Profile 分层 + §70 Case 4/Case 5/Case 6 延续 + §50/§51 默认不覆盖），Stage10+（Archive A/B/C + `current_path` 更新、LaunchAgent + Fault 全套件 + Golden、Menu Bar）一律 Out，写了即 FAIL；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；Normalization 只做规则替换、Paragraph 只做段落格式化——LLM 改写润色禁入（模块内出现 `openai|anthropic|llm|summar|polish|paraphras|rewrite` 即 FAIL）；规则序冻结（§47 Long Pause > Strong Punctuation > Target Length > Hard Max，改序即 FAIL）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“规则变了怎么办”的那一块：在 Stage3 派生 mechanics（改规则不重跑 Whisper）之上，用新一版 Correction 规则表内容替换冻结版规则（仍是确定性替换，§45，无 LLM）→ 走 `derive_on_correction_change` 只读复用产生新 Normalization Revision（Case 4 延续）→ 用新一版 Paragraph formatter 版本/参数重排段落（规则序不变，§47）→ 走 `derive_on_formatter_change` 只读复用产生新 Render Revision（Case 5 延续）→ 全程 Whisper 调用恒为 0、Raw 不变、Canonical 默认不覆盖（§50/§51）→ Stage1~8 回归（`src/stage1-8/` diff 为空）。

## Current Stage

- Stage ID: Stage 9 — Normalization + Paragraph（V1.8 §69）
- Goal: 新版 Correction 规则表（版本号 bump，纯确定性替换，禁 LLM）→ Case 4 延续（Whisper +0、Raw 不变、新 NormRev + 新 Rendered、Canonical 不覆盖）→ 新版 Paragraph formatter（版本/参数 bump，§47 规则序不变）→ Case 5 延续（Raw 不变、Normalized 复用、新 RenderRev、Canonical 不覆盖）→ Case 6 延续（Run 全程 COMPLETED）→ §29/§30 分层延续（新字段只进各自 profile 层）→ Stage1~8 回归（`src/stage1-8/` diff 为空）。

Stage1~Stage8 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（回归只读查）：COMMITTED Raw 只读输入（本 Stage 不转写，
  不调用 run_asr_single_file；调用即 FAIL）
src/stage2/ 原样复用（回归只读查）：open_db 持锁断言 / Run 状态只读（本 Stage
  不推进、不回滚任何 Run；Run 状态被写即 FAIL）
src/stage3/ 只读复用（import，不复制不修改）：normalize（apply_corrections +
  normalization_profile_hash）/ render（render_paragraphs + render_profile_hash）
  / derive（derive_on_correction_change + derive_on_formatter_change 派生
  mechanics）/ artifact_commit 两阶段提交 / lineage 查询；Stage3 冻结版规则表
  内容不改（要改的是 Stage9 自带的新版规则表文件，不是 stage3 原文）
src/stage4/ 零调用（本 Stage 只用 canonical 诱饵文件做“不变”比对，不走 publish；
  publish_records 行数恒为 0；回归只读查）
src/stage5/ 零调用（本 Stage 不起 Watcher/Scan/Reconcile；回归语义不断链）
src/stage6/ 零调用（本 Stage 不做路径映射；回归双算不断链）
src/stage7/ 零调用（本 Stage 不动 prompt/vocab；回归不断链）
src/stage8/ 零调用（本 Stage 不重切分、不重排时间线；回归不断链）
src/stage9/ 新增：rules_v2.py（新版 Correction 规则表内容 + 版本常量）/
  formatter_v2.py（新版 Paragraph formatter 版本/参数常量）/
  derive_v2.py（装配：调 stage3 derive 公开 API，不复制 mechanics）
  （命名以实现为准，前缀恒为 stage9，禁止 stage10+ 关键词文件名如
  archive/launchagent/menu/golden）
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage9 模块零直写 DB，
  一切行效应只许经 stage3 公开 API 并如实披露；
  publish_records/archive_commits 行数恒为 0；
  sources.current_path/status/archived_at 零写）
输入 Raw：Stage1 链在合成输入上产出的 COMMITTED Raw（只读复用，不手写
  raw.json 绕过校验）；Stage9 全程 Whisper 调用恒为 0
诱饵 canonical：外置合成目录内诱饵 md（只做字节级“不变”比对，不碰真实笔记）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Case 4 延续可证明（Correction Rules 改变，§45 + §29 + §70 Case 4）：Stage9 自带新版规则表（版本号 bump，条目为高度确定专业词替换，出现模糊匹配/语义改写/LLM 即 FAIL）→ 经 stage3 `derive_on_correction_change` 只读复用 → Whisper Calls 增量 = 0 + Raw 字节与 hash 全程不变 + 产生新 Normalization Revision（含新 Normalized Artifact，`normalization_profile_hash` 变化且可复算）+ 下游新 Rendered Artifact + 预置 canonical 诱饵字节级不变（§50/§51）。
- [ ] P0-2 Case 5 延续可证明（Paragraph Formatter 改变，§47 + §30 + §70 Case 5）：Stage9 自带新版 formatter（版本/参数 bump，规则序 Long Pause > Strong Punctuation > Target Length > Hard Max 不变，改序即 FAIL；仍是确定性纯格式化，出现 LLM/润色即 FAIL）→ 经 stage3 `derive_on_formatter_change` 只读复用 → Raw 不变 + `normalized_artifact_id` 被复用（同一 ID，NormRev 数增量为 0）+ 产生新 Render Revision（含新 Rendered Artifact，`render_profile_hash` 变化且可复算）+ 诱饵 md 字节级不变。
- [ ] P0-3 Case 6 + 默认不覆盖延续可证明（§10/§50/§51）：Case 4 与 Case 5 派生前后 Processing Run 状态全程保持 COMPLETED（Revision 只维护自身状态；Run 被推进/回滚即 FAIL）；COMMITTED Raw 全程 Immutable（任何经 Stage9 路径的 Raw 写操作被拒绝）；`publish_records` 行数恒为 0（Stage9 不走 publish，出现写行即 FAIL）。
- [ ] P0-4 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/` git diff 为空；`publish_records`/`archive_commits` 行数恒为 0；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL（Archive A/B/C 禁入）；Stage9 代码永不 import/调用 Whisper 执行入口（`run_asr_single_file`）、Archive 模块、`current_path` 回填、LaunchAgent、Menu Bar、LLM/云/SDK（`rg "run_asr_single_file|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage9/` 零命中举证）；`src/stage9/` 零直写 DB（`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage9/` 零命中；验收证据行只许经 stage3 公开 API 并逐行披露）；§47 规则序零变更（改序即 FAIL）。
- [ ] P0-5 外置合成验收门可证明（TM 已定）：一切输入位于外置合成目录 + 外置 Data Root 内（验收前断言，与真实视频目录/真实 Obsidian 库无交集）；异常路径一律合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“不变”，零触碰真实笔记）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告；长文本语义只用合成 segments 夹具证明，不用长音频）；任一用例触碰真实目录/发起云调用即 FAIL。

## In Scope

- 新版 Correction 规则表（版本号 bump + 高度确定专业词条目增改，§45 纯替换语义；规则表内容变更本身即 profile 版本变更，走 Case 4）。
- 新版 Paragraph formatter（版本/参数 bump，§47 规则序不变；参数变更走 Case 5 证明机制）。
- Case 4 / Case 5 / Case 6 延续证明（Whisper +0、Raw 不变、按规则只建对应的新 Revision、Canonical 默认不覆盖、Run 保持 COMPLETED）。
- §29/§30 分层延续（新规则版本只进 normalization profile，新 formatter 版本/参数只进 render profile；串层即 FAIL）。
- Artifact Lineage 延续（新 Revision 链经 stage3 lineage 只读查询可查全链，不新造 lineage 语义）。
- §72 Implementation Acceptance Gate 中仅属于 Stage9 的断言子集：Correction Rules Change 不重新调用 Whisper / Raw Hash 不变 / 新 Normalization Revision / Paragraph Formatter Change 只新建 Render Revision / Normalized 可复用 / Completed Processing Run 不被 Revision 回滚 / Canonical 默认不覆盖。
- Stage1~8 回归（八回归不断链；`src/stage1-8/` diff 为空）。

## Out of Scope

- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 零新增写；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite + Golden Dataset/CER/词准确率（本 Stage 只做 Case 4/5/6 计数 + 规则/格式单测 + 合成夹具派生；文本内容不断言词准确率）。
- Stage12 全部：Menu Bar。
- LLM 改写润色（任何总结/改写/润色/校稿/语义猜测；Correction 与 Paragraph 均为确定性纯函数，出现 LLM/云调用即 FAIL）。
- §47 规则序变更与阈值调优式重设计（规则序冻结只消费；新版 formatter 只 bump 版本化定值并记入 profile，不做开放式调优）。
- 派生 mechanics 重造（stage3 `derive`/`artifact_commit` 语义沿用只读复用，不复制不重写；为复用改 stage3 原文即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实目录扫描/写入/真实 Obsidian 库触碰（用户明确：真实长视频一律不测直到产品完成；测试一律指向合成目录 + 外置 Data Root；canonical 只用诱饵文件）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、`src/stage8/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S9-T01 新版 Correction 规则 + Case 4 延续（§45/§29） | P0 | builder | TODO | 输入：stage3 `normalize`/`derive_on_correction_change` 只读复用 + COMMITTED Raw（只读）+ §45/§29。输出：`src/stage9/rules_v2.py`（`RULES_REVISION="v2"` 版本常量 + 新版规则表增改条目：只增高度确定专业词替换，出现模糊/语义/LLM 即 FAIL）+ `src/stage9/derive_v2.py` 内 Case 4 装配（调 stage3 公开 API 建新 NormRev→下游新 Rendered；本文件永不 import `stage1.asr.run_asr_single_file`）。验收：Case 4（Whisper 增量 0、Raw hash 同、新 NormRev 行 + 新 Normalized Artifact hash==行记录、新 Rendered、诱饵 md 不变、Run 全程 COMPLETED）+ 新旧规则同输入分歧可复现（仅规则命中处文本变，其余逐字节一致）。禁动 `src/stage1-8/`；Whisper 调用 0；新规则版本只进 normalization profile。 |
| S9-T02 新版 Paragraph 格式 + Case 5 延续（§47/§30） | P0 | builder | TODO | 输入：S9-T01 的新 Normalized Artifact（只读）+ stage3 `render`/`derive_on_formatter_change` 只读复用 + §47/§30。输出：`src/stage9/formatter_v2.py`（`FORMATTER_VERSION="v2"` + 新版参数定值，原样记入 render profile；规则序 Long Pause > Strong Punctuation > Target Length > Hard Max 原样保留，改序即 FAIL；纯确定性格式化，无 LLM/润色）+ `derive_v2.py` 内 Case 5 装配（复用同一 `normalized_artifact_id`，只建新 RenderRev + 新 Rendered）。验收：Case 5（Raw 同、normalized ID 同且 NormRev 数增量 0、新 RenderRev 行 + 新 Rendered、诱饵 md 不变）+ Paragraph 规则序单测（长停顿/强标点/目标长/硬上限各一例，新旧 formatter 分歧仅来自版本化参数且可复算）。禁动 `src/stage1-8/`；Whisper 调用 0；新 formatter 版本/参数只进 render profile。 |
| S9-T03 Stage9 验收套件 + §72 子集门 + Stage1~8 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S9-T01–T02 产物 + `src/stage1-8/` 只读复用。输出：Stage9 验收报告（happy 链 1 遍：COMMITTED Raw→Case 4 新 NormRev→Case 5 新 RenderRev→lineage 全链可查 + 异常/边界至少 6 个：Case 4（规则变 Whisper 0/Raw 同/新 NormRev/诱饵不变）/ Case 5（格式变 Raw 同/normalized 复用/新 RenderRev/诱饵不变）/ Case 6（Run 全程 COMPLETED）/ LLM 改写企图拒收（规则表塞改写语义用例被拒或 grep 门拦截）/ 规则序篡改拒收 / 同 profile 重放不建新 Revision（幂等或复用证据）；每个用例：前置/动作/期望计数值或 verdict/三表（publish/archive 恒 0；norm/render 新增只许经 stage3 公开 API 并逐行披露）证据/`current_path` 零写证据/Whisper 调用 0 证据/Raw hash 不变证据/诱饵 md 不变证据/最大文件 ≤ 合成小文件声明；结论只落 qa 报告，HANDOFF 只记状态）+ 回归八行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 冻结版规则链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；Stage7 装配→接线→profile executed 仍 PASS；Stage8 合成 wav→VAD→planner→timeline→merge 仍 PASS；`src/stage1-8/` git diff 为空）。验收：任一异常缺失、计数偏离、publish/archive 非空、有 Raw 写、诱饵被改、真实目录/真实库/云/长视频被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S9-T01 → T02 → T03 严格串行（同一 Raw→新 Normalized→新 Rendered 因果链；Case 5 的“normalized 复用、NormRev +0”计数证据必须在 Case 4 新 NormRev 落盘之后跑，否则复用对象不存在；验收在两件未就绪前跑无收口可查）。
- 角色说明：S9-T01–T02 = builder 实现；S9-T03 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 规则表“顺手”变智能：新条目越加越多，出现模糊匹配/语义改写。缓解：S9-T01 硬门——纯确定性替换审计（无 IO/无网络/无模型 import）+ §45 白名单语义 + LLM/改写关键词 grep 零命中。
- R2 Paragraph“顺手”改规则序：为好看调整 Long Pause 与强标点优先级。缓解：S9-T02 硬门——规则序单测四例 + 改序即 FAIL。
- R3 为复用改 stage3 原文：把冻结版规则表/定值参数直接改成新版最省事但违反加法约束。缓解：新版只进 `src/stage9/`；S9-T03 回归硬门——`src/stage1-8/` git diff 为空。
- R4 派生绕过 Raw 跑出新转写：derive 装配里图方便调了 asr 入口，Case 4/5 的 Whisper=0 破功。缓解：S9-T01 模块级 import 禁令 + grep 审计 + 测试期调用计数恒 0。
- R5 顺手发布覆盖：新 Rendered 看着更好就想回填 canonical。缓解：P0-3 硬门——`publish_records` 恒 0 + 诱饵 md 字节比对；出现写盘即 FAIL（Replace Policy 不属 V1.8，§51）。
- R6 Stage10+ 提前实现：Archive 回填、`current_path` 更新最易“顺手”。缓解：S9-T03 三表行数快照对比 + `current_path` 列级 diff + Stage10+ 关键词 grep 零命中。
- R7 真实长视频/真实目录误测：拿真实课程长视频验规则最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件 + 合成 segments 夹具；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言词准确率。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成输入目录，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；canonical 只用诱饵文件比对“不变”，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件，长文本语义只用合成 segments 夹具证明，词准确率/Golden 属 Stage11+）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` + `src/stage6/` + `src/stage7/` + `src/stage8/` 只读加法（新增只进 `src/stage9/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage10+ 禁入：Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar 一律 Out；Normalization 只做规则替换、Paragraph 只做段落格式化，禁 LLM 改写润色，§47 规则序冻结；Case4/5 延续口径：规则变/格式变均 Whisper 不增、Raw 不变、新 Revision、Canonical 不覆盖）。
