
# CODE REVIEW

- Task: 复核 app/ 三文件（server.py / index.html / start.sh），对照 P0-1~5（stdlib-only / 只读复用 / 三接口语义 / 单文件无外部资源 / 默认外置目录+input待填/src零触碰）
- Commit: N/A（非 git 仓库，无 commit；评审对象为工作区 app/ 三文件现状）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（P0-1~5 全 PASS；无 P0/P1；P2×6 + P3×1 进 backlog，不打回）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 stdlib-only：PASS。`python3 -m py_compile app/server.py` 通过；AST 进口仅 `__future__/json/os/sys/tempfile/threading/urllib.parse/http.server/datetime`（全 stdlib）+ `stage12.status_snapshot / stage5.startup`（只读复用目标，非第三方）。`sh -n app/start.sh` 通过，仅用 sh/python/open。
- P0-2 只读复用：PASS。server.py 仅 `from stage12.status_snapshot import collect`、`from stage5.startup import run_startup` 并调用；无对 src/ 的写（rg 仅命中注释与 import 行；`open()` 唯一一次是只读 `index.html` rb；`write` 仅 `wfile.write` 答包）。复用语义正确：`collect` 走 `mode=ro + PRAGMA query_only`（src/stage12/status_snapshot.py:86-96）；`run_startup` 经 daemon 线程后台跑（server.py:138-140），错误进 `_listener["error"]` 不炸进程（server.py:103-107）。
- P0-3 三接口语义：PASS（实测+代码双验）。`GET / → index.html`（实测 200 text/html 10860B，与文件大小一致）；`GET /api/status?data_root=&limit=` 透传 `collect(data_root, limit=limit)` 原样（实测 200，含 ok:true 空库与 DB_MISSING 分支由 collect 构造）；`POST /api/start` 后台 `run_startup`，已在跑 409（server.py:122-123）、空 input 400 / 非绝对 400 / 目录不存在 400（实测三条 400 均命中对应文案）、成功 202（代码验，未 live 触发以免 latch）；`GET /api/start` 返回本进程监听状态 running/data_root/input_root/error（实测 200 `{"running":false,...}`；另带 `started_at` 为加法字段，不违规格）。未知路径 404（实测）。
- P0-4 单文件无外部资源：PASS。index.html 无 `http(s)://`、无 `<link`、无 `<script src`、无 `<img`、无 `src=/href=`（rg 全空）；CSS/JS 全内联（`style>/script>` 各 2 处）；JS 仅 `fetch("/api/status"|"/api/start")` 同源三处，无外部请求。
- P0-5 默认外置目录+input待填/src零触碰：PASS。`DEFAULT_DATA_ROOT = tempfile.gettempdir()/v2o-console-data`（server.py:39，外置 /tmp，不指真实库）；`input_root` 默认空，前端 placeholder 标“必填”、空提交前端拦截 + 后端 400（server.py:127-132）；GET /api/status 缺省回退 DEFAULT（server.py:83）；start.sh 不设真实库路径，仅选 python 起 `app/server.py`；三文件无写 src 动作。
- P1：无（未发现功能阻塞级缺陷）。

## P2 / P3 Backlog Findings

- P2-1 POST `data_root` 缺绝对路径校验：`input_root` 有 isabs+isdir 三重门（server.py:127-132），`data_root` 仅 `str(...) or DEFAULT`（server.py:124）直接进 `run_startup→abspath` 落盘。改法：与 input 同口径加 `os.path.isabs` 400，相对路径拒绝。
- P2-2 `limit` 无上限：`_handle_status` 只做 int  fallback 20（server.py:84-87），超大 limit 透传 sqlite LIMIT。改法：cap（如 200）后透传。
- P2-3 `started_at` 竞态：POST 内先置 `running=True` 即 202 返回（server.py:133-143），`started_at` 由后台 `_launch` 稍后填（server.py:95-100），紧跟的 GET 可见 `started_at:null`。改法：POST 加锁时顺手填 `started_at`（UTC ISO），`_launch` 不覆盖或覆盖为启动完成时间并注明。
- P2-4 PORT 常量重复：`PORT=8765` 仅 server.py 定义（:37），start.sh 硬编码三处 URL/echo。改法：注释联动或由 start.sh 解析 server.py 常量，避免改一处忘一处。
- P2-5 start.sh `sleep 1` 脆弱：慢机上服务未就绪即 `kill -0` 误判。改法：轮询 `curl /api/start` 至多 N 秒代替固定 sleep。
- P2-6 无停止接口（规格内，纯 backlog）：启动后 `running` latch True，只能重启进程换 input_root。按“三接口”规格是预期行为，不卡本轮；是否加 `DELETE /api/start` 由产品定（含 supervisor shutdown 语义需另议）。
- P3-1 `esc()` 未转义单引号（index.html:115）：当前渲染位为文本节点 + 数字 `data-i`，无实际 XSS；若后续拼单引号属性需补全。改法：转义表加 `'→&#39;`。

证据备注：本轮冒烟时 8765 已有常驻实例（新起进程报 `Address already in use`，curl 命中旧实例；`GET /api/start` 示 `running:false` 空闲）。评审结论不受影响（GET 语义无状态、400 分支无副作用、202/409 走代码验）；建议 QA 验证前确认常驻进程归属，必要时重启后重跑一遍 202→409 链。
