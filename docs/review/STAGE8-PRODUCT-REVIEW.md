
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮最大合成64044B≤132K门；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage8闭环） | STAGE8-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 文本内容不断言（词准确率/Golden/CER属Stage11+；合成正弦无语音空文本合法；仅验str/list类型＋调用计数＋prompt一致＋时间轴单调） | P3 | 否（PLAN已定，不卡门） | STAGE8-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s8qa_run.py`＋`--bad`八子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE8-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s8qa` 7库＋input约1M内＋Stage7/6/5/4/3/2/1旧账＋$TMPDIR＋用户级python包，交neat-freak收尾） | P3 | 否（全在/tmp测试区＋用户级site-packages，仓库内零污染） | STAGE8-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`~`src/stage7/` git diff口径N/A（当前目录非git仓库；以七回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE8-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | 三表口径说明（复用/bump库恒0/0/0；reg_s3库1/1系QA脚手架经Stage3公开API合成Rendered所致，archive全库0） | P3 | 否（口径与S7一致，不卡门） | STAGE8-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | HANDOFF滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage3~8链；QA以落盘6文件＋PLAN为准独立覆盖） | P3 | 否（不卡QA PASS，交TM/supervisor补记） | STAGE8-QA-REPORT §未闭环U-7 | OPEN |
| U-8 | VAD SKIPPED路径未走（本轮silero可用走OK路径；缺包分支仅代码走读，未实测） | P3 | 否（容错分支非P0主张；卸包重跑即可补） | STAGE8-QA-REPORT §未闭环U-8 | OPEN |
| U-9 | Stage8无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0~7-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE8-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage8闭环，P0-1~P0-7可证明，VAD advisory/Chunk/Timeline/Merge＋§73-24/25/26可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE8-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE8-QA-REPORT.md`（PASS，happy双链＋异常/边界8个＋回归七行，113/113双轮exit 0，坏例只看exit码八exit 1）＋`src/stage8/`（vad.py/chunk_planner.py/timeline.py/merge.py/transcribe_chunks.py/__init__.py共6文件，只读直读已验）＋QA证据`/tmp/s8qa/s8qa_results.json`（product已复读：`total=113 passed=113 failed=0 fails=[] whisper_calls=2 max_bytes=64044 vad_status双OK`）＋Runner`/tmp/s8qa_run.py`（仓库外）＋八坏例子进程（vad_filter/vad_thr_drift/plan_illegal/plan_drift/timeline_disorder/merge_empty/layer_leak/wav_shape全exit 1，results键已复读）。
- 用户只关心七句话：VAD会不会“智能”丢掉某段语音——不会（`filtering=True`即`VadError`硬拒＋`is_advisory_only()=True`＋观测前后sha/字节一致，双thr 0.3/0.5稳定复现，product独立复跑`vad_filter raised VadError`）；长音频切分会不会丢头丢尾/重叠对不上——不会（`plan_chunks`纯函数，600s→1 chunk、601s→2 chunk且overlap恒2s、1200s三chunk core无缝无重叠，短音频恰1 chunk，非法输入fail-closed，product独立复跑三点一致）；切完时间戳会不会乱——不会（`absolute = chunk_start + relative`纯映射，Relative＋Absolute双保留，乱序拒收，product独立复跑`298.0+0.5=298.5`＋`check_monotonic True`）；重叠区会不会留两份/丢私段/近似文本被误杀——不会（四优先级Core＞Absolute＞Overlap＞Text＋禁整篇fuzzy，重叠双份恰一份、私段全留、`hello world` vs `hello world!`双双保留，product独立复跑`fuzzy kept 2`＋`disorder/empty raised`）；每Chunk提示词会不会复用错——不会（`build_for_chunks`每Chunk重建＋接线侧复算逐字节一致，calls==chunks，注入3 chunk calls==3、真调1 chunk calls==1，文本仅验类型；本机无mlx_whisper，token复算数以QA有界2次为准，代码语义已对齐）；vad/chunk新字段会不会串层污染后续——不会（只进ASR层，串层坏例exit 1，hash 64hex稳定/翻转，product独立走读`assert_asr_layer_only`过/漏两路）；旧地基有没有被动——没有（Stage1门/Stage2链/Stage3 verdict/Stage4旧库PUBLISHED/Stage5十一步/Stage6双算/Stage7接线七回归全PASS，`archive_commits`全库0，`current_path`列级零写）。另加一句定心丸：真实长视频一律没测（最大合成64044B≤135168B门，Whisper全链仅2次happy＋回归），延续到产品完成。
- 打回条件均未触发：P0-1~P0-7任一项不可证明即打回——本轮7项全部有代码＋Count/exit码/hash复算三证据；VAD过滤/阈值漂移/chunk常量漂移/fuzzy dedup/串层/直写DB/Stage9+关键词任一命中即打回——product独立四重`rg -g '*.py'` RC=1四空已确认；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-7可证明逐项（口径=STAGE8-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | VAD advisory可证明（silero thr 0.3–0.5＋只记录不过滤＋字节一致） | `vad.py::observe_vad/observe_vad_all/vad_profile/is_advisory_only`（thr仅0.3/0.5其余`VadError`＋`filtering=True`即拒＋`filtering False/drives_* False`＋观测前后sha比对）；QA：双thr OK稳定＋双跑一致＋sha/字节一致＋SKIPPED fail-closed说明；独立抽验：`advisory True`＋profile五键＋`vad_filter raised VadError`已复跑 | 可证明 |
| P0-2 | ChunkPlanner可证明（10min/2s冻结＋边界数学＋core归属＋fail-closed） | `chunk_planner.py::plan_chunks/CHUNK_SIZE_S=600/CHUNK_OVERLAP_S=2`（非600/2即`ChunkPlanError`＋0/负/NaN/inf/非数字/bool全拒＋短音频恰1 chunk）；QA：600→1/601→2 overlap恒2s/1200三chunk core无缝＋合成2s恰1 chunk；独立抽验：600/601/1200三点＋`plan0 raised ChunkPlanError`已复跑 | 可证明 |
| P0-3 | Absolute Timeline＋Merge可证明（双时间戳＋四优先级＋禁fuzzy） | `timeline.py::to_absolute/check_monotonic`（relative原位＋absolute增补＋word双戳透传＋乱序拒收）＋`merge.py::merge_chunks/PRIORITY`（core＞absolute＞overlap＞text＋同start同文本邻居collapse＋空输入拒收＋单调校验）；QA：overlap双份恰一份＋非overlap逐字节＋近似文本双保留＋word ON/OFF双透传＋fuzzy零命中；独立抽验：`298.5`双戳＋`mono True`＋`fuzzy kept 2`＋`disorder/empty raised`已复跑 | 可证明 |
| P0-4 | Chunk执行接线可证明（冻结对齐＋每Chunk重建＋calls==chunks＋文本不断言） | `transcribe_chunks.py::run_chunks/build_chunk_asr_profile/chunk_asr_profile_hash/assert_asr_layer_only/frozen_alignment`（stage1冻结常量逐字段＋VAD advisory门＋`build_for_chunks`逐项重建＋ffmpeg按边界落盘＋timeline/merge＋exactly计数＋文本只返回不断言）；QA：注入3 chunk calls==3＋三prompt各异复算一致＋真调1 chunk calls==1＋合并单调＋冻结12字段对齐；独立抽验：`_check_chunks`空/错序拒收走读＋results `inj.calls3/real.calls1/recalc`键已复读（真调以QA有界2次为准，product不重调） | 可证明 |
| P0-5 | §72/§73子集门可证明（Stage8 5断言） | 见§2表；QA §4五项全☑（HAPPY-B注入三chunk＋A4夹具双证据＋HAPPY-B/C word双路＋HAPPY-C真调单调＋三Chunk各异＋asr-only＋hash翻转）；独立抽验：results `happy.73-24/25/26/27/15`＋`bad.layer_leak.exit1`键已复读 | 可证明 |
| P0-6 | STOP EXPANSION门可证明（七目录不动＋archive恒0＋current零写＋无越权＋零直写DB） | QA：Stage9+关键词零命中＋直写DB零命中＋VAD过滤零命中＋fuzzy零命中＋常量恒＋archive全库0＋current零写＋七回归PASS；独立抽验：四重`rg -g '*.py'`（Stage9+/直写DB/VAD过滤/fuzzy）RC=1四空＋`ls src/stage8` 6文件＋`src/stage1-7/`未触碰（非git仓库N/A，见U-5） | 可证明 |
| P0-7 | 外置合成验收门可证明（外置目录＋合成副本＋真实长视频零触碰） | QA：全用例在`/tmp/s8qa`内＋最大64044B≤135168B门＋Whisper有界2＋真实库零触碰＋文本不断言声明；独立抽验：`/tmp/s8qa/input/synth_2s.wav`在盘64044B＋results `whisper_calls=2/max_bytes=64044/vad_status双OK`已复读＋本轮product自验仓库内零写盘除本报告 | 可证明 |

## 2. §72/§73子集门5断言（PLAN P0-5，QA §4逐项；任务目标§73-24/25/26重点）

| §72/§73子集 | QA | 产品抽验 |
|---|---|---|
| §73-24（Segment正常：合并后非空＋absolute单调） | ☑ 注入三chunk＋A4夹具双证据（`happy.73-24.nonempty/monotonic`） | ☑ results两键ok已复读＋merge单调校验已走读 |
| §73-25（Word Timestamp能力正常：OFF默认透传＋ON不断链，不扩展） | ☑ HAPPY-C真调OFF＋HAPPY-B ON全员双戳（`happy.73-25.word.on/off`） | ☑ results两键ok已复读＋`_map_words`双戳透传已走读 |
| §73-26（Absolute Timeline正确：夹具双算一致＋接线输出absolute==chunk_start+relative） | ☑ 合成overlap夹具逐段等式＋双保留＋真调单调（`happy.73-26.dual`＋HAPPY-C mono） | ☑ `298.0+0.5=298.5`已复跑＋results键ok已复读 |
| §73-27联动（Prompt每Chunk重建，三Chunk各异，永不复用） | ☑ happy＋接线双证据（distinct/recalc/noreuse三键） | ☑ results三键ok已复读＋`len(prompts)==len(chunks)`门已走读（token数以QA为准） |
| §73-15分层延续（vad/chunking只进ASR，串层即错） | ☑ asr-only＋串层坏例exit 1＋hash翻转（`happy.73-15/hash.flip`＋`bad.layer_leak`＋A8） | ☑ `bad.layer_leak.exit1`已复读＋`assert_asr_layer_only`过/漏两路已走读 |

## 3. U-1~U-8接受为非阻塞的理由（＋U-9；长视频不测延续）

- U-1（真实长视频未测）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言VAD观测＋切分数学＋时间映射＋合并归属＋接线计数（sha/Count/exit码/hash复算/单调），不认语音语义；多chunk长时语义只用600/601/1200数学＋合成segment夹具证明，真实视频造不出门内翻转。延续债：产品完成后再拿1个真实视频走VAD观测（不过滤）→planner→接线（calls==chunks）→merge（单调）一遍，不断言词准确率只断言字节一致＋复算一致＋单调。长视频不测延续。
- U-2（文本内容不断言）：接受。PLAN In Scope＋S8-T04验收行明示“文本内容不断言（词准确率/Golden/CER属Stage11+）”；合成2s正弦无语音，空文本合法；本轮以`str/list`类型＋`calls==chunks`＋prompt复算一致＋VAD字节一致＋单调为判据，质量门后移不卡本门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s8qa_run.py`＋八坏例（vad_filter/vad_thr_drift/plan_illegal/plan_drift/timeline_disorder/merge_empty/layer_leak/wav_shape）＋结果`/tmp/s8qa/s8qa_results.json`已记录，本轮product已复读`113/113 fails=[]`＋八exit1键，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s8qa` 7库＋input 64K＋Stage7/6/5/4/3/2/1旧账＋$TMPDIR）＋用户级python包（numpy/mlx-whisper/silero-vad/torch/watchdog，QA自装），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1门反证＋Stage2五步链＋Stage3 verdict＋Stage4旧库PUBLISHED行＋Stage5十一步＋Stage6双算＋Stage7接线七回归全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）；建议进git后恢复diff硬门。
- U-6（三表1/1口径）：接受。复用/bump库恒0/0/0；reg_s3库`1/1`系QA脚手架经Stage3公开API合成Rendered Final所致（不绕门），非Stage8代码新增写（直写grep RC=1反证＋`archive_commits`全库0＋sources列级不变）；若按字面“恒0”卡脚手架库则无verdict证据可举，QA按S7同一口径验收，product认同。
- U-7（HANDOFF滞后）：接受。根HANDOFF仍停Stage2 CLOSED是TM记账问题，不影响本轮可证明性；QA已以`src/stage8/`落盘6文件＋PLAN S8-T05为准独立覆盖113断言，builder自验入口缺失不卡QA。建议TM/supervisor补记Stage3~8链状态。
- U-8（VAD SKIPPED未走）：接受。SKIPPED系缺包容错分支（fail-closed返回，不抛错不丢音频），非P0主张的OK主路径；本轮silero可用，双thr走OK路径已是更强证据；补测只需卸包重跑一遍，交后续按需补，不卡本PASS。
- U-9（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。VAD硬门审计（`filtering=True`拒＋thr冻结＋字节一致）与Merge审计（四优先级顺序＋text步仅同start同文本＋禁整篇fuzzy）与接线审计（冻结12字段对齐＋`calls==len(chunks)`＋prompt逐项重建＋asr-only）三处正是code-reviewer主责，建议supervisor复检时点名补审这三处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑VAD观测→planner→接线→merge→诱饵Run，不断言速度/准确率只断言字节一致＋复算一致＋单调＋Source/Run；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s8qa`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s8qa_run.py`＋`s8qa_results.json`＋八坏例（vad_filter/vad_thr_drift/plan_illegal/plan_drift/timeline_disorder/merge_empty/layer_leak/wav_shape）路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-7/U-9）：supervisor确认HANDOFF补记Stage3~8链＋Stage8 code-reviewer是否补审（重点：VAD硬门＋Merge四优先级＋接线三审计＋STOP四重grep），非P0，不卡本PASS。

---
目标：Stage8闭环产品验收｜剩 P0：无（P0 Blocking以STAGE8-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
