# QA-REPORT｜Stage8 S8-T05 验收套件 + §72/§73 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage8/`（vad.py/chunk_planner.py/timeline.py/merge.py/transcribe_chunks.py/__init__.py）+ `src/stage1/` 只读复用（冻结常量/model revision/nst 0.6/word OFF/temp-wav 16k mono/worker 1）+ `src/stage2/` 只读复用（store/candidate/discover/runs/AUTO UPSERT/reconcile/instance 持锁）+ `src/stage3/` 只读复用（normalize/render 冻结规则表/公开 API）+ `src/stage4/` 只读复用（canonical_path_for 双算）+ `src/stage5/` 只读复用（run_startup 语义）+ `src/stage6/` 只读复用（resolve_canonical 双算）+ `src/stage7/` 只读复用（load_vocabulary/build_initial_prompt/build_for_chunks/LANGUAGE_STRATEGY=explicit-zh）
- 计划：`docs/pm/STAGE8-PLAN.md` S8-T05（P0-1~P0-7；happy 双链 + 异常/边界 8 个 + 回归七行；外置合成 Input Root + 外置 Data Root；合成小音频 ≤132K；文本内容不断言；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage8 子集：§73-24 合并 segments 非空单调 + §73-25 Word Timestamp 能力 + §73-26 Absolute Timeline 正确 + §73-27 每 Chunk 重建 + §73-15 分层 ASR-only）+ §42（VAD advisory/Chunk/Merge 四优先级/禁 fuzzy）+ §43（Relative + Absolute 双时间戳）+ Stage0 §9 冻结（VAD thr 0.3–0.5/chunk 10min overlap 2s）
- QA 执行目录（仓库外）：`/tmp/s8qa/`（happy/a7_reuse/a8_bump/reg_s2/reg_s3/reg_s5/reg_s6 各独立 data_root + 合成小音频 `/tmp/s8qa/input/synth_2s.wav` 64044B + 合成小 `.mp4` 副本 + `s8qa_results.json`）+ `/tmp/s8qa_run.py`（仓库外 Runner，`--bad` 八子进程取 exit 码；python3.12 自装 numpy/mlx-whisper/silero-vad/watchdog，模型走 `~/.cache/huggingface` 已缓存 whisper-large-v3-turbo，`HF_HUB_OFFLINE=1`）；仓库内零写盘除本报告
- **结论：PASS（happy 双链 + 异常/边界 8 个全过 + 回归七行，113/113 断言双轮稳定，Runner exit 0；坏例只看 exit 码：八坏例 exit 1 符合预期；Whisper 有界=2（happy 真调 1 + 回归 S7 接线 1，逐用例披露）；VAD 双 thr 均为 OK 且稳定复现、观测前后字节一致、零过滤；文本内容不断言（只验 str/list 类型）；三表：复用库 0/0/0 且 runs=1、bump 库 runs=2 且 arch 恒 0；current_path 列级零写；最大合成文件 64044B（≤132K 门 135168B）；结论只落本报告）**

## 1. 输入复核（src/stage8 落盘 6 文件，只读消费）

- `vad.py`（S8-T01）：`observe_vad(wav_path, threshold, filtering=False)`（thr 仅 0.3/0.5，`filtering=True` 即 `VadError` 硬拒；非法 wav 形状拒收）+ `observe_vad_all` 双档 + `vad_profile()`（engine silero/mode advisory-only/thresholds [0.3,0.5]/filtering False/drives_* False）+ `is_advisory_only()=True`。QA 实测：双 thr 状态 OK + 同 thr 双跑逐字节一致 + sha/字节一致 + silero 缺席时 SKIPPED 仍 fail-closed（本轮环境 silero 可用，走 OK 路径）。
- `chunk_planner.py`（S8-T02）：`plan_chunks(duration_s, size_s=600, overlap_s=2)` 纯函数 + `CHUNK_SIZE_S=600`/`CHUNK_OVERLAP_S=2` + core/overlap 归属 + 非法输入（0/负/NaN/inf/非数字/bool）fail-closed + 常量偏离 fail-closed。QA 实测：600s→1 chunk + 601s→2 chunk 且 overlap 恒 2s + 1200s 三 chunk core 无缝无重叠 + 合成 2s 时长恰 1 chunk。
- `timeline.py`（S8-T03）：`to_absolute(segments, chunk_start_s)`（relative 原位保留 + absolute_start/end 增补 + word 双戳透传 + relative 乱序拒收）+ `check_monotonic`。QA 实测：absolute == chunk_start + relative + 双戳齐全 + 乱序 exit 1。
- `merge.py`（S8-T03）：`merge_chunks` 四优先级（core_region > absolute_timestamp > overlap_timestamp > text_similarity；text 步仅 collapse 同 absolute_start 且同文本邻居，无整篇 dedup）+ 空输入拒收 + 输出单调校验。QA 实测：overlap 双份恰一份 + 非 overlap 逐字节 + 近似文本（差一字符）双双保留 + fuzzy 关键词零命中。
- `transcribe_chunks.py`（S8-T04）：`run_chunks`（stage1 冻结常量逐字段对齐 + VAD advisory 门 + 每 Chunk 经 stage7 `build_for_chunks` 重建 + exactly chunk 数调用 + ffmpeg 按边界落盘 + 输出经 timeline/merge + `build_chunk_asr_profile` vad/chunking 只进 ASR 层 + `chunk_asr_profile_hash` + `assert_asr_layer_only`）。QA 实测：注入引擎 3 chunk 调用数==3 + 真调 1 chunk 调用数==1 + prompt 复算逐字节一致 + 合并单调。
- `__init__.py`：装配导出（常量 + 函数全透出，无语义增量）。
- 上轮 builder 验证入口与对账：HANDOFF 仍停在 Stage2，未登记 Stage8 builder 自验入口；QA 按 S8-T05 独立合成（2s 正弦 1ch/16k 64044B，同 S7 夹具形状，builder 原片无从动）+ 独立 Runner 113 断言覆盖；builder 摆动无——QA 未发现 hash/截断/边界口径分叉（planner 600/601/1200 三点与 PLAN 验收值一致）。

## 2. 用例简表（坏例只看 exit 码；三表=norm/rend/arch；Whisper=真调次数；文本内容不断言）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 三表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY-A VAD+Planner | 合成 2s wav | 双 thr 观测 + planner 三点 | OK 稳定 + 无过滤 + 600/601/1200 边界 | 一致（双 OK，双跑一致，sha 等，600→1/601→2 overlap2s/1200 core 无缝） | Runner exit 0 | — | 0 |
| HAPPY-B 注入 3 chunk 接线 | 合成 wav + 三组各异词项 + 注入引擎 | run_chunks（word ON，切片驱动） | calls==3 + prompt 各异且复算一致 + §73-24/25/26/27 + §73-15 + hash 稳定/翻转 | 一致（calls 3，三 prompt 异，overlap 恰一份，单调，word 双戳，asr-only，64hex） | Runner exit 0 | — | 0 |
| HAPPY-C 真调 1 chunk | 合成 wav + stage7 词项 | run_chunks（engine=None） | calls==1 + 1 chunk + prompt 复算一致 + 单调 + 冻结对齐 + 文本只验类型 | 一致（calls 1，token 复算等，vad 字节等，word OFF） | Runner exit 0 | — | 1（有界） |
| A1 VAD 过滤拒收 | 合成 wav | observe(filtering=True) | VadError，exit 1 | 一致 | exit **1** | — | 0 |
| A2 planner 非法 fail-closed | 纯函数 | 0/-5/NaN/inf/str/None/True | 全 ChunkPlanError，exit 1 | 一致（7/7 拒收） | exit **1** | — | 0 |
| A3 短音频 1 chunk | DUR=2.0s | plan_chunks(DUR) | 恰 1 chunk，起止合法 | 一致 | — | — | 0 |
| A4 overlap 恰一份 | 合成双份夹具 | to_absolute→merge | core 恰一份 + 非 overlap 逐字节 + 单调 | 一致 | — | — | 0 |
| A5 absolute 乱序拒收 | 乱序 segments | to_absolute / merge | TimelineError/MergeError，exit 1 | 一致 | exit **1**（×2 模式） | — | 0 |
| A6 fuzzy 拒收 | 近似文本夹具 | merge | 差一字符双双保留；同 start 同文本恰一份 | 一致 | — | — | 0 |
| A7 同 profile 同 Run | 新库 + 合成 clip.mp4 + happy hash | discover→get_or_create×2→reconcile | 同 run_id + Source=1/Run=1 + dup0 + arch0 + current 零写 | 一致 | Count 1/1 | 0/0/0 | 0 |
| A8 bump 新 hash 新 Run | A7 同库 + Creator 末词+`x` | 快照/装配/profile/hash 重算→get_or_create | 快照变 + hash 变 + 新 run + 总 Runs=2 + asr-only | 一致 | Count 2 | 0/0/0 | 0 |
| B-八坏例 | 各合成前置 | --bad 八子进程 | 期望错误未吞，exit 1 | 一致（八 exit 1，见§3） | 八 exit **1** | — | 0 |
| STOP 外置/常量 | 全量输入 + 全仓 stage8 | 路径前缀 + 最大文件 + Whisper 有界 + 双 grep + 常量比对 | 全在 /tmp/s8qa + max≤132K + calls=2 + 零命中 + 冻结恒 | 一致（max 64044B，calls 2） | — | arch 全库 0 | 2 |
| REG-S1 | 合成门 | probe_volume + 非法 Raw | ALLOW + 非法拒收 | 一致 | exit 0 | — | 0 |
| REG-S2 | 新 root | startup 5 步 + discover | 5 步逐字 + PROMOTED + Source=1 + Run=1 + arch0 | 一致 | 1/1 exit 0 | 0/0/0 | 0 |
| REG-S3 | 新 root（合成 Raw 经门） | norm→render | COMPLETED→PUBLISH_EVALUATION + verdict 双值域 | 一致（PENDING_PUBLISH） | Norm=1/Render=1 | 1/1/0 | 0 |
| REG-S4 | 旧库只读 | 查 /tmp/s4qa | PUBLISHED 行仍可查（≥1） | 一致（旧库命中） | ≥1 | — | — |
| REG-S5 | 新 root | run_startup | order 逐字 + RUNNING 不断链 + shutdown 幂等 | 一致 | exit 0 | 0 | 0 |
| REG-S6 | 合成嵌套 Unicode | resolve 双算 | stage6 与 stage4 双算逐字节一致 | 一致（`AI/博主A/系列1/DeepSeek V4 分析.mp4→…md`） | — | — | 0 |
| REG-S7 | 合成 wav + stage7 词项 | 装配→单文件接线→profile executed | token≤200 + calls==1 + 复算一致 + executed + 文本只验类型 | 一致 | calls=1 | — | 1（有界） |

Runner：`/tmp/s8qa_run.py`（仓库外）→ `/tmp/s8qa/s8qa_results.json`（113 断言 JSON 已落盘，可复算；双轮 `TOTAL 113/113 FAILS=[] exit=0`）；坏例子进程八 exit **1**（判据只用 exit 码，不看打印）；最大合成文件 64044B（`synth_2s.wav`，≤135168B 门，真实长视频零触碰）；Whisper 调用全链=2（HAPPY-C 1 + REG-S7 1，其余注入引擎/纯函数/DB 零真调）。

## 3. 每用例明细（前置/动作/期望；Count 或 exit 码 + dup0 + 三表 + current_path + Whisper 有界 + 外置路径 + 文本不断言声明）

- HAPPY-A：前置合成 2s 正弦 wav（1ch/16k，64044B）；动作 `observe_vad_all` + `plan_chunks(600/601/1200/DUR)`；期望双 thr OK 且双跑一致 + sha/字节一致 + filtering False + drives 全 False + 600→1 chunk（0–600）+ 601→2 chunk（step 598，overlap 恒 2s，core 0–0/300?实际 core 无缝 `c0.core_end==c1.core_start` 且尾 core_end==601）+ 1200→3 chunk core 无缝无重叠 + 短音频恰 1 chunk + 起止非负无越界；实测全中（VAD_STATUS 双 OK）。
- HAPPY-B：前置三组词项（`CA0/CA1/CA2` 各异）+ 合成 3 切片驱动（0–0.8/core 0–0.4；0.4–1.4/core 0.4–1.1；1.0–2.0/core 1.1–2.0）+ 注入引擎（chunk0 返回私段 + overlap 旧份 abs 0.5–0.7 含 word；chunk1 返回 overlap 新份 + 私段；chunk2 返回私段）；动作 `run_chunks(word_timestamps=True, engine=fake)`；期望 calls==3 + 三 prompt 各异且与 `build_for_chunks` 复算逐字节一致 + absolute == chunk_start + relative 且双戳齐全 + 合并非空单调 + overlap 区恰一份（新旧二存一）+ 私段全留 + word ON 全员双戳 + layering asr-only + hash 64hex 稳定且 chunking 一字节翻转 + 冻结对齐 12 字段 + merge_priority 四项全序；文本内容不断言声明：本用例及全链仅断言 `isinstance(text,str) and isinstance(segments,list)`，不做词准确率/CER/内容包含断言（属 Stage11+ Golden 门；合成正弦无语音，空文本亦合法）；实测全中。
- HAPPY-C：前置合成 wav + stage7 词项（G3/T2/C2）；动作 `run_chunks(engine=None)`（`HF_HUB_OFFLINE=1`，ffmpeg 真切 1 片，mlx_whisper 真调 1 次）；期望 engine_calls==1 + chunks==1 + prompt 与纯函数复算一致 + token 相等且 ≤200 + merged 单调 + vad bytes_equal + 冻结对齐 + 文本只验类型 + decode word OFF；实测全中（WHISPER_CALLS 累计 1）。
- A1/A2（坏例正文见 B）：A1 `filtering=True` 即 VadError；A2 七类非法输入（0/-5/NaN/inf/"600"/None/True）全 ChunkPlanError；另常量漂移（size 300）ChunkPlanError（`plan_drift` 坏例）。
- A3：`plan_chunks(2.0)` 恰 1 chunk（start 0，end≈DUR），独立断言（HAPPY-A 内同值复核）。
- A4：chunk0（0–600/core 0–300）私段“前区唯一文本”+ chunk1（298–601/core 300–601）私段“后区唯一文本”+ 双份“dup旧”（abs 299 vs 299）→ 合并“dup旧”恰 1 + 双私段逐字节保留 + 单调 + priority 全序；实测全中。
- A5：relative 乱序（1.0 在前、0.2 在后）`to_absolute` TimelineError（`timeline_disorder` exit 1）；空列表 `merge_chunks([])` MergeError（`merge_empty` exit 1）；合并后 `check_monotonic` 乱序拒收由 merge 内建校验覆盖。
- A6：同 core 内“hello world”vs“hello world!”（差一 `!`）双双保留、顺序不变（禁整篇 fuzzy dedup 的直接证据）；同 start 同文本双份恰 collapse 一份（文档化 text_similarity 步，非 fuzzy）；`src/stage8/` fuzzy 关键词零命中（STOP 门复证）；实测全中。
- A7：前置新 `a7_reuse/{data_root,input}` + 合成 `clip.mp4`（1K）+ HAPPY-B hash；动作 discover（PROMOTED）→get_or_create×2（同 run）→reconcile（同 run）；期望 Source=1/Run=1/dup0/三表 0/0/0/arch0/`current_path==path_key/status=ACTIVE/archived_at NULL`；实测全中。
- A8：前置 A7 口径新库 + Creator 末词+`x`；动作快照/装配/分片 profile/hash 重算→get_or_create；期望快照变/hash 变/新 run/总数 2/arch0/asr-only（含 vad/chunking 双字段；render/normalization 用冻结 DEFAULT  profile 对打）；实测全中（chunk size/overlap 全程 600/2 未动，bump 只走词典快照，冻结无漂移）。
- B-八坏例（判据只用 exit 码）：`vad_filter exit 1=VadError` + `vad_thr_drift（0.4）exit 1` + `plan_illegal（7 类全拒）exit 1` + `plan_drift（size 300）exit 1` + `timeline_disorder exit 1=TimelineError` + `merge_empty exit 1=MergeError` + `layer_leak（vad 进 render）exit 1=ChunkTranscribeError` + `wav_shape（双声道）exit 1=TranscribeError/ChunkTranscribeError`；任一吞错/错类型即非 1 项未触发（首轮 113 前曾有 Runner 自身排序 bug 与缺包 3 项，已修，业务零改，见指纹）。
- STOP 外置/有界/冻结：输入全在 `/tmp/s8qa/*/input` + 外置 Data Root（与真实视频目录/真实 Obsidian 库无交集）；最大合成文件 64044B（≤135168B 门）；Whisper 全链=2（`s8qa_results.json:whisper_calls=2`，HAPPY-C 1 + REG-S7 1；超预算即 FAIL 项未触发）；Stage9+ 关键词 grep 零命中（`paragraph|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber`）+ 直写 DB 零命中（`sqlite3|INSERT|UPDATE|DELETE`）+ VAD 过滤零命中（`remove_silence|gate_audio`）+ fuzzy 零命中；冻结恒（chunk 600/2、VAD 0.3/0.5、word OFF、nst 0.6、budget 200/order Global→Topic→Creator）；`git diff` 口径 N/A（非 git 仓库，以七回归 PASS + QA 零改代证）；各库 `archive_commits` 全 0。
- 回归：REG-S1 `s1probe(/tmp)→ALLOW` + 非法 Raw 拒收；REG-S2 `instance.startup` 5 步逐字 + PROMOTED + Source=1 + AUTO Run=1 + arch0；REG-S3 合成 Raw 经门→`COMPLETED→PUBLISH_EVALUATION` + verdict `PENDING_PUBLISH`（双值域内）；REG-S4 `/tmp/s4qa` 旧库只读 `PUBLISHED≥1` 仍可查（旧库命中）；REG-S5 `run_startup` order 逐字 + `running==True` + `shutdown` 幂等（Ready→Scan→Reconcile→RUNNING 不断链）；REG-S6 嵌套 `AI/博主A/系列1/DeepSeek V4 分析.mp4` 经 stage6 与 stage4 双算逐字节一致；REG-S7 stage7 装配（token≤200 非空）→单文件接线真调 1 次（prompt 复算一致 + executed + 文本只验类型）；`src/stage1-7/` 本轮 QA 未触碰（目录非 git 仓库，`git diff` 口径 N/A，以七回归 PASS + QA 零改代证）。

## 4. §72/§73 子集门（Stage8 5 断言逐项）

- [x] §73-24 PASS（Segment 正常：合并后 segments 非空 + absolute 单调；HAPPY-B 注入三 chunk + A4 夹具双证据，`happy.73-24.nonempty/monotonic`）
- [x] §73-25 PASS（Word Timestamp 能力正常：OFF 默认透传（HAPPY-C 真调 decode word OFF）+ ON 能力不断链（HAPPY-B word 全员双戳透传），不扩展语义；`happy.73-25.word.on/off`）
- [x] §73-26 PASS（Absolute Timeline 正确：合成 overlap 夹具逐段 `absolute == chunk_start + relative` + Relative + Absolute 双保留 + 真调输出单调；`happy.73-26.dual` + HAPPY-C mono）
- [x] §73-27 PASS（Prompt 每 Chunk 重建：合成三 Chunk 词项各异→三 prompt 各异 + 接线侧与纯函数复算逐字节一致，任一复用即 FAIL 项未触发；`happy.73-27.distinct/recalc/noreuse`）
- [x] §73-15 PASS（ASR/Normalization/Render 分层正确：vad_profile/chunking_profile 只进 ASR 层，串层坏例 exit 1，hash 输入含双字段且翻转；`happy.73-15/hash.flip` + `bad.layer_leak` + A8）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | 113/113 双轮 exit 0；八坏例 exit 1 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s8qa/s8qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S8-T05 Stage8 验收套件 + §72/§73 子集门 + Stage1~7 回归（首轮 QA 执行，Runner 修 2 次，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；3 个 FAIL 均为 Runner 自身问题：①A4 夹具 segments 相对顺序倒置触发 `to_absolute` 乱序拒收（业务行为正确，夹具错）；②③reg.s5/reg.s6 缺 `watchdog` 包（stage5 import 依赖，新 python3.12 环境未装，业务无辜））
- Approach: 仓库外 `/tmp/s8qa` 各用例独立 data_root + 合成确定性小音频（2s 正弦 1ch/16k 64044B，文本内容不断言）+ 合成小 `.mp4` 副本（真实长视频零触碰）；VAD 双 thr OK 稳定 + sha/字节一致为判据；planner 以 600/601/1200 三点数学为判据；timeline/merge 以合成 overlap 双份夹具 + 近似文本反 fuzzy 为判据；接线以注入引擎 calls==chunks + prompt 复算一致 + 真调 1 次有界为判据（文本只验类型）；Case4 以中央库 `COUNT(*)`/行级对比为判据；bump 以词典快照一字节翻转→新 hash→新 Run 为判据（chunk 常量全程冻结）；挡路/漂移/乱序/空合并/串层/坏 wav 走子进程只看 exit 码；grep 四重 STOP 门；集成库三表逐库快照 + archive 全库 0 + sources 列级不变；回归 S1 门/S2 链/S3 verdict/S4 旧库只读/S5 十一步/S6 双算/S7 接线
- Files Changed: 仅新增本报告 `docs/qa/STAGE8-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s8qa`（H2 外置目录约束延续）；Runner `/tmp/s8qa_run.py` 在仓库外；python3.12 自装包（numpy/mlx-whisper/silero-vad/watchdog）落在用户级 site-packages，非仓库
- Verification: 双轮 `TOTAL 113/113 FAILS=[] exit=0`（`s8qa_results.json` 可复算，`whisper_calls=2/max_bytes=64044/vad_status双OK`）；八坏例 exit 1 已取（`vad_filter/vad_thr_drift/plan_illegal/plan_drift/timeline_disorder/merge_empty/layer_leak/wav_shape`）；复用库三表 0/0/0 且 runs=1，bump 库 runs=2/arch0；诱饵/真实库零触碰；`src/stage1-7/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）；Runner 首轮 105/108 的 3 项系夹具排序 + 缺包，修 Runner 后 113/113（`--bad` 子进程 runners 同 Runner 同修）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 Runner 修 2 次：夹具重排 1 行 + pip 装 watchdog）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 64044B，合成 2s 正弦；多 chunk 长时语义只用 planner 数学 + 合成 segment 夹具证明）。
- U-2 文本内容不断言（PLAN 已定：词准确率/Golden/CER 属 Stage11+；合成正弦无语音，空文本合法；本报告仅验 `str/list` 类型 + 调用计数 + prompt 一致 + 时间轴单调）。
- U-3 Runner 在仓库外（`/tmp/s8qa_run.py` + `--bad` 八子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3/Stage4 U-3/Stage5 U-2/Stage6 U-2/Stage7 U-3 同 Pattern）。
- U-4 残留待清：`/tmp/s8qa`（4 库 + input，本轮新增，约 1M 内）+ Stage7 残留（`/tmp/s7qa` + `/tmp/s7_stage7_verify`）+ Stage6 残留（`/tmp/s6qa` + `/tmp/s6self`）+ Stage5 残留（`/tmp/s5qa` + `/tmp/s5_builder_selfcheck`）+ Stage4 残留（`/tmp/s4qa` + `/tmp/s4qa_out`）+ Stage3 残留（`/tmp/s3qa`）+ Stage2 残留（`/tmp/s2t07_qa` 约 1.9M）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`）+ 用户级 python 包（numpy/mlx-whisper/silero-vad/torch/watchdog，QA 自装，非仓库），交 neat-freak 收尾。
- U-5 `src/stage1/`…`src/stage7/ git diff 为空`口径 N/A（当前目录非 git 仓库；以七回归 PASS + QA 零改代证，未改业务代码）。
- U-6 三表口径说明：复用/bump 库 `normalization/render` 恒 0；reg_s3 库 `1/1` 系 QA 脚手架经 Stage3 公开 API 合成 Rendered Final 所致（不绕门），非 Stage8 代码新增写（直写 grep 零命中反证 + `archive_commits` 全库 0 + sources 列级不变）；若按字面“恒 0”卡脚手架库则无 verdict 证据可举，QA 按 S7 同一口径验收。
- U-7 HANDOFF 滞后：根 HANDOFF 仍停在 Stage2 CLOSED，未登记 Stage3~Stage8 builder 链；本报告输入复核以 `src/stage8/` 落盘 6 文件 + PLAN S8-T05 为准，builder 自验入口缺失不卡 QA（已独立覆盖）。
- U-8 VAD SKIPPED 路径未走：本轮 silero 可用，双 thr 走 OK 路径；`observe_vad` 的 SKIPPED（缺包）分支仅代码走读，未实测（属容错分支，非 P0 主张；若需补，卸包重跑一遍即可）。

---
目标：Stage8 验收 S8-T05｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
