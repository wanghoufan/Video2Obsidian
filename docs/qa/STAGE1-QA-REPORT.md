# QA-REPORT｜Stage1 S1-T08 验收套件 + §72子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage1/`（ingest.py/verify.py/asr.py/post_verify.py/prepare.py/commit.py/recovery.py）+ S1-T01~T07输入产物（`/tmp/s1t05_demo/data/jobs/job_20260910T164213_c58d3cad` + `/tmp/s1t04_evidence` + `/tmp/s1t05_demo` + `/tmp/s1t07_evidence`）
- 计划：`docs/pm/STAGE1-PLAN.md` S1-T08（H4=至少5个断言、H1复用Stage0素材 lineage、H2外置测试目录、H3允许写盘kill-9、H5暂不清tmp）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage1子集9断言）+ Case 8/9/15
- QA执行目录（仓库外）：`/tmp/s1t08_qa/`（data_root + sources + s1t08_results.json，768K；仓库内零写盘除本报告）
- **结论：PASS（happy 1遍 + 异常5个全过；坏例只看exit码；During后Raw Commit=0；kill-9/SQLite落后均Repair Forward且Whisper不增加；结论只落本报告）**

## 1. 输入复核（S1-T01~T07产物未动）

- `job_20260910T164213_c58d3cad`：PREPARED（sqlite `PREPARED`，`raw.json.tmp`存在，expected `sha256:fca13dc4…bef4`），post_verify PASS（`COMMITTING_RAW_ASR`），输入完好。
- `/tmp/s1t04_evidence`：jobA happy PASS；jobB During BLOCK（size/mtime变+hash mismatch）；jobC Case8 BLOCK（changed `[]`但hash mismatch，SHA256裁决生效）。三者 `raw_commit_count=0`（BLOCK侧），diagnostic-only隔离存在。
- `/tmp/s1t07_evidence`：case9/case15均为 COMMITTED（sqlite+manifest+final hash一致，`whisper_calls.txt=1`）；negHash/tmpOnly中间态完好。本轮QA未改动这些目录。
- ASR冻结值（代码常量直读，未跑真实模型）：`mlx-community/whisper-large-v3-turbo @ a4aaeec0`、audio `temp`、word默认 `False`、nst `0.6`、worker `1`，与Stage0 §9一致。本轮转写用计数桩代替真实Whisper（见§3声明），冻结值走常量断言。

## 2. 5+1用例简表（坏例只看exit码）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit码 | Whisper计数 | Raw Commit计数 | final hash证据 |
|---|---|---|---|---|---|---|---|---|
| QA-HAPPY 端到端 | 新source `happy.bin`（64K确定性字节） | ingest→verify→桩ASR(1次)→post_verify→prepare→commit | 全0 + COMMITTED | 全0 + COMMITTED，immutable REFUSED且hash不变 | 0/0/0/0/0 | 1 | 1 | `sha256:f640ea75…4a2b3d5` == expected（prepare_receipt/sqlite/manifest三方一致） |
| QA-BEFORE 转写前改 | 新job后append 15B | verify CLI + gate_transcription计数桩 | BLOCK `BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION`，asr_calls=0 | BLOCK一致，桩零调用 | verify **2** | 0 | 0 | 无final（BLOCK无raw.json） |
| QA-DURING 转写中改 | T03读后append 31B（size+mtime变） | post_verify CLI + 试prepare | BLOCK `BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION`，prepare REFUSED，diagnostic-only 1件 | 一致 | post **2** / prepare **2** | 1（污染前旧字节1次，不计入commit） | 0 | 无formal raw；diagnostic `…_job_s1t08_during_20260910T170434_…DIAGNOSTIC-ONLY.json` |
| QA-CASE8 同size+mtime异bytes | 翻转1000B + `utime(ns)`恢复mtime | post_verify CLI | BLOCK（changed `[]`但hash mismatch） | BLOCK一致，`fstat_changed_before_after=[]`，`stored_after=[]`，`hash_match=false` | post **2** | 0 | 0 | 无formal raw（只看size/mtime的实现必FAIL，本实现PASS） |
| QA-CASE9 PREPARE后kill-9 | PREPARE后`rename(tmp→final)`，sqlite保持PREPARED，manifest保持SCAFFOLD | recovery CLI | exit 0，`prepared_final_exists_repair_forward`，Whisper不增，final==expected | 一致，manifest/SQLite→COMMITTED | recovery **0** | 1→1（recover_receipt `whisper_calls=0/asr_calls=0`） | 1 | `sha256:ffda12df…996d1e` == expected |
| QA-CASE15 SQLite落后 | 全COMMIT后`UPDATE artifacts SET state='PREPARED'` | recovery CLI | exit 0，Repair Forward，final不变，Whisper不增 | 一致，sqlite→COMMITTED，`prepared_final_exists_repair_forward` | recovery **0** | 1（recover `whisper_calls=0`） | 1 | before==after `sha256:8d68ae72…571c0c` |

Runner：`/tmp/s1t08_qa_run.py`（仓库外）→ `/tmp/s1t08_qa/s1t08_results.json`（6用例JSON已落盘，可复算）。

## 3. 每用例明细（前置/动作/期望四件套）

- QA-HAPPY：前置新source+空data_root；动作串行5 CLI；期望5×exit 0；实测ingest/verify/post/prepare/commit全0；Whisper桩1；formal commit 1；final==expected；`guarded_open_raw_for_write`抛`RawImmutableError`（REFUSED），复算hash不变；lineage `raw=raw/raw.json`且`grep diagnostic`零命中（exit 1=无命中已确认）。
- QA-BEFORE：前置ingest ok；动作先篡改后verify；期望exit 2+BLOCK码；实测exit 2，`gate_transcription`桩`asr_calls=0`、stub零调用；formal 0。
- QA-DURING：前置ingest+fstat.before快照；动作转写中append；期望post exit 2+BLOCK码+`commit_authorized=false`+`raw_commit_count=0`；实测一致；diagnostic-only 1件；随后prepare exit 2 REFUSED（`post_verify verdict 'BLOCK' != 'PASS'`）；formal 0。
- QA-CASE8：前置ingest并记录mtime_ns；动作同长异字节+`os.utime(ns)`还原；期望size/mtime双同但BLOCK；实测size同、mtime同、新sha≠content_identity、post exit 2、changed双`[]`、`hash_match=false`；formal 0。
- QA-CASE9：前置到PREPARED（expected `ffda12df…`）；动作rename+fsync(parent)模拟rename后manifest前kill；期望recovery exit 0+path `prepared_final_exists_repair_forward`；实测一致；whisper 1→1；manifest SCAFFOLD→COMMITTED；sqlite PREPARED→COMMITTED；final==expected。
- QA-CASE15：前置到COMMITTED（final `8d68ae72…`）；动作sqlite回拨PREPARED（manifest保持COMMITTED）；期望recovery exit 0+同path；实测一致；final before==after；sqlite回COMMITTED；recover `whisper_calls=0`。

## 4. §72子集门（Stage1 9断言逐项）

- [x] Transcription前 Verification PASS（HAPPY verify exit 0）
- [x] 转写后 Mandatory SHA256 PASS（HAPPY post exit 0，`hash_recomputed=true`，无条件重算）
- [x] Same size+mtime+b不同bytes PASS（CASE8 BLOCK，changed `[]`反证SHA256裁决）
- [x] During变化 Raw Commit=0（DURING + CASE8 formal均为0；diagnostic不计入）
- [x] Raw PREPARED Receipt PASS（HAPPY prepare exit 0，expected已持久化，三方一致）
- [x] Raw Rename/Manifest Kill Recovery PASS（CASE9 exit 0，Repair Forward）
- [x] Artifact Hash Validation PASS（HAPPY/CASE9/CASE15 final==expected；mismatch永不视为有效由CASE8/DURING反证）
- [x] SQLite Forward Repair PASS（CASE15 exit 0，落后方被修，不重跑ASR）
- [x] Raw Immutable PASS（HAPPY API guard REFUSED + hash不变 + 0444标记；`is_committed`任一证据即拒写）

## BUGS（照BUGS.template.md；本轮无P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 6/6 exit码符合预期，hash三方一致 | CLOSED | 无需builder修 | 详见 `/tmp/s1t08_qa/s1t08_results.json` |

## Fix Attempt Fingerprint

- Task ID: S1-T08 Stage1验收套件 + §72子集门（首轮QA执行）
- Root Cause Hypothesis: 不适用（PASS；6/6一次过，无返修）
- Approach: 仓库外`/tmp/s1t08_qa`新鲜6 job串行跑；CLI exit码为唯一坏例判据；Whisper用计数桩（真实模型不断言耗时路径）；final用sha256复算+sqlite/manifest三方对账；immutable用`guarded_open_raw_for_write`拒写+复算hash
- Files Changed: 仅新增本报告 `docs/qa/STAGE1-QA-REPORT.md`；业务代码零改；测试写盘只在`/tmp/s1t08_qa`（H2/H3许可内）
- Verification: ingest/verify/post/prepare/commit/recovery exit码全量记录（§2表）；`grep diagnostic`在happy job零命中；输入产物（s1t04/s1t05/s1t07）复查未动
- Failure Reason: 无FAIL项
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交supervisor/product-reviewer定，不卡本PASS）

- U-1 真实Whisper端到端未在本套件重跑（桩1次代替；冻结revision走常量断言+沿用Stage0基准；若要真音频路径需另起重跑轮）。
- U-2 非合成源：本套件用64K确定性`.bin`（H1 Stage0素材 lineage复用，非5–25分钟真实中文视频；provenance/commit门与音频内容无关，音频路径见U-1）。
- U-3 残留待清（H5暂不清）：`/tmp/s1t08_qa`（768K，本轮新增）+ 既有`/tmp/s1t04_evidence` + `/tmp/s1t05_demo` + `/tmp/s1t07_evidence` + `$TMPDIR` 1.8G，交neat-freak收尾。
- U-4 Runner脚本在仓库外（`/tmp/s1t08_qa_run.py`），未进`docs/qa`，复现找QA要路径（H2外置目录约束所致）。

---
目标：S1-T08验收（happy 1 + 异常5）｜剩 P0：无（QA口径PASS；P0-1~P0-9闭环判定以supervisor复检为准）｜下一步：交product-reviewer验 + supervisor复检（HANDOFF只记状态，不代写结论）。
