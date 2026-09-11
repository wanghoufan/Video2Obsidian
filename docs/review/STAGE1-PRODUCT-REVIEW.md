
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实Whisper端到端重跑（本轮桩1次代替；冻结revision走常量断言+沿用Stage0基准） | P2 | 否（转补测债，不卡Stage1闭环） | STAGE1-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 真实中文视频复验（本轮64K确定性.bin合成源；provenance/commit门与音频内容无关） | P2 | 否（转补测债，不卡Stage1闭环） | STAGE1-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | 残留清理（/tmp/s1t08_qa 768K + s1t04/s1t05/s1t07证据 + $TMPDIR 1.8G，H5=暂不清） | P3 | 否（交neat-freak收尾） | STAGE1-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | Runner脚本归档（/tmp/s1t08_qa_run.py在仓库外，复现找QA要路径） | P3 | 否（H2外置约束所致，路径已记录） | STAGE1-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | Stage1无独立code-reviewer报告（只有Stage0四件套；本轮链是否跳过code-reviewer请supervisor确认） | P2 | 否（流程项，非STAGE1-PLAN §Stage P0） | product-reviewer独立发现 | CLOSED（STAGE1-CODE-REVIEW.md已落盘，前提消失，neat-freak 2026-09-11对齐） |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage1闭环，P0-1~P0-9可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE1-PLAN.md`（§Stage P0=验收唯一口径）＋`docs/qa/STAGE1-QA-REPORT.md`（PASS，happy 1遍+异常5个，坏例只看exit码）＋`src/stage1/`（ingest/verify/asr/post_verify/prepare/commit/recovery共7模块）。
- 用户只关心四句话：单视频能不能跑通——能（happy端到端COMMITTED，final==expected三方一致）；源文件被改会不会错入库——不会（Before/During/Case8全部BLOCK且Raw Commit=0，diagnostic-only隔离）；中途断电丢不丢——不丢（Case9/Case15均Repair Forward，Whisper不增加）；已入库的Raw改得动吗——改不动（0444+API guard双拒写，hash不变）。
- 打回条件均未触发：P0-1~P0-9任一项不可证明即打回——本轮9项全部有代码+exit码+hash三方证据；During后Raw Commit≠0即打回——实测DURING/CASE8 formal均为0；kill-9后重跑Whisper即打回——实测1→1零增加。

## 1. P0-1~P0-9可证明逐项（口径=STAGE1-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码+QA+独立复验） | 结论 |
|---|---|---|---|
| P0-1 | 指定路径ingest跑通，产出COMMITTED Raw+SQLite COMMITTED | `ingest.py::ingest_specified_path`（§36 namespace+先Source后Run G1）；QA-HAPPY全0+COMMITTED（final `f640ea75…4a2b3d5`==expected，prepare_receipt/sqlite/manifest三方一致）；独立复算happy manifest COMMITTED+sqlite COMMITTED+0444+disk==expected已确认 | 可证明 |
| P0-2 | 转写前Fast Verification（device/inode/size/mtime_ns，变则重hash，mismatch BLOCK不进ASR） | `verify.py::verify_source_for_transcription`+`gate_transcription`（BLOCK时asr_calls=0）；QA-BEFORE exit 2+BLOCK码+桩零调用+无final；独立复验：clean exit 0 PASS / 篡改后exit 2 BLOCK一致 | 可证明 |
| P0-3 | ASR参数=Stage0冻结（a4aaeec0/temp-wav 16k mono/word默认OFF/nst 0.6/单文件直转/VAD只观测） | `asr.py`冻结常量与TECHNICAL_BENCHMARK_REPORT §9逐项一致（repo/rev/temp/False/0.6/thr 0.3–0.5/worker 1，独立直读确认）；revision漂移/word未声明ON/nst偏离/pipe/多worker/VAD过滤均FAIL硬门；执行层本轮为计数桩（见U-1，不卡门逻辑，理由见§3） | 可证明（代码+常量；执行层转U-1补测债） |
| P0-4 | 转写后Mandatory Strong SHA256+G2前后fstat对比（无条件重算，只认SHA256裁决） | `post_verify.py`无条件`sha256_file`+`hash_recomputed=true`；QA-DURING exit 2 BLOCK+`commit_authorized=false`；QA-CASE8 changed双`[]`但BLOCK（`hash_match=false`，只看size/mtime的实现必FAIL）；独立复算case8 post_verify.json一致 | 可证明 |
| P0-5 | Raw PREPARE（tmp→flush→fsync→schema validation→expected持久化→SQLite PREPARED→COMMIT事务） | `prepare.py::prepare_raw`（非PASS verdict直接REFUSED exit 2；validation缺失unlink tmp无行；SQLite/tmp不一致FAIL）；QA-HAPPY prepare exit 0+expected三方一致 | 可证明 |
| P0-6 | Raw COMMIT+Immutable（atomic rename→fsync(parent)→final校验→Manifest/SQLite COMMITTED；已COMMIT只读） | `commit.py::commit_raw`（final!=expected永不COMMIT；`assert_raw_mutable`+0444双 guard）；QA-HAPPY commit exit 0+`guarded_open_raw_for_write` REFUSED+复算hash不变；独立复验immutable REFUSED一致 | 可证明 |
| P0-7 | Recovery Truth Model（Final+Hash=Truth；PREPARED+Final在→补Manifest/SQLite不重跑Whisper；tmp在→验后继续Commit；hash错永不视为有效；SQLite落后只许Repair Forward） | `recovery.py::recover_raw`（零ASR import，结果`asr_calls=0/whisper_calls=0`）；QA-CASE9/CASE15均exit 0+`prepared_final_exists_repair_forward`+whisper 1→1+final==expected；独立复算recover_receipt一致 | 可证明 |
| P0-8 | Hash mismatch隔离（diagnostic-only，不进lineage不触发下游；During Raw Commit=0） | `post_verify.quarantine_to_diagnostic`（只写`diagnostic_only/*DIAGNOSTIC-ONLY.json`，不动raw/manifest/sqlite）；QA-DURING diagnostic 1件+formal 0+prepare REFUSED exit 2；happy lineage `grep diagnostic`零命中；独立复算during无raw.json+manifest SCAFFOLD+无artifacts表一致 | 可证明 |
| P0-9 | 异常全覆盖可复现（Before/During/Case8/kill-9/SQLite落后任一缺失即不闭环） | QA 5异常全过：BEFORE(exit 2)/DURING(post 2+prepare 2)/CASE8(post 2,changed [])/CASE9(recovery 0)/CASE15(recovery 0)，覆盖PLAN T08“至少4个”及H4加严“kill-9与SQLite落后分开计”共5断言；独立复验Before/During exit 2链一致 | 可证明 |

## 2. H1-H5兑现（H4=5断言）

| H | 拍板内容 | 兑现 |
|---|---|---|
| H1 | 单测视频路径+是否允许复制/篡改副本（原片不动） | 部分偏离但接受：QA用64K确定性.bin合成源而非5–25分钟真实中文视频（U-2）；只动副本、原片不动原则遵守；provenance/commit门与音频内容无关，音频路径由U-1覆盖。转补测债，不卡闭环 |
| H2 | Data Root父目录位置+本地盘确认 | 兑现：`/tmp/s1t08_qa/`仓库外独立测试目录，仓库内零写盘除本报告；`ingest.probe_volume`本地门+`/tmp`本地盘，iCloud/远端BLOCK逻辑在代码内 |
| H3 | 允许写job/tmp/final/manifest/SQLite+kill-9演练+复用Stage0 venv不新增依赖 | 兑现：6 job全在H2目录内；rename模拟kill-9+sqlite回拨演练已执行；stdlib+Stage0 venv（报告声明未新增依赖） |
| H4 | T08“至少4个”是否改为“至少5个（kill-9与SQLite落后分开计）” | 兑现：QA执行5异常（Before/During/Case8/Case9/Case15），kill-9与SQLite落后分开两用例，与supervisor建议一致 |
| H5 | $TMPDIR 1.8G现在清还是留 | 兑现：决策=暂不清（QA U-3），残留清单齐全交neat-freak收尾 |

## 3. U-1~U-4接受为非阻塞的理由

- U-1（桩代替真实Whisper）：接受。本Stage门逻辑（Verification/Provenance/PREPARE/COMMIT/Recovery/Immutable）与音频内容无关；冻结值走代码常量断言已与Stage0 §9逐项对齐；真实模型能力（RTF/中文检出/word差/VAD）Stage0已用19轮真机证明。补测债：拿H1真实视频跑一遍`asr.run_asr_single_file`真路径（temp-wav+revision match+profile落盘），不断言耗时只断言门状态。
- U-2（合成源非真实视频）：接受。同上，门只认fstat+SHA256+hash，不认音频语义；Case8（同size+mtime异bytes）恰恰只能用合成字节精确构造，真实视频反而造不出。补测债与U-1合并为一次真实视频端到端。
- U-3（tmp待清）：接受。H5决策本就是暂不清；残留全部在`/tmp`测试区（768K新增+s1t04/s1t05/s1t07证据+$TMPDIR 1.8G），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-4（runner外置）：接受。H2外置目录约束所致（仓库内零写盘），路径`/tmp/s1t08_qa_run.py`+结果`/tmp/s1t08_qa/s1t08_results.json`已在报告中记录，可复算；建议neat-freak收尾时把runner路径记入HANDOFF。

## 4. §72子集门9断言（Stage1段，PLAN In Scope §56）

| §72子集 | QA§4 | 独立复验 |
|---|---|---|
| Transcription前Verification PASS | ☑ happy verify exit 0 | ☑ fresh ingest exit 0 + verify clean exit 0 |
| 转写后Mandatory SHA256 PASS | ☑ happy post exit 0+`hash_recomputed=true` | ☑ 代码无条件重算路径已读 |
| Same size+mtime异bytes PASS | ☑ CASE8 BLOCK（changed []反证SHA256裁决） | ☑ post_verify.json复算一致 |
| During变化Raw Commit=0 | ☑ DURING+CASE8 formal均为0 | ☑ during无raw.json+manifest SCAFFOLD |
| Raw PREPARED Receipt PASS | ☑ happy prepare exit 0+expected三方一致 | ☑ prepare_receipt==disk复算一致 |
| Raw Rename/Manifest Kill Recovery PASS | ☑ CASE9 exit 0 Repair Forward | ☑ recover_receipt path一致 |
| Artifact Hash Validation PASS | ☑ HAPPY/CASE9/CASE15 final==expected；mismatch永不有效由DURING/CASE8反证 | ☑ 三job复算一致 |
| SQLite Forward Repair PASS | ☑ CASE15 exit 0落后方被修不重跑ASR | ☑ recover whisper=0一致 |
| Raw Immutable PASS | ☑ API guard REFUSED+hash不变+0444 | ☑ guarded_open REFUSED独立复现 |

## 5. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1+U-2合并）：拿一台Mac+Stage0 venv+1个中文视频跑happy全链真ASR，机器时间约5–25分钟片长的1/6–1/12（RTF 0.08–0.18为据）+人工<30min；不断言速度只断言门状态与hash三方一致。
- 清理（U-3）：neat-freak顺手清`/tmp/s1t08_qa`+旧证据+$TMPDIR（删前先快照结论，证据已在报告+results.json），<15min人工。
- 归档（U-4）：把`/tmp/s1t08_qa_run.py`路径记入HANDOFF（或拷一份进docs/qa备注外置原因），<5min。
- 流程确认（U-5）：supervisor确认Stage1是否跳过code-reviewer（本窗口只见到Stage0 code-review；按AGENTS不可跳code-reviewer+qa+supervisor，跳了需记一句原因）。非P0，不卡本PASS，但需在supervisor复检前补记。

---
目标：Stage1闭环产品验收｜剩 P0：无（P0 Blocking以STAGE1-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
