
# CODE REVIEW

- Task: 复核 src/stage4/（对照 docs/pm/STAGE4-PLAN.md S4-T01~T05 + No-Clobber/原子link/禁rename落Final/禁O_TRUNC/禁force + Stage5禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage4/ 六文件现状：__init__.py / volume_probe.py / publish_commit.py / publish.py / conflict.py / lineage_ext.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0/P1；P2×4 + P3×3 记 backlog，不阻塞 QA；改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无 P0/P1。本轮硬红线逐项通过，证据如下（qa 可复执行）：
  - 原子 No-Clobber：Final 落盘唯一路径为 `publish_commit._link_and_finish` 内 `os.link(tmp, final)`（EEXIST 即 BLOCK，零截断、零窗口）；`os.rename` 只出现在 `volume_probe` 探针文件（covering_dir 内 `.s4probe_*`），`publish_commit/publish/conflict` 内零 `os.rename/os.replace/shutil.move` 落 Final（rg 实测：Final 侧 rename 零命中，注释声明除外）。
  - 禁 O_TRUNC：`open(canonical, "rb")` 全为只读；`"wb"` 只用于 same-dir tmp 与探针文件；`os.open(O_CREAT|O_EXCL)` 只用于探针与 gate 能力测量，无 Final 截断写。
  - 禁 force/覆盖后门：rg `force|FORCE|allow_overwrite|shutil.(move|copy)` 在 `src/stage4/` 零命中（除注释）；`publish.py` 存在分支直接委托 `conflict.publish_or_block`，本模块内无第二条落盘分支；`conflict.py` BLOCK 分支返回 `canonical_sha_before==after` + `canonical_writes==0`，无覆盖写。
  - 卷门：`volume_probe.probe_volume` 实测返回 §54 九字段全非空（本机验证：filesystem_type/volume_id/local_or_remote/case_sensitive/supports_atomic_rename/supports_exclusive_rename/supports_exclusive_create/supports_hardlink/supports_advisory_lock；APFS 上 `exclusive_rename=False` 系 POSIX 诚实值，`exclusive_create=True` 故 gate 放行）；`gate_output_root` 无可靠原语（两者皆无）→ `BLOCKED_UNSUPPORTED_OUTPUT_FILESYSTEM`，iCloud/network/remote 特征 → `BLOCKED_UNSUPPORTED_ROOT_FOR_V1`；发布三入口（prepare 后 commit / initial_publish / publish_or_block）均先过 gate；rg `Reservation|fallback` 零命中，无 Reservation Copy Fallback。
  - Stage5 禁入：rg `-i "watch|reconcile|path.?mirror|launchagent|menu.?bar|current_path|archive_commits|run_asr_single_file"` 在 `src/stage4/` 零命中；`archive_commits` 零写入（grep 仅 publish_records/artifacts/state_events/processing_runs）；Source 行零触碰；Run 回填仅 `initial_publish_record_id + updated_at` 两列且有列级 drift 断言（`publish._backfill_run`）；Whisper 执行入口零 import（仅 `whisper_calls/asr_calls: 0` 证据字段）。
  - 加法约束：`src/stage4/` 对 stage1/2/3 均为 `import` 只读复用（`stage1.probe_volume` / `stage3.artifact_commit.validate_rendered_bytes` / `stage3.lineage.get_lineage + record_lineage_manifest` / `stage2.store.utc_now_iso + central_db_path`），无写 `src/stage1-3/` 路径（rg `src/stage[123]` 仅注释声明）；`publish_records` 九字段（§35）+ `publish_mode=INITIAL` + `published_at` 仅 PUBLISHED 置值 + `state_events` 全跳变均齐；Case12 缝 `on_tmp_ready`（tmp fsync 后、link 前）三入口透传完备。

## P2 / P3 Backlog Findings

- P2-1 `publish_commit.py:452` `os.chmod(canonical, 0o444)` 计划外只读标记：STAGE4-PLAN 未授权 Canonical 只读化（只读是 Stage1 Raw Immutable 语义，不适用于需用户编辑的 Canonical §51）。当前不改字节、不破 hash，故不判 P0；但 QA 做“用户编辑诱饵一字节→BLOCK”用例前须 `chmod +w`，否则编辑失败会被误判为 BLOCK 成功；清理脚本亦须先加写权限。改法（二选一）：① 删掉该行 chmod（推荐，保持诱饵可编辑语义，权限交由文件系统默认）；② 保留则在模块 docstring + QA 报告前置条件中写明“诱饵编辑前 chmod u+w”，且验收加断言“chmod 不改变 hash”。
- P2-2 `conflict.py:108-116` 恢复匹配过宽（rev-only 即 Forward）：§53 分支①要求 `publish_record_id` 对上 + `expected==final` + `PUBLISHING`，当前 `publish_record_id is None` 时仅凭 `render_revision_id` 相同即 Forward。因 `_open_publishing_rows` 已按 `canonical_output_path` 过滤且 pub id 系 `(rev, canonical, hash)` 确定性派生，同 rev+同 canonical+同 hash 实为同一 publish，风险低，故 P2。改法：`publish_or_block` 无显式 `publish_record_id` 时，要求候选行 `expected_hash==sha_before` 且同 canonical 下 PUBLISHING 行唯一，否则判 BLOCK 系；或在 docstring 写明 rev-match 与 id-match 等价性证明。
- P2-3 `lineage_ext.get_lineage_with_publish` 绕过 `stage2.open_db` 持锁断言（直连 `sqlite3.connect` 只读）：读诊断不写库，绕过无写风险，但与 Stage2 “持锁写库”治理口径不一致，supervisor 易误判为锁门绕过。改法：改用 `stage2.store.open_db(data_root, require_lock_held=False)` 或在 docstring 注明“只读诊断、永不写入，故不走写锁门”。
- P2-4 `publish_commit.canonical_path_for` 仅 `abspath + commonpath` 防逃逸，未 `realpath` 消解父目录 symlink：恶意/误配 symlink 父目录可致 Final 落到 Output Root 外。测试用外置诱饵目录无 symlink，QA 口径不受影响，故 P2。改法：`makedirs` 前对 `root` 与 `final` 做 `os.path.realpath` 后再 `commonpath` 校验；或在 plan 外文档注明“Output Root 不得含 symlink 组件”。
- P3-1 `volume_probe._case_sensitive` 死变量 `lower`（仅建 `lower2/upper`，`lower` 只用于清理名单）：无功能影响。改法：删 `lower` 或改名注释。
- P3-2 成功 dict 亦带 `canonical_writes: 0`，与模块 docstring“BLOCK 路径带 0、成功报 hash”表述不一致：QA 应以 `published_hash==expected==final` 为成功判据，勿以 writes 计数判成功。改法：统一 docstring（成功亦 0，以 hash 为准）。
- P3-3 `publish._find_run_for_render` 多 Run 共 raw 时取最早 `ORDER BY created_at LIMIT 1`：happy 单 Run 不受影响。改法：多 Run 时抛错或按 `initial_publish_record_id IS NULL` 优先选择，并在注释写明。
