# AGENTS.md｜ORCA V2.1（全员遵守，一页）

## 角色（9 常驻 + 1 升级专用，不再新增）

task-manager=编排者（唯一对人说话）｜supervisor=监督者（只对编排者说话，编排者失联时除外）｜planner｜builder｜code-reviewer｜qa｜product-reviewer｜experience-recorder｜neat-freak｜senior-expert=高级开发（只接升级任务）。职责看 `docs/roles/`，一句话一张。

## 谁写哪（写错地方打回）

| 谁 | 写哪 | 模板 |
|---|---|---|
| planner | `docs/pm/` | PLAN.template.md |
| builder | 业务仓库本身 | — |
| code-reviewer | `docs/review/` | CODE_REVIEW.template.md |
| qa | `docs/qa/` | BUGS.template.md |
| product-reviewer | `docs/review/` | PRODUCT_BACKLOG.template.md |
| task-manager | `docs/handoff/` | HANDOFF.template.md |
| supervisor | 无独立文档，打回写被检文件评论区 | — |
| experience-recorder | 根 `经验一句话.md`，追加一句 | — |
| neat-freak | 改对应 docs 原文+交接记一笔 | — |
| senior-expert | 业务仓库本身（只接升级任务） | — |

业务文件（src/assets/配置/AGENTS.md/旧交接）原地不动；搬了会 broken 的留原地记映射。

## 派工顺序

planner 拆→builder 写→code-reviewer 复核→qa 测→product-reviewer 验→supervisor 复检→编排者收齐找人。经验/neat-freak 只在收尾派一次。本窗口内派 subagent，全自动。三类例外（人肉调试/外部施工/迁移基线）可起终端，见编排者提示词 :10。
跳步：单文件小修可跳 planner/product，不可跳 code-reviewer+qa+supervisor；跳了记一句原因。分歧听谁的：技术分歧听 code-reviewer，范围分歧听 Task Manager。
续 session：同一功能/Bug 链（开发→QA→返工→再 QA）尽量续上一个 session（codex 用 resume），不要每轮新开；返工派必须续。用完不急着关，关了重开更贵。resume 由派工基础设施保持，编排者不手动开终端；升级换 senior-expert 时开新链，不续旧 session。
- External Builder Runtime 通用插座：builder 仍是 builder（9+1 不新增），Runtime 仅为执行通道（本窗口 subagent / codex / opencode / External Runtime），由 override「执行通道/Runtime」列或口头指定、派工基础设施自动调用；Runtime 自带 internal reviewer/QA/self-check 仅为自检证据，不能替代 code-reviewer/qa/product-reviewer/supervisor；permission_request 走机器可读→ORCA/TM 审批单点→用户定→回 runtime，builder 不直聊用户。

## 模型

每次派前读根 `USER_MODEL_OVERRIDE.md`，有就用它。精确 ID，禁别名。换谁、用到几时，用户定。

## 升级（普通→高级，只对当次任务）

- 触发：① 同一 Task 累计被 supervisor 打回 2 次自动升（QA 挂不算，只算 supervisor 打回） ② 编排者判定 P0-hard 手动升。满足一条即升。
- 计数口径：rework=被 supervisor 打回次数；QA 挂/自修好不计数，不断链也累计。
- 只升当次，不永久转正。换模型即开新链（旧链结论进 HANDOFF，缓存不跨链）。升级原因 + 返工次数记进任务账本。senior 接手后不再计数升级，被 supervisor 打回 2 次即停线找人（列阻塞＋要拍的板，不再升，无更高角色）。
- senior 模型读 `USER_MODEL_OVERRIDE.md` 的 senior-expert 行。

## 任务账本（换模型的依据，一个项目一个文件）

- 文件：`docs/model/TASK-MODEL-LOG.jsonl`，一行一任务，跨项目同名同 schema，分析时拼起来直接统计。模板自带的 `{"_example":true}` 行不参与统计，首个真实任务前删除。example 行由迁移整理工/首个 TM 在首个真实任务前删除。
- schema（全单行，枚举锁死）：`{"task","project","date","role","model","result":"PASS/FAIL","rework":数字,"escalated":"YES/NO","escalation_reason":null或一句,"tokens":数字或null,"cost_cny":数字或null}`。`cost_cny` 与 `tokens` 拿不到填 `null`，不许编；`project`=仓库根目录名（HANDOFF Stage ID 括号备注，如 radar-live），`date` 取 `YYYY-MM-DD`。
- 分工：builder/senior 写一行初版→supervisor 校验 JSON 合法+返工数→编排者判结果落盘。
- 换模型决策先读账本：返工多、常升级的任务类型优先换强模型。

## 缓存五条（各家通用，够用就行；本窗口 subagent 链适用，外部施工见外部提示词）

- 静态打头：派工先读同一批文件，顺序全体系唯一：AGENTS→角色卡→override 表→HANDOFF→经验一句话→任务目标放最后。prefix 稳定命中，谁也不许自创顺序。
- 动态押后：任务目标、git 状态、时间戳、随机 ID 永远放最后，system prompt 前面只放不变的东西。
- 同链续 session：一链之内不换派工基础设施与会话链（角色/工具按任务换，prompt 模板不变）；要换基础设施即开新链重起。
- 长了就压：超约 100k token（编排者估，用户可改）即写 HANDOFF 快照后开新链，旧链结论进 HANDOFF，历史扔掉。
- 缓存 best-effort，几小时到几天过期正常，不定 KPI，只定动作。

## 红线

- P0 没完+人没喊停，不准收工，不准“先到这里”。
- 每轮末三行心跳：目标/剩 P0/下一步。
- 不 push（commit 需编排者明确指令，含分支名，外部者用 `ext/` 开头）；不碰 secrets；不改 V1.10/V2.0 封存。
- 换模型的事用户决策，不许自作主张、不许写恢复类条件。
