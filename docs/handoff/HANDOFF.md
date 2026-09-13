# HANDOFF｜开发暂停（2026-09-13 17:15）：七链全 PASS 全收口，恢复开发先读我

> V1 字段（governance-state / Evidence / Human Gate / Promotion / Dispatch ID）已废弃，不填。
> 本文件即恢复开发的唯一入口；下面「一、当前进展／二、下一步／三、注意事项」三节按恢复用结构编排，字段名仍按 HANDOFF 模板（AGENTS 要求），一一对应。

- Captured at（YYYY-MM-DD HH:MM）：2026-09-13 17:15（本机钟点；本文件旧条目标注钟点偏高，以实际为准）
- Stage ID（本阶段叫什么）：**暂停／收口完成**。今日八项迭代全收口：分段 para-v2.7＋批量重排＋词库 v2＋错词重跑＋三件套 UI＋词库折叠＋轮询修复＋错词重跑进度显示（异步 202＋轮询进度条＋主题浅色迁移）。

---

## 一、当前的工作进展

- **剩 P0（没完的才列，多一条都不行）**：
  - 无。无阻塞事项，无未开工开发项。
- **当前 Task（正干到哪）（累计打回 n/2）**：supervisor 累计 **0/2** 从未打回，senior-expert 从未启用。最后一条链「错词重跑进度显示」已四角色全链收口：builder 交付并两轮返工 → code-reviewer「返工复核二」**PASS** → qa 独立复验 **PASS** → supervisor 复检 **PASS**（账本 schema exit=0）。
- **今日八链状态**：reapply 收口／错词重跑／三件套 UI／词库折叠／轮询修复／para-v2.7 直做轮（本窗口直做）／**进度显示链**（返工二轮）／neat 收尾 —— **全 PASS**。
- **代码现状（工作树，未提交）**：10 处改动 + 11 份新增报告未纳管。
  - 业务代码：`app/server.py`（候选接口 + apply + rerun_old + 进度任务态与线程保护）、`app/index.html`（进度条 + 轮询容错 + 主题一次性迁移 + 折叠 + 范围二选一 + 词库折叠过滤）、`src/stage9/formatter_v2.py`（v2.7）、`app/presets/vocab/vocab-programming.json`、`app/presets/vocab/vocab-crypto.json`、`tests/selftest_v26_presets.py`、`USER_MODEL_OVERRIDE.md`（镜像）。
  - 文档：`docs/handoff/HANDOFF.md`、`docs/model/TASK-MODEL-LOG.jsonl`、`经验一句话.md`；新增报告 `docs/review/` 5 套、`docs/qa/` 5 套（含 `RERUN-PROGRESS-REWORK-QA-REPORT.md`，末附 supervisor 复检节）。
- **服务现状**：`stage0bench venv py3.12.13` 跑 `app/server.py`，**PID 12429**，`127.0.0.1:8765` 监听中（16:58:06 启动，晚于 `server.py` 16:31 的改动，即**线上已是最新后端**）。主页 HTTP 200。
- **数据现状**：live 词库 **303 条**，rev `s9-corr-v2-user-977413c8`；待审候选**高 4 中 3** 在位；污染事故已回滚（见追记 18:00）。
- **执行链/Session**：builder 走 codex（`gpt-5.6-luna`；进度显示链为 codex 新链 workspace-write，tokens 约 86177）；code-reviewer 走本窗口 subagent；qa 走 codex 新链（`gpt-5.6-luna`）；supervisor 走 codebuddy（`deepseek-v4.1-flash`，`-y` 已带）。codex 旧双终端（term_8d84 / term_5944）暂留未关（同功能续用比新开便宜）。**git 未提交、未推。**
- **未闭环评审意见**：无 P0/P1。继承 backlog：前序四链 **16×P3** ＋ 进度显示链 **6×P3**＝**22×P3**，全部非阻塞（在各评审原文）。污染事故已回滚；qa blindness（合成数据未覆盖真实旅程）已用真实候选端到端补过。
- **docs 落盘清单（本轮新增/改了哪几个）**：`app/server.py`、`app/index.html`、`src/stage9/formatter_v2.py`、`app/presets/vocab/` 两域 v2、`tests/selftest_v26_presets.py`、`USER_MODEL_OVERRIDE.md`、`docs/handoff/HANDOFF.md`、`docs/model/TASK-MODEL-LOG.jsonl`（39 行）、`经验一句话.md`、`docs/review/` 5 套、`docs/qa/` 5 套。

---

## 二、下一步的任务

- **下一步（Next Single Action，按序）**：
  1. **用户手测验收**：开 http://127.0.0.1:8765/ 亲手点一遍「错词重跑」（跑的是最新后端）。候选高 4 中 3、默认勾高中；**先生成／阅历两类勿勾**。点完给验收结论。
  2. **用户给分支名 → commit**（不许自推；用户未给名则继续留在工作树）。
  3. 验收通过即视为本阶段收工；无其它未开工开发项。
- **人要拍什么板（列出来问，不问不许开工）**：
  1. **验收结论**：错词重跑实点结果 OK / 不 OK（不 OK 则按现象开新链）。
  2. **分支名**：给名字才好 commit；给不给、给什么，用户定。
  3. 可选（非阻塞，用户可暂不定）：① 22×P3 backlog 是否排期修；② 账本 `rework` 口径统一（见下）；③ `env.err` 去向（见下）。
- **待排期 backlog（非阻塞，供恢复后挑活）**：
  - 22×P3：进度显示链 6 条（details 结构不齐／status 忽略 data_root／job_id 前端不用／无候选却画绿 100%／运行中仍可改下次参数／无超时与取消）＋ 前序四链 16 条。
  - 真实规模未验：真实 whisper 转写、61 篇量级端到端重跑的耗时与长视频阶段表现（各报告均已标注「未跑，不可推断为通过」）。
  - qa 报告 O-1 提的「词库 303 vs 307 对账」仍未与用户核。

---

## 三、注意事项及相关规矩（本项目专用）

- **读盘顺序（全体系唯一，别乱）**：AGENTS → 角色卡 → 真源 `USER_MODEL_OVERRIDE.md`（模板包；本地镜像可速览，**改表只改真源**）→ 本 HANDOFF → 根 `经验一句话.md` → 任务目标放**最后**。
- **派工显式**：每派必先贴「正在调用 XX｜主用精确ID＋Runtime／备用精确ID＋Runtime」，收工必贴「XX 回来了 PASS/FAIL＋实际走主还是备」；HANDOFF 执行链与账本记同一行。
- **固定通道**：builder=codex/`gpt-5.6-luna`；planner=codex/`gpt-5.6-sol`；code-reviewer=本窗口 subagent；qa=codex/`gpt-5.6-luna`；supervisor=codebuddy/`deepseek-v4.1-flash`（非交互 **必带 `-y`**）；senior-expert=codex/`gpt-5.6-sol`（只接升级任务）。
- **超限口径**：主备均不可用即**停派找用户**，不静默扣费、不自动进 GO（GO=MANUAL_ONLY，仅用户明确说「这次可用 GO」才单次启用）。
- **不可跳** code-reviewer + qa + supervisor；跳 planner/product 需记一句原因；**结论只落 `docs/review` / `docs/qa` 报告，HANDOFF 只记状态**。
- **升级**：同一 Task 被 supervisor 累计打回 2 次自动升 senior-expert（QA 挂不算），只升当次；换模型即开新链。
- **账本**：`docs/model/TASK-MODEL-LOG.jsonl`，一行一任务，schema 锁死枚举；builder 写初版 → supervisor 校验 → TM 判结果落盘。
  - **已知口径分歧（待用户统一）**：`AGENTS.md` 字面「rework=被 supervisor 打回次数」，本仓历史行按「reviewer 返工轮次」记；记账时写明用哪种。
- **模型表**：真源为 4 列旧版、本地镜像为 5 列新版，**角色→ID 映射一致无冲突**；根模型表非用户指令被改即上报（09-11 翻转过一次）。
- **红线**：**不 push**（commit 需用户明确给分支名）；**不碰 secrets**；不改 V1.10/V2.0 封存物。
- **数据安全**：测试只用**外置 tmp ＋ 合成数据**；用户真实目录与 Obsidian 库**禁写**（只读浏览例外）；**凡调 handler 的测试，首行必须断言 `data_root` 在 tmp 下**（18:00 污染事故补丁）。
- **No-Clobber**：已发布笔记**永不覆盖**（EXISTS/CONFLICT 只判不写）；缺失 vault 不重建；user-edited = 一切字节差异。
- **服务**：`stage0bench venv python` 跑 `app/server.py`，固定 **8765**（PORT 硬编码，只能覆盖端口、不能改业务文件）；**改 `app/` 或 `src/` 后必须重启服务再验**（懒加载教训 ×2）；当前 PID **12429**，监听状态重启即丢失。
- **主题（用户投诉项）**：默认必须**浅色**（`<html data-theme="light">` ＋ 一次性迁移清掉旧版机器写入的 `v2o-theme=dark`）；**自动化禁止点真机主题开关**，验证改用「抽源码 ＋ node 桩」；不同 origin/端口是各自独立的 localStorage 区。
- **词库三铁律**：wrong ≥ 2 字；正确文本含 wrong 即删条；长 wrong 排前。上限 500（现三域 369 ＋ 用户 0，手头候选待审）。
- **收尾**：经验 / neat-freak 每阶段**只派一次**。

---

## 收尾记一笔（neat-freak）

- 首轮（18:30）：4 份 docs 加注对齐；删 5 目录 2 文件；保留 2 备份目录。
- 二轮（17:05）：仅加注、未删任何文件；RERUN 两报告加收口注记 ＋ 补迭代映射。
- 三轮（**本轮，获用户授权清理**）：**删 11 个 `__pycache__` ＋ 3 个 `.DS_Store`**，复查命令输出为空（清零）；只改本 HANDOFF 一处追记，未删任何业务/文档文件，未碰 `008林粒粒AI编程/` 其余素材。未决中 `env.err`（仓根 0 字节、已被 git 跟踪）去向待用户定 —— **未动**。

---

## 追记

## 追记 2026-09-13 13:00（reapply 收口：61篇vault全量vocab+v2.7；教训：改src必重启；No-Clobber三确认；残留2备份+43 ob测试仅数据稿）

## 追记 2026-09-13 15:30（错词重跑链：候选接口+一键apply；返工P2标记/P1 codesummary/P0 vault透传；报告review/qa各一；线上demo验过）

## 追记 2026-09-13 16:30（三件套UI：待审折叠+rerun_old二选一互斥+预置查看停用+effective_revision；报告各一）

## 追记 2026-09-13 17:10（词库折叠+过滤+空态文案+首份真实候选高4中3；报告各一）

## 追记 2026-09-13 17:40（轮询弹开bug：refresh参数化；报告各一）

## 追记 2026-09-13 18:00（测试污染正式库事故：15:16擅自导入7条+标imported+104重衍生；vault零改动；已回滚303+去标记+重启；制度补丁+两链警告）

## 追记 2026-09-13 18:30（neat收尾：4docs加注对齐；删5目录2文件；保留2备份；未决git/哈希/账本v2.7轮/16P3/旧tmp）

## 追记 2026-09-13 17:05·进度显示链收口（异步202+轮询进度条+主题浅色一次性迁移M1-M4；返工二轮：code-reviewer「返工复核二」PASS→qa复验 QA-RR-01/02/03+P1-1 全CLOSED、新增BUG=0→supervisor复检PASS、账本schema exit0；账本补L39 rework=2；服务重启8765 PID12429；6条既有P3非阻塞）

- 修复点（真源码已抽查在位）：M1 主题一次性迁移 `index.html:331-334`＋静态首帧 `<html data-theme="light">`:2；M2 202 先建表 `:1296`；M3 构造与 start 同保护 `server.py:2301-2315`；M4 停表文案分流 `index.html:1244-1249`；R3 `server.py:4307-4313` 映射仅在有回调时求值。

## 追记 2026-09-13 17:05（neat对齐：RERUN两报告加收口注记＋HANDOFF补迭代映射；仅加注未删、未改结论正文）

- 迭代映射：分段para-v2.7＋批量重排＋词库v2＋错词重跑＋三件套UI＋折叠＋轮询修复＋错词重跑进度显示，均为 Stage0-12 之后、V1.8 冻结基线外的迭代，**不进任何 STAGE*-PLAN**；唯一落盘索引＝本 HANDOFF 追记链＋`docs/review|qa/` 各链报告。`docs/pm/STAGE0-12-PLAN.md` 全部未动（pm 下零先例，照本仓既有体例记在 HANDOFF）。
- 不改只记（历史快照）：两报告内记线上 PID 72407、`count=307/rev 6536029d` 等为当时取证数字，与现状（PID 12429；303/rev 977413c8）不同，按规矩不改报告正文。

## 追记 2026-09-13（neat对齐二：删11个__pycache__+3个.DS_Store；清理获用户授权，仅删清单内系统产物，只改本 HANDOFF 一处，其余不改只记）

- 清理（已删，全部在 `.gitignore` 内）：`__pycache__` **11 个** = `app/`×1 + `src/stage1|2|3|4|5|6|7|8|9|12/`×10；`.DS_Store` **3 个** = 仓根、`docs/`、`008林粒粒AI编程/`。
- 复查：`find . -path ./.git -prune -o \( -name "__pycache__" -o -name ".DS_Store" \) -print` → **输出为空**（清零）。`008林粒粒AI编程/` 其余素材零改动；未删任何 `.py/.json/.md/.html/.sh/.log`、未删 `docs/` 任何报告。
- 只列不删：`env.err`（仓根、0 字节、已被 git 跟踪，疑似 `2> env.err` 残留）——去向待定；`docs/qa/benchmark_stage0/results/*.log`（20 个）为 benchmark 证据，保留。

## 恢复读盘（全体系唯一顺序，别乱）

1. AGENTS；2. 角色卡；3. 真源 `USER_MODEL_OVERRIDE.md`（模板包；本地镜像可速览）；4. 本 HANDOFF；5. 根 `经验一句话.md`；6. 任务目标放最后。
冲突才扩大读。
