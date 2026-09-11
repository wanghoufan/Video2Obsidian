# PLAN｜Stage 7 Prompt + Vocabulary + Language Strategy（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage6 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING + `src/stage6/` Path Mirror + Unicode/Case 矩阵；Stage1 最小可用 prompt 为 `initial_prompt=None/prompt_chars=0/executed=False/recorded_only=True`，完整 PromptBuilder 留本 Stage）。
> Stage1~Stage6 冻结输入：`src/stage1/`（`run_asr_single_file` 单文件直转 + `initial_prompt=None` + 冻结常量 `FROZEN_*`）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `asr_profile_hash` 身份）与 `src/stage3/`（Revision 链 + 冻结版确定性 Correction 规则表）与 `src/stage4/`（publish 语义）与 `src/stage5/`（三路发现）与 `src/stage6/`（`resolve_canonical` 纯映射）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/` 任一文件（改了即 FAIL；新增只进 `src/stage7/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage7 only）`——本 Stage 只实现 §69 Stage7 定义的事项（Prompt + Vocabulary + Language Strategy，§28 ASR Profile 扩展 + §44 PromptBuilder + §45 确定性边界 + §73 第 15/16/27/28 条 + §72 Derived Revision 子集 + §70 Case 4），Stage8+（VAD 过滤执行/Chunk 执行与 Merge/Absolute Timeline、阈值调优、Normalization + Paragraph 语义升级、Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar）一律 Out，写了即 FAIL；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；prompt budget 恒为 200 tokens、order 恒为 Global→Topic→Creator（Stage0 §9 冻结，真实容量 223 实测，本 Stage 只消费不重调）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“说什么词、用什么话提示模型”的那一块：在 Stage1 最小可用 prompt（`initial_prompt=None`，只记录 budget/order 不执行）之上，实现完整 PromptBuilder 并替换其语义——Global/Topic/Creator 三级词库快照（§2.1/§28 `dictionary snapshot`）→ 真实 Tokenizer 先计数再装配（budget 200，顺序 Global→Topic→Creator，超限头部截断保尾部 Creator，§44 + Stage0 Prompt Capacity 实测）→ 每 Chunk 重建 `initial_prompt`（§73-27）→ Language Strategy 冻结（显式 `zh`，§28 `language strategy`/`language`）→ 扩展字段全部落入 ASR Profile 分层（§73-15，Normalization/Render 侧沿 Stage3 冻结版不升级）→ Case 4 可证明（Correction 规则变更不重跑 Whisper、Raw 不变、新 Normalization Revision，§73-16）→ 专业词 correction 不改变语义（§73-28，精确匹配只修高度确定词，§45）。

## Current Stage

- Stage ID: Stage 7 — Prompt + Vocabulary + Language Strategy（V1.8 §69）
- Goal: 词库存快照（`dictionary_snapshot = sha256` 规范序列化）→ PromptBuilder 纯装配（先计数后装配 + budget 200 + Global→Topic→Creator + 超限去头保尾 + `prompt_builder_version` 常量）→ Language Strategy（`explicit-zh` 冻结 + 引擎显式传 language + 检出值只记录不 BLOCK）→ ASR Profile 扩展（§28 新增字段只进 ASR 层，`prompt.executed=True` 替换 Stage1 `recorded_only` 语义，stage1 文件零触碰）→ 单文件引擎接线（整文件即一 Chunk，合成小音频真调，`initial_prompt` 非空落盘）→ 合成多 Chunk 装配证明（无音频切分，Chunk 执行属 Stage8）→ Case 4 身份语义（同 profile 同 Run 复用 / 词典快照变更 hash 变允许新 Run）→ §73-15/16/27/28 + §72 Derived Revision 子集可证明 → Stage1~6 回归（`src/stage1-6/` diff 为空）。

Stage1~Stage6 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import 冻结常量，不复制不修改）：FROZEN_MODEL_REPO/
  FROZEN_MODEL_REVISION/FROZEN_AUDIO_MODE/FROZEN_WORD_DEFAULT/
  FROZEN_NO_SPEECH_THRESHOLD/DECODE_DEFAULTS（接线参数逐字段对齐；
  transcribe_wav_file 本体不调不改，因其 initial_prompt=None 硬编码）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现
  入口）/ runs.get_or_create_auto_run（AUTO UPSERT；Stage7 只改变 hash 输入
  内容，不改去重 mechanics）/ asr_profile_hash 身份语义（§3.3）
src/stage3/ 原样复用（import，不复制不修改）：normalize（Case 4 / §73-16
  证据经公开 API 取，Correction 应用语义不升级）/ render（零语义变更）
src/stage4/ 零调用（本 Stage 不落 canonical、不碰 publish）
src/stage5/ 零调用（本 Stage 不起 Watcher/Scan/Reconcile）
src/stage6/ 零调用（本 Stage 不做路径映射；Unicode 口径由回归复现不断链）
src/stage7/ 新增：vocabulary.py / prompt_builder.py / language.py（命名以实现
  为准，前缀恒为 stage7，禁止 stage8+ 关键词文件名）
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage7 模块零直写 DB，
  一切行效应只许经 stage2/stage3 公开 API 的脚手架调用并如实披露；
  archive_commits 行数恒为 0；sources.current_path/status/archived_at 零写）
输入音频：外置合成小音频（仓库外独立目录；ffmpeg 本地合成秒级 wav/mp4，
  不扫真实视频目录；文本内容不断言，词准确率属 Golden Dataset，Stage11+）
asr_profile_hash：Stage7 输出新字段参与其输入内容（身份计算用；Stage2 去重
  mechanics 只读复用）
Stage7 Whisper 调用：仅 S7-T03 接线证明用合成小音频调用（次数有界、逐次披露；
  词库快照/装配/语言策略证明一律零调用纯函数）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 Vocabulary 快照可证明（§2.1 Global/Topic/Creator 词库 + §28 `dictionary snapshot`）：`vocabulary.py` 提供三级词表装载（Global/Topic/Creator 分层输入，逐字节原样存，无 encode/slugify/casefold/归一）+ 规范序列化 + `dictionary_snapshot = sha256`（同输入同 hash 差一字节即不同 hash；快照变更可复现举证）；词表只供 prompt 装配与确定性引用，不含任何改写/润色/总结语义（出现 llm/summar/polish/paraphras/rewrite 关键词即 FAIL）；Stage0 实测字数口径（Global 320/Topic 187/Creator 333）仅作装配输入量级参照，不回写架构。
- [ ] P0-2 PromptBuilder 可证明（§44 + Stage0 Prompt Capacity 实测 + §73-27 每 Chunk 重建）：`prompt_builder.py` 提供纯函数 `build_initial_prompt(global_terms, topic_terms, creator_terms, budget_tokens=200)`：真实 Tokenizer（mlx_whisper 真实 tokenizer）先计数再装配 + 装配顺序恒 Global→Topic→Creator + 总量超 200 时去头保尾截断（Creator 尾部优先存活，对应引擎只留尾部 `n_ctx//2-1` = 223 语义，budget 200 恒在其内）+ 输出 `{initial_prompt, token_count<=200, truncated_head, prompt_builder_version}`（版本常量如 `pb-v1`，变更即 profile 变更）；每 Chunk 重建：合成多 Chunk 词项集合各异 → 逐 Chunk 调用各得其 `initial_prompt`（任一 Chunk 复用别 Chunk 结果即 FAIL；本 Stage 只证装配，音频切分执行属 Stage8）；函数本身零 Whisper 调用（模块内出现 transcribe/requests/openai/http 即 FAIL）。
- [ ] P0-3 Language Strategy + ASR Profile 扩展可证明（§28 + §73-15 分层正确）：`language.py` 提供冻结语言策略 `language_strategy="explicit-zh"`（Stage0 全轮自动检出 Chinese，取值只消费不重测）+ 引擎调用显式传 `language="zh"`（确定性，不依赖自动检出方差）+ 引擎返回的检出 language 只记录（advisory， mismatch 永不 BLOCK 转写）；ASR Profile 扩展字段（`language_strategy`/`language`/`dictionary_snapshot`/`prompt_builder_version`/`prompt_profile={budget_tokens:200, order:"Global->Topic->Creator"}`）只进 ASR 层（出现在 normalization/render profile 即 FAIL）；`prompt.executed=True` + `initial_prompt` 非空 + `prompt_chars>0` 替换 Stage1 `recorded_only` 语义（`src/stage1/` diff 为空为硬门，替换的是语义不是文件）；`asr_profile_hash` 输入内容包含新字段规范值（同输入同 hash；任一新字段变更 hash 即变，变了不断言去重 mechanics，只断言输入完备）。
- [ ] P0-4 单文件引擎接线可证明（替换 Stage1 最小可用 prompt 的落地点）：`src/stage7/` 内自有接线函数（复用 stage1 冻结常量逐字段对齐：model/revision/temp-wav 16k mono/word OFF/nst 0.6/单文件单调用/VAD advisory，任一偏离即 FAIL；不 import stage1 的 `transcribe_wav_file` 本体因其 `initial_prompt=None` 硬编码，复制其调用形状而非改其文件）：合成小音频（秒级，外部合成目录）真调 exactly one call → `initial_prompt` 为 P0-2 同输入复算一致（复算差一字节即 FAIL）+ token_count<=200 + profile 落盘 `executed=True`；文本内容不断言（词准确率/Golden/CER 属 Stage11+ 质量门）；接线调用次数逐用例披露且有界（超预算调用即 FAIL）。
- [ ] P0-5 §72/§73 子集门可证明（仅属于 Stage7 的断言）：§73-15（ASR/Normalization/Render Profile 分层正确：新字段只进 ASR 层）PASS + §73-27（Prompt 每 Chunk 重建：合成多 Chunk 各异 prompt）PASS + §73-28（专业词 correction 不改变语义：Stage3 冻结规则表精确匹配复跑，输出除目标词精确替换外逐字节一致，无增删改写）PASS + §73-16 / §72 Derived Revision 子集（Correction Rules Change 不重新调用 Whisper + Raw Hash 不变 + 新 Normalization Revision：经 stage3 公开 API，Whisper 调用计数不变举证）PASS + §70 Case 4（同 Source + 同 asr_profile_hash → Reconciliation 返回既有 AUTO Run 不建新；词典快照 bump → 新 hash → 允许新 Run， mechanics 复 Stage2 只读）PASS。
- [ ] P0-6 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/` git diff 为空；`archive_commits` 行数恒为 0；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL（Archive A/B/C 禁入）；Stage7 代码永不 import/调用 VAD 过滤执行、Chunk 执行/Merge、Absolute Timeline、Paragraph/Render 语义升级、Archive 模块、LaunchAgent、Menu Bar、LLM/云/SDK（`rg "vad_filter|chunk_merge|absolute_timeline|paragraph|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage7/` 零命中举证）；`src/stage7/` 零直写 DB（`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage7/` 零命中；验收证据行只许经 stage2/stage3 公开 API 并逐行披露）；阈值调优零发生（budget/order/VAD thr/Chunk 常量沿冻结值，出现新值即 FAIL）。
- [ ] P0-7 外置合成验收门可证明（TM 已定）：一切输入位于外置合成目录 + 外置 Data Root 内（验收前断言，与真实视频目录/真实 Obsidian 库无交集）；异常路径一律合成副本（原片不动，只动副本；canonical/笔记零触碰，本 Stage 不落 canonical）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告）；任一用例触碰真实目录/发起云调用即 FAIL。

## In Scope

- Global/Topic/Creator 三级词库装载 + 规范序列化 + `dictionary_snapshot`（sha256；变更可复现）。
- 完整 PromptBuilder（真实 Tokenizer 先计数再装配 + budget 200 + Global→Topic→Creator + 超限去头保尾 + `prompt_builder_version` + 每 Chunk 重建 API；替换 Stage1 最小可用 prompt 语义）。
- Language Strategy（`explicit-zh` 冻结 + 引擎显式 language + 检出值 advisory 记录；mismatch 永不 BLOCK）。
- ASR Profile 扩展（§28 新增字段只进 ASR 层；`prompt.executed=True`；`asr_profile_hash` 输入完备）。
- 单文件引擎接线（整文件即一 Chunk；合成小音频真调；exactly one call；`initial_prompt` 复算一致；文本内容不断言）。
- 合成多 Chunk 装配证明（词项集合各异 → prompt 各异；无音频切分无 Merge）。
- Case 4 身份语义（同 profile 同 Run 复用 / 快照 bump 允许新 Run；mechanics 复 Stage2 只读）。
- §72 Derived Revision 子集 + §73-15/16/27/28（见 P0-5；Correction 应用语义沿 Stage3 冻结版，只复跑举证不升级）。
- Stage1~6 回归（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 三层嵌套 Unicode mirror 双算一致；`src/stage1-6/` diff 为空）。

## Out of Scope

- Stage8 全部：VAD 过滤执行 + Chunk 执行/切分 + Chunk Merge + Absolute Timeline（VAD 本 Stage 仍 advisory-only；chunk size/overlap 只做冻结值记录；转写执行本身除 P0-4 单文件接线外不扩展）。
- Stage9 全部：Normalization + Paragraph 语义升级（Correction 规则应用沿 Stage3 冻结版；规则表内容语义升级、段落 formatter 一律不做）。
- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 零新增写；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite + Golden Dataset/CER/词准确率（本 Stage 只做 P0 指定的 Case 4 复用 + 装配单测 + 单文件接线；Cold Boot、Absolute Binary Paths、20 Video Batch 不做）。
- Stage12 全部：Menu Bar。
- 阈值调优：budget/order/VAD thr/Chunk/no_speech 任何调优不做（Stage0 冻结值只消费，变更即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实目录扫描/写入/真实 Obsidian 库触碰（用户明确：真实长视频一律不测直到产品完成；测试一律指向合成目录 + 外置 Data Root；本 Stage 不落 canonical）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S7-T01 Vocabulary 三级词库 + 快照（§2.1/§28） | P0 | builder | TODO | 输入：Stage0 Prompt 实测输入文件口径（Global/Topic/Creator 分层，只做量级参照）+ §28 `dictionary snapshot`。输出：`src/stage7/vocabulary.py`（`load_vocabulary(global_src, topic_src, creator_src)` 逐字节原样装载 + `canonical_serialize(vocab)` 固定字段序 + `dictionary_snapshot(vocab) = sha256` + 精确引用 helper（只做精确词条透传，无模糊/语义逻辑）；模块内无改写语义，出现 llm/summar/polish/paraphras/rewrite/casefold/normalize 即 FAIL）。验收：同输入同 snapshot + 任一词条差一字节 snapshot 即变 + 三级缺一即 FAIL + 全链无归一化 grep 零命中。禁动 `src/stage1-6/`；Whisper 调用 0；只存词条，不做 Correction 应用。 |
| S7-T02 PromptBuilder 先计数再装配 + 每 Chunk 重建（§44/§73-27） | P0 | builder | TODO | 输入：S7-T01 的词库 + Stage0 Prompt Capacity 实测（真实容量 223，budget 200，order Global→Topic→Creator）。输出：`src/stage7/prompt_builder.py`（`build_initial_prompt(global_terms, topic_terms, creator_terms, budget_tokens=200)`：mlx_whisper 真实 tokenizer 先计数再装配 + 顺序恒 Global→Topic→Creator + 超限去头保尾（Creator 尾部优先）+ 输出 `{initial_prompt, token_count<=200, truncated_head_chars/tokens, prompt_builder_version="pb-v1"}` + `build_for_chunks(list_of_term_sets)` 逐 Chunk 重建；预算/顺序/版本全常量，偏离即 FAIL）。验收：三合一超限用例保尾（Creator 词条存活，Global 头部先丢）+ 200 内用例零截断 + token_count 与真实 tokenizer 复算一致 + 合成三 Chunk 词项各异→三 prompt 各异 + 模块内 transcribe/云关键词 grep 零命中。禁动 `src/stage1-6/`；Whisper 调用 0；音频切分不做（Stage8）。 |
| S7-T03 Language Strategy + ASR Profile 扩展 + 单文件引擎接线（§28/§73-15，替换 Stage1 最小 prompt 落地） | P0 | builder | TODO | 输入：S7-T01–T02 + stage1 冻结常量（只读 import 对齐）+ §28 字段表。输出：`src/stage7/language.py`（`LANGUAGE_STRATEGY="explicit-zh"` 冻结 + 引擎显式 `language="zh"` + 检出值 advisory 记录 helper，mismatch 永不 BLOCK）+ `src/stage7/profile.py`（ASR Profile 扩展组装：`language_strategy`/`language`/`dictionary_snapshot`/`prompt_builder_version`/`prompt_profile` 只进 ASR 层 + `prompt.executed=True` + `asr_profile_hash` 输入完备性 helper）+ `src/stage7/transcribe.py`（自有单文件接线：stage1 冻结常量逐字段对齐、exactly one call、VAD advisory、不 import stage1 `transcribe_wav_file` 本体；`initial_prompt` 取 S7-T02 同输入输出）。验收：合成秒级小音频真调 1 次 → `initial_prompt` 与纯函数复算逐字节一致 + token_count<=200 + profile `executed=True`/`prompt_chars>0` + 调用次数=1 + 文本内容不断言 + 任一冻结常量偏离即 FAIL。禁动 `src/stage1-6/`；除本 Task 接线调用外 Whisper 调用 0；不落 canonical；无云调用。 |
| S7-T04 Stage7 验收套件 + §72/§73 子集门 + Stage1~6 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S7-T01–T03 产物 + `src/stage1-6/` 只读复用。输出：Stage7 验收报告（happy 链 1 遍：合成词库→快照→装配（token<=200）→合成小音频接线（initial_prompt 非空复算一致）→profile executed→§73-15/27 双断言 + 异常/边界至少 8 个：超限保尾（Creator 存活）/ 三 Chunk 各异 / 语言检出 mismatch 只记录不 BLOCK / 同 profile 同 Run 复用（Reconcile 不建新 Run）/ 快照 bump 新 hash 允许新 Run / Correction 规则变更 Whisper 调用不变 + Raw 不变 + 新 Normalization Revision（经 stage3 公开 API，计数举证）/ §73-28 冻结规则复跑逐字节（除目标词精确替换）/ Stage8+ 关键词 grep 零命中；每个用例：前置/动作/期望 Count 或 exit 码/`Duplicate Source/Run` 证据/三表（archive 恒 0；norm/render 新增只许经 stage3 公开 API 并逐行披露）证据/`current_path` 零写证据/Whisper 调用有界证据/外置合成目录路径证据/文本内容不断言声明；结论只落 qa 报告，HANDOFF 只记状态）+ 回归六行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；`src/stage1-6/` git diff 为空）。验收：任一异常缺失、计数偏离、archive 新增行、`current_path` 被写、有转写/发布越权写、真实目录/真实库/云被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S7-T01 → T02 → T03 → T04 严格串行（词库快照→装配→语言+profile+接线→验收；T02 在快照口径未冻结前跑无 hash 可对；接线在装配语义前定会把 `initial_prompt=None` 带进引擎；验收在三件未就绪前跑无收口可查）。
- 角色说明：S7-T01–T03 = builder 实现；S7-T04 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 “智能”截断丢掉 Creator：超限时顺手去尾最省事但违反 Creator > Topic > Global。缓解：S7-T02 硬门——去头保尾 + Creator 存活用例 + 真实 tokenizer 复算。
- R2 词库顺手归一化吞掉专业词：`casefold/normalize` 最省事但破坏逐字节与快照稳定。缓解：S7-T01 硬门——逐字节装载 + 归一化关键词 grep 零命中 + 差一字节快照即变。
- R3 语言检出方差污染确定性：依赖自动检出会导致同文件不同结果。缓解：显式 `language="zh"` 冻结 + 检出值只记录；mismatch BLOCK 即 FAIL。
- R4 为接线改 stage1 本体：把 `transcribe_wav_file` 的 `initial_prompt=None` 改成参数最省事但违反加法约束。缓解：stage7 自有接线函数 + S7-T04 回归硬门——`src/stage1-6/` git diff 为空。
- R5 Correction 语义顺手升级：借词库做模糊纠错/润色最易滑向 §2.2 禁止项。缓解：Correction 应用沿 Stage3 冻结版只复跑举证；S7-T01–T03 出现 llm/summar/polish/paraphras/rewrite 即 FAIL。
- R6 真实长视频/真实目录误测：拿真实课程视频验 prompt 最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言。
- R7 Stage8+ 提前实现：Chunk 切分/Merge、VAD 过滤、Paragraph、Archive 回填最易“顺手”。缓解：S7-T04 三表行数快照对比 + `current_path` 列级 diff + Stage8+ 关键词 grep 零命中 + 阈值常量比对。
- R8 profile 分层放错层：新字段顺手写进 normalization/render profile 会破坏 §73-15。缓解：S7-T03 硬门——扩展字段只进 ASR 层，分层断言逐字段过。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成输入目录，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；本 Stage 不落 canonical，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件，文本内容不断言）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` + `src/stage6/` 只读加法（新增只进 `src/stage7/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage8+ 禁入：VAD 过滤执行/Chunk 执行与 Merge/Absolute Timeline、阈值调优、Normalization + Paragraph 语义升级、Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar 一律 Out；禁 LLM/云/总结改写润色；prompt budget 恒 200 tokens、order 恒 Global→Topic→Creator；完整 PromptBuilder 本 Stage 实现，替换 Stage1 最小可用 prompt 语义——替的是语义不是文件，stage1 文件零触碰）。
