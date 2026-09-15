# BUGS

## 结论

**PASS（无本任务新增 P0/P1/P2；DoD 1–5 均通过；真机 UI 未验证）。**

本报告只做代码级 QA，未改业务代码、测试代码或其他 docs；未启动 8765，未访问或写入用户真实视频目录、Obsidian 库。

## 七查证据

| 检查 | 结论 | 命令与 rc |
|---|---|---|
| unit | 过 | `python3 tests/selftest_p1_2_contract.py` → `SELFTEST ALL PASS（479 项断言）`，rc=0。独立后端合成夹具＋独立前端直抽源码探针均 PASS，rc=0。 |
| build | 过（脚本级） | `PYTHONPYCACHEPREFIX=/tmp/p14-pycache python3 -m compileall -q app`，rc=0；仓库未发现独立前端构建配置。 |
| lint | 未覆盖 | 未发现可用 lint 配置/命令；`git diff --check` 无输出，rc=0，不能据此宣称 lint 通过。 |
| API | 过 | 独立合成 SQLite 调 `_handle_failure_diagnosis`，rc=0；随机端口 `ThreadingHTTPServer` 真请求 `/api/failures/diagnosis`，端口 63717（`!=8765`），HTTP 200，shutdown/close 完成，rc=0。 |
| logs | 过（本任务输出面） | 独立扫描复制正文、详情证据、逐条面板和诊断 JSON，未发现 `/Users/`、`/Volumes/`、`/var/`、`/private/`；无新增导出路径。HTTP 访问日志会按标准 access log 记录测试请求 URL 中的 tmp `data_root`，不属于复制/页面/诊断响应泄漏。 |
| regression | 过 | `python3 tests/selftest_p1_2_frontend.py` → `FRONT ALL PASS` / `FRONT SELFTEST PASS`，rc=0；`python3 tests/selftest_v26_presets.py` → `SELFTEST ALL PASS`，rc=0。 |
| DoD | 过 | 下表逐条覆盖；默认浅色、`say()` 120 字、D-12、No-Clobber、词库三铁律与 P1-3 语义均未回退。 |

## 独立坏例与重点复验

所有 handler 夹具首行均执行 `data_root` 在系统 tmp 下的断言；测试数据为外置 tmp 合成数据。

1. 自造绝对路径与替代路径：手工建 SQLite，登记路径为 `/Users/zzymima0000/需转录视频/sample.mp4`，实际同身份替代文件在 tmp；后端返回 `identity_match=MATCH` 且 `alternate_path_redacted` 脱敏。独立扫描器逐字扫描诊断 JSON、复制正文、详情证据、逐条面板，四类绝对路径模式均为零。独立后端探针 rc=0。
2. 白名单强制：独立 Node 桩向诊断 item 注入 `transcript`、`note_body`、`token`、`request_body`；复制正文不出现任一字段值，且仅保留 `label,tail,code,category,confidence,missing,next`。独立前端直抽源码探针 rc=0。
3. 长文本不入状态行：复制完成后只检查 `#msg` 短句，不出现 `错误码：` 等整篇摘要内容；通过。仓内前端自测亦覆盖 `10a/10d`，rc=0。
4. 降级脱敏：非法相对目录／诊断不可用时，复制正文包含 `未提供（诊断不可用）`，不留空；建议中的深层 `/Users/...` 也被抹除。通过。
5. A→B 迟到响应：仓内前端坏例 `10f/10f2` 独立覆盖「A 请求在飞→切 B（含刷新与不刷新）→放行 A」，断言 B 保留且 A 不得写入 B 缓存；前端自测 rc=0。源码 `loadDiag` 的 box 认领保护在 `app/index.html:1299-1326`。
6. 真 HTTP：随机端口 HTTP 访问 `/api/failures/diagnosis`，响应 200；端口断言 `!=8765`，结束后 `shutdown()`、`server_close()`、线程 join，rc=0。
7. alternate_path_redacted 真分支：后端合成夹具未创建登记文件、只在 tmp 替代目录放同 basename 且 size/mtime/hash 匹配，命中 `identity_match=MATCH`；前端自测 `10g/11i` 另覆盖异常回包中的替代路径脱敏，rc=0。

本轮独立探针早期两次 rc=1 均为 QA 手写夹具错误（SQLite 占位符数量、Node response/Promise 桩类型），未执行到业务断言；修正后最终独立后端、真 HTTP、前端直抽源码探针均 rc=0，未将夹具错误计为 BUG。

## BUG 清单

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注 |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | — | 本任务未发现新增 BUG | DEVELOP-P1-4 | 前置 code review 已确认 P2-1/P2-2 闭环；本轮未复开。 |

## DoD 覆盖表

| DoD | 结论 | 证据行号／复验 |
|---|---|---|
| 1. 一键复制只含允许字段 | 过 | `app/index.html:1249` 白名单；`:1281-1284` 唯一 `digestEntry` 出口；`:1353-1365` 摘要渲染；`:1415-1425` 唯一复制出口。合同/前端自测 rc=0；独立注入额外字段探针 rc=0。 |
| 2. 绝不含绝对路径、正文、笔记、密钥、请求体 | 过 | 后端 `_strip_paths` `app/server.py:354-378`；诊断项 `:1636` 替代路径脱敏；前端 `app/index.html:1253-1278`、`:1373-1387`。独立扫描复制正文、详情、面板、JSON 均零命中。 |
| 3. 页面可看逐条本地证据 | 过 | 详情内联块 `app/index.html:735-736`、挂载 `:757`；`renderDiagEvidence` `:1403-1412`；`showFailEvidence` `:1430-1436`；证据组装 `:1368-1392`。前端自测 `10c/10g/11i` rc=0。 |
| 4. 不弹成功 toast 洪水 | 过 | `say()` `app/index.html:1038` 截断 120 字；复制成功用短句 `:1423`，长文只放可关闭面板参数 `:1424`。前端自测 10a/10d 与独立状态行探针通过。 |
| 5. 不提供完整绝对路径导出、不新增导出按钮 | 过 | 仅新增复制与本地证据按钮 `app/index.html:608-609`；无 export 导出入口；静态检查 rc=0。 |

## 前序成果无回退

- 默认浅色：`app/index.html:2` 为 `<html lang="zh-CN" data-theme="light">`。
- D-12：`app/server.py:354` `_strip_paths` 保留；异常路径不直接回传。
- No-Clobber、词库三铁律 58 项、P1-3 五桶同源／锁定提示／无目标不画 100%：三套基线自测全 rc=0。
- 未新增导出按钮，未改主题、词库或真实数据目录。

## 未覆盖项

- 真机能力预检、Canary、读屏、截图、点击、输入、滚动、像素 UI 目检：**NOT_VERIFIED**；本会话无可用原生桌面读屏/截图/点击能力，未启动 8765，未编造 UI 证据。
- lint：无可执行项目 lint 配置，未覆盖。
- 真实 whisper、真实 16 条视频端到端、长视频耗时与真实 Obsidian 库：未覆盖。
- 多标签真实浏览器并发：未覆盖；A→B 迟到响应使用独立 Node 异步桩及仓内反例验证。

## 真机 QA 会话能力预检结果

- 日期/任务名：2026-09-15 / `DEVELOP-P1-4`「脱敏摘要复制（HD-2=A）」
- session ID：N/A（代码级 QA，未开启真机 session）
- 模型精确 ID：`codex/gpt-5.6-luna`（按 `USER_MODEL_OVERRIDE.md`）
- Runtime：未启动真机 Runtime
- 原生 CUA 是否实际注入：未使用，未验证
- 可用工具：本轮仅使用 shell、Python、Node；无读屏/截图/点击工具
- 读屏／截图／点击／输入／滚动／界面恢复：均未执行
- 最终结论：**NOT_VERIFIED**
- 是否允许进入正式真机 QA：否；仅代码级 QA 结论有效

## Fix Attempt Fingerprint

- Task ID：`DEVELOP-P1-4`
- Root Cause Hypothesis：交付将诊断字段、路径脱敏、降级占位、页面证据与复制出口分离，需验证白名单和目录异步隔离是否真正闭环。
- Approach：三套既有回归；外置 tmp 合成 SQLite；独立绝对路径扫描器；独立 Node 直抽源码探针；随机端口 `ThreadingHTTPServer`；静态行号核对。
- Files Changed：仅新增本报告；未改业务代码、测试代码或其他 docs；未 commit/push。
- Verification：contract 479/rc0；frontend rc0；vocab rc0；compileall rc0；diff-check rc0；独立后端/HTTP/前端探针 rc0；8765 无监听。
- Failure Reason：无产品失败；独立探针早期失败均为 QA 夹具错误，修正后全部通过。
- Difference From Previous Attempt：本任务首次 QA；新增独立真实形态绝对路径、alternate `MATCH` 分支、白名单额外字段、降级占位、状态行和 A→B 迟到响应重点复验。

心跳：目标＝完成 P1-4 代码级 QA｜剩 P0/P1＝无｜下一步＝交 supervisor 复检。

---

---

# supervisor 复检（2026-09-15）｜DEVELOP-P1-4「脱敏摘要复制（HD-2=A）」全链收口

- 复检人：supervisor（`opencode-go/muse-spark-1.3-contributor`，本窗口，按 `USER_MODEL_OVERRIDE.md` 行；角色卡 `docs/roles/supervisor.md`）。
- 范围：**不读报告下结论**——本节的每一条都是我自己跑出来的（实跑 rc、自算 sha256、自写探针、自己造坏例）。**未改业务代码、未改任何报告正文、未 commit/push**；本文件只在尾部追加本节。
- 结论：**PASS｜无 blocking｜本链 supervisor 累计打回 0/2**（链内 0 次 FAIL）。放行收口。
- 基线（动手前我自己复算，与派单书逐字一致）：`app/index.html`=`31e1ea5b…313f`、`app/server.py`=`36d78124…b21f`；`HEAD`=`fa6ba1b`（＝`origin/main`，P1-4 交付**全在工作树、未提交**）。

## 一、实跑三套自测（看 rc，不看打印）

| # | 命令 | 实测结论行 | 断言数（`grep -c '^PASS'`） | rc |
|---|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（479 项断言）` | 479 | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS` | 139 | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | 58 | **0** |

三套数字与派单书（479／139／58）**逐个吻合**；断言计数与 QA 报告一致。另实测：`git diff --check` rc=0；`git diff --numstat`＝`index.html 210/16`、`server.py 3/0`、`contract 197/7`、`frontend 357/2`（4 文件 **+767/−25**），与派单书逐字一致；8765 **无监听**（socket 实测 `ConnectionRefusedError`，且无 `app/server.py` 进程）。

## 二、两道账本校验（exit 码为准）＋坏行负控

按角色卡校验块**整块照粘**（路径照实），只看 exit 码：

- `docs/model/TASK-MODEL-LOG.jsonl`（**51 行**，`_example` 0 行、非空行 51）→ **exit 0**。
- `docs/model/DISPATCH-LOG.jsonl`（**62 行**，`_example` 0 行、非空行 62）→ **exit 0**。

**坏行负控（证明校验器真会 exit 1，不是空转）**——用两账本真行做模板在 `/tmp` 造假行，逐条跑同一校验器：

| 负控样本 | exit | 打印 |
|---|---|---|
| TASK 坏 JSON | **1** | `L1: JSON坏: Expecting property name…` |
| TASK 缺键 `escalated` | **1** | `L1: 缺键 ['escalated']` |
| TASK `result="OK"` | **1** | `L1: result枚举错: OK` |
| TASK `rework=true` | **1** | `L1: rework非int: True` |
| DISPATCH `used="备"` | **1** | `L1: used非常量主: 备` |
| DISPATCH `runtime="codebuddy2"` | **1** | `L1: runtime枚举错: codebuddy2` |
| DISPATCH 缺键 `note` | **1** | `L1: 缺键 ['note']` |
| **正控**：完好单行 | **0** | 无输出 |

7/7 坏行 exit 1、正控 exit 0 → **校验器有牙**（`经验一句话` 2026-09-10 那条：只计算不 exit(1) 的校验等于没验，已照办）。

## 三、三处对账（HANDOFF ↔ DISPATCH-LOG ↔ TASK-MODEL-LOG，逐字对分工表）

- **本链 5 派，逐行核 `role`／`model`／`runtime`／`result`／`used`／`date` 与 `USER_MODEL_OVERRIDE.md` 分工表**：

| # | HANDOFF 执行链 | DISPATCH 行 | role／model／runtime | 判定 |
|---|---|---|---|---|
| 1 | ① builder 交付（PASS） | L58 | builder／`opencode-go/deepseek-v4.1-flash`／本窗口 | **一致** |
| 2 | ② code-reviewer 首轮（PASS） | L59 | code-reviewer／`opencode/muse-spark-1.3-contributor-free`／本窗口 | **一致** |
| 3 | ③ builder 返工 P2-1／P2-2（PASS） | L60 | builder／`opencode-go/deepseek-v4.1-flash`／本窗口 | **一致** |
| 4 | ④ code-reviewer 复核二（PASS） | L61 | code-reviewer／`opencode/muse-spark-1.3-contributor-free`／本窗口 | **一致** |
| 5 | ⑤ qa 独立 QA（PASS） | L62 | qa／`codex/gpt-5.6-luna`／codex | **一致** |

- **TASK-MODEL-LOG L51**（本链任务级 1 行）：`role=builder`／`model=opencode-go/deepseek-v4.1-flash`／`result=PASS`／`rework=0`／`escalated=NO`／`escalation_reason=null`／`tokens=null`／`cost_cny=null` → 与分工表 + 「本链 supervisor 打回 0 次」口径**一致**（`rework` 口径按 HANDOFF 明写：＝supervisor 打回次数）。
- **本链三处对账不匹配项数 ＝ 0**（5 派 × 6 字段 ＋ TASK 行 5 字段，全过）。
- **全文件扩核（额外做）**：DISPATCH 62 行**全量**对分工表，得 **2 行**不符——`L1`（2026-09-13 迁移整理 supervisor＝`deepseek-v4.1-flash`／`codebuddy`）、`L8`（2026-09-14 DEVELOP-P0-1 首版 builder＝`codex/gpt-5.6-luna`／`codex`）。这两行是 **2026-09-14 表换代之前**派出的历史行，HANDOFF「模型通道现状」节已交代（supervisor 与 builder 由用户切为本窗口通道）→ **判「历史行如实反映当时通道」，非本链缺口、不返工**；仅记一笔，TM 可择机在账本首页加一句断代注记（非阻断）。

## 四、DoD 5 条逐条到源码核（不看报告，自己读代码）

| DoD | 判定 | 我自己核到的源码证据 |
|---|---|---|
| ① 只含 7 类允许字段 | **真闭环** | 白名单 `FAIL_DIGEST_FIELDS`（`index.html:1249`）＝`label/tail/code/category/confidence/missing/next`，与 Plan `FR-3`（`PRODUCT_PLAN.md:49`）那 7 类**逐字同序**；唯一构造函数 `digestEntry:1281-1285`（`forEach` 取键，**不可能带第 8 键**）；唯一渲染 `failDigestText:1353-1366`（正文只出现 `f.*` 七变量）；唯一复制出口 `copyAllFailedReasons:1415-1426`→`copyText:1070`。全文件 `copyText(` 调用点 4 处，另 3 处（`:674/:768/:788`）是 diff 未触碰的既有「复制路径」按钮。 |
| ② 绝不含真实绝对路径／正文／密钥／token／请求体 | **真闭环** | 后端：`source_label`＝`os.path.basename(recorded)`（`server.py:1629`）、`recorded_path_redacted`／`alternate_path_redacted` 走 `_diag_redact_path:1428-1433`、新增 `source_dir_tail` 走既有 `_dir_tail:1044-1055`（`server.py:1630-1632`，**本链后端只 +3 行**）、`next_action` 全是 `_diag_action:1552-1577` 里的**硬编码人话常量**（从不回 `row.reason`／异常原文）；前端三层兜底 `redactPathField:1253`／`redactPathTail:1260`／`redactCopyField:1267` 落位。**结构性无出口**：摘要只读诊断 7 键，降级路只读 `failPartsForRun().next`。 |
| ③ 页面可看逐条本地证据 | **真闭环（两入口）** | 详情内联块 `index.html:736`＋`renderDiagEvidence:1403-1413`＋接线 `:757`；全量可关闭面板 `showFailEvidence:1430-1437`＋按钮 `:609`（绑定 `:613`），正文 `evidenceLinesFor:1368-1393`／`failEvidenceText:1394-1399`；降级时 `:1389` 如实写「诊断不可用…不编造」。 |
| ④ 不弹成功 toast 洪水／长文不进状态行 | **真闭环** | `copyText:1070-1096` 的 `done()` 只 `say(shortOk)+toast(shortOk)`；`shortOk`＝`"已复制 N 条脱敏摘要"`（`:1423`）；长文只落 `lastLongText` 并点亮 `btnViewLong`（`:1077-1080`），**不自动开面板**；`say():1038` 仍 `.slice(0,120)`＋3 秒清。 |
| ⑤ 不做全路径导出、不新增导出入口 | **真闭环** | 新增按钮只有 `复制脱敏摘要`（`:608`，替换旧「复制失败原因」文案）与 `查看本地证据（逐条）`（`:609`）；全文 grep `导出全路径/导出完整路径/导出绝对路径/复制完整路径/复制全路径` → **0 命中**。 |

另核：`raw_error_code`＝`row.get("raw_error_code") or "UNKNOWN"`（`server.py:1649`），而 `processing_runs` DDL（`src/stage2/store.py:151-172`）**确实没有该列** → 恒 `UNKNOWN` **属如实、未编造**（符合 FR-1）。

## 五、独立探针（全部自写，落 `/tmp/supP14/`，不入仓；不为复跑仓内自测）

**探针 A｜后端（自建合成 tmp DB → 真实 DDL → 直调真实 handler `_handle_failure_diagnosis`）：`PASS=30 FAIL=0`，rc=0。**
自造 3 条真实形态登记路径：`/Users/zzymima0000/需转录视频/第七周/样例视频.mp4`、`/Volumes/外置盘/暂不转录视频/另一样例.mp4`、`<tmp>/missing_parent/替代样例.mp4`（后者把同 basename／size／mtime／sha256 都匹配的替代文件放进 data_root 下 `_alt/`，让**真扫描器**自己找到 → 真 `MATCH` 分支）。结果：

- 诊断响应 `blob` 对 `/Users/`、`/Volumes/`、`/var/`、`/private/`、`/tmp/`、`/home/` **六个模式全 0 命中**；三条真实登记路径明文**全 0 命中**。
- item 里**没有** `transcript`／`note_body`／`token`／`request_body`／`body`／`text` 任一键（结构性无出口）。
- 替代路径分支**真跑到**：`recorded_path_exists=False`、`identity_match=MATCH`、`action_category=SOURCE_LOCATION_REVIEW`、`confidence=HIGH`、`alternate_path_redacted='…/_alt/第七周/替代样例.mp4'`（`…/` 形态、≠ 真实替代路径明文、整包无明文）；`source_dir_tail='…/missing_parent'`（`…/` 形态，与列表侧同 helper）。
- `raw_error_code` 三条**全 `UNKNOWN`**。tmp 目录 `finally` 已清理（未留痕）。首行即断言 `data_root` 在系统 tmp 下。

**探针 B｜前端（真实后端回包 → 逐字抽 `index.html` 真源码跑 node）：`PASS=43 FAIL=0`，rc=0。**

| 组 | 覆盖 | 结果 |
|---|---|---|
| F1／F2 | ① 真实形态绝对路径：摘要正文与**页面证据**里零绝对路径、零真实登记路径明文、零真实替代路径明文（且确有内容、非空跑，`len=436`） | 10/10 PASS |
| F3／F4 | ② 白名单额外字段注入：键集恰为 7 类、`digestEntry` 输出恰 7 键、注入 `transcript`／`note_body`／`token`／`request_body` **八个值一个都不出现**、摘要长度不因额外字段变长 | 13/13 PASS |
| F5 | ④ 替代路径分支：真跑到（`MATCH`＋非 `UNKNOWN`）、面板里是脱敏形态、零真实明文 | 4/4 PASS |
| F6 | 长文不进状态行：`#msg`＝`"已复制 3 条脱敏摘要"`（≤120 且无 `错误码：`）、剪贴板真拿到摘要正文、**不自动开面板**、剪贴板内容零绝对路径 | 5/5 PASS |
| F8 | ③ **A→B 迟到响应不串味**（用两个真实形态回包 A/B）：换目录+刷新后拿到 B；放行 A 的迟到响应后仍是 `B-ITEM`、快照 id 仍 `diag-B`、缓存 root 仍 `/rootB`、摘要正文**零 A 目录数据** | 5/5 PASS |
| F9 | 防御性反例：后端若日后回**未打码**值，前端兜底仍须抹掉 → 摘要与页面证据仍零绝对路径、零明文 | 3/3 PASS |
| F10 | 降级路（诊断不可用）：摘要零绝对路径、缺失一律写「未提供（诊断不可用）」、不留空、建议仍有人话 | 4/4 PASS |

**探针自身两次假绿，我自己抓出并修掉（留痕，避免后人误读）**：① 首版把 `setTimeout` 桩成「永不回调」→ 事件循环空转、node 在 F6 前就退出（打印 rc=0 却**根本没跑到 F6–F8**）——这正是「rc=0 未必有牙」的活例，改成真定时器（只让 `say()` 的 3 秒清不触发）后才真跑；② 首版夹具把失败行 `status` 写成 `TRANSCRIBE_FAILED`，而 `isFailedRun` 只认 `/^FAILED/` → `failedRuns()` 回空、F6 空跑，改 `FAILED` 后才咬住。**两条都是我自己发现的，不记作交付缺陷。**

## 六、抽检反向证伪（改坏 → 跑 → 记 rc → 字节级还原 → 比对全量 sha256）

动手前**我自己先算基线**（见开头），每次变异前再断言一次基线一致；还原用 `wb` 字节级写回：

| # | 变异 | 仓内 contract | 仓内 frontend | 我方 probe_be | 我方 probe_fe | 还原 sha256 |
|---|---|---|---|---|---|---|
| M1 | 前端白名单**加第 8 键 `reason`** | **1** | **1** | 0 | **1** | 一致 |
| M2 | 前端 `redactPathField` 末 3 段 → **末 4 段** | 0 | **1** | 0 | 0 | 一致 |
| M3 | 前端摘要 `label` **去掉兜底脱敏** | 0 | **1** | 0 | **1** | 一致 |
| M4 | 前端 `mark()` 守卫**只留 root 检查**（删 `diagCache!==box` 半） | 0 | **0** | 0 | 0 | 一致 |
| M5 | 后端 `alternate_path_redacted` **不脱敏** | **1** | 0 | **1** | **1** | 一致 |
| M6 | 后端 `source_dir_tail` **直塞真实目录** | **1** | 0 | **1** | 0 | 一致 |

**结果与判读**：4/6 被至少一路咬住（M1／M3／M5／M6），**6/6 还原后全量 sha256 与自算基线逐字一致**（`31e1ea5b…313f`／`36d78124…b21f`／两测试文件同 baseline，`git status --porcelain` 仍只有那 4 个 `M`）。
- **M4 三方全 rc=0 → 确认复核二的 P3-新1 属实**（`diagCache!==box` 半无断言；缺的反例是「同目录手动刷新＋迟到响应」，仓内 `10f/10f2` 都换了目录，接不住）。**当前代码行为正确**（复核二探针场景 4 已证），纯测试覆盖缺口、**不阻断**，维持 P3 不返工。
- **M2 我方两探针接不住、只有仓内 frontend 咬住**——如实说明：我的探针用「绝对路径形态扫描」，而末 4 段只多带一层账号名、不含 `/Users/`；这一档由仓内 `10b/10g` 的**整条精确串比对**守着（复核二 FA-6 已证）。**口径差异不是缺陷，但我的探针不能替代仓内那两条断言**。

## 七、未修项是否被如实申报

- 首轮 **8×P3（P3-1…P3-8）**与复核二 **5×P3（P3-新1…新5）**在 `docs/review/P1-4-REDACT-DIGEST-CODE-REVIEW.md` 里**逐条在位、无含糊**（我逐条核过：位置、归属、是否仍开都有写）；复核二第五节还逐条给了「仍开／已闭」现状。
- 复核一第七节「咬不住」3 条：⑨⑩**已闭**、⑪**仍开**（＝P3-新2），申报属实（我用 M4/M5 对照与探针活性交叉验证了这批结论的方向）。
- `raw_error_code` 恒 `UNKNOWN`：报告写「表无该列，**如实写未编造**」（review P3-2、builder 自陈 #6、QA DoD 表）→ **与源码一致，不是掩盖**。
- QA 报告的「未覆盖项」（真机 UI `NOT_VERIFIED`、真实 16 条未跑、lint 未覆盖、多标签未覆盖）**如实标注、无一处写成通过**；`_diag_alternate_paths` 的只读全盘扫描（P3-新4）也如实记了。→ **无隐瞒、无虚报。**

## 八、Phase Integrity 五查

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | PLAN 阶段禁 builder／code-reviewer／qa 业务派工 | **过** | DISPATCH 按 `date×role` 分布：2026-09-13（PLAN）只有 planner×4／product-reviewer×2／supervisor×1，**零** builder／code-reviewer／qa。 |
| 2 | WAITING_HUMAN_APPROVAL 禁自动开发 | **过** | 第一条 builder 在 **2026-09-14**（用户当日说「第二阶段，开发」）；此前无任何业务派工。 |
| 3 | DEVELOP 必有 DEV_BASELINE | **过** | `HANDOFF.md:11` `DEV_BASELINE=PRODUCT_PLAN_V1.3`；`:7` `PROJECT_PHASE=DEVELOP`。 |
| 4 | C 类变更禁绕 Controlled Reopen | **过** | `CHANGE_REQUEST=B`。P1-4 **不是**产品/架构变更：`PRODUCT_PLAN.md:49` 的 `FR-3` 原文已逐字写死「一键复制只包含脱敏 source label、目录尾段、错误码、类别、置信度、缺失证据和建议，不含真实绝对路径、转写/笔记正文、密钥或请求体；不弹出成功 toast 洪水」，`:262` 的 `HD-2=A` 写明「页面可看＋一键复制脱敏摘要；不导出完整路径」——本次交付就是这两句的落地（7 类字段与白名单**逐字同序**，见第四节）→ **B 级判定正确，无需 Reopen、无需新版本/新基线**。 |
| 5 | TM 停摆 watchdog | **过** | 本链 5 派连续推进、无停摆；HANDOFF 执行链与状态已回写。 |

## 九、红线抽查

| 项 | 结论 | 证据 |
|---|---|---|
| 不 push／不 commit | **过** | `HEAD`＝`origin/main`＝`fa6ba1b`（P1-3 收口）；P1-4 **全部改动仍在工作树**；`git status --porcelain`＝4 个 `M` ＋ HANDOFF/两账本 `M` ＋ 两份新报告 `??`。 |
| 不碰 secrets | **过** | `git diff -U0` 新增行 × 8 种密钥形态扫描：命中项**全是**注释/测试里的「正文/token/请求体」字样与账本 `task` 字段，**零真实密钥**。 |
| 不改封存件 | **过** | 仓内不存在 V1.10／V2.0 封存文件（规则里提及，实物无）；diff 只含 7 个文件，`008林粒粒AI编程/` **零改动**。 |
| `docs/sop/` 只作模板示例 | **过** | `git diff --name-only` 中 `docs/sop/` **0 条**。 |
| 测试只用外置 tmp ＋ 合成数据 | **过** | `make_data_root` 首行 `assert_tmp`（`selftest_p1_2_contract.py:122-126`）；`build_root_a` 类同理。**调 handler 用例首行断言**：我逐个用例组扫了「首个 handler 调用 vs 首个 `assert_tmp`」，被算法标出的 3 组（`part9`／`part10`／`part12`）**均为误报**——它们首个调用点是 `make_data_root()` 本身，而该函数**第 2 行就 `assert_tmp`**，先于任何 handler 调用。→ **无一组越门**。 |
| 主题默认浅色 | **过** | `index.html:2`＝`<html lang="zh-CN" data-theme="light">`（未动）；contract `8 主题默认浅色未回退` PASS。 |
| **D-12 口径（`_strip_paths`）未被放宽** | **过** | `git diff -U0 app/server.py` 只有**一个 hunk**：`@@ -1629,0 +1630,3 @@`（纯插入 3 行），`_strip_paths:354-374`／`_err_text:377-393`／`_PATH_STOP_CHARS:350-351` **字节未变**；M5/M6 反向证伪中 `_strip_paths` 相关断言未见放松。 |
| No-Clobber | **过** | 本链**未动任何发布/写盘逻辑**（后端只新增一个只读派生字段）。 |
| 词库三铁律 | **过** | `selftest_v26_presets.py` **58/58 rc=0**；`app/presets/vocab/*` **不在 diff** 内。 |
| 服务状态 | **过** | 8765 无监听（socket 实测 `ConnectionRefusedError`；无 `app/server.py` 进程）——**本机服务已停，不影响代码级结论**；真机 UI 仍 `NOT_VERIFIED`（如实，不推断为通过）。 |

## 十、P1-3 已收口语义是否被回退

**未回退，逐条有据**：

- **五桶同源 fail-closed**：`STATE_BUCKET`／`_state_bucket` 在 `app/server.py`——本链后端**只 +3 行且在同一 hunk**，P1-3 判据函数体零接触；contract `10a`／`10a3`／`10a4`／`10a2`／`10b` 全 PASS（含「未知/空 state→failed，缺键仍按 ok 成功」）。
- **运行中锁定提示**：`index.html:239`（`#batchLockHint`）与 `:1553` 文案写入点，**均落在 diff hunk 之外**；contract `10e 锁定检查先于版本锁`／`10e 运行中提交→409 人话（零执行）` PASS。
- **无目标不画 100%**：`renderProgress:832`／`stageStep:824` 落在 hunk 外；contract `10d2 明说「没有可重跑的已完成任务」`＋`10d2 stats.total=0 且五桶之和为 0（不画满的依据）` PASS。
- **elapsed 提示**：contract `10b 长任务 elapsed_seconds 可读（90s）`／`10b 坏/缺时间戳回 0（不编造）` PASS；`vocabApplyElapsedText` 相关断言（frontend 139）全 PASS。
- **diff hunk 全集**（`-U0` 实测）：`88`／`560`／`604`／`607`／`728`／`748`／`1228-1362`／`1241→1365-1436`／`1843→2037`——**P1-3 五个关键函数（`renderProgress`／`stageStep`／`vocabApplyPct`／`vocabApplyLockText`／`#batchLockHint`）一个都不在其中**，与复核二结论**独立吻合**。

## 十一、遗留 backlog（全部非阻断，逐条写明归属）

**P1-4 链——code-reviewer 首轮 8 条（全部仍开）**：P3-1 真 16 条诊断耗时未实测（逐行 2s 预算、前端无超时取消，**QA 亦未实测墙钟**，仍属唯一未取证项）｜P3-2 `raw_error_code` 恒 `UNKNOWN`（表无该列，**如实未编造**；补列属 Change B／Plan 范畴）｜P3-3 前端 `redactPathField`／`redactPathTail` 无 `normpath`、非 `/` 开头原样透传｜P3-4 `REDACT_STOP_CHARS` 缺 ASCII `(` `)`（多吞人话尾句，方向安全）｜P3-5 title 承诺「不含密钥/请求体」实为结构性保证（建议口径写实）｜P3-6 降级提示枚举不完备（404/网络错同句）｜P3-7 `diagCache` 「已查过」哨兵未置位（性质未变、不构成跨目录串味）｜P3-8 P1-7 盘点过期（`V2O` 现 5 处 `:6/:38/:179/:1060/:1064`，HANDOFF 记「4 处」需对齐，**且行号因本轮 +9 再漂**）。
**P1-4 链——复核二新记 5 条（全部非阻断）**：P3-新1 守卫 `diagCache!==box` 半无专项断言（**我用 M4 独立复核：确无牙；行为正确**）｜P3-新2 `evidence_sources`／`evidence_conflicts` 兜底无牙（后端两处均为硬编码中文，**零当前风险**）｜P3-新3 `11i` 无「整条精确值」断言（现由 `11e` 逐字断言兜住）｜P3-新4 `part12` 让自测首次触发只读全盘扫描（合法、有界、零写，但耗时开始依赖用户真实目录规模）｜P3-新5 记账口径（builder 自报增量 vs 实测 stat 对不上，**已由复核二列三条独立证据表明实质无碍**）。
**跨链承继（不在本链修）**：P1-3 `QA-P13-P2-4-REAPPLY-MUTEX`（既有残留）＋ P1-3／P1-2／P0-3 若干 P3／P2；`data/state.db` 真源待核；**真实 whisper／真机 UI／真实 16 条端到端未跑**（各报告已如实标注，不得推断为通过）。

## 十二、两点裁定（TM 明请）

**裁定一｜「跳 planner／product-reviewer」是否合规 → 合规，不予打回。**
理由三条，全部落在 Plan 原文与本次交付的**可逐字比对**上：① P1-4 由 Plan **既有**条目直接定义——`FR-3`（`PRODUCT_PLAN.md:49`）已把摘要允许字段**逐条写死为那 7 类**并写明「不含真实绝对路径、转写/笔记正文、密钥或请求体；不弹出成功 toast 洪水」，`HD-2=A`（`:262`）写明「页面可看＋一键复制脱敏摘要；不导出完整路径」；我实测白名单 `FAIL_DIGEST_FIELDS` 与该 7 类**同名同序**，DoD5 条与该两句**一一对应**——即**需求不存在未决点**，没有需要 planner 重新拆解或 product-reviewer 重新验证的产品判断；② 交付**未引入产品/架构变更**（后端 +3 行只读派生字段、前端新增两个只读入口，无新契约、无数据迁移、无新依赖），故不触发 Change C 的 Controlled Reopen，**`CHANGE_REQUEST=B` 判定正确**；③ AGENTS 明文「跳 planner/product 需记一句原因」，TM **已记**且我在 HANDOFF 执行链与 DISPATCH L58 note 里都看到该原因——**程序完备**。→ 跳步**合规**，**不计打回**。

**裁定二｜「supervisor 复检行尚未记入账本」算不算缺口 → 不算缺口（体例内），但属必须在本次结论后立即补的待办。**
① **性质**：`DISPATCH-LOG` 是「逐派一行」的**派工**账本，supervisor 的结论**在体例上产生于回检完成之时**，不能先记后判；HANDOFF 执行链 ⑥ 已留占位（「见下（三处对账／五查／无 blocking）」）、HANDOFF 账本节亦明写「supervisor 复检行在本节写就后由 TM 追加」——即**该行本就设计为「我出结论 → TM 落盘」**，与我此刻的处境一致，**不构成漏记**。② **但必须补**：P1-3 链的先例是 `L57`（supervisor 复检）**已在账本内**，为保持两链体例一致与「三处对账」闭口，本行**须由 TM 在本节落盘后立即追加**（`role=supervisor`／`model=opencode-go/muse-spark-1.3-contributor`／`used=主`／`runtime=本窗口`／`result=PASS`），并按同样口径把 HANDOFF 执行链 ⑥ 从占位改为实结论、把 `DISPATCH 62→63` 的计数写进 HANDOFF 账本节。**补记完成前，本链账本视为「差一行 supervisor 行」——属程序未完，不影响本轮 PASS 结论的有效性。** ③ 同样提示：`TASK-MODEL-LOG` 是**任务级一行**（L51 已在，`rework=0`），**无需**为 supervisor 复检再开一行。

## 十三、supervisor 复检结论

- **PASS｜无 blocking｜本链 supervisor 累计打回 0/2**（链内 0 次 FAIL）。**不升级、不停线**。
- 依据：三套自测 479／139／58 **全 rc=0**；两账本 **exit 0** ＋ 7 条坏行负控 **exit 1**、正控 exit 0；三处对账 **0 不匹配**（另记 2 行表换代前历史行，非本链）；DoD 5 条**逐条到源码**核过、均真闭环；自写探针 **30/30（后端）＋43/43（前端）rc=0**，覆盖真实形态绝对路径零命中、白名单额外字段注入、**A→B 迟到响应不串味**、替代路径分支真跑到且已脱敏、降级占位；抽检反向证伪 **6 条、4 条被咬住、6/6 还原 sha256 与自算基线逐字一致**（M4 无牙确认为**已知 P3-新1**，非新缺陷）；Phase Integrity **五查全过**；红线**逐项过**（无 commit/push、无 secrets、未碰封存、`docs/sop/` 未动、测试 tmp＋`assert_tmp` 时序正确、主题浅色、**D-12 未放宽**、No-Clobber、词库三铁律）；**P1-3 已收口语义一行未碰**。
- 两点裁定：**跳步合规（不打回）**；**supervisor 行未记属体例内、须即时补**。
- **未改业务代码、未改他人报告正文、未 commit/push**；本文件只追加本节。
- 非阻断待办（交 TM／neat 收尾）：① 立刻补 `DISPATCH-LOG` 本链 supervisor 行（62→63）并同步 HANDOFF 账本计数与执行链 ⑥；② HANDOFF 待排期 backlog 的 P1-7 盘点（「4 处」→ 现 5 处且行号再漂）；③ 账本 L1／L8 历史行可择机加断代注记（非必须）；④ P3-1「真 16 条诊断墙钟」仍是本链唯一未取证项，建议并入 P1-1 真实规模重验证时一并实测。

心跳：目标＝P1-4 全链收口复检｜剩 P0/P1＝0（遗留 P3 全部非阻断）｜下一步＝TM 补登记 supervisor 行后收口，按序推进 P1-5。
