
# CODE REVIEW

- Task: 错词重跑进度显示（`/api/vocab/candidates/apply` 异步化 + 前后端轮询）。本轮新增段定界：server.py 87-88（全局任务态）、2032-2334（`_run_vocab_candidates_apply` 改名＋`_vocab_apply_worker`＋202/409 入口＋只读 status）、4278-4357（`_reapply_all` 抽 `progress_cb`＋`_handle_reapply_post` 透传）、4410-4413 / 4455-4458（GET/POST 路由）；index.html 1140-1265（进度条/`vocabApplyTimer`/`vocabApplyRunning`/render/poll/resume/点击改 202）、1367-1372（`refresh(false)` 挂续看钩子）、1637（5s 轮询改 `refresh(true)`）
- Commit: 工作树未提交（HEAD 65cfe2c + dirty）。`git diff -- app/server.py app/index.html` 是全工作区**累计** diff（含 15:30 候选接口 / 16:30 三件套 UI / 17:10 词库折叠 / 17:40 轮询修复四条已单审链），本轮按上列 hunk 定界；`src/stage9/formatter_v2.py` 的 dirty 属 para-v2.7 旧链（HANDOFF:10，其 diff 通读无 progress/async 成分），本轮未碰 src。
- Reviewer: code-reviewer（本窗口 subagent，只读复核，未改业务代码）
- Result: **过（PASS）**；无 P0/P1；3×P2 + 6×P3 进 backlog

> **返工复核（2026-09-13 晚）结论：需返工** —— R0 未真正闭环（P1-1）；详见文末「返工复核」一节。

> **收口注记（neat 对齐 2026-09-13）：** 以上头部 Result 与「返工复核：需返工」均为过程态；本链最终以文末「返工复核二 2026-09-13」结论 **PASS** 收口（P1-1/P2-1/P3-1/P3-2 全 CLOSED），独立复验见 `docs/qa/RERUN-PROGRESS-REWORK-QA-REPORT.md`（末附 supervisor 复检 PASS）。正文结论未改。

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## 验证方法与边界（先说证据强度）

- **真跑**：`/tmp/v2o_rr_review.py`（repo 外，临时合成），python3.12.13 直接导入 `app/server.py`，起 `ThreadingHTTPServer` 于 `127.0.0.1:8795`，**52 项断言全 PASS**（其中 T3.1 真双线程并发、T7.1-T7.3 为"确认缺陷存在"的正向断言）。
- **隔离**：所有 data_root 由 `tempfile.mkdtemp()` 建在系统 tmp，脚本首行断言 `realpath(data_root).startswith(realpath(gettempdir()))` 且 `!= DEFAULT_DATA_ROOT`；未写用户真实库/ob 库/vault；仓库内无 V1.10/V2.0 目录，未动封存物；本轮未改任何业务文件，只新增本报告。
- **不可核验项（明说）**：
  1. 上一版**同步体**从未进 git（`git stash list` 空、`git log --all` 仅 5 个旧 commit、无备份快照），`_run_vocab_candidates_apply` 与旧同步体**无法做字节级 diff**；本轮按语义＋行为等价核验，不对"逐字等价"背书。
  2. 真实 whisper/61 篇量级的端到端重跑未跑（需真实库，超只读边界）；进度在真实规模下的耗时、长视频阶段表现**未验证**。

## 硬门逐项（任一命中即 FAIL，本轮全过）

- 未动 src/封存/secrets：本轮 hunk 只落 `app/server.py` + `app/index.html`；`git diff -- app/server.py app/index.html | grep -iE "api_key|secret|token|password|BEGIN .*PRIVATE"` 零命中。
- 未破 No-Clobber / apply 校验链：重跑仍复用 `_handle_reapply_post({all:true,+vault_s})` → `_reapply_one`（转写 0 次、CONFLICT 只判不写）；apply 逐条走 `_validate_vocab_pair` + 内存 `_register_user_rules`（失败回滚 `entries_before`）＋容量门 500，链路一行未改。实测 T1.1-T1.17 全过：短词拒收、撞基表拒收（实测撞到 `VIP COIN`）、重复/越界/非法索引逐条拒收、已 `imported` 候选拒收、重复提交 `imported=0` 且**不触发重跑**。
  - 说明：HANDOFF 词库三铁律中本轮实测复验的是「wrong≥2 字」与「重跑不动老稿」；apply 链路未改，另两条由 15:30/17:10 两轮评审覆盖，本轮未重审。
- 无失败静默：起线程失败实测回 500（T7.1）；后台抛异常实测转 failed 终态＋人话原因（T4.2/T4.3）；导入 0 条走 200 明示「没有候选通过校验，未导入；未执行重跑」（T1.17）。
- 未写真实库：写路径仅 data_root 下 `vocab-user.json` / 候选文件标记 / `vocab-domains.json`（tmp+rename+finally 清 tmp）；新增 status 为纯读，不落盘。

## 派工 6 问逐项证据

### 1. 并发与线程安全 —— 无 P0/P1

- `_vocab_apply_job` 的**每一处**读/写都在 `_state_lock`（server.py:55 普通 Lock）下：建单 2275-2300、进度回调 2209-2219、收尾提交 2228-2256、status 读取 2312-2313。已逐处核对全仓 `_state_lock` 临界区（879/936/949/1565/3157/3254/3608/... ），**均为短拷贝或赋值，无长操作**，1.5s 轮询不会排队。
- **无撕裂**：status 只做 `dict(job)` 浅拷贝；worker 对嵌套字段用**整键重绑**（`job["summary"]={...}`、`job["result"]=obj`）而非原地改，浅拷贝不会读到半成品；`state` 与 `result` 同锁同段提交，不存在"done 了但 result 未写"的窗口。
- **job_id 唯一**：`_vocab_apply_seq` 在锁内自增（2281），实测 1→2→3→4→5 单调且互异（T3.5）。
- **409 无"先判后置位"竞态**：判定与占位同处一个 `with _state_lock`（2275-2300）。**真并发实测**：两线程同时 POST，结果恰好 `[202, 409]`（T3.1）；409 体带 `running:true + job_id + 人话`（T3.2）。

### 2. 重构等价性 —— `_reapply_all` 有 1 处非等价（P2-2）；改名函数语义等价（字节级不可核验）

- 逐行比对 diff 中被删的旧 inline `all=true` 块与新 `_reapply_all`：targets 过滤、`except (sqlite3.Error, OSError)` / `except Exception` 两分支的**文案与结构逐字相同**，summary 口径相同，返回 dict 相同；空目标时实测与旧实现**逐字一致**（T5.6）。
- 唯一差异：新函数在循环前**无条件**多调一次 `_run_source_path_map(data_root)`（4295-4298，只读 `mode=ro`），`progress_cb=None` 时也调 → P2-2。
- `progress_cb` 只在 all=true 分支被消费（4356-4357）；单 run_id 分支忽略该参数，apply 恒走 all=true，无影响。`progress_cb=None` 实测零回调（T1.12）、summary/results 与带回调一致（T5.5）。
- `_run_vocab_candidates_apply`：改名后仍是完整旧链（校验→容量门→save→register＋回滚→标记 imported→only-new/重跑分支），实测 17 项行为断言全过。**但**该函数上一版未进 git、无快照，"逐字等价"无法验证字节级，本轮只断言"语义与实测行为等价"。

### 3. 异常与终态 —— 1×P2（无终态守护）

- 已验：worker 内 `try/except Exception` 兜底转 failed（2223-2226）；实测抛异常 → `state=failed`、`error=错词重跑异常：…`、`finished_at` 落盘，**不悬挂**（T4.2-T4.4）。
- 缺口：**建单置位与起线程不同段**。`state=running` 在锁内先落（2284-2300），`threading.Thread(...).start()` 在锁外且**无 try**（2301-2305） → P2-1。
- 失败原因回传：`error`/`message` 均人话；failed 任务的 status 字段完整（T4.2）。
- `details` 结构不稳定：见 P3-1。

### 4. 前端轮询泄漏 —— 无 P0/P1，1×P2 + 2×P3

- **不会起两个 timer**：`pollVocabApplyStatus`（1222）与 `resumeVocabApplyPoll`（1237）都先判 `if(!vocabApplyTimer)`，共用同一全局（T6.1 静态双查）。
- **三个出口都停表**：无任务（1218）、终态（1225）、fetch 失败（1228），`vocabApplyStopPoll()` 恰好 3 处覆盖（T6.2）；终态分支后无任何重建 interval 语句（T6.4）。
- **不无限重试刷屏**：catch 里先 `vocabApplyStopPoll()` 再收尾（T6.5）——代价是**单次抖动即永久停表** → P2-3。
- **重复点击**：点击后同步置 `disabled=true`（1246），confirm 同步阻塞使第二次 click 落到已禁用按钮上；后端 409 双保险，实测并发只放行一次（T3.1）。
- **切页/关页**：interval 随页面销毁；`resumeVocabApplyPoll` 只在 `refresh(false)`（首屏/手动刷新，1371）与 409 路径（1254）挂，5s 自动轮询不挂。

### 5. 回归风险 —— 无 P0/P1

- **5s 自动轮询**：`refresh(true)` 仍常走 p1（`/api/status`→renderTape/renderRuns）与 p2（`/api/start`→renderLock），只跳过词库三件套＋续看（1367-1372）；`refresh(false);setInterval(function(){refresh(true);},5000)`（1637）与首屏顺序正确（T6.3）。手动/裸调 `refresh()` 等价 false，全量拉取不回归。
- **`setCandidateControls`**：有候选时 `setCandidateControls(true)`（1165）→ 运行态只禁 apply 钮（1142 `!on||vocabApplyRunning`），**非运行态勾选/全选/二选一全部可用**（T6.7）；空态（1153）与读失败（1152/1171）才整体置灰。候选勾选功能在非运行态未失效。

### 6. 越界改动 —— 无

未碰 src/、无封存物、无 secrets、无真实数据目录写（见硬门）。

## P0 / P1 Findings

- 无。

## P2 / P3 Backlog Findings

- **P2-1 无终态守护：建单置位与起线程不同段，起线程失败会把任务永久钉在 running。** 文件:行 `app/server.py:2284-2300`（锁内置位）、`2301-2305`（锁外无 try 起线程）、`2232-2256`（收尾提交）。
  失败场景：线程创建失败（`RuntimeError: can't start new thread`，长跑/线程泄漏后耗尽时触发）或起线程前锁外任何异常 → 请求回 500「服务开小差」，但 `_vocab_apply_job` 已卡 `state=running`；此后**每次**「错词重跑」都回 409「已有一次错词重跑在进行中」，页面无任何提示，**只能重启服务恢复**（已实测 T7.1/T7.2/T7.3）。
  建议：把 `_vocab_apply_job = {...}` 移到 `thread.start()` 成功之后（保留锁内 409 判定＋`_vocab_apply_seq` 自增），或 `try: thread.start() except Exception as exc:` 在锁内置 `state="failed"` + `error` 人话 + `finished_at` 再回 500。约 3 行，不引入新状态机。
- **P2-2 `_reapply_all` 的"None 时逐字一致"不成立：`progress_cb is None` 也调 `_run_source_path_map`。** 文件:行 `app/server.py:4295-4304`（对照注释 4281-4282）。
  失败场景：旧同步入口 `/api/reapply {all:true}`（前端「全部重跑」按钮、curl）每次多开一次 state.db（`mode=ro`, timeout=30s）并做 `processing_runs LEFT JOIN sources` 全表扫描；单机 61 篇量级只多几十毫秒，但与写事务抢锁时最长可挂 30s 才 fail-open。结果面实测等价（results/summary/message 与旧字面一致，T5.5/T5.6），故非行为回归。
  建议：把 `fn_map`/`_name` 挪进 `if progress_cb is not None:` 分支或惰性求值；4281-4282 的"逐字一致"改为"结果一致"。
- **P2-3 轮询单次失败即永久停表，终态可能永不呈现。** 文件:行 `app/index.html:1228`。
  失败场景：重跑进行中一次 fetch 抖动 / 后端瞬时不可达 → 进度条冻结在"已处理 n/N"、按钮解禁，`完成/失败` 终态永不出现（正是本功能要消灭的"不知道跑完没"）。可自愈但无提示：再点一次按钮走 409→`resumeVocabApplyPoll()`，或点刷新。
  建议：失败计数 ≤3 次内保持 1.5s 继续轮询，超限再停表并把文案改为"进度暂时读不到，点「刷新」续看"（不弹窗、不刷屏，符合 POLL-FIX 教训）。
- **P3-1 `details` 结构不齐。** `app/server.py:2055-2065` 三个索引非法分支只回 `{index,accepted,decision,reason}`，其余走 `_candidate_detail`（2024-2030）才带 `wrong/right/confidence/evidence`；`index` 还可能是字符串（实测 `"x"`）。前端 `d.wrong||('索引'+d.index)`（index.html:1211）不炸，但字段契约不稳。建议统一补空值字段。
- **P3-2 status 忽略 `data_root`。** `app/server.py:2310-2334` 不读 query；实测带 `?data_root=<另一目录>` 仍返回全局最近一次任务（T8.1）。用户换数据目录后进度/终态会显示另一目录的任务（job 已回 `data_root`，前端未用）。建议前端比对 `s.data_root` 与当前 `dataRoot()`，不匹配则不渲染。
- **P3-3 job_id 前端完全不用。** 202 回了 job_id，轮询回调从不校验（`app/index.html:1216-1229`）；上一任务终态后新任务 job_id 会变（实测 T3.5），多标签页下 A 页可能把 B 页任务的进度/结果画到自己页面（终态分支还会顺手 `loadVocabCandidates()` 重绘清单）。建议前端记住自己那次 job_id，只渲染匹配任务。
- **P3-4 无候选通过校验也画绿色 100%。** `imported=0` 的 200 终态走正常分支（`app/index.html:1205-1207`）；文案本身准确（T1.17），但绿满条与"什么都没发生"语义冲突。建议该分支画灰/中性色。
- **P3-5 运行中仍可编辑"下次提交"的参数。** `app/index.html:1142` 只随本轮禁用 apply 钮，`candidateSelectAll`/`candidateRerunOld`/`candidateOnlyNew` 在运行中仍可点（本次参数已快照，只影响下次提交），易被误解为能改变本次任务。建议运行态一并置灰两个开关。
- **P3-6 无超时与取消。** 后台任务进入 `_reapply_one` 长阶段后进度会长时间停在同一 `done` 值，页面只能等（本轮未要求取消按钮）。真实 61 篇量级耗时未实测。建议文案带"可离开页面稍后回来看"，或加 elapsed 时间。

## 结论

**PASS**（过）。无 P0/P1，无需返工；建议 P2-1（3 行防护）随下一次同类改动顺手收口，P2-2/P2-3 视排期处理。

> **收口注记（neat 对齐 2026-09-13）：** 本处「无需返工」随后被「返工复核」推翻（需返工，P1-1），最终由「返工复核二」判 **PASS** 重新收口；最终状态以文末「返工复核二结论」为准。原文未改。

---

# 返工复核 2026-09-13（R0 用户投诉主题 + R1/R2/R3 三条 P2）

- 复核对象：工作区未提交的返工改动（R0 index.html 主题默认 / R1 server.py:2301-2316 起线程保护 / R2 index.html 轮询容错 / R3 server.py:4304-4310 去掉多余查询）
- 复核方式：**不改业务代码**。① 前端两处逻辑按「抽取真源码 + node 桩」验证（不点真机开关）：`/tmp/v2o_rr2_front.js` 35 项，32 PASS + 3 项为「确认缺陷存在」的正向断言；② 后端用上一轮脚本升级后重跑回归：`/tmp/v2o_rr_review.py`（python3.12.13）58 项，**58 PASS**（其中 T7* 断言已修行为、T7b* 断言残留缺陷存在）；③ 静态排查初始态变深色的其它路径。
- 隔离与红线：只写系统 tmp 合成目录（脚本首行断言 `realpath(data_root)` 在 `gettempdir()` 下）；**未对线上 8765 发起任何请求、未重启/未杀进程**；未 commit/push；未碰 secrets/真实库/vault/封存物；上一轮 52 项断言全部随本轮重跑（现 58 项）无回归。
- 逐条结论：**R0 部分修复（P1-1）｜R1 已修复（留 P3-1）｜R2 部分修复（P2-1、P3-2）｜R3 已修复**。

## R0 主题默认浅色（用户投诉，最高优先）—— 部分修复

- **结论：规格内已修复，用户可见症状未闭环。**
- 已修复部分（实测 14 项全过）：
  - 静态首帧即浅色：`<html lang="zh-CN" data-theme="light">`（index.html:2），浅色调色板由 `:root[data-theme="light"]`（index.html:17-22）覆盖，**首屏不依赖 JS**、无深色闪一下。
  - `applyTheme` 只有显式 `"dark"` 才深色，其余一律 light 并**自愈回写**（index.html:321-326）；`initTheme` 默认与回退 `"light"`（328-331）。
  - 实测：无存储 / 空串 / `Dark`、`DARK`、`" dark"`、`"dark "`、`true`、`1`、`darkmode`、`深色`、`#dark`、`null` 共 11 种脏值 → 全部 light 且落盘 light；`getItem`/`setItem` 抛异常（隐私模式）→ 仍 light 且不炸。
  - 手切仍持久化：light→dark 存 dark、dark→light 存 light（实测）。
  - 未引入 `prefers-color-scheme`（全文件零命中）；**只有 `applyTheme` 一处写 `data-theme`**（全文件 1 处命中），无内联 style、无后端注入（`_serve_index` 逐字节直出，server.py:1098-1110），全仓仅 `app/index.html` 一个 HTML、仅 `v2o-theme` 一个主题键。
- **P1-1（新发现，必修）历史 `v2o-theme=dark` 残留会让投诉症状复现。** 文件:行 `app/index.html:328-331`（读同键）+ `321-326`（回写）。
  失败场景：旧版（`git show HEAD:app/index.html:288-300`）用的是**同一个键 `v2o-theme`**，且旧 `initTheme` 默认 `"dark"`、旧 `applyTheme` 每次加载把 `t` 原样写回 → **任何打开过旧版页面的浏览器，localStorage 里都已落盘 `"dark"`**。新代码读到的就是这个机器写入的 `"dark"` → 开机即深色，并继续回写 `"dark"`。已实测：存储 `dark` → `data-theme=dark` 且 store 仍为 `dark`（R0.6）。即**投诉人这台机器下次打开大概率还是深色**，必须手动点一次「◑ 深色/◐ 浅色」才回到浅色——正是用户原话「一打开又变深色」。
  **对用户提问的判断**：按本轮字面规格（「无存储/空值/脏值/读不到 → light」）存储 `dark` 属合法值，判「符合」；但按用户真实诉求判「**违背**」——该 `dark` 不是用户手动选择，是旧版 bug 机器写入的污染。两者只能靠**一次性迁移**调和。
  建议（一次性迁移，不引入跟随系统）：加标记键（如 `v2o-theme-scheme2`）：标记不存在时**忽略并 `removeItem("v2o-theme")`**（视为旧版污染）→ 强制 light → 写标记；标记存在后按现有逻辑「记住手动选择」。代价：此前真把 dark 当默认的用户会被恢复浅色一次（与用户「要浅色」一致，可接受）。**不改此条，R0 不算闭环。**
- 其它观察（未验证，非阻塞）：`_serve_index` 未发 `Cache-Control`/`ETag`/`Last-Modified`（server.py:1106-1109），理论上浏览器可能复用旧版 HTML（旧版无 `data-theme` 属性 → 落回 `:root` 深色）。我无法在本环境验证浏览器缓存行为，标「未验证」；建议顺手加 `Cache-Control: no-store`。
- 覆盖缺口（流程建议）：`docs/qa/RERUN-PROGRESS-QA-REPORT.md` 全文**零处涉及主题/浅色/深色/localStorage**（grep 已确认），即 R0 这条最高优先投诉**没有 QA 用例兜底**，下轮回归抓不住。建议 TM 派 QA 补一条 R0 用例，且按既定规矩用「抽取源码 + node 桩」验（**禁止真机点主题开关**，防再次把用户主题留在深色）。

## R1 `thread.start()` 保护 —— 已修复（留 1 条 P3 残留）

- **结论：已修复**（其声称范围）。文件:行 `app/server.py:2301-2316`。
- 证据（实测 T7.1-T7.5，全过）：把异常打在 `start()` 上时——① 请求回 **500** 且 body 为新人话「后台任务启动失败：can't start new thread，请重试或重启服务」；② 单例落 **`state=failed` + `finished_at` + `error`**，不再悬挂 `running`；③ `/status` 能看到该 failed 任务（前端据此出 err 文案，node 桩 R1.F1 验过 500 时按钮解禁、无 timer 残留）；④ 失败后**立刻可再点**（第二次 POST 回 202，job_id 由 `vocab-apply-5-12345` → `vocab-apply-6-99232`，**不再永久 409**）；⑤ 重试任务跑到终态。
- 并发/一致性核对：失败分支**在 `_state_lock` 内**且带 `job_id` 匹配守卫（2311），不会覆盖更新的任务；`_vocab_apply_seq` 仍在锁内自增（2281），无泄漏（失败不占用任何需释放的资源，仅一个自增整数）；判定与置位仍同处一把锁，上一轮验过的「并发 POST 恰好一个 202、一个 409」不变（T3.1）。
- **P3-1（新发现，同族残留）异常若打在 `threading.Thread(...)` 构造行仍会悬挂。** 文件:行 `app/server.py:2301-2304`（构造在 try 之外，只包了 `start()`）。
  失败场景（实测 T7b.1/T7b.2）：让构造行抛异常 → 请求 500（走 `do_POST` 兜底「服务开小差」），单例仍卡 `running`，随后每次 POST 都 409，需重启进程。**降级理由**：常量参数（target/args/name/daemon）下 CPython 的 `Thread.__init__` 实际不会抛，真实可达的那条（OS 线程耗尽）是在 `start()` 里抛、已被修好，故列 P3 不列 P2。建议：把 `thread = threading.Thread(...)` 一并缩进 try（1 行），彻底消除同窗口。

## R2 轮询容错（单次失败不停表）—— 部分修复

- **结论：主诉求已实现；新增/残留 2 个洞（P2-1、P3-2）。** 文件:行 `app/index.html:1142-1145`（计数器/阈值）、`1220-1236`（startTimer/noteFail）、`1237-1252`（poll）、`1253-1268`（resume）、`1269-1290`（apply）。
- 已实现且实测通过：
  - 计数器复位正确：**任何一次成功的 status 读都先清零**（1241 在状态分支之前），实测连丢 7 次后成功一次 → streak 回 0 且不停表（R2.6）；`job=null`（1240）、点 apply（1275）、resume（1259/1265）也清零。
  - 单例 timer：守卫收敛到 `vocabApplyStartTimer()` 一处（1222），poll（1245）/resume（1261）都经它 → 实测 apply+resume+startTimer 三路叠加后仍只有 **1 个 interval**（R2.11），不会起两个 timer。
  - 阈值：连续失败 7 次仍继续轮询并显示「进度读取失败，正在重试…（第7次：…）」（R2.4），第 8 次才停表 + err 人话 + 放开按钮（R2.7）；失败期间按钮保持禁用（R2.5）。
  - 终态：done 才停表并渲染终态文案/满条（R2.8），**done 之后不再重开 interval**（即便有迟到的失败回调也不起表，R2.9）；resume 载入读失败也仍开表限期重试（R2.10），不再静默冻结。
- **P2-1（新发现，建议必修）首次 status 读失败 → 既不重试也不解锁，且文案称"正在重试"是失真。** 文件:行 `app/index.html:1282`（202 分支直接调 `pollVocabApplyStatus()`）+ `1228-1231`（重试分支只改文案、不建表）。
  失败场景（实测 R2.1/R2.2）：点击 → POST 202 成功 → **第一次** status 读失败（此时还没有 timer）→ `noteFail` streak=1 <8 且未超时 → 只显示「进度读取失败，正在重试…（第1次）」**然后 return，不调用 `vocabApplyStartTimer()`** → 没有任何后续轮询，进度条永久停在"正在重试"，`vocabApplyRunning` 仍是 true、apply 按钮**保持禁用**。文案说"正在重试"但没有重试，用户既看不到终态也不能再点，只能点页头「刷新」（走 `refresh(false)`→`resumeVocabApplyPoll()`）才恢复。这正是 R2 要消灭的"冻结"，且相比返工前是**退化**（返工前该分支会解禁按钮）。
  建议（1 行）：把 202 分支改成 `if(x.code===202){vocabApplyStartTimer();pollVocabApplyStatus();return;}`——已知有任务在跑就先把表立起来，首次读失败由表自然重试，读到终态再 `stopPoll` 清掉；不要改 `noteFail` 里建表（否则 done 之后迟到的失败回调会重新起表）。
- **P3-2（新发现）已跑 >10min 时，单次失败会立刻停表，且文案写成"连续失败1次"。** 文件:行 `app/index.html:1227-1228`。
  `tooLong` 取的是「从任务开始到现在的墙钟时长」而非「失败持续时长」，实测把 startedAt 调到 11 分钟前，第一次失败即停表并输出「进度读取**连续**失败1次，已停止自动刷新」（R2.12），与本轮口径「单次/短暂失败不停表」冲突，文案也不准确。**降级理由**：错词重跑是 0 次转写（仅规范化+成稿），61 篇量级通常在分钟内完成，>10min 概率低。建议：或把窗口改成「首次失败起累计 10min」，或把文案改成「任务已运行超 10 分钟且本次进度读取失败，先停止自动刷新」。

## R3 `progress_cb is None` 不再查 run→文件名 映射 —— 已修复

- **结论：已修复。** 文件:行 `app/server.py:4304-4310`（`fn_map` 求值包进 `if progress_cb is not None:`）。
- 证据（实测）：把 `_run_source_path_map` 换成计数器——`progress_cb=None` 时调用 **0 次**，带回调时调用 **1 次**（T5.5b/T5.5c）；空目标早回的字面与旧实现逐字一致（T5.6）；`progress_cb=None` 与带回调的 `summary`/`results` 完全一致（T5.5）。即旧同步入口 `/api/reapply {all:true}` 恢复到**零多余 DB 查询**，上一轮 P2-2 关闭。
- 备注：代码行仍与旧 inline 写法不同（多了 `total`/`enumerate`/闭包），但**无任何多余 I/O、返回面逐字一致**，属注释口径问题（4288-4291 已改述为"为 None 时行为与旧版逐字一致"）；按行为等价判「逐字一致」成立，不计 finding。

## 本轮新发现汇总

| 编号 | 级别 | 位置 | 问题 |
|---|---|---|---|
| P1-1 | P1 | index.html:321-331 | 旧版同键机器写入的 `v2o-theme=dark` 残留未清 → 投诉症状「一打开又变深色」在投诉人机器上大概率复现；需一次性迁移（标记键 + 清污染） |
| P2-1 | P2 | index.html:1282 + 1228-1231 | 首次 status 读失败不重试、按钮锁死、文案称"正在重试"失真（返工前的行为退化） |
| P3-1 | P3 | server.py:2301-2304 | `Thread(...)` 构造行仍在 try 外，实测该行抛异常仍悬挂 running + 永久 409（常量参数下实际不可达） |
| P3-2 | P3 | index.html:1227-1228 | >10min 后单次失败即停表 + 文案"连续失败1次"不准确（重跑 0 转写，概率低） |
| 观察 | 未验证 | server.py:1106-1109 / 线上进程 | ① 无 `Cache-Control`，旧 HTML 理论可被缓存复用（浏览器行为未验证）；② **线上 8765 进程启动于 15:33:42，早于本轮后端改动（server.py 16:24）→ 线上后端仍是旧代码，index.html 每请求从磁盘读故前端已是新版；R1/R3 要生效需重启服务（本轮未重启、未请求线上）** |

## 返工复核结论

- **需返工**：必修 **P1-1**（R0 用户投诉未闭环，代价约 5 行一次性迁移）；建议同轮带修 **P2-1**（R2 首个轮询失败新洞，1 行）。
- 上轮结转：P2-1→R1 **已修**（留 P3-1）；P2-2→R3 **已修（关闭）**；P2-3→R2 **部分修**（主干达标，新增 P2-1/P3-2）；其余 6 条 P3 状态不变。
- 回归：上一轮 52 项 + 本轮新增 6 项后端断言 = 58 项全 PASS；前端 35 项中 32 PASS、3 项为缺陷正向断言，未发现 R1/R3 引入的新回归。

---

# 返工复核二 2026-09-13（M1 主题一次性迁移 / M2 首轮建表 / M3 构造行保护 / M4 停表文案）

- 复核对象：M1 `app/index.html:328-346`、M2 `app/index.html:1296`、M3 `app/server.py:2301-2315`、M4 `app/index.html:1234-1250`
- 方式：**不改业务代码**。① 前端「抽取真源码 + node 桩」（`/tmp/v2o_rr3_front.js`，28 项全 PASS，含多轮加载共用同一 store 模拟真实浏览器）；② 后端升级上轮脚本重跑（`/tmp/v2o_rr_review.py`，**61 项全 PASS** = 上轮 58 项 + M3 新增 3 项）；③ 静态复核其它变深色路径。
- 隔离与红线：只写系统 tmp 合成目录；**未对线上 8765 发起任何请求、未重启/未杀进程**；测试端口 8795 已释放；未 commit/push；未碰 secrets（`grep -icE "api_key|secret|token|password"` = 0）/真实库/vault/封存物；`src/stage9/formatter_v2.py` 的 diff 与上轮完全一致（161/53），本轮未碰。
- 逐条结论：**M1 已修复｜M2 已修复｜M3 已修复｜M4 已修复**；**无 P0/P1 新发现**。

## M1 主题一次性迁移 —— 已修复（P1-1 关闭）

- 代码：`initTheme`（index.html:328-342）先看标记键 `v2o-theme-migrated`；**无标记** → `removeItem("v2o-theme")` + 写标记 + `t="light"`；**有标记** → `t=localStorage.getItem("v2o-theme")||"light"`；整段包在 `try` 里，`catch` 落 `t="light"`。
- **对用户特别指定的问题「开过旧版的浏览器（已有 `v2o-theme=dark`、无标记）现在打开是否一定 light」——实测：是。** 多轮加载共用 store：`{v2o-theme:"dark"}`（无标记）载入 → `data-theme=light`，且 store 被改成 `{v2o-theme:"light", v2o-theme-migrated:"1"}`（M1.1）。两个 origin 各自残留 dark 也各自自愈为 light（M1.15）。
- 迁移不会被反复触发：标记已写 → 下次直接走 else 分支（M1.2：有标记 + dark 仍 dark）。**不会吃掉本次手切**：首载写标记后手切 dark → 落盘；重开页面仍 dark（M1.4→M1.5 连测），再切回 light 亦正常（M1.6）。
- 无标记但键缺失/脏值：有标记无键 → light（M1.7）；有标记 + `Dark` → light 并自愈（M1.8）。
- 异常路径：`getItem`/`setItem`/`removeItem` 任一抛异常 → 均 light 且不炸页面（M1.9/M1.10/M1.11）；`catch` 里 `t="light"` 兜底。
- 不误伤同库其它键：`{v2o-input-root, v2o-vault-root, v2o-theme}` 载入后路径键原样保留、只清主题键（M1.14）；全仓主题键仅 `v2o-theme` / `v2o-theme-migrated` 两个（grep 确认）。
- 深色闪屏：`<html data-theme="light">`（index.html:2）静态即浅色，`:root[data-theme="light"]`（17-22）覆盖深色基色板，**首帧不依赖 JS、不存在深色闪屏**；主题脚本在 `<script>`（284）内紧随标记之后执行，仅"手切过 dark 的用户"可能浅→深跳一下（预期行为；具体首绘时机属浏览器行为，未验证）。其它变深色路径复核：只有 `applyTheme` 一处写 `data-theme`（1 处命中）、无内联 style、无 `prefers-color-scheme`（0 命中）、无后端注入（`_serve_index` 逐字节直出，server.py:1098-1110）、全仓仅一个 HTML。
- 理论边界（已实测、判不可达、非 finding）：只有在「存储实现对 **标记键** 选择性写失败、对主题键写成功」时，重开页面会清掉手切 dark（M1.12）。真实 localStorage 不会按键选择性失败——`setItem` 失败要么是配额/隐私模式，那种环境下 `applyTheme` 写 `v2o-theme` 同样失败，dark 本就存不住，故用户可见损失为零。

## M2 202 后先建表再轮询 —— 已修复（P2-1 关闭）

- 代码：`if(x.code===202){vocabApplyStartTimer();pollVocabApplyStatus();return;}`（index.html:1296）。
- 实测：202 成功 → **首轮 status 读失败时 timer 已存在**（`timer=1`、文案「进度读取失败，正在重试…（第1次：net down）」，M2.1/M2.2）；让表走一格即自动重试并恢复进度「已处理 3/10」（M2.3）；随后读到 done → 停表 + 终态文案 + **按钮解禁**（M2.4）→ 上一轮的「永久冻结 + 按钮锁死」消失。
- 单例仍成立：`vocabApplyStartTimer` 的 `if(!vocabApplyTimer)` 是唯一建表点，apply 后再调 `resume`+`startTimer` 叠加仍只有 1 个 interval（M2.7）。
- 阈值/终态未回归：首轮失败后连丢 8 次才停表并解禁（M2.6）；done 之后迟到的失败回调不重开表（M2.5）。
- 观察（既有行为，非本轮引入）：若 status 回 `job:null`（如后端进程重启丢了内存态），前端停表并解禁按钮，但进度文案仍停在点击时的占位「正在导入错词并准备重跑…」且无提示（M2.8）。用户可点「刷新」恢复；概率低，未计 finding。

## M3 `Thread(...)` 构造与 `start()` 同保护 —— 已修复（P3-1 关闭）

- 代码：`try:` 起点前移到构造之前（server.py:2301-2307），异常统一走 2308-2315 的 failed 分支。
- 实测（异常打在**构造行**，上一轮该场景必悬挂）：请求回 500 且为新人话「后台任务启动失败：can't allocate thread object，请重试或重启服务」（T7b.1）；单例落 `state=failed` + `finished_at` + `error`（T7b.2）；`/status` 可见（T7b.3）；**单例释放，立刻可再点回 202**（T7b.4）；重试任务跑到终态（T7b.5）。异常打在 `start()` 的路径保持上轮结论不变（T7.1-T7.5 全过）。失败分支仍在 `_state_lock` 内且带 `job_id` 守卫，`_vocab_apply_seq` 无泄漏。

## M4 停表文案区分原因 —— 已修复（P3-2 关闭）

- 代码：`why = streak>=MAX_FAIL ? "进度读取连续失败N次" : "进度刷新累计超过10分钟仍未完成"`（index.html:1244-1249）。
- 实测文案与成因一一对应：连丢 8 次（未超时）→ 只出现「连续失败8次」、不提 10 分钟（M4.1）；超 10min + 单次失败 → 只出现「累计超过10分钟」、不提"连续失败"（M4.2），且该分支确实停表 + 解禁（M4.3）；两条同时成立 → 给「连续失败8次」，不矛盾不崩（M4.4）。
- caveat（不影响结论）：10 分钟分支的实际成因是「已跑超 10min **且** 本次读失败」，文案只提时间未提这次失败；按可读性可接受，未计 finding。

## 本轮新发现

- **无 P0/P1，无新 P2/P3。** 仅 1 条未验证观察：线上 8765 进程仍为 15:33:42 启动（`app/server.py` mtime 16:31）→ **线上后端仍是旧代码，M3 需重启服务才生效**；`app/index.html` 每次请求从磁盘读，前端 M1/M2/M4 已是新版（本轮未重启、未请求线上，交由 TM/用户决定）。
- 结转：P1-1 / P2-1 / P3-1 / P3-2 **全部关闭**；上轮 6 条既有 P3 状态不变。

## 返工复核二结论

- **PASS**（过）。M1-M4 四条全部按声达修复，且经「多轮加载 / 构造行异常 / 首轮失败 / 双原因停表」等对抗性用例实测；无新问题、无回归。
- 回归口径：后端 61 项全 PASS（上轮 58 + M3 新增 3）；前端 28 项全 PASS（含 M1 多轮加载 15 项、M2 7 项、M4 4 项）；两套桩均只写 tmp、未触线上。
