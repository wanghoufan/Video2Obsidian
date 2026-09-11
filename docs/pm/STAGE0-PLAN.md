# PLAN｜Stage 0 Technical Benchmark（Video2Obsidian）

> 基线：`docs/2026-09-10 丨 MAC 丨 GPT 网页端 丨 Video2Obsidian 本地视频自动转写工具开发计划-交接上下文 丨 V1.8.md`
> 基线状态：`ARCHITECTURE APPROVED / V1.8 ARCHITECTURE FROZEN / READY FOR STAGE 0`（§75），
> `IMPLEMENTATION NOT YET ACCEPTED / IMPLEMENTATION ACCEPTANCE GATE = OPEN`（§75）。
> 最高约束：`STOP ARCHITECTURE EXPANSION`（§65-71）——VAD Threshold / Chunk Size / Overlap /
> Prompt Budget / Word Timestamp 开关 / FFmpeg Pipe-Temp / Paragraph Length / Worker Count
> 全部是 Stage 0 Benchmark 结论，不是架构问题，不得因此重开架构设计。

## Product Goal

Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：
用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、
自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档（V1.8 §1.2）。
目标设备：Mac mini M4 / 24GB RAM，macOS / Apple Silicon。日常使用只剩“把视频放进目录”
（V1.8 §73 DoD-56）。V1.8 明确不做：AI 总结/改写/润色/校稿、LLM、云端 ASR、任何云 API、
Redis/PostgreSQL、微服务、Docker、消息队列、RAG/Embedding/向量库、复杂 UI（V1.8 §2.2）。

## Current Stage

- Stage ID: Stage 0 — Technical Benchmark（V1.8 §68 / §69）
- Goal: 在 Mac mini M4 24GB 真机上验证 12 项技术基线，冻结 Dependency Versions 与
  Model Revision，输出 `TECHNICAL_BENCHMARK_REPORT.md`，给出 GO（进 Stage 1）/ NOGO 结论。
  本轮禁止进入正式业务功能开发（Stage 1–12 的实现工作全部不在本轮）。

## Stage P0（P0=本 Stage 非做不可、缺它不算完的事项，由 planner 初定、Task Manager 拍板；同时作为 qa / product-reviewer 的 P0 Blocking 参照）

- [ ] P0-1 真实环境采集完成且可复现：macOS 版本/芯片/RAM/Python/FFmpeg/mlx/mlx-whisper
  commit/watchdog/onnxruntime/Silero 版本、model repo + 真实 revision + 本地路径 + 文件大小。
  禁只写 `latest`（V1.8 §66 Pinning 清单）。
- [ ] P0-2 数据集就绪：A（约 5 分钟）/ B（约 30 分钟）/ C（约 60 分钟）中文真实视频，
  合计覆盖普通口播 / AI 专业词 / 币圈词 / 中英混说 / 片头音乐 / 长静音 / 快速讲话。禁假音频
  （合成正弦波/TTS 占位/静音文件冒充）。
- [ ] P0-3 MLX Whisper 在目标机可用，且 `large-v3-turbo` 真实 revision 被验证并锁定；
  若模型不可用，走 P0-12 阻断流程，不自行换模型。
- [ ] P0-4 5 / 30 / 60 分钟真实视频性能基线完成：Model Load Time、RTF、Peak Memory 全量记录。
- [ ] P0-5 Word Timestamp ON / OFF 对比完成并给出默认开关建议（能力必须保留，开关由 Benchmark 定，V1.8 §43）。
- [ ] P0-6 Audio Preprocess 对比完成：FFmpeg Temp vs Pipe，并给出默认选择（优先稳定可恢复）。
- [ ] P0-7 VAD 候选对比完成并给出推荐阈值方向（原则：宁可多送静音，不误删语音）。
- [ ] P0-8 Chunk 候选 5 / 10 / 15 min × Overlap 1 / 2 / 3 s 初始数据完成（只 Benchmark，
  不实现完整 ChunkMerge；Merge 优先级 Core Region Ownership > Absolute Timestamp >
  Overlap Timestamp > Text Similarity，禁整篇 fuzzy dedup，V1.8 §42）。
- [ ] P0-9 Prompt Budget 真实 Capacity 实测完成（禁沿用 `max_tokens=350` 假设；
  按 V1.8 §44 验证 Creator > Topic > Global 装配顺序与真实 Tokenizer 计数）。
- [ ] P0-10 长视频（60 分钟，数据集 C）稳定性结论：完成无 crash、无 OOM、无永久卡死。
- [ ] P0-11 `TECHNICAL_BENCHMARK_REPORT.md` 落盘，含环境/版本/revision/视频信息/原始结果/
  汇总/RTF/内存/对比/建议/异常/Blocking/推荐配置/PASS-FAIL/GO-NOGO（见附录 C 大纲）。
- [ ] P0-12 若 `large-v3-turbo` 或关键依赖阻断：输出 BLOCKING TECHNICAL FINDING 记录
  （环境 + 复现步骤 + 已试排除项 + 影响面），视为 P0 闭环，不悬空、不自行换模型，
  等 Task Manager / 用户定夺（见 Risks）。

## In Scope

- 12 项验证：MLX Whisper 可用性、large-v3-turbo 真实 revision、5/30/60 分钟真实视频性能、
  Word Timestamp ON/OFF 差、FFmpeg Pipe/Temp 表现、VAD 候选、Chunk/Overlap 初始数据、
  Prompt Budget 真实 Capacity、Peak Memory、RTF、Model Load Time、长视频稳定性。
- 真实环境采集（清单见 P0-1；对应 V1.8 §66 锁定项：Python、mlx、mlx-whisper、watchdog、
  onnxruntime、Silero、FFmpeg、Whisper model、Whisper model revision）。
- 数据集 A/B/C 准备与场景覆盖矩阵（普通口播/AI专业词/币圈词/中英混说/片头音乐/长静音/快速讲话）。
- 全部对比项的原始数据 + 汇总 + 推荐配置（推荐配置 = Benchmark 结论，可直接作为 Stage 1
  ASR Profile / VAD profile / ChunkPlanner / PromptBuilder 参数输入，不回写架构文档）。
- Implementation Guardrail 1/2/3 记入 Implementation Notes（见附录 B；Stage 0 只记录、
  不实现，约束 Stage 1+ 的 builder）。
- Stage 0 Gate 13 问评审（见附录 A），输出 GO / NOGO。
- 输出物：`TECHNICAL_BENCHMARK_REPORT.md` 一个文件（大纲见附录 C）。
- 只读 + 跑 Benchmark 脚本 + 写报告；Benchmark 脚本本身是为采集数据而写的临时实验脚本，
  不属于 Stage 1 业务实现，不进业务目录规范评审。

## Out of Scope

- 架构扩张（全部禁止）：改数据库类型（SQLite 以外）、引入 Redis / PostgreSQL / 微服务 /
  Docker（含 Docker Whisper）/ 云端 ASR / LLM / 消息队列 / 分布式锁 / 新模型 / 复杂 UI /
  Obsidian 插件 / SaaS / 手机端 / RAG / Embedding / 向量数据库（V1.8 §2.2 + §65-71）。
- 禁止进入 Stage 1 及之后业务开发：Single Video、Source Provenance、Raw PREPARED/COMMIT、
  Candidate/Source/Processing Run、AUTO Run 去重、SQLite 接入、Single Instance、
  Normalization/Render Revision、Canonical Publish、Watch/Reconcile、Archive、LaunchAgent、
  Golden Dataset、Fault Injection（V1.8 §69 Stage 1–12 全部不在本轮）。
- 禁止实现完整 ChunkMerge（Stage 0 只要各 Chunk 配置下的独立转写数据，不做跨 Chunk 合并实现）。
- 禁止把参数当输入拍板：VAD Threshold / Chunk Size / Overlap / Prompt Budget /
  Word Timestamp 开关 / Paragraph Length / Worker Count 没有“默认值先定”，只能从 Benchmark
  数据里出推荐值。
- 不改 V1.8 架构基线文档、不动治理表（`docs/model/TASK-MODEL-LOG.jsonl` 由执行链按 AGENTS 分工写，
  planner 不代写）、不 push、不碰 secrets。

## Task Breakdown

| Task ID | Priority | Role | Status | Notes |
|---|---|---|---|---|
| S0-T01 环境采集脚本与基线锁定 | P0 | builder | TODO | 输入：目标机 shell；输出：环境清单（含 P0-1 全部字段）+ `pip freeze` 等价物 + `ffmpeg -version` + mlx-whisper commit + model repo/revision/本地路径/文件大小。验收：任一版本字段缺失或写 `latest` 即 FAIL；可与 T02 并行。 |
| S0-T02 数据集 A/B/C 准备与覆盖矩阵 | P0 | builder | TODO | 输入：用户提供的测试视频（见 Human Decisions）；输出：A/B/C 文件清单（时长/分辨率/编码/文件大小/语音场景标注）+ 7 场景覆盖矩阵。验收：任一缺场景或用假音频即 FAIL；可与 T01 并行。 |
| S0-T03 MLX 基线打通 + large-v3-turbo revision 验证 | P0 | builder | TODO | 依赖 T01+T02；输出：模型加载成功证据 + 真实 revision + 单次 5min 转写成功 + Model Load Time。验收：转写失败则不掩盖，直接触发 P0-12 阻断流程。 |
| S0-T04 5/30/60min 性能基线（RTF/内存/加载时间） | P0 | builder | TODO | 依赖 T03；输出：三档视频的 RTF、Peak Memory、Model Load Time 原始记录。单机串行跑，避免资源争抢污染数据。 |
| S0-T05 Word Timestamp ON/OFF 对比 | P0 | builder | TODO | 依赖 T03；在同一视频同一模型配置下只翻转该开关，对比 RTF 差 + 输出差异 + 默认开关建议。可与 T06–T08 在数据层面并行设计、串行执行。 |
| S0-T06 FFmpeg Temp vs Pipe 对比 | P0 | builder | TODO | 依赖 T03；对比转写一致性 + 耗时 + 失败可恢复性；默认推荐优先稳定可恢复（预期 Temp，以数据为准）。Pipe 失败不可恢复即判负，不优化 Pipe。 |
| S0-T07 VAD 候选对比 | P0 | builder | TODO | 依赖 T03；在含长静音/片头音乐的视频上对比候选阈值；验收红线：语音误删 = FAIL 级发现，宁可多送静音。 |
| S0-T08 Chunk/Overlap 网格 + Prompt Capacity 实测 | P0 | builder + qa | TODO | 依赖 T03；Chunk 5/10/15min × Overlap 1/2/3s 只采各配置独立转写数据（不实现 Merge）；Prompt 侧用真实 Tokenizer 计数验证 Engine Capacity 与 Creator > Topic > Global，禁 `max_tokens=350` 假设。builder 采数，qa 核对计数方法。 |
| S0-T09 长视频（60min）稳定性 | P0 | builder | TODO | 依赖 T03，可与 T04 合并执行；输出：C 数据集端到端完成证据 + 异常记录（crash/OOM/卡死任一即 NOGO 级发现，如实记录）。 |
| S0-T10 报告汇总与 Gate 13 问评审 | P0 | builder（汇总）+ qa（核验） | TODO | 依赖 T01–T09；输出 `TECHNICAL_BENCHMARK_REPORT.md`（附录 C 大纲）+ Gate 13 问逐项 PASS-FAIL + GO/NOGO。qa 按“坏例看 exit 码、不看打印”（经验 2026-09-10）核验全部原始数据可复现；结论只落报告，HANDOFF 只记状态。 |

- 并行性说明：T01 ∥ T02；T03 依赖 T01+T02；T04–T09 依赖 T03，设计可并行但真机执行必须串行
  （单台 M4，防内存/CPU 争抢污染 RTF 与 Peak Memory）；T10 依赖全部。qa 核验贯穿 T08/T10，
  失败数据不得重跑掩盖，重跑需注明轮次。
- 角色说明：benchmark 执行=builder，数据核验=qa；code-reviewer / product-reviewer /
  supervisor 按 AGENTS 派工顺序在报告完成后介入，本计划不代派。

## Risks

- R1 `large-v3-turbo` 不可用（如下架/改名/revision 失效/下载失败/HF 不可达）：触发
  BLOCKING TECHNICAL FINDING 流程——如实记录环境+复现步骤+已试排除项，P0-12 闭环，
  不自行换模型、不编 revision；换模型是用户决策（AGENTS 红线）。
- R2 24GB 内存 OOM（尤其 60min + Word Timestamp ON）：Peak Memory 超预算即 NOGO 级发现，
  不降采样掩盖；缓解只能是 Benchmark 结论（如推荐 Chunk 切分值），不是架构改动。
- R3 用户给不出 30/60min 真实中文视频：数据集降级需 Task Manager 批准并在报告 Blocking 节
  声明覆盖缺口；禁拿短视频循环拼接冒充长稳（拼接接缝会污染 VAD/Chunk 数据）。
- R4 测试视频涉隐私/版权：Benchmark 只在本地跑，不上传；报告中视频信息只记脱敏元数据
  （时长/编码/场景标签），不贴原始文本全文。
- R5 单机串行耗时超限：T04–T09 全网格耗时可能数小时，先跑 P0 最小集（A 全对比 + C 长稳），
  再补 B 网格；耗时上限见 Human Decisions。
- R6 旧假设残留（`max_tokens=350`、Pipe 更快等）：一律以实测为准，报告中单列“假设 vs 实测”
  对照行，防止结论被旧数污染。
- R7 假音频/演示视频混入数据集：qa 在 T10 按覆盖矩阵反查来源，无法溯源的视频数据整段作废。

## Human Decisions Needed

- D1 请提供测试视频路径：A（约 5min）、B（约 30min）、C（约 60min）中文真实视频各至少 1 个，
  需合计覆盖普通口播/AI专业词/币圈词/中英混说/片头音乐/长静音/快速讲话（缺的场景请明示）。
- D2 模型存放位置与获取方式：`large-v3-turbo` 现有本地路径（如有），或是否允许从 HF 下载
  （约数 GB）及网络/代理方式。
- D3 是否允许在本机安装依赖（pip：mlx / mlx-whisper / watchdog / onnxruntime / Silero 相关）
  与 `brew install ffmpeg`（如缺）；如不允许，请指定已备好的 Python 环境。
- D4 耗时上限：全网格 Benchmark 预计数小时（含 60min 多轮），请给单轮时间盒（如 4h / 隔夜可跑）。
- D5 确认执行机即 Mac mini M4 24GB 本机（还是另有真机）；报告落盘位置默认
  `docs/qa/TECHNICAL_BENCHMARK_REPORT.md` 是否接受。
- D6 GO/NOGO 拍板人：Gate 13 问若出现 NOGO 项，由谁定夺（降级进 Stage 1 / 补测 / 停线）。

---

## 附录 A｜Stage 0 Gate 13 问（GO/NOGO 逐项 PASS-FAIL，映射 V1.8 §72 Stage 0/Runtime）

1. MLX Whisper 在目标机可运行？（§72: Mac mini M4 Technical Benchmark PASS）
2. `large-v3-turbo` 真实 revision 已锁定（repo+revision+本地路径+大小齐全）？（§72: Whisper Model Revision Locked）
3. 依赖版本已冻结且可复现（无 `latest`）？（§72: Dependency Versions Locked）
4. 5 分钟视频 RTF 达标并记录？ 5. 30 分钟视频 RTF 达标并记录？ 6. 60 分钟视频端到端完成，
   无 crash / OOM / 永久卡死？（§72: RTF / Peak Memory 数据完成；§67 Crash 范围）
5. Peak Memory 在 24GB 预算内（含 Word Timestamp ON 最坏档）？
6. Model Load Time 已量化且可接受（常驻/冷启策略有数据支撑）？
7. Word Timestamp ON/OFF 差已量化，默认开关有数据结论？（§72: Word Timestamp Benchmark PASS）
8. VAD 候选有结论且语音误删 = 0？（§72: VAD Benchmark PASS；红线：宁多送静音不误删语音）
9. FFmpeg Temp/Pipe 有结论且默认选择 = 稳定可恢复侧？
10. Chunk/Overlap 初始数据齐全且给出 Stage 1 推荐值（不实现 Merge）？
11. Prompt 真实 Capacity 已实测，Creator > Topic > Global 与真实 Tokenizer 计数验证通过？
12. 全部 BLOCKING 事项或已清零、或已有 FINDING 记录并获定夺？有一项无记录阻断即 NOGO。
- 判定：13 问全 PASS → GO（进 Stage 1，按 §69 顺序从 Single Video 起）；任一 FAIL →
  NOGO（补测 / 降级 / 停线由 D6 拍板人定）。

## 附录 B｜Implementation Notes（Guardrail 1/2/3：Stage 0 只记录，约束 Stage 1+ builder）

- G1 AUTO Run 顺序：AUTO Processing Run 的创建必须在 Logical Source 注册之后，
  NOT NULL 链（Source → Run）不得倒置；Stage 0 报告需声明 Benchmark 脚本未预设任何
  绕过该顺序的捷径。
- G2 Strong Hash 前后 fstat 对比：Transcription 后 / Archive 前的 Mandatory Strong SHA256
  （V1.8 §25/§26）必须附带前后 fstat 对比（device / inode / size / mtime_ns），
  防 Same size + same mtime + different bytes（V1.8 Case 8）与转写中 Source 被改；
  Stage 0 如涉及大文件哈希性能，一并记录耗时。
- G3 Crash Recovery 后、Archive 前重确认 Publish 存在且用户编辑优先：Rendered Artifact ≠
  Canonical Publish（V1.8 §30/§49/§50）；恢复流程在 Archive 前必须重确认 Publish 记录存在，
  且用户已编辑的 Markdown 覆盖次数恒为 0；Stage 0 不实现恢复流程，只把本条记为
  Stage 10/11（Archive/LaunchAgent）的前置约束。

## 附录 C｜`TECHNICAL_BENCHMARK_REPORT.md` 大纲（P0-11 验收模板）

1. 环境（P0-1 全字段） 2. 依赖与模型版本 + revision 冻结表 3. 数据集 A/B/C 信息与场景覆盖矩阵
2. 原始结果（每轮：配置/耗时/RTF/Peak Memory/Model Load/输出哈希/日志位置）
3. 汇总表（三档视频 × 关键配置） 6. RTF 分析 7. 内存分析 8. 对比结论
   （Word Timestamp / Pipe-Temp / VAD / Chunk-Overlap / Prompt Capacity） 9. 推荐配置
   （Stage 1 Profile 参数输入） 10. 异常记录 11. Blocking FINDING（无则写 NONE）
4. PASS-FAIL（Gate 13 问逐项） 13. GO / NOGO。
