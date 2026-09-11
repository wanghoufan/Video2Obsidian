
# CODE REVIEW

- Task: V26分段v2.6（目标80/硬顶120/防碎30，单源头，禁LLM）+ 预置词库三域一键导入（金融66/编程83/币圈68，合并+bump+撞基表拒收+单字门，server stdlib-only）
- Commit: 工作区未提交（base `b22c464`；`M src/stage9/formatter_v2.py` + `M app/server.py` + `M app/index.html` + `?? app/presets/vocab/` + `?? tests/selftest_v26_presets.py`；`M HANDOFF/账本`为治理同步非本次被检，`M USER_MODEL_OVERRIDE.md`为作废丢失待定（同UX2-P0注，已记HANDOFF未决）；未 commit、未 push，符合红线）
- Reviewer: code-reviewer（`src/` 改动面以 `git diff --name-only -- src/` 仅 `src/stage9/formatter_v2.py` 佐证，stage3 零碰；技术分歧听 code-reviewer）
- Result: 过（P0 全闭环，无打回项；P2 记 backlog，不拦 QA）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-① 参数单源头属实，过：`PARA_PARAMS_V2={1.5,80,120,30}`（`src/stage9/formatter_v2.py:73-78`）为唯一数字源；`_engine_params` 读其中三键（:115-121），`render_with_v2` 读 hard_max/min（:269-272），`postprocess_paragraphs`/`split_segments_for_engine` 缺省全回落该 dict（:215-216,252-255）；生产两入口经同一函数：`_render_profile_for_new_jobs→new_render_profile`（`app/server.py:1773-1778`）与 `_apply_v25_postpass→render_with_v2`（:1811）及重跑入口同源（:3583,3612-3620）。`rg 200/40` 在分段路径无残留硬编码（仅 `limit clamp 200` 与一条旧注释见 P2-②）。
- P0-② 版本/revision 链条，过：`FORMATTER_VERSION=para-v2.6`（:55），`new_render_profile` 只写 `#30` 两字段 version+params（:101-112）；stage3 侧 `render_profile_hash` 对五字段规范 JSON 求哈希（`src/stage3/render.py:95-125`，params 整体入哈希，MIN 变化亦换 hash=Case5），`render_paragraphs` 只读三键、额外 MIN 键被忽略（:145-160），与注释一致；实测 `render_profile_hash(new_render_profile)` 正常出哈希、新 revision 可 mint。冻结引擎与 stage3 文件零改（`git status -- src/stage3/` 空）。
- P0-③ 新旧分段行为，过：自验 `python3 tests/selftest_v26_presets.py` EXIT=0（15/15 段相关断言全过，含 `check_rule_order.all_pass`）；450 字无标点合成段→全段≤120、段数>1、无空段、字面未改写（自验 :48-54，复核机重放一致）；旧行为对照（同 6 段合成输入）：v2.5 引擎参数 `{120,200}` 得 3 段 `[203,203,203]`，v2.6 `render_with_v2` 得 9 段、max 102，收紧符合预期；边界 `frag 29→合并、30→不并`（MIN=30 生效），`cap 120→[120]、240→[120,120]`。禁 LLM：formatter 纯函数、无网络/模型调用（全文仅 docstring 一处 “no LLM” 自述，`rg -i llm|openai|gpt` 零命中业务逻辑）。
- P0-④ 预置条目质量抽查，过：三文件计数与任务一致（finance 66 / programming 83 / crypto 68，`python -c` 直读）；全域 `len(wrong)≥2`、`wrong!=right`、同域错词去重全过（自验 :104-108，复核机重放 PASS）；跨域错词零重叠（全量 217 错词集合无交集）；真实词误伤抽查 12 词（融资/融券/转账/地址/比特币/区块链/变量/函数/数据库/美联储/市盈率/创业板）无一被当作错词；重叠模式 benign（`钱抱/冷钱抱`、`哈西/哈西表`、`中心话/去中心化` 短串先替结果与长串直替一致）；每域含 `source` 且明示“知识兜底、无现成对表、仅精确子串替换”（:5 各文件）。
- P0-⑤ 导入语义，过：已存在跳过不覆盖用户自定（实测预置 `通货膨涨=用户自定` 后导入 finance：added 65 / skipped 1，`通货膨涨` 仍为用户值）；撞基表拒收（真实三域 `rejected_base_count==0`；合成 `Github→GitHubX` 被拒收且不落库）；单字门保留（读取层 `len(wrong)>=2` 过滤 `app/server.py:2016-2018` + `_validate_vocab_pair` 拒收 `len<2` :1702-1704，合成 `a→bb` 被丢弃、`added==1`）；幂等（二次导入 added 0 / skipped 全量 / revision 不变）；bump（`revision=s9-corr-v2-user-*`，`vocab-user.json` 落盘，`_norm_profile_for_new_jobs` 取该 revision，新转写 `apply_corrections` 金融+币圈替换生效）；坏例 `domains=[]→400`、全未知域→400。
- P0-安-① 改动面+无 secrets+stdlib-only，过：`src/` 仅 `formatter_v2.py`（上文）；`rg -i api[_-]?key|secret|token|password` 在 `formatter_v2/server.py` 零命中；`server.py` import 全为 stdlib+`stage*`（`ast` 实测：datetime/hashlib/http/json/os/shutil/sqlite3/string/subprocess/sys/tempfile/threading/urllib + stage1-9，无新增三方）；预置 json+自验脚本均为 stdlib（json/os/shutil/sys/tempfile/importlib/traceback）；预置目录运行时只读、落盘只写 `<data_root>/vocab-user.json`（隔离 tmp 实测互不污染）；未 push。
- P1：无（未发现需返工的 P1；121 余数孤儿见 P2-①，按 cap 优先的既定取舍不算 P1）。

## P2 / P3 Backlog Findings

- P2-① 硬顶/防碎冲突取舍（已知限制，非缺陷）：余数<30 且前段已满 120 时合并不被允许（`_merge_shorts` 拒超 cap，:159-195），故 `121→[120,1]`、`241→[120,120,1]`、`250→[120,120,10]` 尾段<30 孤儿。cap 优先正确（硬顶是硬保证），但与“防碎 30”表面矛盾。改法（任选其一，不拦）：A）文档化（formatter docstring + QA 报告注“余数孤儿系 cap 优先”）；B）尾段均衡切分（如 121→[61,60]，需改 `_split_overlong` 尾段重分配，动纯函数+补单测）。
- P2-② 命名/注释残留 v2.5：函数名 `_apply_v25_postpass` 实际跑 v2.6 阈值（`app/server.py:1781`，3 处引用），`server.py:3521` 注释仍写“200/MIN 生效”。改法：函数改名 `_apply_v26_postpass`（同步 :1781 定+义 :2532/:3620 两调用+formatter docstring 两处引用）或留名加注“一律走 PARA_PARAMS_V2，名存实亡”；注释改“120/30 生效”。
- P2-③ 探针键改名兼容：`hard_cap_v25/min_merge_v25→hard_cap_v26/min_merge_v26`（:355,368）为版本化改名，当前无代码引用旧键（仅旧评审文档提及），`all_pass` 口径不变。改法：HANDOFF/QA 报告注一句“探针键随版本改名”，外部脚本勿按旧键断言。
- P2-④ 口径说明（非本次引入，不重复计）：`app/server.py` 本次 diff 含 UX2-P0/P1 既有链（clear/stop/note/summary 等）与 `app/index.html` 同理，其中预置 UI（`presetBox`+`/api/vocab/presets*` 前后端）属本次，余部已由 UX2-P0/P1 评审覆盖。本次 V26 hunks（render profile 注释+postpass 注释+预置块 :1986-2160+两路由+两生产调用点）干净。
- P3-① 预置 `source` 已诚实注明“联网检索到方法但未获现成对表”（各 json :5），接受现状；后续若获权威对表可增量校准条目（尤其 `净利绿→净利润` 类 绿/率 派生对），当前低频长串误伤面小，不动。
