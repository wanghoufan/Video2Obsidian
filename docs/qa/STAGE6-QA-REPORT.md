# QA-REPORT｜Stage6 S6-T04 验收套件 + §72/§73 子集门（Video2Obsidian V1.8 §69）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`src/stage6/`（mirror.py/unicode_cases.py/__init__.py）+ `src/stage2/` 只读复用（store/candidate/source/runs/instance 持锁/AUTO UPSERT）+ `src/stage4/` 只读复用（volume_probe/publish/publish_commit/conflict）+ `src/stage1/` 只读复用（probe_volume/build_raw_content/validate 门）+ `src/stage3/` 只读复用（normalize/render 脚手架经公开 API，Verdict 语义不断链）+ `src/stage5/` 零调用（回归不断链）
- 计划：`docs/pm/STAGE6-PLAN.md` S6-T04（P0-1~P0-7；happy 1 遍 + 异常 8 个 + 三表 + current_path 列级 + 回归五行；外置合成 Input Root + 外置 Data Root + 外置诱饵 Output Root；合成副本，原片不动；真实长视频一律不测；坏例只看 exit 码；结论只落本报告）
- 基线：V1.8 §72 Implementation Acceptance Gate（Stage6 子集 9 断言：Atomic No-Clobber（mirror 嵌套仍 PASS）/ Output Race（mirror 路径抢建仍 BLOCK）/ Unknown-User-edited Overwrite=0 / Initial Publish（嵌套首发）/ Subsequent 不自动覆盖 / PENDING_PUBLISH / CANONICAL_OUTPUT_EXISTS / §73-34 / §73-35）+ §73-34（Canonical 完整镜像原目录）+ §73-35（中文/Unicode/Case/空格/`丨`原样保留）+ Case 14（NFC/NFD/大小写/同实体真机）
- QA 执行目录（仓库外）：`/tmp/s6qa/`（happy/pure/a1_nfc/a2_case/a3_hardlink/a4_caseblock/a_space/a7_useredit/a8_race/reg_s2/reg_s3/reg_s5/bad_* 各独立三 Root + 合成小 `.mp4` 副本 + `s6qa_results.json`）+ `/tmp/s6qa_run.py`（仓库外 Runner，`--bad escape/escape2/parentblock/race/useredit/caseblock` 六子进程取 exit 码）；仓库内零写盘除本报告
- **结论：PASS（happy 1 遍 + 异常 8 个全过 + 回归五行，97/97 断言双轮稳定，Runner exit 0；坏例只看 exit 码：escape/escape2/parentblock exit 1=MirrorEscape/MirrorBlockedError 未吞 + race/useredit/caseblock exit 2=BLOCK；三表：纯映射/矩阵库 0/0/0、集成库脚手架 1/1/0 且 archive 恒 0；current_path 列级零写；Whisper 恒 0；最大合成文件 ~1KB（≤32768 门）；结论只落本报告）**

## 1. 输入复核（src/stage6 落盘 3 文件，只读消费；builder 口径锁定沿用）

- `mirror.py`（S6-T01）：`resolve_canonical(input_root, output_root, abs_source_path)` 纯函数（`relpath` 相对合成 Input Root + `..`/盘外逃逸抛 `MirrorEscapeError` + `canonical=output_root/<rel_without_ext>.md` 仅末尾视频后缀 strip、`VIDEO_SUFFIXES` 复 Stage5 大小写不敏感语义 + 本函数零写盘）；`ensure_parent_dir(canonical)`（`mkdir -p` 语义，同名文件挡路抛 `MirrorBlockedError` 不删不覆盖）。QA 实测：三层 `A/B/C.mp4→A/B/C.md` + 大写 `.MP4→.md` + 中间点号不动（`my.clip.v2.mp4→my.clip.v2.md`）+ 中文嵌套 `AI/博主A/DeepSeek V4 分析.mp4→AI/博主A/DeepSeek V4 分析.md` + 越界双例抛错 + 与 Stage4 `canonical_path_for` 双算逐字节一致 + resolve 体 `open/write/mkdir/link` grep 零命中。
- `unicode_cases.py`（S6-T02）：`MATRIX` 11 项（中文/空格/`丨`/圆括号/方括号/NFC/NFD/大小写/`MP4` 大小写/中间点号）全合成生成；`assert_byte_preserved` 逐字节断言 helper（`path_identity_key==abspath` 逐字节 + `rel` 非空相对 + canonical 以 `stem+.md` 结尾）；`entity_key/is_same_entity`（`os.stat` 取 `st_dev+st_ino` 同实体判定）。模块内无归一化（`quote/slug/casefold/normalize("NFC"` grep 零命中）。
- `__init__.py`（S6-T03）：装配导出 + `publish_mirrored(input_root, output_root, abs_source_path, con, job_dir, render_revision_id, on_tmp_ready)`（`resolve_canonical` 算路径 → 越界复检 → `ensure_parent_dir` → 透传 `source_relative_path/output_root` 调 Stage4 `initial_publish`，不复制 No-Clobber/commit 实现；回包附 `source_relative_path/canonical_output_path/whisper_calls=0/asr_calls=0`）；`case_flag` 只读探针（`case_sensitive/volume_id` 只读复用，不重探针语义）。
- 上轮 builder 自验入口与对账：`/tmp/s6_selfcheck_run.py`（T01 纯映射 + T02 矩阵 + T03 集成 + regression-lite + STOP 门，66 cases 全 PASS，`TOTAL 66/66 exit=0`，QA 已复跑确认）；QA 以独立 Runner 97 断言覆盖（口径一致，exit 码对账一致；builder 摆动无——矩阵同 inode 双 Source、大小写同 inode 双 Source 均按 §23 字符串身份裁决，QA 按同一口径验收）。

## 2. 用例简表（坏例只看 exit 码；三表=norm/rend/arch；Whisper=whisper_calls）

| 用例 | 前置 | 动作 | 期望 | 实测 | exit 码 / Count | 三表 | Whisper |
|---|---|---|---|---|---|---|---|
| HAPPY 全链 | 新三 Root + 3 层 Unicode `AI/博主A/系列1/DeepSeek V4 分析.mp4` | discover→mirror→publish_mirrored | PUBLISHED + hash 一致 + 父目录自建 + §73-34/35 双断言 + 同内容重发 BLOCK | 一致（`pub_38368ece3683`，`0fbc5077…` 三方一致，`…/系列1/DeepSeek V4 分析.md` 落诱饵） | Runner exit 0；Source=1/Run=1 | 1/1/0（脚手架经 stage3 公开 API，stage6 无新增写） | 0 |
| A1 NFC vs NFD 不同 Source | 新库 + 同目录 NFC/NFD 同字节合成副本 | discover×2 | 不同 `path_identity_key` → 不同 Source=2（吞并即 FAIL） | 一致（2/2 PROMOTED，同 ino 仍 2 Logical，dup 0/0） | Count 2 | 0/0/0 | — |
| A2 大小写不同 Source | 新库 + 同目录 `Clip.mp4/clip.mp4` 同字节副本 | discover×2 | 不同 key → 不同 Source 各 1（合并即 FAIL） | 一致（1+1，同 ino 仍 2 Logical，dup 0/0） | Count 1+1 | 0/0/0 | — |
| A3 同实体硬链接不建新 Source | 新库 + `base.mp4` PROMOTED + `os.link` 硬链接 | helper + 同路径重 discover | `is_same_entity==True` + `st_ino` 相等举证 + 同路径重访 MERGED + Source 不变 | 一致（helper True，`st_ino` 相等，MERGED，1→1） | Count 1→1 | 0/0/0 | — |
| A4 大小写不敏感冲突 BLOCK | `Clip.mp4` 链首发 PUBLISHED（`case_sensitive==False` 只读） | `initial_publish(rel="clip.mp4")` | 第二个一律 BLOCK（EXISTS/CONFLICT），Overwrite=0 | 一致（BLOCK，诱饵字节不变，`writes=0`） | 子进程 exit **2** + in-process BLOCK | 1/1/0 | 0 |
| A5 越界逃逸 BLOCK | 新三 Root | `resolve_canonical(../escape)` + 盘外绝对路径 | `MirrorEscapeError` 双例 | 一致 | 子进程 `--bad escape/escape2` exit **1**×2 | — | — |
| A6 父目录文件挡路 BLOCK | 诱饵 out 内预置同名文件 `blocked` | `ensure_parent_dir(blocked/x.md)` | `MirrorBlockedError`，不删不覆盖 | 一致 | 子进程 `--bad parentblock` exit **1** | — | — |
| A7 用户编辑 BLOCK | HAPPY 链首发后诱饵 append 一字节 `U` | `publish_or_block` | `BLOCKED_OUTPUT_CONFLICT` + 诱饵保留用户字节 + Overwrite=0 | 一致（before==after edited，`writes=0`） | 子进程 exit **2** | 1/1/0 | 0 |
| A8 Output Race 抢建 BLOCK | 新链至 Rendered | `publish_mirrored(on_tmp_ready=抢建异字节)` | BLOCK + 抢建方字节不变 + Overwrite=0 | 一致（`BLOCKED_OUTPUT_CONFLICT`，`racer wins` 保留） | 子进程 exit **2** | 1/1/0 | — |
| A-空格/`丨`/括号 happy | 新库 + `空格 前后丨括号 (B) [C].mp4` + `my doc 丨 test [v1] (final).mp4` | discover×2 + 逐字节 | PROMOTED×2 + byte preserved×2 | 一致 | Count 2 | 0/0/0 | — |
| STOP 门 | 全仓 | grep 五重 + 最大文件 + 三 Root 前缀 | 无归一化/无 Whisper/无 force/无 Stage7+（`current_path` 等）+ 最大 ≤32768 + 全在 `/tmp/s6qa` | 一致（grep 空，max ~1KB，全前缀内） | — | arch 全库 0 | 0 |
| REG-S1 | 合成门 | `probe_volume` + 非法 Raw | ALLOW + 非法拒收 | 一致 | exit 0 | — | — |
| REG-S2 | 新 root | `startup` 5 步 + `discover` | 5 步逐字 + PROMOTED + Source=1 + Run=1 | 一致 | 1/1 exit 0 | 0 | — |
| REG-S3 | 新 root（合成 Raw 经门） | norm→render | COMPLETED→PUBLISH_EVALUATION + verdict 双值域 | 一致（PENDING_PUBLISH） | Norm=1/Render=1 | 0（arch） | 0 |
| REG-S4 | 旧库只读 | 查 `/tmp/s4qa` | `PUBLISHED` 行仍可查（行数≥1） | 一致（多候选首命中即过） | ≥1 | — | — |
| REG-S5 | 新三 Root | `run_startup` | order 11 逐字 + RUNNING 不断链 | 一致 | 11 步 exit 0 | 0 | — |

Runner：`/tmp/s6qa_run.py`（仓库外）→ `/tmp/s6qa/s6qa_results.json`（97 断言 JSON 已落盘，可复算；双轮 `TOTAL 97/97 FAILS=[] exit=0`）；坏例子进程：`--bad escape` exit **1**、`--bad escape2` exit **1**、`--bad parentblock` exit **1**、`--bad race` exit **2**、`--bad useredit` exit **2**、`--bad caseblock` exit **2**（判据只用 exit 码，不看打印）；最大合成文件 ~1KB（`Clip.mp4` 1042B，≤32768 门）。

## 3. 每用例明细（前置/动作/期望；Count 或 exit 码 + dup0 + 三表 + current_path + Whisper0 + 三 Root + 字节证据）

- HAPPY：前置新 `happy/{data_root,input,out}` + 3 层 Unicode 源 `AI/博主A/系列1/DeepSeek V4 分析.mp4`（合成 `S6-qa-happy` + 1K pad）；动作 `candidate.discover`（PROMOTED，`path_identity_key==abspath` 逐字节）→ `resolve_canonical`（`rel==nested`，`canonical==out/AI/博主A/系列1/DeepSeek V4 分析.md`，`assert_byte_preserved` 过，与 `pc.canonical_path_for` 双算一致）→ 脚手架经 `build_raw_content+validate` 门合成 COMMITTED Raw（不绕校验）+ Run 置 COMPLETED → `normalize.create_normalization_revision`（COMPLETED）→ `render.create_render_revision`（PUBLISH_EVALUATION，probe=缺席 canonical）→ `publish_mirrored`；期望 PUBLISHED（`pub_38368ece3683`，`expected==published==0fbc5077…`，`state_events≥3`）+ 父目录 `AI/博主A/系列1/` 自动建 + 诱饵 out 内落盘且前缀恒为诱饵 Root + 真实库零触碰 + `whisper/asr==0` + 三表 1/1/0（脚手架各 1，stage6 无新增写，archive 恒 0）+ sources 快照列级不变（`current_path/status/archived_at` 全同，`archived_at IS NULL`）+ dup 0/0 + 同内容重发 BLOCK（`BLOCKED_OUTPUT_EXISTS/CONFLICT`，字节不变，`writes=0`）；§73-34（`canonical` 完整镜像三层嵌套）+ §73-35（`博主A`/空格逐字节保留，`.md` 仅后缀替换）双断言过；实测全中。
- A1：前置新库 + 同目录 NFC（`café.mp4` U+00E9）/NFD（`café.mp4` e+U+0301）同字节副本（`nfc-nfd-same` + 256B pad）；动作先后 `discover`；期望双 PROMOTED + `abspath` 字符串不等 + `sources` 各 key 一行（2/2）+ dup 0/0 + 三表 0/0/0 + `archived_at` 全 NULL + `st_ino` 相等（同 Volume 同实体，仍 2 Logical——不得假设 `NFC+casefold` 等同 Volume 语义）+ 双 `assert_byte_preserved` 过；实测全中（`os.listdir` 仅 1 项、同 ino 仍 2 行，吞并项未触发）。
- A2：前置新库 + 同目录 `Clip.mp4/clip.mp4` 同字节副本（`clip-same` + 256B）；动作先后 `discover`；期望 PROMOTED/MERGED 皆合法（实测双 PROMOTED）+ 各 key 一行（1+1）+ dup 0/0 + 三表 0/0/0 + `st_ino` 相等（大小写不敏感卷同一实体，仍 2 Logical——合并即 FAIL）；实测全中。
- A3：前置新库 + `base.mp4`（`hardlink-base` + 256B）PROMOTED；动作 `os.link(base, base_link.mp4)` → `is_same_entity==True` + `entity_key` 相等（`st_dev+st_ino` 举证，`st_ino==stat().st_ino`）→ 同路径重 `discover(base)`；期望 MERGED + `sources` 1→1 + dup 0/0 + 三表 0/0/0；跨路径硬链接按 §22（`path|content`）另 mint 不同 Logical 系设计（本用例不以跨路径 discover 计不建新，仅以 helper + 同路径 MERGED 举证同实体识别）；实测全中。
- A4：前置 `Clip.mp4` 全链首发 PUBLISHED；动作只读 `case_flag(out)`（`case_sensitive==False`，`volume_id` 同卷）→ `pub.initial_publish(con, job_dir, rend, out, "clip.mp4")`（`Clip.md` vs `clip.md` 同拼写碰撞）；期望 BLOCK（EXISTS/CONFLICT，in-process dict + `--bad caseblock` 子进程 exit **2** 双证据）+ 诱饵字节不变 + `canonical_writes==0` + Overwrite=0 + `whisper==0` + 三表 1/1/0 + sources 列级不变；实测全中（`CASE_BLOCK dict`）。
- A5：前置新三 Root；动作 `resolve_canonical(ir, out, ir/../escape.mp4)` + `resolve_canonical(ir, out, /tmp/outside_root_file.mp4)`；期望双 `MirrorEscapeError`（子进程 `--bad escape/escape2` exit **1**×2，判据只用 exit 码）；实测全中。
- A6：前置诱饵 out 内 `blocked` 同名文件；动作 `ensure_parent_dir(blocked/x.md)`；期望 `MirrorBlockedError`（子进程 exit **1**，不删不覆盖，父仍为文件）；实测全中。
- A7：前置 HAPPY 链首发；动作 chmod 644 后 append `U` 模拟用户编辑 → `cf.publish_or_block`；期望 `BLOCKED_OUTPUT_CONFLICT`（in-process + `--bad useredit` exit **2** 双证据）+ `sha_before==after(edited)` + `canonical_writes==0` + Overwrite=0（用户 `U` 字节保留）；三表 1/1/0；实测全中。
- A8：前置新链至 Rendered；动作 hook 在 tmp fsync 后 Final commit 前抢建异字节 `racer wins`（fsync 落盘）→ `publish_mirrored(on_tmp_ready=hook)`；期望 `link(2)` EEXIST → `BLOCKED_OUTPUT_CONFLICT`（in-process raise + `--bad race` exit **2** 双证据）+ 抢建方字节保留（`racer wins`）+ Overwrite=0；实测全中。
- A-空格/`丨`/括号：前置新库；动作 `空格 前后丨括号 (B) [C].mp4` + `my doc 丨 test [v1] (final).mp4` 各 `discover`；期望双 PROMOTED + 双 byte preserved + Source=2 + 三表 0/0/0；任一字符类建不出 Source 即 FAIL 项未触发；实测全中。
- STOP：`grep quote|slug|casefold|normalize("NFC"` 空；`grep run_asr_single_file` 空；`grep -i force|overwrite|clobber` 空；`grep Prompt|Vocab|VAD|Chunk|Archive|LaunchAgent|Menu Bar|current_path` 空；`resolve_canonical` 体 `open/write/mkdir/link` 空；各库 `archive_commits` 全 0；canonical 全在 `/tmp/s6qa/<case>/out/` 内（仓库外，与真实视频目录/真实 Obsidian 库无交集，输出前缀断言逐用例过）；最大合成输入 ~1KB（1042B，≤32768 门，真实长视频零触碰）。
- 回归：REG-S1 `s1probe(/tmp)→ALLOW` + 非法 Raw 拒收；REG-S2 `instance.startup` 5 步逐字 + PROMOTED + Source=1 + AUTO Run=1（同对同 run 反证 UPSERT）；REG-S3 合成 Raw 经门 → `COMPLETED→PUBLISH_EVALUATION` + verdict `PENDING_PUBLISH`（双值域内）；REG-S4 `/tmp/s4qa` 旧库只读 `PUBLISHED≥1` 仍可查；REG-S5 `run_startup` order 11 逐字 + `running==True` + `shutdown` 幂等（Ready→Scan→Reconcile→RUNNING 不断链）；`src/stage1-5/` 本轮 QA 未触碰（目录非 git 仓库，`git diff` 口径 N/A，以五回归 PASS + QA 零改代证）。

## 4. §72/§73 子集门（Stage6 9 断言逐项）

- [x] Atomic No-Clobber implementation PASS（HAPPY `link(2)` + 三方 hash + A8 tmp-only 碰撞原地 BLOCK，rename 零落 Final 沿 Stage4）
- [x] Output Race Fault Injection PASS（A8 hook 抢建 → BLOCK + 抢建字节不变 + Overwrite=0，子进程 exit 2）
- [x] Unknown/User-edited Overwrite=0 PASS（A7 一字节编辑 → CONFLICT + 诱饵保留用户字节，子进程 exit 2）
- [x] Initial Publish PASS（HAPPY 嵌套 mirror 首发 `PENDING→PUBLISHING→PUBLISHED` + §35 九字段 + `published_at`）
- [x] Subsequent 不自动覆盖 PASS（HAPPY 同内容重发 BLOCK + A4 大小写碰撞 BLOCK，零写盘）
- [x] PENDING_PUBLISH PASS（HAPPY 缺席分支 + REG-S3 verdict 双值域）
- [x] CANONICAL_OUTPUT_EXISTS PASS（Stage3 verdict 语义沿用；Stage6 存在分支走 BLOCK，`initial_publish` 零写盘已验）
- [x] §73-34 PASS（Canonical 路径完整镜像原目录：`AI/博主A/系列1/DeepSeek V4 分析.mp4→AI/博主A/系列1/DeepSeek V4 分析.md` 三层逐级保留）
- [x] §73-35 PASS（中文/Unicode/Case/空格/`丨`原样保留：`博主A`/空格/`丨`/括号逐字节，`assert_byte_preserved` 全链过）
- [x] Case 14 PASS（NFC/NFD 不同 Source + 大小写不同 Source + 硬链接同实体 helper + 不敏感冲突 BLOCK + 空格`丨`括号 happy，真机同 Volume `st_ino` 举证）

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无 | — | 否 | 97/97 双轮 exit 0；坏例 exit 1/2 符合预期 | CLOSED | 无需 builder 修 | 详见 `/tmp/s6qa/s6qa_results.json` |

## Fix Attempt Fingerprint

- Task ID: S6-T04 Stage6 验收套件 + §72/§73 子集门 + Stage1~5 回归（首轮 QA 执行）
- Root Cause Hypothesis: 不适用（PASS；首轮 97/97 一遍过，无业务侧 FAIL）
- Approach: 仓库外 `/tmp/s6qa` 各用例独立三 Root + 合成确定性小 `.mp4`（最大 ~1KB，真实长视频零触碰）；纯映射以 `resolve_canonical` 双算 + Stage4 口径 parity 为判据；矩阵以中央库 `COUNT(*)`/行级 `abspath` 逐字节对比为判据；挡路/越界/竞态/编辑/大小写碰撞走子进程只看 exit 码；grep 五重 STOP 门；集成库三表以脚手架 1/1/0 + archive 恒 0 + sources 列级快照对比为判据；回归 S1 门/S2 链/S3 verdict/S4 旧库只读/S5 十一步
- Files Changed: 仅新增本报告 `docs/qa/STAGE6-QA-REPORT.md`；业务代码零改；测试写盘只在 `/tmp/s6qa`（H2 外置目录约束延续）；Runner `/tmp/s6qa_run.py` 在仓库外
- Verification: 双轮 `TOTAL 97/97 FAILS=[] exit=0`（`s6qa_results.json` 可复算）；`ESCAPE_EXIT=1` + `ESCAPE2_EXIT=1` + `PARENT_EXIT=1` + `RACE_EXIT=2` + `EDIT_EXIT=2` + `CASE_EXIT=2` 六坏例 exit 码已取；纯矩阵库三表全 0，集成库 1/1/0 且 archive 全库 0；诱饵用户/抢建字节三用例不变；`src/stage1-5/` 未触碰
- Failure Reason: 无 FAIL 项（业务侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（PLAN 已定：真实长视频一律不测直到产品完成；本套件最大合成文件 1042B）。
- U-2 Runner 在仓库外（`/tmp/s6qa_run.py` + `--bad` 六子进程），未进 `docs/qa`，复现找 QA 要路径（H2 外置目录约束延续；Stage1 U-4/Stage2 U-3/Stage3 U-3/Stage4 U-3/Stage5 U-2 同 Pattern）。
- U-3 残留待清：`/tmp/s6qa`（17 三 Root，本轮新增）+ `/tmp/s6self`（builder 自检 66 例）+ Stage5 残留（`/tmp/s5qa` + `/tmp/s5_builder_selfcheck`）+ Stage4 残留（`/tmp/s4qa` + `/tmp/s4qa_out`）+ Stage3 残留（`/tmp/s3qa`）+ Stage2 残留（`/tmp/s2t07_qa` 约 1.9M）+ Stage1 残留（`/tmp/s1t*` + `$TMPDIR`），交 neat-freak 收尾。
- U-4 `src/stage1/`/`src/stage2/`/`src/stage3/`/`src/stage4/`/`src/stage5/ git diff 为空`口径 N/A（当前目录非 git 仓库；以五回归 PASS + QA 零改代证，未改业务代码）。
- U-5 三表口径说明：纯映射/矩阵库恒 0/0/0；集成库（happy/a4/a7/a8/reg_s3）`normalization/render` 各 1 系 QA 脚手架经 Stage3 公开 API 合成 Rendered Final 所致（不绕门），非 Stage6 代码新增写（`grep` 反证 + `archive_commits` 全库 0 + sources 列级不变）；若按字面“恒 0”卡集成库则无 Rendered 可发布，QA 按 builder 自验同一口径（`t03.norm1/rend1`）验收。
- U-6 同实体跨路径语义：硬链接跨路径按 §22（`path|content`）另 mint 不同 Logical 系设计（字符串身份），本报告 A3 以 helper 真 + 同路径 MERGED + 计数不变举证同实体识别；跨路径去重不在 Stage6 范围内。

---
目标：Stage6验收S6-T04｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验 + supervisor 复检（HANDOFF 只记状态，不代写结论）。
