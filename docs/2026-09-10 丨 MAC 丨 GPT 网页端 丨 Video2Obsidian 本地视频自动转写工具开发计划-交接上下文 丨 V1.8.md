# Video2Obsidian 本地视频自动转写工具开发计划

> 版本：V1.8  
> 日期：2026-09-10  
> 平台：macOS / Apple Silicon  
> 目标设备：Mac mini M4 / 24GB RAM  
> Architecture Specification：FROZEN  
> Implementation：NOT STARTED  
> 下一阶段：Stage 0 Technical Benchmark

---

# V1.8 最终冻结验证摘要

本轮只做最后一次**语义与治理收口**。

不新增产品功能，不新增数据库类型，不新增服务，不更换模型，不增加技术栈，也不重新设计已经审查通过的核心安全机制。

本轮完成四项一致性整改：

1. **Architecture Specification Freeze Gate 与 Implementation Acceptance Gate 完全分离**  
   架构规范是否定义完成，与代码是否真实实现并通过测试，不再使用同一套勾选项表达。

2. **Processing Run 语义统一**  
   `processing_runs` 正式定义为：**一次以 ASR 为核心的端到端 Initial Ingestion Run**。初次运行可以继续产生首个 Normalization Revision、Render Revision、首次 Canonical Publish 和首次 Archive；后续派生更新由各自 Revision 生命周期管理，不回滚已完成 Processing Run 的状态。

3. **AUTO Processing Run 数据库级去重**  
   同一个 `source_id + asr_profile_hash + creation_mode=AUTO` 只允许存在一个自动 Processing Run。Watchdog、Startup Scan、Reconciliation、程序重启以及 `NO_SPEECH_DETECTED` 长期留在输入目录都不得重复创建 Run。

4. **Rendered Artifact 与 Canonical Markdown Publish 正式分离**  
   新的 Normalization / Render Revision 可以产生新的内部 Rendered Artifact，但默认不得自动覆盖已经存在的 Obsidian Canonical Markdown。用户笔记安全优先。

Architecture Specification 已满足冻结条件：

```text
ARCHITECTURE APPROVED
V1.8 ARCHITECTURE FROZEN
READY FOR STAGE 0
```

但真实实现尚未开始，因此：

```text
Implementation Acceptance Gate
=
全部未完成
```

下一步必须直接进入：

```text
Mac mini M4
↓
Stage 0 Technical Benchmark
↓
Dependency / Model Revision Lock
↓
Stage 1 Implementation
↓
Fault Injection
↓
Golden Dataset
```

从 V1.8 开始：

```text
STOP ARCHITECTURE EXPANSION
```

不得再因为 VAD threshold、Chunk size、Overlap seconds、Prompt token budget、Word Timestamp 默认开关、Paragraph length、Worker count 重新开启架构设计。这些全部通过 Stage 0 Benchmark 与 Golden Dataset 决定。

---

# 1. 产品定义

## 1.1 项目名称

**Video2Obsidian**

## 1.2 一句话定义

> Video2Obsidian 是一个运行在 Apple Silicon Mac 上的零 API 成本、本地常驻视频知识入库工具：用户只需要把视频放入已经分类好的本地文件夹，系统自动完成本地 Whisper 转写、专业词增强、自然分段、目录镜像、Obsidian Markdown 安全写入和源视频安全归档。

## 1.3 用户最终操作

用户只需要：

```text
把视频放入对应专题 / 博主文件夹
```

例如：

```text
视频知识库/
├── AI/
│   ├── 博主A/
│   │   ├── DeepSeek V4 分析.mp4
│   │   └── AI Agent 趋势.mp4
│   └── 博主B/
│       └── Claude 新模型.mp4
├── 加密货币/
│   └── 博主C/
│       └── BTC 牛市周期.mp4
└── 投资/
    └── 红利/
        └── 红利基金分析.mp4
```

系统自动：

```text
发现 Candidate
↓
Stable File
↓
Logical Source
↓
AUTO Processing Run
↓
本地 Whisper
↓
Raw Artifact
↓
Normalization Revision
↓
Normalized Artifact
↓
Render Revision
↓
Rendered Markdown Artifact
↓
Initial Canonical Publish
↓
Safe Archive
```

Obsidian 最终：

```text
视频转写/
├── AI/
│   ├── 博主A/
│   │   ├── DeepSeek V4 分析.md
│   │   └── AI Agent 趋势.md
│   └── 博主B/
│       └── Claude 新模型.md
├── 加密货币/
│   └── 博主C/
│       └── BTC 牛市周期.md
└── 投资/
    └── 红利/
        └── 红利基金分析.md
```

---

# 2. 产品边界

## 2.1 V1.8 需要实现

- macOS Native；
- Python；
- FFmpeg；
- MLX Whisper；
- `large-v3-turbo`；
- SQLite；
- watchdog / FSEvents；
- Watch First / Scan Second / Reconcile Third；
- Stable File Detection；
- SourceCandidate；
- Logical Source；
- Processing Run；
- AUTO Run 去重；
- Strong SHA256 Source Provenance；
- Transcription 后强制 Strong Verify；
- Archive 前强制 Strong Verify；
- ASR / Normalization / Render Profile 分层；
- Raw Immutable；
- Job-scoped Artifact；
- Artifact PREPARED Receipt；
- SQLite Forward Repair；
- Absolute Timeline；
- PromptBuilder；
- Engine-aware Prompt Budget；
- Global / Topic / Creator 词库；
- Deterministic Corrections；
- Segment；
- Word Timestamp 能力；
- VAD 接口；
- Chunk / Overlap；
- Hallucination Classification；
- Natural Paragraph；
- Atomic No-Clobber Markdown；
- Output Ownership；
- Initial Canonical Publish；
- Derived Revision Safe Publish Policy；
- Same-FS Archive；
- Cross-FS Archive；
- O_EXCL Reservation Copy；
- Archive Level A / B / C；
- VolumeCapabilityProbe；
- Local Filesystem Only；
- Single Instance；
- Dependency / Model Pinning；
- LaunchAgent；
- `NO_SPEECH_DETECTED`；
- Golden Dataset；
- Fault Injection。

## 2.2 明确不做

```text
AI 总结
AI 改写
AI 润色
AI 校稿
LLM
云端 ASR
OpenAI / Claude / Gemini / DeepSeek API
百度 / 腾讯 / 阿里云转写
Redis
PostgreSQL
微服务
Docker
消息队列
分布式锁
多进程 Worker
复杂 UI
Obsidian 插件
SaaS
手机端
浏览器上传
RAG
Embedding
向量数据库
iCloud File Coordination
新模型
自动覆盖用户已存在 Obsidian 笔记
Reprocess UI
复杂历史版本 UI
```

---

# 3. 核心 Architecture Invariants

## 3.1 Discovery Delivery = At Least Once

同一实际视频可能同时被 Watchdog、Startup Scanner、Reconciliation 发现多次。系统必须接受重复 Delivery。

## 3.2 Logical Source Registration = Exactly Once

重复 Discovery 不得形成重复 Logical Source。最终通过 Candidate Partial UNIQUE、Strong Content Identity、Logical Source UNIQUE、UPSERT 收口。

## 3.3 AUTO Processing Run = Exactly Once Per Source + ASR Profile

对于 `creation_mode=AUTO`：

```text
同一个 source_id
+
同一个 asr_profile_hash
=
最多一个 AUTO Processing Run
```

重复 Discovery 返回已有 AUTO Run。

## 3.4 Candidate / Source / Processing Run / Revision 生命周期独立

严禁把 Candidate status、Source status、Processing Run status、Normalization Revision status、Render Revision status 混入一个状态字段。

## 3.5 Fast Metadata 不是 Provenance 证据

`device / inode / file id / size / mtime_ns` 只作为优化和变化检测信号。正式来源证明使用 Strong SHA256。

## 3.6 Transcription 后必须 Strong Verify

Whisper 完成后无条件重新计算 Source SHA256，只有 Hash 与 `source.content_identity` 相同，Raw 才允许 COMMIT。

## 3.7 Archive 前必须 Strong Verify

Archive 前无条件重新计算 Source SHA256，不允许只依赖 size / mtime。

## 3.8 Raw ASR Immutable

正式 Commit 的 Raw Artifact 不被后续 Correction / Normalization / Render 修改。

## 3.9 Derived Revision 不自动触发 ASR

```text
Correction Rules 改变
→ 新 Normalization Revision

Paragraph Formatter 改变
→ 新 Render Revision

不是：
→ 新 Whisper 调用
```

## 3.10 Rendered Artifact != Canonical Publish

新的 Render Revision 可以生成新的内部 Rendered Artifact，但不得默认覆盖已有 Canonical Markdown。

## 3.11 Unknown / User-edited Markdown Overwrite = 0

用户 Obsidian 文件安全优先级最高。

## 3.12 Archive Target Overwrite = 0

Archive 不覆盖任何未知目标文件。

## 3.13 Source 不确定时必须保留

任何冲突、Hash 不一致、Ownership 不明确、文件系统能力不足：`BLOCK + 保留 Source`。

## 3.14 Production Root = Local Filesystem Only

Input / Output / Data Root 如果属于 iCloud-managed root、network filesystem、remote mounted root，V1.8 进入 `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`。

---

# 4. 最终 Artifact Lineage

```text
SourceCandidate
↓
Logical Source
↓
Processing Run
↓
Raw Artifact
↓
Normalization Revision
↓
Normalized Artifact
↓
Render Revision
↓
Rendered Markdown Artifact
↓
Canonical Markdown Publish
```

Archive 是 Initial Ingestion Run 的最后安全动作。

---

# 5. SourceCandidate Lifecycle

```text
DISCOVERED
↓
WAITING_FOR_STABLE_FILE
↓
IDENTIFYING_SOURCE
↓
PROMOTED
```

旁路：

```text
MERGED
REJECTED
SOURCE_MISSING
```

Candidate 只负责 Discovery、Stable File、Provisional Identity、Strong Hash、Logical Source Promotion，不负责 ASR、Normalization、Render、Publish、Archive。

---

# 6. Logical Source Lifecycle

建议状态：

```text
ACTIVE
ARCHIVED
MISSING
```

至少保存：

```text
source_id
source_relative_path
path_identity_key
content_identity
logical_source_identity
current_path
current_location_type
source_size
source_mtime_ns
source_device_id
source_inode_or_file_id
status
first_seen_at
last_seen_at
archived_at
```

---

# 7. Source Archive 后的路径语义

成功 Archive 后：

```text
sources.current_path = 真实 Archive Path
sources.current_location_type = ARCHIVE
sources.status = ARCHIVED
```

不得继续假定 Source 永远位于 INPUT_ROOT。

未来如果创建新的 Processing Run，必须从 `sources.current_path` 解析真实 Source Location。V1.8 不实现手工 Reprocess UI，但数据模型不得阻塞未来重跑。

---

# 8. Processing Run 正式语义

V1.8 正式定义：

> **Processing Run = 一次以 ASR 为核心的端到端 Initial Ingestion Run。**

每个 Processing Run：

- 绑定一个 Logical Source；
- 绑定一个 `asr_profile_hash`；
- 包含一次 ASR Execution；
- 产生一个 Raw Artifact；
- 初次 Ingestion 可以继续自动创建首个 Normalization Revision；
- 可以继续自动创建首个 Render Revision；
- 可以继续执行首次 Canonical Markdown Publish；
- 可以继续执行首次 Archive；
- 最终进入 `COMPLETED`。

`processing_runs` 不是只到 Raw ASR 为止的 ASR-only Job。

---

# 9. Processing Run Lifecycle

只有 Logical Source 注册后才允许创建 Processing Run。

```text
QUEUED
↓
VERIFYING_SOURCE_FOR_TRANSCRIPTION
↓
PREPARING
↓
TRANSCRIBING
↓
VERIFYING_SOURCE_AFTER_TRANSCRIPTION
↓
COMMITTING_RAW_ASR
↓
NORMALIZING_INITIAL
↓
COMMITTING_NORMALIZED_INITIAL
↓
RENDERING_INITIAL
↓
PREPARING_INITIAL_PUBLISH
↓
COMMITTING_INITIAL_PUBLISH
↓
VALIDATING_INITIAL_PUBLISH
↓
READY_TO_ARCHIVE
↓
VERIFYING_SOURCE_FOR_ARCHIVE
↓
ARCHIVING
↓
COMPLETED
```

业务终态：

```text
COMPLETED
NO_SPEECH_DETECTED
FAILED_FINAL
```

可恢复：

```text
FAILED_RETRYABLE
```

Blocked：

```text
BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION
BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION
BLOCKED_SOURCE_CHANGED
BLOCKED_SOURCE_MISSING
BLOCKED_OUTPUT_EXISTS
BLOCKED_OUTPUT_CONFLICT
BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM
BLOCKED_ARCHIVE_EXISTS
BLOCKED_ARCHIVE_CONFLICT
BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM
BLOCKED_PERMISSION
BLOCKED_CONFIG
BLOCKED_UNSUPPORTED_ROOT_FOR_V1
```

---

# 10. Completed Processing Run 不得被派生 Revision 回滚

一旦 `processing_run.status = COMPLETED`，后续 Correction / Normalization / Render 变化不得把 Processing Run 重新设置成 `NORMALIZING` 或 `RENDERING`。

后续派生处理由：

```text
normalization_revisions.status
render_revisions.status
```

独立管理。

---

# 11. Normalization Revision Lifecycle

```text
PENDING
↓
NORMALIZING
↓
COMMITTING
↓
COMPLETED
```

旁路：

```text
FAILED_RETRYABLE
FAILED_FINAL
```

Normalization Revision 复用 Raw Artifact，不修改已完成 Processing Run 状态。

---

# 12. Render Revision Lifecycle

```text
PENDING
↓
RENDERING
↓
ARTIFACT_COMMITTING
↓
ARTIFACT_COMPLETED
↓
PUBLISH_EVALUATION
```

Initial Publish：

```text
PUBLISHING
↓
PUBLISHED
```

Subsequent Derived Revision 且 canonical 已存在：

```text
PENDING_PUBLISH
```

或：

```text
CANONICAL_OUTPUT_EXISTS
```

Canonical 保持不变。

---

# 13. AUTO Processing Run Identity

新增：

```text
auto_run_identity = source_id + asr_profile_hash
```

仅用于 `creation_mode=AUTO`。

---

# 14. Processing Run creation_mode

至少定义：

```text
AUTO
MANUAL_REPROCESS
```

V1.8 只实现 AUTO 自动流程。`MANUAL_REPROCESS` 只做未来数据模型预留，不实现 UI。

---

# 15. AUTO Run 数据库级约束

对于 AUTO，同一 `source_id + asr_profile_hash` 只能存在一个 Processing Run。

推荐 SQLite Partial UNIQUE：

```sql
CREATE UNIQUE INDEX ux_auto_processing_run
ON processing_runs(source_id, asr_profile_hash)
WHERE creation_mode = 'AUTO';
```

创建必须使用 UPSERT / Conflict-safe Insert，禁止依靠 `SELECT → 不存在 → INSERT` 作为唯一并发防线。

---

# 16. AUTO Run 重复发现行为

Watchdog、Startup Scan、Reconciliation 同时发现同一 Source：

```text
Logical Source = 1
AUTO Processing Run = 1
```

重复 Discovery 返回既有对象。

---

# 17. FAILED_RETRYABLE 行为

已有 AUTO Run 进入 `FAILED_RETRYABLE` 后，再次 Reconciliation 必须重试原 Run，不得建立第二个 AUTO Run。

---

# 18. NO_SPEECH_DETECTED 行为

AUTO Run 已进入 `NO_SPEECH_DETECTED` 后，即使视频继续留在 INPUT_ROOT，后续 Startup Scan、Watchdog Event、Periodic Reconciliation 都返回既有终态 Run，不得再次创建 AUTO Run。

---

# 19. SourceCandidate 与 AUTO Run 去重是两层约束

Candidate 去重防止同一时间重复 Discovery Candidate；AUTO Run 去重防止同一 Source + ASR Profile 被长期重复处理。二者不得混为一层。

---

# 20. Provisional Identity

Candidate 早期：

```text
path_identity_key + size + mtime_ns
```

仅对活跃 Candidate Partial UNIQUE。历史 Candidate 不继续占用 Provisional 唯一约束。

---

# 21. Strong Content Identity

Stable 后：

```text
content_identity = SHA256(source bytes)
```

---

# 22. Logical Source Identity

```text
logical_source_identity = path_identity_key + content_identity
```

同内容位于不同知识库路径仍是不同 Logical Source。

---

# 23. path_identity_key

真实 `source_relative_path` 必须保留原始中文、Unicode、大小写、空格、`丨`、括号。

不得 URL Encode、slugify、修改磁盘文件名，也不得假设 `NFC + casefold` 100% 等同于所有 macOS Volume 的比较语义。

Candidate 活跃期优先结合 `st_dev + st_ino / file id` 判断同一实际文件实体，并通过同 Volume Unicode / Case Fault Test 验证 Identity 行为。

---

# 24. Source Provenance：Transcription 前 Fast Verification

进入 `VERIFYING_SOURCE_FOR_TRANSCRIPTION` 后检查：

```text
device / inode / file id
size
mtime_ns
```

Fast Metadata 变化时重新 SHA256。

若 `current_hash != source.content_identity`：

```text
BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION
```

Fast Metadata 未变化可以继续进入 ASR，但 Fast Metadata 不是最终 Provenance Proof。

---

# 25. Source Provenance：Transcription 后 Mandatory Strong Verification

Whisper 完成后、正式 Raw Commit 前，无论 size / mtime 是否变化，都必须重新 SHA256。

只有：

```text
current_source_sha256 == logical_source.content_identity
```

才允许 `COMMITTING_RAW_ASR`。

否则：

```text
BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION
```

本次 ASR 不得正式 Commit、不得进入 Normalization、不得生成 Render、不得 Publish Markdown、不得 Archive。

可保存 diagnostic-only 数据，但不属于正式 Raw Artifact。

---

# 26. Archive 前 Mandatory Strong Verification

进入 `VERIFYING_SOURCE_FOR_ARCHIVE` 后必须重新计算 Source SHA256。

只有 `current_source_sha256 == source.content_identity` 才允许 Archive，否则进入 `BLOCKED_SOURCE_CHANGED`。

---

# 27. Profile 分层

取消单一 `processing_profile_hash`，正式拆成：

```text
asr_profile_hash
normalization_profile_hash
render_profile_hash
```

---

# 28. ASR Profile

只包含会影响 Raw ASR 的内容：

```text
engine
engine_version
model
model_revision
audio_preprocess_profile
VAD profile
chunking profile
language strategy
language
word timestamp mode
dictionary snapshot
prompt builder version
prompt profile
ASR decode parameters
```

ASR Profile 改变时可以产生新的 Processing Run。

---

# 29. Normalization Profile

包含：

```text
correction rules revision
hallucination classifier version
duplicate cleanup version
chunk merge normalization rules
mechanical cleanup version
quality threshold profile
```

变化时复用 Raw，创建新 Normalization Revision，不自动重新调用 Whisper。

---

# 30. Render Profile

包含：

```text
paragraph formatter version
paragraph parameters
H1 setting
Frontmatter setting
Markdown renderer version
```

变化时复用 Raw + 合适的 Normalized Artifact，创建新 Render Revision 与内部 Rendered Artifact，不重新调用 Whisper。

---

# 31. 数据库建议

建议表：

```text
discovery_candidates
sources
processing_runs
normalization_revisions
render_revisions
artifacts
publish_records
archive_commits
state_events
```

---

# 32. processing_runs

正式语义：一次以 ASR 为核心的端到端 Initial Ingestion Run。

至少：

```text
job_id
source_id
creation_mode
auto_run_identity
asr_profile_hash
engine
engine_version
model
model_revision
language_strategy
raw_artifact_id
initial_normalization_revision_id
initial_render_revision_id
initial_publish_record_id
status
retry_count
created_at
updated_at
completed_at
```

---

# 33. normalization_revisions

至少：

```text
normalization_revision_id
raw_artifact_id
normalization_profile_hash
normalized_artifact_id
status
created_at
completed_at
```

---

# 34. render_revisions

至少：

```text
render_revision_id
normalized_artifact_id
render_profile_hash
rendered_artifact_id
status
created_at
completed_at
```

---

# 35. publish_records

用于区分 Rendered Artifact 与 Canonical Publish。

至少：

```text
publish_record_id
render_revision_id
canonical_output_path
expected_hash
publish_mode
status
published_hash
created_at
published_at
```

建议状态：

```text
PENDING
PUBLISHED
PENDING_PUBLISH
CANONICAL_OUTPUT_EXISTS
BLOCKED_OUTPUT_EXISTS
BLOCKED_OUTPUT_CONFLICT
```

---

# 36. Artifact Namespace

继续 Job-scoped：

```text
data/jobs/<job_id>/
├── source.json
├── run.json
├── manifest.json
├── chunks/
├── raw/
│   └── raw.json
├── normalized/
│   └── <normalization_revision_id>.json
└── render/
    └── <render_revision_id>.md
```

内部 Rendered Artifact 可以有多个版本。Obsidian Canonical Markdown 不放 Data Root。

---

# 37. Artifact Two-Phase Commit

Raw / Normalized / internal Rendered Artifact 使用：

```text
PREPARE
↓
FILESYSTEM COMMIT
↓
RECEIPT COMMIT
```

---

# 38. PREPARE Phase

```text
写 artifact.tmp
↓
flush
↓
fsync(file)
↓
parse / schema validation
↓
计算 expected_artifact_hash
↓
SQLite artifacts 表写：
artifact_id
owner_id
artifact_type
expected_hash
temp_path
final_path
state = PREPARED
↓
COMMIT SQLite transaction
```

expected hash 必须在 Final Commit 前可靠持久化。

---

# 39. COMMIT Phase

```text
PREPARED Receipt 已持久化
↓
Atomic Commit tmp → internal final artifact
↓
fsync(parent)
↓
验证 final hash
↓
Manifest 写 COMMITTED Receipt
↓
SQLite artifact.state = COMMITTED
```

---

# 40. Artifact Recovery

PREPARED + Final Exists + Hash Match：Repair Forward，补写 Manifest COMMITTED 与 SQLite COMMITTED，不得重新跑 Whisper。

PREPARED + tmp Exists + Final Missing：验证 tmp 后继续 Commit。

Final Hash != Expected Hash：不得视为有效 Artifact。

---

# 41. Recovery Truth Model

```text
Valid Filesystem Artifact + Expected Hash
=
Artifact Truth
```

```text
PREPARED / COMMITTED Receipt
=
Commit Evidence
```

```text
Manifest
=
Commit Receipt + Lineage Metadata
```

```text
SQLite
=
Workflow State / Index
```

SQLite 落后时 Repair Forward。

---

# 42. Audio / VAD / Chunk / Timeline

继续保留 FFmpeg、VadEngine、ChunkPlanner、Absolute Timeline、Core Region Ownership、Overlap Dedup。

Chunk Merge 优先级：

```text
1. Core Region Ownership
2. Absolute Timestamp
3. Overlap Timestamp
4. Text Similarity
```

禁止整篇 fuzzy dedup。

---

# 43. Segment / Word Timestamp

必须保留 Relative + Absolute Timestamp。Word Timestamp 默认开关由 Stage 0 Benchmark 决定，但能力必须保留。

---

# 44. PromptBuilder

每个 Chunk 重新构造 Prompt：

```text
Topic / Creator
↓
Global + Topic + Creator
↓
Engine Prompt Capacity
↓
真实 Tokenizer 计数
↓
Creator > Topic > Global
↓
initial_prompt
```

---

# 45. Deterministic Corrections

只修高度确定专业词，不使用 LLM，不润色、不改写、不总结、不进行语义猜测。

---

# 46. NO_SPEECH_DETECTED

无讲话 / 纯音乐：

```text
Processing Run = NO_SPEECH_DETECTED
```

保留分析数据，不无限 Retry，不生成普通 Canonical Markdown，不自动 Archive。重复 Reconciliation 返回同一个 AUTO Processing Run。

---

# 47. Natural Paragraph

规则：

```text
Long Pause
>
Strong Punctuation
>
Target Length
>
Hard Max
```

具体阈值由 Benchmark / Golden Dataset 决定。

---

# 48. Canonical Markdown Path

```text
OBSIDIAN_OUTPUT_ROOT/<source_relative_path_without_ext>.md
```

例如：

```text
INPUT:
AI/博主A/DeepSeek V4 分析.mp4

CANONICAL:
AI/博主A/DeepSeek V4 分析.md
```

---

# 49. Initial Publish

首次 Initial Ingestion，如果 Canonical Markdown 不存在，允许 Atomic No-Clobber 创建。

```text
Rendered Artifact
↓
expected_output_hash 预持久化
↓
same-directory tmp
↓
flush / fsync
↓
Atomic No-Clobber Commit
↓
Final Hash Verify
↓
Publish Record = PUBLISHED
```

---

# 50. Subsequent Derived Revision Publish Policy

后续 Correction / Normalization / Paragraph / Render Profile 更新时，系统可以生成新的 Normalized Artifact 与 Rendered Artifact。

如果 canonical Markdown 已存在：

```text
默认不得覆盖
```

状态：

```text
PENDING_PUBLISH
或
CANONICAL_OUTPUT_EXISTS
```

Canonical Markdown 保持不变。

---

# 51. Derived Revision 不自动覆盖的原因

即使数据库能够证明旧 Canonical 最初由 Video2Obsidian 创建，也不能证明用户之后没有手工编辑。

因此正式冻结：

```text
New Rendered Artifact
!=
Automatic Canonical Replace
```

未来如需安全 Replace，必须单独设计显式 Publish/Replace Policy，不属于 V1.8。

---

# 52. Output Ownership

Initial Publish 继续记录 render_revision_id、rendered_artifact_id、publish_record_id、expected_output_hash、published_hash、SQLite、Manifest，主要用于 Crash Recovery、Initial Publish Ownership、Conflict 诊断，不授权 Subsequent Revision 自动覆盖。

---

# 53. Output Conflict

Initial Publish 时 Final 已存在：

- Ownership + Hash 可以证明是当前未完成 Initial Publish → Recovery Forward；
- 其他情况 → `BLOCKED_OUTPUT_EXISTS` 或 `BLOCKED_OUTPUT_CONFLICT`；
- 绝不覆盖。

---

# 54. VolumeCapabilityProbe

保留：

```text
filesystem_type
volume_id / st_dev
local_or_remote
case_sensitive
supports_atomic_rename
supports_exclusive_rename
supports_exclusive_create
supports_hardlink
supports_advisory_lock
```

---

# 55. Output Volume

如果不能提供可靠 Atomic No-Clobber：

```text
BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM
```

Output 不允许 Reservation Copy Fallback。

---

# 56. Archive Level A

支持 `RENAME_EXCL` 或等价 Atomic No-Clobber 时使用 Atomic No-Clobber Archive Finalization。

---

# 57. Archive Level B

如果不支持 Atomic Exclusive Rename，但支持 `O_CREAT | O_EXCL`，采用 Reservation Copy Mode：

```text
Strong Source Verify
↓
O_EXCL 独占创建 Final Archive Path
↓
持久化 Ownership / PREPARED
↓
copy
↓
flush / fsync
↓
SHA256
↓
ARCHIVE_COMMITTED Receipt
↓
再次 Strong Source Verify
↓
删除 Input Source
```

文件存在不代表 Archive 完成。

---

# 58. Archive Level C

如果没有可靠 Exclusive Create / No-Clobber：

```text
BLOCKED_UNSUPPORTED_ARCHIVE_FILESYSTEM
```

---

# 59. Archive 成功后更新 Source

```text
sources.current_path = archive_final_path
sources.current_location_type = ARCHIVE
sources.status = ARCHIVED
sources.archived_at = now
```

未来 Reprocess 必须解析 `sources.current_path`。

---

# 60. Default Permanent Delete

```yaml
archive:
  enabled: true
  auto_delete_days: never
```

V1.8 默认不永久删除 Archive。

---

# 61. Root Support

Production Supported：Local Filesystem。

Input / Output / Data Root 如为 iCloud-managed、network、remote mounted：

```text
BLOCKED_UNSUPPORTED_ROOT_FOR_V1
```

Archive Root 可以是符合 VolumeCapabilityProbe 要求的外置本地 Volume。

---

# 62. Runtime Startup Ordering

唯一正式顺序：

```text
Static Preflight
↓
Acquire Single Instance Lock
↓
Open SQLite
↓
Runtime / Volume Preflight
↓
Recovery Bootstrap
↓
Start Watcher
↓
Confirm Watcher Ready
↓
Startup Scan
↓
Initial Reconciliation
↓
Start Workers
↓
RUNNING
```

---

# 63. Static Preflight

只做 Config Parse、Config Schema、基本路径配置检查、明显非法拓扑检查。不得修改数据库、Repair Artifact、创建业务 Job、启动 Worker。

---

# 64. Single Instance

使用：

```text
fcntl.flock
LOCK_EX | LOCK_NB
```

第二实例直接退出。

---

# 65. Runtime / Volume Preflight

获得 Lock 后才允许 SQLite、Volume Probe、Dependency Verification、Artifact Recovery、Runtime Mutation。

---

# 66. Dependency / Model Pinning

锁定：Python、mlx、mlx-whisper、watchdog、onnxruntime、Silero、FFmpeg、Whisper model、Whisper model revision。

升级前必须重新 Benchmark、Golden Dataset、Regression。

---

# 67. Crash Guarantee Scope

必须恢复：process crash、kill -9、application restart、LaunchAgent restart、normal macOS reboot。

Best Effort：突然掉电、异常强制断电。

Out of Scope：物理硬盘故障、文件系统损坏、SSD 控制器故障、用户手工删除数据库 / Artifact。

---

# 68. Stage 0：Technical Benchmark

架构冻结后下一步直接执行 Mac mini M4 / 24GB 真机测试：

```text
MLX Whisper large-v3-turbo
5 / 30 / 60 分钟
Word Timestamp ON / OFF
FFmpeg Pipe / Temp
VAD
Chunk Size
Overlap
Prompt Budget
Model Load
RTF
Peak Memory
```

并冻结 Dependency Versions 与 Model Revision。

输出：

```text
TECHNICAL_BENCHMARK_REPORT.md
```

---

# 69. Implementation 顺序

```text
Stage 0
Technical Benchmark + Dependency / Model Revision Lock

Stage 1
Single Video + Source Provenance + Raw PREPARED / COMMIT

Stage 2
Candidate / Source / Processing Run + AUTO Run Partial UNIQUE + SQLite + Single Instance

Stage 3
Normalization Revision + Render Revision + Artifact Lineage

Stage 4
Initial Canonical Publish + Atomic No-Clobber + Output Ownership

Stage 5
Watch First + Startup Scan + Reconciliation

Stage 6
Obsidian Path Mirror + Unicode / Case Tests

Stage 7
Prompt + Vocabulary + Language Strategy

Stage 8
VAD + Chunk + Absolute Timeline

Stage 9
Normalization + Paragraph

Stage 10
Archive Level A / B / C + Source current_path update

Stage 11
LaunchAgent + Full Reliability + Fault Injection

Stage 12
Menu Bar（可选，核心稳定后）
```

---

# 70. Acceptance Cases

以下均是未来 Implementation Acceptance 标准。

## Case 1：Architecture / Implementation Gate 分离

Architecture Specification Gate 已定义；Implementation Acceptance Gate 不得提前勾选。

## Case 2：NO_SPEECH Reconciliation × 10

要求：Logical Source Count = 1，AUTO Processing Run Count = 1。

## Case 3：Triple Discovery Race

Watchdog + Startup Scan + Reconciliation 同时发现，要求 Logical Source Count = 1，AUTO Processing Run Count = 1。

## Case 4：Correction Rules 改变

要求 Whisper Calls 不增加、Raw Hash 不变、生成新 Normalization Revision、生成新 Render Artifact、Canonical Markdown 默认不覆盖。

## Case 5：Paragraph Formatter 改变

要求 Raw 不变、Normalized 可复用、生成新 Render Revision、Canonical Markdown 默认不覆盖。

## Case 6：Completed Processing Run 后派生 Revision

Processing Run 保持 COMPLETED，Revision 自己维护状态。

## Case 7：Archived Source Location

Archive 完成后 `sources.status = ARCHIVED` 且 `sources.current_path = Archive Path`。

## Case 8：Same Size + Same mtime + Different Bytes

Transcription 后强制 SHA256，Hash mismatch 时进入 `BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION`，Raw 不 Commit。

## Case 9：Raw Rename 后、Manifest 前 kill -9

SQLite 已 PREPARED，重启后通过 Final Hash == expected_hash Repair Forward，不得重新 Whisper。

## Case 10：Archive Reservation Copy Mid-kill

无 RENAME_EXCL、有 O_EXCL。Mid-copy kill 后 Source 完整保留；未知 Final 不删除；Ownership 明确时可安全恢复。

## Case 11：iCloud / Remote Root

必须 `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`，不能只 Warning。

## Case 12：Output Race

Publish 瞬间其他进程创建 canonical，要求用户文件不变、Overwrite = 0。

## Case 13：Historical Provisional Collision

历史 Candidate 完成后出现 same path + same size + same mtime + different bytes，必须进入 Strong Hash 并识别为新 Logical Source。

## Case 14：Unicode / Case

同一 Volume 真机验证 NFC、NFD、大小写、中文、空格、`丨`、括号，真实名字保持原样。

## Case 15：SQLite Lag Behind Artifact

Artifact 已 Commit、SQLite 落后，必须 Repair Forward，不重复昂贵 Stage。

---

# 71. V1.8 Architecture Specification Freeze Gate

本 Gate 只证明架构规则已经在计划中定义清楚，不代表代码已实现。

## Version Governance

- [x] 实际输出文件版本定义为 V1.8
- [x] 正文版本定义为 V1.8
- [x] Architecture Freeze Gate 使用 V1.8
- [x] Definition of Done 使用 V1.8
- [x] 最终冻结结论使用 V1.8

## Lifecycle Semantics

- [x] SourceCandidate Lifecycle 已定义
- [x] Logical Source Lifecycle 已定义
- [x] Processing Run 定义为端到端 Initial Ingestion Run
- [x] Processing Run 从 Source 注册后创建
- [x] Derived Revision 不回滚 Completed Processing Run
- [x] Normalization Revision 生命周期独立
- [x] Render Revision 生命周期独立

## AUTO Run Dedup

- [x] creation_mode 已定义
- [x] `auto_run_identity = source_id + asr_profile_hash` 已定义
- [x] AUTO Run 数据库级唯一语义已定义
- [x] Reconciliation 不重复创建 NO_SPEECH AUTO Run
- [x] FAILED_RETRYABLE 使用原 Run 重试

## Source Provenance

- [x] Transcription 前 Fast Verification 语义已定义
- [x] Transcription 后 Mandatory Strong SHA256 已定义
- [x] Archive 前 Mandatory Strong SHA256 已定义
- [x] Source Changed 时 Raw 不 Commit 规则已定义

## Profiles / Lineage

- [x] ASR Profile 已定义
- [x] Normalization Profile 已定义
- [x] Render Profile 已定义
- [x] Raw 复用语义已定义
- [x] Artifact Lineage 已定义

## Artifact Safety

- [x] PREPARED Receipt 已定义
- [x] expected hash 预持久化规则已定义
- [x] Filesystem Commit 规则已定义
- [x] COMMITTED Receipt 规则已定义
- [x] SQLite Forward Repair 规则已定义

## Render / Publish Separation

- [x] Rendered Artifact 与 Canonical Publish 已分离
- [x] Initial Publish No-Clobber 规则已定义
- [x] Subsequent Derived Revision 默认不覆盖 canonical 已定义
- [x] `PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS` 语义已定义
- [x] 用户编辑安全优先级已定义

## Archive

- [x] Level A Atomic No-Clobber 已定义
- [x] Level B O_EXCL Reservation Copy 已定义
- [x] Level C Unsupported Block 已定义
- [x] Archive 前 Strong Verify 已定义
- [x] Mid-copy Crash 保留 Source 已定义
- [x] Archive 后 `sources.current_path` 更新规则已定义

## Runtime / Root

- [x] Local Filesystem Only 已定义
- [x] iCloud / Remote Root Block 已定义
- [x] Startup Ordering 已统一
- [x] Single Instance 已定义
- [x] Dependency / Model Pinning 已定义
- [x] LaunchAgent 方向已定义

## Architecture Specification Freeze Result

```text
ARCHITECTURE APPROVED
V1.8 ARCHITECTURE FROZEN
READY FOR STAGE 0
```

---

# 72. V1.8 Implementation Acceptance Gate

本 Gate 只允许在真实代码、真机 Benchmark、Fault Injection 和 Golden Dataset 逐项通过后勾选。

**当前 Stage 0 尚未执行，因此以下全部保持 `[ ]`。**

## Stage 0 / Runtime

- [ ] Mac mini M4 Technical Benchmark PASS
- [ ] Dependency Versions Locked
- [ ] Whisper Model Revision Locked
- [ ] Word Timestamp Benchmark PASS
- [ ] VAD Benchmark PASS
- [ ] RTF / Peak Memory 数据完成

## Discovery / Identity

- [ ] Watch First / Scan / Reconcile implementation PASS
- [ ] Stable File Detection PASS
- [ ] Candidate Partial UNIQUE PASS
- [ ] Historical Provisional Collision PASS
- [ ] Logical Source Exactly Once PASS
- [ ] Triple Discovery Race PASS

## AUTO Processing Run

- [ ] AUTO Run Partial UNIQUE implementation PASS
- [ ] Watchdog + Scan + Reconciliation AUTO Run Count = 1
- [ ] NO_SPEECH Reconciliation × 10 AUTO Run Count = 1
- [ ] FAILED_RETRYABLE 重试原 Run PASS

## Source Provenance

- [ ] Transcription 前 Source Verification PASS
- [ ] Transcription 后 Mandatory SHA256 PASS
- [ ] Same size + same mtime + different bytes Test PASS
- [ ] Source Changed During Transcription Raw Commit = 0
- [ ] Archive 前 Mandatory SHA256 PASS

## Artifact

- [ ] Raw PREPARED Receipt implementation PASS
- [ ] Normalized PREPARED Receipt implementation PASS
- [ ] Raw Rename / Manifest Kill Recovery PASS
- [ ] Artifact Hash Validation PASS
- [ ] SQLite Forward Repair PASS
- [ ] Raw Immutable PASS

## Derived Revision

- [ ] Correction Rules Change 不重新调用 Whisper PASS
- [ ] Raw Hash 不变 PASS
- [ ] 新 Normalization Revision PASS
- [ ] Paragraph Formatter Change 只新建 Render Revision PASS
- [ ] Completed Processing Run 不被 Revision 回滚 PASS

## Canonical Publish

- [ ] Atomic No-Clobber implementation PASS
- [ ] Output Race Fault Injection PASS
- [ ] Unknown/User-edited Markdown Overwrite = 0
- [ ] Initial Publish PASS
- [ ] Subsequent Render Revision 不自动覆盖 Canonical PASS
- [ ] PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS PASS

## Archive

- [ ] Same-FS Archive PASS
- [ ] Cross-FS Level A PASS
- [ ] O_EXCL Reservation Copy PASS
- [ ] Cross-FS Mid-copy Kill PASS
- [ ] Archive Conflict PASS
- [ ] Unsupported Archive Filesystem Block PASS
- [ ] Archive 后 `sources.current_path` 更新 PASS
- [ ] Source Mis-delete = 0

## Root / LaunchAgent

- [ ] iCloud Root Block PASS
- [ ] Network / Remote Root Block PASS
- [ ] VolumeCapabilityProbe PASS
- [ ] Single Instance PASS
- [ ] LaunchAgent Cold Boot PASS
- [ ] Absolute Binary Paths PASS

## Batch / Quality

- [ ] 20 Video Batch PASS
- [ ] Lost Job Count = 0
- [ ] Duplicate Logical Source Count = 0
- [ ] Duplicate AUTO Run Count = 0
- [ ] Golden Dataset PASS
- [ ] CER / Term Accuracy 基线完成
- [ ] Hallucination / Duplicate 指标完成
- [ ] Fault Injection Suite PASS

---

# 73. Definition of Done V1.8

本节是**未来真实 Implementation 的完成标准**，当前并不表示已经完成。

V1.8 只有在以下要求全部真实实现并通过测试后，Implementation 才可视为完成：

1. 任意层级 MP4 自动发现；
2. 程序停止期间加入的视频启动后补回；
3. Watchdog 漏事件由 Reconciliation 补回；
4. Candidate Lifecycle 与 Processing Run Lifecycle 独立；
5. Historical Provisional Collision 不吞新 Source；
6. Logical Source Exactly Once；
7. 同一 Source + ASR Profile 的 AUTO Run Exactly Once；
8. `NO_SPEECH_DETECTED` 连续 Reconciliation 不新增 Run；
9. `FAILED_RETRYABLE` 重试原 Run；
10. Transcription 前 Source Verification 正常；
11. Transcription 后无条件 Strong SHA256；
12. Archive 前无条件 Strong SHA256；
13. Source 变化时正式 Raw 不 Commit；
14. Raw ASR Provenance 可证明；
15. ASR / Normalization / Render Profile 分层正确；
16. Correction Rules 更新不重新调用 Whisper；
17. Paragraph Formatter 更新不重新调用 Whisper；
18. Completed Processing Run 不被派生 Revision 状态回滚；
19. Raw Immutable；
20. Raw / Normalized Artifact PREPARED Receipt 正常；
21. Final Artifact + expected hash 可以 Forward Repair；
22. 半个 Artifact 永远不被视为成功；
23. MLX Whisper / large-v3-turbo 稳定运行；
24. Segment 正常；
25. Word Timestamp 能力正常；
26. Absolute Timeline 正确；
27. Prompt 每 Chunk 重建；
28. 专业词 correction 不改变语义；
29. `NO_SPEECH_DETECTED` 正常；
30. Rendered Artifact 与 Canonical Publish 完全分离；
31. Initial Canonical Publish 使用 Atomic No-Clobber；
32. Derived Revision 默认不覆盖已存在 Canonical Markdown；
33. Unknown/User-edited Markdown Overwrite = 0；
34. Canonical 路径完整镜像原目录；
35. 中文 / Unicode / Case / 空格 / `丨` 原样保留；
36. Output Volume 不支持安全语义时正确 Block；
37. Archive Level A 正常；
38. Archive Level B Reservation Copy 正常；
39. Archive Level C 正确 Block；
40. Cross-FS Mid-copy Crash 不丢 Source；
41. Archive Target Overwrite = 0；
42. Archive 前 Source Provenance 正确；
43. Archive 完成后 `sources.current_path` 指向真实 Archive；
44. iCloud / Remote Production Root 正确 Block；
45. SQLite / Artifact / Manifest Recovery 正确；
46. Single Instance 正常；
47. Dependency / Model Revision 锁定；
48. LaunchAgent Cold Boot 正常；
49. 20 Video Batch Lost Job = 0；
50. Duplicate Logical Source = 0；
51. Duplicate AUTO Processing Run = 0；
52. Source Mis-delete = 0；
53. Output Overwrite = 0；
54. Fault Injection 后无永久卡死；
55. Golden Dataset 通过；
56. 日常使用只剩“把视频放进目录”。

---

# 74. 最终优先级

任何实现冲突按以下优先级解决：

```text
1. 不覆盖用户 Markdown
2. 不误删 / 误归档 Source
3. Raw ASR 必须有可信 Source Provenance
4. 不漏任务
5. 不制造重复 Logical Source
6. 不制造重复 AUTO Processing Run
7. Crash 后可恢复
8. Derived Revision 不无故重新跑 ASR
9. Canonical Markdown 不被自动派生更新覆盖
10. 保持 Absolute Timeline
11. 转写准确
12. 自动化体验
13. 性能
14. UI
```

---

# 75. 最终冻结结论

本 V1.8 完成的是：

```text
Architecture Specification Freeze
```

而不是：

```text
Implementation Completion
```

当前可以正式声明：

```text
ARCHITECTURE APPROVED
V1.8 ARCHITECTURE FROZEN
READY FOR STAGE 0
```

同时必须明确：

```text
IMPLEMENTATION NOT YET ACCEPTED
IMPLEMENTATION ACCEPTANCE GATE = OPEN
```

下一步不再进行 Architecture Expansion，直接进入：

```text
Mac mini M4
↓
Stage 0 Technical Benchmark
↓
Dependency / Model Revision Lock
↓
Stage 1 Implementation
↓
Fault Injection
↓
Golden Dataset
↓
长期无人值守运行测试
```

参数型问题全部通过 Stage 0 / Golden Dataset 决定。

本 V1.8 作为 Video2Obsidian 的最终 Architecture Specification 基线。
