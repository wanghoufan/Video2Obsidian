
# BUGS

## 测试结论

qa 回来了：**PASS（带 3 个已确认的 P2 缺陷，均非本轮新发现，均可复现）**。

- 测试对象：错词重跑进度显示（`/api/vocab/candidates/apply` 异步化 202 + job_id、`/api/vocab/candidates/apply/status` 只读进度、`app/index.html` 进度条/轮询/续看/终态）。
- 结论：**主功能闭环成立**——异步 202 → 进度可见（total/done/当前文件推进）→ 终态汇总 → 运行中刷新可续看 → 终态清 timer。DoD 6 项全过；reviewer 的 3×P2 **全部复现（成立）**，无新增 BUG。
- 用例统计：**33 项检查，30 PASS / 0 新 FAIL / 3 项为已登记 P2 缺陷复现（成立）**。
- 真机 UI：本轮**有 computer-use，做了真机目检**（Chrome 首页 + 词库/待审页；进度态、确认框、终态均有截图）。UI 目检为主，另用 CDP 对同一页面做 DOM 级数值取证（P2-3 的 500 注入必须用代理 + CDP 才能确定性复现）。

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---|---|---|---|---|
| QA-RR-01 | P2 | 否 | 100% 必现（注入线程创建失败） | OPEN（reviewer P2-1 复现成立） | RERUN-PROGRESS | 起线程失败 → 任务永久钉 running，之后恒 409，需重启进程 |
| QA-RR-02 | P2 | 否 | 100% 必现 | OPEN（reviewer P2-2 复现成立） | RERUN-PROGRESS | `progress_cb=None` 仍多扫一次 state.db（结果等价，性能面） |
| QA-RR-03 | P2 | 否（但直接违背本功能承诺） | 100% 必现（注入单次 500） | OPEN（reviewer P2-3 复现成立） | RERUN-PROGRESS | 单次轮询失败即永久停表：进度与终态永不出现 |

> **收口注记（neat 对齐 2026-09-13）：** 上表 QA-RR-01/02/03 的 OPEN 与本文头部「PASS（带 3 个已确认的 P2）」均为**复验前**状态；返工后独立复验已将三条全部判 **CLOSED**、新增 BUG=0，见 `docs/qa/RERUN-PROGRESS-REWORK-QA-REPORT.md`（末附 supervisor 复检 PASS）。正文结论未改。

## 环境与命令（真机）

- 仓库根：`/Users/zzymima0000/Developer/coding/1.Active/ing丨 0910 本地视频转文字工具`（HEAD `65cfe2c` + dirty，未 commit）。
- **8765 被用户线上服务占用（PID 72407，`venv/bin/python app/server.py`），全程未关闭、未干扰**。
- 测试端口：**8799**（主测试服务）；**8798 → 8799**（QA 注入代理，仅 P2-3 用）。
- Python：`/private/var/folders/mp/mnxk3h8x4wq5ztr7__vlplp40000gn/T/opencode/stage0bench/venv/bin/python3`（3.12.13，mlx 可导入）。
- 起服务命令（repo 外包装，**跑的仍是 `app/server.py` 本体**；`server.py` 的 `PORT` 硬编码 8765，故只能覆盖端口，不能改业务文件）：
  ```
  python3 /tmp/v2o_qa_rr/run_server.py 8799 /private/tmp/v2o_qa_rr/ui_data3
  # 包装脚本内容：import server; server.PORT=8799; server.DEFAULT_DATA_ROOT=<tmp 数据目录>; server.main()
  ```
  附注：包装脚本额外把 `DEFAULT_DATA_ROOT` 指向测试 tmp 目录，作为**防污染硬保险**——即使前端 `data_root` 为空，请求也只会落到 tmp。
- 合成夹具生成（1200 篇：1000 可成功 / 100 无原文跳过 / 100 故意失败；4 条合成候选）：
  ```
  python3 /tmp/v2o_qa_rr/gen.py /private/tmp/v2o_qa_rr/ui_data3 1000 100 100
  ```
  夹具为真实可跑数据：`data/state.db`（sources + processing_runs）+ `data/jobs/<run>/raw/raw.json`（经 `stage1.prepare.build_raw_content` 构造，过 `validate_raw_artifact`）+ `manifest.json`，走**真实** `_reapply_all → _reapply_one → stage3.derive` 链路（转写 0 次）。
- 注入代理：`python3 /tmp/v2o_qa_rr/proxy.py 8799 8798`（把第 N 次 status 请求回 500；`/__qa_stats` 回请求计数）。
- QA 自建脚本全部在 repo 外 `/tmp/v2o_qa_rr/`：`gen.py / run_server.py / api_e2e.py / ui_flow.py / ui_visual.py / p23_cdp.py / edges.py / dod5_409.py / p21_p22.py / cdp.py(极简 CDP) / proxy.py`。

## 数据边界（防污染制度补丁执行情况）

- **凡调 handler 的脚本，首断言即验证 data_root 在 tmp 下**（`realpath` 前缀 `/private/tmp/` 或 `gettempdir()`），且 `!= DEFAULT_DATA_ROOT`；`p21_p22.py` 实测打印 `[guard] data_root=/private/tmp/v2o_qa_rr/edge_norerun 在 tmp 下，非 DEFAULT_DATA_ROOT`。
- 全程**未写**用户真实库 / vault / Obsidian 库 / V1.10 / V2.0 / secrets；未 commit；未 push。
- 反向核对：测试结束后**只读**查用户线上 8765：`ok=True count=307 revision=s9-corr-v2-user-6536029d`（见"未执行/限制"O-1）。

## 用例逐项（步骤 / 期望 / 实际 / 证据 / 结论）

### A 组：API 端到端（服务 8799，data_root=tmp，1200 篇）

| 编号 | 步骤 | 期望 | 实际 | 证据 | 结论 |
|---|---|---|---|---|---|
| A1 | `GET /api/vocab/candidates` | 返回三组候选 + index | `count=4, {high:2, medium:1, low:1}` | `api_e2e.log` T-A1 | PASS |
| A2 | `POST /api/vocab/candidates/apply {indices:[0,1,2,3], rerun_old:true}` | 202 + job_id，立即返回 | `202 {"job_id":"vocab-apply-1-73440","state":"running"}` | `api_e2e.log` T-A2 | PASS |
| A3 | 运行中立刻再 POST 同一请求 | 409 + running + job_id + 人话 | `409 {"running":true,"job_id":"vocab-apply-1-73440","error":"已有一次错词重跑在进行中，请等它跑完再试"}` | `api_e2e.log` T-A3 | PASS |
| A4 | 每 1s `GET .../apply/status` 采样 | running→done；total/done/当前文件推进 | 1.0s `running/rerunning 1200/29 video_01130.mp4` → 12.1s `1200/437` → 24.1s `1200/819` → 36.1s `1200/1197` → 37.2s `done 1200/1200` | `api_e2e.log` T-A4；`server.log`（1.5s 轮询行） | PASS |
| A5 | 终态读汇总 | 成功/跳过/失败三数齐 | `summary={"success":1000,"skipped":100,"failed":100}`；`codesummary=导入3条/重跑成功1000篇/跳过100篇/失败100篇`；`details` 逐条含保留/拒收+原因（`VIP COIN` 撞内置词库被拒收） | `api_e2e.log` T-A4 尾 | PASS |
| A6 | 终态后再 POST 同一批 indices | 幂等：不重复导入、不重复重跑 | `imported=0`，`message=没有候选通过校验，未导入；未执行重跑`，`total=0 done=0`（未再触发 1200 篇重跑） | `api_e2e.log` T-A5 + 后续 status 读取 | PASS |
| A7 | `GET /api/vocab` | 导入生效 | `count=3, revision=s9-corr-v2-user-453dc58e` | `api_e2e.log` T-A6 | PASS |
| A8 | `GET /api/vocab/candidates` 复查 | 已导入项从清单过滤 | `count=1`（仅剩未导入的 VIP COIN） | `api_e2e.log` T-A7 | PASS |
| A9 | 真实规模耗时基线 | — | 1200 篇真实重跑 **37.2~39.4s**（in-process 计 39.38s） | `timing.py` 输出 | 记录 |

### U 组：真机 UI（computer-use，Chrome 真机窗口；data_root=tmp）

| 编号 | 步骤 | 期望 | 实际 | 证据 | 结论 |
|---|---|---|---|---|---|
| U1 | 打开首页 → 滚到词汇区 | 候选清单渲染，high/medium 默认勾选 | 高置信度(2) 两条勾选、中置信度(1) 勾选、低置信度(1) 未勾、`全选` 未勾、`已跑过的也重跑` 未勾、`只对新视频生效` 勾选、`已导入词库（0条）` | 截图 `01_候选清单_非运行态.png` | PASS |
| U2 | 勾 `已跑过的也重跑` | 与 `只对新视频生效` 互斥 | `已跑过的也重跑=1`、`只对新视频生效=0` | AX 值 | PASS |
| U3 | 点 `错词重跑` | 弹二次确认，文案含 No-Clobber 提示 | 原生确认框：「导入所选错词并重跑全部已完成任务吗？\n转写0次，改过的笔记会按 No-Clobber 跳过。」 | 截图 `02_确认对话框.png` | PASS |
| U4 | 点 `确定` 后立即看 | 进入进度态、按钮禁用 | `timer=2(激活)`、`btnDisabled=true`、进度条 0%、文案「正在导入错词并准备重跑…」 | `ui_flow.py` 17.5s 前采样 | PASS |
| U5 | 运行中连续采样 | total/done/当前文件持续推进 | `已处理 44/1200（当前：video_00419.mp4）` → 143 → 246 → 300 → 404 → 625 → 810 → 1003 → 1133/1200 | `ui_flow.py` 采样 1-13；截图 `03_运行中进度_391of1200.png`（另一轮：进度条 33%、「已处理 391/1200（当前：video_00716.mp4）」） | PASS |
| U6 | **运行中刷新页面（续看）** | 刷新后自动接管进行中任务并继续显示进度 | 刷新后 2.5s 内即显示 `已处理 541/1200（当前：video_00607.mp4）`，按钮保持禁用，timer 重新挂上并继续推进（625→1133） | `ui_flow.py` 17.5s 刷新 → 22.3s 采样 | PASS |
| U7 | 等终态 | 显示汇总、按钮解禁 | 进度条 100%、文案「已导入2条；重跑成功1000篇，跳过100篇，失败100篇。词已入库，但重跑失败，请检查失败明细后重试。未给笔记库，库内笔记未更新」、`错词重跑` 恢复可点 | 截图 `04_终态汇总.png` | PASS |
| U8 | **终态清 timer**（静默 12s） | 不再 1.5s 轮询、无刷屏 | 窗口期内新增 `apply/status` = **0**；新增请求仅 6 条（3×`/api/start` + 3×`/api/status?limit=200`，即 5s 自动轮询） | `server3.log` 前后差分（83→89 行，status 29→29） | PASS |
| U9 | 运行中强制再点（绕过 disabled） | 走 409 分支且自愈续看 | 服务端 `409`（`server4.log:142`）；前端 warn 文案被 resume 的进度渲染覆盖后继续推进（137 → 194 → 250/1200），timer 保持 | `dod5_409.py` + `server4.log:142` | PASS |
| U10 | 非运行态勾选：全选 / 单项 / 分组 | 三档联动正确 | 真机：`全选` → 4 条全勾（含折叠的 low 组）；再点 → 全不勾；逐条点 3 条 → 全部=1 / 低=0。分组：CDP 触发同一 `onchange`（`[data-candidate-group]`）→ 取消 high 组其子项全 0、勾 low 组其子项全 1、`全选` 同步态正确 | AX 值序列；`group` 用例输出 | PASS（分组为功能级，非视觉，见限制 L-3） |
| U11 | 词库列表 / 折叠 / 过滤 | 三件套正常 | 列表 3 条（`我自己加的（3条）`）；过滤「转问」→1 条；过滤「zzzz」→0 条 + 兜底「暂无匹配词条」；清空→3 条；`<details>` 分组与 `已导入词库` 折叠可开合 | CDP DOM 计数 + AX `开合三角标记` | PASS |

### E 组：边界（CDP + 真机页面，data_root=tmp）

| 编号 | 步骤 | 期望 | 实际 | 证据 | 结论 |
|---|---|---|---|---|---|
| E1 | data_root 无候选文件 | 空态文案 + 禁操作 | 清单显示「暂无待审候选，去跑一次AI审查生成清单（找编排者要提示词）」；`错词重跑`/`全选` 均 `disabled=true` | `edges.py` E1 | PASS |
| E2 | 0 篇已完成（有候选）+ rerun_old=true | 明确「无稿可重跑」，不报错 | 「已导入3条；重跑成功0篇，跳过0篇。未给笔记库，库内笔记未更新」；timer=null；绿条 100% | `edges.py` E2 | PASS（观感见 O-5） |
| E3 | rerun_old=false | 只导入、老稿不动 | 「已导入3条；未重跑老稿，老稿未动」；候选被标记 imported（与旧语义一致） | `edges.py` E3 | PASS |
| E4 | data_root 只读（词库保存失败） | **失败态可见且有原因**、红条 | `state=failed`；`cls=hint err`、进度条 `var(--red)` 100%、文案「词库保存失败，未生效：[Errno 13] Permission denied: '.../vocab-user.json.tmp'→检查磁盘空间/目录权限后重试」；按钮解禁可重试 | `edges.py` E4；截图 `06_E4_失败终态.png` | PASS |
| E5 | 混合终态（含 100 篇失败） | 失败数可见且带原因提示 | 「…重跑成功1000篇，跳过100篇，失败100篇。词已入库，但重跑失败，请检查失败明细后重试…」（warn 态） | `04_终态汇总.png` | PASS |

### R 组：reviewer 3×P2 定向打风险（本组为 reviewer 结论的独立复现）

| 编号 | 复现方法 | 实际（含原始输出） | reviewer 结论判定 |
|---|---|---|---|
| R1 = P2-1 `server.py:2284-2305` | 注入 `threading.Thread.start = raise RuntimeError` 后直调 `_handle_vocab_candidates_apply`（tmp data_root，首断言已过） | 第1次：handler **抛异常**（外层 `do_POST` 兜底 → 500「服务开小差」）；`_vocab_apply_job.state = running`；第2次 `409`；第3次仍 `409`。原始行：`结论: 起线程失败后 state=running，后续调用恒为 409（需重启进程才能恢复）` | **成立**（复现 100%；确需重启进程） |
| R2 = P2-2 `server.py:4295-4304` | 计数 `_run_source_path_map` 调用次数，2 篇数据集，分别 `progress_cb=None` / `=fn` | `progress_cb=None: 调用次数=3`；`progress_cb=fn: 调用次数=3`。3 = `_reapply_all` 无条件 1 次 + 每篇 `_reapply_one` 1 次×2。**None 时的那 1 次即多扫**，结果面等价 | **成立**（性能面；结果无差异） |
| R3 = P2-3 `index.html:1228` | 8798 注入代理，第 6 次 status 回 500（真实 1200 篇在跑） | 失败前 `count=5`、`timer=2`、`btnDisabled=true`、「已处理 139/1200（当前：video_00249.mp4）」；失败后立刻 `failed=1`、**`timer=null`**、`running=false`、`btnDisabled=false`、文案**冻结在 139/1200**、进度条停在 11%；其后 **24s（16 个轮询周期）`status_count` 恒为 6，0 次新请求**，终态永不出现 | **成立**（且直接命中用户原始痛点「不知道跑完没有」；自愈仅靠重按/刷新） |

## 未执行 / 限制（别当已验）

- **L-1** 未跑用户真实库/真实 vault 的端到端重跑（只读边界）；用户线上 8765 全程未使用。
- **L-2** 未验真实 whisper 阶段（本轮语义就是转写 0 次）。
- **L-3** `[data-candidate-group]` 分组勾选框在 Chrome 无障碍树**未单独暴露**，且 `click --x/--y` 在本窗口**实测无效**（对已知元素也不生效，已用全选勾选框反证）；故分组联动改用 CDP 触发**同一个 `onchange` handler** 验证（功能级，非视觉级）。
- **L-4** P2-1 的线程创建失败为**注入模拟**，非自然线程耗尽。
- **L-5** 未验多标签页 job_id 串扰（reviewer P3-3）、`status` 忽略 `data_root` 的跨目录显示（P3-2）、无超时/无取消（P3-6）。
- **L-6** 未做长视频/超大批量（>1200）表现；1200 篇基线 37~39s。

## 观感 / 非阻塞观察（不进 BUG，供编排者决策）

- **O-1** 用户线上 8765 现为 `count=307 / rev s9-corr-v2-user-6536029d`，与 HANDOFF 记的「303 条 / rev s9-corr-v2-user-977413c8」不同。**与本次测试无关**：本轮所有 POST 只打到 8799 且 data_root 全在 tmp（8765 一条写请求都没有）。推测是用户自己按 HANDOFF 下一步「亲手点一遍错词重跑」导入 4 条所致，建议编排者与用户对一下账。
- **O-2** 真机 UI 测试需要真实浏览器，**在用户正在使用的 Chrome 里开过一个标签页**（现指向 127.0.0.1:8799）。收尾时 AX 不暴露标签 URL、无法安全区分我开的标签与用户自己的控制台标签，**故未关闭**，请用户手动关掉多余的 `V2O · 本机控制台` 标签。测试期间用户也在用同一浏览器（期间出现过一次地址栏交叠），已尽量仅用元素级点击避开。
- **O-3** 页面加载时 Chrome 会弹「127.0.0.1:8799 想获得以下权限：显示通知」——这是页面主动申请通知权限，不是缺陷，但会遮挡操作。
- **O-4** 词库区在 200 行任务表下方，真机需要按 End 才能看到；仅操作备注。
- **O-5** **复现 reviewer P3-4**：E2「零可跑」仍画绿色 100% 满条，与"什么都没发生"语义冲突（文案本身准确）。

## Fix Attempt Fingerprint

- Task ID: rerun-progress-qa-2026-09-13
- Root Cause Hypothesis: 本轮为功能验收复测，非返工修复；三条 P2 的根因假设与 reviewer 一致——P2-1 建单置位与起线程不同段且无 try、P2-3 catch 里无条件 `vocabApplyStopPoll()`。
- Approach: 真机起服务（8799，8765 不动）+ 合成 1200 篇真实可跑夹具 + computer-use 真机目检 + CDP DOM 取证 + 注入代理制造瞬时 500 + handler 级定向注入。
- Files Changed: **仅新增本报告**；未改任何业务代码，未 commit/push。
- Verification: 33 项：30 PASS、0 新 FAIL、3 项已登记 P2 复现成立。
- Failure Reason: 无（本轮为验收，非修复）。
- Difference From Previous Attempt: 首次对 202/409/status/续看/终态清 timer 做**真机 + 真实规模（1200 篇）**端到端；首次对 reviewer 3×P2 逐条做**可复现判定**（含 P2-3 的确定性 500 注入）。
