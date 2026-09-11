# QA-REPORT｜成品包装验收（app/server.py + index.html + start.sh 起服实测）

- QA：qa（opencode-go/glm-5.3-flash，本窗口 subagent；未改业务代码，只写本报告）
- 被测：`app/server.py` + `app/index.html` + `app/start.sh`（成品包装；`src/` 只读复用）
- 任务目标：起 server 实测 GET / 200、GET /api/status 无库 DB_MISSING/有库 ok:true、POST 空 input 400/相对路径 400/正常 202/重复 409；index.html 含开始监听/刷新/磁带/轮询且零外部资源；start.sh sh -n 过；src/ 零改；只用外置测试目录，真实库零碰；坏例看 exit 码
- QA 执行目录（仓库外）：`/tmp/v2o-pack-qa-data`（136K：data/state.db + wal/shm + .lock）+ `/tmp/v2o-pack-qa-input`（空目录 0B）+ `/tmp/v2o-pack-qa-empty`（不存在路径，用于无库用例，不建盘）+ `/tmp/v2o-pack-qa-validate.py` + `/tmp/v2o-pack-qa-neg.py`（仓库外 Runner）；仓库内零写盘除本报告
- **结论：PASS（原子 validator 7/7 exit 0；index 四关键词齐 + 外部资源 0 行审计 exit 0；start.sh sh -n exit 0；src 66 个 .py md5 diff 为空；默认 /tmp/v2o-console-data 全程 absent；坏例负控 exit 1 已证；结论只落本报告）**

## 1. 用例简表（坏例只看 exit 码）

| 用例 | 动作 | 期望 | 实测 | exit 码 |
|---|---|---|---|---|
| GET / | `GET /` | 200 + text/html | 200 + text/html，body 10860B 含开始监听×5 | curl exit **0**，validator PASS |
| status 无库 | `GET /api/status?data_root=/tmp/v2o-pack-qa-empty` | HTTP 200 + `{ok:false,code:DB_MISSING}` | 一致（message 指向 empty/data/state.db 不存在） | exit **0** |
| POST 空 input | `POST /api/start {}` | 400 请填写 input_root | 400 一致 | exit **0**（HTTP 400 非 curl 非零，判据为 HTTP_CODE） |
| POST 相对路径 | `POST /api/start {input_root:relative/path}` | 400 须为绝对路径 | 400 一致 | exit **0**（同上） |
| POST 正常 | `POST /api/start {data_root:/tmp/v2o-pack-qa-data,input_root:/tmp/v2o-pack-qa-input}` | 202 ok:true running:true | 202 一致 | exit **0** |
| POST 重复 | 同上再 POST 一次（running 中） | 409 监听已在运行 | 409 一致 | exit **0** |
| status 有库 | `GET /api/status?data_root=/tmp/v2o-pack-qa-data` | HTTP 200 + `{ok:true}` | 一致（counts 五表全 `{}` + recent `[]` + error 0） | exit **0** |
| 原子汇总 | `/tmp/v2o-pack-qa-validate.py` 7 断言 | 全 PASS 则 exit 0 | TOTAL 7/7 FAILS=[] | **VALIDATE_EXIT=0** |
| 坏例负控 | `/tmp/v2o-pack-qa-neg.py` 故意错误期望（重复启动断言 202） | 应 FAIL 且 exit 1 | FAIL code=409 | **NEG_EXIT=1**（符合预期，证坏例非只打印） |
| index 内容 | 文件断言 | 含开始监听/刷新/磁带/轮询 + setInterval + fetch /api/status | 全含（len 10003） | 审计 exit **0** |
| index 零外部 | 逐行扫 `http://|https://|<script src|<link |@import|src="http|href="http` | 0 行 | bad_lines=[] | **EXT_AUDIT_EXIT=0** |
| start.sh | `sh -n app/start.sh` | exit 0 | exit 0 | **SHN_EXIT=0** |
| src 零改 | 66 个 `src/**/*.py` md5 前后 diff | 为空 | 为空 | **DIFF_EXIT=0** |
| server 只读审计 | `grep -nE "INSERT|UPDATE|DELETE|open(.*w|shutil|os.remove|unlink" app/server.py` | 无命中（rc=1）；import 仅 stdlib + stage12.collect + stage5.run_startup | 无命中 rc=1 | rc=**1** |

Runner：单进程原子 validator（urllib 直调，HTTPError 取 code 断言，不看打印）+ 负控错期望 + 三审计（外部资源/sh -n/md5 diff）；server 起于 `python3 app/server.py`（127.0.0.1:8765），测后已停；server 日志 9 行请求码与上表一一对应（200/200/400/400/202/409/200/409/409）。

## BUGS（照 BUGS.template.md；本轮无 P0/P1）

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| 无（包装侧） | — | 否 | 7/7 实测码与期望一致；负控 exit 1 | CLOSED | 无需 builder 修 | validator + server 日志双证 |
| OBS-1（观察，非 bug） | P3 | 否 | 监听 running 中时 POST 不存在目录返回 409 而非 400（running 检查优先，符合 server.py:121-123 顺序） | CLOSED | 无需修 | 行为符合代码顺序，报告备查 |

## Fix Attempt Fingerprint

- Task ID: 成品包装验收（起服实测；首轮 QA 执行，业务零修）
- Root Cause Hypothesis: 不适用（业务 PASS；首个 server 实例日志混入 7 行非本轮请求疑似并发探针，重启后原子复验 9 行干净一一对应，结论以原子轮为准）
- Approach: 外置三目录（empty 不存在/data+input）+ urllib 原子 7 断言只看 HTTP_CODE/exit 码 + 错期望负控证 exit 1 + index 逐行外部审计 + sh -n + 66 py md5 diff + 默认 data_root absent 快照 + server 日志对账
- Files Changed: 仅新增本报告 `docs/qa/PACKAGING-QA-REPORT.md`；`src/` + `app/` 零改；测试写盘只在 `/tmp/v2o-pack-qa-*`（data 136K + input 0B，交 neat-freak 收尾）
- Verification: VALIDATE_EXIT=0（7/7）+ NEG_EXIT=1 + EXT_AUDIT_EXIT=0 + SHN_EXIT=0 + DIFF_EXIT=0 + 默认库 absent + 日志 9 行对齐
- Failure Reason: 无 FAIL 项（包装侧）
- Difference From Previous Attempt: 首轮，无上一轮

## 未闭环清单（交 supervisor/product-reviewer 定，不卡本 PASS）

- U-1 真实长视频未测（延续产品完成已知限制；本轮 input 为空目录 0B，只验启动/状态机，不转写）。
- U-2 真实库零碰以“只用 /tmp/v2o-pack-qa-* + 默认 /tmp/v2o-console-data 全程 absent + 仓库内零写盘除本报告”代证；无真实库快照可附（按禁令不得碰）。
- U-3 `__pycache__` mtime 可能因 import 执行被刷新（`*.py` md5 diff 为空，源零改成立；pyc 为构建产物）。
- U-4 残留待清：`/tmp/v2o-pack-qa-data`（136K）+ `/tmp/v2o-pack-qa-input` + `/tmp/v2o-pack-qa-*.py/log/pid/md5`，交 neat-freak 收尾。
- U-5 非 git 仓库，`src/ git diff 为空`口径 N/A；以 66 文件 md5 diff 为空代证（同 Stage10/11/12 U-5 Pattern）。

---
目标：成品包装验收｜剩 P0：无（QA 口径 PASS；闭环判定以 supervisor 复检为准）｜下一步：交 product-reviewer 验＋supervisor 复检（HANDOFF 只记状态，不代写结论）。
