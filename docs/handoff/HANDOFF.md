# HANDOFF｜开发中（2026-09-14）：DEVELOP P0-1/P0-2 全链收口，P0-3 待派，恢复开发先读我

> 旧版字段（governance-state / Evidence / Human Gate / Promotion / Dispatch ID）已废弃，不填。
> 本文件即恢复入口。下面「一、当前进展／二、下一步／三、注意事项」按恢复用结构编排，字段名仍按 HANDOFF 模板。**Phase1 全过程记录**（用户四条反馈原文、九项 HD 决策、16 条真相、迁移决策、额度事件）见本文件后段各节；**迁移前项目交接原文**见文末附录。

- Captured at（YYYY-MM-DD HH:MM）：2026-09-14 13:00
- PROJECT_PHASE：**DEVELOP**（用户 2026-09-14 明确说「第二阶段，开发」进 Phase2）
- PLAN_VERSION：`PRODUCT_PLAN_V1.3`（正文最新；文末「Readiness Score / 本轮真实验证记录」两段仍为 V1.2 旧文本——第 5 轮修订被用户中止，未收尾，见 `docs/pm/PRODUCT_PLAN.md` 顶部收尾注记）
- PLAN_READINESS_SCORE：**未达 90**（planner 自评 **89**；Research Reviewer 独立打分 **83**，两轮结论均 FAIL；用户已知并决定开工）
- PLAN_GATE：**APPROVED**（用户明确进 DEVELOP，锁定基线开工；不是 Readiness 达标通过）
- DEV_BASELINE：`PRODUCT_PLAN_V1.3`（Phase2 锁定基线，禁随意改 Plan；变更只走 Change C）
- CHANGE_REQUEST：**NONE**
- Stage ID（本阶段叫什么）：**DEVELOP-P0-2 收口／P0-3 待派**（P0-1、P0-2 builder→reviewer→qa→supervisor 全 PASS；P0-1 打回停 1/2，P0-2 本链 0/2）
---

## 一、当前的工作进展

- **DEVELOP-P0-1 全链收口（2026-09-14）**：builder 首版（luna旧通道，server.py +220行）→reviewer 首轮FAIL三项→builder 返工三项（go/deepseek本窗口）→reviewer 复核PASS→qa 初验FAIL两BUG→builder 返工2→qa RETEST2双PASS→supervisor 首检FAIL（打回1/2：账本缺行＋派工缺行＋HANDOFF模型过期）→TM补账本＋派工行＋HANDOFF对齐根表→supervisor 复检PASS。报告：`docs/review/P0-1-DIAGNOSIS-CODE-REVIEW.md`、`P0-1-DIAGNOSIS-REWORK-REVIEW.md`、`docs/qa/P0-1-DIAGNOSIS-INDEPENDENT-RETEST-2026-09-14.md`、`P0-1-DIAGNOSIS-RETEST2-2026-09-14.md`。
- **DEVELOP-P0-2 全链收口（2026-09-14，本链0/2）**：builder 实现批量恢复闭环（server.py 累计约+837行：retry-plan dry-run/token摘要/TTL10分钟、retry-batch confirm+409零执行+幂等单job、job真源原子写、INTERRUPTED不续跑、三策略、16条双层排除、No-Clobber）→reviewer PASS（P0-2-RECOVERY-CODE-REVIEW.md，1×P1交qa）→qa 首轮撞真实 `_diag_alternate_paths` 扫 ~/Downloads 卡死（单条10秒＋不返回，工具超时无报告）→builder SCAN-FIX 有界重写（2s/2000目录预算、跳过云同步根大目录、Volumes只扫顶层、fail-closed）→reviewer SCAN-FIX复核PASS→qa 复验PASS无新增BUG（P0-2-RECOVERY-QA-2026-09-14.md，11项全过：77=61+16可复算、幂等单job、三409、INTERRUPTED、No-Clobber、两路fail-closed、真函数tmp计时54.2ms）→supervisor PASS。已知缺口（不拦收口）：D-20/D-21执行级注入与真并发、P1-1真机转写端到端；RETRANSCRIBE恒whisper=0如实fail-closed。报告见上。账本45行、派工21行，schema均exit 0。`app/server.py` 未提交未推送。
- **code-reviewer FAIL（返工三项未落盘）**：报告 `docs/review/P0-1-DIAGNOSIS-CODE-REVIEW.md`——P0-1 成功项隔离（SUCCEEDED+manifest 会被误标 FAIL 计入，违反 D-8）；P1-1 counts 口径（auto_retryable 只数 whisper，漏 AUTO_REUSE/AUTO_PUBLISH）；P1-2 七类互盖（manifest 分支抢在 transient 之前）。builder 返工 4 次均撞 `Selected model is at capacity` 未落盘，仍是首版 220 行。
- **模型通道现状**：luna 2026-09-14 多次 capacity（首版那次 patch 落盘但尾部报错、返工三次零落盘）；sol 探针也无回包，属 codex 侧不稳、非本地登录问题。supervisor 已由用户切为 `opencode-go/muse-spark-1.3-contributor`（走本窗口），builder 切为 `opencode-go/deepseek-v4.1-flash`（走本窗口），以 `USER_MODEL_OVERRIDE.md` 为准。
- **本窗口已做准备**：P1-7 改名只读盘点（`index.html` 可见 4 处待改＋`server.py` 兼容 7 处不动）；`data/state.db` 仓根不存在（旧记约 2.97MB）已记账，待核 data_root 真源。**git 未提交未推送**（`app/server.py` P0-1＋治理镜像改动在工作树）。
- **Phase1 基线（继承）**：`docs/pm/PRODUCT_PLAN.md`=V1.3；16 条红字真相=用户自移视频、DB 全 QUEUED；HD-1~9 全=A；Readiness 89/83 未达 90 用户已知开工。Phase1 详情见本文后段各节与文末附录。

## 二、下一步的任务

- **下一步（Next Single Action，按序）**：
  1. 派 builder P0-3 核心状态、恢复入口与可退出反馈（FR-13 四层状态＋监听脱钩、FR-14 统一恢复入口、FR-17 查询/复制可退出；D-16/D-19/D-23）。
  2. code-reviewer 复核返工（PASS 才往下），qa 独立复验（luna/codex）＋supervisor 复检（go Muse Spark/本窗口），TM 收齐落账本。
  3. 续 P0-2 批量恢复闭环 → P0-3 状态/入口/复制修复 → P1-1~P1-7（解不了的挂账记报告，不拦主线）。
- **人要拍什么板（只问大事，小事不问直接推）**：
  1. 何时继续（你说"继续"即重派；luna 仍 capacity 则继续挂账）。
  2. 是否换 builder/qa/supervisor 主用模型（给精确 ID 才改表，不自切）。
  3. 是否 commit/push（含分支名才动；API 密钥问题才找你，其他一律往前推）。
- **待排期 backlog（非阻塞）**：22 条 P3 按 V1.3 处置表分流；`data/state.db` 真源待核；P1-7 改名盘点已备好等 builder；benchmark `results/*.log` 19 个保留不删。

## 三、注意事项及相关规矩（本项目专用）

- **读盘顺序（全体系唯一，别乱）**：AGENTS → `docs/roles/` → 根 `USER_MODEL_OVERRIDE.md`（真源在模板包，本地为镜像）→ 本 HANDOFF → 根 `经验一句话.md` → 任务目标放**最后**。
- **两阶段治理**：`PLAN / WAITING_HUMAN_APPROVAL / DEVELOP / PLAN_REOPEN_REQUIRED`。Phase1 **只许** task-manager／supervisor／planner(Sol)／product-reviewer(FREE)，**禁** builder／code-reviewer／qa／业务代码改动／Release；只有用户明确说"第二阶段，开发"才进 Phase2。
- **派工显式**：每派必先贴「正在调用 XX｜主用精确ID＋Runtime／备用精确ID＋Runtime」，收工必贴「XX 回来了 PASS/FAIL＋实际走主还是备」；HANDOFF 执行链与账本记同一行。
- **固定通道（4 列表，无备用列，以根表为准）**：builder=`opencode-go/deepseek-v4.1-flash`（本窗口）；qa=`codex/gpt-5.6-luna`（codex）；supervisor=**`opencode-go/muse-spark-1.3-contributor`（本窗口）**；planner/senior=`codex/gpt-5.6-sol`；code-reviewer／experience-recorder／neat-freak＝本窗口。**主用不可用即停派找人，禁自动切备用/降级；换模型用户定。**
- **推进纪律（用户 2026-09-14 明确）**：小问题不问直接推；P0/P1 尽量解、解不了挂账记报告；除 API 密钥问题外一律往前推。luna capacity 时小步重试＋挂账，不在错基线上盖楼。
- **额度纪律（本轮新增，用户明确要求）**：外部模型单轮动辄数十万 token，**先小步试、及时收**；能本窗口做的别外派；用户说"停"立即停；烧了多少要如实报。
- **升级**：同一 Task 被 supervisor 累计打回 2 次自动升 senior-expert（QA 挂不算），只升当次；换模型/换 Runtime 即开新链。
- **账本**：`docs/model/TASK-MODEL-LOG.jsonl` 一行一任务（schema 锁死枚举）；`docs/model/DISPATCH-LOG.jsonl` 逐派一行（`used` 恒填主）。builder 写初版 → supervisor 校验 → TM 判结果落盘。
- **红线**：**不 push**（commit 需用户明确给分支名）；**不碰 secrets**；不改 V1.10/V2.0 封存；`docs/sop/` 仅模板示例。
- **数据安全**：测试只用**外置 tmp ＋ 合成数据**；用户真实视频目录与 Obsidian 库**禁写**（只读浏览例外）；**凡调 handler 的测试，首行必须断言 `data_root` 在 tmp 下**（污染事故补丁）；只读真实库时先拷到 tmp 查、**用完即删**。
- **No-Clobber**：已发布笔记**永不覆盖**（EXISTS/CONFLICT 只判不写）；缺失 vault 不重建；user-edited ＝ 一切字节差异。
- **服务**：`stage0bench venv python` 跑 `app/server.py`，固定 **8765**（PORT 硬编码）；**改 `app/` 或 `src/` 后必须重启服务再验**；当前 PID **12429**；**别请求、别重启**用户正在用的 8765。
- **主题**：默认必须**浅色**；自动化**禁止点真机主题开关**，用「抽源码 + node 桩」验。
- **词库三铁律**：wrong ≥ 2 字；正确文本含 wrong 即删条；长 wrong 排前；上限 500。
- **产品名**：用户已定 **「懒得笔记」**（落地范围见 PRODUCT_PLAN P1-7；GitHub 仓库名与内部 `v2o-*` 标识**不动**）。
- **收尾**：经验 / neat-freak 每阶段只派一次。

- **收尾记一笔（neat-freak，2026-09-13 本轮）**：清理＝删 2 个 `__pycache__`（`src/stage4`、`src/stage7`）＋2 个 `.DS_Store`（仓根、`docs/`），复查命令输出为空；未删任何业务/文档文件，未碰 `008林粒粒AI编程/`。文档仅改 `docs/pm/PRODUCT_PLAN.md` 一处（H1 下加"V1.3 正文最新、文末两段为 V1.2 旧文本、第 5 轮未收尾"的收尾注记）；HANDOFF 正文当时一字未动。Phase1 五项落盘全在。**不改只记**：QA/review 报告内 `PID 72407`、`count=307`、`HANDOFF:14「未开工」`等历史快照引用；`PRODUCT_PLAN:296` 轮次"待复审"过期句（已被新注记覆盖）。
- permission_request：无

## 恢复读盘（全体系唯一顺序，别乱）

1. AGENTS；2. 角色卡；3. 根 `USER_MODEL_OVERRIDE.md`；4. 本 HANDOFF；5. 根 `经验一句话.md`；6. 任务目标放最后。
冲突才扩大读。

---

## 附：迁移前项目交接原文（截至 2026-09-13 17:30；迁移时换新模板版，原件已从 git `d807483` 恢复并折叠于此，不另存文件）

> 下列内容为原文逐字，未改动。项目历史（八条迭代链、污染事故追记、服务/词库现状、注意事项）全在此节。

# HANDOFF｜开发暂停（2026-09-13 17:30）：七链全 PASS 全收口，已提交推送 main（91beaf8），恢复开发先读我

> V1 字段（governance-state / Evidence / Human Gate / Promotion / Dispatch ID）已废弃，不填。
> 本文件即恢复开发的唯一入口；下面「一、当前进展／二、下一步／三、注意事项」三节按恢复用结构编排，字段名仍按 HANDOFF 模板（AGENTS 要求），一一对应。

- Captured at（YYYY-MM-DD HH:MM）：2026-09-13 17:30（本机钟点；本文件旧条目标注钟点偏高，以实际为准）
- Stage ID（本阶段叫什么）：**暂停／收口完成**。今日八项迭代全收口：分段 para-v2.7＋批量重排＋词库 v2＋错词重跑＋三件套 UI＋词库折叠＋轮询修复＋错词重跑进度显示（异步 202＋轮询进度条＋主题浅色迁移）。

---

## 一、当前的工作进展

- **剩 P0（没完的才列，多一条都不行）**：
  - 无。无阻塞事项，无未开工开发项。
- **当前 Task（正干到哪）（累计打回 n/2）**：supervisor 累计 **0/2** 从未打回，senior-expert 从未启用。最后一条链「错词重跑进度显示」已四角色全链收口：builder 交付并两轮返工 → code-reviewer「返工复核二」**PASS** → qa 独立复验 **PASS** → supervisor 复检 **PASS**（账本 schema exit=0）。
- **今日八链状态**：reapply 收口／错词重跑／三件套 UI／词库折叠／轮询修复／para-v2.7 直做轮（本窗口直做）／**进度显示链**（返工二轮）／neat 收尾 —— **全 PASS**。
- **代码现状（已提交并推送）**：commit **91beaf8**（21 files，+2190/−186）已 push 到 `origin/main`；工作树干净、与远端 0/0 同步。`env.err`（0 字节）仍留仓根未处理。
  - 业务代码：`app/server.py`（候选接口 + apply + rerun_old + 进度任务态与线程保护）、`app/index.html`（进度条 + 轮询容错 + 主题一次性迁移 + 折叠 + 范围二选一 + 词库折叠过滤）、`src/stage9/formatter_v2.py`（v2.7）、`app/presets/vocab/vocab-programming.json`、`app/presets/vocab/vocab-crypto.json`、`tests/selftest_v26_presets.py`、`USER_MODEL_OVERRIDE.md`（镜像）。
  - 文档：`docs/handoff/HANDOFF.md`、`docs/model/TASK-MODEL-LOG.jsonl`、`经验一句话.md`；新增报告 `docs/review/` 5 套、`docs/qa/` 5 套（含 `RERUN-PROGRESS-REWORK-QA-REPORT.md`，末附 supervisor 复检节）。
- **服务现状**：`stage0bench venv py3.12.13` 跑 `app/server.py`，**PID 12429**，`127.0.0.1:8765` 监听中（16:58:06 启动，晚于 `server.py` 16:31 的改动，即**线上已是最新后端**）。主页 HTTP 200。
- **数据现状**：live 词库 **303 条**，rev `s9-corr-v2-user-977413c8`；待审候选**高 4 中 3** 在位；污染事故已回滚（见追记 18:00）。
- **执行链/Session**：builder 走 codex（`gpt-5.6-luna`；进度显示链为 codex 新链 workspace-write，tokens 约 86177）；code-reviewer 走本窗口 subagent；qa 走 codex 新链（`gpt-5.6-luna`）；supervisor 走 codebuddy（`deepseek-v4.1-flash`，`-y` 已带）。codex 旧双终端（term_8d84 / term_5944）暂留未关（同功能续用比新开便宜）。**git 已提交（91beaf8）并 push `origin/main`。**
- **未闭环评审意见**：无 P0/P1。继承 backlog：前序四链 **16×P3** ＋ 进度显示链 **6×P3**＝**22×P3**，全部非阻塞（在各评审原文）。污染事故已回滚；qa blindness（合成数据未覆盖真实旅程）已用真实候选端到端补过。
- **docs 落盘清单（本轮新增/改了哪几个）**：`app/server.py`、`app/index.html`、`src/stage9/formatter_v2.py`、`app/presets/vocab/` 两域 v2、`tests/selftest_v26_presets.py`、`USER_MODEL_OVERRIDE.md`、`docs/handoff/HANDOFF.md`、`docs/model/TASK-MODEL-LOG.jsonl`（39 行）、`经验一句话.md`、`docs/review/` 5 套、`docs/qa/` 5 套。

---

## 二、下一步的任务

- **下一步（Next Single Action，按序）**：
  1. **用户手测验收**：开 http://127.0.0.1:8765/ 亲手点一遍「错词重跑」（跑的是最新后端）。候选高 4 中 3、默认勾高中；**先生成／阅历两类勿勾**。点完给验收结论。
  2. ~~用户给分支名 → commit~~ **已完成**：用户指定推 `main`，commit **91beaf8** 已 push 到 `origin/main`。
  3. 验收通过即视为本阶段收工；无其它未开工开发项。
- **人要拍什么板（列出来问，不问不许开工）**：
  1. **验收结论**：错词重跑实点结果 OK / 不 OK（不 OK 则按现象开新链）。
  2. ~~分支名~~ **已办**：用户定 `main`，91beaf8 已推。
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

## 追记 2026-09-13 17:30（git 提交并推送：用户指定推 main；commit 91beaf8「控制台：错词重跑进度显示+主题浅色迁移+候选三件套UI+词库折叠+para-v2.7+词库v2」21 files +2190/−186；`git push origin main` 65cfe2c..91beaf8；提交前扫描无密钥/.env/隐私；工作树干净、与 origin/main 0/0；未动 env.err）

## 恢复读盘（全体系唯一顺序，别乱）

1. AGENTS；2. 角色卡；3. 真源 `USER_MODEL_OVERRIDE.md`（模板包；本地镜像可速览）；4. 本 HANDOFF；5. 根 `经验一句话.md`；6. 任务目标放最后。
冲突才扩大读。

---

## Phase1 用户反馈原文（2026-09-13，下一版硬输入）

> 用户原话，逐字保留。planner 的 PRODUCT_PLAN 必须正面回应这三条；Research Reviewer 要核。

现在使用过程中，这个界面还是比较混乱的，主要存在以下问题：

1. 内容过多且缺乏展示优化
(a) 列表过长：首先完成的内容列在这儿非常长，内容太多了。
(b) 缺乏折叠机制：不能把七八十条全部怼在这个界面上给用户。可以参考市面上成熟产品的做法，比如采用滚动展示最近的二三十条，之前已完成的内容折叠起来，用户想看可以打开，不想看也可以不看。

2. 监测状态显示不一致
点击"监测"和没有点"监测"时，下面的每一条状态为什么不一样？
(a) 未点监测时：显示一堆失败或者是红色的字。
(b) 点击监测后：依然是一堆东西在上面，之前完成的也在上面。
不管点没点，不应该都统一显示当前任务的状态（比如已完成哪些、哪些还在排队）吗？为什么两个状态会不一样呢？

3. 缺少清空列表功能
应该有清空已完成列表的功能。我看现在这个功能好像没有做，或者做好了也没有发挥作用。

建议参考一下市面上成熟产品是怎么做的。

### 事实核对（TM 只读代码，2026-09-13，供 planner 起点；细节以代码为准）

- **清空功能"已存在但与期望不符"（对第 3 条的更正）**：`app/index.html:211` 有按钮「清空本目录任务」→ 弹窗 `:273`「清空本目录任务（先看清代价）」，选项只有「只清失败」(`:278`) 与「全部清空」(`:279`)；后端有只读代价预览 `_clear_plan`（`app/server.py:1248`）与 `_handle_clear_post`。**没有"只清已完成"选项**，入口也不显眼 → 用户感知为"没做/没生效"。
- **列表全量渲染（对第 1 条）**：`app/index.html:1396` 取数必带 `limit=200`，77 条一次全铺进表格；无折叠、无分页、无"只看最近 N 条"。与用户诉求（最近二三十条 + 已完成折叠）直接冲突。
- **状态口径不统一（对第 2 条）**：状态文案由 `statusCN(r, cur)`（`app/index.html:355`）产出，依赖运行态（`worker.current` / running）。未监听与监听下同一任务可能呈现不同文案与颜色（含失败红字），缺一条统一的"任务状态机"口径。

- Phase1 状态：`PROJECT_PHASE=PLAN`、`PLAN_GATE=IN_PROGRESS`；planner(Sol) 第 1 轮已在跑（初稿 brief 未含本节反馈，需在下一轮修订中并入）。

### 追加反馈二（2026-09-13，布局；同样交 planner 并入 PRODUCT_PLAN）

> 用户原话，逐字保留。

还有当前这个布局，我觉得也非常不合理：

1. 左侧流程占地过大：
为什么左侧从上到下的这个流程占了那么大的空间？这很有必要吗？我觉得应该放到最顶上，做成薄薄的一横条就可以了。现在放到左上角，占了一大块空间，空间利用率不好。

2. "重跑"措辞位置不当：
"重跑"这个措辞放在了最下面，那不是用户要翻半天才能翻到最底下去吗？这样也不对呀。

所以，布局应该符合用户的操作逻辑，即从上到下、从左到右。尽量让用户在视线范围内，就能把这个功能全部进行操作。比如说最左边就。我觉得也需要让这个 planner 看怎么优化一下。

#### 事实核对（TM 只读代码，2026-09-13）

- **第 1 条属实**：主布局是三列栅格 `main{grid-template-columns:220px 1fr 300px}`（`app/index.html:33`）——左列 **220px** 是「流水线磁带」（`<section>` :176-181 / `.tape` CSS :37），**纵向铺满全高**；中列 1fr 是「处理任务」；右列 300px 是词库/待审等。用户诉求：把左侧纵向流程改成**顶部一条横向细条**，把 220px 让给内容。
- **第 2 条属实**：`app/index.html:702-708` 注释写明「重跑（应用新词库）收进详情『高级』」——即「应用新词库重跑」被藏在 **详情区 → `<details>高级`** 里，而详情区「选中任务详情」位于页面**最下方**（表格之后），用户须滚到底再展开才找得到。另有 `:253`「全部应用新词库重跑」（在词库区）、`:578`「重试全部失败（N个）」（表格上方）——**同族动作散落三处**，无统一入口。
- 用户诉求总纲：**布局按操作逻辑自上而下、自左而右；常用操作尽量在首屏视线内可达**。planner 需给出具体优化方案（含是否改栅格、折叠阈值、动作归并到哪）。

### Phase1 用户决策记录（2026-09-13）

- **HD-1 = A（用户答复「a」）**：下一版**先解决 16 个失败**（失败根因归类 + 批量诊断 + 差异化恢复为主线）；**22 条 P3 只做支撑主线的与低成本项**，不单独排期清 backlog。与 planner 建议一致，属用户已拍板。
- 待办：该决策需并入 `docs/pm/PRODUCT_PLAN.md` 的 `Human Decisions Needed` / P0-P1 优先级 / Readiness 自评（在 planner 下一轮修订时落）。
- 其余 4 个 HD（HD-2 诊断导出形式 / HD-3 自动恢复边界 / HD-4 是否支持其他笔记软件 / HD-5 真实验证样本边界）**用户尚未答复**，等 Research Reviewer 第 1 轮结论后一并提交。
- **HD-3 = A（用户「其他的按照建议来」）**：自动恢复只覆盖"规则确定、安全可恢复"的类别；未知/环境/媒体类失败留人工确认。
- **HD-4 = A（同上）**：v2 继续 Markdown + Obsidian，不加其他笔记软件专有适配。
- **HD-5 = A（同上）**：允许只读查看真实 16 条失败证据，并把少量代表性失败视频复制到外置 tmp 做真实 whisper 验证；**用户真实目录与 Obsidian 库仍零写**。
- **HD-2 = A（用户 2026-09-13：「那就按 A」）**：页面可看 + 一键复制**脱敏**摘要（真实绝对路径打码，如 `…/第七周/xxx.mp4`）；不做完整路径导出。
- **五项 HD 全部拍板完成**（HD-1=A / HD-2=A / HD-3=A / HD-4=A / HD-5=A），需在 planner 下一轮全量并入 PRODUCT_PLAN 与 Readiness 自评。
- **HD-6 = A（用户 2026-09-13 拍板）**：已完成列表默认显示**最近 20 条**，更早的默认收起，总数与展开入口常显。
- **HD-7 = A（同上）**：「清空已完成列表」= **只从当前列表归档/隐藏，可在历史恢复**；稿件、任务记录、中间产物一律不删。破坏性清理仍留"高级"入口并二次确认。
- **HD-8 = A（同上）**：任务状态**与监听开关脱钩**——同一快照在未监听/监听中/停止收尾三种系统态下，逐 run_id 的状态文字与颜色不变；"监听中"单独一处显示，worker 只细化当前 ACTIVE 阶段。
- **HD-9 = A（同上）**：顶部流程条为**普通横条**（向下滚动自然离开视野），不做 sticky、不做可收起（若日后实测需要再升级）。
- **九项 HD 全部拍板完毕**（HD-1..HD-9 均 = A），等 Research Reviewer 第 1 轮结论后，由 planner 在下一轮**全量并入** PRODUCT_PLAN 与 Readiness 自评。

### 追加反馈三（2026-09-13，复制失败原因导致页面被文字占满；同样交 planner 并入 PRODUCT_PLAN）

> 用户原话：为什么我点"查询失败原因"后，它就卡在这儿了？有一些失败的记录，我点"查询失败原因"，它就开始卡在这儿，也没办法缩小，或者我不想看它了也不行，我不知道怎么处理它。
> 用户截图：`/var/folders/mp/.../orca-paste-1789294139055-...png`（页面被一大段"已复制：V2O 失败原因清单（共 16 个）1. …"文字占满，无关闭入口）

#### 事实核对（TM 只读代码，2026-09-13）——**这是真 BUG，不是误操作**

- **根因**：`app/index.html:1009` `copyText(t)` 复制成功后调用 `say("已复制："+t,"ok")`；而 `say()`（`:987`）把这段字符串**整段塞进状态提示行 `#msg` 的 textContent**。用户复制的是「复制全部失败原因」的**16 条长文本**，于是提示行被撑成整屏文字。
- **为什么"关不掉、缩不小"**：`say()` 写入的 `#msg` **没有截断、没有关闭按钮、没有超时清除**（对比 `toast()` `:988` 有 `max-width:360px` + 3 秒自动消失 + 点击可关，但这里没用 toast）。
- **正确做法（下一版）**：复制成功的提示只能是一句短话（如「已复制 16 条失败原因」）；长文本不得进状态提示行。若要看长文本，应给**可关闭的面板/抽屉**。
- **用户自救**：按 `Cmd+R` 重新加载页面即可清除（该文字只存在页面内存中，未持久化）。

#### 副产品：16 个失败的真实根因证据（对 P0-1 与 Research Reviewer Required Fix #1 直接有用）

- 截图与接口数据显示：这 **16 条失败原因高度同质**，全部是「**源视频文件找不到了：<原文件名>**，下一步：检查视频是否被移动或删除，补回后点重试」，且**全部归属 `…/葫芦军师`**（该目录 成功 8 / 排队 16）。
- 含义：计划里"按 8 类根因归类"的假设**很可能是错的**——至少这 16 条是**同一类**（源文件缺失）。planner 的失败分类矩阵必须用这批真实证据校正，并回答"这类失败是否根本不该算『转写失败』，而是『源文件已不在』"。

### 追加反馈四（2026-09-13，产品命名；**不需 planner/reviewer 讨论，已由用户直接拍板**）

- **决策**：产品名从 `V2O 本机控制台`（V2O = Video2Obsidian 缩写，字母 O 易被误读成数字 0）改为 **「懒得笔记」**。
- **用户原话**：网页的名字应该改一下吧？什么叫"V20 本机控制台"？你们取个名字吧，好记一点。→ 用户自选 **懒得笔记**。
- **命名含义（TM 理解，供文案参考）**：懒得记笔记 → 工具替你记；有梗、好记、一看就懂。
- **落地范围（v2 待改，Phase1 禁改代码）**：`app/index.html` 的 `<title>`（现「V2O · 本机控制台」）与页眉 `<h1>`（现「V2O 本机控制台」）；`.tape::before` 的「V2O · 本机磁带」文案；`README.md` / `README.en.md` 标题；建议配副标题「懒得笔记 · 本地视频自动转文字」。
- **不在本次范围**：GitHub 仓库名（现 `wanghoufan/Video2Obsidian`）与技术标识符（`v2o-*` 的 localStorage 键、日志前缀、`v2o-console-data` 数据目录）——改这些会破坏兼容/数据路径，如需再单独议。
- 由 TM 直接办，**不派 planner / product-reviewer**（用户明确说"不用他们讨论"）。

### Phase1 收束（用户指令，2026-09-13）

- **用户原话**：可以了 到这一轮给我看一下 不要继续讨论了。
- **执行**：**停止 planner↔Research Reviewer 循环**，不再开新的评审轮；V1.3 修订轮（已在跑）让其写完即止（避免打断写坏文件），**不再派第 3 轮复审**。
- **Gate 状态如实记录**：**Readiness 未达 90**（planner 自评 V1.2=89/100；Reviewer 第 2 轮独立打分 **83/100**，结论 FAIL）。本次进入人工审阅属**用户主动提前看**，**不是 Gate 通过**，不得记为 APPROVED。
- **已完成轮次留痕**：V1.0(76) → V1.1(87, 12条全改) → V1.2(89, 真实16行矩阵+分类8→7+反馈A/B/C入计划) → V1.3(在跑) ；评审 2 轮：第1轮 FAIL(12条)、第2轮 FAIL(11/12到位+新增RF13~16, 独立83)。
- **未闭环项（留给开发阶段验，属用户已知）**：Reviewer RF13~16（替代路径核验/页面-DB provenance/双轴分类/反馈A与改名边界）在 V1.3 中处置中；旧恢复入口六项契约、真实性能实测、UI 原型本质需 Phase2 才能验。
- **下一步**：TM 出一份**人话版计划总览**交用户过目；用户拍板后才谈"第二阶段，开发"。

### 16 条"失败"真相（TM 独立核实，2026-09-13，**已闭环，非工具故障**）

- **结论**：页面那 16 条红色"失败"**不是转写失败**——是**用户自己把那批视频移出了监听目录**。
  - 登记路径：`/Users/zzymima0000/Downloads/需转录视频/葫芦军师/`（现在只剩 **8** 个文件 = 8 个成功任务）
  - 实际文件：`/Users/zzymima0000/Downloads/暂不转录视频/葫芦军师/`（**16/16 全部找到，文件大小逐条一致**）
- **核实方式（只读）**：只读 `data/state.db`（拷贝到 tmp 后查询，用完已删）取 `processing_runs`×`sources`，筛 `葫芦军师` 共 **24** 条 → 8 条路径存在、16 条不在；再按 basename 在 `Downloads`/`Volumes` 全盘查找 → **16/16 命中**「暂不转录视频」目录，`source_size` **16/16 一致**。
- **DB 侧真相**：这 24 条的 `processing_runs.status` **全部为 `QUEUED`**、`sources.status` 全部 `ACTIVE` —— **数据库从未记录过"失败"**；页面的红字是**运行时找不到源文件**导致的显示层映射。
- **产品含义（v2 要改）**：应把这类区别于"真失败"——标为「源文件不在原位（可能被你移走）」，**保留可见**（别静默消失），但**不计入"可自动重试失败"**、不进批量重试；并提示"若已移到别处，请重新指定目录"。
- **可立即自查的事实**：`Downloads/暂不转录视频/葫芦军师/` 在**监听目录之外**，所以工具看不到它们；把该文件夹移回 `需转录视频/` 下（或把监听目录改到 `Downloads`）即可被重新发现。
- **额度事件记录**：Phase1 循环消耗较大（planner 单轮 13.6 万→42.5 万 token，reviewer 单轮 10.9 万→54.6 万 token），用户反映额度被耗尽；TM 已**停止全部外派**，并中止 planner 第 5 轮（V1.3 正文已写、尾部 Readiness/未验证项段仍为 V1.2 旧文本，**未完成收尾**）。

### 用户对 Phase1 计划的评价（2026-09-13，重要信号，供下一轮规划）

- **用户原话**：就这样 说实话似乎改的不多 产品功能上也没有参考别的产品来完善优化。
- **用户决定**：Phase1 **就此收束**，不再推进、不再开评审轮、不进入开发（未说"第二阶段，开发"）。
- **TM 认账（不辩解）**：本版计划本质是「**治病**」而非「**长身体**」——
  - 范围被 HD-1=A 与用户四条反馈锁定为：分清失败类型 + 批量恢复闭环 + 界面收拾 + 改名 + 22 条 P3 取舍；
  - 计划里**大量是"看不见的工程活"**（双轴分类、dry-run/plan token、四层状态与 provenance、快照/指纹/并发安全、cursor 分页、脱敏），**用户可见的新功能确实少**；
  - Research Reviewer 虽引了 26 条外部来源（GitHub Actions / Todoist / Docker Desktop / HandBrake / qBittorrent / aria2 / yt-dlp / Android DownloadManager / Apple / MLX 等），但**只用于"验证设计对不对"，没有用于"找别人有什么功能可以抄"**——用户这条批评**成立**。
- **下一轮规划应做（用户若再提"第一阶段，计划"时）**：以「**功能对标 / feature gap**」为主题——对标同类本地转写与笔记工作流产品（如 MacWhisper、Aiko、whisper.cpp GUI、Obsidian 相关插件等），产出「**别人有、我们没有**」的功能清单，由用户挑要哪些；而不是再打磨现有链路的工程细节。
- **当前状态**：Phase1 停在 V1.3（正文已写、尾部 Readiness/未验证项为 V1.2 旧文本）；PROJECT_PHASE=PLAN、PLAN_GATE=IN_PROGRESS；**未提交、未推送**；无外派在跑。
