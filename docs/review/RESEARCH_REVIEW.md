# RESEARCH_REVIEW（Phase1）

- Plan Version（评的是哪版 PRODUCT_PLAN）：`PRODUCT_PLAN_V1.0`
- Review Round（第几轮）：第 1 轮 Research Review
- Result：（FAIL＋一句话结论）：FAIL；方向基本正确，但真实 16 条分类证据、恢复契约、性能边界和 4 个交互语义仍未闭合，不应进 `WAITING_HUMAN_APPROVAL`。
- P0 / P1 / P2：
  - P0：3 个（P0-1 诊断、P0-2 差异化恢复、P0-3 控制台信息架构/状态重构）
  - P1：5 个（P1-1～P1-5，其中 P1-1、P1-2 为 blocking）
  - P2：4 个（P2-1～P2-4）

## Key Assumptions（逐条列＋是否成立）

1. **16 个失败可以稳定归类：部分成立，尚未证实。** 八类作为初始 taxonomy 合理，但计划没有展示 16 条逐条的 `code/state/stage/manifest/receipt/verdict/产物` 证据矩阵，也没有证明同一人话错误不会对应多个根因。Apple 官方明确列出沙盒、POSIX/ACL、SIP、数据保护等不同访问阻断来源，说明“读不到/写不进”不能只按表面错误文案归类。[Apple Developer，官方文档](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?changes=_4)  
   **要求：** 先只读生成 16 行证据矩阵；有冲突证据或缺字段即 `UNKNOWN`，并记录分类置信依据。
2. **现有单条 retry/reapply/publish 是安全原语：未验证。** 计划假设可复用，但没有逐入口列出前置条件、写入边界、是否重启 worker、是否改变任务状态、是否满足 No-Clobber。不能从“代码已有入口”推出“批量编排可安全复用”。
3. **用户优先处理 16 个失败高于清 P3：成立。** 这是 HD-1=A 的已拍板约束，不再作为未决项；但应明确“支撑主线的 P3”必须有纳入理由，避免 P1-5 变成隐性 backlog 清理。
4. **用户接受 dry-run + 确认：合理但未验证。** 对破坏性/耗时动作是成熟模式；但还需真实 UI 走查确认预览信息是否足够让用户判断，而不是只验证 API 返回字段。
5. **成功 61 项默认隔离：成立且必须保持。** 这是 HD-1/HD-5 安全边界的直接推论；但计划需要用恶意传入成功 `run_id` 的接口测试证明后端拒绝，而非只测正常 UI。
6. **“当前/异常优先，已完成历史收起”符合用户反馈，但 N=20 未证实。** 任务/下载类产品常把 active 与 completed 分开：Docker Builds 将 Active builds 与已完成 Build history 分栏，aria2 也有 `active/waiting/paused/error/complete/removed` 状态；这些证明分层方向，不证明 20 是最佳阈值。[Docker Docs，官方文档](https://docs.docker.com/desktop/use-desktop/builds/)、[aria2，官方 GitHub 文档](https://github.com/aria2/aria2/blob/master/doc/manual-src/en/aria2c.rst)
7. **监听态与任务态分离：产品上正确，但“状态永久独立”仍需定义边界。** GitHub Actions 同时区分运行 `status` 与 `conclusion`，并允许 queued/in_progress/completed 等枚举；反例是下载器需要把 paused/retry/error 作为可行动状态，不能把所有运行信息都降为系统状态。[GitHub Docs，官方文档](https://docs.github.com/en/rest/actions/workflow-runs)、[Android DownloadManager，官方文档](https://developer.android.com/reference/android/app/DownloadManager)
8. **“P0-3 必须升 P0”：部分成立，范围过宽。** 状态口径、失败可达性、统一恢复入口直接影响 16 条主线，应为 P0；但顶部流程条的 64px、sticky、清空列表和视觉栅格属于不同风险，全部绑成一个 P0 会让核心恢复被视觉决策阻塞。建议拆成 `P0-3a 状态/操作可用性` 与 `P1-UI 信息架构`，或至少把视觉尺寸作为可调整 DoD，不把“好看/占地”当发布阻断。
9. **“先诊断再差异化恢复”有产品价值：成立；“大多数可恢复”未证实。** 本地转写工具确有多阶段失败的现实需要，但本计划没有真实 16 条的阶段分布、可复用 Raw/Norm 数量和会调用 Whisper 数量。

## Verified Facts（已验证事实＋证据）

- Apple 官方将 macOS 文件访问失败拆为 App Sandbox、用户未授权、POSIX/ACL 的 `EACCES`、SIP/数据保护的 `EPERM` 等不同来源；外置/可移动卷、网络卷、Desktop/Documents/Downloads 等也受隐私控制影响。[官方文档](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?changes=_4)、[Apple Support，官方支持](https://support.apple.com/en-ie/guide/security/secddd1d86a6/web)
- App Sandbox 的用户选择文件权限可以是只读或读写；跨次运行需要 security-scoped bookmark，并且访问时要正确 start/stop。计划的“路径/权限/环境”诊断应至少保留这些可区分证据，而不是只输出“权限失败”。[Apple Developer，官方文档](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?language=objc)
- MLX Whisper 官方示例提供 benchmark 脚本，明确分开 feature、model forward、decode、端到端时间；官方 README 也说明模型可从 tiny 到 large-v3、首次运行可能下载模型。[Apple MLX Examples，官方 GitHub](https://github.com/ml-explore/mlx-examples/blob/main/whisper/benchmark.py)、[Apple MLX Examples README，官方 GitHub](https://github.com/ml-explore/mlx-examples/blob/main/whisper/README.md)
- 高质量第三方 benchmark 在 M2 8GB 的单一场景报告 small 约 23.6× realtime、turbo 约 12.4×，并指出批处理未必更快；官方/社区 issue 还记录了某些 `clip_timestamps` 参数导致短音频耗时显著异常。它们只能给量级，不能替代本机实测。[第三方 benchmark](https://github.com/ilyasmukiev/mlx-whisper-fast)、[官方 GitHub issue](https://github.com/ml-explore/mlx-examples/issues/1285)
- 任务历史的成熟做法不是一律铺平：Docker 把活动构建与完成历史分开，历史可查看统计并管理；GitHub Actions 先看运行历史，再下钻到 job/step；aria2 明确提供 active/waiting/stopped 分组及错误码。[Docker 官方文档](https://docs.docker.com/desktop/use-desktop/builds/)、[GitHub 官方文档](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/viewing-workflow-run-history)、[aria2 官方 GitHub 文档](https://github.com/aria2/aria2/blob/master/doc/manual-src/en/aria2c.rst)
- No-Clobber/成功记录保护已有成熟先例：yt-dlp 提供 `--no-overwrites`，并用 download archive 记录成功项、后续跳过已下载项；这支持本项目“成功项隔离 + 不覆盖”，但不证明本项目的 Markdown 用户编辑判定已完整实现。[yt-dlp，官方 GitHub](https://github.com/yt-dlp/yt-dlp/blob/master/README.md?plain=1)、[yt-dlp FAQ，官方 GitHub](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)

## External Sources（来源类型与链接）

1. 官方文档：Apple 文件夹权限与隐私控制——https://support.apple.com/en-ie/guide/security/secddd1d86a6/web
2. 官方文档：Apple App Sandbox 失败根因——https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?changes=_4
3. 官方文档：Apple security-scoped 文件选择——https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?language=objc
4. 官方 GitHub：Apple MLX Whisper benchmark——https://github.com/ml-explore/mlx-examples/blob/main/whisper/benchmark.py
5. 官方 GitHub：Apple MLX Whisper README——https://github.com/ml-explore/mlx-examples/blob/main/whisper/README.md
6. 第三方 GitHub benchmark：mlx-whisper-fast——https://github.com/ilyasmukiev/mlx-whisper-fast
7. 官方 GitHub issue：mlx-whisper 长短音频耗时异常——https://github.com/ml-explore/mlx-examples/issues/1285
8. 官方文档：Docker Builds 活动/历史——https://docs.docker.com/desktop/use-desktop/builds/
9. 官方文档：GitHub Actions 历史与详情——https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/viewing-workflow-run-history
10. 官方 GitHub 文档：aria2 状态、队列与错误——https://github.com/aria2/aria2/blob/master/doc/manual-src/en/aria2c.rst
11. 官方 GitHub：yt-dlp No-Clobber——https://github.com/yt-dlp/yt-dlp/blob/master/README.md?plain=1
12. 官方 GitHub：yt-dlp 成功归档——https://github.com/yt-dlp/yt-dlp/wiki/FAQ
13. 官方文档：Android DownloadManager 状态/重试反例——https://developer.android.com/reference/android/app/DownloadManager

## Competitor Findings（竞品现状＋对本 Plan 的启示）

| 主要主张 | 支持证据 | 反对证据/限制 | 成功但做法相反的案例 | 对 Plan 的结论 |
|---|---|---|---|---|
| 当前/失败/历史应分层 | Docker Active/History；GitHub Actions 历史→详情；aria2 active/waiting/stopped | 这些工具的对象、数量和用户目标不同，不能直接推出本项目的默认 N | Android DownloadManager 保留 pending/running/paused/failed/successful 等完整状态，不把状态全部折叠 | 采纳分层；不采纳“竞品因此证明 N=20” |
| 失败要有状态和可行动原因 | aria2 有 error 状态和错误码；Android 有 waiting-to-retry 与 failed | 错误码仍可能只说明表象；macOS 访问失败的根因层次很多 | yt-dlp 以 archive/No-overwrite 直接跳过已成功项，未要求用户先做复杂诊断 | 诊断必须显示证据、置信度、动作边界；未知 fail-closed |
| 已完成应可回看但不占当前工作面 | Docker 有完成历史；GitHub 默认近期历史并可下钻 | 未验证这些产品的默认 20/30 阈值，也未验证折叠对本项目用户的可用性 | aria2 的 stopped 查询支持 offset/num，按页取历史而非“最近固定 20 + 折叠” | N 应为可配置/可验证参数；API 分页比只做前端隐藏更重要 |
| No-Clobber 是合理安全策略 | yt-dlp `--no-overwrites`、download archive；本计划已有 D-7/D-8 | 下载成功归档不等于“用户编辑 Markdown”判定；写入前原子性/并发仍未证 | MLX 官方转换脚本明确会覆盖目标模型目录，说明成熟工具也会在明确命名的生成物上允许覆盖 | No-Clobber 仅限已发布/用户编辑产物，需把范围和例外写成契约，不能泛化为所有中间产物 |
| 本地 MLX 速度足以支持重试 | 第三方 M2 8GB 报告显示部分模型明显快于实时 | 设备、模型、音频内容、JIT/下载、参数会改变结果；官方 issue 证明存在非线性异常 | 某些社区/第三方实现用 CoreML 或其他引擎更快，但本计划明确不换引擎 | 保留 P1-1 blocking；dry-run 只显示 whisper 调用数和“未测耗时”，不显示伪 ETA |

## Counter-evidence（反对证据＋成功的相反做法）

- **反对“八类足够”**：Apple 官方列出多个独立访问控制层；外置盘、网络卷、iCloud/受保护目录、POSIX/ACL、SIP、文件锁/占用、文件损坏和编解码失败可能在同一用户文案下重叠。成功的相反做法是 aria2 公开细粒度错误码与 active/waiting/stopped 查询，而不是仅用一个“失败”类别；本项目至少要保留原始错误码、阶段和证据来源。
- **反对“P0-3 整体不可降级”**：用户反馈确实证明布局痛点，但没有证明顶部流程条比失败恢复安全契约更紧急。成功的相反做法是 GitHub Actions 先提供可用的运行列表/详情，再通过下钻解决复杂信息，而不是先重做全局布局。建议拆分发布阻断项。
- **反对“最近 20 条天然合理”**：aria2 支持 offset/num 分页，Docker 的历史是独立视图；两者都没有给出 20 的普适依据。相反成功做法是“用户选择/分页/按需加载”，因此 HD-6 只能决定首版默认值，不能把 20 固化成产品真理。
- **反对“状态永久独立”过度简化**：Android DownloadManager 的 paused/waiting-to-retry 是任务状态，因为它决定下一步是否自动继续；若本项目把 worker 阶段完全剥离，用户可能看不出 BLOCKED 与可自动重试的区别。应定义持久生命周期状态、当前阶段、恢复资格三层显示契约。
- **反对“复用旧入口无需重写”**：现有入口可能带有旧的参数默认值、目录透传和状态副作用。成功的相反做法是 yt-dlp 将 no-overwrite/archive 作为明确、独立的命令语义；本项目也要给每个恢复策略列前置、读写集合、状态转移和失败回滚。
- **反对“真实性能只需一条短视频+一条长视频”足够**：第三方数据跨 M2/不同模型，官方 benchmark 还拆分加载、解码、端到端；单样本不能覆盖中文课程、静音比例、模型缓存和并发。P1-1 至少应固定模型、音频时长/语言、冷/热缓存和顺序执行。

## Unverified Items（未验证项＋验证方法）

1. 16 条真实失败的实际类别、阶段、错误码和证据完备度——只读读取当前 `state.db/manifest/receipt/verdict`，生成脱敏 16 行矩阵；不执行恢复。
2. 真实 16 条中 Raw/Norm/Render 可复用的数量——只读检查产物存在性、哈希/版本与发布记录，输出可复用/不可复用/冲突。
3. 现有 retry/reapply/publish 对每类的真实副作用——在系统 tmp 合成夹具中逐入口记录 DB、manifest、产物、笔记写次数和状态迁移；真实目录仍只读。
4. 诊断是否真正零写、零 Whisper——文件系统写计数/审计日志 + 调用桩；不得只看 UI。
5. dry-run 与 execute 的 token、状态指纹、跨 `data_root` 和两标签页并发——两线程/两浏览器请求测试，验证恰一个 202、其余 409/明确冲突。
6. No-Clobber 对既有、用户编辑、缺失 vault、同名不同内容的边界——构造 QA Markdown，执行后逐字节 hash、覆盖写次数和 vault 创建次数为零。
7. 实际 MLX Whisper 冷启动/热启动、短/长视频、中文课程和内存峰值——仅把少量代表视频复制到外置系统 tmp；记录设备、模型、版本、音频时长、总耗时、峰值内存、阶段停留。
8. 1440×900 和 960px 以下布局、DOM/Tab 顺序、首屏操作可达性——不请求线上 8765；用合成数据和离线浏览器/DOM 测试，截图与可访问性树分别留证。
9. 最近 20/30 对真实用户完成项可发现性和首屏高度——原型 A/B 或至少用 77 条夹具测量首屏可见行数、定位失败和展开历史所需操作数。
10. “清空已完成列表”是否应只做视图归档、是否跨刷新持久化——先由 HD-7 决策，再在 tmp 中验证刷新、恢复、产物 hash 和 DB 业务记录不变。
11. 监听开/关/停止收尾时 `ACTIVE`、`BLOCKED`、`SKIPPED` 的显示契约——先由 HD-8 决策，再用同一持久快照渲染三态，对比状态、颜色、计数和当前阶段。
12. P1-1 的 61 篇量级“Whisper 0”重跑是否真的不触发模型——执行前后调用计数、模型日志和文件 hash 三重证据；当前不得把计划文字当成通过。

## Required Fixes（Planner 必须改项，打回依据）

1. 在 `FR-2/FR-4` 增加“分类证据优先级、冲突证据、置信度、UNKNOWN 触发条件”；补一张 16 条真实失败只读证据矩阵的交付物和验收字段。
2. 将 `P0-1` 的成功标准从“八类至少各一个合成用例”改为“真实 16 条逐条可追溯；合成用例覆盖规则分支”；不能用合成覆盖替代真实分布。
3. 给每个恢复策略补充前置条件、允许读写的文件/DB 集合、状态迁移、失败回滚/重复提交语义；在 `FR-4/D-5` 明确旧入口复用的证据门槛。
4. 把 `P0-3` 拆成核心可用性与视觉布局两个可独立验收的条目；至少将流程条 64px、sticky、栅格尺寸改为可验证但可调整的设计约束，避免视觉争议阻塞诊断恢复。
5. 在 `FR-12/D-15` 把 N=20 写成首版默认参数而非固定产品规则；定义分页/按需加载 API、排序键、并列时间戳、删除/归档后计数和刷新一致性。
6. 在 `FR-13/D-16` 明确三层契约：持久生命周期、当前 worker 阶段、恢复资格；列出监听开关不会改变什么、worker 会改变什么。
7. 在 `FR-5/FR-6/D-6/D-9` 固化快照一致性：诊断快照版本、任务状态指纹、plan token 的生成/过期/重算、部分成功、服务重启和 job 记录的真源。
8. 在 `FR-7/D-7/D-8/D-17` 明确 No-Clobber 范围：源视频、Raw/Norm/Render、已发布 Markdown、用户编辑 Markdown、DB 记录分别是什么保护级别；补充“原子写失败/并发写”的验收。
9. 在 `D-10/P1-1` 补齐可复现实验协议：硬件、macOS、Python/MLX/模型版本、语言、音频时长、冷/热缓存、并发、峰值内存和结果格式；禁止将第三方 benchmark 数字当本机 ETA。
10. 在 `D-12/D-14` 增加真实路径脱敏和错误信息安全验收：UI 可看但复制摘要不含真实绝对路径、原始正文、密钥；外置 tmp 复制行为须有来源/目标/清理证明。
11. 在 `P1-3/P1-5/P3 处置表` 标出每项与 16 条失败主线的直接关系、工作量和若不做的影响；清除“低成本”但没有证据的措辞。
12. 更新 `Human Decisions Needed`：HD-1～HD-5 标为已决，不再占 readiness 缺口；保留 HD-6～HD-9，并补充是否跨刷新持久化、清空后历史是否默认可恢复、状态三层显示和流程条可隐藏/可访问性要求。

## Plan Readiness Score（分项打分＋合计，口径以 PRODUCT_PLAN.template.md 为准）

- 产品目标与用户需求（20）：**18/20**。真实反馈和 HD-1～HD-5 已锁定主线；16 条实际失败结构未呈证据。
- 核心方案完整性（20）：**14/20**。诊断、dry-run、恢复、结果汇总链条齐全；状态三层、旧入口副作用、服务重启和归档语义不足。
- 外部事实与竞品验证（20）：**16/20**。本轮补足 13 条来源，覆盖任务历史、文件权限、性能和 No-Clobber；仍不能从公开资料推出本项目阈值或失败恢复成功率。
- 技术可行性（15）：**10/15**。复用现有入口有希望，但没有真实 16 条证据矩阵和恢复副作用证明。
- 风险与异常场景（10）：**8/10**。已覆盖未知、状态漂移、并发、No-Clobber、长视频；缺 iCloud/外置盘/文件锁/原子写失败等显式验收。
- 开发范围与 DoD（10）：**7/10**。DoD 数量多且可测方向正确，但部分是视觉愿望或合成测试，未把真实证据和 API 契约写实。
- 未决问题（5）：**3/5**。HD-1～HD-5 已决；HD-6～HD-9 仍会改变数据/交互语义，且 HD-7/HD-8 的问题定义需要补充持久化和三层状态边界。
- **合计：76/100**。
- **Gate 判断：未达到。** 低于 90；且 P0 尚未清零，blocking P1 尚未清零，真实分类/性能/恢复副作用关键事实未验证，不进 `WAITING_HUMAN_APPROVAL`。

## Human-only Decisions（只需人类拍板项）

- **HD-1～HD-5：已拍板，不再提问，也不扣“未决”分。** 评审只检查它们是否被计划正确落地：当前计划大体已落地，但 HD-2 的“复制摘要脱敏”还需把绝对路径、原始正文和错误详情边界写成 DoD。
- **HD-6：问题问对了，但建议选项改为“首版默认 20/30，是否允许用户改变/是否持久化”。** 建议首版默认 20、历史收起；不要把 20 当成永久阈值。
- **HD-7：问题问对了，但必须明确“归档/隐藏是否写入本地视图状态、是否跨刷新/重启、历史如何恢复”。** 在这些语义明确前，不应实现“清空”。
- **HD-8：问题问对了但不够完整。** 人类只需决定用户看到的三层口径；建议选 A，并要求计划明确“任务生命周期/worker 当前阶段/恢复资格”三者如何同时呈现。
- **HD-9：问题问对了，但应同时问可访问性和小屏行为。** 建议普通顶部条作为首版默认；sticky/可收起可留作后续，但流程条不能遮挡焦点、不能制造横向溢出。
- **额外需要人拍板的项：无。** HD-1～HD-5 已覆盖范围、隐私、自动恢复边界和验证样本；其余缺口是 Planner 应补的事实/契约，不应包装成新的 HD。

## Next Action（回 Planner 修订 / 进 WAITING_HUMAN_APPROVAL 找人）

**回 Planner 修订。** 修完 Required Fixes 1～10 后，先做只读 16 条证据矩阵和外置 tmp 性能/恢复验证协议，再由 Research Reviewer 复审；HD-6～HD-9 可在修订稿中带建议选项交用户一次性拍板。当前不得进 `WAITING_HUMAN_APPROVAL`。

# 第 2 轮复审（PRODUCT_PLAN_V1.2）

- Plan Version（评的是哪版 PRODUCT_PLAN）：`PRODUCT_PLAN_V1.2`
- Review Round（第几轮）：第 2 轮 Research Review
- Result：（PASS / FAIL＋一句话结论）：**FAIL**；V1.2 已认真落地大部分上一轮修订，但真实证据只证明“原登记路径缺失”，尚未证明“不可恢复/唯一根因”，且 16 行矩阵没有逐行填满 FR-1 要求的全部证据字段。
- P0 / P1 / P2：
  - P0：3 个，均仍未实现/验收清零：P0-1 缺源校正与诊断、P0-2 差异化恢复、P0-3 核心状态/恢复入口/可退出反馈。
  - P1：7 个，其中 P1-1、P1-2 为 blocking；P1-6 视觉布局与历史管理、P1-7 改名为 non-blocking。
  - P2：4 个。

## Key Assumptions（逐条列＋是否成立）

1. **“16 条当前原路径不存在”——成立，高置信。** 只读查询 `data/state.db` 的 `sources.current_path` 与 `processing_runs` 得到 24 个“葫芦军师” run；文件系统当前仅有 8 个该目录视频，16 个登记路径 `is_file=false`；这 16 个 run 均无 `raw_artifact_id`，且对应 `data/jobs/<run_id>/manifest.json` 不存在。该结论可采信。
2. **“16 条都是 SOURCE_MISSING”——部分成立，需收窄措辞。** 它支持“SOURCE_NOT_AT_RECORDED_PATH/当前登记路径缺失”；但未检查外置盘、iCloud/网络卷、同 basename 的其他位置、内容哈希匹配或路径迁移表，因此不能推出文件已删除、不可恢复，或不存在可重新指定的替代路径。计划仍在 Product Goal、Problem、FR-4 和 P0-1 使用了“不可修复/无法自动恢复”的强表述。自动恢复为 0 可以成立，但应定义为“按当前证据不允许自动恢复”。
3. **“页面失败不是 DB 中已记录的转写失败”——部分成立。** DB 中 24 条 `run.status` 均为 `QUEUED`，16 条没有 Raw/Norm/Render/Publish 引用；这证明 DB 没有记录终态 Whisper 失败。它不能证明页面错误是某个确定的“运行时缺源映射”，因为页面导出、DB 快照和文件扫描未共享可核对的生成时间/diagnosis id，且 DB 状态本身可能是旧状态、恢复失败后的残留或映射 bug。应改为“页面显示与持久 DB 状态不一致；缺源是当前最强解释，运行时映射原因待验证”。
4. **“7 类行动分类优于原 8 类”——方向成立，粒度仍需验证。** 以用户动作区分自动重试、人工处理和不适用，比按错误文案平铺更可用；但把权限、No-Clobber、发布阻断合并到 `PUBLISH_BLOCKED`，把瞬时异常并入 `RETRYABLE_TRANSCRIPTION`，可能丢失根因统计。应至少同时保留“行动类别”和“技术根因/发生阶段”两个维度，不能让行动类成为唯一事实分类。
5. **“SOURCE_MISSING 不计入失败”——对当前 UX 合理，但不是普适真理。** 当前 16 条没有源文件，给“放回/重新指定目录”比给“重试 Whisper”更诚实；但用户仍会把它视为未完成的失败任务，若从失败总览完全移除，可能降低召回率。成熟下载器 qBittorrent 将“missing files”保留为红色错误状态并提供 recheck/resume，说明“独立显示”比“从失败完全消失”更稳妥。[官方 GitHub Wiki](https://github.com/qbittorrent/qBittorrent/wiki/Status-of-Missing-files-at-start-up-or-after-restart)。建议计划明确“双计数语义”：不计入可重试失败，但在未完成/受阻总览中可见。
6. **“P0-3 拆成 P0-3 与 P1-6 已解耦”——基本成立。** 计划已将核心状态/恢复入口/反馈与视觉布局/历史管理拆开，并写明视觉不阻塞 P0。剩余风险是 P0-3 的“首屏两次点击”和 P1-6 的“主操作不落历史之后”仍共享未验证的页面布局；需要把 P0-3 验收改为功能可达性，不依赖 64px、两列或视觉原型。
7. **“改名但保留 v2o 兼容标识”——成立且边界合理。** 面向用户的 title/h1/README 改名与内部 localStorage、日志、数据目录分离，符合迁移安全。反例风险是流程条文案、导出摘要、窗口标题、帮助文案可能残留 V2O；D-24 目前只列 title/h1/流程标识/README，需做全仓库用户可见字符串盘点，但不应改内部兼容字面。
8. **“查询面板必须可退出”——成立且 DoD 可测。** D-23 已给出短提示、关闭按钮、Esc、遮罩、焦点返回、页面高度与正文不进入 `#msg`，可由 DOM/键盘/布局测试验收。仍需补“复制成功后默认不自动打开长文本面板”以及“复制失败时面板/提示可退出”的明确断言，避免实现把长文本从一个堵塞点换成另一个堵塞点。

## Verified Facts（已验证事实＋证据）

- 只读打开 `/var/folders/mp/mnxk3h8x4wq5ztr7__vlplp40000gn/T/v2o-console-data/data/state.db`；根级 `v2o.db` 实测 0 字节，`data/state.db` 实测约 2.97 MB 且包含 `sources`、`processing_runs`、`artifacts`、`render_revisions`、`publish_records` 等表。
- `葫芦军师` 范围为 24 个 source/run；8 个源视频当前存在，16 个 `current_path` 当前不存在；24 条 raw state 均为 `source=ACTIVE`、`run=QUEUED`。
- 8 个现存源对应 8 个 Raw artifact、Render revision、Publish record，并有 job manifest；16 个缺失源没有 `raw_artifact_id`，对应 job manifest 也不存在。该对照支持“16 条不是已生成 Raw 后的转写失败”，但不支持“永远不可恢复”。
- 编排者提供的页面导出显示 16 条均为“源视频文件找不到了……检查视频是否被移动或删除……补回后点重试”。这是页面旁证，不是 DB 的结构化错误码。
- `葫芦军师` 目录当前有 8 个视频；`需转录视频` 下另有 `008林粒粒AI编程` 视频，但没有发现这 16 个缺失文件的原登记路径重新出现。未执行全盘扫描、同内容哈希搜索或外置卷挂载核验，因此“其他位置没有替代物”未验证。
- 本轮未请求 8765、未重启服务、未复制真实视频、未写真实视频目录或 Obsidian 库；数据库/目录检查为只读，单次命令墙钟小于 1 秒。

## External Sources（Web Search / Web Fetch / 官方文档 / 官方 GitHub / 第三方 / 社区反馈，附链接）

1. **官方 Apple Developer 文档**：App Sandbox、POSIX/ACL、SIP、数据保护都可能导致文件访问错误，不能从“读不到”单独推出根因。<https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?changes=_4>
2. **官方 Apple Support**：Documents、Downloads、Desktop、iCloud Drive、网络卷受用户同意与隐私控制影响。<https://support.apple.com/en-ie/guide/security/secddd1d86a6/web>
3. **官方 GitHub 文档（aria2）**：明确区分 active/waiting/paused/error/complete/removed，并保留完成/错误结果；支持按 offset/num 取结果。<https://github.com/aria2/aria2/blob/master/doc/manual-src/en/aria2c.rst>
4. **官方 GitHub Wiki（qBittorrent）**：missing files 是独立可见状态，可 recheck/resume；外置盘未挂载、网络位置离线也可造成该状态。<https://github.com/qbittorrent/qBittorrent/wiki/Status-of-Missing-files-at-start-up-or-after-restart>
5. **官方 GitHub Wiki（qBittorrent WebUI API）**：支持 completed/active/inactive/error 等过滤、排序、limit，说明可分页分组而不必固定铺平列表。<https://github.com/qbittorrent/qBittorrent/wiki/Home/96f8fe70807e70ee9b599d15580350fcf642c3a0>
6. **官方 Android 文档**：DownloadManager 对 waiting/retry、file already exists、device not found、insufficient space 等状态/错误作区分，并且目标已存在时不覆盖。<https://developer.android.com/reference/android/app/DownloadManager>
7. **官方 GitHub（yt-dlp）**：`--no-overwrites` 与 download archive 是成功项跳过/不覆盖的成熟做法，但不是用户编辑 Markdown 判定的直接证据。<https://github.com/yt-dlp/yt-dlp/blob/master/README.md?plain=1>
8. **官方 GitHub（Apple MLX examples）**：Whisper benchmark 分开模型加载、forward/decode 与端到端时间，支持本地测量而非只用单一 ETA。<https://github.com/ml-explore/mlx-examples/blob/main/whisper/benchmark.py>
9. **第三方 GitHub benchmark**：`mlx-whisper-fast` 报告不同模型/设备的 realtime factor，但其环境不能作为本机 ETA。<https://github.com/ilyasmukiev/mlx-whisper-fast>

## Competitor Findings（竞品现状＋对本 Plan 的启示）

| 主要主张 | 支持证据 | 反对证据/限制 | 别人成功但做法相反的案例 | 对 Plan 的结论 |
|---|---|---|---|---|
| 缺源应从可重试失败分离 | Apple 文档说明访问原因多层；qBittorrent 有 missing files 独立状态和 recheck | qBittorrent 仍把 missing files 作为红色错误/未完成对象，说明“分离”不等于“不算失败” | qBittorrent 成功保留错误状态并给 recheck，而不是将对象移出所有失败/未完成视图 | 保留 `source_missing` 独立计数，但继续出现在受阻/未完成总览；只从“可自动恢复失败”排除 |
| 7 类行动分类 | aria2/qBittorrent 都将状态、错误、队列动作分开，支持按状态筛选 | macOS 访问错误可能来自沙盒、ACL、SIP、挂载、路径迁移，行动类会遮蔽根因 | Android DownloadManager 使用更细错误码，如 file exists/device missing/space，而非一个 publish blocked | 双轴字段：action category + root cause/stage；保留 raw code 与 evidence，UNKNOWN fail-closed |
| P0-3 核心与视觉解耦 | GitHub Actions/aria2 提供可用的状态列表和下钻/筛选接口 | 本项目“首屏两次点击”仍受布局和长内容影响；没有 UI 实点证据 | aria2 可通过命令/API 直接按状态取结果，用户不必先完成视觉重排 | P0 只验状态、动作可达、可退出；P1-6 验视觉/历史，不共享发布门 |
| 保留 v2o 内部标识而改用户品牌 | yt-dlp 等工具把用户可见命令语义与内部归档机制分开 | 公开项目改名常遗漏帮助、流程节点、日志/导出文案；本项目尚无全字符串扫描结果 | Android/aria2 保持稳定 API/状态字段，同时允许 UI 标签独立演进 | D-24 增加用户可见字符串盘点；禁止改兼容键/目录/日志 |
| 查询/复制面板可退出 | Apple/浏览器无障碍惯例支持键盘焦点边界；D-23 已写可测关闭路径 | “可关闭”不保证长文本不自动塞进常驻提示；复制失败和焦点恢复仍可能漏测 | qBittorrent 使用独立日志/状态区与明确退出/过滤操作，不把整段错误塞进状态标题 | 复制只短提示；长文独立面板；用键盘、遮罩、焦点和布局高度做自动验收 |

## Counter-evidence（反对证据＋成功的相反做法）

- **对“16 条不可修复”的反对证据**：数据库保存了原路径和 source identity，但本轮没有证明该 identity 在别的目录、已挂载外置盘或云占位路径不存在；Apple 官方也明确指出沙盒授权、POSIX/ACL、SIP、iCloud/网络卷会产生不同访问结果。相反成功做法是 qBittorrent 在缺源时保留任务并允许 recheck/resume，而不是把任务标成永久不可修复。计划应说“当前原路径缺失、自动恢复禁用”，不要说“不可修复”。
- **对“DB 不是转写失败，所以页面只是缺源映射”的反对证据**：`QUEUED` 可能是旧状态、状态持久化不完整或运行时映射 bug；页面导出没有与 DB 快照绑定的时间戳/diagnosis id。相反成功做法是 aria2 公开 `status` 与结果队列，qBittorrent 公开状态过滤和 recheck，状态来源可追溯。需先补 provenance，再把因果结论降级为当前最强解释。
- **对“7 类已经足够”的反对证据**：Android DownloadManager 至少区分目标已存在、外部设备缺失、存储不足和一般文件错误；Apple 也列出 EACCES/EPERM 与沙盒等不同层。相反成功做法是保留细粒度 raw reason，同时上层提供较少的用户动作类别。现在的七类可作为 UI action taxonomy，但不能替代技术根因分类。
- **对“源缺失不算失败更好”的反对证据**：用户的目标是完成转写，源文件消失仍是任务未完成；完全从失败/异常区域移除会让用户以为 24 条都处理完成。qBittorrent 的相反做法是把 missing files 作为红色错误状态保留，再提供恢复动作。应采用“未完成/受阻可见，自动重试失败不计入”双语义。
- **对“P0-3 已完全解耦”的反对证据**：D-19 的两次点击、D-23 的面板高度和 D-18 的横条可访问性存在共享 DOM 约束，尚未有原型或离线 UI 证据。相反成功做法是 aria2 先用稳定状态/API 完成操作，再逐步优化展示。P0-3 必须移除布局尺寸依赖，P1-6 单独验收。
- **对“兼容边界已充分”的反对证据**：只列四处可见文案不能证明不存在其他用户可见 V2O 文案；相反成功的稳定接口原则要求显式回归内部键/协议。D-24 应加入 `rg` 字符串盘点和内部标识逐项断言，但不应扩展为仓库名改动。
- **对“可退出 DoD 已充分”的反对证据**：如果 `copyText` 成功后仍将正文传给另一个面板，用户仍会被迫处理长内容；如果焦点返回未测，键盘用户可能迷失。相反成功做法是独立状态/日志区 + 明确过滤和返回路径。D-23 应加“不自动打开长文面板”和复制失败路径。

## Unverified Items（未验证项＋验证方法）

1. **16 个文件是否被移到其他位置/外置盘/iCloud 占位路径**：未验证。只读检查已挂载卷、受限路径和用户明确允许的输入根目录；按 basename/源 size/mtime，必要时对候选文件做 hash 比对；结果只落系统 tmp。
2. **`data/state.db` 与页面导出是否为同一时间快照**：未验证。下次由页面诊断 API 输出 `diagnosis_snapshot_id/generated_at`，与只读 DB 的 WAL/mtime/状态事件时间对齐；禁止请求本轮禁用的线上服务。
3. **“运行时缺源映射”具体代码因果**：未验证。Phase2 用离线 handler/单元夹具追踪从 `current_path`、run status 到页面失败文案的映射；需要同时保留 raw state 和 display state。
4. **16 行矩阵是否能逐行提供 FR-1 全字段**：当前计划的表格只展示部分字段，`raw_error_code/worker_stage/artifact_presence/state_fingerprint/diagnosis_snapshot_id` 等未逐行出现。验证方式是每行输出字段存在性、值或 `UNKNOWN`，再做 schema 校验。
5. **7 类与技术根因双轴是否覆盖权限、挂载、路径迁移、媒体损坏、发布冲突**：未验证。用系统 tmp 合成夹具逐类注入，并断言 action category、root cause、stage、confidence 不互相覆盖。
6. **旧 retry/reapply/publish 六项门**：仍未验证。系统 tmp 夹具执行入口契约、状态迁移、写集、回滚、重复提交和 No-Clobber 测试。
7. **真实 Whisper 性能与峰值内存**：仍未验证。HD-5 已授权，但本轮不复制视频；需后续只复制 1 个短样本和 1 个长样本到外置 tmp，记录 D-10 全协议。第三方数字只能作量级背景。
8. **D-23 的真实布局/键盘行为**：仍未验证。离线合成 16 条长文，测试 `#msg` 高度、面板关闭按钮、Esc、遮罩、焦点返回、复制失败和窄屏无溢出。
9. **D-24 全部用户可见文案与内部兼容标识**：未验证。Phase2 对 `app/index.html`、README 和资源文案做静态扫描，并逐项确认 `v2o-*`、日志前缀、数据目录字符串不变。

## Required Fixes（Planner 必须改项，打回依据）

本轮判定上一轮 12 条中 **11 条到位、1 条未完全到位**：

1. **到位**：FR-1/FR-2/FR-4 已补证据优先级、冲突、置信度、UNKNOWN 与矩阵交付物；但本轮新增要求见 RF-13，矩阵需逐行完整落字段。
2. **到位**：P0-1/D-1 已把真实 16 条逐条可追溯设为门，合成仅覆盖未来规则分支。
3. **到位**：各策略已有前置、读写集合、迁移、失败、回滚、重复提交；D-5 也设置了旧入口六项契约门。
4. **到位**：核心 P0-3 与视觉/历史 P1-6 分拆，尺寸为可调整基线，并声明视觉不阻塞核心。
5. **到位**：FR-12/D-15 明确首版 20、cursor、排序、并列时间戳、归档和刷新一致性。
6. **到位**：FR-13/D-16 明确持久生命周期、worker 阶段、恢复资格三层契约及监听不变量。
7. **到位**：FR-5/FR-6/D-6/D-9 明确 snapshot、fingerprint、token TTL/漂移、部分成功、重启和 job 真源。
8. **到位**：FR-7/D-7/D-8/D-17/D-20/D-21 已覆盖源、Raw/Norm/Render、Markdown、用户编辑内容与 DB 历史的保护及原子/并发失败。
9. **到位**：D-10/P1-1 已写完整实验协议并禁止第三方 benchmark 充当本机 ETA；事实仍未实测，但这是计划字段的要求，不是本条缺陷。
10. **到位**：FR-3/D-12/D-14/D-22 已写脱敏、错误响应和外置 tmp 审计边界。
11. **到位**：P1-1～P1-7 与 P3 表逐项写主线关系、工作量和不做影响，已移除无证据的“低成本”。
12. **未完全到位**：HD-1～HD-9 已标已决并写规格，但 FR-15 使用“不可逆 data_root 摘要分区”措辞，容易把视图隐藏误读为不可逆；且 Human Decisions 段落没有把“历史默认可恢复”作为可验收语义标题单独列出。D-17 虽补了恢复测试，建议 Planner 统一用“不可逆 hash/摘要标识、可逆隐藏状态”，并让 HD-7 规格与 D-17 字面一致。

### 本轮新增 Required Fixes

13. **收窄真实证据结论并补替代路径判定**：在 Product Goal、Problem、FR-1/FR-4、D-1、P0-1 和真实矩阵说明中，将“源文件已缺失/不可修复”改为“源文件不在原登记路径；当前证据不允许自动恢复”。增加 `alternate_path_checked / identity_match / mount_or_provider_checked / snapshot_time` 或等价字段；找不到替代物时也必须写 `UNKNOWN/未验证`，不能把未搜索当作不存在。
14. **补持久状态与页面显示的 provenance 契约**：把“页面失败≠DB 转写失败/运行时缺源映射”改为可证程度的表述；增加页面快照与 DB 状态的时间、snapshot/diagnosis id、state event 来源，以及 `display_state` 与 `persisted_state` 不一致时的处理。否则页面失败的因果判断仍是推断。
15. **将七类改为双轴 taxonomy**：保留七个用户行动类别，但新增或明确技术 `root_cause` 与 `stage` 字段，至少能分别表达路径不在原位、权限/沙盒、挂载/云占位、媒体不可读、转写瞬时异常、产物复用、发布冲突/No-Clobber。合成验收须断言行动类别与技术根因不会互相覆盖。
16. **补反馈 A 与 D-24 的边界验收**：D-23 增加复制成功不自动打开长文面板、复制失败不显示正文、焦点返回和窄屏高度上限；D-24 增加全仓库用户可见 V2O 文案静态盘点，同时逐项证明内部 `v2o-*` 键、日志前缀和数据目录不变。

## Plan Readiness Score（分项打分＋合计，口径以 PRODUCT_PLAN.template.md 为准）

- 产品目标与用户需求（20）：**19/20**。HD-1～HD-9 已闭合，且反馈 A/B/C 已落点；扣 1 分因为“缺源不计失败”尚未验证对用户可发现性的影响。
- 核心方案完整性（20）：**16/20**。上一轮 +2：恢复契约、三层状态、分页、快照和安全边界已写全；扣 4 分因为真实状态 provenance、替代路径判定和双轴分类仍未闭合。
- 外部事实与竞品验证（20）：**17/20**。已有 Apple/aria2/qBittorrent/Android/yt-dlp/MLX 等高质量来源，足以支持方向；扣 3 分因为公开资料不能证明本项目 20 阈值、分类覆盖率或本机性能。
- 技术可行性（15）：**11/15**。真实 DB/磁盘旁证增强了缺源判断；旧入口、API provenance、性能、并发和 UI 仍无实现证据。
- 风险与异常场景（10）：**8/10**。已覆盖 No-Clobber、并发、权限、未知、长提示和恢复漂移；扣 2 分因为路径迁移/云占位/状态层不一致还没有实际验收。
- 开发范围与 DoD（10）：**8/10**。24 条 DoD 大多可测，P0/P1 已拆；扣 2 分因为 D-1 的“完整 FR-1 逐字段”与现有 16 行展示表不一致，D-24 用户可见文案范围不完整。
- 未决问题（5）：**4/5**。没有新的 Human-only Decision；剩余是可由工程/研究验证的事实，不应转嫁给用户，但关键事实尚未执行。
- **合计：83/100**。
- **Gate 判断：未达到。** Readiness < 90，P0 仍有 3 条未清，blocking P1 仍有 2 条，且 provenance、替代路径、旧入口和性能等关键事实未验证；不能进 `WAITING_HUMAN_APPROVAL`。

## Human-only Decisions（只需人类拍板项）

**0 项。** HD-1～HD-9 已决，本轮没有发现必须用户重新选择的产品语义。新增要求均是 Planner/Phase2 的证据、字段、契约或验收问题，不应包装成 HD。

## Next Action（回 Planner 修订 / 进 WAITING_HUMAN_APPROVAL 找人）

**回 Planner 再修。** 原 12 条只有 11 条完全到位；并且本轮新增 Required Fixes 13～16 直接影响“16 条全是缺源、0 条可恢复”和诊断分类的事实强度。修完后应先完成只读 provenance/替代路径边界与完整逐字段矩阵，再复审；在此之前不得进入 `WAITING_HUMAN_APPROVAL`。
