
# PRODUCT BACKLOG

| Item | Task | Priority | Stage P0 Blocking? | Source | Status |
|---|---|---:|---|---|---|
| U-1 | 真实长视频未测（本轮最大合成~1KB；PLAN已定真实长视频一律不测直到产品完成） | P2 | 否（转延续债，不卡Stage6闭环） | STAGE6-QA-REPORT §未闭环U-1 | OPEN |
| U-2 | Runner脚本归档（`/tmp/s6qa_run.py`＋`--bad escape/escape2/parentblock/race/useredit/caseblock`六子进程在仓库外，复现找QA要路径；H2外置约束延续） | P3 | 否（路径已记录，可复算） | STAGE6-QA-REPORT §未闭环U-2 | OPEN |
| U-3 | 残留清理（`/tmp/s6qa` 17三Root＋`/tmp/s6self`＋Stage5/4/3/2/1旧账＋$TMPDIR，交neat-freak收尾） | P3 | 否（全在/tmp测试区，仓库内零污染） | STAGE6-QA-REPORT §未闭环U-3 | OPEN |
| U-4 | `src/stage1/`~`src/stage5/` git diff口径N/A（当前目录非git仓库；以五回归PASS＋QA零改代证） | P3 | 否（代证成立，不卡门） | STAGE6-QA-REPORT §未闭环U-4 | OPEN |
| U-5 | 三表口径说明（纯矩阵库恒0/0/0；集成库happy/a4/a7/a8/reg_s3为1/1/0系QA脚手架经Stage3公开API合成Rendered所致，archive全库0） | P3 | 否（口径与builder自验一致，不卡门） | STAGE6-QA-REPORT §未闭环U-5 | OPEN |
| U-6 | 同实体跨路径语义（硬链接跨路径按§22字符串身份另mint系设计；A3以helper真＋同路径MERGED＋计数不变举证） | P3 | 否（设计内，不在Stage6范围） | STAGE6-QA-REPORT §未闭环U-6 | OPEN |
| U-7 | Stage6无独立code-reviewer报告（本窗口product验时docs/review下仅STAGE0~5-CODE-REVIEW；按AGENTS不可跳code-reviewer，需supervisor复检前确认） | P2 | 否（流程项，非STAGE6-PLAN §Stage P0） | product-reviewer独立发现 | OPEN |

> Product / Visual 问题是否立即修，由 Task Manager 判定是否阻塞 P0（P0 定义见 PLAN.template.md Stage P0 节）。

## 产品验收结论：PASS（Stage6闭环，P0-1~P0-7可证明，Unicode/Case矩阵＋Mirror×No-Clobber可证明，无P0 Blocking）

- 被验：`docs/pm/STAGE6-PLAN.md`（§Stage P0＝验收唯一口径）＋`docs/qa/STAGE6-QA-REPORT.md`（PASS，happy 1遍＋异常8个＋回归五行，97/97双轮exit 0，坏例只看exit码）＋`src/stage6/`（mirror.py/unicode_cases.py/__init__.py共3文件）＋QA证据`/tmp/s6qa/s6qa_results.json`（product已复读：`total=97 passed=97 failed=0 fails=[]`）＋Runner`/tmp/s6qa_run.py`＋六坏例子进程（escape/escape2/parentblock exit 1，race/useredit/caseblock exit 2）。
- 用户只关心六句话：目录长什么样、笔记就长什么样——是（HAPPY三层`AI/博主A/系列1/DeepSeek V4 分析.mp4→…/DeepSeek V4 分析.md`完整镜像，父目录自建，hash三方一致`pub_38368ece3683`）；中文/空格/`丨`/括号/大小写会不会被“智能”改掉——不会（11项MATRIX逐字节保留，`assert_byte_preserved`全链过，归一化grep零命中）；长得像的两个文件（NFC/NFD、`Clip/clip`）会不会被吞成一个——不会（各建各的Source=2，吞并即FAIL项未触发，同ino仍2 Logical按§23字符串身份裁决）；已经存在的笔记/用户改过的笔记会不会被覆盖——不会（同内容重发＋用户编辑＋抢建＋大小写碰撞一律BLOCK，诱饵字节不变，Overwrite=0，writes=0）；路径逃逸/父目录挡路会不会乱写到真实库——不会（越界双例`MirrorEscapeError` exit 1，挡路`MirrorBlockedError` exit 1，全输出前缀恒为诱饵Root）；旧地基有没有被动——没有（Stage1门/Stage2链/Stage3 verdict/Stage4旧库PUBLISHED/Stage5十一步五回归全PASS，archive全库0，Whisper恒0）。另加一句定心丸：真实长视频一律没测（最大合成~1KB，≤32768门），延续到产品完成。
- 打回条件均未触发：P0-1~P0-7任一项不可证明即打回——本轮7项全部有代码＋Count/exit码双证据；三表异常新增写即打回——纯矩阵库0/0/0，集成库1/1/0系脚手架预期且archive恒0＋sources列级不变；出现归一化/Whisper/force后门/Stage7+关键词即打回——product独立三重`rg` RC=1三空已确认；结论写进HANDOFF代报告即打回——结论只落QA报告＋本报告，HANDOFF只记状态。

## 1. P0-1~P0-7可证明逐项（口径=STAGE6-PLAN §Stage P0）

| P0 | 要求一句话 | 证据（代码＋QA＋独立抽验） | 结论 |
|---|---|---|---|
| P0-1 | Path Mirror纯映射可证明（三层＋大写后缀＋中间点号＋越界BLOCK＋零写盘＋Stage4口径一致） | `mirror.py::resolve_canonical`（relpath＋逃逸抛错＋仅末尾后缀strip复`VIDEO_SUFFIXES`＋commonpath复检）；QA：三层`A/B/C`＋`.MP4`＋`my.clip.v2`＋越界双例＋双算一致＋resolve体写盘grep空；独立抽验：5映射全OK＋越界双BLOCK＋与Stage4口径一致项已复跑 | 可证明 |
| P0-2 | Unicode/Case原样保留可证明（中文/空格/`丨`/括号/大小写逐字节＋禁归一化） | `unicode_cases.py::MATRIX` 11项＋`assert_byte_preserved`；QA：空格/`丨`/括号双PROMOTED＋byte preserved；独立抽验：`MATRIX n=11`＋`café`/NFD/`Clip`/`clip`四项byte OK＋`rg quote/slug/casefold/normalize` RC=1空 | 可证明 |
| P0-3 | Case 14故障矩阵可证明（NFC/NFD分Source＋大小写分Source＋同实体识别＋不敏感冲突BLOCK＋特殊字符happy） | `entity_key/is_same_entity`（st_dev+st_ino）；QA：A1双Source（同ino仍2）＋A2双Source（同ino仍2）＋A3 helper真＋同路径MERGED 1→1＋A4 `case_sensitive==False`第二个BLOCK exit 2＋空格`丨`括号happy；独立抽验：STOP grep空＋QA results 97/97已复读 | 可证明 |
| P0-4 | Mirror×No-Clobber集成可证明（父目录自建＋首发PUBLISHED＋三类BLOCK＋Overwrite=0） | `__init__.py::publish_mirrored`（算路径→复检→建父→透传`initial_publish`，不复制commit）；QA：HAPPY PUBLISHED三方hash＋父自建＋同内容重发BLOCK＋A7用户编辑BLOCK（exit 2，字节不变）＋A8抢建BLOCK（exit 2，racer保留）＋A4大小写BLOCK（exit 2）；独立抽验：parent挡路BLOCK已复跑 | 可证明 |
| P0-5 | §72/§73子集门可证明（Stage6 9断言＋Case 14） | 见§2表；QA §4十项全☑；独立抽验：results `passed=97 fails=[]`已复读 | 可证明 |
| P0-6 | STOP EXPANSION门可证明（五目录不动＋三表/archive恒0＋无越权import＋只落诱饵Root） | QA：grep五重空＋archive全库0＋三Root前缀＋Whisper 0＋五回归PASS；独立抽验：三重`rg`（归一/Whisper/force＋resolve写盘＋Stage7关键词）RC=1三空；`src/stage1-5/`未触碰（非git仓库N/A，见U-4） | 可证明 |
| P0-7 | 外置合成验收门可证明（三Root＋合成副本＋真实长视频零触碰） | QA：全用例在`/tmp/s6qa`内＋最大1042B≤32768门＋真实库零触碰；独立抽验：`/tmp/s6qa` 17三Root在盘＋results `total=97`已复读＋本轮product自验另起`/tmp/s6pv_*`合成目录、仓库内零写盘除本报告 | 可证明 |

## 2. §72/§73子集门9断言＋Case 14（PLAN P0-5，QA §4逐项）

| §72/§73子集 | QA | 产品抽验 |
|---|---|---|
| Atomic No-Clobber（mirror嵌套仍PASS） | ☑ HAPPY link(2)＋三方hash＋A8 tmp-only碰撞原地BLOCK | ☑ results `happy.published`＋`happy.hash` ok（97项内，已复读total/passed） |
| Output Race（mirror路径抢建仍BLOCK） | ☑ A8 hook抢建→BLOCK＋抢建字节不变＋exit 2 | ☑ results `bad_race exit 2`口径＋`a8_race`三Root在盘 |
| Unknown/User-edited Overwrite=0 | ☑ A7一字节编辑→CONFLICT＋用户字节保留＋exit 2 | ☑ results内useredit项ok＋`a7_useredit`在盘 |
| Initial Publish（嵌套首发） | ☑ HAPPY PENDING→PUBLISHING→PUBLISHED＋九字段＋published_at | ☑ results `happy.published` ok |
| Subsequent不自动覆盖 | ☑ 同内容重发BLOCK＋A4大小写碰撞BLOCK零写盘 | ☑ results内BLOCK项ok |
| PENDING_PUBLISH | ☑ HAPPY缺席分支＋REG-S3 verdict双值域 | ☑ results `reg_s3`项ok |
| CANONICAL_OUTPUT_EXISTS | ☑ 存在分支走BLOCK，initial_publish零写盘已验 | ☑ 同上BLOCK三用例 |
| §73-34（完整镜像原目录） | ☑ 三层`AI/博主A/系列1/…`逐级保留 | ☑ product独立复跑`AI/博主A/DeepSeek V4 分析.mp4→.md` OK |
| §73-35（原样保留） | ☑ 博主A/空格/`丨`/括号逐字节 | ☑ product独立复跑`测试 中文丨Case (A).mp4→.md` OK |
| Case 14（NFC/NFD/大小写/同实体真机） | ☑ 双Source＋helper真＋不敏感BLOCK＋特殊字符happy，st_ino举证 | ☑ product独立复跑byte四项OK＋`MATRIX n=11` |

## 3. U-1~U-6接受为非阻塞的理由（＋U-7；长视频不测延续）

- U-1（合成小文件非真实长视频）：接受。PLAN Out of Scope第77行明示“真实长视频一律不测直到产品完成（用户明确）”；本Stage只断言路径映射/身份/冲突分支（Count/dup/exit码/hash/字节），不认音视频语义；NFC/NFD、大小写碰撞、Output Race抢建恰恰只能用合成字节精确构造，真实视频造不出门内竞态。延续债：产品完成后再拿1个真实视频走放盘→discover→mirror→诱饵PUBLISHED一遍，不断言速度只断言rel/canonical逐字节＋Source/Run=1。长视频不测延续。
- U-2（runner外置）：接受。H2外置测试目录约束延续（仓库内零写盘除报告）；路径`/tmp/s6qa_run.py`＋六坏例（escape/escape2/parentblock/race/useredit/caseblock）＋结果`/tmp/s6qa/s6qa_results.json`已记录，本轮product已复读`97/97 fails=[]`，可复算。建议HANDOFF记一笔路径。
- U-3（残留待清）：接受。残留全在`/tmp`测试区（本轮`/tmp/s6qa` 17三Root＋`/tmp/s6self`＋Stage5/4/3/2/1旧账＋$TMPDIR），仓库内无污染；交neat-freak收尾，不影响门结论。
- U-4（git diff口径N/A）：接受。当前目录非git仓库，无diff可跑；代证成立——Stage1门反证＋Stage2五步链＋Stage3 verdict＋Stage4旧库PUBLISHED行＋Stage5十一步五回归全PASS＋QA零改声明（业务代码零改，仅新增QA报告；本轮product亦只写本报告）；建议进git后恢复diff硬门。
- U-5（三表1/1/0口径）：接受。纯映射/矩阵库恒0/0/0；集成库（happy/a4/a7/a8/reg_s3）norm/render各1系QA脚手架经Stage3公开API合成Rendered Final所致（不绕门），非Stage6代码新增写（grep反证＋archive全库0＋sources列级不变）；若按字面“恒0”卡集成库则无Rendered可发布，QA按builder自验同一口径（66例）验收，product认同。
- U-6（跨路径硬链接另mint）：接受。按§22字符串身份（path|content）另mint不同Logical系设计；A3以helper真＋同路径MERGED＋计数1→1举证同实体识别已闭环；跨路径去重不在Stage6范围内，不卡门。
- U-7（缺code-reviewer报告）：非阻塞但需supervisor复检前确认。按AGENTS不可跳code-reviewer＋qa＋supervisor；本轮qa PASS＋product PASS齐了，只差reviewer一环。Mirror纯函数零写盘审计（resolve体内open/write/mkdir/link）与集成透传审计（不复制No-Clobber/commit、无force后门）两处正是code-reviewer主责，建议supervisor复检时点名补审这两处，不返工产品结论。

## 4. 差哪清单（用户版：缺什么、补多久）

- 真实一遍（U-1延续）：产品完成后拿1个真实视频跑放盘→discover→mirror→诱饵PUBLISHED，不断言速度只断言逐字节＋Source/Run；机器时间分钟级＋人工＜15min。
- 清理（U-3）：neat-freak顺手清`/tmp/s6qa`＋`/tmp/s6self`（删前确认results.json结论已进报告，本报告已复读备份）＋旧账，＜15min人工。
- 归档（U-2）：HANDOFF记一笔`/tmp/s6qa_run.py`＋`s6qa_results.json`＋六坏例（escape/escape2/parentblock/race/useredit/caseblock）路径（或拷进docs/qa备注外置原因），＜5min。
- 流程确认（U-7）：supervisor确认Stage6 code-reviewer是否补审（重点：resolve零写盘＋透传无自有commit＋无force后门＋归一化零命中），非P0，不卡本PASS。

---
目标：Stage6闭环产品验收｜剩 P0：无（P0 Blocking以STAGE6-PLAN §Stage P0为准，本轮零阻塞）｜下一步：交supervisor复检（结论只落本报告，HANDOFF只记状态）。
