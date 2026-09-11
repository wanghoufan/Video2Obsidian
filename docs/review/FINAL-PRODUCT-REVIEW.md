# PRODUCT BACKLOG｜FINAL（产品完成验收，V1.8 §69 Stage0-12全链）

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| F-1 | V1.8 §69 Stage0-12全链可证明（Stage0基准＋Stage1~12各P0全过＋全链12段回归过） | P0 | 否 | STAGE0~12-PLAN/QA-REPORT/PRODUCT-REVIEW＋FINAL-REGRESSION §4 | CLOSED |
| F-2 | §72全量子集门88断言复述齐（9+12+9+7+10+9+5+5+7+8+6+1=88，各Stage QA §4逐项） | P0 | 否 | FINAL-REGRESSION §5＋各STAGE*-QA-REPORT §4 | CLOSED |
| F-3 | FINAL-REGRESSION 19/19 PASS（Runner exit 0；坏例只看exit码：space/wrongdir/stopscan/across exit 1、noclobber exit 2；Whisper恒0；最大合成12288B门内） | P0 | 否 | FINAL-REGRESSION-REPORT＋/tmp/finalqa/finalqa_results.json | CLOSED |
| F-4 | P1×5全CLOSED且终验重过（S3-P1-1中途RENDERING续行／S3-P1-2诱饵后建verdict稳定／S5-P1-1 stop后隐式scan拒收／S6-P1-1首尾空格BLOCK／S6-P1-2错目录必raise） | P1 | 否 | STAGE3/5/6-CODE-REVIEW P1 CLOSED复核＋FINAL-REGRESSION §1/§3 | CLOSED |
| F-5 | A-cross正式例已补且过（强制跨盘分支＋tmp提交后改源一字节→拒删源ArchiveError＋源留新字节＋Final留旧字节；in-process＋--bad across exit 1双证据） | P1 | 否 | STAGE10-CODE-REVIEW P1-1 CLOSED＋FINAL-REGRESSION §2 | CLOSED |
| U-1 | 真实长视频未测（终验最大合成12288B，S11套件内最大2816B，S12为0B纯合成行；文本/ASR内容不断言；用户明确延续为已知限制） | P2 | 否（已知限制延续，不卡完成） | FINAL-REGRESSION U-1＋各Stage U-1（S0~S12一贯口径） | OPEN |
| U-2 | 文本/词准确率/Golden/CER/幻觉指标Out（PLAN已定；只验哈希/计数/verdict/顺序/exit码/只读） | P3 | 否 | FINAL-REGRESSION U-8＋各Stage U-2 | OPEN |
| U-3 | Runner/证据在仓库外（/tmp/finalqa＋/tmp/finalqa_run.py＋各Stage外置s*qa-*目录；H2外置目录约束延续；复现找QA要路径） | P3 | 否 | FINAL-REGRESSION U-2/U-3＋S12 U-4 | OPEN |
| U-4 | git diff口径N/A（当前目录非git仓库；以全链PASS＋QA零改＋三rg零命中代证；进git后恢复硬门） | P3 | 否 | FINAL-REGRESSION U-4＋S10/S11/S12 U-5 | OPEN |
| U-5 | A-cross为单盘强制跨盘分支模拟（本机单盘无第二device；同盘A为真link路径；需真双盘可挂卷重跑） | P3 | 否 | FINAL-REGRESSION U-5（同S10 U-6） | OPEN |
| U-6 | Stage0笔误/artifact/残留旧账（B档Peak誊写、T09-C3 Peak誊写、tokenizer独立artifact、41MB wav清理；结论不受影响） | P3 | 否 | STAGE0-PRODUCT-REVIEW U-1~U-4 | OPEN |
| U-7 | HANDOFF滞后（根HANDOFF仍停Stage2 CLOSED，未登记Stage3~12计数基线；终验以src/stage*/落盘＋各PLAN/QA为准独立覆盖，不卡QA/产品结论） | P3 | 否 | FINAL-REGRESSION U-7＋S12 U-7 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：产品完成PASS（无P0 Blocking）

- 被验：`docs/pm/STAGE0~12-PLAN.md`（各§Stage P0＝验收唯一口径）＋`docs/qa/STAGE0~12-QA-REPORT.md`（13份全PASS：S0基准PASS／S1 39／S2 27／S3 39／S4 107／S5 56／S6 97／S7 115／S8 113／S9 65／S10 64／S11 11/11／S12快照复算PASS，坏例只看exit码）＋`docs/review/STAGE0~12-PRODUCT-REVIEW.md`（13份全PASS，无P0 Blocking）＋`docs/review/STAGE0~12-CODE-REVIEW.md`（P1全CLOSED：S3×2、S5×1、S6×2、S10×1、S11×5；S12无P1）＋`docs/qa/FINAL-REGRESSION-REPORT.md`（PASS：19/19一轮全绿）＋`src/stage1/`~`src/stage12/`（业务零改终验，十二目录齐）。
- 用户只关心五句话：从头到尾能不能转——能（Stage1 ingest→prepare→commit→Stage2发现→Stage3双revision→Stage4发布→Stage5常驻→Stage6镜像→Stage7词/提示→Stage8切分→Stage9改写→Stage10归档→Stage11自愈→Stage12只读快照，终验全链12段一致）；修过的5个硬 bug 有没有真修——修了（中途崩溃可续行／诱饵增删verdict不翻转／stop后scan拒收／空格路径拒收／错目录必raise，终验真路径重过）；跨盘搬运会不会丢源——不会（删源前源复验正式例：源变即拒删源保留，exit 1双证据）；旧功能有没有被碰坏——没有（终验业务零改＋回归十二import＋诱饵/Archive/真实库零触碰＋Whisper恒0）；长视频有没有测——没有（用户明确：真实长视频一律不测直到产品完成，最大合成12288B门内，文本内容不断言，转已知限制延续，不卡完成）。
- 打回条件均未触发：任一Stage P0不可证明即打回——Stage0降级GO放行（21.7min＋66min累计零异常，Q5/Q6补测债记账不清零不卡Stage1，见经验2026-09-11）＋Stage1~12 P0-1~P0-N全部有代码＋Count/exit码/mtime三证据；P1×5任一未CLOSED即打回——5项code-reviewer已CLOSED＋终验§1重过；A-cross未补即打回——§2正式例过；§72合计88任一对不上即打回——9+12+9+7+10+9+5+5+7+8+6+1=88逐项复述齐；终验19/19任一FAIL即打回——TOTAL 19/19 FAILS=[] exit 0；真实目录/真实库/真实Archive/真实LaunchAgents/云/LLM/`enable`/长视频任一触碰即打回——终验真实长视频零触碰＋三零（archive/Whisper/Overwrite按段披露为0）成立；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。
- 差哪（非阻塞延续）：U-1真实一遍产品完成后补（拿1个真实视频走快照→CLI→菜单，不断言准确率只断言counts/顺序/exit/只读）；U-3残留交neat-freak收尾（/tmp/finalqa＋各s*qa-*，删前确认结论已进报告）；U-6 Stage0笔误/artifact顺手修（<15min人工）；U-7 HANDOFF补记Stage3~12链状态交TM/supervisor。

---
目标：产品完成验收｜剩 P0：无（产品完成PASS，无P0 Blocking；U-1~U-7为已知限制/收尾债）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
