
# CODE REVIEW

- Task: 复核 app/ V2.3（runs filename联查、vault注册检测、app侧canonical包装去扩展名且src零碰）
- Commit: N/A（非 git 仓库；评审对象为工作区现状 app/server.py 2215行 / app/index.html 951行 / app/start.sh 40行；src 只读对照 src/stage6/mirror.py 66行 + src/stage4/publish_commit.py canonical_path_for + src/stage4/publish.py initial_publish + src/stage3/render.py canonical_probe）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（V2.3 三项目标全 PASS；V2.2 遗留 P0×1+P1×3 已确认修复；无 P0/P1；P2×5 + P3×2 进 backlog，不打回）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 runs filename联查：PASS。`_run_source_path_map`（server.py:864-888）经 `_open_ro`（837-861，`central_db_path` 只读 `mode=ro`，缺库回 `{}` fail-open）取 `{run_id: current_path or pik}`；`_attach_source_filenames`（522-551）给 `recent_runs` 逐行附 `source_filename=basename(path) or "未知文件"`，非 dict/非 list/映射缺失/空路径/异常全回退不炸（`_handle_status:1061-1066` 仅 `ok` 时附加）。`_listener_snapshot details`（736-784）内存 `source_filename` 优先、缺失联 map 取 basename、再缺回“未知文件”。`_process_one_run _src_fn`（1239-1244，`current_path or ""` 防 None）、worker 未知异常 `_ffn`（1543-1550）同口径。前端 `filenameForRun/FilenameForRunId`（index.html:314-341）按 runs→details→processed→current 逐级兜底，任务列（400-403）显“文件名+短 id”，toast/重试（653-660/730-741）用人话文件名，裸 run_id 只留 title/详情区。实测缺库 attach 全回“未知文件”不崩；`r[1] or r[2]` 对空串回 pik 正确，空白路径经 strip 判回“未知文件”。
- P0-2 vault注册检测：PASS。`_is_vault_registered`（472-486）判 `abspath(vault)/.obsidian isdir`，None/非 str/空串/缺目录/`.obsidian` 为文件/不可读一律 False（fail-closed，只读不落盘）。实测矩阵 7 例全对（None/空/数字/缺目录/无 .obsidian→False，有 .obsidian→True，.obsidian 为文件→False）。消费三处一致：`_listener_snapshot:805-809` 回显 `vault_registered`；`_handle_note` 有 md 时（2121-2124）未注册则 `ob_url=None+注册引导`，无 md 时（2135-2137）已配未注册才覆盖（未配保持“未配置笔记库”原人话）；前端 `obLinkFor`（342-353）空 vault 先回未配置、`vault_registered===false` 回 `needRegister` 并禁用按钮（377-386/498-517 `obdis` + `obClickHint` toast）。后端 `_finder_url`（942-944 `quote(safe="/:")`）与前端 `finderUrlFor`（366-376 后端优先、回退逐段 `encodeURIComponent` 保 `:`）双源一致，V2.2 P1-2 前端裸拼已修（`outCellFor:377-387` 与 `renderOpenRow:498-518` 均走 `finderUrlFor`，`#/?` 中文空格三例不再截断）。
- P0-3 app侧canonical包装去扩展名且src零碰：PASS。`_app_resolve_canonical`（489-519）只读复用 `stage6.mirror.resolve_canonical`（不改 src 文件），以 `splitext(basename)[0]+".md"` 为期望名校对、仅替换 basename、保持子目录（实测 `sub/09.test.mp4→vault/sub/09.test.md` 子目录保留，`app_expected_name/app_single_ext_fixed` 双键齐）。16 例实测（mp4/大写MP4/多点/uw m4a-mp3-wav/mov-mkv-m4v-avi-webm/txt/无扩展/a.mp4.txt/隐藏/中文空格#?）wrap 与底座全一致 `fixed=False`——底座 `mirror.py:36-48`（VIDEO_SUFFIXES 命中去扩展、否则 `stem_raw`）与发布侧 `publish_commit.canonical_path_for:129-133`（`splitext(rel)[0]+".md"`）三层本来就是单扩展，`09.xxx.mp4→09.xxx.md` 无双扩展 bug，wrapper 为防御性守卫（若底座某天回双扩展则 probe 与 publish 重对齐：wrapper 只换 `canonical_output_path`、保留 `source_relative_path`，publish 重算 `splitext(rel)` 结果与 wrapper 期望一致，不分叉）。`canonical_probe` 仅进 `render.evaluate_publish` 做存在性探针（render.py:339-356），真正落盘由 `initial_publish(source_rel)` 重算，probe/publish 口径一致。调用方：`_process_one_run:1344-1356` 越界抛转 `MIRROR_FAILED` verdict（实测 `/etc/passwd` 抛 `MirrorEscapeError` 正确上收），`_preview_mapping:554-572` 演示文件不触盘、缺 vault/缺 input 回 `""`。src 零碰：AST 无 `from stageX import _*`、无 `stageX._*` 私有调用；写操作仅 `data_root/data/jobs/<run_id>/manifest+raw`、`data_root/data`、`jobs/<run_id>` 单层删（2046 `startswith(jobs_base+sep)` 防穿越），`index.html` 无外部资源，`sys.path.insert(src)` 只读。
- V2.2 遗留回归：PASS。P0-1 `_launch input_abs NameError` 已修（1599 `_install_scoped_gates(input_root)`，全局无 `input_abs` 残留，`py_compile` 过）；P1-1 空归属 fail-closed 已修（`_blocked_run:227-229` + runstates:324 `unatt` 计挡住，`_handle_clear_post:1864-1865/2010-2014` 门清一致）；P1-3 clear 已修（1801-1804 运行中 409 拒 + NULL archive 同步删 + 孤儿 run 并入）；P1-2 前后端编码已修（见 P0-2）。
- P1：无（未发现功能阻塞级缺陷）。

## P2 / P3 Backlog Findings

- P2-1 `_attach_source_filenames` 主路径覆盖已有好文件名：DB 缺失时 `mapping={}`，`r2` 自带 `source_filename="already.mp4"` 被重写为“未知文件”（实测复现；except 回退分支有 `if "source_filename" not in r` 守卫，主路径无）。生产 `collect()` 的 runs 本无该字段，无用户影响。改法：主路径加 `if isinstance(r.get("source_filename"),str) and r.get("source_filename").strip(): continue` 再查 map。
- P2-2 `_handle_note` RENDER_ONLY+未配 vault 文案分叉：有 md 分支（2122）`if not registered` 无条件覆盖为注册引导，vault=None 的 RENDER_ONLY 会丢“未配置笔记库”人话；无 md 分支（2135）有 `and vault_root` 守卫保持原人话。前端 `obLinkFor` 空 vault 先回未配置，与后端有 md 分支不一致。改法：有 md 分支加同款 `and vault_root` 守卫（未配保持未配置，已配未注册才给注册引导）。
- P2-3 前端 OB 库内判定仍字符串前缀（index.html:349-352 `cp!==v && indexOf(v+"/")!==0`），与后端 realpath+commonpath（server.py:959-962）有 symlink/trailing-slash 差异（V2.2 P2 延续）。改法：前端入参前统一去尾斜杠，或以后端 `/api/note ob_url` 为单源（后端已算对，前端 `loadNote` 暂未渲染 `ob_url`，V2.2 P1-2 死代码尾巴仍在）。
- P2-4 `_preview_mapping` 演示名硬编码“示例视频.mp4”（server.py:561）：若用户视频全为 `.mov/.mkv`，预览仍显示 mp4 式样。改法：按 `VIDEO_EXTS` 首个或当前目录首个真实视频扩展名动态演示，或文案注明“以 mp4 为例”。
- P2-5 打包/启停延续（V2.1 P2-5 原样）：`start.sh:29 sleep 1+kill -0` 慢机误判、`PORT 8765` 两边硬编码，本轮未动，不卡 V2.3。
- P3-1 `_handle_status` 每轮 5s 三连开库（`collect` + `_filter_status_runs` map + `_attach_source_filenames` map 各一次 `_open_ro`）：正确性无碍，仅多两次只读 open。改法：一次 `mapping` 复用两步（传参 threading）。
- P3-2 wrapper `app_single_ext_fixed` 16/16 例恒 False（本轮实测）：防御守卫，保留无害。建议加一行注释“底座三层已单扩展（mirror/publish_commit/render），本包装为防回归守卫，正常恒 False，True 即底座行为变更告警”，免后人误删。

证据备注：`py_compile app/server.py` 过；`input_abs` 全局零命中；vault 7 例 + attach 缺库/非 dict/非 list + wrapper 16 例 + 子目录保留 + preview 三态 + 越界抛 `MirrorEscapeError` + finder 编码 `file:///tmp/%E5%B8%A6%20…%231%3F.mp4` 均本机实跑；`initial_publish(con,job_dir,rend_id,vault,source_rel)` 签名已核（publish.py:163-166），`canonical_path_for`（publish_commit.py:118-136）与 `mirror.resolve_canonical`（mirror.py:19-51）逐行已核三层单扩展一致。
