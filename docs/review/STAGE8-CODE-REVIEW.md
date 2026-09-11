
# CODE REVIEW

- Task: 复核src/stage8/（对照STAGE8-PLAN + VAD禁过滤/chunk常量/禁fuzzy/禁DB直写/Stage9+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage8/ 六文件现状：__init__.py / vad.py / chunk_planner.py / timeline.py / merge.py / transcribe_chunks.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0；无 P1；P2×3 + P3×8 记 backlog，不阻塞 QA/supervisor；本复核独立静态+纯函数实测，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无 P0。本轮硬门逐项通过，证据如下（本机实测，qa 可复执行；`python3 -m py_compile src/stage8/*.py` 通过）：
  - P0-1 VAD advisory：`vad.py:16` 阈值冻结 `(0.3, 0.5)` + `79-91` `observe_vad` 硬门（`filtering=True` 即 `VadError`；阈值非 0.3/0.5 即 `VadError`，本机 0.4/0.0/1.0/`'x'`/`None` 全部拒收）+ `23-25` `is_advisory_only()=True` + `28-37` `vad_profile()`（`filtering=False/drives_chunking=False/drives_audio_choice=False`）+ 观测前后 sha 比对（OK 路径 `127`，SKIPPED 路径音源未写）。本机无 silero/numpy 故状态为 `SKIPPED`（`filtering_applied=False/audio_bytes_equal=True/mode=advisory-only`），与 Stage7 复核“缺 venv 依赖走静态+fail-closed 逻辑验证”同一口径，不卡结论；真调举证留给 QA（S8-T01 双 thr 可复现）。`rg "drop|remove_silence|gate_audio"` 零命中；`filter` 命中仅 `filtering=False` 门控字面（PLAN 明示要求），无过滤动作。
  - P0-2 ChunkPlanner：`chunk_planner.py:11-12` 常量 `CHUNK_SIZE_S=600/CHUNK_OVERLAP_S=2` + `46-50` 尺寸漂移即 `ChunkPlanError` + `30-76` 纯函数（仅 `math`，零 Whisper/零音频 IO）+ core/overlap 归属。本机复算：600s→1 chunk；601s→2 chunk（overlap 恒 2s，core `[0,600)/[600,601]` 无缝无重叠）；1200s→3 chunk（core `0-600/600-1198/1198-1200`）；5s→1 chunk；0/负/NaN/inf/非数字/`True`/`None` 全部 fail-closed；`size_s=300` 拒收。VAD 不驱动边界（planner 签名无 VAD 输入）。
  - P0-3 Timeline+Merge：`timeline.py:53-82` 纯映射（relative 原样保留 + `absolute_start/end = chunk_start + relative`，word 有则同步打绝对戳、无则透传）+ 相对乱序拒收（本机已验）；`merge.py:12-17` 优先级 `core_region > absolute_timestamp > overlap_timestamp > text_similarity` 与 PLAN 四优先级逐字对齐 + `26-32` core 归属（末 chunk 含右端点，其余左闭右开）+ `93-99` 仅“同 `absolute_start` 且同文本”的相邻副本去重（exact 同戳同文，无整篇 dedup）。本机合成夹具复算：overlap 双份输入→恰一份 + absolute 单调 + 非 overlap 区逐字节一致（`merge_n=3`）。`rg -i "fuzzy|difflib|SequenceMatcher|rapidfuzz|levenshtein"` 零命中（`text_similarity` 仅优先级名，系 PLAN 原文要求）；word ON/OFF 双透传（`_map_words` 有无 `words` 均可）。
  - P0-4 接线：`transcribe_chunks.py:22-52` 只读复用 stage1 冻结常量（`FROZEN_MODEL_REPO/REVISION/WORD_DEFAULT/NST0.6/DECODE_DEFAULTS/resolve_model_revision`，未 import stage1 单文件本体）+ stage7 `ENGINE_LANGUAGE/LANGUAGE_STRATEGY/build_for_chunks/check_wav_mono_16k` 只读复用 + `WORKER=1` + `AUDIO_NOTE=temp-wav 16k mono` + `140-172` 单 chunk 单 `mlx_whisper.transcribe` 调用（`word透传/initial_prompt/clip 0/nst 0.6/language zh/verbose False/path_or_hf_repo Frozen`，调用前验 revision match + nst 漂移拒收）+ `345-350` `len(prompts)==len(chunks)`（每 Chunk 经 stage7 重建，复用别 Chunk 即拒收）+ `390-394` `call_count==len` + 合并后 `check_monotonic` + `337-340` VAD 观测仅记录（接线不按 VAD 取舍音频）。`DECODE_DEFAULTS` 经查不含 `word_timestamps/no_speech_threshold` 键，故 `decode` 字典“显式键在前 + `**DECODE_DEFAULTS` 在后”与 stage1/stage7 同序、无覆盖问题。`build_chunk_asr_profile:175-234`（`layer=asr` + `vad_profile/chunking_profile` 只进 ASR + `prompt_profile={200,Global->Topic->Creator,rebuilt_per_chunk=True}` + decode 沿冻结）+ `237-281` hash 输入含 vad/chunking（本机改 thr 即 hash 翻转）+ `284-303` 串层即 `ChunkTranscribeError`（本机已验 normalization 漏入被抓）。真调计数留给 QA（本机无 `mlx_whisper`/tokenizer，不跑引擎）。
  - P0-5 分层/§73：vad/chunking 只进 ASR 层（`assert_asr_layer_only` + 本机漏层测试通过）；`frozen_alignment():62-78` 逐字段对齐（model/revision/word OFF/nst 0.6/explicit-zh/advisory/600/2/worker 1）；§73-24/25/26/27 逻辑链齐备（单调校验/双透传/纯映射公式/逐 Chunk 重建+计数对齐），数值断言留 QA 报告。
  - P0-6 STOP/禁入：`rg "sqlite3|INSERT INTO|UPDATE |DELETE FROM|state\.db|current_path|archived_at"` 零命中（零直写 DB）；`rg -i "paragraph|launchagent|menu_bar|menubar|openai|anthropic|import requests|summar|polish|paraphras|rewrite|clobber"` 零命中（Stage9+ 与 §2.2 禁止项禁入）；`rg "from stage|import stage"` 仅 `stage1.asr` + `stage7.language/prompt_builder/transcribe` + `stage8.*`（stage2/3/4/5/6 零 import，stage4/5/6 零调用）；文件名无 `paragraph/archive/launchagent/menu` 关键词；常量无调优（VAD 0.3–0.5/chunk 600/2/word OFF/nst 0.6/budget 200/order 全对齐冻结值）。
  - P0-7 外置合成门：属 QA 执行域；代码侧无真实目录/真实库/云调用路径（ffmpeg 仅切分输入 wav 落 work_dir，`_cut_chunk_wav:109-137` 按 planner 边界 `-ss start -to end`，与 ffmpeg 官方 `-ss/-to` 输出选项绝对位置用法一致，首 chunk 与后续 chunk 均正确）。文本内容不断言（`run_chunks` 只返回文本）。
  - 无 P1：未发现需 QA 前必修的语义分叉；下节 P2 均不影响 P0-1~P0-7 判据。

## P2 / P3 Backlog Findings

- P2-1 `vad.py:16` `VAD_THRESHOLDS=(0.3, 0.5)` 本地重定义，未 import stage1 `FROZEN_VAD_THRESHOLDS`（值一致，属 Stage7 复核 P2-2 同类双源）。改法：`from stage1.asr import FROZEN_VAD_THRESHOLDS` 单源（或保留本地常量 + 模块加载断言 `assert VAD_THRESHOLDS==FROZEN_VAD_THRESHOLDS`），QA 加一例双源一致断言。
- P2-2 `transcribe_chunks.py:224-228` `prompt_profile={budget_tokens:200, order:"Global->Topic->Creator"}` 字面量双源（vs stage7 `PROMPT_BUDGET_TOKENS/PROMPT_ORDER` + stage1 `FROZEN_PROMPT_BUDGET_TOKENS`，值一致）。改法：从 `stage7.prompt_builder` import 双常量 + 漂移断言，与 P2-1 同批修。
- P2-3 `transcribe_chunks.py:86-106` `_check_chunks` 对显式传入的合成 chunk 列表只验序号/数值/非空/core 界内，不验 overlap 恒 2s 与 core 无缝（冻结几何后门；`result["chunks"]` 虽原样返回可披露，但无 `planner_derived` 标记，profile 仍报冻结 600/2）。改法二选一：① 显式 `chunks` 传入时置 `result["planner_derived"]=False` + 原样披露几何（QA 判读用）；② 对显式列表同样强制 overlap/core 无缝（合成小尺寸多 chunk 场景会变严，须先与 PLAN S8-T04“合成短 chunk 列表”允许口径对齐）。推荐①（披露优先，不误伤 QA 合成接线）。
- P3-1 `__init__.py:3-5`/`transcribe_chunks.py:20` `sys.path.insert(0,.../src)` 导入期副作用。沿 stage1-7 既有模式，不改；仅记一笔。
- P3-2 `transcribe_chunks.py:155` `os.environ.setdefault("HF_HUB_OFFLINE","1")` 进程级副作用无恢复。与 stage1/stage7 同模式，不改；仅记一笔。
- P3-3 `transcribe_chunks.py:18` `import wave` 未使用（实际经 stage7 `check_wav_mono_16k` 验头）。改法：删该行（lint 级，QA 前顺手）。
- P3-4 `src/stage8/__pycache__/` 残留（运行复算产物）。改法：neat-freak 收尾清掉，不进复核结论。
- P3-5 `vad.py:67-76` `_skipped` 直接断言 `audio_bytes_equal=True` 未复哈希（OK 路径 `127` 有复哈希）。实际未写音频，结论为真，但举证不对称。改法：SKIPPED 路径同样 `sha_before == _sha256_file(wav_path)` 实算后填值。
- P3-6 `merge.py:64-111` 非归属 segment 静默丢弃，无丢弃计数披露（设计正确：core 划分覆盖 `[0,duration)`，非 overlap 区永不丢；仅幻觉超界戳会丢）。改法：返回体加 `dropped_n` 供 QA 披露，不改变归属语义。
- P3-7 `transcribe_chunks.py:140-172` word ON 透传不要求 `S1_T03_WORD_ON_DECLARED=1`（stage1 本体门的声明机制）。系设计使然（stage8 从不调用 stage1 本体，PLAN 要求 ON 不断链），不改；仅记一笔：QA 报告写明 stage8 ON 路径独立于 S1 声明 env。
- P3-8 `transcribe_chunks.py:35-37` 从 `stage7.transcribe` 复用 `check_wav_mono_16k`，超出 PLAN 点名的 stage7 复用名单（`load_vocabulary/build_initial_prompt/build_for_chunks/LANGUAGE_STRATEGY/build_asr_profile`）。只读复用、无语义复制、不改 stage7，无阻塞；仅记一笔：PLAN 名单加“等只读”或 QA 视作只读复用通过。
