# QA-REPORT｜Stage9 S9-T03 验收套件 + §72 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage9/`（rules_v2.py/formatter_v2.py/derive_v2.py/__init__.py）+ `src/stage1/` 只读复用（prepare 门/commit 不变性/probe）+ `src/stage2/` 只读复用（store/instance/candidate/runs）+ `src/stage3/` 只读复用（normalize/render/derive/lineage 公开 API）+ `src/stage4/5/6/7/8` 只读复用（回归探针）
- 计划：`docs/pm/STAGE9-PLAN.md` S9-T03（P0-1~P0-5；happy 链 1 遍 + 异常/边界 6 个 + 回归八行；外置合成 Input Root + 外置 Data Root；合成小文件；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage9 子集：Correction Rules Change 不重调 Whisper / Raw Hash 不变 / 新 Normalization Revision / Formatter Change 只建新 RenderRev / Normalized 可复用 / Completed Run 不回滚 / Canonical 默认不覆盖）+ §45（确定性 Correction）+ §47（Long Pause > Strong Punctuation > Target Length > Hard Max）+ §29/§30（分层）
- QA 执行目录（仓库外）：`/tmp/s9qa/`（happy/reg_s2/reg_s3/reg_s5 各独立 data_root + 合成 `clip.bin` 896B + 合成 `reg_s2.bin` + 诱饵 `decoy.md` + `s9qa_results.json`）+ `/tmp/s9qa_run.py`（仓库外 Runner，`--bad` 六子进程取 exit 码）；仓库内零写盘除本报告
- **结论：PASS（happy 链 + 异常/边界 6 个全过 + 回归八行，65/65 断言双轮稳定，Runner exit 0；坏例只看 exit 码：六坏例 exit 1 符合预期；Whisper 恒 0；publish/archive 恒 0；Raw/decoy 字节不变；current_path 零写；最大合成文件 896B；结论只落本报告）**

## 1. 输入复核（src/stage9 落盘 4 文件，只读消费）

- `rules_v2.py`（S9-T01 规则半）：`RULES_REVISION="s9-corr-v2"` + 基座 `corr-v2` 原样复用（非手抄，缺基座即拒）+ `ADDED_RULES=(Github→GitHub, Vscode→VS Code)` 高度确定大小写/空格修复 + `validate_rules` 形状门（两侧长度差 >16 即 `RulesError` 拒收粘贴段落）+ `register_rules` 内存注册（同 key 异内容拒换）+ `new_normalization_profile` 仅改 `correction_rules_revision`（§29 其余五字段原样继承）+ `apply_v2` 走冻结 `apply_corrections`。QA 实测：新旧同输入仅命中处分歧（1/3 段变），冻结命中 `VIP COIN→Vibe Coding` 新旧一致。
- `formatter_v2.py`（S9-T02 格式半）：`FORMATTER_VERSION="para-v2"` + `PARA_PARAMS_V2={pause 1.5, target 240, hard_max 400}`（相对冻结 `para-v1` 仅 `target_chars` 180→240 一钮变化）+ `RULE_ORDER` 四项冻结序 + `new_render_profile` 仅改版本/参数两字段（§30 其余三字段原样继承）+ `render_with_v2` 走冻结 `render_paragraphs` + `check_rule_order` 四探针。QA 实测：四探针全过；合成夹具 v1=2 段 vs v2=1 段，分歧仅来自 target 一钮。
- `derive_v2.py`（装配半）：`derive_case4`（新 Correction profile + 冻结 render → 新 NormRev + 下游新 Rendered，全程 `whisper_calls==0`）+ `derive_case5`（新 formatter → 仅新 RenderRev，NormRev 数不变由 stage3 层内置断言）。QA 实测：Case4 Norm=1/Rend=1、Case5 同 normalized ID + delta=0 + Rend=2。
- `__init__.py`：装配导出（常量 + 函数全透出，无语义增量）。
- 上轮 builder 计数基线与异常清单：HANDOFF 仍停在 Stage2 CLOSED，未登记 Stage9 builder 自验入口/计数值；QA 按 S9-T03 口径独立合成（896B 确定性 `.bin` + 合成 3 段夹具 + 诱饵 md），6 异常按 PLAN 全覆盖（Case4/Case5/Case6/LLM 拒收/规则序篡改拒收/同 profile 重放）；builder 摆动无——未发现规则/格式口径分叉（新版仅 bump 版本化定值，规则序未动）。

## 2. 用例简表（坏例只看 exit 码；三表=norm/rend/arch；Whisper=真调次数）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 三表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY Raw→Case4→Case5→lineage | 新 root + 合成 raw（门合成）+ 诱饵 md | derive_case4→derive_case5→get_lineage | Norm=1/Rend=2 + 同 ID 复用 + verdict 双 `CANONICAL_OUTPUT_EXISTS` + 全链可查 | 一致（normrev_63dd…/rendrev_0680…/rendrev_cefc…） | Runner exit 0；Norm=1/Rend=2 | 1/2/0 | 0 |
| A1 Case4 | HAPPY 库 | 计数/hash/分层复核 | Whisper 0 + Raw 同 + 新 NormRev + hash 可复算 + 仅规则层变 + 诱饵不变 | 一致 | Count 1/1 | 1/1/0 | 0 |
| A2 Case5 | HAPPY 库 | 计数/hash/分层复核 | Raw 同 + normalized 同 ID + delta=0 + 新 RenderRev + hash 可复算 + 仅渲染层变 + 诱饵不变 | 一致 | delta=0；Rend=2 | 1/2/0 | 0 |
| A3 Case6 | 派生前后 | 查 Run + 三表 + sources 列 | Run 全程 COMPLETED + publish/archive 0 + current_path/status/archived_at 零写 + Raw 字节不变 | 一致 | — | 0/0 | 0 |
| A4 LLM 改写拒收 | 纯函数 | 长改写段落调 validate_rules | `RulesError`，exit 1 | 一致 | exit **1** | — | 0 |
| A5 规则序篡改拒收 | 纯函数 | 非法参数 + 顺序冻结断言 | `RenderError`，exit 1；RULE_ORDER 四项冻结 + 四探针全过 | 一致 | exit **1** | — | 0 |
| A6 同 profile 重放 | HAPPY 库 | Case4/Case5 各重放一次 | 同 IDs + Norm/Rend 行数不变（幂等复用） | 一致 | Count 不变 | 1/2/0 | 0 |
| B-六坏例 | 各合成前置 | --bad 六子进程 | 期望错误未吞，exit 1 | 一致（六 exit 1，见§3） | 六 exit **1** | — | 0 |
| STOP 门 | 全量输入 + 全仓 stage9 | 路径前缀 + 最大文件 + Whisper 0 + 三 grep + 规则序 | 全在 /tmp/s9qa + max 896B + 零命中 + 冻结恒 | 一致 | — | arch 恒 0 | 0 |
| REG-S1 | 合成门 | probe_volume + 非法 Raw | ALLOW + 非法拒收 | 一致 | exit 0 | — | 0 |
| REG-S2 | 新 root | startup + discover | PROMOTED + Source≤1/Run≤1 + arch0 | 一致 | 1/1 exit 0 | 0 | 0 |
| REG-S3 | 新 root（合成 Raw 经门） | norm→render（冻结版） | COMPLETED→PUBLISH_EVALUATION + verdict 双值域 | 一致（PENDING_PUBLISH） | Norm=1/Render=1 | 1/1/0 | 0 |
| REG-S4 | 合成嵌套 Unicode | stage4 与 stage6 双算 | 双算逐字节一致 | 一致（`AI/博主A/系列1/DeepSeek V4 分析.mp4→…md`） | — | — | 0 |
| REG-S5 | 新 root | instance 5 步 + order 常量 + shutdown | 5 步逐字 + 11 步常量尾 RUNNING + shutdown 幂等 | 一致 | exit 0 | 0 | 0 |
| REG-S6 | 越界路径 | resolve_canonical | 越界拒收 | 一致 | exit 0 | — | 0 |
| REG-S7 | 合成词项 | vocab→snapshot→budget/order→language | 快照翻转 + 200/Global→Topic→Creator + explicit-zh（tokenizer 缺席项 SKIPPED） | 一致 | — | — | 0 |
| REG-S8 | 合成夹具 | plan→to_absolute→merge | 601→2 chunk 起点 598 + absolute 透传 + 合并保留 | 一致 | — | — | 0 |

Runner：`/tmp/s9qa_run.py`（仓库外）→ `/tmp/s9qa/s9qa_results.json`（65 断言 JSON 已落盘，可复算；双轮 `TOTAL 65/65 FAILS=[] exit=0`）；坏例子进程六 exit **1**（判据只用 exit 码，不看打印）；最大合成文件 896B（`clip.bin`，合成小文件门内，真实长视频零触碰）；Whisper 调用全链=0（无真调，derive 输出 `whisper_calls==0` 双证据）。

## 3. 每用例明细（前置/动作/期望；Count 或 exit 码 + 三表 + current_path + Whisper 0 + 外置路径）

- HAPPY：前置新 `happy/{data_root,input}` + 合成 `clip.bin`（896B）+ 经 `validate_raw_artifact` 门合成 COMMITTED Raw（三段夹具：s1 命中新规则、s2/s3 长弱标点边界、s3 命中冻结规则）+ 诱饵 md；动作 `derive_case4`（s9-corr-v2 + 冻结 render，probe=诱饵）→ `derive_case5`（para-v2，复用同一 normalized ID）；期望 Norm=1/Rend=2、双 verdict `CANONICAL_OUTPUT_EXISTS`、lineage 1 NormRev→2 RenderRev 且 `file_present` 全真、profile hash 双复算一致、§29/§30 串层无、规则序冻结、四探针全过、新旧纯函数分歧可复现（Correction 仅 1 段变、Paragraph 2 段 vs 1 段）；实测全中（IDs 见§2）。
- A1：HAPPY 库复核——`whisper_calls==0` + `stage9_render_profile_is_frozen` + Raw sha `53794ef7…` 前后一致 + 新 NormRev `normrev_63ddad1d5493` + 新 Normalized hash==行记录（复算一致）+ 新 Rendered + 诱饵 sha 不变 + Norm/Rend=1/1（Case4 时点）；实测全中。
- A2：HAPPY 库复核——Raw 同 + `normalized_artifact_id` 同一 ID（`normalized_63ddad1d5493`）+ `normalization_revisions_delta==0`（stage3 内置非 0 即抛）+ 新 RenderRev `rendrev_cefc0301544f` + 新 Rendered + 诱饵不变 + Norm/Rend=1/2；实测全中。
- A3：派生前后 Run=`COMPLETED→COMPLETED`（预置 COMPLETED 行，derive 路径不读写 Run 行）；`publish_records/archive_commits` 恒 0；`sources.current_path/status/archived_at` 列级零写；Raw 复算不变；诱饵不变；实测全中。
- A4：`validate_rules([("Hi", 长改写段落)])` 两侧长度差 >16 → `RulesError`（子进程 exit 1）；另 `src/stage9/` LLM/改写关键词 grep 零命中反证（STOP 门复证）；实测全中。
- A5：`render_paragraphs(target 500 > hard_max 400)` → `RenderError`（子进程 exit 1）；`RULE_ORDER` 四项冻结断言 + `check_rule_order` 四探针全过（篡改序≠冻结序的否定对照）；实测全中。
- A6：Case4/Case5 同参各重放一次 → 同 revision IDs + Norm/Rend 行数不变（1/2）+ 同 normalized 复用；实测全中。
- B-六坏例（判据只用 exit 码）：`llm_passage exit 1=RulesError` + `bad_params exit 1=RenderError` + `guard_immutable exit 1=RawImmutableError` + `unknown_revision exit 1=NormalizationError` + `empty_segments exit 1=RenderError` + `empty_raw_id exit 1=DeriveV2Error`；任一吞错即非 1 项未触发。
- STOP 外置/冻结：输入全在 `/tmp/s9qa/*/input` + 外置 Data Root（与真实视频目录/真实 Obsidian 库无交集）；最大合成文件 896B（合成小文件门内）；Whisper 全链=0（双 derive 输出 + 无 asr import）；`src/stage9/` 三重 grep 零命中（banned 串 / 直写 DB / `requests.`）+ §47 规则序冻结；`git diff` 口径 N/A（非 git 仓库，以八回归 PASS + QA 零改代证）；happy 库 `archive_commits` 恒 0。
- 回归：REG-S1 `probe_volume(/tmp/s9qa/input)→ALLOW` + 非法 Raw 拒收；REG-S2 `instance.startup` 5 步逐字 + discover PROMOTED + Source=1 + Run=1 + arch0；REG-S3 合成 Raw 经门→`COMPLETED→PUBLISH_EVALUATION` + verdict `PENDING_PUBLISH`（双值域内）；REG-S4 嵌套 `AI/博主A/系列1/DeepSeek V4 分析.mp4` 经 stage6 与 stage4 双算逐字节一致；REG-S5 `instance.startup` 5 步逐字 + `STARTUP_ORDER` 11 步常量尾 RUNNING + `shutdown(None)` 幂等（live watcher 未起，语义不断链声明见未闭环）；REG-S6 越界 `/etc/passwd` 拒收；REG-S7 vocab 快照一字节翻转 + budget 200/order Global→Topic→Creator + `explicit-zh`（tokenizer 缺席项 SKIPPED 声明）；REG-S8 `plan_chunks(601)` 2 chunk 起点 598 + `to_absolute` 透传 + `merge_chunks` 保留；`src/stage1-8/` 本轮 QA 未触碰。

## 4. §72 子集门（Stage9 7 断言逐项）

- [x] Correction Rules Change 不重新调用 Whisper（Case4 `whisper_calls=0` + 无 asr import；`happy.case4.whisper0`）
- [x] Raw Hash 不变（HAPPY/Case4/Case5 三复算一致；`happy.raw_immutable`）
- [x] 新 Normalization Revision（Case4 新 ID + Norm=1 + hash 可复算；`happy.case4.norm1/hash_recalc`）
- [x] Paragraph Formatter Change 只新建 Render Revision（Case5 delta=0 + 新 RenderRev + 同 ID 复用；`happy.case5.delta0/reuse`）
- [x] Normalized 可复用（Case5 复用同一 `normalized_artifact_id`；`happy.case5.reuse`）
- [x] Completed Processing Run 不被 Revision 回滚（Case6 COMPLETED→COMPLETED；`happy.case6.run_completed`）
- [x] Canonical 默认不覆盖（双 verdict `CANONICAL_OUTPUT_EXISTS` + 诱饵字节不变 + publish 恒 0；`happy.publish0/decoy_same`）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（业务侧） | — | 否 | 65/65 双轮 exit 0；六坏例 exit 1 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s9qa/s9qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S9-T03 Stage9 验收套件 + §72 子集门 + Stage1~8 回归（首轮 QA 执行，Runner 修 4 次，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；4 处均为 Runner 自身问题：①reg.s4 把 stage6 dict 与 stage4 str 直接比（业务行为正确，取 dict 内 canonical 字段后一致）；②③reg.s7/s8 调错纯函数签名与返回键名（`build_initial_prompt` 需三词项、`plan_chunks` 键为 `start_s`、`merge_chunks` 项为 `{chunk, segments}`，业务无辜）；④mlx_whisper 缺席致 prompt 真调分支不可跑（改走 vocab 快照/budget/order/language 纯层 + SKIPPED 声明，业务无辜））
- Approach: 仓库外 `/tmp/s9qa` 各用例独立 data_root + 合成确定性小文件（896B `.bin` + 3 段合成夹具，文本内容仅作规则/格式分歧证据，不断言词准确率）+ 诱饵 md；Count/行数/SQLite 直查为正常路径判据；LLM 拒收/坏参数/immutable/未知版本/空输入/空 ID 走子进程只看 exit 码；grep 三重 STOP 门；happy 库三表快照 + archive 全库 0 + sources 列级不变；回归 S1 门/S2 链/S3 verdict/S4 双算/S5 五步+常量/S6 越界/S7 纯层/S8 planner-timeline-merge
- Files Changed: 仅新增本报告 `docs/qa/STAGE9-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s9qa`（H2 外置目录约束延续）；Runner `/tmp/s9qa_run.py` 在仓库外
- Verification: 双轮 `TOTAL 65/65 FAILS=[] exit=0`（`s9qa_results.json` 可复算，`whisper_calls=0/max_bytes=896/publish=0/archive=0`）；六坏例 exit 1 已取（`llm_passage/bad_params/guard_immutable/unknown_revision/empty_segments/empty_raw_id`）；happy 库三表 1/2/0 且 runs=1/sources=1；诱饵/真实库零触碰；`src/stage1-8/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）；Runner 首轮后段 4 项系签名/键名/缺包，修 Runner 后 65/65（`--bad` 子进程同修）
- Difference From Previous Attempt: 首轮，无上一轮（同轮内 Runner 修 4 次：dict 取字段 1 行 + 签名键名 3 处 + tokenizer 缺席改 SKIPPED）

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 896B；长文本语义只用合成 segments 夹具证明）。
- U-2 文本内容不断言词准确率（PLAN 已定：Golden/CER 属 Stage11+；本报告仅验规则命中分歧 + 段数分歧 + 调用计数 + hash 一致）。
- U-3 Runner 在仓库外（`/tmp/s9qa_run.py` + `--bad` 六子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3/Stage8 U-3 同 Pattern）。
- U-4 残留待清：`/tmp/s9qa`（happy/reg_s2/reg_s3/reg_s5 四库 + input，本轮新增，约 1M 内）+ Stage8 残留（`/tmp/s8qa`）+ 更早 Stage 残留（`/tmp/s1t*` + `$TMPDIR` + `/tmp/s2t07_qa`），交 neat-freak 收尾。
- U-5 `src/stage1/`…`src/stage8/ git diff 为空`口径 N/A（当前目录非 git 仓库；以八回归 PASS + QA 零改代证，未改业务代码）。
- U-6 REG-S4 为只读映射回归（stage4/stage6 双算一致），未在本套件执行 Stage4 `initial_publish` 真写（happy 库 publish 恒 0 为 P0 硬门；真写 publish 属 Stage4 门，已由 Stage4 套件覆盖）。
- U-7 REG-S5 未起 live watcher/worker 线程（`run_startup` 全 11 步需 watchdog + 常驻线程，易 flake；本套件验 instance 5 步 + `STARTUP_ORDER` 常量 + `shutdown` 幂等，语义不断链；全量常驻属 Stage5 门）。
- U-8 REG-S7 prompt 真调分支 SKIPPED（本机缺 `mlx_whisper` tokenizer，属环境缺包非业务缺陷；已验 vocab 快照/budget/order/language 纯层；若需补，装包重跑该一行即可）。
- U-9 HANDOFF 滞后：根 HANDOFF 仍停在 Stage2 CLOSED，未登记 Stage9 builder 计数基线与异常清单；本报告输入复核以 `src/stage9/` 落盘 4 文件 + PLAN S9-T03 为准，基线缺失不卡 QA（已独立覆盖）。

---
目标：Stage9验收S9-T03｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
