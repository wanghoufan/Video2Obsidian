
# CODE REVIEW

- Task: 复核 src/stage6/（对照 docs/pm/STAGE6-PLAN.md S6-T01~T03 + 纯映射零写盘/禁归一化slug/Stage7+禁入）
- Commit: n/a（工作区无 git，核对对象为 src/stage6/ 三文件现状：__init__.py / mirror.py / unicode_cases.py）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（无 P0；P1×2 + P2×4 + P3×3 记 backlog，不阻塞 QA；P1 建议 builder 在 QA 前修，mandated 用例均不受影响，改法见各条）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P1-1 `mirror.py:19-49` `resolve_canonical` 与 Stage4 `canonical_path_for` 在首尾空格相对路径上差一字节（本机实测 `DIVERGE`）：Stage4 `publish_commit.py:121` 先 `rel.strip()` 再映射，Stage6 原样保留前导空格。复现：`rel=' lead.mp4'` → Stage6 `'<out>/ lead.md'` vs Stage4 `'<out>/lead.md'`。常规名（嵌套/中文/`丨`/括号/大小写/`.MP4`/中间点号）双算全一致（7 例 `OK`），越界三例全 `BLOCK_OK`，故不定 P0。但 P0-1 明写“同一输入双算差一字节即 FAIL”，首尾空格是 macOS 合法文件名且 P0-2 要求空格原样保留，属真分叉不是假想。改法（二选一，推荐① fail-closed）：① `resolve_canonical` 在算出 `rel` 后加 `if rel != rel.strip(): raise MirrorEscapeError(...)`，把与冻结 Stage4 口径冲突的名字显式 BLOCK（不静默错映射、不静默改名）；② 若 TM 拍板“首尾空格按 Stage4 strip 口径”，则 Stage6 同步 `strip()` 并在 docstring 写明与 §73-35 的例外关系。无论选哪个，QA 在 S6-T04 加一例 ` lead.mp4`（或空格目录 ` mydir/clip.mp4`）断言 BLOCK 或双算一致。
- P1-2 `unicode_cases.py:22-40` `assert_byte_preserved` 只验尾巴不验目录，错目录会假 PASS（本机实测：`rel='A/B/C.mp4'` + `canonical='/evil/X/Y/C.md'` 返回 `{'ok': True}`，记 `WEAK_PASS_WrongDir`）。`path_identity_key` 相等性、`..`/绝对路径、`.md` 尾缀三处是对的（`IDENTITY_OK raises`），缺的是“目录逐级保留 + 输出前缀恒为诱饵 Root”。改法：给 helper 加 `output_root` 形参（调用方全在仓库外合成测试，改签名无线上影响），内加两断言：① `os.path.commonpath([abspath(output_root), abspath(canonical_path)]) == abspath(output_root)`；② `os.path.dirname(abspath(canonical_path)) == os.path.join(abspath(output_root), os.path.dirname(rel))`（顶层文件时 `dirname(rel)==''` 即等于 root）。加完后现有 5 例 happy（中文/`丨`/Clip/clip/NFC/NFD）仍过，错目录例必 raise。QA 在修好前对每例另行显式 `==` 全路径，不依赖本 helper 做目录断言。
- 无 P0。本轮硬门逐项通过，证据如下（qa 可复执行，下均为本机实测）：
  - 纯映射零写盘：`resolve_canonical` 内仅 `abspath/relpath/splitext/join/commonpath`，`rg "makedirs|open\(|O_CREAT|O_EXCL|shutil|unlink|remove|rename|link\(" src/stage6/` 唯一命中是 `mirror.py:59`（`ensure_parent_dir` 的 `makedirs`，属 S6-T01 明示允许的父目录创建，不在纯函数内）；实测调 `resolve_canonical` 前后诱饵 Root `os.listdir` 无变化（`PURE_ZERO_WRITE`）。
  - 越界 BLOCK：`..` 逃逸/Input Root 外绝对路径/以 input_root 本身为源三例全 `MirrorEscapeError`（`BLOCK_OK ×3`）；`rel=='.'`/空部件/`commonpath` 二次校验三层门齐全。
  - 嵌套+后缀：`A/B/C.mp4→A/B/C.md`、`my.clip.v2.mp4→my.clip.v2.md`（中间点号不动）、`UPPER.MP4→UPPER.md`（大小写不敏感 strip 但 stem 原样）、`AI/博主A/DeepSeek V4 分析.mp4` 全链 OK；与 Stage4 双算 7/7 一致（首尾空格边缘除外，见 P1-1）。
  - 禁归一化 slug：`rg "quote|slug|casefold|normalize\(|unicodedata|NFC|NFD" src/stage6/` 零命中（`ZERO_HITS_normalize`）；`ext.lower()` 仅用于后缀成员判定，stem 取 `base[:len-len(ext)]` 原字节保留；`MATRIX` 11 项含 `测试 中文丨Case (A)`/`丨`/圆括号/方括号/空格/`Clip vs clip`/`UPPER.MP4`/`my.clip.v2`/NFC `café(U+00E9)` vs NFD `cafe(U+0065+U+0301)`（字节确不同，`NFC_NFD_BYTES_DIFFER`），逐字节 helper 7 例 happy 全过；同实体 `entity_key=(st_dev,st_ino)` 硬链接实测相等（`is_same_entity True`）。
  - 父目录安全创建：`ensure_parent_dir` 正常建 `A/B`（`ready True`）；同名文件挡路抛 `MirrorBlockedError` 且诱饵字节不变（`BYTES_INTACT`）；中途祖先是文件时 `makedirs` 的 `OSError→MirrorBlockedError` 转换覆盖；无 `rmtree/remove/unlink/rename`（上条 grep 为证）。
  - Mirror×Publish 集成只透传不复制：`__init__.py` import 面仅 `stage6.mirror/unicode_cases` + `stage4.publish/volume_probe`（`rg import` 全量核对）；`publish_mirrored` 为 `resolve→ensure_parent→_pub.initial_publish(con,job_dir,render_rev,output_abs,rel)` 单线透传，签名与 `publish.py:163-166` 对位正确；`rg "commit_publish|publish_commit|os\.link|O_EXCL" src/stage6/` 零命中——无内联 commit、无自造 No-Clobber；`whisper_calls/asr_calls=0` 标记正常（`rg whisper` 唯一命中即该标记，无执行入口）；`case_flag` 仅读 `probe_volume` 的 `case_sensitive/volume_id` 两字段做分支断言，未重实现探针、未改门。
  - Stage7+ 禁入：`rg "run_asr_single_file|prompt|vocab|vad|chunk|archive|current_path|launchagent|menu|force|overwrite|clobber" src/stage6/` 零命中（`whisper` 仅证据标记字段）；文件名 `mirror.py/unicode_cases.py/__init__.py` 无 Stage7+ 关键词；中央库三表（normalization/render/archive）本模块零直写（一切 DB 效应经 `initial_publish` 语义，`rg "sqlite3|INSERT|UPDATE|DELETE" src/stage6/` 零命中）。

## P2 / P3 Backlog Findings

- P2-1 `__init__.py:27` `publish_mirrored` 先 `ensure_parent_dir` 后调 `initial_publish`（内含 `gate_output_root`）：gate 拒绝或 canonical 已存在 BLOCK 时，空父目录已留下。无字节风险（空目录），故 P2。改法二选一：① 先调轻量 gate（`case_flag` 或 `_vp.gate_output_root(output_abs)` 只读探针）再建目录；② 不改代码，QA 把“BLOCK 后空目录残留可接受”写进报告容差（推荐②，动门顺序收益小）。
- P2-2 `unicode_cases.py:7-19` `MATRIX` 11 项全是顶层文件名，无 `A/B/C.mp4` 嵌套条目。嵌套由 mirror 双算用例覆盖，不断链，故 P2。改法：MATRIX 追加 2 项嵌套（如 `A/B/C.mp4`、`AI/博主A/DeepSeek V4 分析.mp4` 的 rel 形态）或在模块注释写明“嵌套由 mirror 双算覆盖，本表只做文件名类”，二选一。
- P2-3 `mirror.py:19-24` 未断言 `input_root` 与 `output_root` 互斥：同树映射（output 在 input 内）技术上可算，误配会把 canonical 算进源树。外置三 Root 验收门在 QA 侧覆盖，故 P2。改法：`resolve_canonical` 头加 `if commonpath([input_abs, output_abs]) in (input_abs, output_abs): raise MirrorEscapeError` 或保持现状由验收前断言覆盖（推荐后者，库函数不过度限制单测复用）。
- P2-4 `src/stage1-5/` 零修改硬门本窗口无法用 git 证明（工作区无 git）。代码侧 `rg` 显示 Stage6 无任何写 stage1-5 路径，`__init__` 仅只读 import stage4/stage5（见 P0 证据），故不阻塞。改法：QA/Supervisor 用快照对比（`diff -r` 或落盘清单）补证 `src/stage1-5/` 未动，结论进 QA 报告。
- P3-1 三文件头均有 `sys.path.insert(0, .../src)` 导入期副作用，与安装包并存时顺序相关。沿 stage1-5 既有模式，不改；仅记一笔：若将来打包，改相对导入并删 hack。
- P3-2 `mirror.py:6` 经 `stage5.watcher` 复用 `VIDEO_SUFFIXES` 会传递导入 `watchdog`（watcher 模块级 import）。属 PLAN 明示复用（不重定义冲突口径），不改；仅记一笔：无 watchdog 环境 import stage6 即失败，QA 环境需保证依赖齐（Stage5 同理）。
- P3-3 `__init__.py:12-14` `case_flag` 调的是活探针（建临时 `.s4probe_*` 后删），非纯读。属 `volume_probe` 设计语义（量测非臆测），不改；仅记一笔：QA 在断言“诱饵 Root 零外来文件”时容忍探针瞬时文件或测后复核（`ls -a` 无残留）。

## P1 复核（2026-09-11 builder 修后，code-reviewer 追加，只增不改原文）
- P1-1 CLOSED：mirror.py:25-26 `resolve_canonical` 加 `if rel != rel.strip(): raise MirrorEscapeError`（选型① fail-closed）；实测 ` lead.mp4` BLOCK_OK，常规嵌套 `A/B/C.mp4` 仍 OK，未引入 strip 改名或静默错映射。
- P1-2 CLOSED：unicode_cases.py:22-23 签名加 `output_root=None`，45-53 加双目录门（commonpath 前缀恒为 Root＋dirname 逐级保留）；实测错目录 `A/B/C.mp4→/evil/X/Y/C.md` 必 raise（WRONGDIR_RAISE_OK），正确嵌套/顶层仍 `ok True`，无参旧调用仍只验尾巴（向后兼容）。
