
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮32–64K确定性.bin合成副本；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage2闭环） | STAGE2-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | 真实Watchdog/Scan/Reconciliation未起（本轮三线程直调discover()并发模拟；PLAN Out of Scope明示不起watchdog线程不扫真实目录） | P2 | 否（范围外，不卡闭环） | STAGE2-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | Runner脚本归档（/tmp/s2t07_qa_run.py在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE2-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | 残留清理（/tmp/s2t07_qa约1.9M新增＋Stage1残留/tmp/s1t*＋$TMPDIR，H5延续暂不清） | P3 | 否（交neat-freak收尾） | STAGE2-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | src/stage1/ git diff口径N/A（当前目录非git仓库；以Stage1功能回归PASS代证，QA未触碰业务代码） | P3 | 否（代证成立，不卡门） | STAGE2-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | MANUAL_REPROCESS仅模型预留（NotImplementedError，语义留后续Stage）；NETWORK/Remote根门与iCloud共用probe_volume，本轮只实测iCloud marker路径 | P3 | 否（PLAN只要求iCloud-Remote用例） | STAGE2-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Stage2无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0/1-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE2-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage2闭环，P0-1~P0-8可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE2-PLAN.md`（§Stage P0=验收唯一口径）＋`docs/qa/STAGE2-QA-REPORT.md`（PASS，happy 1遍＋异常6个，27/27双轮exit 0，坏例只看exit码）＋`src/stage2/`（store/candidate/source/runs/instance/__init__共6文件）＋QA证据`/tmp/s2t07_qa/s2t07_results.json`（27键全pass=true已复读）。
- 用户只关心四句话：同一视频发现三次会不会建出三条身份——不会（Triple Race后Source=1且AUTO Run=1，PROMOTED＋2×MERGED）；文件内容变了但size+mtime没变会不会吞掉——不会（Case13建新Candidate出新Source，nsrc=2旧保留）；双开会不会把库写坏——不会（第二实例exit 3，DB mtime纳秒级不变，零写盘）；iCloud目录会不会错吃——不会（exit 2＋BLOCKED_UNSUPPORTED_ROOT_FOR_V1）。另加一句定心丸：Stage1还能跑（per-job ingest→commit回归COMMITTED），Stage3+四表全0、Whisper调用恒0（本Stage不产生任何转写行为）。
- 打回条件均未触发：P0-1~P0-8任一项不可证明即打回——本轮8项全部有代码＋Count/exit码双证据；Stage3+表非空即打回——抽查happy/p05/p02三库12格全0；Run出QUEUED即打回——抽查三库直方图仅QUEUED；src/stage2全文grep whisper零命中已确认。

## 1. P0-1~P0-8可证明逐项（口径=STAGE2-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | 中央SQLite落盘可用（9表DDL＋两Partial UNIQUE＋WAL＋FK＋无锁即FAIL） | `store.py::init_db/open_db`（9表DDL＋`ux_auto_processing_run`逐字＋`ux_candidate_provisional_active`三活跃态＋`require_lock`）；QA：P0-1-DDL/WAL-FK/两处LockNotHeldError全过；独立抽验：results.json三键pass=true＋happy库9表可开 | 可证明 |
| P0-2 | Candidate生命周期可证明（主链4态＋旁路3态，禁ASR调用） | `candidate.py::discover`（DISCOVERED→WAITING→IDENTIFYING→PROMOTED＋MERGED/REJECTED/SOURCE_MISSING）；QA：WAITING/REJECTED/MISSING/PROMOTED/重发现MERGED＋全文无whisper字样全过；results.json 6键全true | 可证明 |
| P0-3 | 活跃期Partial UNIQUE＋Case13历史碰撞建新（吞掉即FAIL） | DDL `WHERE status IN (三活跃态)`；`source.py` Strong SHA256 promotion；QA P0-3：改bytes保size+mtime→新PROMOTED＋新source_id＋nsrc=2旧保留；results.json pass=true | 可证明 |
| P0-4 | Logical Source Exactly Once（content+logical双UNIQUE，path原样存，dup=0） | `source.py::upsert_source`（logical_source_identity UNIQUE＋UPSERT收口）；QA P0-4：`测试 中文丨Case (A).bin`逐字节原样＋重发现MERGED＋nsrc=1＋dup=0 | 可证明 |
| P0-5 | AUTO Run Partial UNIQUE逐字＋冲突安全创建（禁SELECT-then-INSERT） | `runs.py::get_or_create_auto_run`（`ON CONFLICT … DO NOTHING`原子单语句，SELECT只在INSERT后取行返显；MANUAL抛NotImplementedError）；QA：同hash同run＋异hash第二run＋SQL审计全过 | 可证明 |
| P0-6 | 两层去重（Triple Race 1/1＋NO_SPEECH×10 Count=1＋RETRYABLE原Run retry+1） | 装配：Candidate层MERGED＋Run层返既有＋`reconcile_*`；QA：三线程真并发Source=1/Run=1＋×10同run_id＋retry 0→1无新Run；results.json三键true | 可证明 |
| P0-7 | Single Instance（flock＋exit 3零写盘＋启动5步有序） | `instance.py`（`fcntl.flock LOCK_EX\|LOCK_NB`于`data/.lock`＋第二实例exit 3＋startup五步）；QA：exit 3＋mtime不变＋flock运行时断言＋HAPPY-ORDER五步逐字一致 | 可证明 |
| P0-8 | 异常全覆盖可复现（6异常任一缺失即不闭环，合成副本） | QA 6异常全过：Triple Race/Case13/NO_SPEECH×10/RETRYABLE/第二实例互斥/iCloud-BLOCK（＋无锁exit 1附带）；results.json对应键全true；输入全在仓库外data_root，无真实目录触碰 | 可证明 |

## 2. §72子集门12断言（PLAN In Scope §44，QA §4逐项）

| §72子集 | QA | 产品抽验 |
|---|---|---|
| Candidate Partial UNIQUE | ☑ DDL逐字＋MERGED收口 | ☑ results P0-1-DDL＋P0-2-REDISCOVER-MERGED true |
| Historical Provisional Collision | ☑ 新Source=2旧保留 | ☑ P0-3-CASE13 true |
| Logical Source Exactly Once | ☑ P0-4 | ☑ P0-4-EXACTLY-ONCE true |
| Triple Discovery Race | ☑ Source=1/Run=1 | ☑ P0-6-TRIPLE-RACE true |
| AUTO Run Partial UNIQUE implementation | ☑ 逐字索引＋原子UPSERT审计 | ☑ P0-5-UPSERT-AUDIT true |
| Watchdog＋Scan＋Reconciliation AUTO Count=1 | ☑ 三线程直调discover()模拟（PLAN明示不起线程） | ☑ 同上（范围声明一致，非偷换） |
| NO_SPEECH×10 Count=1 | ☑ 同一run_id | ☑ P0-6-NOSPEECH-x10 true |
| FAILED_RETRYABLE重试原Run | ☑ 同run_id retry+1 | ☑ P0-6-RETRYABLE true |
| Single Instance | ☑ exit 3＋mtime不变 | ☑ P0-7-SECOND-INSTANCE true |
| iCloud Root Block | ☑ exit 2＋BLOCK码 | ☑ P0-8-ICLOUD-BLOCK true |
| Duplicate Logical Source=0 | ☑ dup查询0行 | ☑ P0-4-EXACTLY-ONCE dup=0 |
| Duplicate AUTO Run=0 | ☑ 全库同三元组无重复 | ☑ Triple/×10双反证一致 |

## 3. U-1~U-6接受为非阻塞的理由（＋U-7）

- U-1（合成副本非真实长视频）：接受。PLAN Out of Scope第57行明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage身份门只认path/size/mtime/SHA256，不认音视频语义；Case13恰恰只能用合成字节精确构造（保size+mtime改bytes），真实视频造不出。延续债：产品完成后再补真实长视频一遍，不断言本Stage门。
- U-2（三线程模拟非真实三路）：接受。PLAN Out of Scope明示本Stage“三路发现只是同进程/多线程直接调discover() API的并发模拟，不起watchdog线程、不扫真实Input目录”；QA如实声明未起线程，无冒充。真实Watchdog/Scan/Reconciliation实现留Stage5。
- U-3（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s2t07_qa_run.py`＋结果`/tmp/s2t07_qa/s2t07_results.json`已记录，本轮product已复读27键全true，可复算。建议HANDOFF记一笔路径。
- U-4（残留待清）：接受。H5“暂不清”延续；残留全在`/tmp`测试区（本轮约1.9M＋Stage1旧账），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-5（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1功能回归（ingest→verify→桩→post→prepare→commit全PASS）证明`src/stage1/`行为未被破坏，且QA声明未触碰业务代码。建议进git后恢复diff硬门。
- U-6（MANUAL预留＋只测iCloud）：接受。PLAN S2-T04明示MANUAL_REPROCESS只做模型预留不实现语义，抛NotImplementedError即正确行为；PLAN P0-8异常只要求iCloud-Remote Root BLOCK（Case 11），NETWORK/Remote侧与iCloud共用`probe_volume`门，覆盖声明一致。
- U-7（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。SQL审计（SELECT-then-INSERT）与DDL逐字（Partial范围）两处正是code-reviewer主责，建议supervisor复检时点名补审这两处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑discover→PROMOTED→Source=1→Run=1，不断言速度只断言身份Count；机器时间分钟级＋人工<15min。
- 清理（U-4）：neat-freak顺手清`/tmp/s2t07_qa`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，<15min人工。
- 归档（U-3）：HANDOFF记一笔`/tmp/s2t07_qa_run.py`＋`s2t07_results.json`路径（或拷进docs/qa备注外置原因），<5min。
- 流程确认（U-7）：supervisor确认Stage2 code-reviewer是否补审（重点：DDL两Partial逐字＋UPSERT原子性），非P0，不卡本PASS。

---
目标：Stage2闭环产品验收｜剩 P0：无（P0 Blocking以STAGE2-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
