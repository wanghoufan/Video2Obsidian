
# CODE REVIEW

- Task: 复核 app/ V2 改动（normalize_path 去引号 / browse 只列目录 / PRECHECK 探针 / worker 装配只调公开 API / src 零改）
- Commit: N/A（非 git 仓库；评审对象为工作区 app/server.py 662行 / app/index.html 313行 / app/start.sh 40行现状）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（五项 V2 目标全 PASS；无 P0/P1；P2×5 + P3×4 进 backlog，不打回）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 stdlib-only：PASS。`python3 -m py_compile app/server.py` + `sh -n app/start.sh` 均过；AST 进口顶层仅 `json/os/sys/tempfile/threading/urllib.parse/http.server/datetime`（全 stdlib），`stage*` 均为只读复用目标；`mlx_whisper` 仅 `__import__` probe（server.py:88），无 hard 依赖。
- P0-2 normalize_path 去引号：PASS。`normalize_path`（server.py:71-82）语义正确：非 str→`""`；strip 后只去最外一层配对同种引号。实测 `' /tmp/a '`→`/tmp/a`、`"/tmp/b"`→`/tmp/b`、`'abc`（不成对）保留、`None/123`→`""`；三处调用点全覆盖：`_handle_status:132`、`_handle_browse:143`、`_handle_start_post:567-569`。前端 `dataRoot()/loadDir/btnStart` 均走 `encodeURIComponent` + 后端归一，前后端一致。
- P0-3 browse 只列目录：PASS。`_handle_browse`（server.py:140-170）：非绝对 400、非目录 400、`probe_volume` 非 ALLOW 400、`os.listdir` 仅 `isdir` + 按名 `sorted` + 上限 `dirs[:1000]`；实测含引号路径 `'<tmp>'` 200 且 `dirs==['adir','bdir']`（文件被滤掉）、文件路径 400、相对路径 400、空路径回退 `~` 200。index.html 无外部资源（无 `http(s):///<link/<script src/<img`），浏览弹窗仅 `fetch("/api/browse")` 同源。
- P0-4 PRECHECK 探针：PASS（双层）。`_mlx_available()`（server.py:85-91）probe import；`_handle_start_post:591-596` 缺 mlx 即 400 `{"code":"PRECHECK_MLX_MISSING"}`；start.sh:20-24 同口径预检（有则提示就绪、缺则 WARN 但仍起控制台靠接口兜底）+ 优先选 `stage0bench/.venv/venv` python（start.sh:8-10）。实测本机无 mlx 时 POST 隔离目录回 400 + code 字段正确，且 `_listener.running` 保持 False，无副作用。
- P0-5 worker 装配只调公开 API：PASS。20 个符号逐个 `hasattr` 验证全存在：`stage12.collect / stage5.run_startup / stage1.extract_temp_wav+transcribe_wav_file+FROZEN_* / stage1.prepare.build_raw_content+validate_raw_artifact / stage3.normalize.create_normalization_revision+DEFAULT_PROFILE / stage3.render.create_render_revision+DEFAULT_PROFILE / stage3.lineage.record_lineage_manifest / stage4.initial_publish / stage6.resolve_canonical / stage2.store.open_db / stage1.ingest.probe_volume / stage7.build_initial_prompt+run_single_file_with_prompt / stage8.plan_chunks+run_chunks`；无 `from stageX import _*`、无 `stageX._*` 属性调用（AST 扫描零命中）。短音频≤600s 走 stage7、长走 stage8、异常回退 stage1 直调（server.py:196-247），失败只记 verdict/receipt 不炸 worker（server.py:509-513）。
- P0-6 src 零改：PASS。写操作审计：`open(w)` 仅 `manifest.json:297` + `raw.json:361`（均在 `data_root/data/jobs/<run_id>/` 下，外置 job 产物），`makedirs` 仅 `job_asr_dir/job_dir/data:204/293-294/587`；`open(index.html)` 唯一读为 `rb:118`；`wfile.write` 仅答包；`sys.path.insert(src)` 只读。`rg "REPO_ROOT|src/"` 仅命中注释与 path-insert 行，无写 src 动作。
- P0-7 默认外置 + input 待填：PASS（延续 V1 并收敛其 P2-1）。`DEFAULT_DATA_ROOT=tempfile/v2o-console-data`（server.py:46）；`_handle_start_post:572-585` 现对 `data_root/input_root/ob_vault_root` 三者均做 `isabs+isdir` 门（V1 欠的 `data_root` 绝对校验已补）；空 input 前端拦截 + 后端 400。
- P1：无（未发现功能阻塞级缺陷；下述 P2-1 fail-open 仅影响只读浏览，不构成 P1）。

## P2 / P3 Backlog Findings

- P2-1 browse probe 异常 fail-open（本轮唯一新增问题）：server.py:153-156 `except Exception: verdict="ALLOW"`，与 `probe_volume` 本体 fail-closed（`src/stage1/ingest.py:90-119` 读表失败即 BLOCK）方向相反；import 失败/签名变更等意外异常会放行非本地盘浏览。改法：`except` 分支改 `verdict="BLOCK"` 并回 400（与 157-158 同文案）。
- P2-2 `limit` 无上限（V1 P2-2 延续）：`_handle_status:133-136` 只做 int fallback 20，负数/超大透传 sqlite LIMIT（-1 即不限）。改法：`limit=max(1,min(int,200))` 后透传。
- P2-3 worker 直写 `UPDATE processing_runs` 无 store 封装（server.py:396-404）：经公开 `store.open_db()` 拿连接是对的，但 `SET raw_artifact_id/norm/render_revision_id` 手写 SQL，`src/stage2/store.py` 无对应 helper，后续 schema 变即脱钩。改法：二选一——① `store` 加 `attach_revisions(con, run_id, ...)` 公开函数并改 worker 调用；② 暂保留直写但在该行加注释声明“有意直写 + 依赖列名清单”，供 reviewer 豁免。
- P2-4 `started_at` 窗口残留（V1 P2-3 已收窄未根除）：POST 置 `running=True`（server.py:598-603）与 `_launch` 首行填 `started_at`（server.py:531-535）之间仍有线程调度窗，紧跟 GET 可见 `started_at:null`。改法：POST 加锁块内顺手填 `started_at`，`_launch` 不覆盖。
- P2-5 打包脚本与启停延续三件（V1 P2-4/P2-5/P2-6 原样）：start.sh:29 `sleep 1` 后 `kill -0` 慢机误判→轮询 `curl /api/start` 至多 N 秒；`PORT=8765` 仅 server.py:44 定义、start.sh 三处硬编码→注释联动或解析常量；无停止接口（`running` latch，只能重启进程换 input）→是否加 `DELETE /api/start` 由产品定。
- P3-1 `esc()` 未转义单引号（V1 P3-1 延续，index.html:176）：当前渲染位为文本节点 + 双引号 `data-p/data-d` 属性，单引号无实际 XSS；后续若拼单引号属性再补 `'→&#39;`。
- P3-2 `_listener_snapshot` 双锁非原子（server.py:94-103）：`_listener` 与 `_worker` 分两次 `with _state_lock` 快照，高并发下两半可错位。改法：合并为一把锁一次快照。
- P3-3 `commonpath` 跨盘 `ValueError` 走通用通道（server.py:286）：不同挂载/盘符下抛错被 `_transcribe_worker:509` 通用 except 吃掉，单 run 只记 `last_error` 无结构化 verdict。改法：该行包 `try`，异常记 `SKIP + verdict=跨盘/路径不可比`。
- P3-4 轮询 `threading.Event().wait(0.1)×50`（server.py:514-519）：每 5s 周期分配 50 个 Event 对象。改法：复用单个 `Event` 或 `time.sleep(0.1)` 循环。

证据备注：`open_db(data_root)` 默认 `require_lock_held=True`（src/stage2/store.py:236），worker 三处调用均不传参，依赖 `run_startup` 先 `mark_held`；停止后轮询先检查 `_listener["running"]` 再 open，无锁竞态引发的误报错链。结论不受影响。
