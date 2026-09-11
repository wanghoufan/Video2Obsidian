
# CODE REVIEW

- Task: 复核src/stage9/（对照STAGE9-PLAN + 纯确定语义/禁LLM/规则序冻结/经stage3 API/Stage10+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage9/ 四文件现状：__init__.py / rules_v2.py / formatter_v2.py / derive_v2.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0；无 P1；P2×2 + P3×4 记 backlog，不阻塞 QA/supervisor；本复核独立静态+纯函数实测，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无 P0。本轮硬门逐项通过，证据如下（本机实测，qa 可复执行；`python3 -m py_compile src/stage9/*.py` 通过）：
  - P0-1 Case 4 延续（S9-T01，§45/§29）：`rules_v2.py:43/46` `RULES_REVISION="s9-corr-v2"`（bump）/`BASE_RULES_REVISION="corr-v2"` + `49-52` `ADDED_RULES=(("Github","GitHub"),("Vscode","VS Code"))`（高度确定大小写/空格修复，`validate_rules:64-100` 形状门：非对/空边/同边/超 64 字符/两边长度差超 16 即 `RulesError`，本机改写语义长串已验拒收）+ `103-119` `full_table()` 冻结基行逐字取自 `stage3.normalize.CORRECTION_RULES["corr-v2"]`（非手抄，缺基即拒不自造）+ `153-164` `new_normalization_profile()` 仅动 `correction_rules_revision` 一字段（其余五字段原样继承，本机已验）+ `apply_v2` 走冻结 `apply_corrections`（`stage3` 源码已核：纯 `str.replace` 精确子串语义，无 IO/网络/模型）。本机新旧分歧复现：`Github/Vscode` 句在 corr-v1/v2 下零命中原文不动，s9 下恰两处替换（`applied` 计数 2），其余逐字节一致。
  - P0-2 Case 5 延续（S9-T02，§47/§30）：`formatter_v2.py:35/38` `FORMATTER_VERSION="para-v2"`/`BASE_FORMATTER_VERSION="para-v1"` + `43-47` `PARA_PARAMS_V2={pause 1.5, target 240, hard_max 400}`（相对冻结 `{1.5, 180, 400}` 仅 `target_chars` 单旋钮移动，pause/hard-max 原位，本机已核 `stage3.render.DEFAULT_PROFILE`）+ `63-74` `new_render_profile()` 仅动 `paragraph_formatter_version` + `paragraph_parameters` 两字段（其余三字段原样继承；基漂移即 `FormatterError` 拒不自造）+ `51-56` `RULE_ORDER=(long_pause, strong_punctuation, target_length, hard_max)` 与 PLAN §47 逐字对齐，且模块内无段落引擎自实现（`render_with_v2:77-79` 直调冻结 `render_paragraphs`；`stage3.render` 源码已核边界检查确为 pause→强标点→目标长→硬上限固定序）。本机 `check_rule_order()` 四探针全 `True`（`all_pass=True`）；单旋钮分歧复现：200 字+`。`夹具在冻结版断成 2 段、在 v2 下合成 1 段，分歧仅来自 `target_chars`。
  - P0-3 Case 6 + 默认不覆盖：`derive_v2.py:56-84` `derive_case4` 调 `derive.derive_on_correction_change`（新 NormProfile + 冻结 render，下游新 Rendered，Case 4 隔离 Correction 变更）+ `87-112` `derive_case5` 调 `derive.derive_on_formatter_change`（新 render profile，NormRev 数不变由 stage3 层抛错保证）；`stage3.derive` 源码已核两函数签名与调用逐参对齐（含 `title/canonical_probe_path/source_id/run_id` 透传），返回体自带 `whisper_calls=0/asr_calls=0`；本模块零 publish 调用、零 Run 行读写（下条 grep 门举证）。
  - P0-4 STOP EXPANSION 门：`rg -i "openai|anthropic|llm|summar|polish|paraphras|rewrite"` 在 `src/stage9/` 零命中（§2.2/改写润色禁入）；`rg "run_asr_single_file|archive|launchagent|menu|openai|anthropic|requests\.|llm|summar|polish|paraphras|rewrite|force|overwrite|clobber"` 零命中（Whisper 入口/Archive/`current_path` 回填/LaunchAgent/Menu Bar 禁入）；`rg "sqlite3|INSERT|UPDATE|DELETE"` 零命中（零直写 DB，一切行效应经 stage3 公开 API）；`rg "from stage|import stage"` 仅 `stage3.normalize/render/derive`（stage1/2/4/5/6/7/8 零 import，stage4/5/6/7/8 零调用）；文件名仅 `rules_v2/formatter_v2/derive_v2/__init__`（无 archive/launchagent/menu/golden 关键词）。`src/stage1-8/` diff 门：工作区无 git，静态举证替代——stage9 内无任何写盘路径指向 `src/stage1-8/`（仅三处 `sys.path.insert` 读用 + 只读 import），文件级 diff 留 QA 在有基线的环境补断言。
  - P0-5 外置合成门：属 QA 执行域；代码侧无真实目录/真实库/云调用路径（四文件 import 仅 `os/sys/typing/stage3/stage9`，无网络/音频/文件写 import；`canonical_probe_path` 仅透传给 stage3 做 verdict 探测，零字节回填 canonical）。
  - 无 P1：未发现需 QA 前必修的语义分叉；下节 P2 均不影响 P0-1~P0-5 判据。

## P2 / P3 Backlog Findings

- P2-1 `rules_v2.py:122-150` `register_rules` 运行时向 `stage3.normalize.CORRECTION_RULES` 全局装新键（文件不碰，仅内存映射；幂等 + 同键异内容拒换已披露）。改法：保持现状 + QA 加一例“注册后冻结基行逐元组不变”（`tuple(CORRECTION_RULES["corr-v2"])` 前后比对），防未来误写基键；`full_table` 已在调用期现读基行，无导入期快照过期问题，不改。
- P2-2 `derive_v2.py:69/99` `frozen_render=dict(DEFAULT_PROFILE)` 与 `formatter_v2.render_with_v2` 的 `dict(PARA_PARAMS_V2)` 均为浅拷贝（嵌套 `paragraph_parameters` 与 stage3 全局共享引用）。改法：下游当前只读（`stage3.render` 源码已核无 profile 原地写），不改逻辑； unify 为 `copy.deepcopy`（两处各一行），QA 加一例“derive 前后 `DEFAULT_PROFILE` 深比对不变”。
- P3-1 四文件 `sys.path.insert(0,.../src)`（含 `__init__.py:5`）导入期副作用。沿 stage1-8 既有模式，不改；仅记一笔。
- P3-2 `derive_case4/derive_case5` 仅校验 artifact id 非空，`con/job_dir` 合法性全权委托 stage3 fail-closed。系设计使然（不复制校验语义），不改；仅记一笔：QA 异常 6 例覆盖空 id 路径即可。
- P3-3 `ADDED_RULES` 精确子串语义与冻结引擎一致（`"Vscode"` 在长 token 内同样触发，如 `"VscodeX"`）。与冻结行为同构，不改；仅记一笔：QA 报告写明子串语义继承，不作词边界断言。
- P3-4 `derive_v2.py:81-83/110-111` 向 stage3 返回体追加 `stage9_*` 披露键（原地改写出参 dict）。无害且利披露，不改；仅记一笔。
