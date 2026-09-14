# BRIDGE_INTEGRATION_CONTRACT

DeepSeek Bridge 作为 **ORCA V2.1 builder 角色的 External Builder Runtime / Execution Channel** 的最小机器接入契约。
面向 V2.1 执行优化者与派工基础设施实现者；不含 Registry / Promotion / 新角色 / 新治理状态机。
架构固定：`ORCA V2.1 Task Manager → DeepSeek Bridge → DeepSeek Official ACP → DeepSeek Official Harness → DeepSeek API`。
机制细节见 [ARCHITECTURE.md](ARCHITECTURE.md)（§8–§10）；本文只给接入面。

> 分发注记（2026-09-11，随 ORCA V2.1 治理模板分发版拷入包根，原件在业务仓 `Infrastructure/orca-deepseek-bridge/docs/`，两边内容一致；Contract 更新时以业务仓为准重拷；ARCHITECTURE/tools/runtime 系业务仓路径，模板包仅含接入面，激活前回仓核对）。

## 0. V2.1 Compatibility Verdict

**PASS**（2026-09-10，生产接入收口实测）。

仍需治理模板配合的最小接口（共 3 项，①②已落地——模板侧 Runtime 列＋编排者派发口在位，2026-09-11 复核；③待 V2.1 执行优化者）：

1. ✅ 已落地：`USER_MODEL_OVERRIDE.md` 规则行——A通道模型列写精确 ID `deepseek-flash`、Runtime 列写 `deepseek-bridge`（route `deepseek-bridge/deepseek-flash` 只记备注禁入 Model 列）即启用本通道，仅用户改表/口头指定时生效；旧 `deepseek-bridge/deepseek-v4-flash` 为兼容 alias。
2. ✅ 已落地：`编排者提示词.md` 派发口一句——已正式接入的外部 Builder Runtime / Bridge 由派工基础设施自动调用，不算"起终端"；TM 不人工开终端/复制 Prompt/QA/Reviewer/Session ID/历史上下文；resume 由派工基础设施维护。
3. ⏳ 待 V2.1 执行优化者：治理模板中 External Builder Runtime contract 一节（复用"外部开发者提示词.md"的安全思想，但不套用其 EXT-WORKLOG/人工外请模式）。本文件即其技术输入。

## 1. Execution channel / route 标识

- 逻辑 route：`deepseek-bridge/deepseek-flash`（builder 插槽专用；禁别名）；旧 `deepseek-bridge/deepseek-v4-flash` 为兼容 alias（官方暂路由至 V4.1 Flash），禁作新默认。
- 稳定 Runtime Channel ID（2026-09-11 新契约定义，非历史字段）：`deepseek-bridge` = ORCA V2.1 External Builder Runtime 的内部执行通道标识（非 DeepSeek 官方字段；禁当 model ID 用）。此前文件无独立 machine-readable runtime_channel_id，特此定义；不改 Bridge 实现、不改进程链。
- 当前 canonical 三元组（2026-09-11 Gate APPROVED）：model `deepseek-flash`（DeepSeek V4.1 Flash 正式调用名，官方 2026-09-10 发布；真链 Probe session `0018f7b3` 验证）＋ runtime `deepseek-bridge` ＋ route `deepseek-bridge/deepseek-flash`。§0/§16/§18.1 中的旧 route 一律读作兼容 alias（官方暂路由至 V4.1 Flash），不得再作新默认 canonical。
- 进程链（由派工基础设施自动拉起，禁止 TM 手动操作）：
  `node tools/orca/supervisor.mjs --workspace <ABS_WS> --role builder`（前台普通 shell 终端内常驻；supervisor 自动托管 bridge，见 §11–§13）。

## 2. 精确 Model ID 的取证方式

- 官方 Harness 持久化日志实报：`zstd -dc <DSH_HOME>/sessions/<wsKey>/<sessionId>/session.jsonl.zstd | grep -o '"model":"[^"]*"'`
- 当前实证（Canary #2 session bf3c06d6）：`deepseek-v4-flash`（42 处，无别名）。
- Harness 版本精确 pin：`@deepseek-ai/dsh@0.1.2-rc.1`，`dsh --profile acp`。

## 3. 派发一个 Builder Task 的最少输入

| 输入 | 说明 |
|---|---|
| `workspace`（绝对路径） | 唯一身份键的一半；必须已存在（supervisor/bridge 以其为 cwd） |
| `role` | `builder`（固定） |
| 任务正文 | `--text`（短）或 `--task-file`（长，走 §4/§5） |
| 审批模式 | `file`（决策文件，默认）/ `orca-ask` / 测试用 allow-all/reject-all |

不需要：Session ID、历史上下文、Prompt 拼装、终端操作。参考实现：`node tools/orca/dispatch.mjs --workspace <ABS_WS> --task-file <ABS_TASK> [--timeout-ms N]`。

## 4. 短 PTY envelope 正式 schema（唯一越 pty 的内容）

```json
{"cmd":"task_file","path":"/abs/task.md","sha256":"<64hex>","bytes":1234,"resume":"auto"}
```

- 原始单行 ≤ 900B（`ORCA_PTY_ENVELOPE_LIMIT` 可调；ORCA pty 实测上限 ~1001B，1201B 损坏、≥1501B 静默丢且管道坏死）。
- 超限 → `{"type":"task_file_rejected","reason":"envelope_too_large",...}` fail-fast，永不转发。
- `resume` 只接受 `"auto"`；其他值 → `task_file_rejected` (`unsupported_resume_policy`)。

## 5. task_file 读取与完整性校验（supervisor 内部，fail-closed）

1. `path` 必须绝对；不可读 → `task_file_error` (`task_file_unreadable`)。
2. 字节长度 ≠ `bytes` → `task_file_error` (`byte_length_mismatch`)。
3. sha256 ≠ `sha256` → `task_file_error` (`sha256_mismatch`)。
4. 通过 → `task_file_loaded`（含 bytes/sha256），经 supervisor↔bridge 内部 pipe（无 pty 限制）转发 `{"cmd":"prompt","text":<正文>}`。
5. 保证：不截断、不静默丢弃——每条失败路径都有 machine-readable 事件。契约证据：`runtime/evidence/TASK_FILE_CONTRACT_results.json`（TF-1…TF-7，7/7 PASS）。

## 6. 新建 Session 规则

- 身份键 = `(canonical workspace, role)`；bridge 持久映射无此键时才创建新 session（supervisor 代为声明 `allowNew:true`）。
- 无主孤儿 session 认领 fail-closed（bridge 内 identity check 拒绝不匹配认领）。
- 显式 `{"cmd":"new"}` 仅在映射不存在时成功；禁止为"重置"而新建。

## 7. Resume 原 Session 规则

- 对同一 `(workspace, role)` 的任何后续 prompt（含 task_file）自动 resume 同一 DeepSeek Harness session；bridge 进程重启后同样成立（持久映射 + fail-closed `session/list` 确认）。
- 返工 = 同链追加 feedback delta（新 prompt），不重发整套治理上下文。
- Task Manager 永不查看/搬运 Session ID，不手动 resume。

## 8. Reviewer / QA feedback 回传原 Session

```json
{"cmd":"task_file","path":"/abs/qa-findings-round2.md","sha256":"...","bytes":N,"resume":"auto"}
```

或短反馈直接 `{"cmd":"prompt","text":"<delta>"}`。两者落到同一原 session。全程由 Task Manager 通过派工基础设施自动完成，用户不复制任何反馈。

## 9. Session ID / chain ID 保存方

- bridge 持久会话映射：`runtime/bridge-state/session-map.json`（原子写，含 repo/worktree 元数据）。
- 证据日志（`runtime/evidence/*.jsonl`）与官方 session log 记录实际 ID 供审计；治理角色不保存、不传递。

## 10. Permission event schema（基础设施事件，非 Builder 与用户对话）

```
Harness session/request_permission
→ bridge {"type":"permission_request","id":N,"toolCall":{...}}
→ supervisor {"type":"approval_routed","id","key","decisionFile","tool"}   # 决策面（V2.1: ORCA/Task Manager approval surface）
→ 人工/编排者写 {"decision":"allow"|"reject"} 到 decisionFile
→ supervisor {"type":"approval_decision","id","decision"}
→ bridge {"cmd":"permission",...} → Harness 继续
```

- fail-closed：`BRIDGE_PERMISSION_TIMEOUT_MS`（默认 300s）超时未决即拒绝；迟到决策记 `approval_late` 丢弃。
- 无静默放行；文件系统是事实源（`.ask.json` / `.decision.json`）。

## 11. Cancel / timeout

- `{"cmd":"cancel"}` → turn 取消 → `{"type":"status","state":"CANCELLED"}`，其后文件操作冻结，session 可复用。
- 卡死 worker：`BRIDGE_TURN_IDLE_MS`（默认 600s）空闲看门狗自动 cancel。

## 12. Crash / restart / resume

- ACP server 崩溃：bridge 内自动 respawn + re-init + auto-resume 同 session。
- bridge 进程死亡：supervisor 有界 respawn（见 §13/§14）；下一个 prompt 自动续链。
- 会话映射持久，任何一层重启都不换 session。

## 13. Single-writer

- 一个 `(workspace#role)` 同一时刻只允许一个 bridge；锁冲突退出被分类为 `lock_conflict`。
- 陈旧锁仅按 pid 存活检查窃取；孤儿清理后自动恢复（§14）。
- 确定性证据：`runtime/evidence/SUPERVISOR_RESILIENCE_results.json`（RS-1…RS-5，6/6 PASS）。

## 14. 状态与事件（machine-readable）

- bridge 状态机：`READY | RUNNING | COMPLETED | BLOCKED | FAILED | CANCELLED`。
- supervisor 事件：`bridge_started / bridge_respawned / bridge_exit / bridge_exited_clean / respawn_scheduled / DEGRADED / BLOCKED / RECOVERED`。
- respawn 语义：指数退避 500ms×2^(n-1) 封顶 30s；连续失败 ≥8 进入 `BLOCKED`（`DEGRADED` 同拍发出），仅按 30s 慢速重试，锁解除/恢复健康（ready 或稳定 60s）后 `RECOVERED`。全部 env 可调（`ORCA_SUPERVISOR_*`）。

## 15. Telemetry 真实字段（只读官方 `session.jsonl.zstd`）

`node tools/telemetry.mjs [--session <id>] [--out <file>]`：
`inputTokens_uncached / cacheReadTokens / outputTokens / reasoningTokens / totalTokens / cacheHitRate / eventsSeen / sessionId / workspaceKey`。

## 16. 统计来源与计数语义

- 全部来自官方 Harness 持久化事件（非推算）；`cost_cny` 无可靠官方定价 → `null`，不估算。
- `approval/asked` = Harness 发出的 permission 请求数（每请求唯一 id）；`approval/decided` = 被解决数（决策或 fail-closed 超时）。1 次人工审批 round 合法对应 asked=2/decided=2（首请求 300s 超时被拒 + 重试请求被批），非重复计数（Canary #2 id `20ea1b09…`/`67574c75…` 取证）。
- 账本 `model` 字段写 `deepseek-flash`（A通道实际精确 ID；旧 `deepseek-bridge/deepseek-v4-flash` 为兼容 alias，不写虚构别名）；`rework` 按 V2.1 定义 = supervisor 打回次数，QA round 数不计入。

## 17. 能力边界

Bridge 拥有：Builder task 自动派发、workspace/worktree 映射、session 创建/resume、feedback 回原 session、permission transport、cancel、crash/recovery、single-writer、telemetry、transport（PTY envelope + 内部 pipe）、machine-readable status。

Bridge **不拥有**：Planner、Code Reviewer、QA、Product Reviewer、V2.1 Supervisor、Task Manager、senior-expert 升级决策、HANDOFF 最终裁决、TASK-MODEL-LOG 最终判定、Agent Loop/Tools/Skills/Context/Compaction/Cache（全部留在官方 Harness）。

## 18. ORCA V2.1 最小接入所需信息（汇总）

1. override 表 builder 行 A 通道写法：模型列 `deepseek-flash`＋Runtime 列 `deepseek-bridge` 即选择本通道（用户决定权；旧 `deepseek-bridge/deepseek-v4-flash` 为兼容 alias）。
2. 派工 = `dispatch.mjs`（或等价 supervisor 协议客户端）+ §3 四项输入；长任务用 §4 envelope + 任务文件。
3. 权限审批面 = §10 decisionFile（或 `orca-ask`）；审批是基础设施事件。
4. 升级规则由 V2.1 治理拥有：supervisor 累计打回 2 次 / P0-hard / 用户切通道 → 停 DeepSeek 链、开新链（新 workspace/worktree 或新模型），不为保 session/cache 违反升级规则。
5. Prompt 构造：新 session 首轮按 静态（AGENTS→builder 角色契约→稳定执行约束→HANDOFF 本 Task 状态）→动态（当前 Task）顺序；同链返工只追加 delta。
6. 审计与账本：§15 telemetry + §16 语义；证据在 `runtime/evidence/`（gitignored，不删）。
