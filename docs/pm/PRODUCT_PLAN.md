# PRODUCT_PLAN（Phase1 专用；Readiness 定义唯一正典，卡内引用不重写）

> ⚠️ 收尾注记（2026-09-13，neat-freak 加）：本文件 **V1.3 的正文为最新**；但文末「Readiness Score」与「本轮真实验证记录」两段仍是 **V1.2 旧文本**——第 5 轮修订被用户中止（用户要求停止循环），**未完成收尾**。引用评分/验证结论时，请以正文与 `docs/review/RESEARCH_REVIEW.md` 第 2 轮为准。

- Plan Version：`PRODUCT_PLAN_V1.3`
- PROJECT_PHASE：（PLAN / WAITING_HUMAN_APPROVAL / DEVELOP / PLAN_REOPEN_REQUIRED，仅Change C受控重开期间）`PLAN`
- Product Goal：让用户在“懒得笔记”本机控制台中看懂任务真实状态：当前 16 条均为“源文件不在原登记路径、但已在替代路径发现身份匹配文件”的未完成/受阻任务；它们保持可见，但在用户确认重新绑定且完成新诊断前不计入可自动重试失败。对其他真正可恢复的失败提供可解释诊断与安全恢复，同时不覆盖既有笔记、不写用户真实视频目录。
- Target Users：
  - 核心用户：在 Apple Silicon Mac 上批量处理课程、会议、采访等本地音视频，并将 Markdown 笔记写入 Obsidian 的个人用户。
  - 次要用户：只需要本地转写与 Markdown 成稿、不配置 Obsidian 库的用户。
  - 使用前提：能启动 Python 3.12 虚拟环境，环境中可用 `mlx_whisper`，系统可调用 `ffmpeg`；接受工具仅监听 `127.0.0.1:8765`。
  - 当前页面基线：77 条任务，成功 61、显示失败 16。V1.3 只读复核确认：16 条原登记路径当前均无文件，但 16/16 都在 `…/暂不转录视频/葫芦军师/` 找到 basename、大小、mtime 与 SHA-256 完全一致的替代文件。可证结论是“原登记路径不在位、替代身份 MATCH、当前自动恢复资格为 0”；不能据此断言文件被删除、不可恢复或页面失败的唯一代码根因。
- Problem：
  - 当前控制台把 16 个原登记路径无文件的 `QUEUED` 历史 run 显示成“失败”，并提供“重试全部失败”，造成“已证实为 Whisper 失败且可直接重试”的错误心智。V1.3 已找到 16 个身份完全匹配的替代文件，但它们位于名为“暂不转录视频”的目录；在用户明确确认重新绑定、身份复核和新诊断前，当前证据不允许自动恢复。
  - 不同失败需要不同动作：环境缺失、媒体不可读、转写异常、整理/成稿异常、入库受阻、No-Clobber 冲突、瞬时异常不能使用同一重试策略。
  - 批量重试缺少按根因分组、执行前代价预览、不可重试项隔离和执行后汇总，容易浪费真实 whisper 时间，或误以为“按钮点过即全部恢复”。
  - 当前 16 条在“用户行动”轴上均为 `SOURCE_LOCATION_REVIEW`，在“技术根因”轴上均为 `SOURCE_NOT_AT_RECORDED_PATH + IDENTITY_MATCH_AT_ALTERNATE_PATH`，发生阶段为 `DISCOVERY`。页面 FAIL 与 DB `QUEUED` 并非同一时间对齐快照，具体显示映射因果仍未验证；旧恢复入口副作用、真实 Whisper 耗时、61 篇量级重跑耗时与长视频表现也未验证。
  - 累计 22 条 P3 虽不阻塞现版本，但其中一部分会影响 v2 的任务身份、批量操作契约和结果可信度，必须逐条取舍，不能整体忽略或整体升为 P0。
- Core Value：
  - **先证据后结论**：先区分“可自动重试失败 / 原路径不在位 / 替代身份已匹配 / 人工受阻”；每条记录同时给出行动类别、技术根因、阶段、provenance、置信度和下一步。无法可靠判断即 `UNKNOWN`，不得把“未搜索”写成“不存在”。
  - **只重跑该重跑的**：按失败类型选择“直接重试、修复环境后重试、仅重试入库、不可自动重试”，降低时间成本。
  - **批量但可控**：批量动作必须先预览数量、预计会重新调用 whisper 的数量、不会调用 whisper 的数量、排除项和风险，再由用户确认。
  - **不伤已有成果**：61 个成功项保持不动；主题默认浅色；No-Clobber 永久成立；用户真实视频目录与 Obsidian 库禁作测试写入目标。
- User Flow：
  1. 用户打开控制台，首屏按“从上到下、从左到右”依次看到：普通顶部五步横条 → 独立监听状态与路径/开始停止 → 当前任务总览 → 当前与异常任务 → 恢复与重试 → 完成历史；页面仍默认浅色。
  2. 顶部流程条位于普通文档流，滚动时自然离开，不 sticky、不可收起；建议高度不超过 64px，但可根据原型验证调整。桌面建议主任务区 + 操作/详情两列，320px/960px 为可调整设计基线，不作为诊断恢复主线的发布阻断尺寸；窄屏按 DOM 顺序单列且不得横向溢出或遮挡焦点。
  3. 控制台把任务信息分为四层：持久生命周期、页面展示状态、仅对当前 ACTIVE 有意义的 worker 阶段、诊断得出的恢复资格。“监听中/未监听/停止收尾”单独显示；同一快照下监听开关不改变逐 run_id 的任务文字、颜色、原因、统计或恢复资格。`display_state` 与 `persisted_state` 不一致时同时展示并标“显示与记录不一致，原因待验证”，不静默择一。
  4. 首屏任务列表始终优先显示“处理中 + 排队 + 失败/受阻”；已完成首版默认显示最近 20 条，更早完成默认收起并按需加载，总数与展开入口常显。20 是首版默认参数，不是永久产品规则。
  5. 首屏可见的统一“恢复与重试”操作区集中放置：重试所选失败、重试全部可恢复失败、应用新词库重新成稿、仅重试入库；具体任务详情仍可给上下文动作，但不再把同族动作散落在表头、词库底部和页面最下方。
  6. 用户点击“查询失败原因”。分析只读生成带时间戳与 provenance 的诊断快照；当前总览显示“未完成/受阻 16”“其中原路径不在位 16”“发现身份匹配替代文件 16”“可自动重试失败 0”。这 16 条保持在未完成/受阻区，不静默消失；操作仅为“确认替代路径并重新诊断/保持暂不转录”，不显示直接自动重试。
  7. 页面按类别显示失败数量、证据来源、置信度、冲突/缺失、建议动作、恢复资格和是否会再次调用 whisper；用户可展开查看 16 条逐项明细。
  8. 用户勾选一个或多个安全可重试类别或具体任务，进入“执行前预览”：展示选中、将排队、被排除、预计重新转写、仅重做后续阶段、No-Clobber 跳过的数量。
  9. 用户确认后，系统使用诊断快照、任务指纹和 plan token 幂等排队；页面以持久 `data_root + job_id` 真源显示完成/失败/跳过/人工处理/中断，刷新或服务重启后可恢复终态或明确显示中断，不串目录或标签页。
  10. “清空已完成列表”实际只把成功项加入浏览器本地视图归档：按 data_root 摘要隔离，跨刷新和同浏览器服务重启保留；历史区可逐项或全部恢复显示。不得写业务 DB，不删 Markdown、任务记录、Raw/Norm/Render 或源视频；破坏性清理仍留高级入口并二次确认。
  11. 执行结束后，用户获得按类别汇总的结果；61 个原成功项和用户改过的笔记保持不变。
- Functional Scope：
  - **FR-1 失败诊断快照、替代路径与 provenance 契约**：每条异常输出 `run_id / source_label / recorded_path_redacted / recorded_path_exists / alternate_path_checked / alternate_path_redacted / identity_match / mount_or_provider_checked / persisted_state / persisted_state_source / state_event_at / display_state / page_snapshot_at / provenance_status / worker_stage / job_manifest_exists / artifact_presence / evidence_sources / raw_error_code / evidence_conflicts / confidence / action_category / root_cause / stage / retry_policy / recovery_eligibility / will_call_whisper / reason / missing_evidence / next_action / state_fingerprint / diagnosis_version / diagnosis_snapshot_id / snapshot_time`。V1.3 已用只读审计补齐真实 16 行矩阵；未获得的值必须写 `UNKNOWN/未验证`。诊断不得修改 DB、manifest、源视频或笔记。
  - **FR-2 七类用户行动 + 技术根因/阶段双轴 taxonomy**：用户行动类保持七个：`SOURCE_LOCATION_REVIEW / PRECONDITION_BLOCKED / INPUT_MEDIA_INVALID / RETRYABLE_TRANSCRIPTION / REUSABLE_DERIVED_FAILURE / PUBLISH_BLOCKED / UNKNOWN`。另设独立 `root_cause`，至少覆盖 `SOURCE_NOT_AT_RECORDED_PATH / IDENTITY_MATCH_AT_ALTERNATE_PATH / PERMISSION_OR_SANDBOX / MOUNT_OR_CLOUD_PLACEHOLDER / MEDIA_UNREADABLE / TRANSCRIPTION_TRANSIENT / DERIVED_ARTIFACT_REUSABLE / PUBLISH_PERMISSION / PUBLISH_NO_CLOBBER_CONFLICT / UNKNOWN`；独立 `stage` 至少覆盖 `DISCOVERY / ASR / NORMALIZE / RENDER / PUBLISH / SYSTEM / UNKNOWN`。行动类回答“用户下一步做什么”，root_cause 回答“技术上发生了什么”，stage 回答“发生在哪一步”，三者不得互相覆盖或互相推导冒充事实。证据优先级固定为“结构化错误码与带时间的持久状态事件 > manifest/receipt/verdict > 源/产物存在性与身份哈希 > 只读挂载/权限/云占位探针 > 人话文案”。证据冲突、时间未对齐或必要证据缺失时自动恢复必须 fail-closed。

    | 行动分类 | 当前 16 条数量 | 是否计入失败 | 自动恢复 | 用户动作/策略 |
    |---|---:|---:|---:|---|
    | `SOURCE_LOCATION_REVIEW` | 16 | 计入“未完成/受阻”；不计入“可自动重试失败” | 否 | 已发现身份匹配替代路径；确认是否重新绑定并生成新诊断 |
    | `PRECONDITION_BLOCKED` | 0（未观察） | 否；计入“环境受阻” | 否 | 修复环境/权限后重新诊断 |
    | `INPUT_MEDIA_INVALID` | 0（未观察） | 是 | 否 | 检查格式、损坏、可读性；人工处理 |
    | `RETRYABLE_TRANSCRIPTION` | 0（未观察） | 是 | 证据满足时可 | 重新转写；含转写阶段瞬时异常 |
    | `REUSABLE_DERIVED_FAILURE` | 0（未观察） | 是 | 证据满足时可 | 复用 Raw/Norm 重做后续，Whisper=0 |
    | `PUBLISH_BLOCKED` | 0（未观察） | 视原因：权限受阻不计失败，成稿后发布失败计失败 | 仅安全新建时可 | 仅重新入库；No-Clobber 仍只判不写 |
    | `UNKNOWN` | 0（未观察） | 否；单列“待判断” | 否 | 展示缺失/冲突证据，人工确认 |
  - **FR-3 批量诊断 UI 与脱敏摘要**：页面可看逐条本地证据；一键复制只包含脱敏 source label、目录尾段、错误码、类别、置信度、缺失证据和建议，不含真实绝对路径、转写/笔记正文、密钥或请求体；不弹出成功 toast 洪水。
  - **FR-4 差异化重试策略**：
    - `SOURCE_LOCATION_REVIEW`：DB 有 recorded path 与 run，但原路径 `is_file=false`。必须先只读检查已挂载卷、常见替代位置及可用的 iCloud/云占位位置，并按 basename、记录大小、mtime，必要时 SHA-256 判定身份。未搜索或没有候选写 `identity_match=UNKNOWN`；候选匹配也只表示“发现同一内容的替代路径”，不代表用户授权重新绑定。该类仍计入“未完成/受阻”，但不计入“可自动重试失败”且不进入批量自动重试。用户确认替代路径后须重新生成 snapshot/fingerprint，旧 plan token 永不复用。
    - `BLOCK_UNTIL_FIXED`（环境）：前置条件未满足；只读状态/证据/能力探针，零业务写入，生命周期不变、资格=`NEEDS_HUMAN`，不排队。
    - `MANUAL_REVIEW`（媒体/未知）：媒体不可可靠读取、证据冲突或缺失；只读状态及 ffprobe/ffmpeg 探针，探针输出只准系统 tmp，零业务写入，生命周期不变，不排队。
    - `RETRANSCRIBE`：仅转写/瞬时异常、源可读、当前非成功且指纹匹配；可读源与旧元数据，只能向 data_root 新 job 工作区写新 Raw/Norm/Render、job 与状态事件；`FAILED/BLOCKED→QUEUED→ACTIVE→SUCCEEDED/FAILED/BLOCKED`。原子写失败保留旧有效版本；同 token/run 只允许一个活跃 job，重复返回既有 job 或 409。
    - `REUSE_DERIVED`：Raw/Norm 存在且哈希与 lineage 可证；只写新 Norm/Render 版本、job 与状态事件，不直接发布；`FAILED/BLOCKED→QUEUED→ACTIVE→SUCCEEDED/FAILED`，失败保留旧版本，重复提交同上，whisper_calls=0。
    - `PUBLISH_ONLY`：Render/lineage 有效、vault 已配置且目标可安全新建；只可新建不存在的 canonical Markdown，并写 publish receipt/job/状态；`FAILED/BLOCKED→QUEUED→ACTIVE→SUCCEEDED/SKIPPED/NEEDS_HUMAN`。目标已存在或并发竞态即跳过/人工，覆盖次数 0，whisper_calls=0。
    - 旧 `retry/reapply/publish` 入口必须先通过“前置条件、允许读写集合、状态迁移、失败后状态、重复提交、No-Clobber”六项契约测试，才可作为批量原语；任一项未证不得接入。
  - **FR-5 执行前 dry-run 与快照一致性**：诊断生成 snapshot；每个 run 由持久状态、stage、关键证据/产物版本生成 fingerprint。dry-run 用排序后的 `data_root_digest + snapshot + run/fingerprint + strategy + server_nonce` 生成不可猜测 plan token，服务端仅存摘要；首版 TTL=10 分钟。过期、漂移或跨目录返回 409 并要求重新诊断，不静默重算后执行。
  - **FR-6 持久批量任务真源**：确认后原子创建 `data_root/data/recovery_jobs/<job_id>.json`，它是批量 job 真源，内存仅为运行缓存。逐项记录 snapshot、token 摘要、fingerprint、策略、状态、结果与时间；部分成功逐项原子落盘。服务重启后终态可读，未终态标 `INTERRUPTED`，不自动续跑，重新诊断后方可新建计划。
  - **FR-7 No-Clobber 分级安全守卫**：源视频只读，禁改名/移动/删除/写入；旧 Raw/Norm/Render 不覆盖不删除，只写新版本；任何既有 canonical Markdown 均不覆盖，用户编辑过的任意字节差异为最高保护级，只能 skipped/needs_human；DB/manifest/receipt/job 仅允许追加必要状态与新版本引用，禁止删除成功记录或改写历史事实。事务/原子写失败必须保持可复算状态。成功 61 项默认不进入失败恢复；缺失 vault 不创建；测试写入只在系统 tmp。
  - **FR-8 结果汇总与统计双语义**：终态区分 `recovered / still_failed / source_location_blocked / skipped / needs_human / interrupted`。第一层是任务完成语义：`source_location_blocked` 仍计入“未完成/受阻”并保持可见，用非静默的受阻色和文案显示“原登记路径无文件；已发现替代路径，待确认”；第二层是恢复资格语义：这些项不计入 `auto_retryable_failure_count`，不进入“重试全部可恢复失败”或自动重试。页面同时显示“未完成/受阻 16”与“可自动重试失败 0”；逐条返回最终状态、策略、Whisper 调用数、原因和下一步。
  - **FR-9 现有功能不回退**：监听、停止、目录浏览、路径记忆、单条重试、清空预览、笔记预览、访达/Obsidian 打开、词库、候选应用、错词重跑和浅色主题继续可用。
  - **FR-10 普通顶部横向流程条（HD-9=A）**：移除左侧全高流程列，改为普通文档流横条，滚动自然离开，不 sticky、不可收起。建议高度不超过 64px但可按验证调整；节点有文字与非颜色状态，不遮挡焦点。
  - **FR-11 首屏信息层级与响应式栅格**：桌面建议主任务区 + 操作/详情两列，320px/960px 是首轮可调整基线；小屏按 DOM 顺序单列，无横向溢出，主操作不落到历史之后。视觉尺寸争议不得阻塞 P0 诊断恢复安全闭环。
  - **FR-12 任务列表分层、cursor 历史与首版默认 20（HD-6=A）**：当前/排队/失败/受阻始终可见；完成项请求默认 `completed_limit=20`，返回 `completed_total/next_cursor`。排序为 `finished_at DESC, run_id DESC`，缺 finished_at 时用 `updated_at DESC, run_id DESC`；cursor 含排序键，并列时间戳由 run_id 决胜。更早完成默认收起并按需加载。归档只改变本地视图过滤、不改服务端总数；刷新后同 data_root 摘要恢复同一视图，展开无重复遗漏。
  - **FR-13 四层任务状态与 provenance 契约（HD-8=A）**：①持久生命周期 `persisted_state=QUEUED/ACTIVE/SUCCEEDED/FAILED/BLOCKED/SKIPPED`，必须附 `persisted_state_source/state_event_at`；②页面展示状态 `display_state`，必须附 `diagnosis_snapshot_id/page_snapshot_at/snapshot_time`；③worker 阶段仅在 ACTIVE 显示“发现/听写/整理/成稿/入库”，只能由带时间的实际处理事件推进；④诊断恢复资格为 `AUTO_RETRANSCRIBE/AUTO_REUSE/AUTO_PUBLISH/NEEDS_ENV_FIX/NEEDS_MEDIA_CHECK/NEEDS_HUMAN/NOT_APPLICABLE`。仅当 state event 与页面 snapshot 时间对齐且证据无冲突时，才可声明映射因果；`display_state != persisted_state` 时必须并列两者、来源和时间，显示“展示与记录不一致，原因待验证”，恢复资格 fail-closed，不用页面状态回写或覆盖持久状态。监听开关只改变独立监听状态。
  - **FR-14 统一恢复入口**：将“重试全部失败”“应用新词库重跑”“全部应用新词库重跑”和入库重试收敛到首屏可见的“恢复与重试”区域；用动作后果命名为“重新转写 / 从已有文字重新成稿 / 仅重新入库”，并在执行前标明是否调用 whisper。详情内仅保留当前任务的上下文快捷操作。
  - **FR-15 隐藏已完成的持久语义（HD-7=A）**：任务标题区提供“从当前列表隐藏已完成”，状态只写浏览器 localStorage，跨刷新和同浏览器服务重启持久。**使用不可逆的 data_root hash/摘要标识做分区；隐藏状态可逆；历史默认可恢复，可逐项或全部恢复；业务数据零删写。**不同浏览器不承诺同步；破坏性清理继续放高级入口，展示代价并二次确认。
  - **FR-16 P3 分流**：按本计划“22 条 P3 处置表”实施、延后或明确不做，不得在开发阶段自行改优先级。
  - **FR-17 查询/复制结果可退出（反馈 A）**：`copyText(t)` 成功后只允许短提示，例如“已复制 16 条失败原因”，且不自动打开长文面板；长文本不得写入常驻 `#msg`。需要查看长文本时使用有标题、关闭按钮、Esc 关闭、点击遮罩关闭且焦点可返回原触发控件的面板/抽屉；窄屏高度上限为 `min(70vh, 560px)` 并内部滚动。短提示 3 秒自动消失或可点击关闭；复制失败只显示短错误，不显示、不打开也不把待复制正文拼入提示。
  - **FR-18 产品改名（反馈 C，已决）**：页面产品名改为“懒得笔记”，建议副标题“懒得笔记 · 本地视频自动转文字”。Phase2 先静态盘点全仓库用户可见的 `V2O/v2o` 文案，至少包括 `app/index.html`、`README.md`、`README.en.md`、`docs/usage.md`、`docs/troubleshooting.md` 及 assets/资源中的 UI 文案；逐项改用户品牌文案，但不改仓库名。兼容清单须逐项证明全部内部 `v2o-*` 键、`v2o-console:` 日志前缀、`v2o-console-data` 数据目录字符串以及 API/状态标识不变，不将范围扩展为仓库改名。

- 真实 16 行只读证据矩阵（V1.3，2026-09-13）：
  - 诊断快照：`diagnosis_snapshot_id=plan-v1.3-readonly-20260913T183831+0800`，`snapshot_time=2026-09-13T18:38:31+0800`，`diagnosis_version=plan-v1.3-offline-audit-1`。SQLite 通过 `file:…/data/state.db?immutable=1` 只读打开；DB 文件 mtime=`2026-09-13T18:08:12+0800`。未请求 8765。
  - 替代路径检查：对 Desktop、Documents、Downloads、Movies、Music、Pictures、Public、Trash、`/Users/Shared` 九个常见根做确定性 basename/`.icloud` 变体扫描，同时用 Spotlight 对索引范围做精确 basename 查询。逐项比较 DB 记录的 `source_size/source_mtime_ns/content_identity`；16/16 在 `…/Downloads/暂不转录视频/葫芦军师/<同 basename>` 命中，大小、mtime 与 SHA-256 全部一致。
  - 挂载/云提供方检查：枚举 `mount`、`df` 与 `/Volumes`，当前只有本机 APFS 系统卷及只读 App Translocation，没有独立外接盘或网络卷；`~/Library/CloudStorage`、`~/Library/Mobile Documents` 与 `com~apple~CloudDocs` 当前不存在，常见根内也未发现 `.icloud` 占位变体。因此能证明“当前已挂载/可见范围已检查”，不能证明未挂载卷或未配置云端中没有其他副本。
  - 16 行共享字段（每行均适用，不是省略）：`recorded_path_exists=false`；`alternate_path_checked=九个常见根+Spotlight+占位变体`；`alternate_path_redacted=…/暂不转录视频/葫芦军师/<同 basename>`；`identity_match=MATCH(size+mtime+sha256)`；`mount_or_provider_checked=本机挂载已枚举/外接与网络卷未挂载/常见云根当前不存在`；`persisted_state_source=state.db:sources+processing_runs`；`display_state=FAIL（页面导出）`；`page_snapshot_at=UNKNOWN`；`provenance_status=NOT_TIME_ALIGNED`；`worker_stage=UNKNOWN`；`job_manifest_exists=false`；`artifact_presence=Raw/Norm/Render/Publish 均无`；`raw_error_code=UNKNOWN`；`evidence_conflicts=DB QUEUED vs 页面 FAIL`；`confidence=HIGH（路径与身份）/UNVERIFIED（页面因果）`；`action_category=SOURCE_LOCATION_REVIEW`；`root_cause=SOURCE_NOT_AT_RECORDED_PATH + IDENTITY_MATCH_AT_ALTERNATE_PATH`；`stage=DISCOVERY`；`retry_policy=CONFIRM_ALTERNATE_THEN_REDIAGNOSE`；`recovery_eligibility=NEEDS_HUMAN`；`will_call_whisper=false`；`state_fingerprint=UNKNOWN（Phase2 API 尚未生成）`；`missing_evidence=与页面同刻 snapshot/state event 链`；`next_action=用户确认是否重新绑定替代路径，再生成新诊断`。

  | run_id | source label / recorded path | alternate_path_checked | identity_match | persisted_state / state_event_at | display provenance | action_category / root_cause / stage | 自动恢复 / snapshot |
  |---|---|---|---|---|---|---|---|
  | `run_1aa4b0dffec30b34` | `2024-07-11…497747.mp4`；原登记路径无文件 | `…/暂不转录视频/葫芦军师/<同名>` | `MATCH`（size+mtime+SHA-256） | source=`ACTIVE` / run=`QUEUED`；`2026-09-11T03:05:32Z` | 页面=`FAIL`；时间 `UNKNOWN`；`NOT_TIME_ALIGNED` | `SOURCE_LOCATION_REVIEW` / `SOURCE_NOT_AT_RECORDED_PATH+IDENTITY_MATCH_AT_ALTERNATE_PATH` / `DISCOVERY` | 否；`plan-v1.3…183831` |
  | `run_ab0f8ffc97120411` | `2024-08-03…764412.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:33Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_066b3a09f06c092c` | `2024-10-30…194423.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:33Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_bdf6e9df1e870f9c` | `2025-01-01…042101.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:33Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_2fe9e8c1136037fc` | `2025-03-09…348559.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:34Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_53d22e8f4f6751e7` | `2025-03-15…174103.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:34Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_aa2ab0e4ab814f9a` | `2025-04-04…587116.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:34Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_bcbd94e9227b6f3f` | `2025-05-24…499415.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:34Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_49aeecba93358a35` | `2025-06-14…黄金投资….mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:35Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_364bc15d669a8d69` | `2025-07-12…270803.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:35Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_e2934614fe9de01f` | `2025-07-26…429155.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:35Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_e2bb05c0c6654502` | `2025-08-18…589029.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:35Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_c86cef2478da4f49` | `2025-09-20…股市分析….mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:35Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_54f91386e59d2ca7` | `2025-09-25…460343.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:36Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_5e1cbc22f5c0f33b` | `2026-01-24…101835.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:36Z` | 同上 | 同上 | 否；同 snapshot |
  | `run_351d30e36be17a6c` | `2026-02-10…691918.mp4`；原登记路径无文件 | 同上 | `MATCH`（size+mtime+SHA-256） | `ACTIVE/QUEUED`；`2026-09-11T03:05:36Z` | 同上 | 同上 | 否；同 snapshot |

  结论：16/16 的原登记路径当前无文件，16/16 在替代路径身份匹配，UNKNOWN=0（就本次已检查范围与 16 个 identity 而言）。它们仍是“未完成/受阻”任务，不能从异常总览消失；但在用户确认替代路径、重新绑定并生成时间对齐的新诊断前，“可自动重试失败”=0。页面 FAIL 的具体运行时代码因果仍为 `UNKNOWN/未验证`。

- User Feedback Mapping：

  > 现在使用过程中，这个界面还是比较混乱的，主要存在以下问题：

  > 建议参考一下市面上成熟产品是怎么做的。

  > 还有当前这个布局，我觉得也非常不合理：

  > 所以，布局应该符合用户的操作逻辑，即从上到下、从左到右。尽量让用户在视线范围内，就能把这个功能全部进行操作。我觉得也需要让这个 planner 看怎么优化一下。

  | 用户反馈（逐字） | 判断的根因 | 下一版怎么改 | 落点 | 验收方式 |
  |---|---|---|---|---|
  | 内容过多且缺乏展示优化<br>(a) 列表过长：首先完成的内容列在这儿非常长，内容太多了。<br>(b) 缺乏折叠机制：不能把七八十条全部怼在这个界面上给用户。可以参考市面上成熟产品的做法，比如采用滚动展示最近的二三十条，之前已完成的内容折叠起来，用户想看可以打开，不想看也可以不看。 | 前端固定 `limit=200`，77 条一次全铺；没有当前/历史分层、折叠、分页或懒加载。 | 当前/排队/失败优先；完成首版默认显示 20 条；更早完成默认折叠并用 cursor 按需加载，显示当前/总数。 | **P1-6** | 构造 77 条（61 成功/16 失败）：首屏不出现 77 行；当前和 16 失败均可到达；完成默认 20；展开历史后全部 61 条无重复/漏项。 |
  | 监测状态显示不一致<br>点击"监测"和没有点"监测"时，下面的每一条状态为什么不一样？<br>(a) 未点监测时：显示一堆失败或者是红色的字。<br>(b) 点击监测后：依然是一堆东西在上面，之前完成的也在上面。<br>不管点没点，不应该都统一显示当前任务的状态（比如已完成哪些、哪些还在排队）吗？为什么两个状态会不一样呢？ | `statusCN(r, cur)` 依赖 worker.current/running，把监听系统态混入任务持久态；同一任务在监听开关前后可能换文案和颜色。 | 拆分“系统监听状态”和“任务生命周期状态”；同一状态快照在监听开/关时任务状态、颜色、计数不变，只有 ACTIVE 的当前阶段可随 worker 推进。 | **P0-3** | 固定同一批任务，分别在未监听/监听中/停止收尾三态渲染；逐 run_id 对比稳定状态、颜色、成功/失败/排队计数完全一致，仅系统状态条和当前 ACTIVE 阶段允许变化。 |
  | 缺少清空列表功能<br>应该有清空已完成列表的功能。我看现在这个功能好像没有做，或者做好了也没有发挥作用。 | 功能并非不存在：现有入口叫“清空本目录任务”，位置不显眼，只有“只清失败/全部清空”，缺少用户要的“只清已完成”；“清列表”和“删数据”也未分开。 | 增加“从当前列表隐藏已完成”；localStorage 按 data_root 摘要持久，历史可恢复，业务数据零删写。破坏性清理留高级区。 | **P1-6** | 隐藏后跨刷新/同浏览器服务重启保留，历史可逐项/全部恢复；源、稿件、Raw/Norm/Render、DB/manifest 不变。 |
  | 左侧流程占地过大：<br>为什么左侧从上到下的这个流程占了那么大的空间？这很有必要吗？我觉得应该放到最顶上，做成薄薄的一横条就可以了。现在放到左上角，占了一大块空间，空间利用率不好。 | 三列网格固定 `220px 1fr 300px`，流水线磁带独占左列并铺满全高，重复占用最宝贵的首屏水平空间。 | 流程改为普通顶部横条，滚动自然离开；两列/尺寸仅作可调整设计基线；小屏按 DOM 顺序单列。 | **P1-6** | 不再存在左侧全高流程列；横条非 sticky/不可收起；小屏无横向溢出或焦点遮挡；尺寸调整不阻塞 P0。 |
  | "重跑"措辞位置不当：<br>"重跑"这个措辞放在了最下面，那不是用户要翻半天才能翻到最底下去吗？这样也不对呀。 | “应用新词库重跑”藏在页面最下方详情高级折叠；同族动作还散在词库底部和任务表头，缺少按任务意图组织的统一入口。 | 首屏右侧建立“恢复与重试”区，集中所选失败、全部可恢复失败、重新成稿、仅重新入库；名称说明后果与 whisper 成本，详情仅保留上下文快捷按钮。 | **P0-3** | 首屏无需滚动即可看到统一入口；从页面加载到发起任一恢复动作不超过 2 次点击（确认弹窗不计）；全文不再出现三个互不关联的批量重跑入口；每个动作都显示作用范围和是否重新转写。 |
  | 反馈 A：查询失败原因后页面被长提示撑满，不能缩小/关闭 | `copyText(t)` 成功后把完整 16 条文本拼进 `say("已复制："+t)`；`#msg` 无截断、关闭或超时 | 复制仅显示短句；长文本只进可关闭面板/抽屉，支持关闭按钮、Esc、遮罩与焦点返回 | **P0-3** | 复制 16 条后 `#msg` 不含正文且页面高度不突增；短提示自动消失/可关；长面板四种退出方式可用 |
  | 反馈 B：16 条页面异常的真实原因需要查清 | 已证明 16 条原登记路径当前无文件，并在替代路径找到 16/16 身份匹配文件；页面 FAIL 与 DB `QUEUED` 的快照时间未对齐，具体显示因果仍未验证 | 用双语义显示：仍列为“未完成/受阻”，但不计入“可自动重试失败”；提供“确认替代路径并重新诊断/保持暂不转录” | **P0-1** | 真实矩阵复现原路径不在位=16、替代身份 MATCH=16；页面同时显示未完成/受阻=16、可自动重试失败=0；批量自动恢复选集排除 16 条 |
  | 反馈 C：产品改名“懒得笔记” | 现有页面与文档仍使用 V2O 控制台品牌 | 页面 title/h1/流程标识与中英文 README 标题改名；兼容标识不动 | **P1-7** | 四处可见名称与建议副标题一致；仓库名、v2o-* 键、日志前缀、数据目录名逐项保持不变 |
- Out of Scope：
  - v2 不增加 Windows、Intel Mac、Linux、iOS 或 Android 支持。
  - v2 不更换 `mlx-whisper`、不引入云转写、不增加云 API Key、不把 whisper.cpp 设为第二引擎；引擎替换另开产品计划。
  - v2 不增加说话人识别、实时字幕、录音、翻译、全文搜索、音频播放器、视频编辑或人工校对工作台。
  - v2 不直接集成 Notion、Apple Notes、Logseq 等其他笔记软件；按 HD-4=A 继续输出 Markdown，并保留 Obsidian 路径工作流。
  - v2 不自动修复系统环境、不自动安装 `ffmpeg`/Python/模型、不删除失败源文件、不清理用户真实数据。
  - v2 不承诺词级准确率、CER、幻觉率或未来所有失败都能自动恢复；当前 16 条只能诚实显示为“原登记路径无文件；已发现替代路径，待确认”，在用户确认重新绑定并完成新诊断前不得自动恢复。
  - v2 不提供任意进行中 whisper 任务的强制取消；先提供耗时与安全离开页面提示。取消需要证明不会留下半状态后再另立项。
  - 22 条 P3 中明确标记“不做”的项目不进入本版；不得为了清空 backlog 扩张范围。
- Technical Approach：
  - 保持本地 Mac 形态：`app/server.py` 的 stdlib HTTP 服务 + `app/index.html` 单页控制台 + `src/stage1..12` 现有引擎，不引入前端框架或新常驻服务。
  - 新增一个只读诊断层，从现有状态快照、processing_runs/sources、job manifest、receipts、verdict、产物存在性和只读文件身份检查推导诊断；原路径不在位时，先扫当前已挂载卷、常见替代根和可见云占位，以 basename/大小/mtime 缩小候选，必要时 SHA-256 定身份；未检查必须返回 UNKNOWN。
  - 分类规则采用有版本的确定性表，例如 `diagnosis_version=v2-failure-taxonomy-1`，独立输出 `action_category/root_cause/stage`，并保留原始 code/state 与证据摘要。合成用例必须证明三轴不互相覆盖。
  - provenance 契约以 `diagnosis_snapshot_id/snapshot_time/page_snapshot_at/state_event_at/persisted_state_source` 对齐页面与 DB；只有同一时间窗、同一 run 且证据链完整时才下因果结论。时间未对齐时并列 `display_state/persisted_state`、标 `NOT_TIME_ALIGNED`，不用展示态覆盖 DB。
  - P0 阶段优先“运行时派生”，不做 DB schema 迁移；如性能实测证明每次派生过慢，再在 `data_root` 下增加可重建缓存。缓存绝不能成为唯一真源。
  - 批量恢复只复用已通过 FR-4 六项契约门的单条重试、重跑、入库与 No-Clobber 路径；新增编排层不复制 Stage1..12 逻辑，未过门的旧入口不得接入。
  - dry-run 与 execute 使用同一规划函数；execute 必须携带诊断 snapshot、逐 run fingerprint 与 10 分钟 plan token，执行前复核，状态漂移时 409 且零执行。
  - 批量 job 持久记录原子写入 `data_root/data/recovery_jobs/<job_id>.json` 并作为唯一真源；内存仅作缓存。job 绑定 data_root、snapshot、token 摘要和逐项策略/终态，前端只渲染匹配项。
  - 轮询使用有限退避/连续失败阈值；页面刷新后恢复查看。服务重启后终态照常读取，未终态标 `INTERRUPTED`、不自动续跑，需重新诊断后创建新计划。
  - 所有文件写仍走既有原子写/No-Clobber 机制；测试夹具在调用任何 handler 前断言 data_root 位于系统 tmp 且不等于默认/真实数据目录。
  - 保留 `<html data-theme="light">` 首帧和既有一次性迁移，不引入 `prefers-color-scheme` 或跟随系统逻辑。
- Data / API：
  - 既有只读入口继续使用：`GET /api/status?data_root=&limit=`、`GET /api/start`、`GET /api/note?run_id=`；既有动作入口继续兼容：`POST /api/retry`、`POST /api/reapply`。
  - 计划新增 `GET /api/failures/diagnosis?data_root=<abs>`：返回 `ok / diagnosis_version / diagnosis_snapshot_id / generated_at / persisted_snapshot_at / page_snapshot_at / provenance_status / counts / categories[] / items[]`；`counts` 至少分开 `incomplete_or_blocked_total / auto_retryable_failure_count / source_location_review / alternate_identity_matches / unknown`；items 使用 FR-1 字段，不返回正文，data_root 对页面本机可用但不进入复制摘要。
  - 计划新增或扩展历史查询：`completed_limit=20&completed_cursor=`，返回 `completed_total/next_cursor`；cursor 为 `finished_at|updated_at + run_id` 排序键的签名，不用易漂移 offset。
  - 计划新增 `POST /api/failures/retry-plan`：请求含 `data_root / run_ids[] / diagnosis_snapshot_id`，仅 dry-run；返回逐项 fingerprint、selected/eligible/excluded/retranscribe/reuse/publish-only、ETA 未验证说明、plan token 与 expires_at。
  - 计划新增 `POST /api/failures/retry-batch`：请求含 `data_root / run_ids[] / plan_token / confirm:true`；返回 202、job_id 和初始计数。无 confirm、过期 token、状态漂移或跨 data_root 一律 400/409 人话失败。
  - 计划新增 `GET /api/failures/retry-batch/status?data_root=&job_id=`：返回 `state / total / done / recovered / still_failed / source_location_blocked / skipped / needs_human / interrupted / current / results[] / started_at / finished_at / error`。
  - 行动分类枚举：`SOURCE_LOCATION_REVIEW / PRECONDITION_BLOCKED / INPUT_MEDIA_INVALID / RETRYABLE_TRANSCRIPTION / REUSABLE_DERIVED_FAILURE / PUBLISH_BLOCKED / UNKNOWN`；技术根因与阶段分别使用 FR-2 独立枚举；重试策略枚举：`CONFIRM_ALTERNATE_THEN_REDIAGNOSE / BLOCK_UNTIL_FIXED / RETRANSCRIBE / REUSE_DERIVED / PUBLISH_ONLY / MANUAL_REVIEW`。
  - 数据最小化：不在日志/报告/复制摘要/错误响应中复制视频内容、完整转写正文、真实库文件内容、密钥或请求体；路径在本机 UI 可见，复制摘要只保留脱敏标签与目录尾段；按 HD-2=A 不提供完整绝对路径导出。
  - 不写用户真实视频目录；Obsidian 写入只发生在用户主动执行既有发布/入库路径时，并继续服从 No-Clobber。Phase2 QA 对真实目录和真实 Obsidian 库仍是只读。
- Key Assumptions：
  - **已验证事实**：当前真实 16 条的原登记路径 16/16 无文件，但在 `…/暂不转录视频/葫芦军师/` 找到 16/16 basename、大小、mtime、SHA-256 完全一致的替代文件；身份 UNKNOWN=0，但用户是否要重新绑定不可推断。当前应显示未完成/受阻=16、可自动重试失败=0；页面 FAIL 因果因快照未对齐仍为 UNKNOWN。
  - **待证事实**：现有 retry/reapply/publish 是否满足六项契约门；通过后才作为差异化恢复原语，不需要复制 Stage1..12。
  - **已决规格（HD-1=A）**：优先把 16 个失败处理明白并尽量恢复，高于一次性清完 22 条 P3。
  - 用户接受批量动作前多一步预览与确认，以换取不误重跑、不覆盖和耗时透明。
  - 成功 61 项在 v2 的失败恢复中应默认完全隔离；只有用户另行进入词库重跑功能时才处理成功项。
  - **已决规格（HD-6/7/8/9=A）**：完成首版默认 20、更早收起；隐藏状态写 localStorage 且历史可恢复；三层任务状态与监听脱钩；普通顶部横条、不 sticky、不收起。
  - 真实 whisper、长视频和 61 篇量级性能可能暴露新的时间/内存/阶段停滞问题，因此当前所有耗时数字均不得写死。
  - v2 仍只面向单机、单用户、单进程；多浏览器标签页可以查看，但同类批量写任务保持单例。
- Competitor / Research Summary：
  - **whisper.cpp（官方 GitHub，轻量核验，2026-09-13）**：官方 README 强调本地高性能 Whisper、Apple Silicon/Metal/Core ML 支持及多平台能力。启示是“本地、隐私、Apple Silicon 优化”已是基础能力，不足以单独构成差异；本项目应突出从文件夹监听到 Markdown/Obsidian、安全恢复失败的完整工作流。来源：<https://github.com/ggml-org/whisper.cpp>。
  - **MacWhisper（官方产品页，轻量核验，2026-09-13）**：页面列出本地转写、批量转写、Watch Folder、音视频格式、搜索编辑、Obsidian/自动化等较完整功能。启示是本项目不应在 v2 正面追逐播放器、字幕、搜索编辑等广功能，而应把“77 个批次失败如何诊断和安全恢复”做深。来源：<https://goodsnooze.gumroad.com/l/macwhisper>。
  - **Aiko（开发者官网，轻量核验，2026-09-13）**：页面强调设备端隐私、音视频转写、100 种语言和批量转写。启示同上：本地转写和批量输入是同类产品的常见卖点，失败恢复与 Obsidian No-Clobber 才是本项目更具体的价值。来源：<https://sindresorhus.com/aiko>。
  - **Obsidian（官方帮助，轻量核验，2026-09-13）**：官方存在“Import notes”入口，说明 Markdown/本地文件导入生态成熟；本项目继续产出 Markdown、减少对专有笔记 API 的依赖是合理方向。来源：<https://help.obsidian.md/import>。
  - **GitHub Actions（官方文档，轻量核验，2026-09-13）**：运行历史先展示近期记录，CLI `gh run list` 默认返回 10 条并支持 `--limit`，再进入单次运行查看 job/step 详情。可对照做法：首层限制近期数量，详情按需下钻，不把全部历史和全部步骤同时铺开。来源：<https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/viewing-workflow-run-history>。
  - **Todoist（官方帮助，轻量核验，2026-09-13）**：活动任务是默认工作面；已完成任务通过项目菜单单独查看，并支持显示/隐藏完成项。可对照做法：当前工作与完成历史分层，完成历史可回看但不持续占据主列表。来源：<https://www.todoist.com/help/todoist/get-started/get-started-with-todoist-OgNNJR>、<https://www.todoist.com/help/todoist/features/introduction-to-filters-V98wIH>。
  - **Docker Desktop Builds（官方文档，轻量核验，2026-09-13）**：界面同时覆盖活动构建监控和完成历史；步骤可折叠，历史可按状态筛选，并提供删除构建历史入口。可对照做法：活动态、失败筛选、历史管理分区，破坏性历史删除放在明确管理入口。来源：<https://docs.docker.com/desktop/use-desktop/builds/>、<https://docs.docker.com/reference/cli/docker/buildx/history/ls/>。
  - **HandBrake Queue（官方文档，轻量核验，2026-09-13）**：队列窗口聚焦 pending jobs，常用的显示队列、编辑、移除和开始操作从工具栏或队列窗口可到达。可对照做法：耗时任务的当前队列与主动作保持近距离。来源：<https://handbrake.fr/docs/en/1.2.0/advanced/queue.html>。
  - 本轮未深度验证：上述产品当前 UI 的完整桌面截图、不同版本/平台差异、历史默认阈值、归档与物理删除的具体数据语义、可用性研究指标；也未验证各转写竞品的失败诊断能力、批量失败恢复策略、No-Clobber、定价、性能与用户口碑。以上只提炼公开交互模式，不作为“照抄竞品”或功能优越性结论；交 Research Reviewer 深度复核。
- Risks：
  - **误分类风险**：同一人话错误可能来自不同根因。缓解：优先 code/state/manifest 证据，分类输出置信依据；无法确定归 UNKNOWN，不自动重试。
  - **状态漂移风险**：用户诊断后又单条重试，批量计划可能过期。缓解：plan_token + 当前状态指纹，执行前逐条复核，变化项排除并提示刷新。
  - **重复与并发风险**：多标签页或连点可能重复排队。缓解：data_root + run_id 幂等键、后端单例/原子占位、前端校验 job_id。
  - **成本与时间风险**：当前 16 条在用户未确认替代路径前若误入“重试全部”，可能违背“暂不转录”的真实意图；未来真实转写失败耗时仍未知。缓解：`SOURCE_LOCATION_REVIEW` 在用户确认重新绑定、身份复核和新诊断前排除于批量自动重试；其他项 dry-run 明示 Whisper 调用数，不显示虚假 ETA。
  - **长视频风险**：长视频阶段进度、内存和恢复点未实测。缓解：P1 blocking 真机验证；未通过前保留“未验证”标签，不宣称稳定。
  - **数据安全风险**：错误的测试 data_root 或 handler 调用曾污染正式词库。缓解：所有自动化首行断言 tmp data_root，真实目录/Obsidian 库只读，QA 数据带 `QA-`/`T-` 标识并通过 UI 清理。
  - **No-Clobber 回归风险**：publish-only 或重跑可能触达已有笔记。缓解：所有策略复用现有 publish 判定；user-edited/任意字节差异一律跳过且覆盖写次数为 0。
  - **证据缺失风险**：老失败可能缺少结构化错误码，只剩历史文案。缓解：兼容规则明确版本，保留原文摘要；不为追求“100%已分类”而编造原因。
  - **服务重启风险**：现有任务态以内存为主。缓解：批量 job 持久文件为真源；重启后终态可读，未终态标 INTERRUPTED、不自动续跑。
  - **状态统一与 provenance 风险**：把监听系统态从任务态中拆出后，ACTIVE 当前阶段可能丢失，或用时间未对齐的页面 FAIL 覆盖 DB `QUEUED`。缓解：四层分开，每层带 snapshot/event 时间与来源；不一致时并列、告警、禁止自动恢复且不回写 DB。
  - **历史折叠性能风险**：只在前端隐藏 77 行仍会一次取 200 条，不能解决取数与 DOM 压力。缓解：后端/查询同时支持 current、failed、recent_completed、older_completed 计数与按需页，不只做 CSS 隐藏。
  - **“清空”误删风险**：用户把清空列表理解为整理界面，系统却删除数据或稿件。缓解：默认动作只归档/隐藏且可恢复；物理删除改名为“高级清理任务数据”，独立预览和确认，永不删除源视频/已发布笔记。
  - **范围膨胀风险**：22 条 P3、跨笔记软件、引擎替换会稀释“缺源校正 + 未来失败安全恢复”主线。缓解：按本计划优先级和 Human Gate 决策锁范围，Change C 才能重开产品方案。
  - **macOS 文件失败混因风险**：iCloud/受保护目录、外置或网络卷、POSIX/ACL、SIP、文件锁和媒体损坏可能呈现相似文案。缓解：保留原始错误层与卷/能力证据，探针只读或只写系统 tmp，冲突即 UNKNOWN。
  - **原子/并发失败风险**：DB 事务、rename、独占创建或两个 publish 竞争可能留下半状态。缓解：失败注入与两线程 canonical 竞争为 DoD；旧有效字节和历史事实不得改变。
  - **隐私泄漏风险**：错误响应或复制摘要可能带出绝对路径、正文或 token。缓解：D-22 以敏感夹具做反向扫描，零命中才通过。
- DoD：
  - **D-1 真实 16 行证据矩阵**：V1.3 只读证据已复现“原登记路径无文件=16、替代身份 MATCH=16、身份 UNKNOWN=0”。Phase2 诊断 API 必须在同一只读快照复现 `SOURCE_LOCATION_REVIEW=16`，且逐项输出 `alternate_path_checked/identity_match/mount_or_provider_checked/snapshot_time` 及 FR-1 全字段；页面时间未对齐时必须保留 `display_state=FAIL / persisted_state=QUEUED / provenance_status=NOT_TIME_ALIGNED / 因果=UNKNOWN`。页面同时显示未完成/受阻=16、可自动重试失败=0；用户未确认替代路径时自动恢复=0，真实目录和 vault 写次数=0。
  - **D-2 七类双轴规则可证**：合成用例覆盖七类行动类别，并分别断言 `action_category/root_cause/stage` 不互相覆盖。至少逐项覆盖路径不在原位、权限或沙盒、挂载或云占位、媒体不可读、转写瞬时异常、产物复用、发布权限/发布 No-Clobber 冲突；同一行更改用户行动不得改写已证 root_cause/stage，更改 root_cause 也不得偷换行动类。证据冲突与 UNKNOWN 必须可见；合成用例不得伪装成当前真实分布。
  - **D-3 诊断零副作用**：同输入重复诊断 snapshot/fingerprint 稳定；whisper_calls=0，DB/manifest/receipt/源/产物/笔记写次数=0。
  - **D-4 dry-run 可复算**：汇总等于逐项；不执行；显示 token 过期时间、Whisper 调用数和 ETA=`未验证`。
  - **D-5 旧入口复用门与三策略真执行**：每个接入入口六项契约均有自动化证据；tmp 夹具分别跑 RETRANSCRIBE、REUSE_DERIVED、PUBLISH_ONLY，后两者 whisper_calls=0；任一门失败则该入口不得接入。
  - **D-6 幂等/并发/漂移**：同 token 连点与两线程只有一个新 job；重复返回既有 job 或 409；过期、跨目录、fingerprint 漂移均 409 且零执行。
  - **D-7 No-Clobber 分级**：逐层验证源视频只读、旧 Raw/Norm/Render 不变、已发布/用户编辑 Markdown 字节不变、历史 DB 事实不删改；缺失 vault 不创建。
  - **D-8 成功项隔离与受阻项双语义**：正常 UI 与恶意请求两路均排除 61 个成功项和 16 个 `SOURCE_LOCATION_REVIEW` 自动恢复项；但后 16 条必须仍在“未完成/受阻”区可见、有独立色与下一步。断言 `incomplete_or_blocked_total=16`、`auto_retryable_failure_count=0`；批量恢复可选数=0 时不得生成 job，相关 DB/manifest/产物/笔记不变。
  - **D-9 job 真源与重启**：刷新后同 job 可续看；模拟服务重启后终态可读、运行中变 INTERRUPTED；总数等于逐项终态和，内存不得覆盖持久真源。
  - **D-10 可复现真实性能协议**：按 HD-5，记录设备型号/芯片/内存、macOS、Python、mlx-whisper/MLX、模型与 revision、语言、格式/时长、静音占比（能取则取）、冷/热缓存、顺序单并发、模型加载/转写/总耗时、峰值内存、阶段停留和调用数；结果 JSON/Markdown 均脱敏。至少 1 个短样本、1 个代表性长样本、61 篇规模 whisper=0 重跑。第三方 benchmark 禁止用作本机 ETA。
  - **D-11 UI 与主题**：默认浅色不回退；诊断、预览和汇总在桌面/窄屏可读。
  - **D-12 API 与错误信息安全**：空/坏 JSON、未知/重复 run_id、坏/过期 token、跨目录、非布尔 confirm、坏库/缺表均结构化失败；错误响应与复制摘要不含真实绝对路径、正文、密钥或请求体。
  - **D-13 回归门**：现有自测、Python 静态检查、handler/HTTP、前端 DOM、No-Clobber 与 Stage1..12 相关子集通过；code-reviewer、qa、supervisor 独立 PASS。
  - **D-14 数据边界与 tmp 复制审计**：任何 handler 测试先断言 data_root 在系统 tmp 且非真实/默认目录；代表视频仅从真实源只读复制到新建外置 tmp，记录脱敏来源标识、目标路径摘要、源/副本 hash、起止时间、执行者和清理结果；真实目录/vault 零写，不请求或重启线上 8765。
  - **D-15 历史分页一致性**：77 条夹具下当前/失败全可达，完成默认 20；按 `finished_at|updated_at + run_id` cursor 展开 61 个成功项无重复遗漏；并列时间戳、刷新、归档/恢复后总数和页面计数一致。
  - **D-16 四层状态与 provenance 不变量**：同快照在未监听/监听/停止收尾三态逐 run 的 `persisted_state/display_state/worker_stage/recovery_eligibility`、主颜色、原因与统计不变，只允许独立监听条变化；实际 ACTIVE worker 事件可推进阶段与合法生命周期。另造时间对齐与未对齐两组数据：对齐组可证映射；未对齐组必须并列页面/DB 状态、时间、snapshot/diagnosis id、state event 来源，显示原因待验证、恢复资格 fail-closed，且持久状态字节不变。
  - **D-17 隐藏已完成安全性**：隐藏状态只写 localStorage，跨刷新/同浏览器服务重启保留。**使用不可逆的 data_root hash/摘要标识做分区；隐藏状态可逆；历史默认可恢复，可逐项或全部恢复；业务数据零删写。**验收时源、稿件、Raw/Norm/Render、manifest、DB 业务记录 hash/行数不变；高级清理仍独立 dry-run + 二次确认。
  - **D-18 普通流程条可访问性**：横条在普通文档流，滚动自然离开、不 sticky/不可收起；文字/图标双重表达状态，键盘可达但不截获或遮挡焦点，小屏无横向滚动。64px/两列/960px 为初始基线，可依据原型调整并记录理由。
  - **D-19 恢复入口归并**：核心恢复动作首屏两次操作内进入确认；名称区分三种后果，显示范围、资格和 Whisper 调用。
  - **D-20 原子写失败**：tmp 注入磁盘写、rename/exclusive-create 和 DB 事务失败；旧有效文件与历史事实不变，job 可复算为 FAILED/NEEDS_HUMAN，无半成功终态。
  - **D-21 并发 canonical 创建**：两线程 PUBLISH_ONLY 恰一方创建；另一方 skipped/needs_human，最终字节等于胜者且覆盖次数 0。
  - **D-22 脱敏反向检查**：带用户名、真实目录层级、特殊字符、疑似 token 和正文的夹具生成 UI/复制/错误响应；复制文本与响应经规则扫描零命中绝对路径、正文标记和密钥模式。
  - **D-23 查询/复制提示不撑屏**：对 16 条长文本执行成功/失败两路复制；成功时 `#msg` 只出现“已复制 16 条失败原因”等短句，不含正文、不自动打开长文面板，页面主布局高度不增长；复制失败只显短错误，正文不显示且面板不打开。用户主动打开的长文面板支持关闭按钮、Esc、遮罩关闭，关闭后焦点返回原触发控件；窄屏面板高度不超过 `min(70vh, 560px)` 且正文内部滚动；短提示 3 秒消失或可点击关闭。
  - **D-24 “懒得笔记”改名与兼容**：先产出全仓库用户可见 `V2O/v2o` 文案的静态盘点清单，覆盖 `app/index.html`、`README.md`、`README.en.md`、`docs/usage.md`、`docs/troubleshooting.md` 及 assets/资源 UI 文案；清单中每项标注“用户可见，应改”或“内部兼容，不改”并逐项验证。`<title>`、页眉 `<h1>`、流程标识和中英文用户文档显示“懒得笔记”及等义副标题；以改名前后静态 diff 逐项证明全部内部 `v2o-*` 键、`v2o-console:` 日志前缀、`v2o-console-data` 数据目录字符串、API/状态标识不变；GitHub 仓库名不变，不做仓库改名。
- P0 / P1 / P2：
  - P0（3 个，均为诊断恢复主线）：
    - **P0-1 源文件缺失校正与七类诊断**：V1.2 证据已确认当前 16 条全部 `SOURCE_MISSING`；实现须把它们从失败/可重试计数移到“源文件已不在”，给放回原路径或重新指定目录动作。未来异常按七类行动矩阵诊断；合成只覆盖规则分支。
    - **P0-2 差异化批量恢复闭环**：旧入口六项复用门、dry-run、snapshot/fingerprint/token、幂等持久 job、三策略、No-Clobber、刷新/重启与终态汇总。
    - **P0-3 核心状态、恢复入口与可退出反馈**：三层状态、监听脱钩、失败/缺源/受阻分流、统一恢复入口；修复查询/复制长文本撑屏，所有诊断展示均有明确退出方式；独立于视觉布局验收。
  - P1（blocking / 非 blocking 注明）：
    - **P1-1（blocking）真实规模与长视频验证**：按 D-10 完成短/长样本与 61 篇 whisper=0 基准。与主线关系：决定恢复成本和稳定性声明；工作量 M；不做则不得给 ETA 或宣称同规模稳定。
    - **P1-2（blocking）任务身份与 API 契约加固**：job/data_root 绑定、fingerprint/token、字段一致、候选版本锁、严格类型与部分更新安全。与主线关系：防 16 条恢复串任务/串目录；工作量 M；不做可能执行错误对象。
    - **P1-3（非 blocking）进度与批量语义修正**：无目标不画 100%、运行中参数锁定、零目标/坏文件提示、失败统计统一。与主线关系：恢复结果可信；工作量 S；不做会误导但不改变 No-Clobber。
    - **P1-4（非 blocking）脱敏摘要复制（HD-2=A）**：页面 + 一键复制，不做完整路径导出。与主线关系：携带 16 条诊断证据协作排错；工作量 S；不做会降低反馈效率，但页面诊断仍可用。
    - **P1-5（非 blocking）词库与候选易用性修整**：限分组标签、trim、空态、筛选计数、组头点击、全选初态。与主线关系：减少 REUSE_DERIVED 前后误选；工作量 S；不做不阻断失败恢复，不得升 P0。
    - **P1-6（非 blocking）视觉布局与历史管理**：普通顶部横条、响应式顺序、完成默认 20/cursor 历史、隐藏已完成。与主线关系：回应已确认的界面痛点；工作量 M；独立验收，不阻塞 P0-1/P0-2/P0-3 的事实与安全闭环。
    - **P1-7（non-blocking）产品改名“懒得笔记”**：改页面 title/h1/流程标识与 README 中英文标题，增加建议副标题；GitHub 仓库名、v2o-* 键、日志前缀和数据目录名不动。工作量 S；不做不影响恢复安全，但违反用户已拍板品牌规格。
  - P2：
    - **P2-1 取消能力预研**：仅形成安全点与半状态清单；v2 不交付强制取消。先在 UI 显示 elapsed 与“可离开页面稍后回来”。
    - **P2-2 批量诊断历史比较**：比较“重试前后根因是否变化”的多次快照；首版只保留本次 job 结果，历史趋势后置。
    - **P2-3 其他笔记软件适配调研**：只研究 Markdown 文件夹通用出口与适配成本，不在本版开发专有集成。
    - **P2-4 失败分类规则配置化**：首版规则写成集中、可测试的代码表即可；不做用户自定义分类规则 UI。

  **22 条 P3 处置表**

  | 来源项 | 处置 | 与异常诊断/恢复主线关系 | 工作量 | 若不做的影响 |
  |---|---|---|---|---|
  | RERUN-PROGRESS P3-1 `details` 结构不齐 | 做→P1-2 | 诊断/结果依赖稳定字段 | S | 部分失败无法统一解释 |
  | RERUN-PROGRESS P3-2 status 忽略 data_root | 做→P1-2 | 防跨目录串任务 | S | 可能展示/操作错误目录 |
  | RERUN-PROGRESS P3-3 job_id 前端不用 | 做→P1-2 | 防多标签页串 job | S | 进度可能归错任务 |
  | RERUN-PROGRESS P3-4 无候选画 100% | 做→P1-3 | 结果可信度 | S | 用户误认恢复成功 |
  | RERUN-PROGRESS P3-5 运行中可改参数 | 做→P1-3 | 固定本次执行语义 | S | 页面参数与实际任务不一致 |
  | RERUN-PROGRESS P3-6 无超时与取消 | 部分做→P1-3/P2 | 长任务可理解性 | S（elapsed/提示）；取消另评 | 不做提示会误判卡死；强制取消风险未知 |
  | CANDIDATE-APPLY P3-1 int 接受 bool/float | 做→P1-2 | 防错误候选索引 | S | 可能选错恢复输入 |
  | CANDIDATE-APPLY P3-2 failed 口径不一 | 做→P1-3 | 终态可复算 | S | 汇总不可信 |
  | CANDIDATE-APPLY P3-3 零目标文案不清 | 做→P1-3 | 明确无可恢复项 | S | 用户误以为按钮无效 |
  | CANDIDATE-APPLY P3-4 腐坏与缺失同显暂无 | 做→P1-3 | 区分需修复与空态 | S | 腐坏证据被隐藏 |
  | CANDIDATE-APPLY P3-5 GET/POST 索引漂移 | 做→P1-2 | 快照一致性 | M | 可能应用到错误候选 |
  | CANDIDATE-UI2 P3-1 rerun_old 类型不对称 | 做→P1-2 | 严格请求契约 | S | 非布尔值触发歧义行为 |
  | CANDIDATE-UI2 P3-2 二选一可双空 | 做→P1-3 | 保持安全默认 | S | 提交语义不确定 |
  | CANDIDATE-UI2 P3-3 组头勾选兼折叠 | 做→P1-5 | 降低重成稿误选 | S | 误操作概率上升 |
  | CANDIDATE-UI2 P3-4 全选初态不同步 | 做→P1-5 | 选择范围可信 | S | 页面所见与提交不一致 |
  | CANDIDATE-UI2 P3-5 部分 POST 回启未提交域 | 做→P1-2 | 防恢复旁路副作用 | M | 可能修改未授权设置 |
  | POLL-FIX P3-1 裸 refresh 多请求 | 不做 | 与 16 条安全恢复无直接关系 | S | 仅额外低频请求，结果语义不变 |
  | POLL-FIX P3-2 自动轮询不刷候选 | 不做 | 当前无外部候选写入器 | M | 极短暂 stale，可手动/apply 后刷新 |
  | VOCAB-FOLD P3-1 来源标签不一 | 做→P1-5 | 减少 REUSE_DERIVED 选择误读 | S | 来源展示混乱 |
  | VOCAB-FOLD P3-2 未 trim | 做→P1-5 | 防分组误判 | S | 同类词条分错组 |
  | VOCAB-FOLD P3-3 空库重复文案 | 做→P1-5 | 降低诊断页旁支噪音 | S | 空态冗余，不影响恢复安全 |
  | VOCAB-FOLD P3-4 总数/过滤数不清 | 做→P1-5 | 选择范围透明 | S | 用户误读将应用数量 |

  工作量口径：S=单一现有模块内、无需数据迁移；M=跨前后端契约或并发/版本测试。仅用于范围控制，不是工时承诺。

- Human Decisions Needed（九项均已决，不再提问）：
  - **HD-1=A 已决**：先解决 16 条页面异常；V1.2 已校正为 SOURCE_MISSING，P3 仅按本表分流。
  - **HD-2=A 已决**：页面可看 + 一键复制脱敏摘要；不导出完整路径。
  - **HD-3=A 已决**：只自动恢复规则确定且安全的类别；环境/媒体/未知留人工。
  - **HD-4=A 已决**：Markdown + Obsidian，不加其他笔记软件专有适配。
  - **HD-5=A 已决**：真实 16 条只读；少量代表视频复制到外置 tmp 验证；真实视频目录和 vault 零写。
  - **HD-6=A 已决**：完成默认 20，更早默认收起，总数/展开常显；20 是首版默认参数，可由后续 Change Request 调整。
  - **HD-7=A 已决**：隐藏状态只写浏览器 localStorage，按 data_root 摘要隔离，跨刷新/同浏览器服务重启保留；历史默认可恢复，业务数据零删写。
  - **HD-8=A 已决**：持久生命周期/当前 worker 阶段/恢复资格三层显示；监听状态独立，不改同快照 run 状态文字、颜色、计数和资格。
  - **HD-9=A 已决**：普通顶部横条，滚动自然离开；不 sticky、不收起；小屏无横向溢出、不得遮挡焦点。
  - 未决的人类决策：**0**。真实证据与工程验证是执行门，不转嫁为新 HD。

- Research Review Required Fixes 处置（第 1 轮）：
  1. **已改**：FR-1/FR-2/FR-4、D-1/D-2 增加证据优先级、冲突、置信度、UNKNOWN 与真实 16 行矩阵。
  2. **已改**：P0-1、D-1/D-2 改为真实 16 条逐条可追溯，合成仅覆盖分支。
  3. **已改**：FR-4、D-5/D-20/D-21 明确策略前置、读写、迁移、失败、重复提交及旧入口六项复用门。
  4. **已改**：原 P0-3 拆为 P0-3 核心状态/恢复可用性与 P1-6 视觉布局/历史管理，独立验收；尺寸降为可调整基线。
  5. **已改**：FR-12/D-15 将 20 定为首版默认参数，补 cursor API、排序键、并列规则、归档/刷新一致性。
  6. **已改**：FR-13/D-16 写明生命周期、worker 阶段、恢复资格三层契约及监听/worker 可变边界。
  7. **已改**：FR-5/FR-6、D-4/D-6/D-9 固化 snapshot、fingerprint、10 分钟 token、漂移重算、部分成功、重启和持久 job 真源。
  8. **已改**：FR-7、D-7/D-8/D-17/D-20/D-21 明确五类 No-Clobber 保护与原子/并发验收。
  9. **已改**：D-10/P1-1 增加完整可复现实验协议，禁止第三方 benchmark 作为本机 ETA。
  10. **已改**：FR-3、D-12/D-14/D-22 增加复制/错误响应脱敏和外置 tmp 来源、目标、hash、清理证明。
  11. **已改**：P1-1～P1-7 与 22 条 P3 表逐项补主线关系、S/M 工作量和不做影响；删除无证据的“低成本”措辞。
  12. **已改**：HD-1～HD-9 全部标为已决；HD-6～HD-9 的持久化、恢复、三层状态、普通流程条和可访问性均转为规格。
  - 处置汇总：**改 12 条，反驳 0 条**。

- Readiness Score（Plan Readiness Score / 计划成熟度，满分 100）：
  - 产品目标与用户需求（20）：**20/20**。较 V1.1 不变：九项 HD 已决；V1.2 又纳入查询撑屏、真实缺源分流和“懒得笔记”改名三条明确反馈。
  - 核心方案完整性（20）：**18/20**。较 V1.1 +1：16 条从笼统失败校正为 SOURCE_MISSING，补独立统计/动作、可退出反馈和改名兼容边界；旧入口副作用与 UI 原型仍未验证。
  - 外部事实与竞品验证（20）：**16/20**。较 V1.1 不变：13 条外部来源仍有效；本轮新增的是本机真实证据，不把本地核验冒充外部竞品验证。
  - 技术可行性（15）：**12/15**。较 V1.1 +1：24 个真实 run、16 个缺源与 8 个 RENDER_ONLY 旁证证明缺源分类可从 DB+磁盘只读推导；持久 job、cursor、旧入口六项门仍无实现原型。
  - 风险与异常场景（10）：**9/10**。较 V1.1 不变：新增“缺源误重试”和长提示撑屏风险及验收；取消安全点仍未研究。
  - 开发范围与 DoD（10）：**9/10**。较 V1.1 不变：新增 P1-7 与 D-23/D-24，但均有明确兼容边界；Phase2 实际工作量仍待验证。
  - 未决问题（5）：**5/5**。较 V1.1 不变：用户决策均已闭合；剩余均为工程验证门。
  - 合计：**89/100**
  - Gate（进 Human Review 条件）：Readiness >= 90 AND P0 = 0 AND blocking P1 = 0 AND 关键事实已验证 AND 核心假设已合理验证
  - 当前 Gate 判断：**未达到，PLAN_GATE=IN_PROGRESS**。真实 16 行矩阵已完成，但旧入口六项门、本机性能、查询面板与整体 UI 原型仍未执行；不得为凑 90 把规格完整当成事实已验证。
- Research Review Round（第几轮/Reviewer 结论摘要）：`第1轮（FAIL，12条已修）；第2轮待复审（V1.2）`
- PLAN_GATE：（IN_PROGRESS / READY_FOR_HUMAN_REVIEW / APPROVED）`IN_PROGRESS`

- 本轮真实验证记录：
  - 只读样本：**24 个 `葫芦军师` run**；其中 16 个缺源、8 个源存在。16 行缺源矩阵已实际建立；8 个存在源的对应 manifest 末 receipt 均为 `RENDER_ONLY`，构成交叉旁证。SQLite/磁盘命令单次墙钟均小于 1 秒。
  - 真源校正：根级 `v2o.db` 为 0 字节、无表；实际状态库是 `data/state.db`（约 2.97 MB）。库中 24 条 raw state 均为 source=`ACTIVE`、run=`QUEUED`，说明页面“失败”是运行时缺源映射，不是 DB 中已记录的转写失败。
  - 视频复制：**0 条**；Whisper：**0 次、0 分钟**。原因：16 条代表对象的源文件本身不存在，无法复制，也无需用 Whisper 证明缺源；8 个现存成功视频与本轮缺源分类无关，复制/重转只会扩大真实数据接触面。
  - 未跑：短/长视频性能、61 篇 whisper=0 重跑、旧入口六项契约和 UI 实点。原因：分别属于 D-10、D-5 与 D-23 的 Phase2 验证；本轮禁止请求/重启线上 8765，且没有为缺源结论运行 Whisper 的必要。
