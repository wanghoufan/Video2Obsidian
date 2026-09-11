
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮最大合成64078B；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage7闭环） | STAGE7-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本内容不断言（词准确率/Golden/CER属Stage11+；合成正弦无语音空文本合法；仅验str/list类型＋调用计数＋prompt一致） | P3 | 否（PLAN已定，不卡门） | STAGE7-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s7qa_run.py`＋`--bad`八子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE7-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s7qa` 7三Root＋input 848K＋`/tmp/s7_stage7_verify`＋Stage6/5/4/3/2/1旧账＋$TMPDIR，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE7-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`~`src/stage6/` git diff口径N/A（当前目录非git仓库；以六回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE7-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | 三表口径说明（纯词库/复用/bump库恒0/0/0；corr库norm=2与reg_s3库1/1系QA脚手架经Stage3公开API合成Rendered所致，archive全库0） | P3 | 否（口径与builder自验一致，不卡门） | STAGE7-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | 裸`grep`噪音（不加`--include=*.py`时`__pycache__`二进制致exit 0假阳性；QA口径以`--include=*.py`/rg默认忽略为准，双grep exit 1已落盘） | P3 | 否（口径已锁定，不卡门） | STAGE7-QA-REPORT §未闭环U-7 | OPEN |
| U-8 | Stage7无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0~6-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE7-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage7闭环，P0-1~P0-7可证明，budget200/order/保尾/精确引用/语言策略可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE7-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE7-QA-REPORT.md`（PASS，happy 1遍＋异常/边界8个＋回归六行，115/115双轮exit 0，坏例只看exit码八exit 1）＋`src/stage7/`（vocabulary.py/prompt_builder.py/language.py/profile.py/transcribe.py/__init__.py共6文件）＋QA证据`/tmp/s7qa/s7qa_results.json`（product已复读：`total=115 passed=115 failed=0 fails=[] whisper_calls=1 max_bytes=64078`）＋Runner`/tmp/s7qa_run.py`（仓库外）＋八坏例子进程（vocab_missing/vocab_empty/budget_drift/empty_prompt/wav_missing/layer_leak/unknown_corr/wav_shape全exit 1）。
- 用户只关心六句话：词库里的专业词会不会被“智能”改掉大小写——不会（`Vibe Coding`与`vibe coding`精确区分，`has_exact_term`逐字节`==`，`casefold`全仓零命中已确认）；词太多超了200 token会不会把最重要的博主词丢掉——不会（超限去头保尾，A1大词库193tok/dropped 74，Creator 5/5全活，G00先丢；代码`kept[1:]`去头已直读）；提示词顺序会不会乱——不会（恒Global→Topic→Creator，`G[0]<T[0]<C[0]`＋`budget/order/pb-v1`三常量恒）；中文视频会不会因检出英文被拦掉不转——不会（`explicit-zh`冻结＋引擎显式`language=zh`，`en→mismatch True但blocked False/record-only`，`None/Chinese`亦不BLOCK，product已独立复跑三例）；换了词/换了规则会不会偷偷重跑花钱的转写——不会（§73-16经stage3公开API双rev，`whisper_calls=0/0`，Raw同hash；同profile同Run复用dup0/0，快照bump才允许新Run runs 1→2）；旧地基有没有被动——没有（Stage1门/Stage2链/Stage3 verdict/Stage4旧库PUBLISHED/Stage5十一步/Stage6双算六回归全PASS，`archive_commits`全库0，`current_path`列级零写）。另加一句定心丸：真实长视频一律没测（最大合成64078B≤70000门，Whisper全链仅1次happy接线），延续到产品完成。
- 打回条件均未触发：P0-1~P0-7任一项不可证明即打回——本轮7项全部有代码＋Count/exit码/hash复算三证据；budget/order漂移即打回——`PROMPT_BUDGET_TOKENS=200`＋`budget!=200即PromptBuilderError`＋`token>200即ProfileError`三硬门已直读，QA复算93/193双证据；出现归一化/直写DB/Stage8+关键词/改写语义即打回——product独立三重`rg -g '*.py'` RC=1三空已确认；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-7可证明逐项（口径=STAGE7-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Vocabulary快照可证明（三级原样＋sha256＋差一字节即变＋精确引用） | `vocabulary.py::load_vocabulary/canonical_serialize/dictionary_snapshot/has_exact_term`（逐字节存，不strip内字节，不去重不排序，三级缺一/空即`VocabularyError`）；QA：三级装载＋稳定复算＋一字节翻转变hash＋`Vibe Coding≠vibe coding`；独立抽验：`exact True/lower False`＋`snap flip True`已复跑，`rg casefold` RC=1空 | 可证明 |
| P0-2 | PromptBuilder可证明（真实Tokenizer先计数＋budget200＋order恒＋超限去头保尾＋每Chunk重建＋零调用） | `prompt_builder.py::build_initial_prompt/build_for_chunks`（`PROMPT_BUDGET_TOKENS=200/PROMPT_ORDER/PROMPT_BUILDER_VERSION=pb-v1`三常量＋`budget!=200即错`＋`ordered=g+t+c`＋`kept[1:]`去头＋`JOINER=，`）；QA：happy 93tok零截断＋复算93=93＋A1超限193tok/dropped74/Creator5/5/G00丢＋三Chunk各异（dict＋tuple双形）；独立抽验：三常量＋`ordered`＋`kept[1:]`已直读（本机无mlx_whisper，token复算数以QA真实tokenizer为准，代码语义已对齐） | 可证明 |
| P0-3 | Language＋ASR Profile可证明（explicit-zh冻结＋显式zh＋检出只记录＋新字段只进ASR＋executed替换语义＋hash完备） | `language.py`（`LANGUAGE_STRATEGY=explicit-zh/ENGINE_LANGUAGE=zh`＋`record_detected_language`恒`blocked=False/action=record-only`）＋`profile.py::build_asr_profile/asr_profile_hash/check_layering`（`layer=asr/executed=True/recorded_only=False/prompt_profile={200,order}`＋decode沿冻结常量＋hash全字段参与＋串层即`ProfileError`）；QA：en mismatch不BLOCK＋None不BLOCK＋Chinese不mismatch＋executed/chars/layer/decode对齐＋hash稳定/翻转＋asr-only；独立抽验：三语言例＋hash稳定/翻转＋`check_layering`过/漏BLOCK四项已复跑 | 可证明 |
| P0-4 | 单文件接线可证明（自有接线＋冻结常量对齐＋exactly one call＋复算一致＋文本不断言） | `transcribe.py::check_wav_mono_16k/run_single_file_with_prompt`（1ch/16k门＋`language=zh`显式＋`initial_prompt`预算门＋`resolve_model_revision`对齐＋`clip=0/word OFF/nst 0.6`＋VAD advisory＋不import stage1本体）；QA：合成2s真调1次（`initial_prompt`复算逐字节一致，token 54→93链一致≤200，`prompt_executed=True`，VAD不过滤，冻结常量逐字段对齐，文本仅验str/list）；独立抽验：`wav shape`门＋`language=ENGINE_LANGUAGE`＋`asr_calls=1`＋`vad_observe_only`已直读（真调以QA有界1次为准，product不重调） | 可证明 |
| P0-5 | §72/§73子集门可证明（Stage7 5断言） | 见§2表；QA §4五项全☑（A4/A5 Case4双证据＋A6 Derived双0＋A7逐字节＋A2每Chunk）；独立抽验：results `115/115 fails=[]`已复读＋八坏例键全exit1已复读 | 可证明 |
| P0-6 | STOP EXPANSION门可证明（六目录不动＋archive恒0＋current零写＋无越权import＋零直写DB） | QA：双grep `--include=*.py` exit 1零命中＋常量恒＋transcribe串层查（仅transcribe.py含）＋改写语义零命中＋archive全库0＋current零写＋六回归PASS；独立抽验：三重`rg -g '*.py'`（直写DB/Stage8+/casefold）RC=1三空＋`transcribe`仅transcribe.py含（＋__init__透出）＋`requests`空已确认；`src/stage1-6/`未触碰（非git仓库N/A，见U-5） | 可证明 |
| P0-7 | 外置合成验收门可证明（外置目录＋合成副本＋真实长视频零触碰） | QA：全用例在`/tmp/s7qa`内＋最大64078B≤70000门＋Whisper有界1＋真实库零触碰；独立抽验：`/tmp/s7qa/input/synth_2s.wav`在盘＋results `whisper_calls=1/max_bytes=64078`已复读＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. §72/§73子集门5断言（PLAN P0-5，QA §4逐项）

| §72/§73子集 | QA | 产品抽验 |
|---|---|---|
| §73-15（ASR/Normalization/Render分层正确，新五字段只进ASR） | ☑ `check_layering` asr-only＋串层坏例exit 1 | ☑ product独立复跑过/漏BLOCK＋`NEW_FIELDS`五项已直读 |
| §73-27（Prompt每Chunk重建，三Chunk各异，永不复用） | ☑ happy＋A2双证据（dict＋tuple三异） | ☑ `build_for_chunks`逐项`build_initial_prompt`无复用已直读 |
| §73-28（专业词correction不改变语义，精确替换＋前后缀逐字节） | ☑ 冻结corr-v1复跑`VIP COIN→Vibe Coding/Ai编程→AI编程`，applied=2，前缀`今晚讲`后缀逐字节，无mutate | ☑ results `a7.replace/suffix/prefix/applied/nomutate`五键ok已复读 |
| §73-16/§72 Derived子集（规则变更不重调Whisper＋Raw不变＋新Revision） | ☑ 经stage3公开API双rev异＋raw同hash＋`whisper/asr=0/0` | ☑ results `a6.n2.newrev/raw.same/whisper0`三键ok已复读 |
| §70 Case4（同Source同hash返既有Run；快照bump→新hash→允许新Run） | ☑ A4同run（1/1，dup0/0）＋A5快照变/hash变/新run（1→2） | ☑ results `a4.same.run/count1/dup0`＋`a5.snap.flip/hash.flip/newrun/count2`已复读 |

## 3. U-1~U-7接受为非阻塞的理由（＋U-8；长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言快照/装配预算/语言记录/身份复用/规则变更计数（hash/Count/dup/exit码/token复算），不认语音语义；超限保尾（G40/T40/C5翻转）与三Chunk各异恰恰只能用合成词项精确构造，真实视频造不出门内翻转。延续债：产品完成后再拿1个真实视频走快照→装配（token≤200）→接线（复算一致）→诱饵Run一遍，不断言词准确率只断言复算一致＋`executed=True`＋Source/Run。长视频不测延续。
- U-2（文本内容不断言）：接受。PLAN In Scope第60行＋Task S7-T03验收行明示“文本内容不断言（词准确率/Golden/CER属Stage11+）”；合成2s正弦无语音，空文本合法；本轮以`str/list`类型＋`asr_calls=1`＋`initial_prompt`复算一致＋VAD advisory为判据，质量门后移不卡本门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s7qa_run.py`＋八坏例（vocab_missing/vocab_empty/budget_drift/empty_prompt/wav_missing/layer_leak/unknown_corr/wav_shape）＋结果`/tmp/s7qa/s7qa_results.json`已记录，本轮product已复读`115/115 fails=[]`＋八exit1键，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s7qa` 7三Root＋input 848K＋builder验证`/tmp/s7_stage7_verify`＋Stage6/5/4/3/2/1旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1门反证＋Stage2五步链＋Stage3 verdict＋Stage4旧库PUBLISHED行＋Stage5十一步＋Stage6双算六回归全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）；建议进git后恢复diff硬门。
- U-6（三表norm=2/1/1口径）：接受。纯词库/复用/bump库恒0/0/0；corr库`norm=2`与reg_s3库`1/1`系QA脚手架经Stage3公开API合成Rendered Final所致（不绕门），非Stage7代码新增写（直写grep RC=1反证＋`archive_commits`全库0＋sources列级不变）；若按字面“恒0”卡脚手架库则无Derived证据可举，QA按builder自验同一口径验收，product认同。
- U-7（裸grep噪音）：接受。口径已锁定——`--include=*.py`（rg默认忽略`__pycache__`）为准，双grep exit 1已落盘复算；product本轮以`rg -g '*.py'`复跑三重RC=1三空，口径一致。
- U-8（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。去头保尾审计（`kept[1:]`＋Creator存活＋单巨词char级保尾）与分层审计（新五字段只进ASR＋`token>200`硬门＋串层抛错）与接线审计（不import stage1本体＋冻结常量逐字段＋exactly one call）三处正是code-reviewer主责，建议supervisor复检时点名补审这三处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑快照→装配→接线→诱饵Run，不断言速度/准确率只断言复算一致＋token≤200＋executed＋Source/Run；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s7qa`＋`/tmp/s7_stage7_verify`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s7qa_run.py`＋`s7qa_results.json`＋八坏例（vocab_missing/vocab_empty/budget_drift/empty_prompt/wav_missing/layer_leak/unknown_corr/wav_shape）路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-8）：supervisor确认Stage7 code-reviewer是否补审（重点：去头保尾＋分层＋接线三审计＋STOP三重grep），非P0，不卡本PASS。

---
目标：Stage7闭环产品验收｜剩 P0：无（P0 Blocking以STAGE7-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
