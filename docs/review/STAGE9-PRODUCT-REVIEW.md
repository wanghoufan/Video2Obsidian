
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（最大合成896B；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage9闭环） | STAGE9-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本内容不断言词准确率（Golden/CER属Stage11+；仅验规则命中分歧＋段数分歧＋计数＋hash） | P3 | 否（PLAN已定，不卡门） | STAGE9-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s9qa_run.py`＋`--bad`六子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE9-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s9qa`四库＋input约1M内＋Stage8及更早旧账，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE9-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`~`src/stage8/` git diff口径N/A（当前目录非git仓库；以八回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE9-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | REG-S4只读映射回归（stage4/stage6双算一致；happy库publish恒0为P0硬门，真写属Stage4门） | P3 | 否（口径与PLAN一致，不卡门） | STAGE9-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | REG-S5未起live watcher/worker线程（验instance 5步＋STARTUP_ORDER常量＋shutdown幂等，语义不断链） | P3 | 否（全量常驻属Stage5门，不卡门） | STAGE9-QA-REPORT §未闭环U-7 | OPEN |
| U-8 | REG-S7 prompt真调分支SKIPPED（本机缺mlx_whisper tokenizer，环境缺包非业务缺陷） | P3 | 否（纯层已验，装包重跑一行即可补） | STAGE9-QA-REPORT §未闭环U-8 | OPEN |
| U-9 | HANDOFF滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage9 builder计数基线；QA以落盘4文件＋PLAN为准独立覆盖） | P3 | 否（不卡QA PASS，交TM/supervisor补记） | STAGE9-QA-REPORT §未闭环U-9 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage9闭环，P0-1~P0-5可证明，Case4/5/6＋单旋钮归因可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE9-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE9-QA-REPORT.md`（PASS，happy链＋异常/边界6个＋回归八行，65/65双轮exit 0，坏例只看exit码六exit 1）＋`src/stage9/`（rules_v2.py/formatter_v2.py/derive_v2.py/__init__.py共4文件，只读直读已验）＋QA证据`/tmp/s9qa/s9qa_results.json`（product已复读：`total=65 passed=65 failed=0 fails=[] whisper_calls=0 max_bytes=896 publish=0 archive=0 bad_exits六exit1`）＋Runner`/tmp/s9qa_run.py`（仓库外，在盘已确认）＋六坏例子进程（llm_passage/bad_params/guard_immutable/unknown_revision/empty_segments/empty_raw_id全exit 1，results键已复读）。
- 用户只关心五句话：规则换版会不会重跑Whisper/动原片——不会（Case4经stage3 `derive_on_correction_change`只读复用，`whisper_calls==0`双证据＋Raw sha `53794ef7…`三复算一致＋新NormRev＋下游新Rendered，product独立复核代码装配＋QA计数`Norm=1/Rend=1`时点）；段落换版会不会动原文/另起Normalized——不会（Case5经`derive_on_formatter_change`只读复用，同一`normalized_artifact_id`复用＋`delta==0`由stage3层内置断言＋只建新RenderRev，product独立复核`derive_case5`无Norm写路径＋QA计数`Norm/Rend=1/2`）；Run会不会被回滚/笔记会不会被覆盖——不会（Case6前后COMPLETED→COMPLETED，`publish_records/archive_commits`恒0，诱饵md字节不变，product独立复核derive模块无publish调用＋QA列级零写）；新规则/新格式是不是“就动了一个旋钮”——是（Correction仅增`Github→GitHub/Vscode→VS Code`两高度确定条目，基座`corr-v2`原样复用非手抄；Paragraph仅`target_chars 180→240`一钮，pause/hard_max不动，规则序四项冻结，product独立复跑单旋钮见§2）；旧地基有没有被动——没有（Stage1门/Stage2链/Stage3冻结链/Stage4双算/Stage5五步＋常量/Stage6越界拒收/Stage7纯层/Stage8 planner-timeline-merge八回归全PASS，`src/stage1-8/`零触碰声明＋STOP三重grep RC=1）。另加一句定心丸：真实长视频一律没测（最大合成896B合成小文件门内，Whisper全链0），延续到产品完成。
- 打回条件均未触发：P0-1~P0-5任一项不可证明即打回——本轮5项全部有代码＋Count/exit码/hash复算三证据；LLM/改写/规则序篡改/直写DB/Stage10+关键词任一命中即打回——product独立三重`rg -g '*.py'` RC=1三空已确认（banned串/直写DB/`requests.`）；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-5可证明逐项（口径=STAGE9-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Case4延续可证明（规则变Whisper 0/Raw同/新NormRev/新Rendered/诱饵不变） | `rules_v2.py::RULES_REVISION=s9-corr-v2/BASE=corr-v2/ADDED_RULES 2条/validate_rules形状门/register_rules内存注册幂等/new_normalization_profile仅改一字段/apply_v2走冻结apply_corrections`＋`derive_v2.py::derive_case4`（新Correction profile＋冻结render，`whisper_calls==0`）；QA：HAPPY＋A1（Whisper 0＋Raw同＋新NormRev `normrev_63dd…`＋hash复算＋仅规则层变＋诱饵不变，Count 1/1）；独立抽验：`full_table()[-4:]`尾部恰2新增＋新旧同输入仅s1变（`Github/Vscode→GitHub/VS Code`，s2/s3逐字节一致）＋`validate_rules`长段落拒收已复跑 | 可证明 |
| P0-2 | Case5延续可证明（格式变Raw同/normalized复用/只建新RenderRev/诱饵不变） | `formatter_v2.py::FORMATTER_VERSION=para-v2/PARA_PARAMS_V2={1.5,240,400}/RULE_ORDER四项冻结/new_render_profile仅改两字段/render_with_v2走冻结render_paragraphs/check_rule_order四探针`＋`derive_v2.py::derive_case5`（新formatter，Norm数不变由stage3层内置断言）；QA：HAPPY＋A2（同ID `normalized_63dd…`＋delta=0＋新RenderRev `rendrev_cefc…`＋hash复算＋仅渲染层变，Norm/Rend=1/2）；独立抽验：`check_rule_order() all_pass True`＋`new_render_profile` delta恰版本/参数两字段＋`render_paragraphs(target 500>hard_max 400)`拒收`RenderError`已复跑 | 可证明 |
| P0-3 | Case6＋默认不覆盖可证明（Run全程COMPLETED/Raw Immutable/publish恒0） | `derive_v2.py`模块注释Case6 by construction（不读写Run行＋Raw finals只读＋诱饵只probe＋从不调publish）；QA：A3（COMPLETED→COMPLETED＋publish/archive恒0＋sources三列零写＋Raw/诱饵不变）；独立抽验：`derive_v2`源码无`run_asr_single_file/sqlite3/publish`（STOP门复证）＋results `publish=0/archive=0`已复读 | 可证明 |
| P0-4 | STOP EXPANSION门可证明（八目录不动＋三表恒0＋current零写＋无越权＋零直写DB＋规则序冻结） | QA：八回归PASS＋三表happy库1/2/0（只经stage3公开API）＋archive全库0＋current零写＋三重grep零命中＋规则序冻结；独立抽验：三重`rg -g '*.py'`（banned串/直写DB/`requests.`）RC=1三空＋`derive_v2`无asr import无sqlite已复跑＋`RULE_ORDER`四项冻结＋`ls src/stage9` 4文件（`src/stage1-8/`未触碰，非git仓库N/A见U-5） | 可证明 |
| P0-5 | 外置合成验收门可证明（外置目录＋合成副本＋真实长视频零触碰） | QA：全用例在`/tmp/s9qa`内＋最大896B合成小文件门内＋Whisper全链0＋真实库零触碰＋长文本只用合成segments夹具；独立抽验：`/tmp/s9qa/`四库＋input在盘＋`s9qa_results.json max_bytes=896/whisper_calls=0`已复读＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. 单旋钮归因＋§72子集门7断言（任务目标重点）

- 单旋钮·Correction：基座`corr-v2`原样复用（缺基座即`RulesError`拒造）＋新增恰2条（`Github→GitHub`大小写、`Vscode→VS Code`大小写＋空格）；product复跑新旧同输入：仅命中段s1变，其余逐字节一致；冻结命中（`VIP COIN→Vibe Coding`类）新旧一致（QA实测1/3段变，product窄探针一致方向相同）。
- 单旋钮·Paragraph：`para-v1→para-v2`仅`target_chars 180→240`一钮（pause 1.5/hard_max 400不动）；规则序`long_pause>strong_punctuation>target_length>hard_max`冻结，`check_rule_order`四探针全过（product复跑`all_pass True`）；QA合成夹具v1=2段vs v2=1段，分歧仅来自target一钮且可复算；product窄探针（`y*200`＋tail）v1/v2同为1段——在此长度下同段合法，与QA夹具不矛盾（阈值未跨过不断段正是冻结语义）。
- 分层：`new_normalization_profile` delta恰`correction_rules_revision`一字段（product复跑；DEFAULT基线`corr-v1`→新版`s9-corr-v2`，其余五字段原样继承）；`new_render_profile` delta恰版本/参数两字段（product复跑；§29/§30串层无）。
- §72子集7断言（QA §4逐项，product复读results键＋代码走读）：Correction不重调Whisper☑（`whisper_calls=0`）／Raw Hash不变☑（三复算）／新NormRev☑（新ID＋hash复算）／Formatter只建新RenderRev☑（delta=0）／Normalized可复用☑（同ID）／Completed Run不回滚☑（COMPLETED→COMPLETED）／Canonical默认不覆盖☑（双verdict＋诱饵不变＋publish 0）。

## 3. U-1~U-9接受为非阻塞的理由（长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言规则替换＋段落格式化＋派生计数（Whisper 0/Count/exit码/hash复算/诱饵不变），不认语音语义；长文本语义只用合成segments夹具证明。延续债：产品完成后再拿1个真实视频走Case4→Case5一遍，不断言词准确率只断言计数＋复算＋诱饵不变。长视频不测延续。
- U-2（不断言词准确率）：接受。PLAN In Scope＋S9-T03明示“文本内容不断言词准确率（Golden/CER属Stage11+）”；本轮以规则命中分歧＋段数分歧＋调用计数＋hash一致为判据，质量门后移不卡本门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s9qa_run.py`＋`--bad`六子进程（llm_passage/bad_params/guard_immutable/unknown_revision/empty_segments/empty_raw_id）＋结果`/tmp/s9qa/s9qa_results.json`已记录，本轮product已复读`65/65 fails=[]`＋六exit1键，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s9qa`四库＋input约1M内＋Stage8及更早旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——八回归全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）；建议进git后恢复diff硬门。
- U-6（REG-S4只读映射）：接受。双算一致是更强的“不变”证据；happy库publish恒0为P0硬门，真写publish属Stage4门已由Stage4套件覆盖，不在本套件重演。
- U-7（REG-S5未起常驻线程）：接受。live watcher/worker易flake属Stage5全量门；本套件验instance 5步＋`STARTUP_ORDER`常量＋`shutdown`幂等，语义不断链声明成立。
- U-8（prompt真调SKIPPED）：接受。缺`mlx_whisper` tokenizer系环境缺包非业务缺陷；已验vocab快照/budget/order/language纯层；补测只需装包重跑该一行，交后续按需补，不卡本PASS。
- U-9（HANDOFF滞后）：接受。根HANDOFF仍停Stage2 CLOSED是TM记账问题，不影响本轮可证明性；QA已以`src/stage9/`落盘4文件＋PLAN S9-T03为准独立覆盖65断言，builder自验入口缺失不卡QA。建议TM/supervisor补记Stage3~9链状态。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑Case4→Case5→lineage一遍，不断言速度/准确率只断言Whisper 0＋Raw/诱饵不变＋复算一致＋Source/Run；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s9qa`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s9qa_run.py`＋`s9qa_results.json`＋六坏例路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-9）：supervisor确认HANDOFF补记Stage3~9链；Stage9 code-reviewer报告缺席（docs/review下仅STAGE0~8-CODE-REVIEW）按AGENTS不可跳，建议supervisor复检时点名补审三处（validate_rules形状门＋RULE_ORDER冻结＋derive装配无asr/无直写DB），非P0，不卡本PASS。

---
目标：Stage9闭环产品验收｜剩 P0：无（P0 Blocking以STAGE9-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
