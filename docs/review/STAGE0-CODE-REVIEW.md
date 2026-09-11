# CODE REVIEW

- Task: Stage 0 builder 方法与架构冻结合规复核（TECHNICAL_BENCHMARK_REPORT.md + s0_*.py + results/62 文件 + STAGE0-PLAN.md，对照 V1.8 基线 STOP EXPANSION §65-71、不做 §2.2）
- Commit: N/A（非 git 仓库；被检对象为 docs 落盘，无 commit）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash，本窗口 subagent）
- Result: 过（PASS，无 P0/P1；P2 补证 3 项交 qa/supervisor 跟踪，不阻断 GO/NOGO 判定）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无。架构合规逐项见下（全部通过）；方法硬伤逐项见下（全部通过）；打回条件逐项见下（均未触发）。

### 架构合规逐项（冻结架构，任一违反即打回——均未违反）

- Redis/PostgreSQL/微服务/Docker/消息队列/分布式锁：s0_*.py 仅调 mlx/mlx-whisper/silero-vad/FFmpeg（grep 全文无命中），依赖冻结表（pip-freeze.txt 41 行）无此类包。✅
- 云端 ASR/LLM/新模型：全 18 转写轮 `model=mlx-community/whisper-large-v3-turbo`，silero-vad 仅做观测未参与转写过滤。✅
- 复杂 UI/Obsidian 插件/SaaS/手机端/RAG/Embedding/向量库：无。✅
- 多进程 Worker：推荐 `worker=1`，报告明示“未测多 worker，禁并发假设”（REPORT §9）。✅

### Stage 1 越界逐项（任一实现即打回——均未实现）

- SQLite/Candidate/Source/Processing Run/Publish/Archive：s0_*.py 无 sqlite/DB 代码、无 Run/Source/Publish/Archive 逻辑；唯一 grep 命中是 s0_vad.py 变量名 `candidates`（VAD 阈值候选项），非业务 Candidate。报告 Implementation Notes G1/G2/G3 只记录约束不实现。✅
- 完整 ChunkMerge：s0_run.py 仅用 mlx_whisper 原生 `clip_timestamps` 做各配置独立转写，无合并代码；ov1/2/3 后半段输出差异（4559/4567/4574 chars）符合“不合并只观测”预期。✅

### 参数假设逐项（任一即打回——均未犯）

- `max_tokens=350`：未沿用，已证伪（REPORT §8.5：223 tokens，940tok 全量 prompt 输出坍缩 276→12 segs 为证）。✅
- Pipe 更快断言：未断言。Pipe 33.6s vs Temp 36.1s（差 7%）判为噪声级持平且哈希逐字节一致（67165375bd7e…），默认 Temp 理由是可恢复性而非速度。✅

### 方法硬伤逐项（任一即打回——均未犯）

- RTF 计算：s0_run.py:111 按全片时长算 clip 轮 RTF（偏小），报告 §4 已注记并改用有效 RTF（tr/clip_len）；复算 6 格（0.079/0.078/0.080/0.085/0.080/0.077）全部正确。✅
- Peak 取法：ru_maxrss 进程级，报告取 worst-case（§7 最坏 3429.7MB = T08-B-ch300.json 实测值），Word ON 不增内存有数据支撑（B 两轮均为 3411MB 级）。§5 B 行写 3411.8 未含 chunk 轮 3429.7，见 P2-1（数字不一致，结论不受影响）。✅
- revision 只写 latest：未犯。全哈希 `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`＋本地 snapshot 路径＋1.5GB 大小＋dl.log `SNAPSHOT_DONE` 行佐证。refs 半侧无独立落盘见 P2-2。✅
- 假音频：数据集脚本仅 ffprobe 真实课程视频（h264+aac），币圈/片头音乐缺口如实声明未伪造（§10-D）。prompt 字数与源文件精确吻合（Global 320/Topic 187/Creator 333/全文 843，逐字节复核一致），tokenizer 数据源可信。✅
- 掩盖重跑：18 转写轮＋2 VAD 轮 JSON 全 `status=OK`，.log 无 TRANSCRIBE_FAILED/Traceback 痕迹；唯一管道解析故障（§10-C）在 stdout 层、数据落盘完好，属已声明的脚本卫生问题。✅
- 单机并行污染：各轮独立进程、设计串行；nst0.3 与 base 输出同 sha（67165375bd7e…）佐证环境稳定。执行时间戳未落盘，串行性由 qa 复验 mtime，见 P2-3。✅

### 缺口诚实声明（视为优点，不扣分——已确认）

- Q5/Q6 判 FAIL（覆盖缺口）、B 网格 5/9 子集、C 未测 Word ON、无币圈词、无真片头音乐：§10-D、§12、§13 全部声明；NOGO 判据合理（技术基线全绿，仅数据集时长缺口，交 D6 二选一定夺）。✅
- Prompt 223tok 双验证齐全：代码截断位（decoding.py:494-503/:502，n_text_ctx=448→223）＋真实 tokenizer 分表计数（360/244/336/940tok）两者皆有，不触发打回。tokenizer 原始输出无独立落盘见 P2-2。✅

## P2 / P3 Backlog Findings

- P2-1（报告内数字不一致，不影响结论）：§5 B 档 Peak 写 3411.8MB，但 B 文件相关轮最坏为 T08-B-ch300 的 3429.7MB（§7 已正确采用）。改法：§5 B 行 Peak 改为 3429.7MB（或注明 chunk 轮另计）；qa 核对后由 supervisor 放行。
- P2-2（证据补强，不阻断）：tokenizer 分表计数（360/244/336/940tok）与 revision refs 半侧只有正文陈述，无独立落盘 artifact（results/ 无 tokenizer 输出 JSON、无 refs 查询记录；dl.log 仅覆盖 snapshot 半侧）。改法：补 tokenizer 计数命令输出 JSON＋refs 查询记录落盘 results/，交 qa 按“坏例看 exit 码”复验；超时限可后补，不卡 Gate。
- P2-3（复现链小瑕疵）：各 JSON 内 `transcript`/`log` 字段指向 `/tmp/.../stage0bench/` 临时路径，实际落盘在 results/ 同名文件；results/ 残留中间产物 T08-B-ch900.wav。改法：报告加一句路径映射说明并清理 wav（neat-freak 顺手），交 supervisor 确认。
- P3-1（观察）：ov2（55.4s）比 ov1/ov3（52.1/52.0s）高约 6%，报告判噪声级可接受但系单次测量；Stage 1 采用 overlap=2s 后建议复测一次确认。
- P3-2（观察）：§12 Q4 自设“<0.2 为优”判据（计划书无数字红线，已明示）；RTF 远优于实时（0.08–0.18）事实成立，Stage 1 应由 D6 确认正式 RTF 红线。
