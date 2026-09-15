# CODE REVIEW

- Task: **DEVELOP-P1-3「进度与批量语义修正」**（Plan `docs/pm/PRODUCT_PLAN.md:220`，S 级非 blocking；`CHANGE_REQUEST=B`）＋吸收挂账 **P2-7**（前端 `/api/retry` 带 `data_root`）。范围＝①无目标不画 100%（RERUN-PROGRESS P3-4）②运行中参数锁定（P3-5）③零目标/坏文件提示（CANDIDATE-APPLY P3-3/P3-4）④失败统计统一可复算（CANDIDATE-APPLY P3-2）⑤长任务 elapsed＋可离开（RERUN-PROGRESS P3-6，仅提示）⑥二选一不得双空（CANDIDATE-UI2 P3-2）⑦P2-7 `/api/retry` 带 `data_root`
- Commit: **未提交**（工作树）。`git diff --stat` 实测＝`app/index.html 178/28`、`app/server.py 369/70`、`tests/selftest_p1_2_contract.py 312/0`、`tests/selftest_p1_2_frontend.py 185/1`（合计 1044/99）——与派单书三处数字**逐字一致**（`git diff --numstat` 已核）。**口径修正**：派单书 `HEAD=92fa77e`，实测 `HEAD=3af2da7`（多一个只改 `docs/handoff/HANDOFF.md` 的提交；`git diff --name-only 3af2da7 92fa77e` 输出仅 HANDOFF.md），故本次审查对象与派单书相同，不受影响。`git diff --check` → rc=0。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核，与 builder 非同一审查上下文；先读 CODE_REVIEW.template 与 P1-2 那份报告体例再动手）
- Result: **PASS（无 P0/P1 阻断；P2×4 ＋ P3×9）**。七项范围中 **6 项真闭环、1 项闭环但带 1 处新增文案与事实不符（P2-1，不拦收口、建议同批修）**；builder 9 条自陈 **9 条全接受**（其中 2 条要求改口径表述/补取证，非返工）；「运行中 `/api/reapply` 是否语义旁路」→ **不构成**（独立取证见第四节）。

> 复核口径：只读业务代码＋独立跑自测＋自写探针；**未改业务代码**（4 次反向证伪均为「改回旧形态→取证→还原」，每次以 sha256 校验还原一致）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只新增本报告一个文件。
> 自写探针（全部落 `/tmp`，未入仓）：`/tmp/p13_probe.py`（37 项）、`/tmp/p13_fe_probe.js`（13 项）、`/tmp/p13_recscope_probe.js`（6 项）、`/tmp/p13rev/run.py`（4 组反向证伪，自带 sha256 还原校验）。凡调 handler 的用例首行均断言 `data_root` 在系统 tmp 下。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（427 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS` | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `python3 /tmp/p13_probe.py`（我方独立探针） | 37 项断言，5 条报 FAIL → 逐条归因后**2 条为真发现**（见 P2-3／P3-2）、3 条为我方探针口径过严（见 §七末） | 1（预期，暴露真问题） |
| 6 | `node /tmp/p13_fe_probe.js`（前端独立探针） | 13 项，12 PASS／1 FAIL（该 FAIL 为「`stats` 为非对象时不回落 summary」——**后端不可达**：`stats` 恒为 `null` 或 9 键全量 dict） | 1（同上） |
| 7 | `node /tmp/p13_recscope_probe.js` | `PROBE ALL PASS`（6/6）→ 第 6 项独立复现 | **0** |
| 8 | `python3 /tmp/p13rev/run.py`（反向证伪 4 条） | 4/4「改回旧形态即 rc=1」，且 4/4「还原后 sha256 一致」 | **0** |

还原校验（证伪跑完后）：`app/server.py c6897bc115ca6cf69fccf2b47f24215e008b1830d4ea960101851256f6b553e1`、`app/index.html 5156b12410199bb59b9a08e60d579682a08702089a5602df9018c4d9a259e0a3`，与动手前记录的 sha256 **逐字一致**；`git status --short` 仍只有那 4 个 `M`。

---

## 二、七项范围逐项判定（各给证据行号）

| # | 范围项 | 判定 | 关键证据（工作树行号） |
|---|---|---|---|
| 1 | 无目标不画 100%（RERUN-PROGRESS P3-4） | **真闭环** | 主进度条 `index.html:833-839`（`okPct/failPct/pendPct` 三段全部 `total>0?...:0`，灰段不再满格）；候选条唯一入口 `vocabApplyPct:1384-1388`（`!(total>0)→0`），被 `:1371`（运行中）、`:1436`（失败态）、`:1441`（终态）三处复用；全文件已无硬编码 `width="100%"`（`grep 'style\.width='` 只剩 7 处，全部经守卫函数） |
| 2 | 运行中参数锁定（RERUN-PROGRESS P3-5） | **闭环**（1 处残留 → P2-4） | 前端 `setCandidateControls:1292-1311`＋就地说明 `#batchLockHint:236`（DOM id 实测在位）；后端早锁 `server.py:3690-3693`（**先于**版本锁 `:3694-3703`）、竞态兜底 `:3715-3719`、统一 409 `_vocab_apply_locked_response:3638-3659`（`locked_params` 仅同目录 realpath 才回）；同步入口 `_run_vocab_candidates_apply` **不在路由表**（唯一 HTTP 入口 `Handler:6102` 是异步壳） |
| 3 | 零目标 / 坏文件提示（P3-3＋P3-4） | **真闭环** | 三态 `_vocab_candidates_read:3233-3257`（`missing/corrupt/ok`，缺失与腐坏文案不同）；GET 回传 `candidates_state/candidates_state_message` `:3311-3326`（`source_exists = state!="missing"`）；前端三分支 `loadVocabCandidates:1322-1336`（corrupt 走 `hint err`＋`esc()`，**不落**「暂无待审候选」）。零目标人话：`server.py:1952`（retry-plan）、`:3373`（同步 apply）、`:3678`（异步 apply）、`:3471`（导入 0 条）、`:3535`（词入库但无可重跑稿件）；前端 `index.html:1157-1158`、`:1623-1629`、`:1445-1447` |
| 4 | 失败统计统一可复算（CANDIDATE-APPLY P3-2） | **闭环**（1×P2＋2×P3 收口项） | 唯一归类 `_reapply_result_bucket:5534-5545`／`_reapply_stats:5548-5560`（五桶 `_REAPPLY_BUCKETS:5531`、`total/done/counted/balanced` 齐）；批量恢复同口径 `RECOVERY_BUCKETS:1750-1751`／`_recovery_bucket:1754`／`_recovery_apply_counts:1776-1806`；`_reapply_all:5946-5956`（`failed` 不再把「跳过」算进去）；前端不再自算 `vocabApplyStatsText:1402-1416`；终态两侧读同一 `stats`（`:3618-3623` 白名单透传 → `:3819` status 回包） |
| 5 | 长任务 elapsed＋可离开（P3-6，仅提示） | **真闭环（提示）／未做强制取消＝符合 DoD** | `_elapsed_seconds:4281-4309`（坏时间戳回 0、时区不一致回 0、倒挂不为负——我方探针 3a-3d 实测）；status 回 `elapsed_seconds:3812-3813`＋`indices_count:3807`；前端 `vocabApplyElapsedText:1392-1399`、运行中文案 `:1373-1379`（「· 已用时 Ns · 可离开本页面…（本版不提供中途强制取消）」）。**但批量重试那条文案与事实相反 → P2-1** |
| 6 | 二选一不得双空（CANDIDATE-UI2 P3-2） | **真闭环** | 策略侧 `applyVocabCandidates:1651-1655`（双空→回勾「只对新视频生效」＝安全侧＋`say` 人话；与静态默认一致 `:252`）；范围侧 `recScopeVal:2071-2079`（无选中→回勾 `sel`＋`recoverHint` warn）与 `syncRecScope:2080-2087`（同样自愈）；我方独立探针 6/6 PASS（含「选 all 不被改写」「无 radio 元素不炸」） |
| 7 | P2-7 `/api/retry` 带 `data_root` | **真闭环** | 前端 `retryBody:1091-1097`（框优先→`effectiveDataRoot`→都不带）＋接线 `:1101`（单条）／`:1174`（批量）；后端 `_handle_retry_post:5009-5084`：严格取参 `:5025-5028`、跨目录 realpath 比对 → 409 零执行 `:5038-5045`、缺键沿用监听目录 `:5047-5048`、查库改用请求目录 `:5057-5070`。**残留：主入口静默吞 409 → P2-2** |

### 附：builder 对「阶段条 `:859` 不属该问题」的判断——**独立核过，接受**

- `progStageFill` 只在 `if(cur&&cur.run_id)` 分支（`:845`/`:858-859`）出现，即**真有当前任务在跑**；`stageStep:815-822` 的 `pct` 是「第几步/共 5 步」的位置值（`入库中=100`）。
- 它是**橙色**（`#progStageFill{background:var(--orange)}` `:113`）不是绿，且 DOM 常驻免责声明 `#stageNote`「步骤进度非精确百分比，仅表示当前在哪一步」（`:226`）；P3-4 的原意是「**无候选/无目标**却画绿满 100%」，此条不属于。
- 唯一可议：`入库中` 时该条满格。属观感，记 **P3-8**（可后续改成步骤点，非本次范围）。

---

## 三、builder 9 条自陈逐条裁定

| # | 自陈 | 裁定 | 理由／反例／补测要求 |
|---|---|---|---|
| 1 | 未起服务、未真机目检；DOM `disabled` 未实点 | **接受**（补测要求） | 与红线一致（本窗口禁点真机主题开关、8765 无监听）。但「控件禁用」是本次语义交付的一半，node 桩**不覆盖真 DOM 事件**：我改为静态取证——`setCandidateControls` 动到的 9 个 id 在 HTML 里逐个人工核对在位（`btnRecTranscribe:231`／`btnRecReuse:232`／`btnRecPublish:233`／`recScopeSel|recScopeAll:235`／`batchLockHint:236`／`candidateSelectAll|candidateRerunOld|candidateOnlyNew:252`），真浏览器里 `disabled` 的按钮不会触发 onclick。**要求交 QA 真机实点一次**（起服务后运行中尝试点三个批量按钮＋两个范围单选），并把结果记进 qa 报告。 |
| 2 | `/api/reapply`、`/api/retry` 未加「运行中 409」，理由＝会自锁 | **接受技术理由；不接受「语义已封闭」的表述** | 自锁理由成立且可指认：内部调用点在 `server.py:3501`（`_handle_reapply_post(reapply_body, progress_cb=…)`），而 `_handle_reapply_post:5968-5999` **没有任何内部调用标记**，加锁必自锁。但「运行中用户打 `/api/reapply` 能不能改本次执行的范围」这一问的正确答案是**「改不到本次执行参数，但能另起一次并行重跑」**（独立取证见 §四）。表述要改；并建议把内部调用改成显式 `internal=True` 后再给该入口加锁。**下方 P2-4** |
| 3 | `rerun_old` 缺键仍默认 `True` | **接受** | 属 P1-2 已验收契约（「字段缺失＝全量重跑」），本链改默认会动已固化契约。前端提交时该键**恒存在且为真布尔**（`:1656` 取 `checked` → `reapplyPayload`），缺键分支线上不可达；双空兜底把它钉在 `false`（安全侧）不与之冲突。 |
| 4 | 批量恢复前端无进度 UI，⑤ 只落错词重跑进度条与首屏提示 | **接受** | P0-2 明确只做后端。顺带确认：`retry-batch/status` 的 `elapsed_seconds`（`_recovery_job_read:2396-2400`）仓内 0 调用点，属既有挂账，不因本链变化。 |
| 5 | `_handle_retry_post` 的 DB 404 未跑到，只断言「202/404 二选一＋不泄漏路径」 | **接受（软断言已披露）＋补测要求** | 归因正确：合成库无 stage2 单实例锁，`open_db` 抛错被既有 best-effort 分支（`:5071-5073`）吞掉。但我实测该函数**新增了「按请求目录查库」**（`:5057-5070`），`run_id` 不存在时 404 的文案「任务不存在，请刷新后重试」会被 `retryAllFailed` 静默计入 `badN` 且**不展示**（同 P2-2）。要求 QA 在可读 DB 的 tmp 场景补一条「同目录 + 不存在 run → 404」的真取证（现在 `code in (202,404)` 的软断言掩盖了两条分支的差别）。 |
| 6 | `/api/retry` 的 400 文案沿用 `_take_data_root` 口吻，未统一「数据目录」人话 | **接受** | 不动共享 helper 是对的（牵连 reapply／retry-plan／presets 四条链，属另一次改动）。**实测确认无脱敏风险**：`_bad:157-158` 只回 `key＋期望类型＋类型名`，`_take_data_root:260-276` 的两条 400 分别是「data_root 须为字符串（绝对路径）（收到 数组）」与「数据目录须为绝对路径，请点浏览重选」——**均不吐用户原文/路径**（我方探针 2a-2c 实测）。文案统一记 backlog。 |
| 7 | 两处把半成品判为「做歪」并改掉（`done=counted`、锁回显带 `data_root`） | **接受，且这两处判断正确** | ① `done=processed`（`_recovery_apply_counts:1804`）确有区别：若沿用 `done=counted`，登记 4 条只落盘 3 条时会显示已处理 4（虚满），现为 3（我实测 job `{"total":4, results 3 条}` → `done=3/interrupted=1/balanced=True`）。② 锁回显仅同目录（`:3645-3658`）：我实测别目录调用 409 响应里**无 `locked_params`、且两个 root 字符串均不出现**（探针 1e／2d）。旧句字面不一致属历史快照 → **P3-7**（交收尾 neat-freak 加注，不改正文）。 |
| 8 | 真实 whisper／61 篇／长视频 elapsed 未实测；`retryAllFailed` 的锁是页面态、刷新即丢 | **接受为已声明缺口**（并把后者升格为须修） | 真实规模属 P1-1 链，不在此评。但「刷新即丢」正是 **P2-1** 的成因：批量重试是页面内循环，刷新/关页会**中止剩余入队**，因此绝不能说「可离开页面、排队在后台继续」。 |
| 9 | 词库三铁律／No-Clobber／主题默认浅色自查 0 命中 | **独立复核：接受** | `index.html:2` 仍是 `data-theme="light"`（字符串实测在位）；本 diff 的 hunk 未触碰 `_validate_vocab_pair`、`REAPPLY_ELIGIBLE:5970`、`_reapply_one` 的 No-Clobber/publish 段、`_vocab_base_patterns`；`_vocab_candidates_read` 读腐坏文件不改字节（我方探针 3n：sha 前后一致）。 |

---

## 四、【咬住项】运行中直接打 `/api/reapply`：**不构成本次执行参数的语义旁路**（独立取证）

**结论**：不能改到「本次执行」的范围；能**另起一次并行重跑**（仓内 UI 已禁入口，后端无互斥）——属**既有残留**，本链**降低了**暴露面，记 **P2-4**。

**取证 1｜运行中被冻结的是线程私有的 `params` 快照，不是可变共享态**：`_handle_vocab_candidates_apply:3708-3714` 组 `job_params` → `:3747-3748` `threading.Thread(target=_vocab_apply_worker, args=(job_id, params))`；worker（`:3594`）把该 dict 交给 `_run_vocab_candidates_apply`。全仓 `_vocab_apply_job` 的读写点**穷举**为 `:90 / 3580 / 3599 / 3669 / 3691 / 3716 / 3723 / 3755 / 3782`——**全部**在 apply 入口与 apply worker 内；`_handle_reapply_post`（`:5968` 起）、`_handle_retry_post`、`_handle_retry_batch/plan` 一次都不碰它。

**取证 2｜真 handler 实测（tmp 合成，`assert_tmp` 过门）**：置 `_vocab_apply_job` 为 running（`request_indices=[0,1,2]`、`rerun_old=True`），再逐个打真入口：

| 调用 | 实测返回 | 冻结参数是否被改动（json 逐字比对） |
|---|---|---|
| `POST /api/reapply {data_root, all:true}` | 200「没有可重跑的已完成任务」（**确实执行了**，未 409） | **未改** ✔ |
| `POST /api/retry {run_id, data_root}` | 202 | **未改** ✔ |
| `POST /api/failures/retry-plan {run_ids}` | 200 计划 | **未改** ✔ |
| `POST /api/failures/retry-batch {confirm:true, 坏 token}` | 409（令牌未知；**互斥也不存在**） | **未改** ✔ |
| `POST /api/vocab/candidates/apply {indices:[9], rerun_old:false}` | **409** 且 `locked_params.indices=[0,1,2]`、`rerun_old=true` | **未改**，且**本次提交参数未被采纳** ✔ |
| 同上但 `data_root` 换成别目录 | 409，响应里**无** `locked_params`、无任何路径 ✔ |

**取证 3｜DoD 语义**：P3-5 要求「本次执行参数在运行窗口内冻结」。真用户触点里，触发 `/api/reapply` 的三个按钮与范围单选已在 `setCandidateControls:1292-1311` 内被禁（`btnRecTranscribe/Reuse/Publish`＋`recScopeSel/All`），并在提交/接管时（`:1661`、`:1552`、`:1602`）与终态（`:1478`、`:1492`）正确加解；后端对真正属于「本次执行」的入口（异步 apply）一律 409 零执行。

**残留（记 P2-4）**：`_handle_reapply_post` 与 `_handle_retry_batch_post` 在 apply 运行中可被并行执行（两个线程同时重排/重入稿）。此风险**早于本链**（HEAD 版本里 apply 提交时并不禁用重跑按钮，`git diff` 无对应 hunk），本链反而把 UI 入口关掉了。建议下一批：给 `_handle_reapply_post` 加「非内部调用 + 有 running apply → 409」，内部调用（`:3501`，已带 `progress_cb`）以显式 `internal=True` 豁免。

---

## 五、反向证伪抽查（我抽了哪 4 条、怎么抽、结果）

做法：`/tmp/p13rev/run.py` 对真源码做**唯一锚点**替换 → 跑对应自测 → **要求 rc=1** → 从备份整文件还原 → **sha256 必须与改动前一致**。全程未使用 builder 的断言作为判据（只看 rc 与 FAIL 行）。

| 抽检 | 改回旧形态 | 实测 | 是否「有牙」 |
|---|---|---|---|
| **A**（我评：本链最关键） | `server.py` 早锁块的 `cur.get("state")=="running"` → 改成不可能匹配，使「锁先于版本锁」失效 | `selftest_p1_2_contract.py` **rc=1**，FAIL 两行：`10e 运行中提交 -> 409 人话（零执行）` 与 `10e 锁定检查先于版本锁（不报「清单已变化」）`——实测返回变成版本锁的「候选清单已变化（零执行）」 | **有牙** ✔ 还原一致 ✔ |
| **B** | `index.html` `renderVocabApplyFinal` 的 `vocabApplyPct(s)` → 硬写 `"100%"` | `selftest_p1_2_frontend.py` **rc=1**：`FAIL S8a 零目标终态不画满（宽度 0%，旧形态是 100%） << "100%"` | **有牙** ✔ 还原一致 ✔ |
| **C** | `server.py` `_reapply_result_bucket` 退回旧两桶（只剩 `ok?success:failed`） | `contract` **rc=1**：`10a 跳过/待人工/中断各归各桶` 打印 `skipped=0/needs_human=0/interrupted=0, failed=5` 与 `10a 未知 state / 坏条目 fail-closed` 同挂 | **有牙** ✔ 还原一致 ✔ |
| **D** | `server.py` `/api/retry` 的跨目录比对改成 `if False:` | `contract` **rc=1**：`10f 跨目录重试 -> 409 人话且不回两个真实路径`，实测变成 **202** 并回「该任务已在排队」 | **有牙** ✔ 还原一致 ✔ |

结论：这 4 条断言**不是自我实现的假信心**；`10e`（A）与 `10a`（C）确实咬住了本链的两个核心语义。builder 自述的「13 项反向证伪」我只复现了 4 条（其余未抽样，不为其背书）。

---

## 六、D-12 脱敏：**本次 diff 全量扫描结论＝0 命中**

1. **静态全量**：`git diff -U0 -- app/` 的 **547 条新增行**逐行抽取字符串字面量，按 `/(Users|home|private|var|Volumes|Applications|tmp)/` 扫 → **0 命中**（另有一轮宽松扫描的 6 条命中全为 HTML 标签 `</label></div>` 与注释里的 `P1-3/RERUN-PROGRESS`，非路径）。
2. **新增出口逐个数**（本链新增/改动的错误与提示出口，全部为人话常量，无路径、无异常原文）：`empty_msg` 三处（`:1952/:3373/:3678`）、`_vocab_candidates_read` 两态文案（`:3240-3254`）、`_vocab_apply_locked_response`（`:3648-3658`，含 `job_id`＋`locked_params` 的 rerun_old/revision/indices/total/done，**无路径**）、`/api/retry` 的 400/409（`:5021/:5026-5028/:5037/:5042-5045`）、批量恢复的五桶字段与两处 INTERRUPTED 文案（`:2352-2368`／`:2380-2390`）、`_reapply_all` 的新 message（`:5957-5962`）、`_elapsed_seconds`（无输出）。
3. **`_take_data_root` 是否回显用户传入路径**（点名项）：**不回显**。坏类型走 `_bad` → 只有类型名（`_TYPE_ZH`，`:143-158`）；相对路径走常量「数据目录须为绝对路径，请点浏览重选」（`:275`）。实测 `{"data_root": ["x"]}` → 「data_root 须为字符串（绝对路径）（收到 数组）」、`{"data_root":"相对//Users/reviewer_probe_secret/…"}` → 不含 `Users`/不含 `reviewer_probe_secret`、`{"data_root": True}` 同。(`/tmp/p13_probe.py` 2a/2c)
4. **别目录 409 不泄漏**：`/api/retry` 跨目录 409 与 apply 锁定 409 的响应体里，两个真实 root 均不出现（探针 1e/2d；builder 自测 `10f` 亦含同断言，属独立复算）。
5. **载体澄清（非问题）**：`/api/vocab/candidates` 与 status 仍按产品口径返回 `data_root`／`job.data_root`（HD-2=A：错误摘要打码、不做完整路径导出），与 P1-2 报告第 99 行的既定口径一致，**不作为问题**。

---

## 七、前后端新字段一致性 与 fail-closed 逐路径

**字段对齐（逐字核）**：`stats`（9 键白名单 `:3621-3623` → status `:3819` → 前端 `:1402-1416`，缺失时回落 `summary`）、`locked_params`（仅 409，前端 `:1420-1429`，`rerun_old` 非布尔即回空串不编造）、`counted/balanced`（`/api/failures/retry-batch/status` 专用，**前端 0 引用**——前端自己用五桶做等式校验，非「第二套口径」）、`candidates_state(_message)`（`:3325-3326` → `:1331-1342`，`esc()` 转义）、`elapsed_seconds`／`indices_count`（`:3812/:3807` → `:1392/:1426`）。**缺字段不炸**：我方独立前端探针 13 项中 12 PASS——`renderVocabApplyFinal({})`、`{stats:null,summary:null}`、`{state:"failed"}`、`renderVocabApplyProgress({})` 均不抛异常且进度 0%（第 13 项 FAIL 为我方断言过严：`stats` 为难对象时不回落 `summary`；后端不可达，见 §一 第 6 行）。

**fail-closed 逐路径（真跑/tmp）**：

| 路径 | 期望 | 实测 |
|---|---|---|
| 运行中 apply | 409＋零执行零写盘 | ✔ 409，`tree_snapshot` 前后一致、`vocab-user.json` 未生成（builder `10e`＋我方探针 1d） |
| 跨目录 `/api/retry` | 409＋零执行 | ✔↔（证伪 D：拿掉即变 202） |
| 坏类型 / 相对 `data_root` | 400＋零执行 | ✔ 探针 1b/2a/2c |
| 空 `indices` / 空 `run_ids` | 400 人话＋零写盘 | ✔ 探针 4a/4b（`snap()` 前后一致） |
| 候选清单缺失 | 409（`absent` 哨兵）零执行 | ✔ `:3694-3699`（P1-2 既有） |
| 清单腐坏读不出 | `corrupt` 提示且**不改文件** | ✔ 探针 3n（sha 不变） |
| 未知 state / 坏条目 | 进 failed 桶 | ⚠ **只做到一半**：`ok:false` 类正确；`ok:true` ＋ 未知 state → success（P2-3）；`_recovery_bucket` 侧完全以 state 为准（未知→failed） |
| 非数组 `results`（job 文件损坏） | 不得产生荒谬 total | ✘ 未终态分支按可迭代元素计数（P3-2） |

---

## 八、数据安全 与 测试质量

- **只写外置 tmp ＋ 合成数据**：`part10`（`tests/selftest_p1_2_contract.py:1439` 起）每个子块首行 `assert_tmp`（`:1443-1445`、`:1604`、`:1630`），`make_data_root` 内部亦过门（`:118`）；`DEFAULT_DATA_ROOT` 在 `part1` 过门（`:198`）。我跑完检查 `p12_*/p13_*` 遗留目录 **0 个**。前端自测只写一个临时 JS（`tempfile`），其假目录 `/tmp/p13-fake-root` 仅存内存，node 桩无 `fs` 调用。
- **一处小瑕疵**：`10f` 的符号链接夹具建在**系统 tmp 根**（`os.path.dirname(root_a)`＋`"-rlk"`，`:1706-1719`），而非 root_a 内部；有 `finally` 清理、名字源自 mkdtemp 唯一名，不构成数据风险，仅记 **P3-8** 提醒。
- **软断言**：`10f` 末条 `code in (202, 404)` 已由 builder 披露并给出成因（自陈 #5），我接受但要求 QA 补真取证。
- **无跳过/无早退**：新增 `part10` 无 `skip`、无 `sys.exit(0)` 早退；`main()`（`:1744`）里 `part10_p13_semantics(server)` 已挂进主链。
- **测试「有牙」**：见 §五（我抽 4 条，全有牙）。

---

## 九、范围外改动核查（Scope creep）

逐 hunk 对照七项＋P2-7，**未发现范围外改动**：`index.html` 15 个 hunk 按工作树行号分属 ①（`:824-839` 主条）②（`:236` 提示行＋`:1292-1311` 锁函数＋`:1373-1381` 文案）③（`:1322-1336` 三态＋`:1623-1631` 零目标）④（`:1402-1416` 统计文本＋`:1430-1447` 终态）⑤（`:1392-1399` elapsed）⑥（`:1651-1655`／`:2071-2087` 双空）⑦（`:1091-1097`＋`:1101`／`:1174` 接线）；`server.py` 21 个 hunk 无一落到词库校验/No-Clobber/诊断语义/状态机；主题、改名、`v2o-*` 标识零改动。**另记一句**：`app/server.py` 里亦有历史遗留的「P1-3：运行中拒清」（`:5099/:5171`）字样，经 `git show HEAD` 比对**属 HEAD 既有**、非本次新增，勿与本链混淆。

---

## P0 / P1 Findings

- **无 P0 阻断、无 P1 阻断。** 七项交付目标经独立取证均达成（6 项真闭环；第 5 项闭环但含 1 处与事实不符的新增文案，判 P2）。三套自测 rc 全 0（427／FRONT／58）；反向证伪 4/4 有牙且还原 sha256 一致；D-12 新增出口 0 命中；新拒绝路径实测零执行零写盘；范围外改动 0。

## P2 / P3 Backlog Findings

- **P2-1（须修，建议同批）** `retryAllFailed` 新增文案与事实相反：`index.html:1163`「可离开本页面，稍后回来仍能看到结果」、`:1178`「（可离开页面，排队在后台继续）」，以及运行中常显的 `#batchLockHint`（`:1310`「可离开本页面稍后回来」）。批量重试是**页面内循环**（`:1172-1179` 逐个 `fetch /api/retry`），离开/刷新页面＝**剩余任务不入队**（无任何断点续做，我核过 `retryAllFailed` 无 localStorage/后端 job 支撑）。对照：`reapplyAll:1220-1234`（其 `say` 在 `:1224`）的同类文案是**真的**（单次同步 POST，服务端在客户端断开后仍跑完）。改法（一行级）：批量重试改成「本页需保持打开才能继续排队；已入队的会继续跑完」；或改走已有 `/api/failures/retry-batch` 通路（服务端 job）。
- **P2-2（须修，建议同批）** P2-7 新失败模式在首屏主入口被静默吞掉：`:1177` 只做 `badN++`，**不展示** `x.o.error`，而新加的跨目录 409（`server.py:5042-5045`）与相对路径 400（`:5026-5028`）会让「重新转写全部失败」直接变成「已排队 0/16，失败请求 16」而**零原因**；`retryBody:1091-1097` 也不像 `applyVocabCandidates:1644-1647` 那样先做 `isAbsRoot` 本地拦。改法：`retryBody` 侧加 `isAbsRoot` 前置（不合法就不带/不提交并给话）＋批量循环记首个 `error`，收尾文案回显（或 409 单独计数提示「目录不一致，请核对上方数据目录」）。
- **P2-3（须修，口径）** `_reapply_result_bucket:5534-5545` 的 fail-closed 只做一半：`success/failed` 只看 `item.get("ok")`，未知 `state` 不参与。实测 `{"ok":True,"state":"WEIRD_UNKNOWN"}` → `success`（与 `:5521-5532` 注释「未知 state／坏条目一律并进 failed」及 DoD 冲突）；`{"state":"SUCCEEDED"}`（无 `ok`）→ `failed`。同时与姊妹实现 `_recovery_bucket:1754-1766`（只认 `state`）**判据不同源**。线上暂不可达（`_reapply_one` 产出的条目**根本没有 `state` 键**，只用 `ok/skipped/skipped_user_edited`，`:5739-5748`、`:5816`），故非阻断。改法：`state` 非空且不在白名单时强制 `failed`；或把注释改成「成功以 `ok` 为准」，并补一条 `{"ok":True,"state":"WEIRD"}` 的断言。
- **P2-4（残留，非本链引入）** 运行中 `/api/reapply`、`/api/failures/retry-batch` 无后端互斥，可并行另起一次重跑（见 §四）。改法：`_handle_reapply_post` 加「非内部调用 + 有 running apply → 409」，内部调用改显式 `internal=True`；批量恢复同理。
- **P3-1** `_run_vocab_candidates_apply:3516-3522` 的「老响应回落」键名映射错：读 `summary["success"]/["skipped"]`，而 `_reapply_all` 的真实键是 `ok`/`skipped_user_edited`（`:5949-5951`）——我实测该分支 `success=0`（真值 2）、`balanced=false`（静默）。今天恒不可达（`results` 非空；`total=0` 时全 0 无害），建议删除或修正映射。
- **P3-2** `_recovery_bucket_counts:1768-1774` 未校验 `results` 是否 list；未终态分支（`:2380-2390`）用的是**文件原始值**（读路径 `:2396-2399` 先 normalize 所以安全）。我实测 `{"total":3,"results":"not-a-list"}` → 按 10 个字符计数 → `total` 被抬到 10、`balanced=true` 并写回盘。改法：先 `isinstance(results, list)`。
- **P3-3** `codesummary` 三处口径不齐：`rerun_old=false` 分支（`:3493`）仍是旧格式「导入N条/重跑成功0篇/跳过0篇/失败0篇；老稿未动」，与另两处新格式不一致（该分支确实没重跑，数字无误，仅格式/观感）。
- **P3-4** 候选链的 `balanced` 恒真：`_reapply_stats(results, total=len(results))`（`:3515`）total 由结果数派生 → 前端「可复算：…」在该路径无鉴别力。真正有鉴别力的是 `_reapply_all`（targets 口径 `:5920/:5948`）与 `_recovery_apply_counts`（登记数口径）。
- **P3-5** `indices_count`＝**提交的候选下标个数**（`:3807`＋`:3731`），含重复/越界/已导入而被拒的下标；前端文案「目标候选 N 条」（`:1427-1428`）易被读成「实际生效 N 条」。建议改「本次提交候选 N 条」。
- **P3-6** 锁定范围偏宽＋可控性判据不同源：`setCandidateControls:1292-1311` 在 `retryAllFailed`（`:1155` 起，锁点在 `:1162`）窗口内连带禁掉候选勾选/策略/范围单选（这次批量重试并不读这些控件）；`vocabApplyDropPoll:1478`／`vocabApplyFinish:1492` 用 `candidateCheckboxes().length>0` 决定 `on`，可能放开按钮但 `vocabCandidatesRevision` 为空（点了再报人话错）。
- **P3-7（docs，交收尾 neat-freak 加注不改正文）** 历史报告旧句与新语义冲突：`docs/qa/RERUN-PROGRESS-QA-REPORT.md:84`（E2 曾把「绿条 100%」判 PASS，本链**有意**改 0%）、`:57-58`、`docs/qa/CANDIDATE-APPLY-QA-REPORT.md:24`、`docs/review/CANDIDATE-APPLY-CODE-REVIEW.md:25,37`、`docs/review/RERUN-PROGRESS-CODE-REVIEW.md:28`。builder 自陈 #7 属实。
- **P3-8** 观感/清洁：阶段条在「入库中」= 满格（见 §二附，已有「步骤进度非精确百分比」免责）；`10f` 符号链接夹具建在系统 tmp 根而非 root_a 内；仓内 35 个 `.pyc`（`app/__pycache__` 等，gitignore 内、测试副产物，**本次未动**）建议收尾清理。
- **P3-9** 批量恢复链的零目标可建空 job：`retry-plan` 在全部被排除时回 200＋`eligible=[]`（`:1969-1970/:1994-2000`），据此 `retry-batch` 用 `run_ids:[]` 可建 `total=0` 的空 job（`:2235` 集合相等即过）。仓内无前端调用点，影响 0；建议 eligible==0 时 409 或回人话 message。

## 回归结论

- **无倒退。** 本 diff 的 hunk 逐块读过：未触碰 `_validate_vocab_pair`／词库三铁律、`REAPPLY_ELIGIBLE:5970`、`_reapply_one` 的 No-Clobber 与 publish 段、`_recovery_gate_ok` 六门、`_FAIL_SEMANTICS`/`_diagnosis_item`、三策略执行体、候选版本锁本体、`Handler.do_GET` 外壳；`RECOVERY_RESULT_FIELDS:1811-1814`（P1-2 字段契约）零改动（实测 diff 中该标识 0 命中）。
- 三套自测 rc 全 0（427／FRONT／58）；`selftest_v26_presets.py`（词库侧）未受影响。主题默认浅色未回退。`git diff --check` rc=0。
- 本链唯一**新增行为面**是「无目标不画满＋零目标人话＋运行中 409 锁定＋`/api/retry` 跨目录 409」四处 fail-loud，均已核对仓内调用点：`/api/retry` 的两个调用点（`:1101`／`:1174`）都已改成带 `data_root`；候选 apply 唯一调用点带 `candidates_revision`（既有）；**漏改 0 处**。副作用与残留见 P2-1/P2-2/P2-4。

## 未覆盖项（本复核未验，不得推断为通过）

1. **真机 UI 目检**：未起 8765、未点页面。前端结论＝「抽真源码＋node 桩」＋我对 DOM id 的静态核对，**不替代真机**（builder 自陈 #1，我已提补测要求）。
2. **真实 whisper／真实 61 篇量级／长视频 elapsed 数值**（属 P1-1 链）。
3. **多标签页真并发**：锁定与 `job_id` 隔离只做了函数级/桩级验证。
4. **`/api/failures/retry-batch` 与 `status` 的前端使用场景**（仓内无调用点），其新字段仅经 handler 层验证。
5. **真实 DB 可读时的 `/api/retry` 404 分支**（自陈 #5，要求 QA 补）。
6. **并发两次重跑的真实写盘竞争**（P2-4）未做注入级实验；只证明「不改本次参数」。
7. 用户真实视频目录与 Obsidian 库（红线禁写，未读未写）。

---

心跳：目标＝独立复核 DEVELOP-P1-3 交付并落盘报告｜结论＝**PASS（无 P0/P1；P2×4＋P3×9，其中 P2-1/P2-2 建议同批一行级修）**｜下一步＝交 qa（真机实点三批量按钮＋两范围单选；补「同目录 run 不存在→404」真取证）→ supervisor 复检。

---

# 复核二｜DEVELOP-P1-3 返工（**只核 P2-1／P2-2**）

- Task: **DEVELOP-P1-3「进度与批量语义修正」返工**（`CHANGE_REQUEST=B`；范围锁定＝上一节 P2-1「批量重试文案与事实相反」＋P2-2「P2-7 新失败模式被静默吞掉」两项，其余 Findings 不在本轮）。
- Commit: **未提交**（工作树）。基线 `HEAD=3af2da7`（实测）。工作树累计 `git diff --numstat`＝`app/index.html 231/32`、`app/server.py 369/70`、`tests/selftest_p1_2_contract.py 323/0`、`tests/selftest_p1_2_frontend.py 341/1`；`git diff --check` → **rc=0**。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核；读盘顺序照 AGENTS→角色卡→override 表→HANDOFF→经验一句话→任务）
- Result: **PASS（无 P0／P1 阻断）→ 放行去 QA**。P2-1 **真闭环**；P2-2 **真闭环**（409/400 实测能到用户眼前、本地门零误拦、口径与后端一致、脱敏通过、`say` 截断不伤关键原因）。本轮**新增 0×P0／0×P1／0×P2**，新增 **1×P3**（共用锁定提示尾句，见 P3-新1）＋1×P3（既有测试夹具泄漏，P3-新2）。上一节的 **P2-3／P2-4 仍开**（不在本轮范围，非阻断，留 backlog）。

> 复核口径：只读业务代码＋独立跑三套自测＋自写探针＋自己动手做反向证伪；**未改业务代码**（4 次反向证伪均为「改回旧形态→取证→整文件还原」，每次以 sha256 校验还原一致；还原后 `app/index.html` 与 builder 申报值逐字相同）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只追加本文件一节，**上一节正文一字未动**。
> 自写探针（全部落 `/tmp/p13rev2/`，未入仓）：`run.py`（反向证伪 3 条，自带 sha256 还原校验）、`probe_reapply_disconnect.py`（`:1270` 同步语义，真 socket RST）、`probe_coldstart.py`（`:1424/:1427` 冷启动边界，复用仓内桩）、`probe_apply_disconnect.py`（异步 job 与连接解耦）。凡调 handler 的探针首行均断言 `data_root` 在系统 tmp 下。

---

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（429 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS`（`^PASS` 共 **86** 行，其中 **S9 段 18** 行） | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS` | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/index.html app/server.py` | index `a3735655…56f0`（＝builder 申报值）、server `c6897bc1…53e1`（＝**复核一记录的同一哈希**） | 0 |
| 6 | `python3 /tmp/p13rev2/run.py`（我方反向证伪 3 条） | 3/3「改回旧形态即 **rc=1**」，3/3「还原后 sha256 一致」 | **0** |
| 7 | 内联脚本：反向证伪 **E**（过度修正） | **rc=1**，还原 sha256 一致 | 1（预期，暴露我故意造的错） |
| 8 | `python3 /tmp/p13rev2/probe_reapply_disconnect.py`（真 socket RST） | **5/5 PASS** | **0** |
| 9 | `python3 /tmp/p13rev2/probe_coldstart.py`（node 桩） | **3/3 PASS** | **0** |
| 10 | `python3 /tmp/p13rev2/probe_apply_disconnect.py`（真 HTTP＋RST） | **3/3 PASS** | **0** |

还原校验（证伪全部跑完后）：`app/index.html a37356550b12dca606ed6493a7b2a040118841b567b12f6ac747923cb99e56f0`，与动手前记录**逐字一致**；`git status --short` 仍只有那 4 个 `M`（＋本报告 `??`）。我的全部探针**未在系统 tmp 留下夹具**（`p13b_*` 0 个）。

---

## 二、返工增量：**用上一轮记录的总数反推**，四项自报**全部独立对上**

`git diff` 只有「P1-3 首版＋返工」的累计量，看不出本轮增量。我不采信自报，改用**上一节自己记录的累计数**做差：

| 文件 | 复核一（上一轮）记录总数 | 本轮回测总数 | 反推本轮增量 | builder 自报 | 判定 |
|---|---|---|---|---|---|
| `app/index.html` | `178/28`（上一节 `:4`） | `231/32` | **+53／−4** | +53／−4 | ✔ 逐字一致 |
| `app/server.py` | `369/70`（上一节 `:4`） | `369/70` | **0／0** | 0 行 | ✔ 一致，且见下哈希 |
| `tests/selftest_p1_2_contract.py` | `312/0`（上一节 `:4`） | `323/0` | **+11／−0** | +11／−0 | ✔ 逐字一致 |
| `tests/selftest_p1_2_frontend.py` | `185/1`（上一节 `:4`） | `341/1` | **+156／−0** | +156／−0 | ✔ 逐字一致 |

**「`server.py` 本次 0 行」的独立铁证**：当前 `app/server.py` sha256 ＝ `c6897bc115ca6cf69fccf2b47f24215e008b1830d4ea960101851256f6b553e1`，与**上一节 `:26` 我亲手记录**的还原校验哈希**逐字相同** → 本轮确实一个字节都没动后端。故 P2-1／P2-2 是**纯前端＋测试**的修复（后端 409/400 判定、fail-closed、零执行零写盘原样）。

---

## 三、P2-1 是否真闭环：全文「可离开／后台／稍后回来／继续跑」类逐处判定

做法：`grep -n "可离开|离开页面|离开本页|稍后回来|后台|继续跑|继续重试|刷新即可|本页会等|关闭页面|勿关|保持打开"` 扫全文（含 HTML 静态文本），再对每处判「成立／不成立」；两条 builder 保留项**另做实证探针**（§三附1／附2）。

| # | 位置（工作树行号） | 当前文案（摘） | 判定 | 依据 |
|---|---|---|---|---|
| 1 | `index.html:1186` | 批量重试首条：「…需保持本页打开：离开或刷新后，剩下没排上的不会继续重试（已排上的会照常跑完）」 | **成立** | `retryAllFailed` 是页面内 `for` 循环（`:1193-1225` 逐个 `fetch /api/retry`），进度只存在于闭包 `i`；核过该函数**无 localStorage／无后端 job**（`:1172-1227` 内 0 命中 `localStorage|job_id`），关页即断。已入队的那几条确由 worker 跑，措辞准确 |
| 2 | `index.html:1195` | 逐条进度：「（需保持本页打开，离开则剩余任务不会再排队）」 | **成立** | 同上；且与实际行为对齐（自测 `9a` 断言「真发出两条并报 2/2」，文案没换掉行为） |
| 3 | `index.html:1359` | `#batchLockHint`（共用锁定提示） | **「可离开」已摘 ✔**；尾句余留 → **P3-新1** | 见 §三附3 |
| 4 | `index.html:1270` | 重新成稿：「本页会等到跑完；也可离开页面，后台会继续跑完，回来刷新即可看任务状态」 | **成立（实证）** | 见 §三附1（真 socket RST 探针 5/5） |
| 5 | `index.html:1424` | 错词重跑（rerunning 支）：「· 可离开本页面，稍后回来仍能看到进度（本版不提供中途强制取消）」 | **成立（实证）／边界如实** | 见 §三附2 |
| 6 | `index.html:1427` | 错词重跑（importing 支）：「· 可离开本页面，稍后回来仍能看到进度」 | **成立（实证）／边界如实** | 同上 |
| 7 | `index.html:1533` | 「后台任务进度读不到了，请点「刷新」重看」 | **成立** | 该出口只在 status 被 400/404/409 明确拒时触发（`:1571-1575`），此时后台 job 确已不可读 |
| 8 | `index.html:1563` | 「已停止自动刷新；后台任务可能仍在跑，请点「刷新」或稍后重开页面查看」 | **成立** | 连续失败/超时只停**本页轮询**，服务端 daemon 线程（`server.py:3747-3749`）不受影响；措辞用「可能」 |
| 9 | `index.html:1588 / 1639 / 1618 / 1628 / 1644` | 「后台任务已查不到（服务可能重启过…）」「…不属于本页数据目录，无法接管」 | **成立** | 均为「查不到／接不了」的如实描述，且都给出口 |
| 10 | `index.html:855 / 1895 / 1945` | 「长视频请勿关闭页面」 | **非本链新增**（HEAD `:851/:1706/:1756` 既有），保守建议不构成与事实相反的硬话 | 转写 worker 同为 daemon 线程，关页其实也不丢；属善意过度谨慎，**不计本轮账** |

**结论**：原 P2-1 的三处伪话（首条／逐条／`#batchLockHint`）**全部改对**；两处保留项经**独立实证**确认成立，不是「换个说法继续糊弄」。

### 附1｜`:1270` 同步语义：**我实测过，不是默认接受**（真 socket RST，5/5 PASS）

探针 `/tmp/p13rev2/probe_reapply_disconnect.py`：真起 `ThreadingHTTPServer`（**随机端口，非 8765**）＋真 `Handler`，`data_root` 为系统 tmp 合成目录（首行断言过门）；把 `_reapply_all` 包一层记录器（内含 1.2s 睡眠，**仅用于把窗口拉开使「客户端已死」可观测**），客户端 `SO_LINGER={1,0}` 发送 `POST /api/reapply {all:true}` 后**立刻 RST 断开、不回读任何字节**。实测：

```
客户端已发送并立刻 RST 断开（t+0.000s）
rec = {"t_start": …93.695, "ret": 200, "t_end": …94.905, "send_exc": "BrokenPipeError"}
```

- **t_end（94.905）晚于客户端断开 1.21s** → 活儿是在客户端死掉之后才跑完的；
- 回包阶段抛 `BrokenPipeError`，被 `server.py:6130`（`do_POST` 的 `except BrokenPipeError: pass`）吞掉，**不影响已完成的写盘**；
- 全仓 `wfile.write` **只有 2 处**（`_send_json:1369`、`_serve_index:1384`），即长任务执行期间**对 socket 零写、零探活**——不存在「客户端走了就中止」的机制。

⇒ **`:1270`「也可离开页面，后台会继续跑完」属实**，builder 的判断**接受**；与批量重试（页面内循环）性质相反，正是本次必须在文案上分开的那件事。

### 附2｜`:1424/:1427`：**成立**；builder 自陈的边界**属实**，但**不构成「同样不成立的软话」**（我判 **P3**，非 P2）

两道独立取证：

1. **异步 job 与连接解耦**（`probe_apply_disconnect.py`，真 HTTP，3/3 PASS）：提交 `POST /api/vocab/candidates/apply` 后立刻 RST → 服务端仍建了 job 并**自行跑到终态**（`done`），再用**新连接**（模拟「稍后回来」）`GET apply/status` 得 `HTTP 200 / job.state = done`。job 线程是 `daemon=True`（`server.py:3747-3749`），与提交连接无关 ⇒「可离开本页面」**实质成立**。
2. **冷启动边界**（`probe_coldstart.py`，复用仓内「抽真源码＋node 桩」，3/3 PASS）：
   - `①` 冷启动（`vocabApplyRunning=false`）＋后端 job **已跑完** → 进度行**内容为空**、**零 say**（`resumeVocabApplyPoll:1659` 的 `if(vocabApplyRunning)` 守卫所致）→ **builder 自陈「回来时若已跑完，页面不再显示这次重跑的汇总」逐字属实**；
   - `②` 对照：冷启动＋job **仍在跑** → 接管并显示「已处理 1/4 · 已用时 7s · **可离开本页面**…」（`:1648-1656`）→ **该句成立的那一半也实测成立**。

**裁定**：这句**不算**「同样不成立的软话」，理由三条——① 它**只在 `renderVocabApplyProgress`（任务运行中）渲染**，即「被显示时的状态」正是「它成立的状态」，不是对未来的许诺；② 承重的那半句（**可离开**）经实证成立，用户据它做「关页」决策**不会吃亏**；③ 不成立的只是**可见性**（跑完回来看不到这次汇总），而结果本身在任务列表/刷新即可见，**不会沉默丢事**。与 P2-1 原来的错（关页→剩余任务**永远不排队**，用户按文案决策会**丢事**）**不同量级**。
**建议（P3，不拦）**：把尾句收一格为「稍后回来仍能看到进度（若已跑完，结果在任务列表看）」，或与 `:1270` 统一成「回来刷新即可看任务状态」。代价＝一行文案。

### 附3｜`#batchLockHint` 整句摘掉「可离开」这个取舍：**可接受**（不必按链分叉）

- 事实核对：该句确由 `setCandidateControls` **一处写、三链共用**（`index.html:1359`；调用点 `:1185` 批量重试、`:1272` 重新成稿、`:1601/:1652/:1710` 错词重跑与接管），三链「能不能离开」结论**确实相反**（前已实证）。**同一句无法同时说真话**。
- 摘句后**真话没丢**：每条链自己的出口仍在——批量重试 `:1186/:1195`「需保持本页打开」（成立）、重新成稿 `:1270`「也可离开页面…」（实证成立）、错词重跑 `:1424/:1427`「可离开本页面…」（实证成立）。⇒ **单一真源按链落位**，比在一句共用提示里按链分叉更不容易再次说反。
- 若改为「按链分叉」（给 `setCandidateControls` 加 `canLeave` 参数）：代价＝**多一个入参＋4 个调用点改动**，且会把「能否离开」这个**进度语义**塞进一个**锁定语义**的提示里，两处各说一遍、将来容易漂移。**不划算**。
- **裁定：可接受，记为正面取舍**（不是将就）。唯一余留：尾句「进度条会显示已用时」→ **P3-新1**。

---

## 四、P2-2 是否真闭环：五问逐答

| # | 你要求判的点 | 判定 | 依据（行号／实测） |
|---|---|---|---|
| 1 | **409/400 是不是真能到用户眼前** | **是** | 单条：非 202 → `say("重试失败："+(x.o.error\|\|x.code))`（`:1119`）；批量：所有非 202 走 `noteBad((x.o&&x.o.error)\|\|("请求被拒（HTTP "+x.code+"）"))`（`:1221`），收尾 `say("…失败 N 个（原因见下方提示）")`（`:1201`）＋`recoverHint("本批有 N 个没排上（首个原因：…）。…可修正后重试。")`（`:1202`）。**实测**：仓内自测 `9c/9d/9e` PASS；我自己的证伪 **C**（把 `noteBad` 退回只 `badN++`）→ `9c/9d/9e` **三条同时挂、rc=1** ⇒ 回显链路真的承担了验收，不是摆设 |
| 2 | **本地门会不会误拦合法请求**（缺键／空串／监听态目录） | **不会** | 门只在 `root && !isAbsRoot(root)` 时返回 `null`（`:1103`），`root = typed \|\| learned`（`:1102`）。逐例：**两处都空**→`root=""`→**不拦**，`p={run_id}`（`:1104-1105`）→ 后端 `_take_data_root(params,"","data_root")` 得 `""` → `data_root = listener_root`（`server.py:5038-5048`）＝**沿用监听目录的旧行为**；**空串/纯空白**→`.trim()` 后为假 → 不拦；**框空但已学到生效目录**→用 `effectiveDataRoot`，绝对路径通过；**绝对路径（含尾斜杠/`..`/符号链接/目录不存在）**→本地放行，交后端按 realpath 判（`:5038-5045`）。**实测**：contract `10g` 断言空串仍 202；`9h`（目录合法照常 POST 且带 `data_root`）PASS；我的证伪 **E**（一刀切不带 `data_root`）被 `S8i×2＋9h` **咬住 rc=1** ⇒ 门没有过度修正 |
| 3 | **本地门与后端是否口径一致** | **一致（同口径，非逐字）** | 后端相对路径 400 文案＝`server.py:275`「数据目录须为绝对路径，请点浏览重选」；本地门用 `retryRootHint():1091`「数据目录须为绝对路径，请点「浏览」重选（或清空该框改用默认外置测试目录）」。**精确表述**：核心句「数据目录须为绝对路径」**逐字相同**，前端**多**「」括注与清空兜底——与既有 apply 侧口径同源（`:1617`、`:1694`），contract `10g:1706` 就钉这条子串。且本地门刻意**只拦**后端必 400 的「有值且非绝对」，**空值放行**——与后端「缺键/空串→旧行为」逐条对齐（`10g:1711` 钉住）。全页共 **3 个渲染变体**（retry 1＋apply 2），措辞同口径不同串，属**上一节已记的 backlog**（自陈 #6：不动共享 helper 是对的），**非本轮新增** |
| 4 | **错误文案是否脱敏**（不得吐真实绝对路径／内部异常） | **通过** | 前端只回显**后端已脱敏**的 `x.o.error`；后端的跨目录 409（`:5042-5045`）与相对路径 400（`:275`）**均为常量、零路径**（上一节 §六逐条核过，contract `10f` 亦断言"不回两个真实路径"）。回落文案是常量（「请求被拒（HTTP 409）」）；网络异常走 `noteBad("")` → 固定「请求没送达（网络中断）」（`:1190`），**不插值 `e`**。渲染口 `recoverHint:2116` 与 `say:1029` 均用 **`textContent`**（非 `innerHTML`）⇒ 无 XSS、无标签注入。仓内自测 `9c` 亦断言「回显不含真实数据目录」PASS |
| 5 | **`say` 截 120 字是否会截掉关键原因** | **不会** | `say` 确实 `slice(0,120)`（`:1029`），但**原因不经过 `say`**：原因走 `recoverHint`，而 `recoverHint`（`:2116`）**不截断**。逐条量过本轮的 `say` 文案长度（手数）：`:1186`≈57、`:1195`≈43、`:1201`≈31、`:1112/1178`≈48-51 字，**全 <120**；最长的原因串（409 那句≈62 字）＋前缀落进 `recoverHint` 后无截断。⇒ 关键原因完整可见 |

**边界如实（非问题）**：批量链**只留首个失败原因**（`badWhy`，`:1191`），其余只计数。因整批共用同一个 `data_root`，400/409 的原因对每条**同文**、逐条 404 亦同文 ⇒ 与「上一节 P2-2 建议＝记首个 error 回显」的处置一致，**接受**。

---

## 五、反向证伪抽查：**我自己动手做了 4 条**（builder 报的 4 项 A/B/C/D 我只复现 C/D 并另加 2 条）

做法：对真源码做**唯一锚点**替换 → 跑对应自测 → **要求 rc=1** → **整文件还原** → **sha256 必须与动手前一致**。判据**只用 rc 与 FAIL 行**，不用 builder 的断言当结论。

| 抽检 | 改回旧形态 | 实测 | 结论 |
|---|---|---|---|
| **A**（我加抽，P2-1 核心） | `index.html:1186` 首条文案退回「…可离开本页面，稍后回来仍能看到结果」 | `selftest_p1_2_frontend.py` **rc=1**，FAIL 三行：`9a 首条文案不承诺可离开`／`9a 首条文案明说需保持本页打开`／`9a 逐条进度文案同样不提可离开` | **有牙** ✔ 还原一致 ✔ |
| **C**（builder 报的同名项） | `noteBad` 退回只 `badN++`（原因不回显） | **rc=1**：`9c 后端人话原因落到首屏恢复区`（实测回显成「首个原因：）」）／`9d 404 也回显原因`／`9e 部分成功…失败原因仍回显` | **有牙** ✔ 还原一致 ✔ |
| **D**（builder 报的同名项） | 删掉 `retryBody` 里的本地前置门 `:1103` | **rc=1**：`9f 一个请求都不发`（实测发了 **2** 个）／`9f 人话口径同句`／`9f retryBody 回 null`（实测回 `{"run_id":"run-1","data_root":"relative/x"}`）／`9g 单条遇相对目录不发请求` | **有牙** ✔ 还原一致 ✔ |
| **E**（我加抽，防**过度修正**） | `retryBody:1105` 的 `if(root)` → `if(false)`（一刀切不带 `data_root`，P2-7 回归） | **rc=1**：`S8i 重试请求带本页数据目录`／`S8i 框留空时用生效目录`／`9h 对照：目录合法时…带 data_root` | **有牙** ✔ 还原一致 ✔ |

结论：新断言**不是自我实现的假信心**；`9a`（P2-1 文案）与 `9f/9c`（P2-2 两道门）确实咬住本轮两条修复的中心语义，且 `E` 证明修复**没有反向过度**（合法目录仍照常带 `data_root`）。**`app/index.html` sha256 与 builder 申报的 `a3735655…56f0` 逐字一致**（动手前=还原后=当前工作树，三处相同）。

---

## 六、范围与越界核查（Scope creep）

- **改动面**：`git status --porcelain` 只有 `M app/index.html`、`M app/server.py`、`M tests/selftest_p1_2_contract.py`、`M tests/selftest_p1_2_frontend.py` ＋未跟踪的本报告。**`docs/` 与 `src/` 零改动**；无新增未跟踪文件（除本报告）。
- **`server.py` 零改动已用哈希铁证**（§二）。
- **本轮 diff 落点逐条归 P2-1／P2-2**：P2-1＝`index.html:1186`、`:1195`、`:1356-1359`（含注释）；P2-2＝`retryRootHint:1088-1092`、`retryBody` 本地门 `:1096-1107`、`retryRun:1111-1112`、`retryAllFailed:1177-1181 / 1188-1192 / 1200-1208 / 1210-1215 / 1219-1223`；测试＝contract `10g`（`:1702-1712`）＋frontend `S9`（`:703-843`）＋挂链 `:847`。**未发现第三件事、未发现范围外改动**。
- **红线抽查**：主题默认浅色仍在位（`app/index.html:2` ＝ `<html lang="zh-CN" data-theme="light">`，字符串实测存在，未回退）；词库三铁律／No-Clobber／D-12 口径**本轮零接触**（server.py 字节未动；index 侧改动全在批量重试与共用锁定提示，未碰 `_validate_vocab_pair` 对应前端逻辑、未碰候选导入与发布路径）；未碰 secrets；未改任何封存物。
- 另记一句（非本轮问题）：`index.html:1119/1121`、`:1263/1281` 的 `.catch(function(e){…+e…})` 会把 JS 异常串进 `say`，但**该写法在 HEAD 版就有**（`HEAD:1094/1213`…），且 fetch 的 `Error` 串不含真实路径，**不计本轮账**。

---

## 七、自测是否「有牙」／只加不减／数据安全门

- **只加不减**（独立算术）：contract `312/0 → 323/0`＝**+11／−0**；frontend `185/1 → 341/1`＝**+156／−0**（**本轮删除数 0**；那个唯一的 `−1` 是首版留下的，不在本轮）。三套自测**全绿**（429／86 条 PASS／58）。新 `S9` 段**18 条**与 builder 自报的 `9a×5＋9b×2＋9b2＋9c×3＋9d＋9e＋9f×3＋9g＋9h` **逐条对得上**（我按前缀数过），且已**挂进主链**（`:847 await s8(); await s9();`，跑得出来才是证据）。
- **有牙**：见 §五（我抽 4 条，4/4 rc=1 且还原一致）。
- **数据安全门在位**：`part10` 首行三连断言 `assert_tmp(root_a/root_b/noroot)`（contract `:1443-1445`），`make_data_root` 内部亦过门（`:118`）；子块另有 `:1604`／`:1630`。我三条探针全部自建 tmp 合成夹具并**首行断言过门**，跑完自清（系统 tmp 无 `p13b_*` 残留）。
- 一处**精度说明**（非问题）：contract `10g` 的两条钉的是**后端旧行为**（相对路径 400 文案、空串放行），因 `server.py` 本轮字节未动，它对**前端**本地门不构成回归护栏——前端那道门的真护栏是 `selftest_p1_2_frontend.py` 的 `9f`（我已证伪验证有牙）。两条合起来才算「前后端同口径」的完整证据。

---

## P0 / P1 Findings

- **无 P0 阻断、无 P1 阻断。** P2-1 与 P2-2 经独立实跑＋自写探针＋自做反向证伪，**判定真闭环**：三套自测 rc 全 0（429／86 PASS／58）；四条证伪 4/4 有牙且还原 sha256 与 builder 申报值逐字一致；`server.py` 哈希与上一轮记录逐字相同（本轮后端 0 改动）；`:1270` 与 `:1424/:1427` 两处保留项**各有实证**（真 socket RST 5/5、异步解耦 3/3、冷启动边界 3/3）；本地门零误拦（缺键/空串/监听态目录均可），且有 `E` 证明未过度修正；409/400 实测能到用户眼前；脱敏与 `say` 截断均无问题；范围外改动 0。

## P2 / P3 Backlog Findings

- **P3-新1（本轮余留，非阻断，建议一行级顺手收）** `index.html:1359` 共用锁定提示尾句「**进度条会显示已用时**」只对**错词重跑**成立：会显示「已用时」的只有候选进度条 `candidateApplyProgress`（`vocabApplyElapsedText:1447`；主进度条要等被重排的任务真跑起来才由 `:850` 显示）。而**重新成稿链**（`reapplyAll:1272` 调用同一函数）既无该进度条也无该字段，用户会找不到「进度条」。属**指针类**措辞（不是承诺结果、不影响任何决策与数据安全），故判 **P3 而非 P2**。改法二选一：删尾句，或加范围限定「（错词重跑会显示进度条与已用时）」。*注：`#batchLockHint` 的 DOM 静态内容为空（`:236`），改文案无 HTML 侧连带。*
- **P3-新2（既有测试卫生，非本轮引入、不涉用户数据）** contract 套件在系统 tmp **留夹具不清理**：`tests/selftest_p1_2_contract.py:697`（`tempfile.mkdtemp(prefix="p12_baddb_")`，无 `finally`）与 `:916`（`bad = root + "-baddb"`），凡跑过一次即残留。实测跑完后系统 tmp 有 `p12_baddb_*`、`p12_A_*-baddb` 等（时间戳 09-14 23:48～09-15 00:56，早于本轮；另有 `p12_qa_empty_*`、`p13_fallback_*` 两族来自 QA/builder 的非仓内探针）。**不涉红线**（只在系统 tmp、纯合成），但会让「遗留 0 个」这句无法成立。建议下批顺手给这两处加 `finally` 清理，或收尾 neat-freak 一并处理。
- **上一节 Findings 的存量状态**（本轮只核 P2-1／P2-2，其余**一律不动、不重开**）：**P2-1 已闭环 ✔**、**P2-2 已闭环 ✔**；**P2-3（`_reapply_result_bucket` fail-closed 只做一半）与 P2-4（运行中 `/api/reapply`／`retry-batch` 无后端互斥）仍开**（上一节已判**非阻断**，留 backlog，不在本轮范围）；P3-1～P3-9 与 `#batchLockHint` 相关项原样挂在上一节。

## 回归结论

- **无倒退。** 本轮改动集中在批量重试链与共用锁定提示一处；`server.py` 字节未动（哈希铁证）⇒ 上一节核过的后端语义（严格取参、跨目录 409、候选版本锁、No-Clobber、`_FAIL_SEMANTICS`、五桶统计、fail-closed）**不可能被本轮改坏**。
- 三套自测 rc 全 0（429／86 PASS／58），`git diff --check` rc=0；主题默认浅色未回退；词库三铁律／No-Clobber／D-12 口径本轮零接触。
- 仓内 `/api/retry` 调用点仍是 2 个（`:1114`／`:1216`），**两处都已带原因回显**；`retryRootHint()` 全文**唯一定义、4 个调用点**（`:1112/1178/1179/1212`）⇒「人话只写死一处」属实；新增拒绝路径（本地门）**零请求**且**不产生任何写盘**。

## 未覆盖项（本复核未验，不得推断为通过）

1. **真机 UI 目检**：未起 8765、未点页面。本轮关于文案与 `noteBad`／本地门的结论＝「抽真源码＋node 桩＋我自写探针」，**不替代真机**。上一节对 QA 的补测要求（起服务后运行中实点三个批量按钮＋两个范围单选）**仍然有效**。
2. **真实 whisper／真实 61 篇量级／长视频 elapsed 数值**（属 P1-1 链）。
3. **真实 DB 可读时的 `/api/retry` 404 分支**（上一节自陈 #5 要求 QA 在 tmp 补一条真取证；本轮新文案恰恰会把该 404 原因显示出来，值得 QA 顺手验）。
4. **多标签页真并发**；**并发两次重跑的真实写盘竞争**（P2-4）——本轮未做注入级实验。
5. **`/api/failures/retry-batch` 与 `status` 的前端使用场景**（仓内无调用点）。
6. 用户真实视频目录与 Obsidian 库（红线禁写，未读未写）。

---

心跳：目标＝独立复核 DEVELOP-P1-3 返工（仅 P2-1／P2-2）并追加本报告｜结论＝**PASS（无 P0/P1；P2-1 与 P2-2 均真闭环，新增 0×P2＋2×P3）→ 放行去 QA**｜下一步＝交 qa（真机实点三批量按钮＋两范围单选；补「同目录 run 不存在→404」真取证，顺带验 404 原因已能显示）→ supervisor 复检；上一节 P2-3／P2-4 仍开但非阻断，留 backlog。

---

# 复核三｜DEVELOP-P1-3 返工（**只核 `QA-P13-P2-3-UNKNOWN-STATE`**）

- Task: **DEVELOP-P1-3「进度与批量语义修正」返工**（`CHANGE_REQUEST=A`；范围锁定＝独立 QA 报告 `docs/qa/P1-3-SEMANTICS-QA-2026-09-15.md` 唯一打回项 `QA-P13-P2-3-UNKNOWN-STATE`「两链判据不同源／未知 state 未 fail-closed」）。`QA-P13-P2-4-REAPPLY-MUTEX` 与其余 Findings **不在本轮，一律不动、不重开**。
- Commit: **未提交**（工作树）。基线 `HEAD=3af2da7`（实测）。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核；读盘顺序照 AGENTS→角色卡→override 表→HANDOFF→经验一句话→任务）
- Result: **PASS（无 P0／P1 阻断）→ 放行去 QA 复验**。QA 那条 **P2-3 真闭环**；**同意「已知合法成功态清单无漏项」**（依据见第四节）。本轮**新增 0×P0／0×P1**、**新增 1×P2（P2-三1，须修、一行级、不阻断）＋1×P3**；上一节的 P2-4 与 P3-1～P3-9 **原样仍开**（见 Findings 末条）。

> 复核口径：只读业务代码＋独立跑三套自测＋自写探针＋自己动手做反向证伪；**未改业务代码**（3 次反向证伪均为「改回旧形态→取证→整文件还原」，每次以 sha256 校验还原一致）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只追加本文件一节，**前两节正文一字未动**。
> 自写探针（全部落 `/tmp/p13rev3/`，未入仓）：`run.py`（反向证伪 3 条，自带 sha256 还原校验）、`probe_bucket.py`（两链同源／生产形状等价／静态无 `state` 键／出口字段名，10 项）。凡调 handler 的探针首行均断言 `data_root` 在系统 tmp 下。

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（439 项断言）`（含 `10a3` 段 10 条全 `PASS`） | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS`（`^PASS` 共 **86** 行） | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`^PASS` 共 **58** 行） | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/server.py app/index.html tests/selftest_p1_2_contract.py` | server `ee9b3613…ae60`、index `a3735655…56f0`、contract `355b70b5…a78a` | 0 |
| 6 | `python3 /tmp/p13rev3/probe_bucket.py`（我方独立探针） | **10/10 PASS**（含生产形状新旧归类逐条等价、成功态白名单实测） | **0** |
| 7 | `python3 /tmp/p13rev3/run.py`（我方反向证伪 3 条） | 3/3「改回旧形态即 **rc=1**」，3/3「还原后 sha256 一致」 | **0** |

builder 自报三项**全部对上**：三套自测 `439／FRONT／58` rc=0 ✔；`app/server.py` sha256 ＝ `ee9b36135db8ee65b810bbc73f322c69047cfd32f0937ebad7bf07f87fbdae60` **与当前工作树逐字一致** ✔；新增 10 条断言在 `10a3` **逐条数过，就是 10 条** ✔。

## 二、sha256 与增量对账：**「index.html 零改动」不是采信自报，是哈希铁证**

| 文件 | 复核二（上一轮）记录 | 本轮回测 | 反推本轮增量 | builder 自报 | 判定 |
|---|---|---|---|---|---|
| `app/index.html` | `231/32` ＋ sha `a3735655…56f0` | `231/32` ＋ **sha 逐字相同** | **0／0** | 零改动 | ✔ 铁证：**一个字节都没动** |
| `tests/selftest_p1_2_frontend.py` | `341/1` | `341/1` | **0／0** | （未申报） | ✔ 零改动 |
| `app/server.py` | `369/70` | `412/70` | **+72／−29（净 +43）** | +72／−29 | ✔ 逐字一致 |
| `tests/selftest_p1_2_contract.py` | `323/0` | `385/0` | **+62／−0** | +62/−0 | ✔ 逐字一致 |

- `412 = 369 + 72 − 29` 且**相对 HEAD 的删除数仍为 70** ⇒ 被删的那 29 行本身就是首版的插入行（返工是「就地重写一块」而非「删旧功能」），自洽。
- `git status --porcelain` 仅 `M app/index.html`／`M app/server.py`／`M tests/selftest_p1_2_contract.py`／`M tests/selftest_p1_2_frontend.py`（后二者本轮零改动）＋`M docs/model/DISPATCH-LOG.jsonl`（TM 补记 6 行派工，逐行读过，非业务）＋未跟踪的 QA 报告与本报告。

## 三、两链同源：**14 个已知 state 逐条一致、18 个表外 state 一律 failed**（我方探针实测）

| 探针断言 | 实测 |
|---|---|
| `STATE_BUCKET` 全部 **14** 个 state：`_RECOVERY_BUCKET_NAMES[_state_bucket(s)] == _recovery_bucket(s)` 且 `_reapply_result_bucket({"ok":True,"state":s}) == _state_bucket(s)` | **0 处不一致** |
| 18 个表外 state（`WEIRD_UNKNOWN/TYPO/DONE/SUCCESS/OK/RECOVERED/STILL_FAILED/PARTIAL/DONE_PARTIAL/V25_POSTPASS/WORKING/RUNNING/QUEUED/PUBLISH_ONLY/RETRANSCRIBE/REUSE_DERIVED/SCAFFOLD/PREPARED`）＋`ok=True` | **一律 `failed`**（QA 报的原反例 `{'ok':True,'state':'WEIRD_UNKNOWN'}` 实测 **`failed`**，`_recovery_bucket` 侧 `still_failed`，两链同语义 ✔） |
| 成功态白名单实测 | `== {"PUBLISHED","RENDER_ONLY","SUCCEEDED"}`（与 builder 自报 **3 个**一致） |
| **生产形状回归**：6 条 `_reapply_one`/`_reapply_all` 真实形状条目（`ok/skipped/skipped_user_edited`，**不带 `state` 键**） | 新实现与上一节 `:97` 记录的旧形态（标记优先＋`ok` 两桶）**逐条相同**；五桶 `total==Σ==6`、`balanced=True` |
| **静态**：`_reapply_one` 全部 **14** 个 `return {...}` 字面量、`result = {...}` 构建字面量，`_reapply_all` 全部 `return {...}` | **`"state"` 键 0 命中** ⇒ 存量重跑链**结构上不可能**产出 `state`（与 builder 自陈一致） |

⇒ 本轮改动对**现有生产数据的行为是零变更**（无 state 键 → 回落 `ok`，与旧实现等价）；只对「带 `state` 的条目」收紧，而唯一带 `state` 的链（批量恢复）其取值域已实测落在表内。

## 四、【关键裁定】已知合法成功态清单 **无漏项**（我独立穷举写入点）

做法：**不用 builder 的旁证**，改为穷举全仓所有会把字符串写进 `state` 字段的位置，再逐类判它会不会进两个 bucket 函数。

| 写入点 | 可产出的 `state` | 会不会进 bucket 函数 | 是否成功态 | 表内？ |
|---|---|---|---|---|
| `_exec_retranscribe:2073-2093` | `FAILED`／`NEEDS_HUMAN` | 会（恢复链 `job["results"]`） | 否 | ✔ |
| `_exec_reuse_derived:2096-2108` | **`SUCCEEDED`**／`SKIPPED`／`FAILED` | 会 | **是（唯一）** | ✔ 在表 |
| `_exec_publish_only:2111-2215` | **`SUCCEEDED`**／`FAILED`／`SKIPPED`／`NEEDS_HUMAN` | 会 | **是（唯一）** | ✔ 在表 |
| `_retry_batch` worker 门失败／执行异常 `:2318／:2346` | `NEEDS_HUMAN`／`FAILED` | 会 | 否 | ✔ |
| `_scan_disk_states:928-991`（**归一后**输出） | `RENDER_ONLY`／`PUBLISHED`／`PUBLISH_BLOCKED`／`FAIL` | 间接（是 `_reapply_one`/`_reapply_all` 的输入源，但其输出**只经 `REAPPLY_ELIGIBLE` 过滤**，不进 bucket 函数） | 前两个是 | ✔ 全在表 |
| `_process_one_run` 工作线程 `:4653／:4678-4681／:4689／:4700／:4516／:4552／:4578／:4638` | `RENDER_ONLY`／`PUBLISHED`／`PUBLISH_BLOCKED`／`FAIL`／`TRANSCRIBE_FAILED`／`RAW_FAILED`／`MIRROR_FAILED`／`NORM_RENDER_FAILED` | **不进**（走内存 `_worker["processed"]`＋manifest receipt，供 `/api/status` 映射） | 前两个是 | ✔ 全在表 |
| `_reapply_one` 内存终态 `:5907-5915` | `new_state or prev_state` ∈ `{PUBLISHED, RENDER_ONLY, PUBLISH_BLOCKED}` | **不进**（同一内存通道） | 是 | ✔ 在表 |
| `src/stage1|11`（`SCAFFOLD`／`PREPARED`）、`_handle_retry_post` 回包（`RUNNING`／`QUEUED`）、async apply job（`running`／`done`／`failed`） | 各字面量 | **不进**（回包/job 级状态机，非逐项归档） | 否 | 不需要在表 |

**结论（同意无漏项）**：

1. **能进入两个 bucket 函数的 `state` 取值域 = `_exec_*` 的 4 个态 ∪ 磁盘归一后的 4 个态 ∪ 历史 job 文件里的同族值**，成功侧**只有 `PUBLISHED／RENDER_ONLY／SUCCEEDED` 三个**——表里都有，**无漏项**；反向也无多判：失败家族（含四个 manifest 细分失败态 `TRANSCRIBE_FAILED/RAW_FAILED/MIRROR_FAILED/NORM_RENDER_FAILED`）与跳过（**`SKIPPED`＋`SKIP` 两套拼写都收**）都各归各桶。
2. **「`PUBLISH_ONLY` 只是 strategy 不是 state」——独立核实成立**：`grep -rhoE '"(state|strategy)": *"(PUBLISH_ONLY|RETRANSCRIBE|REUSE_DERIVED)"' app/server.py` → `strategy` 11／4／3，**`state` 0 命中**；`grep -rn 'state": *"(PUBLISH_ONLY|RETRANSCRIBE|REUSE_DERIVED)"' app/ src/ tests/` 全仓 0 命中；连**全 git 历史** `git log --all -S'"state": "PUBLISH_ONLY"'` 也是空。⇒ 把它们排除在成功表外**不是过度修正**，**无反例**。
3. 补一条 builder 未提的旁证/隐患（**P3**，先记不修）：仓里还有第 5 个「成功语义」的 receipt 态 **`V25_POSTPASS`（`server.py:4612`）**，它同样**不进** bucket 函数（`_scan_disk_states` 只输出归一后的 4 个值），故不入表不影响本链；但它正是「`_scan_disk_states` 对未知 raw state 静默丢弃」那一处的具体触发值——**若日后把该处改成查表 fail-closed，必须同时决定 `V25_POSTPASS` 的归属**，否则会把「后处理已完成、只差写 RENDER_ONLY receipt 时崩过」的任务误标 FAIL。另外 DB 行级状态 `SUCCEEDED`（`:1603`）在表内 ✔。

## 五、反向证伪：**我自己动手做了 3 条**（含防过度修正的那条）

做法：对真源码做**唯一锚点**替换 → 跑自测 → **要求 rc=1** → **整文件还原** → **sha256 必须与动手前一致**。判据**只用 rc 与 FAIL 行**，不用 builder 的断言当结论。

| 抽检 | 改回旧形态 | 实测 | 结论 |
|---|---|---|---|
| **A**（退回 `ok` 优先，QA 那条 bug 的原形态） | `_reapply_result_bucket` 的 `if str(item.get("state") or "").strip():` → `if False:` | `contract` **rc=1**，FAIL 6 行：`10a 跳过/待人工/中断各归各桶`、`10a 未知 state/坏条目 fail-closed`、`10a 对照：旧口径`、`10a3 全部已知 state 两链同源`、`10a3「有牙」①ok=True＋未知 state 判 failed`、`10a3 掺入未知 state 后仍可复算` | **有牙** ✔ 还原一致 ✔ |
| **B**（**防过度修正**，本轮最关键）：`_state_bucket` 恒回 `BUCKET_FAILED` | `return STATE_BUCKET.get(...)` → `return BUCKET_FAILED` | `contract` **rc=1**，FAIL 含 `10a3「有牙」②：已知合法成功态仍算 success（防过度修正）`（`('PUBLISHED','RENDER_ONLY')`）、`10a 跳过/待人工/中断各归各桶`、`10a2 批量恢复五桶可复算`、`10b 未落盘剩余目标记中断` | **有牙** ✔ 还原一致 ✔ |
| **C**（判断单点被破） | `_recovery_bucket` 的派生体 → 退回自写 `if ... == "SUCCEEDED"` if 链 | `contract` **rc=1**，FAIL 含 `10a3 判据单点：两个 bucket 函数都从 _state_bucket 派生`、`10a3 旧形态特征已清零`、`10a3 全部已知 state 两链同源`、`10a2 批量恢复五桶可复算` | **有牙** ✔ 还原一致 ✔ |

结论：新断言**不是自我实现的假信心**；`A`（QA 那条原反例）与 `B`（**防过度修正**，我特意要求必做的那条）都确实咬住中心语义，且 A/B 是**方向相反**的两侧——说明修复既没继续 fail-open、也没矫枉成一律失败。还原后 `app/server.py` sha256 ＝ 动手前 ＝ builder 申报值（三处同一）。

## 六、真源是否真唯一

- `STATE_BUCKET = {` 全文**唯一一处**赋值（我方独立计数 = 1，与 `10a3` 断言同源不同实现）；无第二张表、无第二处 `_state_bucket` 定义。
- 两条 bucket 函数体内**都必须经 `_state_bucket(`**：`_recovery_bucket:1798-1800` 只有一行 `return _RECOVERY_BUCKET_NAMES[_state_bucket(state)]`；`_reapply_result_bucket:5570-5588` 的 state 分支 `return _state_bucket(item.get("state"))`。函数体内**已无 state 字面量 if 链**（`10a3 旧形态特征已清零` 断言 + 我读原文确认）。
- 全仓其余「按 state 归类」的 8 处（`_scan_disk_states:962-986`、`_listener_snapshot:1264-1267`、`_clear_plan` 的 `_run_failed/_run_done:2629-2639`、`_scoped_runs_summary:2805-2817`、`_stage_text_zh:2913-2918`、`_handle_note:5470-5490`、`_diagnosis_item._FAIL_SEMANTICS:1613`、`app/index.html:378 statusCN`）**与 `STATE_BUCKET` 的映射方向逐一核对，无一处与表冲突**（`DONE_STATES/FAIL_STATES` 同源；其余是 `FAIL/PUBLISH_BLOCKED/...` 同族字面量复用）。⇒ 它们是**重复字面量（可维护性）**，不是**独立判据（语义冲突）**，判 **P3**（见 Findings）。
- 唯二「不经表」的 bucket 赋值：`_recovery_job_read:2387-2402` 两处兜底硬编码 `total=1/counted=1/interrupted=1`（job 文件读不出来、**没有逐项可归类**时的兜底，方向 fail-closed，不冒充成功）⇒ 可接受，但「唯一真源」在**字面**意义上不覆盖这两行，记 **P3-三2** 一句。

## 七、边界口径裁定（我实测的，不是采信自陈）

| 输入 | `_reapply_result_bucket`（实测） | `_recovery_bucket`（实测） | builder 自陈 | 裁定 |
|---|---|---|---|---|
| **缺 `state` 键** `{"ok":True}` | **`success`** | `still_failed`（该链无 state 即 None） | 「回落 `ok`」 | **接受且必要**：存量重跑结果结构上不带 `state`（第四节静态证明 0 命中），若不回落 `ok`，**全部正常重跑都会被误判 failed**（过度修正）。两链「无 state」默认值不同**不是同源缺口**：两条链的输入契约本就不同（恢复链条条必带 state，重跑链条条不带）。 |
| **`state=""`（空串）／`"   "`（纯空白）／`state=None` 显式存在＋`ok=True`** | **`success`**（`or ""`＋真值判断把「空/全空白」与「缺键」**当同一种**） | `still_failed` | 「`state=""`→**failed**（按 fail-closed）」 | **builder 自陈与代码不符 → P2-三1**（见下）。方向是**窄口 fail-open**（不会误伤正常成功；只在「条目显式带了个坏 state」时判成成功）。 |

**P2-三1（须修，一行级，判定为不阻断）**：`app/server.py:5586` 的 `if str(item.get("state") or "").strip():` 把「`state` 键存在但值为空串/纯空白/None」与「压根没给 `state`」**混为一类**，于是 `{"ok":True,"state":""}` → `success`，而 `_recovery_bucket("")` → `still_failed`（`_state_bucket("")` → `failed`）——**两链在「显式给了个空/坏 state」这一形态上仍不同源**，与本链 DoD「未知 state／坏条目 fail-closed」的**字面**要求仍有缝；且 builder 申报的边界（「`state=""`→failed」）**与实测相反**，属**自陈失实**（不是谎报行为变更，是没实测该分支）。
改法（一行，改判据不改值）：把「是否有 state」的判据从「去空白后非空」改成「键存在且非 None」，例如

```python
if item.get("state") is not None:            # 显式给了 state（含空串）→ 一律以 state 为准
    return _state_bucket(item.get("state"))  # 空/空白/未知 → failed（fail-closed）
```
并补一条断言 `_reapply_result_bucket({"ok":True,"state":""}) == "failed"` 与 `== _RECOVERY_BUCKET_NAMES` 同源对照。
**为何仍判 PASS 不阻断**：① 该形态**今日不可达**——我已穷举全仓写入点（第四节表），没有任何运行路径会产出「带 `state` 的条目」，更没有会产出空/空白 `state` 的路径；② 方向是「更宽容」而非「更危险」：不存在「正常成功被误判失败」的风险，只有「一个不存在的坏条目被当成功」的**理论**风险；③ QA 那条原反例（`WEIRD_UNKNOWN`，非空）已实测 `failed`，**QA 报告的打回理由已消除**。故不构成放行阻断，但**建议本批一并修**（成本＝一行＋一条断言），以免 QA 用 `state=""` 再打回一轮。

## 八、契约、范围、红线与数据安全

- **契约不破**：五桶 `total==Σ`、`balanced` 实测（`10a`／`10a2`／`10b` 全 PASS；我方探针 6 条真实形状 `total==Σ==6/balanced=True`）。**出口字段名**：`_REAPPLY_BUCKETS == FIVE_BUCKETS == ("success","failed","skipped","needs_human","interrupted")`；`RECOVERY_BUCKETS == ("recovered","still_failed","skipped","needs_human","interrupted")`——**值与相对顺序逐字不变**（旁证：`_handle_retry_batch_post` 引导 dict `:2289-2296`、`_recovery_job_read` 兜底 dict `:2387-2400` 的键序与 `docs/pm/PRODUCT_PLAN.md:147` 的 Requirement 键序**三处一致**）。`RECOVERY_BUCKETS` 的**顺序无任何消费方**（前端按 key 读、`_recovery_apply_counts` 用 `job.update`），故顺序即使有变化也不可观测；**值**已两侧核对。
- **前端出口未变**：`app/index.html` 本轮**字节零改动**（sha256 与上一轮记录逐字相同），前端 `:1457-1458` 仍按 `needs_human/interrupted` 等**键名**读取，键名/语义均未变。
- **范围**：本轮只碰 `app/server.py`＋`tests/selftest_p1_2_contract.py`；`docs/`（除 TM 两账本与两份报告）、`src/`、`app/index.html` **零改动**。
- **红线零接触**：主题浅色（`app/index.html:2`）本轮字节未动；词库三铁律／No-Clobber／D-12 口径——累计 diff 扫描：`_validate_vocab_pair`／`REAPPLY_ELIGIBLE`／`initial_publish`／`_reapply_one` 正文／`raw_unchanged`／`_recovery_gate_ok`／`_FAIL_SEMANTICS`／`_vocab_base_patterns` **新增/删除行 0 命中**（`_reapply_one` 正文区间 5590-5938 **不在任何 hunk 的 new-side 范围内** ⇒ 整条链都没动过它，No-Clobber 与 Raw 不变断言原样）；D-12 新增 **412** 行逐行扫 `/Users|/home|/private|/var|/Volumes|/Applications|/tmp` → **0 命中**；未碰 secrets、未改封存物。
- **测试卫生**：新增断言**只加不减**（contract `323/0 → 385/0`，删除 0；frontend `341/1` 本轮未动）；`part10` 首行三连 `assert_tmp`（`:1443-1445`）在位、`10a3` 不调 handler 也不需要新夹具；我跑完系统 tmp **无新增** `p12_*／p13_*` 残留（沿用上一节已记的 **P3-新2**：`part9` 两处夹具仍泄漏，非本轮引入）；测试内出现的 `data_root` 全部在 `/var/folders/.../T/` 下。

## 九、builder 九处「各写一套」清单：我抽检 5 处，**描述全部准确**

| # | 点位 | 我的独立核对 | 判定 |
|---|---|---|---|
| 1 | `_scan_disk_states:928-991` 对未知 raw state **fail-open 丢弃** | 原文 `:966`（成功只认 `RENDER_ONLY/PUBLISHED`）、`:981-986`（失败只认 5 个细分态并映射 `FAIL`），**其余 `state` 直接不落 `out`** ⇒ 描述准确；具体触发值就是 `V25_POSTPASS`（第四节 3） | **P3** |
| 2 | `_listener_snapshot:1264` | `done_n` 用 `DONE_STATES`、`failed_n` 用 `FAIL_STATES`（`:1264-1267`），与表同源不冲突 | **P3** |
| 3 | `_clear_plan:2629` | `_run_failed`＝`FAIL_STATES` ∨ DB `FAILED*`／`NO_SPEECH_DETECTED`；`_run_done`＝`DONE_STATES`（`:2629-2639`），不冲突 | **P3** |
| 4 | `_scoped_runs_summary:2805` | `bucket` 三分类用 `DONE_STATES`／`FAIL_STATES`＋DB 前缀兜底（`:2805-2817`），不冲突 | **P3** |
| 5 | `_diagnosis_item._FAIL_SEMANTICS:1613` 与 `FAIL_STATES` 不相等 | 实测集合＝`{FAIL,PUBLISH_BLOCKED,TRANSCRIBE_FAILED,RAW_FAILED,MIRROR_FAILED,NORM_RENDER_FAILED}`（6 项）≠`FAIL_STATES`（2 项）⇒ **描述准确**；但域不同（比对的是 **DB 行级 status**，不是 job 逐项 state），且与表的失败家族**同族**，非语义冲突 | **P3** |
| （另核） | `_transcribe_worker:4746`（`DONE_STATES` 跳过已完成）、worker 侧 `SKIP` vs 恢复链 `SKIPPED`、`index.html:378 statusCN` | 前两处原文在位准确；`SKIP`/`SKIPPED` **两套拼写表里都收**（`:1771-1772`）；`statusCN` 认 `PUBLISHED/RENDER_ONLY/FAIL/PUBLISH_BLOCKED`（`:390-393`），与表一致——**且 index.html 本轮字节未动** | **P3** |

**裁定**：这 9 处**全部判 P3，不属本链必修**（同意 TM 的「本次只修 P2-3，其余只列」）。理由：它们**今天与 `STATE_BUCKET` 的映射方向一致、无冲突判据**，属「重复字面量／可维护性」而非「语义分叉」；唯一带真实（虽窄）后果的是第 1 条（崩溃窗口内任务从完成/失败计数里静默消失，**无数据丢失**、No-Clobber 不受影响，DB 侧会显示为排队），建议进 backlog 并**与 `V25_POSTPASS` 归属同批处理**。

## P0 / P1 Findings

- **无 P0 阻断、无 P1 阻断。** QA 打回的 `QA-P13-P2-3-UNKNOWN-STATE` 经独立实测**真闭环**：原反例 `{'ok':True,'state':'WEIRD_UNKNOWN'}` → `failed`，与 `_recovery_bucket` 同语义；14 个已知 state 两链逐条同源；18 个表外 state 一律 `failed`；生产形状（无 `state`）与旧口径**逐条等价**（零行为变更）；三套自测 rc 全 0（439／86 PASS／58）；3 条反向证伪 A/B/C 全部 rc=1 且还原 sha256 与 builder 申报值逐字一致；`index.html` 与 `selftest_p1_2_frontend.py` 本轮字节零改动（哈希铁证）；「成功态无漏项」与「`PUBLISH_ONLY` 只作 strategy」两条**独立复核成立**；真源唯一性（单表单函数）成立；D-12 新增 412 行 0 命中；范围外改动 0。

## P2 / P3 Backlog Findings

- **P2-三1（须修，一行级，非阻断）** `app/server.py:5586` 把「`state` 键存在但为空串/纯空白/None」与「缺 `state` 键」当同一种 → `{"ok":True,"state":""}` 得 `success`，而 `_recovery_bucket("")` 得 `still_failed`，**两链在「显式空/坏 state」形态上仍不同源**；且 builder 自陈「`state=""`→failed」**与实测相反**（自陈失实）。改法与理由见第七节。**今日不可达**（全仓无任何写入点产出带 `state` 的条目），故不阻断放行；**建议本批一并修**（一行＋一条断言），避免 QA 以 `state=""` 再打回。
- **P3-三1（继承+细化，不属本链）** `_scan_disk_states:962-986` 对未知 raw state **静默丢弃（fail-open）**；具体触发值 `V25_POSTPASS`（`:4612`）。若日后改 fail-closed 查表，**须同时决定 `V25_POSTPASS` 归属**，否则会把「后处理已完成、仅差 `RENDER_ONLY` receipt」的任务误标 `FAIL`。无数据丢失；No-Clobber 不受影响。
- **P3-三2（新，口径，不阻断）** `_recovery_job_read:2387-2402` 两处兜底**硬编码** `total=1/counted=1/interrupted=1`，不经 `_state_bucket` ⇒ 「唯一真源」在**字面**上不覆盖这两行（语义上无逐项可归类，方向 fail-closed，可接受）。若要把「唯一真源」写成硬约束，宜把这两处也表述为「无逐项可归类时的兜底单位」。
- **上一节 Findings 的存量状态**（本轮只核 P2-3，其余**一律不动、不重开**）：**P2-3 已闭环 ✔**、P2-1／P2-2 已闭环 ✔；**P2-4**（运行中 `/api/reapply`／`retry-batch` 无后端互斥）**仍开**（上一节判非阻断，留 backlog）；P3-1～P3-9、P3-新1、P3-新2 原样挂着；QA 报告另开的 `QA-P13-P2-4-REAPPLY-MUTEX`（既有残留）与 P2-三1 无关，仍在 backlog。

## 回归结论

- **无倒退。** 本轮改动集中在两个 bucket 函数与一处新真源表；对**现有数据形状**（存量重跑结果不带 `state`；恢复链结果只取 4 个态）**行为等价**（我方探针逐条比对旧口径），五桶等式在两条链上均成立。
- 三套自测 rc 全 0（439／86 PASS／58），`git diff --check` rc=0；`app/index.html`／`tests/selftest_p1_2_frontend.py` 本轮 sha/numstat **零变化**；主题默认浅色未回退；词库三铁律／No-Clobber／D-12 零接触；`_reapply_one` 正文不在任何 hunk 内（No-Clobber 与 Raw 不变断言动都没动）。
- 出口契约：五桶键名与 `RECOVERY_BUCKETS` 值**逐字未变**，前端零改动即证明消费侧未破。

## 未覆盖项（本复核未验，不得推断为通过）

1. **真机 UI 目检**：未起 8765、未点页面（本轮为纯函数语义修复，前端零改动）。上一节对 QA 的补测要求（批量按钮＋两范围单选实点）**仍然有效**。
2. **真实 whisper／61 篇量级／长视频 elapsed 数值**（属 P1-1 链）。
3. **真实 DB 可读时的 `/api/retry` 404 分支**（上一节自陈 #5 要求 QA 在 tmp 补真取证）。
4. **多标签页真并发**、并发两次重跑的真实写盘竞争（P2-4／QA-P13-P2-4）——本轮未做注入级实验。
5. 用户真实视频目录与 Obsidian 库（红线禁写，未读未写）。

---

心跳：目标＝独立复核 DEVELOP-P1-3 返工（仅 `QA-P13-P2-3-UNKNOWN-STATE`）并追加本报告｜结论＝**PASS（无 P0/P1；该 P2-3 真闭环、成功态清单无漏项）→ 放行去 QA 复验**，新增 1×P2-三1（一行级、须修不阻断）＋2×P3｜下一步＝交 qa（复验 `{'ok':True,'state':'WEIRD_UNKNOWN'}`→failed 与两链同源；顺带补上一节要的「同目录 run 不存在→404」真取证）→ supervisor 复检；建议 builder 顺手把 P2-三1 的判据改一行并补断言。

---

# 复核四｜DEVELOP-P1-3 返工（**只核 P2-三1 ＋ 顺带修的 P3-新1**）

- Task: **DEVELOP-P1-3「进度与批量语义修正」返工**（`CHANGE_REQUEST=A`；范围锁定＝本报告**复核三 · P2-三1**（`state` 空值口径：`app/server.py:5586` 判据旧写法把「键在但值为空/坏」与「压根没给键」混为一类）＋**复核二 · P3-新1**（`index.html:1359` 共用锁定提示尾句「进度条会显示已用时。」越界）。其余 Findings（P2-4、P3-1～P3-9、QA 的 `QA-P13-P2-4-REAPPLY-MUTEX` 等）**一律不动、不重开**。
- Commit: **未提交**（工作树）。基线 `HEAD=3af2da7`（实测，与上一节一致）。
- Reviewer: code-reviewer（`opencode/muse-spark-1.3-contributor-free`，本窗口 subagent 独立复核；读盘顺序照 AGENTS→角色卡→override 表→HANDOFF→经验一句话→任务）
- Result: **PASS（无 P0／P1 阻断）→ 放行去 QA 复验**。P2-三1 **真闭环**、P3-新1 **真闭环**；**裁定采纳 `if "state" in item:`，我复核三给的 `is not None` 建议作废**（builder 的偏离正确，理由见第三节）。本轮**新增 0×P0／0×P1／0×P2**、新增 3×P3（含一条**勘误：撤 P3-新2**）。上一节存量 P2-4／P3 全部原样仍开。

> 复核口径：只读业务代码＋独立跑三套自测＋自写 AST 探针＋自己动手做反向证伪；**未改业务代码**（4 次反向证伪均为「改锚点→取证→整文件还原」，每次以 sha256 校验还原一致）；未起 8765、未请求线上服务；用户真实视频目录与 Obsidian 库零写；本次只追加本文件一节，**前三节正文一字未动**。
> 自写探针（全部落 `/tmp/p13rev4/`，未入仓）：`probe_state.py`（AST＋运行期 17 项，含「生产形状是否会被过度修正」的独立静态证明）、`run.py`（反向证伪 4 条，自带 sha256 还原校验）。两条探针均不调 handler（故不涉 `data_root` 断言）；未在系统 tmp 留下夹具。

## 一、我自己跑过的命令与退出码（实跑证据，非转述）

| # | 命令 | 实测输出 | rc |
|---|---|---|---|
| 1 | `python3 tests/selftest_p1_2_contract.py` | `SELFTEST ALL PASS（445 项断言）` | **0** |
| 2 | `python3 tests/selftest_p1_2_frontend.py` | `FRONT ALL PASS` ＋ `FRONT SELFTEST PASS`（`^PASS` 共 **87** 行） | **0** |
| 3 | `python3 tests/selftest_v26_presets.py` | `SELFTEST ALL PASS`（`^PASS` 共 **58** 行） | **0** |
| 4 | `git diff --check` | 无输出 | **0** |
| 5 | `shasum -a 256 app/server.py app/index.html` | server `433dd62c…f14b`、index `858080fc…d38c` | 0 |
| 6 | `python3 /tmp/p13rev4/probe_state.py`（我方独立探针：运行期＋AST） | **17/17 PASS** | **0** |
| 7 | `python3 /tmp/p13rev4/run.py`（我方反向证伪 4 条） | 4/4「改回旧形态即 **rc=1**」，4/4「还原后 sha256 一致」 | **0** |
| 8 | 还原后**复跑**三套自测＋`git diff --check` | `445`／`FRONT SELFTEST PASS`／`ALL PASS`，check rc=0 | **0** |

builder 自报**五项全部对上**：自测 `445／87／58` rc=0 ✔；contract 断言 `439→445`（**+6**，我在 `10a4` 段逐条数过就是 6 条：`:1509/1511/1514/1519/1523/1561`）✔；前端 `86→87`（新增 `9b1` 一条）✔；`app/server.py` sha256 ＝ `433dd62c414412d5ce4b941bb8b017a7f6a067260d5fb62ea211bd952657f14b` ✔、`app/index.html` ＝ `858080fcd406e13e9734c25a3bd8a969ae4f7b8b0af3c8f2481fe85c91d4c38c` ✔（两处与当前工作树**逐字一致**）。

## 二、增量对账：净量与**落点**双向核过（不采信自报）

| 文件 | 复核三（上一轮）记录 | 本轮回测 | 反推本轮增量 | builder 自报 | 判定 |
|---|---|---|---|---|---|
| `app/server.py` | `412/70` ＋ sha `ee9b3613…ae60` | `416/70` ＋ `433dd62c…f14b` | **净 +4**（= `416−412`） | `+8／−4` | **净量对上**（拆分见下） |
| `app/index.html` | `231/32` ＋ sha `a3735655…56f0` | `232/32` ＋ `858080fc…d38c` | **净 +1** | `+4／−3` | **净量对上** |
| `tests/selftest_p1_2_contract.py` | `385/0` | `413/0` | **+28／−0** | （未申报） | ✔ 删除 0 |
| `tests/selftest_p1_2_frontend.py` | `341/1` | `346/1` | **+5／−0** | （未申报） | ✔ 删除 0（那唯一的 `−1` 是首版遗留） |

**「增量全部落在哪」不是推算，是可核的落点**：

- `server.py`：`def _reapply_result_bucket` **定义行 5570 一字未漂**（上一节 §六 记的就是 `_reapply_result_bucket:5570-5588`），本轮函数体尾部 **5588 → 5592（+4）**，判据行 **5586 → 5590（+4）** ⇒ **本轮全部净增量集中在这一个函数体内**（注释＋docstring），函数以上与以下的其它函数行号漂移量同源一致。这与「`+8／−4`（换掉旧注释/文档串 4 行、写入 8 行）」唯一自洽。
- `index.html`：`batchLockHint` 行 **1359 → 1360（+1）**（上一节 P3-新1 记的就是 `:1359`），而该行内容本身是 **1:1 改写**（删尾句）⇒ 净 +1 只能来自其**上方注释**：复核二记录的该处注释为 `:1356-1358` **3 行**，现为 `:1356-1359` **4 行** ⇒ 注释 `3→4` ＋文本行 1:1 ＝ **`+4／−3`**，与 builder 自报**逐字一致**。

## 三、【关键裁定】`if "state" in item:` **采纳**；我上一轮的 `is not None` 建议**作废**

**结论：采纳 builder 口径（`if "state" in item:`，即「键存在就以它为准」）。我复核三 §七 建议的 `if item.get("state") is not None:` 在 `None` 一档会与恢复链分叉，属我的建议有洞，builder 的偏离正确。**

实测三条（`/tmp/p13rev4/probe_state.py`，判据全部来自真源码运行，不采信 builder 断言）：

| 输入 | `"state" in item`（**现行**） | `is not None`（我上轮建议） | `_recovery_bucket(x)` | 是否同源 |
|---|---|---|---|---|
| `{"ok":True,"state":None}` | **failed** | **success**（回落 `ok`） | `still_failed` | 现行 ✔ ／ 建议 ✘ |
| `{"ok":True,"state":""}` | **failed** | failed | `still_failed` | 两者 ✔ |
| `{"ok":True,"state":"   "}`（及 `"\t\n"`） | **failed** | failed | `still_failed` | 两者 ✔ |
| `{"ok":True,"state":"WEIRD_UNKNOWN"}` | failed | failed | `still_failed` | 两者 ✔ |
| `{"ok":True,"state":"PUBLISHED"}` | **success** | success | `recovered` | 两者 ✔ |
| `{"ok":True}`（**缺** `state` 键） | **success** | success | （恢复链条条必带 `state`，不适用） | 两者 ✔ 不误伤 |

**你要我核清的三件事，逐条给结论：**

1. **① 三种显式空现在落哪、与 `_recovery_bucket` 是否真同源**：三种（`None`／`""`／`"   "`）**全部落 `failed`**，且 `_RECOVERY_BUCKET_NAMES[_state_bucket(x)] == _recovery_bucket(x)` 实测**逐条成立**（含 `"\t\n"`）⇒ **真同源**（根因：`_state_bucket` 自己用 `str(state or "").strip()` 归一，`None` 与 `""` 在真源里本就等价，故「键存在」这一判据恰好把三者一致地喂进表）。**反例代价（为何不能采我的建议）**：若用 `is not None`，`{"ok":True,"state":None}` 会回落 `ok`→`success`，而恢复链同形态是 `still_failed` ⇒ **我把「同源」修成一半，在 `None` 这一档重新造出分叉**。
2. **② 缺 `state` 键的正常成功是否仍 success（不许误伤）**：**仍 success**，且我用 **AST** 做了独立静态证明（不是 grep）——`_reapply_one` 的 **20 个结果条目键**（`ok/run_id/source_filename/skipped/skipped_user_edited/error/new_state/note/...`）中 **`"state"` 0 命中**（注意 `new_state` 是**另一个键**）；该函数里带 `"state"` 的 6 个 dict 字面量（`:5820/:5851/:5873/:5885/:5896/:5912`）**全部是 manifest 收据或 `_worker["processed"]` 条目，都不进 `results`**；`_reapply_all` 的条目 **0 命中**。下游调用点只有 `_reapply_stats(results, total=…)`（`:3550` 取自 `_reapply_all` 的 `results`、`:5995`）⇒ **生产形状上 `"state" in item` 恒为假**，判据改动对存量数据**零行为变更、零误伤**。builder 的偏离方向是「把理论坏条目收紧」，不动真实成功。
3. **③ 有没有第三种写法更优**：**没有，现口径即为最小正确解。** 逐一试过：`item.get("state", _MISSING) is not _MISSING` 与 `"state" in item` **完全等价**（只多一个哨兵常量）；`"state" in item or item.get("state") is not None` 属冗余；唯一能连「缺键」那一档也强行同源的做法是**给 `_recovery_bucket` 加 `ok` 回落**——那会改坏恢复链「条条必带 `state`」的输入契约，是**过度修正**（且 A2 证伪已证明「缺键也走表」会被断言咬住，见第五节）。⇒ **裁定：现口径可接受，不要求第三种写法。**

**顺带结掉上一轮的两笔账**：① builder 上一轮自陈「`state=""`→failed」与当时代码相反（自陈失实）——**现在代码与该句一致了**（本轮修复结果），该失实项随之消灭；② 我上一轮点的改法（建议 `is not None`）**由我撤回**，本轮不据此提任何返工。

## 四、P3-新1 是否真闭环：**真闭环**（尾句删净、锁定真话仍在、单链真话没丢）

1. **尾句删净**：`app/index.html:1360` 全文以「……本次不改，**跑完再改。**」结束，「进度条会显示已用时。」**已不在共用提示里**；`#batchLockHint`（DOM `:236`，静态内容为空）取值处全文只此一处。`已用时` 仍合法存在于它该在的地方（阶段条 `:850`、候选进度条 `:1448`）——**删的是越界指针，不是能力**。
2. **保留的锁定真话对三条链都成立**：该句由 `setCandidateControls` 一处写、三链共用（批量重试 `:1185`／重新成稿 `:1272`／错词重跑提交 `:1711`）。三条链在窗口内**都**把「范围、策略、rerun_old、目标集合」这批控件置 `disabled`（函数体 `:1345-1355`，`S8d` 九控件断言钉住），窗口结束再 `setCandidateControls(true,false)` 解开（`:1205`／`:1279`／终态轮询）——`S8e` 钉「跑完控件放开＋提示清空」。⇒「已锁定／本次不改／跑完再改」**字面属实**。
3. **没把该说的也说没了**（对照 `S8d`／`9b`）：`S8d` 只要「已锁定」（仍在）；`9b` 要「锁定范围」不许删（仍在）；被删的那半句本来就只对单链成立。而各链自己的真话**各就各位**：错词重跑进度行 `:1425/:1428` 仍写「可离开本页面」（`9b2` 钉住）、重新成稿 `:1270` 仍写「也可离开页面，后台会继续跑完」（复核二已用真 socket RST 实证）、批量重试 `:1186/:1195` 仍写「需保持本页打开」⇒ **越界的那句去掉、成立的那句留下**，方向正确。
4. 唯一可议（**承 复核三 §二 已记的 P3-6，非本轮引入**）：共用句括号里枚举的四个参数对「批量重试」链并非它消费的参数。但对「这些控件此刻被禁用且本次不改」而言字面仍真，且该句本来就是「说锁定这件事」——**不另记账**。

## 五、反向证伪：**我自己动手做了 4 条**（含「防过度修正」的 A2 与「防删真话」的 B2）

做法：对真源码做**唯一锚点**替换（断言锚点命中 1 处）→ 跑对应自测 → **要求 rc=1** → **整文件还原** → **sha256 必须与动手前一致**。判据**只用 rc 与 FAIL 行**。

| 抽检 | 改成什么形态 | 实测 | 结论 |
|---|---|---|---|
| **A**（退回 QA 那条 bug 的原形态） | `if "state" in item:` → `if str(item.get("state") or "").strip():` | `contract` **rc=1**，`FAIL 4/445`：`10a4 {"ok":True,"state":""} → failed`／`10a4 显式空白/None 同样以键为准走表`（实测回落 `success`）／`10a4 掺入显式空 state 后仍可复算`（实测 `success=2/failed=0`）／`10a4 判据单点` | **有牙** ✔ 还原一致 ✔ |
| **A2**（**防过度修正**，本轮最关键） | `if "state" in item:` → `if True:`（缺键也走表） | `contract` **rc=1**，`FAIL 8/445`，含 `10a3 无 state 的既有条目仍按 ok 标志判（正常成功不被误伤）`／`10a4 对照：{"ok":True}（**没有** state 键）→ 仍 success（防误伤）`（实测变 `failed`）＋`10a 跳过/待人工/中断各归各桶` | **有牙** ✔ 还原一致 ✔ |
| **B** | `index.html` 尾句加回「进度条会显示已用时。」 | `frontend` **rc=1**：`9b1 共用锁定提示不得再指进度条/已用时`（实测串＝「…跑完再改。进度条会显示已用时。」） | **有牙** ✔ 还原一致 ✔ |
| **B2** | 把整句提示**删光**（`locked?"":"";`） | `frontend` **rc=1**：`S8d 运行中就地说清为什么不能改`（实测 `""`）＋`9b 共用锁定提示仍写明锁定范围（三链都成立的真话，不许删）` | **有牙** ✔ 还原一致 ✔ |

结论：A 与 A2 是**方向相反**的两侧 ⇒ 本轮修复**既没继续 fail-open，也没矫枉成一律失败**，且 `10a3/10a4` 的对照组断言真的承担了「防误伤」验收；B 与 B2 证明 `9b1` 与 `9b/S8d` 是一对**互补**护栏（删越界句合法、删真话不合法），不是「一刀切删文案」。还原后两文件 sha256 ＝ 动手前 ＝ builder 申报值（**三处同一**），工作树复核 0 漂移。

## 六、范围、红线、数据安全与测试卫生

- **改动面**：`git status --porcelain` ＝ `M app/index.html`／`M app/server.py`／`M tests/selftest_p1_2_contract.py`／`M tests/selftest_p1_2_frontend.py`＋`M docs/model/DISPATCH-LOG.jsonl`（**TM 补记 6 行派工，逐行读过是派工记录、无业务内容**）＋未跟踪的 QA 报告与本报告。**`src/` 零改动**，`docs/` 除账本外零改动；QA 报告 mtime 08:18 **早于**本轮代码改动（08:29-08:30）⇒ 本轮未动它。
- **只加不减**：`contract` 累计删除数 **0**（故 445 项是 439 项的超集，**没有任何旧断言被删或放松**）；`frontend` 累计删除数仍 **1**（首版遗留，**本轮 0 删除**）；`^PASS` 行数 `439→445`／`86→87` 双升。
- **红线零接触**：主题默认浅色在位（`app/index.html:2` ＝ `<html lang="zh-CN" data-theme="light">`，字符串实测）；累计新增 **617 行** D-12 扫描 `/Users|/home|/private|/var|/Volumes|/Applications|/tmp` → **0 命中**；`_validate_vocab_pair`／`REAPPLY_ELIGIBLE`／`initial_publish`／`raw_unchanged`／`_recovery_gate_ok`／`_FAIL_SEMANTICS`／`_vocab_base_patterns`／`publish_or_block` 在增删行里 **0 命中**；`_reapply_one` 正文（No-Clobber 与 Raw 不变断言所在）**不在任何 hunk 的 new-side 范围内**；未碰 secrets、未改封存物。
- **数据安全**：两条探针均不调 handler、不建 `data_root`（不存在污染面）；我跑完系统 tmp **新增 `p12_*/p13_*` ＝ 0 个**（`find -newer` 对照实测）。
- **勘误（纠上一节的 P3-新2，请从 backlog 划掉）**：复核二/三 记的「`contract` 套件在系统 tmp 留夹具不清理（`:697`／`:916` 无 `finally`）」**前提不成立**——这两处**各有清理**：`bad_db` 在 `:719-720` `shutil.rmtree`，`bad = root+"-baddb"` 在 `:1056-1060` 与 `root` 一并 `rmtree`。我本轮回测共跑 `contract` **5 次**、`frontend` **3 次**，系统 tmp **0 新增**；现存 10 个 `p12_*/p13_*` 时间戳**全部 ≤ 08:02**（09-14 23:48～09-15 08:02），来自更早的**中断**运行（含 builder 首派 429 中断）与仓外探针 ⇒ **属中断残留，不是「每跑必漏」**，**不必派工返修**。

## P0 / P1 Findings

- **无 P0 阻断、无 P1 阻断。** P2-三1 与 P3-新1 经独立实跑＋AST 静态证明＋自做反向证伪（4 条，含方向相反的两侧）**判定真闭环**：三套自测 rc 全 0（445／87 PASS／58）；`git diff --check` rc=0；两文件 sha256 与 builder 申报值逐字一致且还原 0 漂移；`"state" in item` 口径**采纳**（我上轮 `is not None` 建议撤回）；生产形状（`_reapply_one` 20 个结果键不含 `state`）经 AST 证明为**零行为变更**；共用锁定提示「越界的删、成立的在」；D-12 与词库/No-Clobber 标识 0 命中；范围外改动 0。

## P2 / P3 Backlog Findings

- **P2-三1 已闭环 ✔**（`app/server.py:5590-5591`）：`{"ok":True,"state":None/""/"   "}` 实测 **failed**，`_RECOVERY_BUCKET_NAMES[_state_bucket(x)] == _recovery_bucket(x)` 逐条成立；缺键仍 `success`；`10a4` 六条断言只加不减且双向有牙。
- **P3-新1 已闭环 ✔**（`app/index.html:1360`）：尾句删净、真话留在该留的三处（`:1425/:1428`、`:1270`、`:1186/:1195`）。
- **P3-四1（承 复核三，非本轮引入，不修）** `_state_bucket:1795` 的 `.upper()` 归一化会接受**小写变体**（如 `"published"` → `success`），对「表外即失败」是**轻微放宽**。两链共用同一真源故不分叉，且全仓 0 个写入点产出小写 `state`；若日后收紧，改点只有这一行。
- **P3-四2（本轮新增，测试卫生）** `contract:1561` 的 `10a4 判据单点` 是**源码文本守卫**（钉 `'"state" in '` 字面），等价重排（如写成 `if ("state" in item):`）会误报；真牙是前 4 条行为断言（A 证伪已证）。与 `10a3` 既有同类守卫体例一致，**不要求改**，仅记。
- **P3-四3（口径，承 复核三）** 混合形态（同一条目**既有** `skipped`/`interrupted`/`needs_human` 标记**又有** `state`）两链优先级不同：重跑侧标记优先、恢复侧只认 `state`。今日无写入点产出该形态，不修。
- **P3-四4（观感）** `app/index.html:1359` 注释尾注 `P3-新1` 是指向**已闭环** finding 的溯源标记（不是残留伪话）；若要更清晰可写成「复核三 P3-新1 已修」，一行级、可不做。
- **顺手（给 TM，非业务、非阻断）** `docs/model/DISPATCH-LOG.jsonl` 现 51 行、JSON 全合法，但 **P1-3 链缺 3 行派工**（`builder返工P2-3`、`code-reviewer复核三`，及**本轮两派**待记），当前只有 6 行 P1-3 记录；supervisor 三处对账时需先补齐。
- **上一节 Findings 的存量状态**（本轮只核 P2-三1／P3-新1，其余**一律不动、不重开**）：**P2-三1 已闭环 ✔**、**P3-新1 已闭环 ✔**、**P3-新2 撤销（勘误，前提不成立）**；**P2-4**（运行中 `/api/reapply`／`retry-batch` 无后端互斥）与 QA 的 `QA-P13-P2-4-REAPPLY-MUTEX` **仍开**（上一节判非阻断）；**P2-三1 之外的存量 P3-1～P3-9、P3-三1、P3-三2 原样挂着**。

## 回归结论

- **无倒退。** 本轮改动只有两处语义：① `_reapply_result_bucket` 的**判据**（`值真值` → `键存在`）＋配套注释/文档串；② 共用锁定提示**删一句越界尾句**。后者纯文案；前者对**现有数据形状**（`_reapply_one` 结果条目**不含** `state` 键，AST 证明）**行为等价** ⇒ 存量重跑与批量恢复的五桶汇总、`balanced` 等式、出口字段名（`success/failed/skipped/needs_human/interrupted`）**一字未变**。
- 三套自测 rc 全 0（445／87 PASS／58），`git diff --check` rc=0；主题默认浅色未回退；词库三铁律／No-Clobber／D-12 零接触（标识 0 命中）；`server.py` 的函数行号漂移只出现在 `_reapply_result_bucket` 之内（定义行 5570 未动）⇒ 不存在「顺手改了别处」的空间。

## 未覆盖项（本复核未验，不得推断为通过）

1. **真机 UI 目检**：未起 8765、未点页面。`#batchLockHint` 的结论＝「抽真源码＋node 桩＋静态核对行号」，**不替代真机**；上一节对 QA 的补测要求（运行中实点三个批量按钮＋两个范围单选）**仍然有效**。
2. **真实 whisper／61 篇量级／长视频 elapsed 数值**（属 P1-1 链）。
3. **真实 DB 可读时的 `/api/retry` 404 分支**（复核一自陈 #5 要求 QA 在 tmp 补真取证）。
4. **多标签页真并发**、并发两次重跑的真实写盘竞争（P2-4／QA-P13-P2-4）——本轮未做注入级实验。
5. 用户真实视频目录与 Obsidian 库（红线禁写，未读未写）。

---

心跳：目标＝独立复核 DEVELOP-P1-3 返工（仅 P2-三1＋P3-新1）并追加本报告｜结论＝**PASS（无 P0/P1；P2-三1 与 P3-新1 均真闭环；`"state" in item` 口径采纳、我上轮的 `is not None` 建议撤回；新增 0×P2＋3×P3＋1 条勘误撤 P3-新2）→ 放行去 QA 复验**｜下一步＝交 qa（真机实点三批量按钮＋两范围单选；补「同目录 run 不存在→404」真取证）→ supervisor 复检；TM 顺手补 P1-3 派工账本 3 行。
