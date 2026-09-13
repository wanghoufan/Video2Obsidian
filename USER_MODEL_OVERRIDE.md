# USER_MODEL_OVERRIDE｜本项目镜像（2026-09-13，用户指令同步真源）

> 真源（唯一可改处）：`/Users/zzymima0000/Developer/coding/4.Templates（PC）/2026-09-09 丨 MAC 丨 ORCA V2.1 治理模板 丨 分发版-2026-09-11/USER_MODEL_OVERRIDE.md`
> 本文件为只读镜像，改表请改真源后重新同步；编排者每次派工前仍读真源。
> 历史备查：2026-09-11 本文件曾作废（声明真源唯一）；同日 18:10 工作区被写回旧 2.1 表后恢复作废声明；2026-09-13 用户指令按真源重建镜像表；同日按新版真源第二次同步（builder切Luna、reviewer/qa等换位）。

| 角色 | 主用模型（精确ID，禁别名） | 备用模型（精确ID，同角色；无=停派找人） | 执行通道/Runtime | 备注 |
|---|---|---|---|---|
| task-manager | 用户临时指派/开窗口时定（不定模型） | deepseek-v4.1-flash | 本窗口 subagent（备切codebuddy） | 每项目常驻编排者；主用由用户临时指派或开窗口时定；备用为同表可选切备，切备记账；无可用通道停派找人 |
| supervisor | deepseek-v4.1-flash | 无（不自动转备份） | codebuddy | 监督复检；额度受限停工即找用户，用户切账号后通知继续，不自动转备份 |
| builder | codex/gpt-5.6-luna | 无（无自动备用） | codex | 普通开发主力；超限停派找人 |
| planner | codex/gpt-5.6-sol | 无（无自动降级） | codex | 第一阶段产品Planner；超限停派找人 |
| code-reviewer | opencode/muse-spark-1.3-contributor-free | 无（无自动备用） | 本窗口 subagent | 独立Review Session；超限停派找人 |
| qa | codex/gpt-5.6-luna | 无（无自动备用） | codex | 测试/回归/DoD；超限停派找人 |
| product-reviewer | codex/gpt-5.6-luna | 无（无自动备用） | codex | Phase1按需Research Review，不常驻；超限停派找人 |
| experience-recorder | opencode/muse-spark-1.3-contributor-free | 无（无自动备用） | 本窗口 subagent | 收尾低频；超限停派找人 |
| neat-freak | opencode/muse-spark-1.3-contributor-free | 无（无自动备用） | 本窗口 subagent | 收尾低频；超限停派找人 |
| senior-expert | codex/gpt-5.6-sol | 无（无自动备用） | codex | 只接升级任务，平时不派；超限停派找人 |

规则（2026-09-12整改版，与真源一致）：
- 精确ID：Sol必须写全 `codex/gpt-5.6-sol`，Luna必须写全 `codex/gpt-5.6-luna`，禁裸别名；V4.1必须写全 `deepseek-v4.1-flash`；FREE必须写全 `opencode/muse-spark-1.3-contributor-free`；codex实调用剥 `codex/` 前缀用短名，表内仍记全ID为ORCA路由ID；不编rank分数。task-manager 主用不定模型（用户临时指派/开窗口时定），表内不写死。
- OPENCODE_GO = MANUAL_ONLY：GO不得作为任何角色主用/备用；一切受限只按表切同角色备用或停派找人，禁自动进GO；只有用户明确说“这次可用GO”才允许单次启用，不写表、不留自动条件。
- V4.1统一（通道保留非删）：CodeBuddy 路由只许 `deepseek-v4.1-flash`；该通道保留可用，现达额度限额暂由主表 Luna/FREE 顶替，用户指定角色后改表启用；档位high只写派工口头，不进模型列。
- Bridge standby：历史Contract（包根 `BRIDGE_INTEGRATION_CONTRACT.md`，只读核对，不改）内已验证 `deepseek-flash` 降为standby历史路由，仅用户明确切回时启用，不进主动表、不作新默认。
- B通道-y：codebuddy非交互派单默认带`-y`；无-y时Bash审批被拒且rc仍为0，自测验成功只看正文回显不看rc；派工显式必须标注`-y`已带，漏标打回。
- 派工显式：编排者每派必先贴一行“正在调用 XX｜主用精确ID＋Runtime／备用精确ID＋Runtime”，收工必贴“XX回来了 PASS/FAIL＋实际走主还是备”，HANDOFF执行链＋账本记同一行。
- 超限口径：主备均不可用即停派找用户，不静默扣费；换模型/换Runtime用户定，换通道开新链记HANDOFF＋账本；槽位不经改表不得擅自顶替。
- 现状（2026-09-13用户述）：deepseek-v4.1-flash额度曾受限（13:00前恢复）；真源已切 Luna/FREE 顶替，codebuddy 通道保留；本窗口subagent可用。
