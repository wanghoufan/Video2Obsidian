# QA-REPORT｜Stage 0 Technical Benchmark（Video2Obsidian V1.8）

- QA：qa（opencode-free/mimo-v2.5-free，本窗口 subagent，只读+轻量只读验证，未重跑转写，未改代码）
- 被测：`docs/qa/TECHNICAL_BENCHMARK_REPORT.md` + `docs/qa/benchmark_stage0/results/`（62 文件）+ `docs/qa/benchmark_stage0/s0_*.py` + `docs/review/STAGE0-CODE-REVIEW.md`
- 计划：`docs/pm/STAGE0-PLAN.md`（P0-1~12）｜轮次：首轮 QA（无重跑轮次声明需求）
- **结论：PASS（无 P0/P1；P2 遗留 4 项不阻断 GO/NOGO 判定，交 supervisor 跟踪；P3 观察 2 项沿用 code-reviewer 结论）**

## 1. 证据存在性与字段完备（18 转写轮全量，非抽查）

- `results/` 共 62 文件：18 轮 × {json,txt,log} = 54 ＋ VAD-A/B.json ＋ env.json ＋ pip-freeze.txt ＋ dl.log ＋ prompt_full.txt ＋ silence.txt ＋ T08-B-ch900.wav（中间产物残留，见 P2-3）。
- 18/18 JSON `status=OK`；必需字段零缺失（run_id/status/media/audio_duration_s/audio_mode/model/word_timestamps/prep_s/model_load_s/transcribe_s/rtf/rss_peak_mb/text_chars/segments/text_sha256/transcript/log）。
- 18/18 同名 `.txt`＋`.log` 存在；18/18 `.log` 无 `TRANSCRIBE_FAILED`/`Traceback`；18/18 `.log` 内嵌 `status=OK` 记录。
- 18/18 `txt` 全文 SHA256 与 JSON `text_sha256` 逐字节一致（含 pipe/nst03 同 sha 佐证环境稳定，见 §3）。

## 2. §4 表格与 JSON 一致性（18/18 全量核对，远超“至少 5 轮”）

- prep/load/tr/chars/segs/words/sha12/duration 全 18 轮与 §4 表格一致。
- 2 处不一致（均为报告誊写类，不影响结论，列 P2）：
  - P2-1（沿用 code-reviewer）：§5 B 档 Peak 写 3411.8MB，未含 chunk 轮最坏 3429.7MB；§7 已正确采用 worst-case。
  - P2-4（本轮新增）：§4 T09-C3 行 Peak 写 3344.6MB，JSON 实为 **3346.3MB**（3344.6 系 T09-C4 的值，疑复制错行；差 1.7MB，结论不受影响）。

## 3. RTF=tr/duration 核对（18/18）

- 11 轮精确一致；7 轮差 ±0.0001~0.0002（T03-A-base、T04-B-base、T05-A-wordON、T06-A-pipe、T08-A-promptfull、T09-C1、T09-C5）。
- 根因：`s0_run.py:111` 用未舍入原始耗时算 RTF（保留 4 位），而 `transcribe_s` 落盘舍入到 0.1s；用舍入值反算必然有舍入误差。属方法自洽，非造假。
- Clip 轮 §4 注记“记录值偏小”属实；有效 RTF（tr/clip_len）复算：300s→0.079、650s→0.078、ov1/2/3→0.080/0.085/0.080、900s→0.077，与 §5 一致，Chunk 无关结论有数据支撑。

## 4. Peak worst-case 取值

- 全量 peak 排序最坏为 T08-B-ch300 **3429.7MB**；§7 采用 3429.7MB 正确；24GB 预算 <15% 结论成立。
- Word ON 不增内存有数据支撑（B 两轮 3411.8 vs 3411.4MB）。

## 5. revision a4aaeec0 与 snapshot 一致性

- `refs/main` 内容 = `a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`；`snapshots/` 下唯一目录同名；双重一致，P2-2 的 refs 半侧本轮已由文件系统独立验证（此前“无独立落盘”缺口现可视为 refs 半侧闭环，tokenizer 半侧仍缺独立 artifact）。
- blob 实测 weights 1613977612 bytes，与 §2 一致（snapshot 内为 symlink，`stat` 须跟随到 `blobs/` 读数，此为取证注记非问题）。
- `dl.log` 含 `SNAPSHOT_DONE …/snapshots/a4aaeec0…` 行；`main` 头取值如实声明（§10-B）。

## 6. 数据集时长 ffprobe 只读复现

- A 文件 ffprobe = 275.737007s（报告 275.74s ✓）；B 文件 = 1300.596009s（报告 1300.60s ✓）；编码 h264 2560×1600 + aac 44.1kHz 立体声 ✓。
- C 累计：B 1300.6 ＋ C1~C5（638.08/620.83/494.14/475.73/430.1）= 3959.48s ≈ 报告 3959.4s ✓（66.0min 口径一致）。
- 均为真实课程视频（禁假音频 ✓）；prompt_full.txt 843 字与 JSON `prompt_chars=843` 一致（单表 Global/Topic/Creator 文件为 321/188/334 含尾换行，报告 320/187/333 系去换行计数，和 843，属口径注记非问题）。

## 7. P2 补证项闭环确认（code-reviewer 移交 3 项）

- P2-1（§5 B Peak 口径）：**未闭环**，报告未改，结论不受影响，仍交 supervisor 放行。
- P2-2（tokenizer＋refs 独立落盘）：**部分闭环**——refs 半侧本轮文件系统验证通过；tokenizer 分表计数（360/244/336/940tok）仍只有正文陈述，`results/` 无独立 artifact。超时限可后补，不卡 Gate。
- P2-3（/tmp 路径映射＋wav 残留）：**映射确认**（18/18 JSON transcript/log 字段均指向 `/var/folders/.../stage0bench/`，实际落盘 `results/` 同名文件，属实）；`T08-B-ch900.wav`（41MB）仍残留未清理，交 neat-freak。另：各 artifact mtime 相同（批量拷贝所致），串行性无法由 mtime 佐证，但 nst0.3/base 同 sha 佐证环境稳定。
- P3-1/P3-2（ov2 单次 +6%、Q4 自设 <0.2 判据）：复核同意 code-reviewer 观察结论，无新增证据。

## 8. 漏测声明完整性（有无掩盖）

- Q5/Q6 判 FAIL、B 网格 5/9 子集、C 未测 Word ON、无币圈词、无真片头音乐、片头音乐/长静音仅部分代理——§10-D、§12、§13 全部如实声明，与证据一致（B 缺口：确只有 300/650/900+ov1/2/3 五格；C 确无 wordON 轮；VAD 仅观测未参与转写）。
- 18 转写轮＋2 VAD 轮全 OK 且零重跑声明可信（无 FAIL 痕迹；§10-C 管道解析故障属 stdout 层且已声明）。
- NOGO 仅因数据集时长缺口、技术基线全绿的判定合理；D6 二选项已给用户。

## 9. 参数假设与冻结架构

- 350 证伪（223tok＋940tok 坍缩 276→12 segs，不同 sha）、Pipe 持平（同 sha 67165375bd7e，差 7% 判噪声）、Chunk 无关（有效 RTF≈0.08 恒定）均有数据支撑，未见“参数假设当结果”。
- `s0_*.py` 无 redis/postgres/docker/sqlite/llm/rag/embedding 命中；`latest` 仅出现在报告否认句中，版本字段无 `latest`；ChunkMerge 未实现；架构未擅改。

## BUGS（照 BUGS.template.md；无 P0/P1，只记 P2）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| P2-1 | P2 | 否（code-reviewer 已定不阻断） | 读 REPORT §5 B 行 Peak 3411.8 vs T08-B-ch300.json 3429.7 | OPEN（交 supervisor 放行） | §5 B 行改为 3429.7 或注明 chunk 轮另计 | §7 已正确用 worst-case，结论不受影响 |
| P2-2 | P2 | 否 | `ls results/` 无 tokenizer 输出 JSON、无 refs 查询记录 | PARTIAL（refs 半侧本轮文件系统验证通过；tokenizer 半侧仍缺） | 补 tokenizer 计数输出 JSON 落盘 results/ | 超时限可后补，不卡 Gate |
| P2-3 | P2 | 否 | 18/18 JSON transcript/log 指向 /tmp/stage0bench；T08-B-ch900.wav 残留 | OPEN（映射已确认，待一句话说明＋清 wav） | 报告加路径映射说明；neat-freak 清 wav | mtime 批量一致，串行性由环境稳定性佐证 |
| P2-4 | P2 | 否 | REPORT §4 T09-C3 Peak 3344.6 vs T09-C3.json 3346.3 | OPEN（新增，同 P2-1 类） | §4 T09-C3 Peak 改为 3346.3 | 差 1.7MB，结论不受影响；疑复制 T09-C4 值错行 |

## Fix Attempt Fingerprint

- Task ID: Stage0-QA 首轮（证据核验，不重跑 4h 基准）
- Root Cause Hypothesis: 不适用（PASS，无 P0/P1；P2 均为报告誊写/证据补强类）
- Approach: 只读核验——18/18 JSON 全量字段＋sha256 复算＋RTF 反算＋peak 排序＋ffprobe 只读＋refs/snapshot 文件系统验证＋全量 grep（FAIL/Traceback/latest/架构违禁词）
- Files Changed: 无（qa 不改代码；本报告为唯一新增 `docs/qa/STAGE0-QA-REPORT.md`）
- Verification: 坏例看 exit 码——sha 复算 18/18 match；`grep FAIL/Traceback` 零命中（exit 非零即“无命中”已确认）；ffprobe 双时长复现到 0.01s 量级
- Failure Reason: 无 FAIL 项
- Difference From Previous Attempt: 首轮，无上一轮

---
目标：Stage0 证据核验｜剩 P0：无（QA 口径 PASS；P0-1~12 评审状态以 supervisor 复检为准）｜下一步：交 supervisor 复检＋product-reviewer 验（含 D6 定夺 Q5/Q6）。
