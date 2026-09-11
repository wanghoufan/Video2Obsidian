
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮确定性`.bin`合成副本＋合成segments；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage3闭环） | STAGE3-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | Stage1 T01→T06 happy未在本套件全链重跑（Raw经`build_raw_content`＋`validate_raw_artifact`门合成；门本身回归反证PASS） | P2 | 否（门与音频内容无关，不卡闭环） | STAGE3-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s3qa_run.py`＋双坏例子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE3-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s3qa`多data_root新增＋双坏例脚本＋Stage2约1.9M＋Stage1旧账＋$TMPDIR，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE3-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`/`src/stage2/` git diff口径N/A（当前目录非git仓库；以S2 startup回归＋S1门反证＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE3-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | builder自验harness未在工作区落盘（6异常清单按S3-T06口径由QA覆盖；以后补以本报告exit码为准对账） | P3 | 否（覆盖已闭环，不卡门） | STAGE3-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Stage3无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0/1/2-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE3-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage3闭环，P0-1~P0-8可证明，Case4/5/6＋lineage可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE3-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE3-QA-REPORT.md`（PASS，happy 1遍＋异常6个＋lineage并入，39/39双轮exit 0，坏例只看exit码）＋`src/stage3/`（artifact_commit/normalize/render/derive/lineage/__init__共6文件）＋QA证据`/tmp/s3qa/s3qa_results.json`（39 case全ok=true已复读）＋Runner`/tmp/s3qa_run.py`＋双坏例脚本。
- 用户只关心五句话：改一次错别字规则会不会重新跑一遍Whisper——不会（Case4 `whisper_calls=0`，只出新NormRev＋新Rendered，Raw/诱饵不变）；改一次分段格式会不会动原文——不会（Case5复用同一normalized ID，NormRev＋0，只出新RenderRev）；转完的Run会不会被新版本回滚——不会（Case6派生前后Run＝COMPLETED，guard拒写exit 2）；中途断电/库落后丢不丢——不丢（Repair Forward补Receipt＋SQLite前向修，Whisper 0）；渲染会不会直接覆盖我的Obsidian笔记——不会（走到PUBLISH_EVALUATION只记verdict，`publish_records`/`archive_commits`恒0，诱饵md字节不变）。另加一句定心丸：全链查得到（`get_lineage` Source→Run→Raw→NormRev→Normalized→RenderRev→Rendered→verdict，缺环标missing不编造）。
- 打回条件均未触发：P0-1~P0-8任一项不可证明即打回——本轮8项全部有代码＋Count/exit码/hash三方证据；publish/archive非空即打回——抽查happy/case4/case5三库6格全0；出现`run_asr_single_file`/`PUBLISHING`/`PUBLISHED`即打回——`src/stage3`全文grep零命中已确认；有Raw写/诱饵被改即打回——三复算不变＋诱饵hash不变已确认。

## 1. P0-1~P0-8可证明逐项（口径=STAGE3-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Normalization Revision生命周期可证明（主链4态＋旁路2态，§29六字段hash，Correction纯函数无LLM） | `normalize.py`（PENDING→NORMALIZING→COMMITTING→COMPLETED＋FAILED_RETRYABLE/FINAL；`NORMALIZATION_PROFILE_FIELDS`六字段；`CORRECTION_RULES` corr-v1/v2冻结表精确替换；写中央`normalization_revisions`＋`state_events`）；QA：P0-1hz改一字段hash变＋`VIP COIN→Vibe Coding`/`Ai编程→AI编程`全中；独立抽验：源码六字段＋corr表已直读，QA results `P01-profile-hash`/`CORR-v1` ok | 可证明 |
| P0-2 | Render Revision生命周期可证明（走到PUBLISH_EVALUATION只记verdict，§30五字段hash，§47规则序） | `render.py`（PENDING→RENDERING→ARTIFACT_COMMITTING→ARTIFACT_COMPLETED→PUBLISH_EVALUATION；`RENDER_PROFILE_FIELDS`五字段；`render_paragraphs`长停顿＞强标点＞目标长＞硬上限；verdict `CANONICAL_OUTPUT_EXISTS`/`PENDING_PUBLISH`零写盘；模块内无`PUBLISHING`/`PUBLISHED`）；QA：P0-2hz四例各2段全中；独立抽验：grep `PUBLISHING`/`PUBLISHED`零命中，results `PARA-*`四键ok | 可证明 |
| P0-3 | Normalized/Rendered两阶段提交可证明（tmp→fsync→schema→PREPARED→rename→final校验→Receipt双落） | `artifact_commit.py`（`prepare_artifact`/`commit_artifact`/`recover_artifact`三分支；中央artifacts PREPARED→COMMITTED；Manifest只追加；hash不等永判无效）；QA：HAPPY Norm=1/Render=1＋artifacts 2 COMMITTED＋state_events 9＋final `sha256:`前缀＋双Receipt；独立抽验：happy库norm=1/rend=1＋`normalized/*.prepare/commit_receipt.json`＋`render/*.prepare/commit_receipt.json`双双在盘 | 可证明 |
| P0-4 | Recovery可证明（三分支＋SQLite前向修＋Whisper 0） | 同上`recover_artifact`；QA：REC `prepared_final_exists_repair_forward` exit 0＋TMP-only `prepared_tmp_only_continue_commit` exit 0＋HASH-tamper子进程exit 1 `ArtifactInvalid`；独立抽验：重跑`TAMPER_EXIT=1`＋`GUARD_EXIT=2`双exit码已取（管道掩码已排除，直调取码） | 可证明 |
| P0-5 | Case4可证明（Correction变→新NormRev＋新Rendered，Whisper 0/Raw不变/诱饵不变） | `derive.py::derive_on_correction_change`（复用同一raw ID→新NormRev→下游新RenderRev，`whisper_calls=0`）；QA：新NormRev `…e336`＋新Rendered `…0d93`＋Norm=2＋Raw/诱饵不变；独立抽验：case4库norm=2/rend=2/pub=0/arch=0 | 可证明 |
| P0-6 | Case5可证明（Formatter变→复用normalized ID零新NormRev＋只建新RenderRev） | `derive.py::derive_on_formatter_change`（delta非0即抛，NormRev＋0）；QA：复用normalized `…5507`＋delta=0＋新RenderRev `…121a`；独立抽验：case5库norm=1/rend=2/pub=0/arch=0（复用成立） | 可证明 |
| P0-7 | Case6＋Raw Immutable可证明（Run不回滚＋Raw拒写） | derive不读写Run行（注释明示）；复用`guarded_open_raw_for_write`语义；QA：派生前后Run=COMPLETED＋子进程exit 2 `RawImmutableError`＋Raw字节不变＋0444；独立抽验：`GUARD_EXIT=2`已取 | 可证明 |
| P0-8 | STOP EXPANSION门可证明（publish/archive恒0＋stage1/2零改＋合成副本＋永不调Whisper） | `artifact_commit.py`头注STOP＋`derive.py` import禁令；QA：三库publish/archive 0/0＋`grep run_asr_single_file`空＋`src/stage1/2`未触碰（回归PASS代证）＋Runner exit 0；独立抽验：happy/case4/case5三库publish/archive 6格全0＋`run_asr_single_file`/`PUBLISHING`/`PUBLISHED` grep零命中＋`whisper`命中仅`whisper_calls==0`计数器＋Runner重跑`TOTAL 39/39 exit=0` | 可证明 |

## 2. §72子集门9断言（PLAN In Scope §51，QA §4逐项）

| §72子集 | QA | 产品抽验 |
|---|---|---|
| Correction Rules Change不重调Whisper | ☑ Case4 `whisper_calls=0`＋无import | ☑ `whisper` grep仅计数器＋results `C4-*` ok |
| Raw Hash不变 | ☑ HAPPY/Case4/Case5三复算一致 | ☑ results `HAPPY-raw-hash`/`C4-raw-hash`/`C5-raw-decoy` ok |
| 新Normalization Revision | ☑ 新ID＋Norm=2 | ☑ case4库norm=2直查 |
| Formatter Change只建Render Revision | ☑ delta=0＋新RenderRev | ☑ case5库norm=1/rend=2直查 |
| Completed Run不被回滚 | ☑ Case6 COMPLETED | ☑ results `C6-run-COMPLETED` ok |
| Normalized PREPARED Receipt | ☑ HAPPY/TMP双证据 | ☑ happy库prepare/commit双receipt在盘 |
| Artifact Hash Validation | ☑ tamper判无效＋final==expected三方链 | ☑ `TAMPER_EXIT=1`直取 |
| SQLite Forward Repair | ☑ REC exit 0落后方被修 | ☑ results `REC-repair-forward` ok |
| Raw Immutable | ☑ guard REFUSED＋字节不变＋0444 | ☑ `GUARD_EXIT=2`直取 |

## 3. U-1~U-6接受为非阻塞的理由（＋U-7）

- U-1（合成副本非真实长视频）：接受。PLAN Out of Scope明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage派生门只认hash/Count/verdict，不认音视频语义；Case4/5的“变与不变”恰恰只能用合成字节＋冻结规则表精确构造，真实视频造不出版本差。延续债：产品完成后再拿1个真实视频走Raw→Norm→Render→lineage一遍，不断言速度只断言门状态。
- U-2（Stage1 happy未全链重跑）：接受。Raw经`build_raw_content`＋`validate_raw_artifact`门合成（不绕校验）；门本身回归反证PASS（非法Raw被`PrepareError`拒收）；provenance/commit门与音频内容无关。不断链，不卡门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s3qa_run.py`＋双坏例脚本＋结果`/tmp/s3qa/s3qa_results.json`已记录，本轮product已复读39 case全ok＋重跑`TOTAL 39/39 exit=0`，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s3qa`多data_root＋双坏例脚本＋Stage2约1.9M＋Stage1旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——S2 `startup`回归＋S1门反证＋QA零改声明（业务代码零改，仅新增本报告）；建议进git后恢复diff硬门。
- U-6（builder harness未落盘）：接受。6异常清单（Case4/5/6＋RepairForward＋tmp-only＋hash篡改）已按S3-T06口径由QA全覆盖＋exit码对账；若builder后补harness，以本报告`TOTAL 39/39`＋`TAMPER 1`＋`GUARD 2`为准对账，不返工产品结论。
- U-7（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。Correction纯函数审计（无IO/无网络/无模型import）与两阶段提交顺序（tmp→fsync→PREPARED→rename→final校验→双Receipt）两处正是code-reviewer主责，建议supervisor复检时点名补审这两处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑Raw→NormRev→RenderRev→verdict→lineage，不断言速度只断言Count/hash/verdict；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s3qa`＋双坏例脚本（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s3qa_run.py`＋`s3qa_results.json`＋双坏例脚本路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-7）：supervisor确认Stage3 code-reviewer是否补审（重点：Correction纯函数无智能化＋两阶段提交顺序＋STOP三符号零命中），非P0，不卡本PASS。

---
目标：Stage3闭环产品验收｜剩 P0：无（P0 Blocking以STAGE3-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
