
# CODE REVIEW

- Task: 复核src/stage7/（对照STAGE7-PLAN + 禁LLM/云/总结改写/禁DB直写/Stage8+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage7/ 六文件现状：__init__.py / vocabulary.py / prompt_builder.py / language.py / profile.py / transcribe.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0；无 P1；P2×5 + P3×4 记 backlog，不阻塞 QA/supervisor；QA 已 115/115 PASS，本复核独立静态+纯函数复算口径一致，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无 P0。本轮硬门逐项通过，证据如下（本机实测，qa 可复执行）：
  - P0-1 词库快照：`vocabulary.py:16-63` 三级逐字节原样装载（list 或 utf-8 文件行，不 strip 内字节、不去重、不排序；三级缺一/空即 `VocabularyError`）+ `66-88` 规范序列化（`sort_keys/separators` 固定序，仅取 LEVELS 子集）+ `sha256` 快照；`98-106` 精确匹配 `==` 透传。本机纯函数复算：同输入同 hash、差一字节即变（`g1→g2` 翻转）、`Vibe Coding≠vibe coding`（无 casefold）。`rg -i "llm|summar|polish|paraphras|rewrite"` 零命中；`rg "casefold|normalize\(|slugify"` 在词库存值路径零命中（仅 `json.encode("utf-8")/tokenizer.encode` 与 `language.py:30` 检出别名 `.lower()`，非词条归一）。
  - P0-2 PromptBuilder：`prompt_builder.py:5-7` 预算 200/order `Global->Topic->Creator`/版本 `pb-v1` 全常量 + `54-55` 预算漂移即 raise + `42-98` 先计数再装配、顺序恒 Global→Topic→Creator、超限去头保尾（`69-71` 头部逐词丢，尾部 Creator 存活）+ 输出含 `{initial_prompt,token_count,truncated_head,prompt_builder_version,budget/order}` + `101-122` 逐 Chunk 重建（dict 或三元组，永不复用别 Chunk）。`rg "transcribe|requests|openai|http" prompt_builder.py vocabulary.py` 零命中；`_get_tokenizer:27` 仅 `from mlx_whisper.tokenizer import get_tokenizer`，无 transcribe/云调用。本机因无 `mlx_whisper` 未跑 tokenizer 复算（`ModuleNotFoundError`），装配语义以静态+QA 真实 tokenizer 复算（93=93、超限 193tok/Creator 5/5）为证，不卡本结论。
  - P0-3 语言+分层：`language.py:5-6` `explicit-zh/zh` 双冻结 + `23-38` 检出 advisory（`mismatch` 仅记录，`blocked=False/action=record-only` 恒不 BLOCK，`None` 不 BLOCK）；`profile.py:39-89` 新五字段只进 ASR 层（`layer=asr` + `prompt.executed=True/recorded_only=False` + `prompt_profile={200,order}` + decode 沿冻结常量）+ `92-121` 身份 hash 全含新字段（同输入同 hash，任一新字段变即变）+ `124-145` 串层即 `ProfileError`。本机纯函数复算：`missing/empty` 抛 `VocabularyError`、`layer_leak` 抛 `ProfileError` 逻辑成立。
  - P0-4 单文件接线：`transcribe.py:12-20` 只读复用 stage1 冻结常量（`MODEL_REPO/REVISION/WORD_OFF/NST0.6/BUDGET200/DECODE_DEFAULTS/resolve_model_revision/vad_observe_only`），未 import `transcribe_wav_file` 本体（`rg transcribe_wav_file src/stage7/` 零命中，为证）+ `34-52` 要求 1ch/16k + `55-94` 单函数单 `mlx_whisper.transcribe` 调用（`word OFF/initial_prompt/clip 0/nst 0.6/language zh/verbose False/path_or_hf_repo Frozen`，逐字段对齐 stage1 `asr.py:182-190` 形状，新增仅 `initial_prompt` 非空与 `language=zh`，系 PLAN 明示替换语义）+ `96` VAD 仅 `vad_observe_only` + 返回 `asr_calls=1/engine_calls=1/prompt_executed=True`。`HF_HUB_OFFLINE=1` 与 stage1 同口径。
  - P0-6 STOP/禁入：`rg "vad_filter|chunk_merge|absolute_timeline|paragraph|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber" src/stage7/` 零命中；`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage7/` 零命中；`rg -i "vad_filter|chunk_merge|absolute_timeline|launchagent|menu bar|openai|anthropic" src/stage7/` 零命中；`rg "requests|urllib|httpx|boto3|cloud|api_key" src/stage7/` 零命中；`rg "current_path|archived_at|archive_commits" src/stage7/` 零命中；`rg "from stage[2-6]|import stage[2-6]" src/stage7/` 零命中（仅只读 `stage1.asr`）。`VAD/Chunk` 命中仅 `vad_observe_only` advisory 与 `build_for_chunks` 纯装配（无音频切分/Merge/Timeline/Paragraph/Archive/LaunchAgent/Menu），属 PLAN 明示允许。阈值恒定：budget 200 与 `FROZEN_PROMPT_BUDGET_TOKENS=200` 一致、order 恒、model `mlx-community/whisper-large-v3-turbo`/`a4aaeec0`/`word OFF/nst 0.6` 全对齐。文件名无 Stage8+ 关键词。`python3 -m py_compile src/stage7/*.py` 通过。
  - 无 P1：未发现需 QA 前必修的语义分叉；下节 P2 均不影响 P0-1~P0-7 判据，QA 115/115 已覆盖。

## P2 / P3 Backlog Findings

- P2-1 `prompt_builder.py:26-39,69,79` tokenizer 每次计数重载（超限 74 词丢即 70+ 次 `get_tokenizer`）。正确但慢。改法：模块级单例缓存（如 `_TOK=None` + `global` 复用，或 `functools.lru_cache` 包 `get_tokenizer`），现有超限/复算用例行为不变。
- P2-2 `profile.py:24` `PROMPT_ORDER` 本地重定义，与 `prompt_builder.py:6` 同值双源。现一致故不阻塞。改法：`from stage7.prompt_builder import PROMPT_ORDER` 单源，或在注释写明双常量须同改并加断言 `assert PROMPT_ORDER==prompt_builder.PROMPT_ORDER`。
- P2-3 `vocabulary.py:91-95` `terms_of` 缺级时 `vocab[level]` 抛 `KeyError` 而非 `VocabularyError`（`canonical_serialize` 有缺级检查，本函数无）。改法：先 `if level not in vocab: raise VocabularyError`，与 `load`/`serialize` 口径对齐；QA 加一例缺级 `terms_of` 断言 `VocabularyError`。
- P2-4 `prompt_builder.py:39` `count_tokens` 对 `text.strip()` 计数，但存值 `initial_prompt` 为未 strip  join 结果；`vocabulary.py:44-47` 允许首尾带空格词条（如 `" hello "`）。极端带空格词可致 `token_count<=200` 过而引擎侧多 1~2 token。改法二选一：① 装载期拒绝首尾空白（`if item!=item.strip(): raise`）；② 计数期不对全串 strip（`tok.encode(" "+text)`）。推荐①（fail-closed，保快照逐字节语义由调用方显式清洗）。
- P2-5 `prompt_builder.py:72-81` 单巨词头部字符截断为死码：单 term 超限时 `kept=kept[1:]→[]` 先触发 `if not kept: raise`，到不了字符截断循环。现行为 fail-closed 可接受，但 docstring“尾部字符保留”误导。改法二选一：① 删字符截断分支并改 docstring 为“单 term 超限即 raise”；② 真实现字符级保尾（单 term 时不整词丢，直接进字符截断）。推荐①（单 term>200token 病态，raise 比静默截断安全）。
- P3-1 `__init__.py:3-5`/`profile.py:10`/`transcribe.py:10` `sys.path.insert(0,.../src)` 导入期副作用，与安装包并存时顺序相关。沿 stage1-6 既有模式，不改；仅记一笔。
- P3-2 `transcribe.py:80` `os.environ.setdefault("HF_HUB_OFFLINE","1")` 进程级副作用无恢复。与 stage1 同模式，不改；仅记一笔：并行 Runner 如需在线先显式设值。
- P3-3 `language.py:30-31` 别名表仅 `zh/chinese/cmn`，`zh-cn/zh-hans/yue` 会标 `mismatch True`。设计上仍 `blocked=False` 永不 BLOCK，故仅记录口径问题，不改；仅记一笔。
- P3-4 `src/stage1-6/` 零修改硬门本窗口无法用 git 证明（`Not a git repository`）。代码侧 stage7 无写 stage1-6 路径、仅只读 import stage1，故不阻塞。改法：QA/supervisor 用快照对比或落盘清单补证，结论进 QA 报告（QA 已以六回归 PASS + 零改代证，见 `STAGE7-QA-REPORT.md §3 STOP外置/U-5`）。
