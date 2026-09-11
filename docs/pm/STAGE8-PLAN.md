# PLAN｜Stage 8 VAD + Chunk + Absolute Timeline（Video2Obsidian V1.8 §69）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`V1.8 ARCHITECTURE FROZEN`（§71）+ Stage1~Stage7 实现已落盘（`src/stage1/` 单视频 Raw 闭环 + `src/stage2/` Candidate/Source/AUTO Run + 中央 `<data_root>/data/state.db` + Single Instance + `src/stage3/` Revision 链 + `src/stage4/` Initial Canonical Publish + `src/stage5/` Watch/Scan/Reconcile 到 RUNNING + `src/stage6/` Path Mirror + Unicode/Case 矩阵 + `src/stage7/` Vocabulary/PromptBuilder/Language Strategy + 单文件接线；VAD 全链 advisory-only，Chunk/Merge/Timeline 均未实现）。
> Stage1~Stage7 冻结输入：`src/stage1/`（`run_asr_single_file` 单文件直转 + 冻结常量 `FROZEN_*` + word 默认 OFF + nst 0.6 + temp-wav 16k mono）与 `src/stage2/`（`candidate.discover` 唯一发现入口 + `runs.get_or_create_auto_run` UPSERT + `asr_profile_hash` 身份）与 `src/stage3/`（Revision 链 + 冻结版确定性 Correction 规则表）与 `src/stage4/`（publish 语义，只读复用）与 `src/stage5/`（三路发现语义，只读复用）与 `src/stage6/`（`resolve_canonical` 纯映射，只读复用）与 `src/stage7/`（`load_vocabulary`/`build_initial_prompt`/`build_for_chunks`/`LANGUAGE_STRATEGY=explicit-zh`/`build_asr_profile`，只读复用不复制）——本 Stage 只做加法，不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/` 任一文件（改了即 FAIL；新增只进 `src/stage8/`）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）+ `STOP EXPANSION（Stage8 only）`——本 Stage 只实现 §69 Stage8 定义的事项（VAD + Chunk + Absolute Timeline，§42 Audio/VAD/Chunk/Timeline + §43 Segment/Word Timestamp 能力 + §28 ASR Profile 内 vad/chunking 字段 + §73 第 24/25/26 条 + §73-27 与 Stage7 联动），Stage9+（Normalization + Paragraph 语义升级、Archive A/B/C + `current_path` 更新、LaunchAgent + Fault 全套件 + Golden、Menu Bar）一律 Out，写了即 FAIL；§2.2 禁止项（LLM/云/总结改写润色）出现即 FAIL；过滤式 VAD 禁令延续——本 Stage 完整 VAD 只做 advisory + chunk 切分 + 绝对时间轴，不做语音过滤；chunk 常量恒为 size 10min / overlap 2s（Stage0 §9 冻结，只消费不重调）。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。目标设备：Mac mini M4 / 24GB RAM。本 Stage 只做其中“长音频怎么切、切完时间怎么对”的那一块：在 Stage1 单文件直转与 Stage7 单文件接线之上，实现 VAD advisory 观测（silero thr 0.3–0.5，只记录不参与过滤）→ ChunkPlanner 纯切分（size 10min / overlap 2s，Core Region Ownership）→ 每 Chunk 独立转写（复用 Stage7 `build_for_chunks` 每 Chunk 重建 `initial_prompt`）→ Absolute Timeline 映射（Relative + Absolute 双时间戳）→ Overlap Merge（优先级 Core > Absolute > Overlap > Text Similarity，禁整篇 fuzzy dedup，§42）→ 合并后 Raw 语义与单文件一致（Word Timestamp 能力保留、默认 OFF 不扩展）→ VAD/chunking 字段落入 ASR Profile 分层（§28，只进 ASR 层）→ §73-24/25/26 可证明 → Stage1~7 回归（`src/stage1-7/` diff 为空）。

## Current Stage

- Stage ID: Stage 8 — VAD + Chunk + Absolute Timeline（V1.8 §69）
- Goal: VAD advisory 观测（silero thr 0.3–0.5，`filtering=False` 硬门）→ ChunkPlanner 纯函数（10min/2s 常量 + 边界数学 + core/overlap 归属）→ Absolute Timeline 纯映射（relative→absolute 偏移 + 双时间戳保留）→ Overlap Merge（四优先级 + 禁 fuzzy）→ Chunk 执行接线（合成小音频真调 + 每 Chunk prompt 重建 + 调用次数=chunk 数举证）→ ASR Profile 扩展（vad/chunking 只进 ASR 层）→ §73-24/25/26 + §73-27 联动可证明 → Stage1~7 回归（`src/stage1-7/` diff 为空）。

Stage1~Stage7 地基复用约定（加法约束）：
```text
src/stage1/ 原样复用（import 冻结常量，不复制不修改）：FROZEN_MODEL_REPO/
  FROZEN_MODEL_REVISION(a4aaeec0)/FROZEN_AUDIO_MODE(temp-wav 16k mono)/
  FROZEN_WORD_DEFAULT(OFF)/FROZEN_NO_SPEECH_THRESHOLD(0.6)/DECODE_DEFAULTS/
  worker 恒 1（接线参数逐字段对齐；单文件本体不调不改）
src/stage2/ 原样复用（import，不复制不修改）：candidate.discover（唯一发现
  入口）/ runs.get_or_create_auto_run（AUTO UPSERT；Stage8 只改变 hash 输入
  内容，不改去重 mechanics）/ asr_profile_hash 身份语义（§3.3）
src/stage3/ 原样复用（import，不复制不修改）：normalize/render/lineage 公开
  API（Merge 输出经既有 Raw 门验，不升级 Correction/Render 语义）
src/stage4/ 零调用（本 Stage 不落 canonical、不碰 publish；回归只读查）
src/stage5/ 零调用（本 Stage 不起 Watcher/Scan/Reconcile；回归语义不断链）
src/stage6/ 零调用（本 Stage 不做路径映射；回归双算不断链）
src/stage7/ 只读复用（import，不复制不修改）：load_vocabulary/
  build_initial_prompt/build_for_chunks（每 Chunk 重建）/
  LANGUAGE_STRATEGY=explicit-zh/build_asr_profile（ASR 层扩展位延续）
src/stage8/ 新增：vad.py / chunk_planner.py / timeline.py / merge.py /
  transcribe_chunks.py（命名以实现为准，前缀恒为 stage8，禁止 stage9+
  关键词文件名如 paragraph/archive/launchagent/menu）
中央库位置：<data_root>/data/state.db（沿用 Stage2；Stage8 模块零直写 DB，
  一切行效应只许经 stage2/stage3 公开 API 的脚手架调用并如实披露；
  archive_commits 行数恒为 0；sources.current_path/status/archived_at 零写）
输入音频：外置合成小音频（仓库外独立目录；ffmpeg 本地合成秒级 wav/mp4，
  不扫真实视频目录；长视频不测，用例最大文件 ≤ 合成小文件；文本内容不
  断言，词准确率属 Golden Dataset，Stage11+）
asr_profile_hash：Stage8 输出新字段（vad_profile/chunking_profile）参与其
  输入内容（身份计算用；Stage2 去重 mechanics 只读复用）
Stage8 Whisper 调用：仅 S8-T04 接线证明用合成小音频调用（次数=chunk 数、
  有界、逐次披露；VAD/Planner/Timeline/Merge 证明一律零调用纯函数）
```

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照。TM已拍板：按初定通过，本节即执行口径）

- [ ] P0-1 VAD advisory 可证明（§42 + Stage0 §9 冻结）：`vad.py` 提供观测函数（silero thr 0.3–0.5 档输入，输出语音比/分段标注仅记录）：同输入同标注 + thr 档变更可复现分歧方向 + `filtering=False` 硬门（模块内出现 filter/drop/remove_silence/gate_audio 即 FAIL；任一用例证明某段音频被 VAD 丢弃即 FAIL）；VAD 结果永不回灌音频选择（接线侧以音频切分前后字节一致举证）；阈值零调优（出现 0.3–0.5 之外新值即 FAIL）。
- [ ] P0-2 ChunkPlanner 可证明（§42 + chunk 10min/overlap 2s 冻结）：`chunk_planner.py` 提供纯函数 `plan_chunks(duration_s, size_s=600, overlap_s=2)`：常量偏离即 FAIL + 输出 `[{index, start_s, end_s, core_start_s, core_end_s}]`（首尾边界无负值无越界 + 相邻 overlap 恒 2s + core 归属无缝无重叠）+ 短音频（<1 chunk）恰 1 chunk + 零时长/负时长 fail-closed + 函数本身零 Whisper 调用；音频切分执行（ffmpeg 按边界落盘）由 S8-T04 复用本函数输出， planner 本体不碰音频。
- [ ] P0-3 Absolute Timeline + Merge 可证明（§42 Merge 优先级 + §43 双时间戳）：`timeline.py` 提供纯映射（`absolute = chunk_start + relative`，Relative + Absolute 双保留，任一丢失即 FAIL）+ `merge.py` 提供 overlap 合并（优先级 Core Region Ownership > Absolute Timestamp > Overlap Timestamp > Text Similarity + 禁整篇 fuzzy dedup，出现 fuzzy/similarity 全局去重即 FAIL）：合成 segment 夹具（overlap 区双份输入）→ 合并后 core 区恰一份 + absolute 单调递增 + 文本除 overlap 去重外逐字节一致；Word Timestamp 能力保留（word ON/OFF 双透传不断链，默认 OFF 不扩展，ON 成本不断言）。
- [ ] P0-4 Chunk 执行接线可证明（Stage7 联动 + §73-27 每 Chunk 重建落地）：`transcribe_chunks.py` 内自有接线（复用 stage1 冻结常量逐字段对齐：model/revision/temp-wav 16k mono/word OFF/nst 0.6/VAD advisory，任一偏离即 FAIL；prompt 取 stage7 `build_for_chunks` 只读复用，任一 Chunk 复用别 Chunk prompt 即 FAIL）：合成小音频（秒级，外置合成目录；planner 在小尺寸下仍输出 1 chunk，或用合成短 chunk 列表驱动多 chunk 接线，真实长视频不测）真调 → 调用次数 == chunk 数 + 各 Chunk `initial_prompt` 与纯函数复算逐字节一致 + 合并后 segments 经 timeline/merge 输出 absolute 单调 + 文本内容不断言（词准确率/Golden/CER 属 Stage11+）；调用次数逐用例披露且有界（超预算调用即 FAIL）。
- [ ] P0-5 §72/§73 子集门可证明（仅属于 Stage8 的断言）：§73-24（Segment 正常：合并后 segments 非空 + absolute 单调）PASS + §73-25（Word Timestamp 能力正常：OFF 默认透传 + ON 能力不断链，不扩展语义）PASS + §73-26（Absolute Timeline 正确：合成 overlap 夹具双算一致 + 接线输出 absolute == chunk_start + relative）PASS + §73-27 联动（Prompt 每 Chunk 重建：合成多 Chunk 词项各异 → 各 Chunk prompt 各异，接线侧复算一致）PASS + §73-15 分层延续（vad/chunking 新字段只进 ASR 层，出现在 normalization/render profile 即 FAIL）。
- [ ] P0-6 STOP EXPANSION 门可证明：`src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/` git diff 为空；`archive_commits` 行数恒为 0；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL（Archive A/B/C 禁入）；Stage8 代码永不 import/调用 Normalization + Paragraph 语义升级、Archive 模块、`current_path` 回填、LaunchAgent、Menu Bar、LLM/云/SDK（`rg "paragraph|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage8/` 零命中举证）；`src/stage8/` 零直写 DB（`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage8/` 零命中；验收证据行只许经 stage2/stage3 公开 API 并逐行披露）；阈值调优零发生（VAD thr/model/nst/word/chunk size-overlap/prompt budget-order 沿冻结值，出现新值即 FAIL）。
- [ ] P0-7 外置合成验收门可证明（TM 已定）：一切输入位于外置合成目录 + 外置 Data Root 内（验收前断言，与真实视频目录/真实 Obsidian 库无交集）；异常路径一律合成副本（原片不动，只动副本；canonical/笔记零触碰，本 Stage 不落 canonical）；真实长视频一律不测（用例最大文件 ≤ 合成小文件，作为 PASS 条件写进报告；多 chunk 长时语义只用 planner 数学 + 合成 segment 夹具证明，不用长音频）；任一用例触碰真实目录/发起云调用即 FAIL。

## In Scope

- VAD advisory 观测（silero thr 0.3–0.5，只记录不参与过滤；`filtering=False` 硬门）。
- ChunkPlanner 纯切分（size 10min / overlap 2s 常量 + 边界数学 + core/overlap 归属；短音频 1 chunk；fail-closed）。
- Absolute Timeline 纯映射（relative→absolute + 双时间戳保留 + 单调性）。
- Overlap Merge（四优先级 Core > Absolute > Overlap > Text Similarity；禁整篇 fuzzy dedup）。
- Chunk 执行接线（合成小音频真调；调用次数 == chunk 数；每 Chunk prompt 经 stage7 只读重建；文本内容不断言）。
- ASR Profile 扩展（§28 vad profile/chunking profile 只进 ASR 层；`asr_profile_hash` 输入完备）。
- Word Timestamp 能力保留（默认 OFF，双透传不断链，不扩展）。
- §72/§73 子集（§73-24/25/26 + §73-27 联动 + §73-15 分层延续）。
- Stage1~7 回归（七回归不断链；`src/stage1-7/` diff 为空）。

## Out of Scope

- Stage9 全部：Normalization + Paragraph 语义升级（Correction 规则应用沿 Stage3 冻结版；段落 formatter、目标长度/硬上限调优一律不做）。
- Stage10 全部：Archive A/B/C + `current_path` 更新（`archive_commits` 零新增写；`sources.current_path`/`status`/`archived_at` 任一被写即 FAIL）。
- Stage11 全部：LaunchAgent + 完整 Fault Injection Suite + Golden Dataset/CER/词准确率（本 Stage 只做 P0 指定的接线计数 + planner/timeline 单测 + 合成夹具合并；Cold Boot、Absolute Binary Paths、20 Video Batch 不做）。
- Stage12 全部：Menu Bar。
- 过滤式 VAD（任何语音丢弃/静音移除/门控音频选择；VAD 结果回灌切分即 FAIL）。
- 阈值调优：VAD thr/chunk size-overlap/word/nst/budget/order/model 任何调优不做（Stage0 冻结值只消费，变更即 FAIL）。
- 任何 §2.2 禁止项：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI、Obsidian 插件、SaaS/手机端/浏览器上传、iCloud File Coordination、新模型、自动覆盖用户笔记、Reprocess UI、复杂历史版本 UI。
- 真实长视频测试与真实目录扫描/写入/真实 Obsidian 库触碰（用户明确：真实长视频一律不测直到产品完成；测试一律指向合成目录 + 外置 Data Root；本 Stage 不落 canonical）。
- 不改 `src/stage1/`、`src/stage2/`、`src/stage3/`、`src/stage4/`、`src/stage5/`、`src/stage6/`、`src/stage7/`、不改 V1.8 架构基线、不动治理表（账本由执行链按 AGENTS 分工写，planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S8-T01 VAD advisory 观测 + profile 输入（§42/Stage0 §9） | P0 | builder | TODO | 输入：Stage0 VAD 实测口径（silero thr 0.3–0.5，advisory only，禁过滤）+ §28 `VAD profile`。输出：`src/stage8/vad.py`（`observe_vad(wav_path, threshold)` 只标注不丢音频 + `vad_profile()` 返回冻结档常量 + `is_advisory_only()=True` 硬门；模块内出现 filter/drop/remove_silence/gate 即 FAIL）。验收：合成秒级 wav 双 thr 可复现（0.3 与 0.5 同输入稳定输出 + 档间分歧方向可复现）+ 观测前后音频字节一致 + 全链无过滤 grep 零命中。禁动 `src/stage1-7/`；Whisper 调用 0；标注只进 ASR profile，不进 normalization/render。 |
| S8-T02 ChunkPlanner 纯切分（size 10min/overlap 2s） | P0 | builder | TODO | 输入：S8-T01 的 vad 档位（仅作 profile 输入，不驱动切分）+ Stage0 Chunk 推荐值（10min/2s）。输出：`src/stage8/chunk_planner.py`（`plan_chunks(duration_s, size_s=600, overlap_s=2)` 纯函数 + `CHUNK_SIZE_S=600`/`CHUNK_OVERLAP_S=2` 常量 + core/overlap 归属 + 短音频 1 chunk + 非法输入 fail-closed；常量偏离即 FAIL）。验收：600s→1 chunk + 601s→2 chunk 且 overlap 恒 2s + 1200s 三 chunk core 无缝无重叠 + 合成秒级时长复算一致 + 模块内 transcribe/云关键词 grep 零命中。禁动 `src/stage1-7/`；Whisper 调用 0；VAD 不驱动边界（VAD 驱动即 FAIL）。 |
| S8-T03 Absolute Timeline + Overlap Merge（§42/§43） | P0 | builder | TODO | 输入：S8-T02 的 chunk 边界 + §42 Merge 优先级 + §43 双时间戳。输出：`src/stage8/timeline.py`（`to_absolute(segments, chunk_start_s)` 纯映射 + 双时间戳保留 + 单调校验）+ `src/stage8/merge.py`（`merge_chunks(chunk_segment_lists)` 四优先级 Core > Absolute > Overlap > Text Similarity + 禁整篇 fuzzy dedup + overlap 区恰一份 + absolute 单调）。验收：合成 overlap 夹具（双份输入）→ core 恰一份 + absolute 单调递增 + 非 overlap 区逐字节一致 + word ON/OFF 双透传 + fuzzy 关键词 grep 零命中。禁动 `src/stage1-7/`；Whisper 调用 0；Paragraph/Render 语义零升级。 |
| S8-T04 Chunk 执行接线 + 每 Chunk prompt 重建 + ASR Profile 扩展（§28/§73-27 联动） | P0 | builder | TODO | 输入：S8-T01–T03 + stage7 只读复用（`build_for_chunks` + `build_asr_profile` 输入位）+ stage1 冻结常量（只读对齐）。输出：`src/stage8/transcribe_chunks.py`（自有接线：stage1 冻结常量逐字段对齐 + VAD advisory + 每 Chunk 经 stage7 重建 prompt + exactly chunk 数调用 + 输出经 timeline/merge + `chunking_profile={size_s:600, overlap_s:2}`/`vad_profile` 只进 ASR 层 + `asr_profile_hash` 输入完备 helper）。验收：合成秒级小音频真调（调用次数 == chunk 数 + 各 Chunk prompt 与纯函数复算逐字节一致 + 合并 absolute 单调）+ 文本内容不断言 + 任一冻结常量/分层偏离即 FAIL。禁动 `src/stage1-7/`；除本 Task 接线调用外 Whisper 调用 0；不落 canonical；无云调用。 |
| S8-T05 Stage8 验收套件 + §72/§73 子集门 + Stage1~7 回归 | P0 | qa（执行）+ builder（修） | TODO | 输入：S8-T01–T04 产物 + `src/stage1-7/` 只读复用。输出：Stage8 验收报告（happy 链 1 遍：合成 wav→VAD 观测（不过滤）→planner→接线（调用数==chunk 数）→timeline→merge（absolute 单调）→profile 分层→§73-24/25/26/27 联动断言 + 异常/边界至少 8 个：VAD 过滤企图拒收 / planner 非法输入 fail-closed / 短音频 1 chunk / overlap 合并恰一份 / absolute 乱序拒收 / fuzzy dedup 拒收 / 同 profile 同 Run 复用（Reconcile 不建新 Run）/ vad-chunk 字段 bump 新 hash 允许新 Run；每个用例：前置/动作/期望 Count 或 exit 码/三表（archive 恒 0；norm/render 新增只许经 stage3 公开 API 并逐行披露）证据/`current_path` 零写证据/Whisper 调用有界证据/外置合成目录路径证据/文本内容不断言声明/最大文件 ≤ 合成小文件声明；结论只落 qa 报告，HANDOFF 只记状态）+ 回归七行（Stage1 per-job happy 仍 PASS；Stage2 discover→AUTO Run=1 仍 PASS；Stage3 verdict 链仍 PASS；Stage4 单文件 PUBLISHED 仍可查；Stage5 Ready→Scan→Reconcile→RUNNING 语义不断链；Stage6 嵌套 Unicode mirror 双算一致；Stage7 装配→接线→profile executed 仍 PASS；`src/stage1-7/` git diff 为空）。验收：任一异常缺失、计数偏离、archive 新增行、`current_path` 被写、有转写/发布越权写、真实目录/真实库/云/长视频被碰、结论写进 HANDOFF 代报告，均为 FAIL。 |

- 并行性说明：S8-T01 → T02 → T03 → T04 → T05 严格串行（VAD 口径→切分边界→时间线合并→接线→验收；planner 在 VAD 口径未冻结前跑无 profile 可对；merge 在边界未冻结前跑无归属可验；接线在装配与边界前定会把错 prompt 带进错 Chunk；验收在四件未就绪前跑无收口可查）。
- 角色说明：S8-T01–T04 = builder 实现；S8-T05 = qa 执行验收 + builder 修；code-reviewer / product-reviewer / supervisor 按 AGENTS 派工顺序在计划完成后介入，本计划不代派。

## Risks

- R1 VAD 顺手做过滤：静音移除最省事但违反 advisory 红线。缓解：S8-T01 硬门——`filtering=False` + 观测前后音频字节一致 + 过滤关键词 grep 零命中。
- R2 Chunk 常量顺手调优：按合成小文件改小 size 最易验证但违反 10min/2s 冻结。缓解：S8-T02 硬门——常量偏离即 FAIL + 多 chunk 长时语义只用数学与夹具证明，不用长音频。
- R3 Merge 顺手 fuzzy 全篇去重：文本相似度全局去重最省事但违反 §42 禁令。缓解：S8-T03 硬门——四优先级 + overlap 区外逐字节一致 + fuzzy 关键词 grep 零命中。
- R4 Timeline 丢一侧时间戳：只留 absolute 最省事但违反 §43 双保留。缓解：S8-T03 硬门——Relative + Absolute 双断言 + 单调校验。
- R5 接线复用错 prompt：全 Chunk 共用一个 prompt 最省事但违反 §73-27。缓解：S8-T04 硬门——每 Chunk 经 stage7 只读重建 + 复算逐字节一致。
- R6 profile 分层放错层：vad/chunking 顺手写进 normalization/render 会破坏 §73-15。缓解：S8-T04 硬门——新字段只进 ASR 层，分层断言逐字段过。
- R7 真实长视频/真实目录误测：拿真实课程长视频验 chunk 最“真实”但违反用户明确禁令。缓解：TM 已定——一律合成小文件；用例最大文件 ≤ 合成小文件写进报告 PASS 条件；文本内容不断言。
- R8 Stage9+ 提前实现：Paragraph、Archive 回填、`current_path` 更新最易“顺手”。缓解：S8-T05 三表行数快照对比 + `current_path` 列级 diff + Stage9+ 关键词 grep 零命中 + 阈值常量比对。

## Human Decisions Needed

- 无，按TM已定执行（本计划无阻塞项，不问人）。
- TM 已定事项备忘（执行，不复议）：① 外置测试目录（仓库外独立 Data Root + 独立合成输入目录，Stage1 `/tmp/s1t*` 与 Stage2 H2 外置目录模式延续）；② 异常路径一律用合成副本（原片不动，只动副本；本 Stage 不落 canonical，不碰真实笔记）；③ 真实长视频一律不测直到产品完成（用户明确，用例最大文件为合成小文件，多 chunk 长时语义只用 planner 数学 + 合成 segment 夹具证明，文本内容不断言）；④ `src/stage1/` + `src/stage2/` + `src/stage3/` + `src/stage4/` + `src/stage5/` + `src/stage6/` + `src/stage7/` 只读加法（新增只进 `src/stage8/`，diff 为空为硬门）；⑤ STOP EXPANSION（Stage9+ 禁入：Normalization + Paragraph 语义升级、Archive A/B/C + `current_path` 更新、LaunchAgent、Menu Bar 一律 Out；禁 LLM/云/总结改写润色；VAD Advisory 禁令延续——过滤式 VAD 禁入，本 Stage 完整 VAD 只做 advisory + chunk 切分 + 绝对时间轴；chunk 恒为 10min/overlap 2s；Stage0 冻结值作 Profile 输入，只消费不重调）。
