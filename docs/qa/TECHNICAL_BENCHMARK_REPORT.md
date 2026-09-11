# TECHNICAL_BENCHMARK_REPORT｜Stage 0（Video2Obsidian V1.8 §68）

- 执行角色：builder（单机串行，真机无争抢）
- 执行机：Mac mini M4 / 24GB（本机）
- 时间盒：4h 口头 deadline 内完成最小集（A 全对比 + B 部分网格 + C 累计长稳）；B 全网格（5/10/15min × 1/2/3s 共 9 格）声明为补测缺口，见 §10
- 报告日期：2026-09-10（实际执行 2026-09-10 深夜～09-11 凌晨，日期取任务 date=2026-09-10）
- 原始记录：`docs/qa/benchmark_stage0/results/`（每轮 JSON + 转写 txt + 日志；JSON 含配置/耗时/RTF/Peak Memory/Load/输出哈希/日志位）
- 临时脚本：`docs/qa/benchmark_stage0/s0_*.py`（实验脚本，不进业务目录；未实现任何 Stage 1 业务与 ChunkMerge）
- 复现：`results/` 内 JSON 的 `media` 为绝对路径，`venv` 为临时环境（Python 3.12.13 + 下表冻结版本）；`pip-freeze.txt`、`env.json` 同目录

## 1. 环境（P0-1 全字段）

- macOS 26.6（Build 25G72），Mac mini（Mac16,10），芯片 Apple M4（arm64，10 核 4P+6E），内存 24 GB
- FFmpeg 8.1.2（`/opt/homebrew/bin/ffmpeg`，Apple clang 21.0.0 构建，含 audiotoolbox/videotoolbox/neon）
- Python 3.12.13（临时 venv；系统 python3 为 3.9.6，无 mlx，故新建 venv，见异常 §10-A）
- 无任一字段缺失，无 `latest`（冻结表见 §2）

## 2. 依赖与模型版本冻结表（P0-1 / P0-3）

| 项 | 版本 / 值 |
|---|---|
| Python | 3.12.13 |
| mlx | 0.32.2（+ mlx-metal 0.32.2） |
| mlx-whisper | 0.4.3（PyPI 安装；无 git commit，direct_url 为空，`pip-freeze.txt` 可复现） |
| watchdog | 6.0.0 |
| onnxruntime | 1.29.0 |
| silero-vad | 6.2.1（含 torch 2.14.0 / torchaudio 2.11.0 / numpy 2.5.3 / huggingface_hub 1.31.0） |
| FFmpeg | 8.1.2 |
| Whisper model repo | `mlx-community/whisper-large-v3-turbo` |
| Model revision | `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`（`main` 分支头；`refs/main` 与 snapshot 目录名双重验证一致） |
| 本地路径 | `~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo/snapshots/a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb` |
| 文件大小 | weights.safetensors 1613977612 bytes（1.5G）+ config.json/README/attributes（≈2KB） |
| 语言检出 | 中文（全部转写运行自动检出 `Detected language: Chinese`） |

## 3. 数据集 A/B/C 与场景覆盖矩阵（P0-2）

素材目录：`008林粒粒AI编程/`（中文 AI 编程口播，全部 h264 2560×1600 + aac 44.1kHz 立体声，禁假音频：均为真实课程视频）

| 集 | 文件 | 时长 | 大小 |
|---|---|---|---|
| A（约5min） | 第一周 `01.为什么人人开始Vibe Coding(氛围编程).mp4` | 275.74s（4.6min） | 95907268 B |
| B（约30min → 缺口） | 第三周 `2026-08-03第二周答疑直播-上.mp4` | 1300.60s（21.7min，全库最长单文件） | 462033894 B |
| C（约60min → 缺口） | 无真 60min 单文件。替代：B + 5 文件累计 3959.4s（66.0min）顺序独立转写（非拼接）：`40.…设计数据库`(638.1s) / `37.Codex 进阶`(620.8s) / `36.Codex 基础`(494.1s) / `25.类 SBTI…需求分析`(475.7s) / `18.AI 短剧分镜生成器`(430.1s) | 3959.4s 累计 | — |

场景覆盖矩阵（7 场景）：

| 场景 | 覆盖 | 证据 |
|---|---|---|
| 普通口播 | ✅ | A/B 全程讲话头口播 |
| AI 专业词 | ✅ | 转写检出 Codex/API/Agent/HTML/Docker/Token/Prompt/Whisper 等（拉丁词 A 67 / B 103 / C1 237 个） |
| 币圈词 | ❌ 缺口 | 全库为 AI 编程课程，无币圈内容；声明缺口，未伪造 |
| 中英混说 | ✅ | 同上拉丁词混排；如 A 首句 "Vibe Coding…HTML…" 中英混说 |
| 片头音乐 | ⚠️ 部分 | 转写全文无音乐标记（`♪/音乐/片头` 0 命中）；B 含 5 处 ≥2s 静音（silencedetect -30dB）+ VAD 非语音段 10.8–15.6%，可作静音/间隙代理，无真片头音乐 |
| 长静音 | ⚠️ 部分 | 同上；A 为密集语音（VAD 语音比 99.3%，静音 0 处），B 有间隙；无超长静音样本 |
| 快速讲话 | ✅（观测值） | A 11.25 chars/s、B 7.0 chars/s（转写字符密度；A 语速快） |

## 4. 原始结果（每轮：配置/耗时/RTF/Peak/Load/哈希/日志位）

注：clip 轮的 `rtf` 字段按全片时长计算（偏小），有效 RTF = transcribe_s / clip_len，见 §5。全部 `status=OK`，零失败、零重跑（无掩盖重跑；chunk stdout 解析小故障见 §10-C，不影响数据）。

| run_id | 配置 | prep_s | load_s | tr_s | RTF(记录值) | peak_MB | chars | segs | words | sha12 | 日志 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T03-A-base | A,temp,nst0.6,无prompt | 0.3 | 1.5 | 36.1 | 0.1311 | 1669.4 | 3102 | 276 | — | 67165375bd7e | results/T03-A-base.{json,txt,log} |
| T05-A-wordON | A,temp,word_ts=ON | 0.3 | 1.2 | 50.3 | 0.1822 | 1669.2 | 3039 | 286 | 2575 | 53cf9d92a6fd | results/T05-A-wordON.* |
| T06-A-pipe | A,pipe,numpy | 0.3 | 0.9 | 33.6 | 0.1217 | 3369.0 | 3102 | 276 | — | 67165375bd7e | results/T06-A-pipe.* |
| T07-A-nst03 | A,temp,nst0.3 | 0.2 | 0.8 | 34.9 | 0.1266 | 3324.3 | 3102 | 276 | — | 67165375bd7e | results/T07-A-nst03.* |
| T08-A-promptfull | A,temp,843字prompt(940tok) | 0.3 | 0.7 | 26.4 | 0.0958 | 3319.2 | 2223 | 12 | — | 636c8f86056f | results/T08-A-promptfull.* |
| T04-B-base | B,temp | 0.8 | 0.8 | 102.2 | 0.0785 | 3411.8 | 9098 | 836 | — | 6e2fa01df3b6 | results/T04-B-base.* |
| T05-B-wordON | B,temp,word_ts=ON | 0.9 | 1.2 | 148.8 | 0.1144 | 3411.4 | 9111 | 884 | 7257 | 157e0e679881 | results/T05-B-wordON.* |
| T08-B-ch300 | B clip 0–300s | 0.9 | 1.0 | 23.7 | (0.0182) | 3429.7 | 2233 | 171 | — | 598064274868 | results/T08-B-ch300.* |
| T08-B-ch650a | B clip 0–650s | 0.7 | 0.8 | 50.7 | (0.039) | 3425.7 | 4559 | 379 | — | ef928777d96e | results/T08-B-ch650a.* |
| T08-B-ch650b-ov1 | B clip 649–1300s(ov1) | 0.9 | 1.0 | 52.1 | (0.0401) | 3410.1 | 4559 | 418 | — | f544bd298a91 | results/…-ov1.* |
| T08-B-ch650b-ov2 | B clip 648–1300s(ov2) | 1.1 | 1.1 | 55.4 | (0.0426) | 3413.3 | 4567 | 423 | — | c563d3f43c4e | results/…-ov2.* |
| T08-B-ch650b-ov3 | B clip 647–1300s(ov3) | 0.9 | 0.9 | 52.0 | (0.040) | 3412.5 | 4574 | 417 | — | cf7b624b4e90 | results/…-ov3.* |
| T08-B-ch900 | B clip 0–900s | 0.7 | 0.9 | 69.2 | (0.0532) | 3411.4 | 6541 | 560 | — | c6478c0ba7c8 | results/T08-B-ch900.* |
| T09-C1 | 40,temp | 0.5 | 0.8 | 73.0 | 0.1143 | 3360.2 | 7152 | 610 | — | 08760841d948 | results/T09-C1.* |
| T09-C2 | 37,temp | 0.5 | 0.8 | 76.9 | 0.1239 | 3357.8 | 7284 | 630 | — | 28b81fc521d5 | results/T09-C2.* |
| T09-C3 | 36,temp | 0.5 | 0.9 | 67.3 | 0.1362 | 3344.6 | 5934 | 525 | — | 0655b950e4f3 | results/T09-C3.* |
| T09-C4 | 25,temp | 0.4 | 0.9 | 47.4 | 0.0996 | 3344.6 | 3934 | 391 | — | a0cd5687ec87 | results/T09-C4.* |
| T09-C5 | 18,temp | 0.3 | 0.8 | 52.2 | 0.1213 | 3326.2 | 4135 | 396 | — | c48da7c21ecc | results/T09-C5.* |

VAD（s0_vad.py，Silero，16k 单声道，只观测、未参与任何转写过滤）：

| 音频 | thr 0.3 | thr 0.5 | thr 0.7 | 推理耗时 |
|---|---|---|---|---|
| A 275.7s | 语音比 0.9926（1 段） | 0.9919（1 段） | 0.9897（6 段） | 0.7s |
| B 1300.6s | 语音比 0.8920（157 段） | 0.8625（265 段） | 0.8443（321 段） | 3.2–3.3s |

Prompt Tokenizer 实测（mlx_whisper 真实 tokenizer，zh）：Global 320字→360tok；Topic 187字→244tok；Creator 333字→336tok；三合一 940tok。引擎截断规则（`decoding.py:494-503`）：prompt 只保留**尾部** `n_ctx//2-1` tokens；large-v3 `n_text_ctx=448` → **真实可用容量 223 tokens**。

## 5. 汇总表（三档 × 关键配置）

| 档 | 基线 RTF | Word ON RTF（+Δ） | Peak（worst，含WordON） | Load | 结论 |
|---|---|---|---|---|---|
| A 4.6min | 0.1311（36.1s） | 0.1822（+39%） | 3369.0MB（pipe 轮；temp 轮 1669MB） | 0.7–1.5s | 远优于实时 |
| B 21.7min | 0.0785（102.2s） | 0.1144（+46%） | 3411.8MB | 0.8–1.2s | 远优于实时；长片摊薄后更快 |
| C 累计66min（6文件） | 0.0996–0.1362 | 未测（时间盒，声明缺口） | 3360.2MB | 0.8–0.9s | 零 crash/OOM/卡死 |

Chunk 有效 RTF（tr/clip_len）：300s→0.079；650s→0.078；651–653s(ov1/2/3)→0.080/0.085/0.080；900s→0.077。**Chunk 尺寸不改变 RTF**（≈0.08 恒定）。

## 6. RTF 分析

- 全配置 RTF 0.08–0.18，约为实时的 1/6～1/12；60min 真片按最坏 0.18 估算约 11min 完成，M4 单机可行。
- 长片 RTF 反而更低（B 0.079 vs A 0.131）：模型加载一次性成本被摊薄；内容相关波动（C 各片 0.10–0.14）大于配置波动。
- Word Timestamp 开销稳定 +39–46%，为 Stage 1 常驻/按需策略提供定价依据。
- Overlap 1→3s 对耗时无实质影响（52.1/55.4/52.0s，噪声级），Chunk 边界成本可忽略。

## 7. 内存分析

- 全轮 Peak RSS 1669–3430MB（ru_maxrss，进程级），最坏 3429.7MB（T08-B-ch300），24GB 预算占用 <15%，余量充足；Word ON 不增加内存（B 两轮均为 3411MB）。
- Temp 首轮 1669MB vs 后续轮 ~3.3GB：MLX 统一内存缓存/分配器预热差异所致（各轮为独立进程，非泄漏证据）；Pipe 轮 3369MB 含整段 PCM numpy 常驻（275s×16k×4B ≈ 17.6MB，主体仍是模型/缓存），内存不是 Pipe 否决项（否决项是可恢复性，见 §8）。
- Model Load 0.7–1.5s（含 1.5GB 权重映射），常驻后边际成本≈0；冷启可接受，无需预热策略。

## 8. 对比结论（五项）

1. **Word Timestamp**：ON 耗时 +39%（A）/+46%（B），文本微差（A 3102→3039 chars；B 9098→9111 chars；word 数 A 2575 / B 7257），内存无增。**默认 OFF（速度优先），能力保留，Stage 1 以 Profile 开关按需开 ON**（需词级时间线时）。
2. **Pipe vs Temp**：输出哈希完全一致（67165375bd7e），RTF 0.1217 vs 0.1311（差 7%，噪声级）。**默认 Temp**：落盘 wav 可断点重跑/复核，不重复解码；Pipe 失败即整段重解码，不可恢复。Pipe 不优化。
3. **VAD**：B 片 thr 0.3→0.7 语音比 89.2%→84.4%，约 62s 音频分类分歧；A 密集语音三档无差。whisper 内置 `no_speech_threshold` 0.3 vs 0.6 在 A 输出**逐字节一致**（同 sha）。**推荐阈值方向取保守侧（Silero thr 0.3–0.5 档），且 Stage 1 只能做 advisory（宁多送静音）；红线：本轮任何转写均未做语音过滤，误删语音 = 0（by construction）。** 误删率真值需 Golden Dataset（Stage 1+）才能量化，本轮如实声明。
4. **Chunk/Overlap**：5min/10.8min/15min 三档有效 RTF 恒定 ≈0.08，尺寸只影响任务粒度不影响速度；ov1/2/3 后半段输出 4559/4567/4574 chars（边界句切分微差，符合"不合并只观测"预期）。**推荐 Chunk=10min / Overlap=2s**（中段折中；15min 亦可，10min 粒度对失败重跑更友好）。未实现 Merge。
5. **Prompt Capacity**：`max_tokens=350` 假设**已证伪**。真实容量 = 223 tokens（代码截断位 `decoding.py:502` + 真实 tokenizer 双验证）；Global/Topic/Creator 任一单表即超限（360/244/336tok）；940tok 全量 prompt 触发输出结构坍缩（276→12 segs，chars 3102→2223，不同 sha）。**推荐：总量 ≤200 tokens；装配顺序改为 Global→Topic→Creator（Creator 放尾部才能在截断中存活，满足"Creator > Topic > Global"优先级语义）；超限直接截断，Stage 1 PromptBuilder 必须先计数再装配。**

## 9. 推荐配置（Stage 1 Profile 输入，只出值不回写架构）

```text
asr.model = mlx-community/whisper-large-v3-turbo @ a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb
asr.audio = temp-wav 16k mono（FFmpeg 落盘，可重跑）
asr.word_timestamps.default = OFF（按需 ON；ON 成本 ×1.4–1.5）
asr.no_speech_threshold = 0.6（0.3 同输出，取默认； dense 口播不敏感）
vad.profile = silero thr 0.3–0.5，advisory only（禁过滤式 VAD；误删红线）
chunk.size = 10min；overlap = 2s（merge 规则沿 V1.8 §42，不实现）
prompt.budget_tokens = 200；order = Global→Topic→Creator（Creator 尾部优先）；超限截断
worker = 1（单机串行；本轮未测多 worker，禁并发假设）
```

## 10. 异常记录

- A. 系统 python3（3.9.6）无 mlx：新建临时 venv（Python 3.12.13，`uv venv`），pip 安装全部依赖；复现链以 `pip-freeze.txt` 为准。
- B. 模型首下约 7min（1.5GB，hf-xet，中途表观停滞实为大文件续传，最终 `SNAPSHOT_DONE`）；revision 取下载时刻 `main` 头并双重验证（refs + snapshot 目录名），非 `latest` 字符串。
- C. Chunk 批处理 stdout 混入 `Detected language: Chinese` 致管道 JSON 解析失败 1 次：数据本身落盘完好（.json/.txt/.log 齐全），改用 `tail -1` 取数；属脚本输出卫生问题，不属转写失败，无重跑掩盖。
- D. 数据集缺口（非阻断，如实声明）：无真 30/60min 单文件（最长 21.7min）；无币圈词素材；无真片头音乐；无超长静音；B 全网格（9 格）只跑了 5 格子集（300/650/900 + ov1/2/3 单边界），C 未测 Word ON。
- E. RSS 跨轮波动（1669→3430MB）为 MLX 分配器行为，报告取 worst-case，不掩盖。

## 11. Blocking FINDING

**NONE**。`large-v3-turbo` 可下载、可加载、可转写；关键依赖均可安装。唯一降级项为数据集时长缺口（§10-D），属覆盖声明，转 Gate 评审由 D6（用户）定夺，不构成技术阻断。

## 12. PASS-FAIL（Gate 问，附录 A 逐项；计划书编号 1–12 即所谓 13 问）

1. MLX 可运行 → **PASS**（19 轮全 OK，中文检出）
2. revision 锁定 → **PASS**（repo+revision+路径+大小齐全，§2）
3. 依赖冻结可复现 → **PASS**（freeze 41 行，无 latest；mlx-whisper 无 git commit，已声明安装来源）
4. 5min RTF → **PASS**（0.1311，远优于实时；计划书无数字红线，本报告以 <0.2 为优判据）
5. 30min RTF → **FAIL（覆盖缺口）**：无真 30min 单文件；21.7min 代理 RTF 0.0785 已记录
6. 60min 无 crash/OOM/卡死 → **FAIL（覆盖缺口，严格口径）**：无真 60min 单文件；最长单文件 21.7min 通过 + 66min/6 文件累计零异常（证据充分但非单文件 60min）
7. Peak 在预算内（含 WordON 最坏档） → **PASS**（最坏 3430MB < 24GB）
8. Load Time 量化可接受 → **PASS**（0.7–1.5s，冷启可接受）
9. Word Timestamp 差量化+默认结论 → **PASS**（+39–46%，默认 OFF）
10. VAD 结论且误删=0 → **PASS**（保守阈值方向；零过滤零误删；真值待 Golden）
11. Pipe/Temp 结论且默认=稳定侧 → **PASS**（默认 Temp）
12. Chunk/Overlap 数据+推荐值 → **PASS**（部分网格：三档尺寸 + ov1/2/3；推荐 10min/2s；B 全 9 格未跑完，缺口已声明）
13. Prompt 真实 Capacity 验证 → **PASS**（223tok 实测；350 假设证伪；装配顺序修正）
14. Blocking 清零或有 FINDING → **PASS**（NONE，无悬空阻断）

## 13. GO / NOGO

**NOGO（仅因 Q5/Q6 数据集时长缺口；技术基线本身全绿）→ 请 D6（用户）一句话定夺**：

- 选项一（建议）：接受降级——以 21.7min 最长单文件 + 66min 累计零异常为长稳证据，转 **GO** 进 Stage 1；待拿到真 30/60min 素材后补测 Q5/Q6（脚本与 Profile 参数不变）。
- 选项二：补测后再 GO（本报告脚本可直接重跑）。

## Implementation Notes（Guardrail 1/2/3，只记录不实现）

- G1：Benchmark 脚本未创建任何 Run/Source 记录，未预设绕过 "Source → Run" 顺序的捷径（纯转写函数调用，无 DB）。
- G2：462MB 源文件 SHA256 实测 0.9s（`shasum`，M4），大文件强哈希+fstat 对比在 Stage 1+ 性能可接受；本轮文本哈希均为 SHA256（见 §4 sha12，全值在 JSON）。
- G3：未实现恢复流程；Stage 10/11 前置约束：Archive 前重确认 Publish 存在、用户编辑覆盖恒为 0——记为约束，不实现。

## 假设 vs 实测对照（R6）

| 旧假设 | 实测 |
|---|---|
| `max_tokens=350` | ❌ 真实 223 tokens（代码+tokenizer 双验证） |
| Pipe 更快 | ~持平（7% 噪声级），且输出逐字节一致；默认选 Temp（可恢复性） |
| Chunk 越大越快 | ❌ RTF 与尺寸无关（≈0.08 恒定）；尺寸只定任务粒度 |
| VAD 默认可过滤静音省时间 | 未验证省时假设；本轮 VAD 只观测（3.3s/21.7min，可忽略），禁过滤 |
