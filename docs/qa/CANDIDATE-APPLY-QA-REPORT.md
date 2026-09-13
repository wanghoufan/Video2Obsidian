
# BUGS

## 测试结论

qa 回来了：**PASS，0 个未解决缺陷**。

- 测试对象：`GET /api/vocab/candidates`、`POST /api/vocab/candidates/apply`（含 `all:true` 重跑联动）、`app/index.html` 待审清单静态走读。
- 测试方式：按 `tests/selftest_v26_presets.py` 的 `load_server()` 方式直接 import `app/server.py` 并调用 handler；重跑函数仅用 stub 捕获调用参数。
- 数据边界：所有数据均为 `mktemp` 外置 tmp 目录中的合成候选；未触碰 `src`、用户真实目录、Obsidian 库；未启动浏览器。
- 结果：原 26 项回归检查 26 PASS；另加 `codesummary` 三路径与 P2 标记聚焦检查 4 PASS；本轮 P0 vault 透传聚焦 6 PASS，共 36 PASS、0 FAIL。

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| CANDIDATE-001 | P1 | 否 | 混合候选 apply 后检查响应对象 | 已修复并复测通过 | 候选 apply 验收 | builder 已补 `codesummary`；混合 apply、零导入、结果列表统计、summary 回退四项均通过 |

## 已验证通过

- GET 返回 `200 + ok`，候选按 `high/medium/low` 分组并保留原始 index。
- 脏数据逐条拒收并注明原因：单字、纯标点、重复错词、撞基表 `Github`、超长 129 字、越界 index、重复 index 均有明确中文原因。
- 合法候选落盘到外置 `vocab-user.json`，返回用户 revision（`s9-corr-v2-user-*`）。
- apply 成功后候选文件接受项被标记 `imported:true`，再次 GET 不再返回接受项。
- 重跑联动已捕获，调用参数准确为 `{"data_root":"<tmp>","all":true}`；stub 返回无失败时 apply summary 正确。
- `codesummary` 三路径通过：零导入返回 `导入0条/重跑成功0篇/跳过0篇/失败0篇`；按 `results` 列表统计成功/跳过/失败；无 results 时按 `summary` 回退统计。
- P2 标记逻辑通过：标记失败时保留 `candidate_mark_error`、`ok:false`，`codesummary` 仍准确，候选文件未误标记。
- 空数组不导入且不触发重跑。
- 缺失候选文件、坏 JSON 均 GET `200 + ok`，返回空清单并保持人话 fail-open。
- `app/index.html` 静态存在 `candidateBox`、全选框、apply 按钮、候选列表、提示节点，以及两个 API 路径和对应加载/提交逻辑。
- `app/server.py` 使用外置 tmp `cfile` 执行 `py_compile` 通过。

## 本轮 P0 聚焦复测（apply 透传 `ob_vault_root`）

- 有 vault：apply 成功，捕获到重跑请求精确包含 `data_root`、`all:true`、`ob_vault_root`；模拟返回 `PUBLISHED` / `vault_updated:true` 的笔记更新成功结果被保留，汇总为成功 1 篇。
- 无 vault：重跑请求保持旧行为，仅包含 `data_root`、`all:true`，不透传 `ob_vault_root`；返回汇总明确提示“未给笔记库，库内笔记未更新”，同时成功计数与 `codesummary` 正确。
- 本轮结果：6 项 PASS、0 FAIL；未写入 vault。

## 未执行 / 限制

- 未启动浏览器，因此 UI 仅完成读码走读与节点存在性检查，不宣称真实点击、渲染或网络交互通过。
- 未执行真实全量重跑；为避免构造状态库和真实任务，使用 stub 验证 apply 对 `_handle_reapply_post` 的联动调用及参数。

## Fix Attempt Fingerprint

- Task ID: candidate-apply-qa-2026-09-13
- Root Cause Hypothesis: apply 响应组装只返回 `summary`，未补充验收约定的 `codesummary` 字段。
- Approach: load_server 直接 handler 黑盒调用；合成候选覆盖合法、脏数据、边界和文件异常；stub 捕获重跑请求；静态读取 HTML。
- Files Changed: 仅新增本报告。
- Verification: 原轮 26 项中 25 PASS、1 FAIL；前轮修复后 30 项全 PASS；本轮 P0 聚焦 6 项全 PASS；无业务代码改动。
- Failure Reason: 上轮 `POST /api/vocab/candidates/apply` 响应缺少 `codesummary`；本轮已复测关闭。
- Difference From Previous Attempt: builder 新增 `ob_vault_root` 透传；本轮验证有 vault 更新成功与无 vault 旧行为/人话汇总均无退化。`py_compile` 继续使用外置 tmp `cfile`，避开 macOS 默认缓存路径权限限制。
