
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮确定性`.bin`合成副本＋合成segments；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage4闭环） | STAGE4-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | Stage1 T01→T06 per-job全链未在本套件重跑（Raw经`build_raw_content`＋`validate_raw_artifact`门合成；门本身回归反证PASS） | P2 | 否（门与音频内容无关，不卡闭环） | STAGE4-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（`/tmp/s4qa_run.py`＋三坏例子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE4-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（`/tmp/s4qa` 13 data_root＋`/tmp/s4qa_out` 13诱饵out新增＋Stage3/Stage2/Stage1旧账＋$TMPDIR，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE4-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | `src/stage1/`/`src/stage2/`/`src/stage3/` git diff口径N/A（当前目录非git仓库；以三回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE4-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | builder自验harness未在工作区落盘（happy1＋异常7清单按S4-T06口径由QA覆盖；以后补以本报告exit码为准对账） | P3 | 否（覆盖已闭环，不卡门） | STAGE4-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Stage4无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0/1/2/3-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE4-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage4闭环，P0-1~P0-8可证明，Case12用户文件不变＋Overwrite=0＋Ownership可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE4-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE4-QA-REPORT.md`（PASS，happy 1遍＋异常7个＋lineage并入＋回归三行，107/107双轮exit 0，坏例只看exit码）＋`src/stage4/`（volume_probe/publish_commit/publish/conflict/lineage_ext/__init__共6文件）＋QA证据`/tmp/s4qa/s4qa_results.json`（107断言全pass已复读，`TOTAL 107 PASS 107 FAIL 0`）＋Runner`/tmp/s4qa_run.py`＋三坏例子进程（tamper/race/gate）。
- 用户只关心五句话：转完的Markdown第一次落盘安不安全——安全（HAPPY经§49六步：expected预持久化→same-dir tmp→flush/fsync→`link(2)`独占建→Final Hash Verify→PUBLISHED，三方hash `5236638f…`一致）；两个人同时落同一盘会不会互相覆盖——不会（Case12竞态抢建→本进程`BLOCKED_OUTPUT_CONFLICT`，抢建方`racer wins…`字节级不变，Overwrite=0，行终态BLOCK非PUBLISHED）；我手工改过的笔记会不会被工具悄悄盖掉——不会（A2诱饵append一字节`U`→`BLOCKED_OUTPUT_CONFLICT`，诱饵保留用户字节`…U`，`canonical_writes=0`；A3同字节重发亦`BLOCKED_OUTPUT_EXISTS`不静默认领）；中途崩了丢不丢——不丢（A4 PUBLISHING残留＋hash对上→Repair Forward得PUBLISHED不重建tmp；A5 tmp-only→续Commit落盘；A6篡改Final永判无效exit 1）；全链查得到、算得清是谁的——查得到（`get_lineage_with_publish` Source→Run→Raw→NormRev→Rendered→Canonical Publish九字段环＋Ownership五件套＋Manifest 4 receipts；Run仅回填`initial_publish_record_id`＋`updated_at`两列，状态保持COMPLETED）。另加一句定心丸：烂盘/网盘不硬上（A7无能力卷→`BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM` exit 2，零staging、无fallback），旧地基没动（Stage1/2/3回归全PASS，`archive_commits` 13库全0，Whisper调用恒0）。
- 打回条件均未触发：P0-1~P0-8任一项不可证明即打回——本轮8项全部有代码＋Count/exit码/hash三方证据；`archive_commits`非空即打回——13库全0已直查；出现`run_asr_single_file`/`Reservation Copy`/`fallback`/`force`/`O_TRUNC`即打回——`src/stage4`全文grep零命中已确认（`os.rename`仅探针＋文档行，Final唯一commit为`link(2)`）；有Raw/Rendered写/诱饵用户字节被改即打回——happy复算不变＋A1/A2/A3诱饵字节不变已确认；`publish_records`口径已按PLAN R3变更接受（happy=1、a2/a3=2为预期，不要求stage2旧四表空断言通过）。

## 1. P0-1~P0-8可证明逐项（口径=STAGE4-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | 卷能力门可证明（§54九字段实测＋§55无能力即BLOCK＋无fallback＋§3.14） | `volume_probe.py`（`probe_volume`经stat/st_dev＋O_EXCL探针＋同目录rename探针＋flock实测；`supports_exclusive_rename=False`为POSIX诚实值；`gate_output_root`为唯一门）；QA：PROBE九字段全非空＋A7 monkeypatch双False→BLOCK exit 2＋grep fallback空；独立抽验：直调`probe_volume('/tmp/s4qa_out/happy')`得12键（9必需全非空，APFS local，xcre=True/xren=False）＋`rg Reservation\|fallback`空 | 可证明 |
| P0-2 | Atomic No-Clobber发布可证明（§49六步＋expected预持久化＋`O_CREAT\|O_EXCL`＋Final Hash Verify） | `publish_commit.py`（748行：prepare同事务写`publish_records PENDING`＋`artifacts PREPARED`→gate复检→same-dir tmp→flush/fsync→`os.link(tmp,final)`独占commit→hash校验→PUBLISHED＋Receipt＋COMMITTED；`os.rename`永不落Final，代码零调用；hash不等永判无效）＋`on_tmp_ready`为Case12唯一抢建缝；QA：HAPPY三方hash一致＋A5 tmp-only续Commit＋A6篡改判无效exit 1＋Whisper 0；独立抽验：happy库`pub_3226e81b395b` PUBLISHED＋expected==published（`52366…`）＋诱饵`/tmp/s4qa_out/happy/s4/clip.md`同hash＋`rg O_TRUNC\|force`空 | 可证明 |
| P0-3 | Initial Publish生命周期可证明（§12 Initial分支＋§35九字段＋`PENDING→PUBLISHING→PUBLISHED`） | `publish.py`（缺席→经S4-T02主链＋`state_events`；存在→委托conflict零写盘；成功仅回填Run两列；`publish_mode=INITIAL`唯一）；QA：HAPPY 1 RenderRev→1行PUBLISHED＋九字段齐＋`published_at`置值＋Run列级diff仅两列变；独立抽验：happy中央`publish_records` count=1＋`canonical COMMITTED`＋Run `initial_publish_record_id=pub_3226…`＋状态COMPLETED | 可证明 |
| P0-4 | Subsequent默认不覆盖可证明（§50/§51＋用户编辑Overwrite=0） | `conflict.py`（存在→§53判定，同字节→`BLOCKED_OUTPUT_EXISTS`，异字节→`BLOCKED_OUTPUT_CONFLICT`，BLOCK分支字节级不变＋`canonical_writes=0`）；QA：A2一字节编辑→CONFLICT＋诱饵保留用户字节＋Overwrite=0＋verdict新行（§51口径锁定）；A3同字节→EXISTS非PUBLISHED；独立抽验：a2库两行（PUBLISHED＋BLOCKED_OUTPUT_CONFLICT）＋诱饵尾字节`…U`保留 | 可证明 |
| P0-5 | Output Conflict三分支可证明（§53＋Ownership五件套只恢复/诊断不授权覆盖） | 同`conflict.py`＋`publish_commit.recover_publish`（PUBLISHING＋对上→Forward不重建tmp，其余判BLOCK系，绝不覆盖）；Ownership五件套落SQLite＋Manifest（`render_revision_id/rendered_artifact_id/publish_record_id/expected_output_hash/published_hash`）；QA：A4残留Forward（`publishing_final_exists_repair_forward`）＋A5 tmp-only（`prepared_tmp_only_continue_commit`）＋BLOCK分支canonical不变；独立抽验：happy Ownership五件套＋`ownership.match`在results.json中＋a2/a3 `canonical_writes=0` | 可证明 |
| P0-6 | Case12 Output Race可证明（§70：抢建→BLOCK＋用户文件不变＋Overwrite=0＋行BLOCK） | hook在tmp fsync后Final commit前抢建异字节；`link(2)` EEXIST→`BLOCKED_OUTPUT_CONFLICT`，open行原地更新为BLOCK（§51口径）；QA：in-process＋子进程exit 2双证据＋`PUBLISHED`计数0；独立抽验：a1库单行`BLOCKED_OUTPUT_CONFLICT`＋PUBLISHED count=0＋诱饵27字节`racer wins different bytes`原样＋重跑`--bad race exit=2`已取 | 可证明 |
| P0-7 | Lineage延伸＋Run回填可证明（§4最后一环＋列级diff＋Manifest只追加） | `lineage_ext.py`（只读复用stage3 `get_lineage`＋追加Canonical环九字段；`record_publish_receipt`经append-only写Manifest；缺环标missing）；QA：LIN-full全链＋4 receipts＋LIN-missing标`publish=missing`非异常；独立抽验：results.json `happy.lineage.ring`＋9字段＋`lin.missing`全pass | 可证明 |
| P0-8 | STOP EXPANSION门可证明（archive恒0＋stage1-3零改＋合成副本＋永不调Whisper） | 代码头注STOP＋无Watch/Scan/Archive/MenuBar/Prompt/VAD/Chunk/阈值路径；QA：13库`archive_commits`全0＋`rg run_asr_single_file`空＋三回归PASS＋Runner exit 0＋诱饵out全在`/tmp/s4qa_out/<case>/`与真实库无交集＋真实长视频零触碰；独立抽验：13库archive直查全0＋`rg run_asr/fallback/force`三空＋rename审计（Final唯一`os.link`）＋重跑`TOTAL 107/107`＋`tamper 1/race 2/gate 2`三exit码已取 | 可证明 |

## 2. §72子集门7断言（PLAN In Scope §56，QA §4逐项）

| §72子集 | QA | 产品抽验 |
|---|---|---|
| Atomic No-Clobber implementation | ☑ HAPPY link(2)＋三方hash＋A5 tmp-only，rename零落Final | ☑ happy三方`5236638f`一致＋`os.link`唯一commit |
| Output Race Fault Injection | ☑ A1 hook抢建→BLOCK＋用户字节不变＋行BLOCK | ☑ a1诱饵`racer wins`原样＋行CONFLICT＋`race exit=2`直取 |
| Unknown-User-edited Overwrite=0 | ☑ A2一字节编辑→CONFLICT＋诱饵保留用户字节 | ☑ a2诱饵尾`U`保留＋`canonical_writes=0` |
| Initial Publish | ☑ HAPPY `PENDING→PUBLISHING→PUBLISHED`＋§35九字段＋`published_at` | ☑ happy行PUBLISHED/INITIAL＋Run回填两列 |
| Subsequent不自动覆盖 | ☑ A3同字节亦`BLOCKED_OUTPUT_EXISTS`，零写盘 | ☑ a3字节不变＋非PUBLISHED |
| PENDING_PUBLISH | ☑ HAPPY verdict缺席分支＋REG-S3双值域 | ☑ results `happy.verdict.absent` ok |
| CANONICAL_OUTPUT_EXISTS | ☑ Stage3 verdict语义沿用；存在分支走BLOCK，S4-T03零写盘 | ☑ results `reg.s3.verdict`＋a2/a3 BLOCK行 |

## 3. U-1~U-6接受为非阻塞的理由（＋U-7；长视频不测延续）

- U-1（合成副本非真实长视频）：接受。PLAN Out of Scope第71行明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage发布门只认Rendered字节/hash/verdict/竞态窗口，不认音视频语义；Case12抢建窗口与A2一字节编辑恰恰只能用合成字节精确构造，真实视频造不出竞态对手。延续债：产品完成后再拿1个真实视频走Raw→Norm→Render→initial_publish→lineage一遍，不断言速度只断言PUBLISHED/三方hash/verdict。长视频不测延续。
- U-2（Stage1 happy未全链重跑）：接受。Raw经`build_raw_content`＋`validate_raw_artifact`门合成（不绕校验）；门本身回归反证PASS（REG-S1非法Raw被拒收）；provenance/commit门与音频内容无关。不断链，不卡门。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s4qa_run.py`＋三坏例（`--bad tamper/race/gate`）＋结果`/tmp/s4qa/s4qa_results.json`已记录，本轮product已复读107断言全pass＋重跑`TOTAL 107/107 exit=0`＋三exit码直取（1/2/2），可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s4qa` 13 data_root＋`/tmp/s4qa_out` 13诱饵out＋Stage3/Stage2/Stage1旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1门反证＋Stage2 startup五步有序＋Stage3 norm/render链三回归全PASS＋QA零改声明（业务代码零改，仅新增本报告）；建议进git后恢复diff硬门。
- U-6（builder harness未落盘）：接受。happy1＋异常7清单（Case12竞态/用户编辑/同字节重发/残留Forward/tmp-only/篡改判无效/无能力卷）已按S4-T06口径由QA全覆盖＋exit码对账；若builder后补harness，以本报告`TOTAL 107/107`＋`TAMPER 1`＋`RACE 2`＋`GATE 2`为准对账，不返工产品结论。
- U-7（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。No-Clobber独占创建审计（`link(2)`唯一、rename永不落Final）与Conflict三分支判定（Forward条件三合一＋BLOCK字节不变）两处正是code-reviewer主责，建议supervisor复检时点名补审这两处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑Raw→NormRev→RenderRev→initial_publish→lineage，不断言速度只断言PUBLISHED/三方hash/verdict/Overwrite；机器时间分钟级＋人工＜15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s4qa`＋`/tmp/s4qa_out`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s4qa_run.py`＋`s4qa_results.json`＋三坏例（tamper/race/gate）路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-7）：supervisor确认Stage4 code-reviewer是否补审（重点：`link(2)`唯一commit＋rename审计＋Conflict三分支＋Ownership五件套只诊断不授权覆盖），非P0，不卡本PASS。

---
目标：Stage4闭环产品验收｜剩 P0：无（P0 Blocking以STAGE4-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
