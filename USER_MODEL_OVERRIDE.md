# USER_MODEL_OVERRIDE｜2.1 一句话切模型（优先于 registry 兜底）

> 你改这张表就生效，不用走 promotion/sync/run-all。编排者每次派工前读一次。
> 窗口说一句也一样：“Builder临时用Terra-medium到明天”，编排者按同格式记一行。

| 角色 | 模型（精确ID，禁别名/前缀） | 执行通道/Runtime（可选，空=本窗口 subagent 原行为；有值由派工基础设施自动调用，TM 不手动开终端） | 到期（无固定到期填「无」；临时换模型填日期如 2026-09-10） | 备注 |
|---|---|---|---|---|
| task-manager | opencode-go/muse-spark-1.3-contributor | —（默认本窗口 subagent） | 无 | 编排者+监督者共用，只走GO |
| supervisor | opencode-go/muse-spark-1.3-contributor | —（默认本窗口 subagent） | 无 | 同编排者，不独立选型 |
| builder | opencode-go/muse-spark-1.3-contributor | —（默认本窗口 subagent） | 无 | 用户指定切GO池Muse Spark 1.3 Contributor |
| planner | codex/gpt-5.6-sol | —（默认本窗口 subagent） | 无 | 拆活 |
| code-reviewer | opencode-go/glm-5.3-flash | —（默认本窗口 subagent） | 无 | 复核 |
| qa | opencode-go/glm-5.3-flash | —（默认本窗口 subagent） | 无 | free限额切GO（原mimo-v2.5-free） |
| product-reviewer | codex/gpt-5.6-luna | —（默认本窗口 subagent） | 无 | 用户指定切Luna |
| experience-recorder | opencode-go/glm-5.3-flash | —（默认本窗口 subagent） | 无 | free限额切GO（原mimo-v2.5-free） |
| neat-freak | opencode-go/muse-spark-1.3-contributor | —（默认本窗口 subagent） | 无 | free限额切GO，跟builder同模型 |
| senior-expert | codex/gpt-5.6-sol | —（默认本窗口 subagent） | 无 | 只接升级任务，平时不派 |

规则（2.1仅保留）：
- 精确ID：`gpt-5.6`别名指Sol，禁用；必须写全 `codex/gpt-5.6-terra`。
- 池子：各行按表走，不串池（builder FREE+GPT_PRO；TM 只走 OPENCODE_GO）；换池须改表。
- 档位（如 medium）写在派工口头指令里，模型列只写精确 ID。
- 到期你定；不静默扣费（超限停）。
- 分工：sol 偏拆活/兜底升级，terra 为主力执行（用户口径为准，不编 rank 分数）。池映射：FREE=opencode-free/，GPT_PRO=codex/，GO=opencode-go/；超限停=编排者停派找人。
- DeepSeek Official Bridge 通道（待 Contract 核对，非已验证值）：如需启用，在 builder 行「执行通道/Runtime」列填 channel ID（待接入）、模型列填 Contract/真实运行为准的精确 ID（待接入）；无 `V2.1_BRIDGE_INTEGRATION_CONTRACT.md` 时一律填「待接入」，不得编造 `deepseek-official/xxx`、`deepseek-bridge/xxx` 或任何看似合理的模型 ID；仅当用户改表或明确口头指定时启用，编排者不自行切换、不新建 Registry。模板既有 `deepseek-bridge/deepseek-v4-flash` 字样仅为待核对占位，不当真实值消费。
