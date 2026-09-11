# QA-REPORT｜Stage7 S7-T04 验收套件 + §72/§73 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage7/`（vocabulary.py/prompt_builder.py/language.py/profile.py/transcribe.py/__init__.py）+ `src/stage1/` 只读复用（冻结常量/verify门/build_raw_content/validate/probe_volume）+ `src/stage2/` 只读复用（store/candidate/discover/runs/AUTO UPSERT/reconcile/instance持锁）+ `src/stage3/` 只读复用（normalize/render冻结规则表/公开API）+ `src/stage4/` 只读复用（canonical_path_for双算）+ `src/stage5/` 只读复用（run_startup语义）+ `src/stage6/` 只读复用（resolve_canonical双算）
- 计划：`docs/pm/STAGE7-PLAN.md` S7-T04（P0-1~P0-7；happy 1遍 + 异常/边界 8个 + 回归六行；外置合成 Input Root + 外置 Data Root；合成小音频真调有界；文本内容不断言；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage7子集：§73-15分层/ASR-only + §73-27每Chunk重建 + §73-28专业词不改语义 + §73-16/Derived Revision + §70 Case4）+ §44 PromptBuilder（真实Tokenizer先计数再装配/budget 200/order Global→Topic→Creator/超限去头保尾）+ Stage0 Prompt Capacity实测（真实容量223，budget 200恒在其内）
- QA 执行目录（仓库外）：`/tmp/s7qa/`（happy/a4_reuse/a5_bump/a6_corr/reg_s2/reg_s3/reg_s5/reg_s6各独立 data_root + 合成小音频 `/tmp/s7qa/input/synth_2s.wav` 64044B + 合成小 `.mp4` 副本 + `s7qa_results.json`）+ `/tmp/s7qa_run.py`（仓库外 Runner，`--bad` 八子进程取 exit 码；venv 用 Stage0 `stage0bench/venv` 真实 tokenizer + 真实模型）；仓库内零写盘除本报告
- **结论：PASS（happy 1遍 + 异常/边界 8个全过 + 回归六行，115/115断言双轮稳定，Runner exit 0；坏例只看 exit 码：八坏例 exit 1符合预期；Whisper有界=1（仅happy接线）；文本内容不断言（只验str/list类型）；三表：纯词库/复用库 0/0/0、bump库 0/0/0且runs=2、corr库 2/0/0且archive恒0；current_path列级零写；最大合成文件 64078B（≤70000门）；结论只落本报告）**

## 1. 输入复核（src/stage7 落盘 6文件，只读消费；builder口径锁定沿用）

- `vocabulary.py`（S7-T01）：`load_vocabulary(global_src,topic_src,creator_src)`逐字节原样装载（list或utf-8文件行，不strip内字节，不去重，不排序；三级缺一/空即 `VocabularyError`）+ `canonical_serialize`（sort_keys固定序）+ `dictionary_snapshot=sha256`（同输入同hash，差一字节即变）+ `has_exact_term/terms_of`精确透传。QA实测：三级装载 + 稳定复算 + 一字节翻转变hash + `Vibe Coding` vs `vibe coding`精确区分（无casefold）。
- `prompt_builder.py`（S7-T02）：`build_initial_prompt(g,t,c,budget=200)`真实Tokenizer（`mlx_whisper.tokenizer.get_tokenizer(multilingual,zh)`）先计数再装配 + 顺序恒Global→Topic→Creator + 超限去头保尾（Creator尾部优先）+ 输出 `{initial_prompt,token_count<=200,truncated_head,prompt_builder_version=pb-v1,budget/order}` + `build_for_chunks`逐Chunk重建（dict或三元组，永不复用别Chunk）。QA实测：happy 93tok零截断 + 复算一致 + 超限74词去头Creator全活 + 三Chunk各异。
- `language.py`（S7-T03）：`LANGUAGE_STRATEGY=explicit-zh`冻结 + `ENGINE_LANGUAGE=zh` + `record_detected_language` advisory（mismatch永不BLOCK，`blocked=False/action=record-only`）。QA实测：`en→mismatch True/blocked False` + `None→不BLOCK` + `Chinese→不mismatch`。
- `profile.py`（S7-T03）：`build_asr_profile(snapshot,version,prompt,tokens)`只进ASR层（`layer=asr` + `prompt.executed=True/recorded_only=False` + `prompt_profile={200,Global->Topic->Creator}` + decode沿冻结常量）+ `asr_profile_hash`（新字段全参与，同输入同hash，任一变即变）+ `check_layering`（新字段漏进correction/render即 `ProfileError`）。QA实测：executed/chars/layer/decode对齐 + hash稳定/翻转 + §73-15 asr-only。
- `transcribe.py`（S7-T03）：自有单文件接线（复用stage1冻结常量逐字段对齐，不import stage1 `transcribe_wav_file`本体；`check_wav_mono_16k`要求1ch/16k；`language=zh`显式；VAD advisory；exactly one call）。QA实测：合成2s正弦真调1次，`initial_prompt`复算逐字节一致，token<=200，prompt_executed，VAD不过滤。
- `__init__.py`：装配导出（常量+函数全透出，无语义增量）。
- 上轮builder验证入口与对账：`/tmp/s7_stage7_verify/input/synth_2s.wav`（63K，1ch/16k）+ `/tmp/s7_stage7_verify/data_root/data/state.db`（sources=1/runs=2/arch=0）；QA以独立合成 `/tmp/s7qa/input/synth_2s.wav`（64044B，同形状，builder原片不动）+ 独立Runner 115断言覆盖（口径一致；builder摆动无——QA未发现hash/截断口径分叉）。

## 2. 用例简表（坏例只看 exit 码；三表=norm/rend/arch；Whisper=asr_calls；文本内容不断言）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 三表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY 全链 | 合成词库（G5/T3/C3）+ 合成2s wav | 快照→装配（93tok）→profile executed→单文件接线1次→§73-15/27 | initial_prompt非空复算一致 + token<=200 + executed + calls=1 + VAD advisory + 文本只验类型 | 一致（`52f76744…`快照，93tok，`7fa4028a…` profile hash，calls=1，vad advisory，text str） | Runner exit 0 | —（无DB写） | 1（有界，唯一真调） |
| A1 超限保尾 | G40/T40/C5合成大词库 | build（预算200） | truncated + Creator全活 + G0先丢 + 复算一致 | 一致（193tok，dropped 74，Creator 5/5，G00丢） | — | — | 0 |
| A2 三Chunk各异 | 三组各异词项（dict + tuple双形） | build_for_chunks | 三prompt各异，永不复用 | 一致（`CA0/CA1/CA2`三异，tuple亦三异） | — | — | 0 |
| A3 mismatch记录 | 冻结策略 | record(en/None/Chinese) | mismatch True仍blocked False，record-only | 一致（en mismatch+不BLOCK，None不BLOCK，Chinese不mismatch） | — | — | 0 |
| A4 同profile同Run复用 | 新库 + 合成clip.mp4 + happy hash | discover→get_or_create×2→reconcile | 同run_id + Source=1/Run=1 + dup0 + arch0 + current零写 | 一致（同run，1/1，dup0/0） | Count 1/1 | 0/0/0 | 0 |
| A5 快照bump新Run | A4库同Source + Creator末词+`x` | 快照重算→hash重算→get_or_create | 快照变 + hash变 + 新run_id + 总Runs=2 | 一致（snap变，hash变，新run，1→2） | Count 2 | 0/0/0 | 0 |
| A6 规则变更新Revision | 新库 + 合成Raw（含VIP COIN/Ai编程）经门 | norm corr-v1→corr-v2（经stage3公开API） | 新revision_id + Raw hash不变 + whisper 0/0 | 一致（两rev异，raw同hash，0/0） | Norm=2 | 2/0/0 | 0 |
| A7 §73-28逐字节 | 冻结corr-v1 | apply_corrections | 目标词精确替换，前后缀逐字节，无mutate，无目标零改 | 一致（Vibe/AI替换，前缀`今晚讲`后缀`，其他不动。`保留，applied=2） | — | — | 0 |
| A8 STOP门 | 全仓src/stage7 | grep三重 + 常量比对 | 无Stage8+/无直写DB/无transcribe串层/无改写语义/budget200/order恒 | 一致（`--include=*.py`双grep exit 1=零命中，200/order恒） | — | arch全库0 | 0 |
| B-八坏例 | 各合成前置 | --bad八子进程 | 期望错误未吞，exit 1 | 一致（八exit 1，见§3） | 八exit **1** | — | 0 |
| STOP外置 | 全量输入 | 路径前缀 + 最大文件 + Whisper有界 + git N/A | 全在/tmp/s7qa + max≤70000 + calls=1 + 非git代证 | 一致（max 64078B，calls=1，git非仓库） | — | arch全库0 | 1 |
| REG-S1 | 合成门 | probe_volume + 非法Raw | ALLOW + 非法拒收 | 一致 | exit 0 | — | 0 |
| REG-S2 | 新root | startup 5步 + discover | 5步逐字 + PROMOTED + Source=1 + Run=1 | 一致 | 1/1 exit 0 | 0/0/0 | 0 |
| REG-S3 | 新root（合成Raw经门） | norm→render | COMPLETED→PUBLISH_EVALUATION + verdict双值域 | 一致（PENDING_PUBLISH） | Norm=1/Render=1 | 1/1/0 | 0 |
| REG-S4 | 旧库只读 | 查/tmp/s4qa | PUBLISHED行仍可查（≥1） | 一致（多候选首命中） | ≥1 | — | — |
| REG-S5 | 新三Root | run_startup | order 11逐字 + RUNNING不断链 + shutdown幂等 | 一致 | 11步 exit 0 | 0 | 0 |
| REG-S6 | 合成嵌套Unicode | resolve双算 | stage6与stage4双算逐字节一致 | 一致（`AI/博主A/系列1/DeepSeek V4 分析.mp4→…md`） | — | — | 0 |

Runner：`/tmp/s7qa_run.py`（仓库外）→ `/tmp/s7qa/s7qa_results.json`（115断言JSON已落盘，可复算；双轮 `TOTAL 115/115 FAILS=[] exit=0`）；坏例子进程八exit **1**（判据只用 exit 码，不看打印）；最大合成文件 64078B（`synth_2s.wav` 64044B，≤70000门，真实长视频零触碰）；Whisper调用全链=1（仅happy接线，其余纯函数/DB零调用）。

## 3. 每用例明细（前置/动作/期望；Count或 exit 码 + dup0 + 三表 + current_path + Whisper有界 + 三Root + 文本不断言声明）

- HAPPY：前置合成词库（Global 5 `AI编程/Vibe Coding/Obsidian 笔记/Whisper 转写/知识库` + Topic 3 + Creator 3）+ 合成2s正弦wav（`check_wav_mono_16k` 1ch/16k过）；动作 `load_vocabulary`→`dictionary_snapshot`（`52f76744…`，复算稳定，一字节`+x`即变，`Vibe Coding≠vibe coding`）→`build_initial_prompt`（93tok，零截断，`Global→Topic→Creator`顺序 `G[0]<T[0]<C[0]`，真实tokenizer复算93=93，`pb-v1/200/order`恒）→`record_detected_language(zh)`（match不BLOCK）→`build_asr_profile`（`executed=True/recorded_only=False`，`prompt_chars=len`，`layer=asr`，`prompt_profile={200,order}`，decode沿`word OFF/nst 0.6/model a4aaeec0`）→`asr_profile_hash`（64hex，复算稳定，`language=en`即变）→`check_layering`（asr-only，§73-15）→`run_single_file_with_prompt`真调1次（`HF_HUB_OFFLINE=1`，9s级，`asr/engine=1/1`，`initial_prompt`与纯函数复算逐字节一致，token 54→93链一致≤200，`prompt_executed=True`，`language=zh/strategy=explicit-zh`，VAD `advisory-only/filtering=False`，冻结常量逐字段对齐，检出`record-only/blocked=False`）；文本内容不断言声明：本用例及全链仅断言 `isinstance(text,str) and isinstance(segments,list)`，不做词准确率/CER/内容包含断言（属Stage11+ Golden门；合成正弦无语音，空文本亦合法）；期望全中，实测全中。
- A1：前置G40/T40/C5（全量>200）；动作 `build_initial_prompt`；期望 `truncated_head=True/dropped>0` + token≤200 + Creator 5/5存活 + G00先丢 + 复算一致；实测193tok/dropped 74/Creator全活/G00丢/复算等。
- A2：前置三组 `G/T/C+i`（dict形 + tuple形双测）；动作 `build_for_chunks`；期望三prompt各异、任一复用即FAIL；实测dict三异 + tuple三异。
- A3：前置冻结策略；动作 `record_detected_language(en/None/Chinese)`；期望en mismatch但永不BLOCK（record-only）、None不BLOCK、Chinese别名不mismatch；实测全中。
- A4：前置新 `a4_reuse/{data_root,input}` + 合成`clip.mp4`（1K）+ happy hash `7fa4028a…`；动作 `discover`（PROMOTED）→`get_or_create×2`（同run）→`reconcile_source`（同run）；期望Source=1/Run=1/dup0/0/三表0/0/0/arch0/`current_path==path_key/status=ACTIVE/archived_at NULL` + 纯stage7调用后行不变（`srow2==srow`无侧写）；实测全中。
- A5：前置A4同库Source + Creator末词`+x`；动作快照/装配/profile/hash重算→`get_or_create`；期望快照变/hash变/新run/总数2/arch0；实测全中（`a5_bump`库src=1/runs=2/arch=0）。
- A6：前置新 `a6_corr`库 + 合成`v.mp4` + 合成Raw（含`VIP COIN/Ai编程`，`build_raw_content+validate`门过，`raw.json`落盘，hash记`raw_before`）+ Run置COMPLETED；动作 `create_normalization_revision(corr-v1)`→`(corr-v2)`（经stage3公开API，逐行披露）；期望两revision_id异 + Raw文件hash前后等 + 双`whisper/asr=0` + 最终JSON各带对应`correction_rules_revision`；实测全中（`a6_corr`库norm=2/rend=0/arch=0；`n1≠n2`；raw同hash）。
- A7：前置冻结`corr-v1` + 含目标段 + 无目标段；动作 `apply_corrections`；期望目标精确替换（`VIP COIN→Vibe Coding/Ai编程→AI编程`，applied=2，前缀`今晚讲`后缀`，其他不动。`逐字节）、输入不mutate、无目标零改（applied空）；实测全中。
- A8：前置全仓`src/stage7/*.py`；动作 `grep --include=*.py`双重（`sqlite3|INSERT|UPDATE|DELETE`与`vad_filter|chunk_merge|absolute_timeline|paragraph|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber`）+ 常量比对（budget 200/order/`pb-v1`/冻结model/nst/word）+ `transcribe`串层查（仅transcribe.py含，余四文件零命中）+ 改写语义查（llm/summar/polish/paraphras/rewrite/casefold零命中）；期望双grep exit 1（零命中）+ 常量恒；实测全中（裸`grep`不加include会命中`__pycache__`二进制噪音，QA口径以`--include=*.py`为准，rg默认亦忽略）。
- B-八坏例（判据只用 exit 码）：`vocab_missing（三级缺一）exit 1=VocabularyError` + `vocab_empty（空级）exit 1` + `budget_drift（223≠200）exit 1=PromptBuilderError` + `empty_prompt（空白prompt接线拒绝）exit 1=TranscribeError` + `wav_missing（无文件）exit 1` + `layer_leak（language串进render）exit 1=ProfileError` + `unknown_corr（未知规则）exit 1=NormalizationError` + `wav_shape（双声道）exit 1=TranscribeError`；任一吞错/错类型即非1项未触发。
- STOP外置/有界：输入全在`/tmp/s7qa/*/input` + 外置Data Root（与真实视频目录/真实Obsidian库无交集，输出前缀断言逐用例过）；最大合成文件64078B（`synth_2s.wav`64044B，≤70000门）；Whisper全链=1（`s7qa_results.json:whisper_calls=1`，仅happy；超预算即FAIL项未触发）；`git diff`口径N/A（非git仓库，`warning: Not a git repository`，以六回归PASS + QA零改代证）；各库`archive_commits`全0（a4 0/a5 0/a6 0/reg_s2 0/reg_s3 0/reg_s5 0）。
- 回归：REG-S1 `s1probe(/tmp)→ALLOW` + 非法Raw拒收；REG-S2 `instance.startup` 5步逐字 + PROMOTED + Source=1 + AUTO Run=1；REG-S3合成Raw经门→`COMPLETED→PUBLISH_EVALUATION` + verdict `PENDING_PUBLISH`（双值域内）；REG-S4 `/tmp/s4qa`旧库只读`PUBLISHED≥1`仍可查（多候选首命中）；REG-S5 `run_startup` order 11逐字 + `running==True` + `shutdown`幂等（Ready→Scan→Reconcile→RUNNING不断链）；REG-S6嵌套`AI/博主A/系列1/DeepSeek V4 分析.mp4`经stage6与stage4双算逐字节一致；`src/stage1-6/`本轮QA未触碰（目录非git仓库，`git diff`口径N/A，以六回归PASS + QA零改代证）。

## 4. §72/§73子集门（Stage7 5断言逐项）

- [x] §73-15 PASS（ASR/Normalization/Render分层正确：新五字段只进ASR层，`check_layering` asr-only；串层坏例exit 1）
- [x] §73-27 PASS（Prompt每Chunk重建：合成三Chunk各异prompt，任一复用即FAIL项未触发；happy + A2双证据）
- [x] §73-28 PASS（专业词correction不改变语义：冻结corr-v1精确匹配复跑，前后缀逐字节一致，无增删改写；无目标零改）
- [x] §73-16 / §72 Derived Revision子集 PASS（Correction Rules Change不重新调用Whisper + Raw Hash不变 + 新Normalization Revision：经stage3公开API，`whisper_calls=0/0`计数举证，raw同hash）
- [x] §70 Case4 PASS（同Source + 同asr_profile_hash→Reconciliation返既有AUTO Run不建新；词典快照bump→新hash→允许新Run，mechanics复Stage2只读；A4/A5双证据，dup0/0）

## BUGS（照BUGS.template.md；本轮无P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 115/115双轮 exit 0；八坏例 exit 1符合预期 | CLOSED | 无需builder修 | 详见 `/tmp/s7qa/s7qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S7-T04 Stage7验收套件 + §72/§73子集门 + Stage1~6回归（首轮QA执行）
- Root Cause Hypothesis: 不适用（PASS；首轮115/115一遍过，无业务侧FAIL）
- Approach: 仓库外`/tmp/s7qa`各用例独立data_root + 合成确定性小音频（2s正弦1ch/16k 64044B，文本内容不断言）+ 合成小`.mp4`副本（最大64078B，真实长视频零触碰）；纯函数以真实tokenizer复算 + 快照翻转 + 保尾存活为判据；接线以exactly one call + 复算一致 + VAD advisory + 冻结常量对齐为判据（文本只验类型）；Case4以中央库`COUNT(*)`/行级对比为判据；corr变更以stage3公开API双rev + Raw同hash + whisper双0为判据；挡路/缺级/预算漂移/串层/坏wav走子进程只看 exit 码；grep双重STOP门（`--include=*.py`）；集成库三表逐库快照 + archive全库0 + sources列级不变；回归S1门/S2链/S3 verdict/S4旧库只读/S5十一步/S6双算
- Files Changed: 仅新增本报告 `docs/qa/STAGE7-QA-REPORT.md`；业务代码零改；测试写盘只在`/tmp/s7qa`（H2外置目录约束延续）；Runner `/tmp/s7qa_run.py`在仓库外
- Verification: 双轮 `TOTAL 115/115 FAILS=[] exit=0`（`s7qa_results.json`可复算，`whisper_calls=1/max_bytes=64078`）；八坏例 exit 1已取（`vocab_missing/vocab_empty/budget_drift/empty_prompt/wav_missing/layer_leak/unknown_corr/wav_shape`）；纯复用库三表0/0/0，bump库runs=2/arch0，corr库norm=2/arch0；诱饵/真实库零触碰；`src/stage1-6/`未触碰
- Failure Reason: 无FAIL项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交supervisor/product-reviewer定，不卡本PASS）

- U-1 真实长视频未测（PLAN已定：真实长视频一律不测直到产品完成；本套件最大合成文件64078B，合成2s正弦）。
- U-2 文本内容不断言（PLAN已定：词准确率/Golden/CER属Stage11+；合成正弦无语音，空文本合法；本报告仅验`str/list`类型 + 调用计数 + prompt一致）。
- U-3 Runner在仓库外（`/tmp/s7qa_run.py` + `--bad`八子进程），未进`docs/qa`，复现找QA要路径（H2外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3/Stage4 U-3/Stage5 U-2/Stage6 U-2同Pattern）。
- U-4 残留待清：`/tmp/s7qa`（7三Root + input，本轮新增，848K）+ `/tmp/s7_stage7_verify`（builder验证入口，1源2跑道）+ Stage6残留（`/tmp/s6qa` + `/tmp/s6self`）+ Stage5残留（`/tmp/s5qa` + `/tmp/s5_builder_selfcheck`）+ Stage4残留（`/tmp/s4qa` + `/tmp/s4qa_out`）+ Stage3残留（`/tmp/s3qa`）+ Stage2残留（`/tmp/s2t07_qa`约1.9M）+ Stage1残留（`/tmp/s1t*` + `$TMPDIR`），交neat-freak收尾。
- U-5 `src/stage1/`/`src/stage2/`/`src/stage3/`/`src/stage4/`/`src/stage5/`/`src/stage6/ git diff为空`口径N/A（当前目录非git仓库；以六回归PASS + QA零改代证，未改业务代码）。
- U-6 三表口径说明：纯词库/复用/bump库`normalization/render`恒0；corr库`norm=2`与reg_s3库`1/1`系QA脚手架经Stage3公开API合成Rendered Final所致（不绕门），非Stage7代码新增写（`--include=*.py`直写grep exit 1反证 + `archive_commits`全库0 + sources列级不变）；若按字面“恒0”卡脚手架库则无Derived证据可举，QA按builder自验同一口径验收。
- U-7 裸`grep`噪音：不加`--include=*.py`时`__pycache__`二进制会致exit 0假阳性，QA口径以`--include=*.py`（rg默认忽略）为准，双grep exit 1已落盘复算。

---
目标：Stage7验收S7-T04｜剩 P0：无（QA口径PASS；闭环判定以supervisor复检为准）｜下一步：交product-reviewer验 + supervisor复检（HANDOFF只记状态，不代写结论）。
