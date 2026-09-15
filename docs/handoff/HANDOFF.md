# HANDOFF｜P1-3 全链收口（2026-09-15 08:45）：全 P0 清＋P1-2／P1-3 全 PASS（P1-3 本链 supervisor 0/2），交付待提交，恢复先读我

> 旧版字段（governance-state / Evidence / Human Gate / Promotion / Dispatch ID）已废弃，不填。
> 本文件即恢复入口。下面「一、当前进展／二、下一步／三、注意事项」按恢复用结构编排，字段名仍按 HANDOFF 模板。**Phase1 全过程记录**（用户四条反馈原文、九项 HD 决策、16 条真相、迁移决策、额度事件）见本文件后段各节；**迁移前项目交接原文**见文末附录。

- Captured at（YYYY-MM-DD HH:MM）：2026-09-15 08:45（恢复窗口续做：P1-3 共 **11 派**（builder×5／code-reviewer×4／qa×2）＋ supervisor 复检，全链收口；无外派在跑。**注：本链跨零点**，机器钟 09-14 23:40 → 09-15 08:45，故部分报告印章为 09-15、此前记录为 09-14，两者并存不矛盾）
- PROJECT_PHASE：**DEVELOP**（用户 2026-09-14 明确说「第二阶段，开发」进 Phase2；23:27 叫停暂停，本轮恢复并收口全 P0，仍在 Phase2 未关闭）
- PLAN_VERSION：`PRODUCT_PLAN_V1.3`（正文最新；文末「Readiness Score / 本轮真实验证记录」两段仍为 V1.2 旧文本——第 5 轮修订被用户中止，未收尾，见 `docs/pm/PRODUCT_PLAN.md` 顶部收尾注记）
- PLAN_READINESS_SCORE：**未达 90**（planner 自评 **89**；Research Reviewer 独立打分 **83**，两轮结论均 FAIL；用户已知并决定开工）
- PLAN_GATE：**APPROVED**（用户明确进 DEVELOP，锁定基线开工；不是 Readiness 达标通过）
- DEV_BASELINE：`PRODUCT_PLAN_V1.3`（Phase2 锁定基线，禁随意改 Plan；变更只走 Change C）
- CHANGE_REQUEST：**B**（P1-3 批含 P2-7「扩 `/api/retry` 契约带 `data_root`」，属局部功能变化→只更新局部 Requirement/DoD，留 DEVELOP、不召 Sol Planner；用户 2026-09-15 明确「继续推进」「按分工表为准」，授权连续推进不再逐次问）
- Stage ID（本阶段叫什么）：**DEVELOP-P1-3 全链收口**（P1-3 达成；P0-1／P0-2／P0-3 仍全清）。P1-3 本链 supervisor 累计打回 **0/2**（链内 4 次 FAIL 全出自 code-reviewer 或 QA，不计 supervisor 打回；supervisor 复检 08:52 **PASS／无 blocking**）。P0-3 链定格 1/2、P0-1 1/2、P0-2 0/2。**P0 交付已 push（c753b15）＋P1-2 交付已提交推送 `main`（92fa77e）＋HANDOFF 回写（3af2da7）；P1-3 交付本轮提交推送 `main`**。
---

## 一、当前的工作进展

- **DEVELOP-P0-1 全链收口（2026-09-14）**：builder 首版（luna旧通道，server.py +220行）→reviewer 首轮FAIL三项→builder 返工三项（go/deepseek本窗口）→reviewer 复核PASS→qa 初验FAIL两BUG→builder 返工2→qa RETEST2双PASS→supervisor 首检FAIL（打回1/2：账本缺行＋派工缺行＋HANDOFF模型过期）→TM补账本＋派工行＋HANDOFF对齐根表→supervisor 复检PASS。报告：`docs/review/P0-1-DIAGNOSIS-CODE-REVIEW.md`、`P0-1-DIAGNOSIS-REWORK-REVIEW.md`、`docs/qa/P0-1-DIAGNOSIS-INDEPENDENT-RETEST-2026-09-14.md`、`P0-1-DIAGNOSIS-RETEST2-2026-09-14.md`。
- **DEVELOP-P0-2 全链收口（2026-09-14，本链0/2）**：builder 实现批量恢复闭环（server.py 累计约+837行：retry-plan dry-run/token摘要/TTL10分钟、retry-batch confirm+409零执行+幂等单job、job真源原子写、INTERRUPTED不续跑、三策略、16条双层排除、No-Clobber）→reviewer PASS（P0-2-RECOVERY-CODE-REVIEW.md，1×P1交qa）→qa 首轮撞真实 `_diag_alternate_paths` 扫 ~/Downloads 卡死（单条10秒＋不返回，工具超时无报告）→builder SCAN-FIX 有界重写（2s/2000目录预算、跳过云同步根大目录、Volumes只扫顶层、fail-closed）→reviewer SCAN-FIX复核PASS→qa 复验PASS无新增BUG（P0-2-RECOVERY-QA-2026-09-14.md，11项全过：77=61+16可复算、幂等单job、三409、INTERRUPTED、No-Clobber、两路fail-closed、真函数tmp计时54.2ms）→supervisor PASS。已知缺口（不拦收口）：D-20/D-21执行级注入与真并发、P1-1真机转写端到端；RETRANSCRIBE恒whisper=0如实fail-closed。报告见上。账本45行、派工21行，schema均exit 0。`app/server.py` 未提交未推送。
- **DEVELOP-P0-3 中链（2026-09-14，本链 0/2）**：builder 实现 FR-13 四层状态与监听脱钩、FR-14 首屏统一恢复入口（`#recoverBox` 三按钮＋whisper 成本文案）、FR-17/D-23 可退出反馈（`say` 截断 120 字＋3 秒清；长文只进可关闭面板，含关闭按钮/Esc/遮罩/焦点返回；浅色默认未动）。工作树 `M app/index.html`＋`M app/server.py`（+112/−11，基于 b94845e，未提交）→ code-reviewer **PASS**（`docs/review/P0-3-STATE-ENTRY-CODE-REVIEW.md`；1×P1「旧三入口未删」交 qa/supervisor 裁决＋2×P2）→ qa **PASS**（`docs/qa/P0-3-STATE-ENTRY-QA-2026-09-14.md`：tmp 合成 4/4 mismatch 全降级 `NEEDS_HUMAN`、`state.db` SHA-256 未变；三态监听/复制短句/面板四退出/窄屏全过；留 P1「表头『重试全部失败』＋词库区『全部应用新词库重跑』＋详情高级『应用新词库重跑』仍残留」＋P2「`#msg` 无点击关闭」）。**差 supervisor 复检，尚未收口。**
- **账本补记（TM，2026-09-14 本轮）**：P0-3 三行派工（builder/code-reviewer/qa）＋`TASK-MODEL-LOG` 一行由 TM 依根表补记——上窗口收工时未落盘（`DISPATCH-LOG` 21→25 行、`TASK-MODEL-LOG` 45→46 行）；supervisor 复检时两道校验 exit 0、模型逐字对齐根表、三处对账一致。
- **supervisor 复检 P0-3＝打回 1/2（2026-09-14，复检节在 `docs/qa/P0-3-STATE-ENTRY-QA-2026-09-14.md:42` 起）**：唯一打回项 **P1-1（阻断）FR-14 收敛未完成**——旧三入口实测仍在（`app/index.html:605` 表头『重试全部失败』绑 `retryAllFailed`，与首屏箱『重新转写』同函数属纯重复；`:270` 词库区『全部应用新词库重跑』；`:742` 详情高级『应用新词库重跑』），P0-3 DoD 明文验收句「全文不再出现三个互不关联的批量重跑入口」不达成，等于用户「追加反馈二」投诉未闭环。返工要求（Change A/B 级、留 DEVELOP、不召 Planner）：① 删表头与词库区两个批量入口；② 删除后 `#recoverBox` 需就地给出**范围**（当前所选／全部已完成）并沿用既有 confirm 语义（转写 0 次／库内改过跳过／不覆盖）；③ 详情高级单条允许保留但文案须标明"当前任务"与首屏区隔、全文不得再出现第二个批量入口；④ 删 UI 入口不得动后端 API/函数。2×P2 记 backlog 不返工。FR-13/FR-17/主题浅色默认经复测无回归。
- **P0-3 返工一轮（2026-09-14，supervisor 仍 1/2）**：builder 按四条收敛旧入口（删表头＋词库区批量入口、`#recoverBox` 就地范围 radio、`reapplyAll/reapplyOne` 范围分流、详情标明"当前任务"；server 零改动）→ code-reviewer 复核 **FAIL（新 P1-1 阻断）**（`docs/review/P0-3-STATE-ENTRY-REWORK-REVIEW.md`）：`btnRecPublish` 与详情 PUBLISH_BLOCKED「重试入库」文案承诺"whisper 0次"但实际只调 `retryRun→POST /api/retry`（必走转写或静默跳过），承诺不兑现；①②③④旧要求全 PASS；另裁决词库候选区「错词重跑」保留（FR-9 不回退，属豁免项，title 去术语）。
- **P0-3 返工二轮（2026-09-14）**：builder 首选改法新增 `publishOnlyRetry(run_id)`（约 `index.html:1098`）走 P0-2 已有 PUBLISH_ONLY 通路（retry-plan 取 plan/token→retry-batch confirm 单条，`run_ids:[id]`；非 PUBLISH_ONLY fail-closed 零执行）；三处接线（首屏 `#btnRecPublish`／行级 `data-retry-publish`／详情 failbox），只改 `index.html`。→ code-reviewer **PASS**（`docs/review/P0-3-STATE-ENTRY-REWORK2-REVIEW.md`；1×P2 术语残留不拦）→ qa **FAIL（新 P0：`QA-P03-RR2-001`）**（`docs/qa/P0-3-STATE-ENTRY-RETEST2-2026-09-14.md`）：静态全 PASS，但 tmp 真 handler 发现 `_diagnosis_item()` 把正常 `PUBLISH_BLOCKED`（展示 `FAIL`）字面判 mismatch，经 FR-13 降级门变 `NEEDS_HUMAN`，retry-plan `PUBLISH_ONLY eligible` 恒 0，前端链路实际不可达。属 QA 挂，不计 supervisor 打回。
- **P0-3 语义修复（2026-09-14，仍 1/2）**：builder 只改 `app/server.py` 约 `:1339` 起 mismatch 判定一块——语义归一化（`display==FAIL` 时持久态属 FAIL 家族 `FAIL/PUBLISH_BLOCKED/TRANSCRIBE_FAILED/RAW_FAILED/MIRROR_FAILED/NORM_RENDER_FAILED` 即不算 mismatch，口径与 `_scan_disk_states` 一致；其余字面比较；真 mismatch 仍 fail-closed；零 DB/manifest/产物写）→ code-reviewer **PASS**（`docs/review/P0-3-SEMANTICS-FIX-REVIEW.md`；1×P2 provenance 加性注记；server 计数 `28/3` vs 报告 `+19/−3` 口径差已由 neat 加注待 supervisor 裁定）→ qa **PASS**（`docs/qa/P0-3-SEMANTICS-FIX-QA-2026-09-14.md`：`QA-P03-RR2-001` CLOSED——正常 `PUBLISH_BLOCKED→AUTO_PUBLISH/PUBLISH_ONLY/eligible=1/whisper=0`，真 mismatch 仍 `NEEDS_HUMAN/MANUAL_REVIEW`，`state.db` SHA-256 前后不变，静态回归全过；真实 whisper/batch 发布/HTTP 服务/真机 UI 未跑）。**→ supervisor 复检 2026-09-14 23:31 PASS（收口）**（复检节在 `docs/qa/P0-3-SEMANTICS-FIX-QA-2026-09-14.md` 尾：计数口径裁定 `28/3` ＝返工前 `19/3` ＋语义修复净增 9 行（`_FAIL_SEMANTICS`＋归一化分支＋8 个只读 provenance 字段），逐行归因无未申报内容→**属修复前快照口径、非失实、不打断口**；两账本 exit 0；三处对账一致；Phase Integrity 五查过；红线抽查过；无 blocking。遗留 2×P2 与「真实 whisper／batch 发布／HTTP 服务／真机 UI 未跑」作已知缺口不拦收口）。
- **暂停前收尾（2026-09-14 23:27，neat-freak PASS）**：四份报告加注对齐（历史快照正文未动）、删 2 个 `.DS_Store`（仓根＋`docs/`）、`__pycache__` 本就为空、`git diff --check` 通过；未动业务/文档文件，未碰 `008林粒粒AI编程/`；`env.err`、`results/*.log` 保留。详见文末「收尾记一笔（neat-freak，2026-09-14本轮）」。
- **账本（TM，08:56 P1-3 收口版）**：`DISPATCH-LOG` 45→**57** 行（本 P1-3 链 **业务 11 派**：builder×5／code-reviewer×4／qa×2 ＋ **supervisor 复检 1 行**，全 `used=主`，模型与 runtime 逐字对分工表；其中 builder 首派因平台 429 中断记 `FAIL` 并如实留痕）；`TASK-MODEL-LOG` 49→**50** 行（本链任务级行 `DEVELOP-P1-3（…）` 由 builder 写初版→supervisor 校验→TM 判 **PASS**，`rework=0`＝本链 supervisor 打回 0 次口径）。两道校验回跑 **exit 0**（TASK 50／DISPATCH 57）；supervisor 复检独立校验并加坏行负控、三处对账 0 不匹配。（此前 01:05 口径：DISPATCH 45、TASK 49。）**本链已报 token：QA 首轮约 111k、QA 复验约 170k（codex 侧）；本窗口各派未计数。**
- **工作树现状（2026-09-15 08:52，P1-3 已提交前快照）**：7 改 ＋ 2 新（`app/index.html` 232/32、`app/server.py` 416/70、`tests/selftest_p1_2_contract.py` 413/0、`tests/selftest_p1_2_frontend.py` 346/1、`docs/handoff/HANDOFF.md` 30/17、`docs/model/DISPATCH-LOG.jsonl`＋12、`docs/model/TASK-MODEL-LOG.jsonl`＋1；新增 `docs/review/P1-3-SEMANTICS-CODE-REVIEW.md`、`docs/qa/P1-3-SEMANTICS-QA-2026-09-15.md`）；`git diff --check` 通过；无游离/未跟踪杂项；**扫描无密钥命中**。**服务：8765 无监听。** 上一提交 `3af2da7`（HANDOFF 回写）＝提交前 HEAD，与 `origin/main` 0/0。**注：supervisor 复检提过本行早期快照三个数字（231/32、347/1、＋6）有误，已按实测改正。**
- **提交推送（TM，23:35）**：用户给分支名 `main` 后动 git——`git add` 只加申报的 12 个文件（`app/index.html`、`app/server.py`、HANDOFF、两账本、7 份新报告），提交前扫敏感（无命中），commit **c753b15**「DEVELOP P0-3收口…全P0清」，`git push origin main` → `b94845e..c753b15`；提交后工作树干净、`HEAD==origin/main` 逐字一致。
- **DEVELOP-P1-2 全链收口（2026-09-15 01:05，本链 supervisor 0/2）**：用户「继续推进」后按 Plan 优先级取 **P1-2（blocking）任务身份与 API 契约加固**，共 **10 派**：builder 首版（严格类型层＋data_root/job_id 绑定＋字段一致＋候选版本锁＋部分更新安全＋错误脱敏，`server.py +547/−187`，自测 257/19）→ code-reviewer **PASS**（无 P0；2×P1 错误出口漏脱敏 `:4435`／`:5417`＋7×P2；仓内调用点 0 漏改）→ builder 返工（脱敏出口补全＋`/api/start` 出网闸门＋`_strip_paths`＋摘要白名单＋realpath 口径＋无参回 `job:null`＋`absent` 409；320/22）→ 复核二 **PASS 8/8**（新 P2-新1：数据目录框空时进度静默停表）→ builder 修 P2-新1（`_take_required_data_root`＋前端 `effectiveDataRoot`／`vocabJobDataRoot`＋人话兜底；337/34）→ **复核三 FAIL**（新 **P1-三1 阻断**：异步壳把 `ob_vault_root=None` 写回 params，笔记库框留空（界面明写"选填"）时核心动作 100% 失败；另 P2-三1 409 接管静默、P2-三2 测试假信心）→ builder 修复（缺键不写回＋409 接管人话＋9g 钉终态＋`isAbsRoot` 本地拦＋文案统一；379/41）→ 复核四 **PASS 5/5**（并验证 9g「有牙」：临时改回旧形态→rc=1；新发现 0×P0/0×P1/0×P2＋3×P3）→ qa 首轮 **FAIL**（业务 BUG＝0：contract 347/0＋前端 41/0＋回归 58/0＋D-22 脱敏扫描过；唯一 FAIL 是环境阻塞 `QA-ENV-HTTP-001`＝codex 沙箱禁 bind 临时端口）→ 放开沙箱补跑 **HTTP 33/33 PASS**、`QA-ENV-HTTP-001` CLOSED → **supervisor 复检 PASS**（三套自测 379/41/58 exit 0；审查意见逐条在位；P1-三1 独立真 HTTP 复验通过；两道校验 exit 0；三处对账 10 行 0 不匹配；五查过；无 blocking）。报告：`docs/review/P1-2-CONTRACT-CODE-REVIEW.md`（首轮＋复核二/三/四）、`docs/qa/P1-2-CONTRACT-QA-2026-09-14.md`（含 HTTP 补跑节＋supervisor 复检节）、新增测试 `tests/selftest_p1_2_contract.py`（379）／`selftest_p1_2_frontend.py`（41）。
- **supervisor 非阻断待办（P1-2 收口时留给 TM）**：① QA 报告「## 结论」段仍有旧句「HTTP 部分未跑，不能推断为通过」（`:7`／`:52`），裁定为**低报文字残留、不阻断**，要求就地加注勘误指向 HTTP 补跑节——挂收尾 neat-freak 一并办；② HANDOFF 执行链本 10 派已由本节补记。
- **P1-2 挂账（TM 定，不在本链修）**：复核方首轮 **P2-7**「前端 `/api/retry`（`index.html:1087`／`:1156`）不带 `data_root`，单条/批量重试目标取监听态而非本页目录」——属任务身份同源缺口，但需扩 `/api/retry` 契约（Change B 级），与 P1-3 同批处理更省；已记 `docs/review/P1-2-CONTRACT-CODE-REVIEW.md` backlog。P3 全部（首轮 5＋复核二 4＋复核三 3＋复核四 3）仍挂 backlog，按 V1.3 处置表分流。
- **P1 编排顺序（TM 定，记一句原因）**：先做**代码类** P1-2（blocking）→ P1-3/P1-4/P1-5/P1-7（S）→ P1-6（M，视觉布局，用户追加反馈二原项）→ **P1-1（blocking）最后**。原因：P1-1 是真实规模/长视频/61 篇基准的重验证活，需真实 whisper 与长耗时，契约（P1-2）未固化前跑会重复实测；HANDOFF 已把「真实 whisper 未跑」记为已知缺口。用户如要换序，一句话即改。
- **提交推送（TM，2026-09-15 01:12）**：用户答「main！」后动 git——`git add` 只加申报的 9 个文件，提交前扫敏感（无命中），commit **92fa77e**，`git push origin main` → `d7540d8..92fa77e`，提交后工作树干净、`HEAD==origin/main`。
- **DEVELOP-P1-3 全链收口（2026-09-15 08:45，本链 supervisor 0/2）**：P1-2 收口后按顺序续做 **P1-3「进度与批量语义修正」**（S，非 blocking；`CHANGE_REQUEST=B`——P2-7 扩 `/api/retry` 契约只更新局部 Requirement/DoD，留 DEVELOP、不召 Sol Planner）。共 **11 派**：
  - **① builder 首派（FAIL，429）**：跑到 7 分 46 秒因平台限流中断（无报告），把半成品留在工作树（约 +474/−82），其中 `index.html` 新函数 `vocabApplyPct` 未同步自测白名单 → `selftest_p1_2_frontend.py` 当时 **rc=1**（`ReferenceError`）。**如实记 FAIL 不掩盖**；恢复窗口第一件事就是查出这个半成品并续做。
  - **② builder 续做（PASS）**：通读半成品判「大方向正确、4 处做歪或没做完」，保留其余、补齐七项（含 P2-7：`/api/retry` 带 `data_root`，跨目录 409 零执行、相对路径 400、缺键沿用旧行为），自测 427/68/58 全绿，反向证伪 13/13 咬住。
  - **③ code-reviewer 首轮（PASS）**：无 P0/P1；4×P2＋9×P3；**独立复现反向证伪 4 条全 rc=1**；D-12 全量扫描 547 行 0 命中；报告 `docs/review/P1-3-SEMANTICS-CODE-REVIEW.md`。
  - **④ builder 返工 P2-1／P2-2（PASS）**：只改 `index.html`＋自测（**server.py 0 改动**）——批量重试文案改为「需保持本页打开」（原文案承诺「可离开/后台继续」与事实相反，因该批是页面内循环）、摘掉共用锁定提示里的越界承诺、409/400 原因透传用户眼前＋本地前置门；自测 429/86/58。
  - **⑤ code-reviewer 复核二（PASS）**：真起 `ThreadingHTTPServer` 实测 `/api/reapply` 同步语义成立（客户端 RST 后活儿仍跑完）；自抽 4 条反向证伪 rc=1、sha256 对上（server.py 哈希与首轮同＝后端 0 改动铁证）。
  - **⑥ qa 独立 QA（PASS）**：无 P0/P1；合同 429/0＋前端 rc0＋词库 rc0＋**独立坏例 16/16**＋**随机端口真 HTTP rc0**（本轮 sandbox 由 TM 放宽为 workspace-write＋网络，**唯一目的是 bind 临时端口**，已记）；确认 1×P2（`QA-P13-P2-3-UNKNOWN-STATE`）＋1×P2 既有（`QA-P13-P2-4-REAPPLY-MUTEX`）；真机 UI 如实标 `NOT_VERIFIED`；约 111k tokens。
  - **⑦ builder 返工 P2-3（PASS）**：五桶判据收敛为**唯一真源** `STATE_BUCKET`＋`_state_bucket()`（`server.py:1746-1800`），`_recovery_bucket`／`_reapply_result_bucket` 两链同源派生；`ok=True`＋未知 state → **failed**（原来落 success）；自测 439。
  - **⑧ code-reviewer 复核三（PASS）**：AST 穷举独立确认**成功态清单无漏项**（`PUBLISH_ONLY` 确为 strategy 非 state）；反向证伪 A/B 方向相反且都有牙；新提一行级 P2-三1（`state=""` 口径）判「本批顺手修」。
  - **⑨ builder 返工 P2-三1＋P3-新1（PASS）**：判据改 `if "state" in item:`（`""`／空白／`None` 全落 failed，**只有键不存在**才回落 ok）；删 `#batchLockHint` 越界尾句；自测 445/87/58。builder 并**主动更正**上一轮一处自陈失实（上轮报「`state=""`→failed」与当时代码相反）。
  - **⑩ code-reviewer 复核四（PASS）**：**采纳 builder 口径并作废自己复核三的 `is not None` 建议**（会给 `None` 那档重造分叉，附反例）；AST 证缺键正常成功不误伤（生产形状零行为变更）；**勘误划掉一条假 P3**（tmp 残留系中断运行产物，非夹具泄漏）。
  - **⑪ qa 复验（PASS）**：同链 resume 续 session；`QA-P13-P2-3` **CLOSED**（未知/空 state fail-closed、缺键仍按 ok 成功、`PUBLISHED` 正常）；无新 BUG；合同 445/前端 87/词库 rc0＋独立坏例与真 HTTP 19/19；两条反向证伪 rc=1 且还原 sha256 一致；`QA-P13-P2-4` 保持 OPEN 进 backlog；约 170k tokens。
  - **⑫ supervisor 复检（2026-09-15 08:52）＝PASS／无 blocking／本链 0/2**：三处对账 **0 不匹配**（HANDOFF 11 派 ↔ DISPATCH-LOG L46-56 ↔ TASK-MODEL-LOG L50，逐行 role/model/runtime/result 与分工表逐字一致）；两账本校验 **exit 0**（TASK 50／DISPATCH 56，并用坏行负控验证校验器确实 exit 1，非空转）；实跑三套自测 445/87/58 rc=0；自写探针 **43/43 PASS**（六类 state 输入：`""`／空白／`None`／未知 → failed、`PUBLISHED` → success、**缺键 → success 不误伤存量**；14 个表内 state 两链同源）；抽检反向证伪 2/2 **rc=1** 且还原 sha256 与基线一致；五查过；红线过；`QA-P13-P2-4` 确认 OPEN＋进 backlog。**并裁定 builder 首派那条 FAIL(429)「该记、记法如实」**。非阻断待办：HANDOFF 早期快照数字（已由 TM 改正）、DISPATCH 补 supervisor 行（已补）、QA 报告行号漂移与「429 vs 445」并存（留 neat 加注）。复检节在 `docs/qa/P1-3-SEMANTICS-QA-2026-09-15.md:150` 起。
  - **链内裁定留痕（TM）**：① 派单书曾把 `PUBLISH_ONLY` 举例为「已知成功态」，builder 核实**全仓只作 `strategy` 出现**后未入表 → **采纳 builder 口径**，TM 举例有误已更正；② 复核三给 `is not None`、builder 给 `"state" in item` → **技术分歧听 code-reviewer**，复核四已裁定采纳后者；③ P2-1／P2-2 属本批新引入且涉「文案与事实相反／新契约被静默吞掉」，**TM 判同批修**（Change A 级）；P2-3 属本链 ④ 范围自证不全，判同批修；P2-4（`/api/reapply` 运行中无互斥，**既有残留**，修复需改内部调用为 `internal=True`）**判 backlog 不返工**。
- **DEVELOP-P1-3 立项（2026-09-15 01:12；已由上条收口）**：范围＝①无目标不画 100%②运行中参数锁定③零目标/坏文件提示④失败统计统一⑤elapsed/可离开提示（不做强制取消）⑥二选一不双空⑦吸收挂账 P2-7；并吸收 V1.3 处置表归 P1-3 的条目（`RERUN-PROGRESS P3-4/P3-5/P3-6`、`CANDIDATE-APPLY P3-2/P3-3/P3-4`、`CANDIDATE-UI2 P3-2`）。
- **模型通道现状**：luna 2026-09-14 多次 capacity（首版那次 patch 落盘但尾部报错、返工三次零落盘）；sol 探针也无回包，属 codex 侧不稳、非本地登录问题。supervisor 已由用户切为 `opencode-go/muse-spark-1.3-contributor`（走本窗口），builder 切为 `opencode-go/deepseek-v4.1-flash`（走本窗口），以 `USER_MODEL_OVERRIDE.md` 为准。
- **本窗口已做准备（暂停前，历史）**：P1-7 改名只读盘点（`index.html` 可见 4 处待改＋`server.py` 兼容 7 处不动）；`data/state.db` 仓根不存在已记账，待核 data_root 真源。工作树未提交未推送（以本节“工作树现状”行为准）。**服务现状：8765 当前无监听**（旧记 PID 12429 已不在，勿再引用该 PID）。
- **Phase1 基线（继承）**：`docs/pm/PRODUCT_PLAN.md`=V1.3；16 条红字真相=用户自移视频、DB 全 QUEUED；HD-1~9 全=A；Readiness 89/83 未达 90 用户已知开工。Phase1 详情见本文后段各节与文末附录。

## 二、下一步的任务

- **下一步（Next Single Action，按序）**：
  1. ~~派 supervisor 复检 P0-3／P1-2~~ **已办**（23:31／01:05 均 PASS）。
  2. ~~P1-3 链~~ **已办（2026-09-15 08:45 全链收口）**：11 派＋supervisor 复检，`QA-P13-P2-3` CLOSED，当前无未收口 P0/P1。
  3. **P1-3 交付已提交推送 `main`**（用户已授权：今后 commit/push 默认走 `main`，不再逐次问）。
  4. **下一个默认做 P1-4**（脱敏摘要复制 HD-2=A，S；用户如要换序一句话即改）。
  5. P1 顺序（TM 定）：**P1-2（已收口）→ P1-3（已收口）→ P1-4 → P1-5 → P1-7 → P1-6 → P1-1**（P1-1 真实规模/长视频/61 篇重验证最后跑）。P1-7 改名盘点已备好（`index.html` 可见 4 处待改＋`server.py` 兼容 7 处不动）。
  6. 若要真机目检 P0/P1 交付：需先起服务（8765 现无监听，PORT 硬编码；改 `app/` 或 `src/` 后必须重启再验）；**自动化禁点真机主题开关**。
  7. 经验／neat-freak 收尾只派一次，等用户说收工再派。
- **人要拍什么板（只问大事，小事不问直接推）**：
  1. ~~P0/P1-2/P1-3 交付 commit/push~~ **已办**：`c753b15`／`92fa77e`／`3af2da7` 均已 push；P1-3 交付本轮提交。**今后默认推 `main`，不再问。**
  2. ~~下一步做哪块~~ **已决**：按 Plan 优先级推进 P1；P1-3 已收口，**默认下一个 P1-4**。
  3. 是否换主用模型：**以分工表为准**；要换谁给精确 ID 才改表，我不自切。
- **待排期 backlog（非阻塞）**：**P1-3 链遗留**——`QA-P13-P2-4-REAPPLY-MUTEX`（运行中 `/api/reapply` 无后端互斥，**既有残留**；修法须把内部调用改 `internal=True` 再上锁，直接加锁会自锁；属局部功能变化，动前判 A/B）×1；code-reviewer 记的 P3（`.upper()` 轻微放宽、`10a4` 源码文本守卫脆性、注释溯源标记、`V25_POSTPASS` receipt 态未入表且**日后改 fail-closed 必须同批决定其归属**、`_recovery_job_read` 硬编码 `interrupted=1`、九处「按 state 归类各写一套」清单）×若干。**P1-2 链 P3 共 15 条**＋**P0-3 遗留 2×P2**（provenance 加性字段、术语残留 `obhint:741`）；22 条 P3 按 V1.3 处置表分流；`data/state.db` 真源待核；benchmark `results/*.log` 19 个保留不删；**真实 whisper／真机 UI 未跑**（各报告「未覆盖项」已如实标注；本链 QA 真机预检标 `NOT_VERIFIED`，未写「真机 QA 已启用」）。

## 三、注意事项及相关规矩（本项目专用）

- **读盘顺序（全体系唯一，别乱）**：AGENTS → `docs/roles/` → 根 `USER_MODEL_OVERRIDE.md`（真源在模板包，本地为镜像）→ 本 HANDOFF → 根 `经验一句话.md` → 任务目标放**最后**。
- **两阶段治理**：`PLAN / WAITING_HUMAN_APPROVAL / DEVELOP / PLAN_REOPEN_REQUIRED`。Phase1 **只许** task-manager／supervisor／planner(Sol)／product-reviewer(FREE)，**禁** builder／code-reviewer／qa／业务代码改动／Release；只有用户明确说"第二阶段，开发"才进 Phase2。
- **派工显式**：每派必先贴「正在调用 XX｜主用精确ID＋Runtime／备用精确ID＋Runtime」，收工必贴「XX 回来了 PASS/FAIL＋实际走主还是备」；HANDOFF 执行链与账本记同一行。
- **固定通道：以根 `USER_MODEL_OVERRIDE.md`（分工表）为准，本行只是方便速览、冲突以表为准**：builder=`opencode-go/deepseek-v4.1-flash`（本窗口）；supervisor=`opencode-go/muse-spark-1.3-contributor`（本窗口）；code-reviewer／experience-recorder／neat-freak=`opencode/muse-spark-1.3-contributor-free`（本窗口）；planner／senior-expert=`codex/gpt-5.6-sol`（codex）；qa／product-reviewer=`codex/gpt-5.6-luna`（codex）。**主用不可用即停派找人，禁自动切备用/降级；换模型用户定。**
- **模型/通道唯一真源＝根 `USER_MODEL_OVERRIDE.md`（分工表，4 列，本仓最新版 mtime 2026-09-14 18:55；用户 2026-09-14 明确「按分工表为准，其他全是旧的说法、历史的垃圾」）**：本文件、`docs/roles/` 角色卡、`经验一句话.md`、`~/.agents/model-routing/USER_MODEL_OVERRIDE.md`（2026-09-11 旧副本）里出现的一切模型名/执行通道字样**均为历史描述，无约束力**，冲突一律以分工表为准；不再逐处同步旧文案。当前分工表口径：`builder`／`supervisor`／`code-reviewer`／`experience-recorder`／`neat-freak`＝**本窗口 subagent 直派**；`planner`／`qa`／`product-reviewer`／`senior-expert`＝**codex 直调**。主用不可用即停派找人，禁自切备用/降级。
- **推进纪律（用户 2026-09-14 明确）**：小问题不问直接推；P0/P1 尽量解、解不了挂账记报告；除 API 密钥问题外一律往前推。luna capacity 时小步重试＋挂账，不在错基线上盖楼。
- **额度纪律（本轮新增，用户明确要求）**：外部模型单轮动辄数十万 token，**先小步试、及时收**；能本窗口做的别外派；用户说"停"立即停；烧了多少要如实报。
- **升级**：同一 Task 被 supervisor 累计打回 2 次自动升 senior-expert（QA 挂不算），只升当次；换模型/换 Runtime 即开新链。
- **账本**：`docs/model/TASK-MODEL-LOG.jsonl` 一行一任务（schema 锁死枚举）；`docs/model/DISPATCH-LOG.jsonl` 逐派一行（`used` 恒填主）。builder 写初版 → supervisor 校验 → TM 判结果落盘。
- **红线**：**不 push**（commit 需用户明确给分支名）；**不碰 secrets**；不改 V1.10/V2.0 封存；`docs/sop/` 仅模板示例。
- **数据安全**：测试只用**外置 tmp ＋ 合成数据**；用户真实视频目录与 Obsidian 库**禁写**（只读浏览例外）；**凡调 handler 的测试，首行必须断言 `data_root` 在 tmp 下**（污染事故补丁）；只读真实库时先拷到 tmp 查、**用完即删**。
- **No-Clobber**：已发布笔记**永不覆盖**（EXISTS/CONFLICT 只判不写）；缺失 vault 不重建；user-edited ＝ 一切字节差异。
- **服务**：`stage0bench venv python` 跑 `app/server.py`，固定 **8765**（PORT 硬编码）；**改 `app/` 或 `src/` 后必须重启服务再验**；**当前 8765 无监听**（本轮实测；旧记 PID 12429 已不在，要真机目检先由用户或 TM 起服务）。
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

---

## 收尾记一笔（neat-freak，2026-09-14本轮）

- 范围：只改对应 docs 原文加注＋本节＋清系统产物；未改业务代码，未 commit/push，未碰 secrets，未碰 `008林粒粒AI编程/`。
- 报告核对（结论/计数/引用行号 vs 当前工作树 `M app/index.html 181/31＋M app/server.py 28/3`，基于 b94845e 未提交）：
  - `docs/review/P0-3-STATE-ENTRY-REWORK2-REVIEW.md`（PASS）：`publishOnlyRetry:1098` 在约 1093-1137 内 ✓；三处接线（首屏 1821／行级 658／详情 752）✓；批量三入口全文 0 命中 ✓；`obhint:741` 文案与 P2-1 描述逐字一致 ✓；`btnCandidateApply` title 已改用户语言（:251）✓；`rerun_old` confirm「转写0次」在 1396 行前后 ✓；index `181/31` 与工作树一致 ✓。server 记 `+19/−3` 属返工前 carryover 口径，无新增后端改动断言成立。
  - `docs/review/P0-3-SEMANTICS-FIX-REVIEW.md`（PASS）：`_FAIL_SEMANTICS:1342` ✓；`_scan_disk_states:660`、docstring `:664-665`、失败映射分支 `:713-716` ✓；`display_persisted_mismatch` 唯一写点 `:1373` ✓。**不一致 1 处**：报告记 server `+19/−3`，工作树实测 `28/3`，差 9 行插入（疑 provenance 字段计数口径差）——已在该文件尾加注，正文未动，待 supervisor 裁定。
  - `docs/qa/P0-3-STATE-ENTRY-RETEST2-2026-09-14.md`（FAIL，`QA-P03-RR2-001` OPEN）：当时快照无误；该 BUG 已在语义修复链 CLOSED（`docs/qa/P0-3-SEMANTICS-FIX-QA-2026-09-14.md`）——已在该文件尾加注链路，正文未动。
  - `docs/qa/P0-3-SEMANTICS-FIX-QA-2026-09-14.md`（PASS，`QA-P03-RR2-001` CLOSED）：断言输出（`AUTO_PUBLISH/PUBLISH_ONLY/eligible=1`、真 mismatch 仍 `NEEDS_HUMAN`、哈希 `3a88…19b` 前后不变）均为当时取证值，未复跑；静态回归项与当前工作树一致（批量 0 命中、文案/三态/面板/窄屏均在位）。未改动该文件。
  - `docs/qa/P0-3-STATE-ENTRY-QA-2026-09-14.md` 尾部 supervisor 复检节（打回 1/2）：历史快照，只加注不改正文——当时 `+112/−11`、账本 46／派工 24，当前已为 `+209/−34`；当时行号 `:605/:270/:742` 为旧位置，旧三入口现 0 命中；P0-3 本链打回计数仍为 `1/2`（语义修复链未新增 supervisor 打回）。
- 清理：删仓根 `./.DS_Store`＋`docs/.DS_Store` 共 2 个；`__pycache__` 全仓本就为空；复查 `find -name __pycache__ -o -name .DS_Store` 输出为空。未删任何业务/文档文件；`env.err`、benchmark `results/*.log` 未动（按要求保留）。
- 未决（P0-3 未收口，差 supervisor 复检；不写收口/完成）：① supervisor 复检语义修复链（含 server `28/3` vs `+19/−3` 计数口径裁定）；② `TASK-MODEL-LOG`／`DISPATCH-LOG` 语义修复链四行（builder/reviewer/qa/语义builder）落盘与 `rework` 口径（仍 1/2）由 TM 定；③ `HANDOFF.md` 工作树 `M`（TM 本轮落盘改动）与四份新报告均未提交未推送，是否 commit/push 待用户给分支名；④ QA 真 mismatch 夹具曾用 `FAILED_RETRYABLE`（旧报告）vs 现实枚举 `*_FAILED` 家族，口径差已记不拦。
