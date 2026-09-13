
# BUGS

## 测试结论

qa 回来了：**PASS，0 个缺陷**。

- 测试对象：待审三组折叠与默认勾选、`rerun_old` 二选一及缺字段兼容、预置查看/停用开关、P2 `effective_revision`。
- 测试方式：按 `tests/selftest_v26_presets.py` 的 `load_server()` 方式直接 import `app/server.py` 并调用 handler；重跑仅用 stub 捕获参数。
- 数据边界：仅使用外置 `mktemp` tmp 目录与合成候选/合成预置文件；未触碰 `src`、用户真实目录、Obsidian 库；未启动浏览器。
- 结果：21 项检查 21 PASS、0 FAIL。

| Bug ID | Priority | Stage P0 Blocking? | Repro | Status | Current Task | 备注（截图/日志一句） |
|---|---|---:|---|---|---|---|
| — | — | 否 | — | 无 | CANDIDATE-UI2 黑盒复测 | 本轮未发现缺陷 |

## 已验证通过

- `GET /api/vocab/candidates` 正确返回 high/medium/low 三组及原始 index。
- UI 走读确认三组使用折叠节点；high/medium 默认勾选，low 默认不勾选。
- `rerun_old=false`：只导入、不调用重跑，响应明确“老稿未动”，接受项仍标记并从 GET 清单过滤。
- `rerun_old=true`：调用重跑并传 `all:true`。
- `rerun_old` 缺字段：兼容旧行为，默认按 `true` 重跑。
- 单字、纯标点、撞基表、超长、越界 index 等脏数据逐条拒收并带原因；合法项正确标记。
- 空候选文件、坏 JSON 均 fail-open 返回空清单且不报错。
- 合成预置域可查看完整词条，默认启用；坏预置文件被跳过。
- 停用开关落盘并回显 disabled 域，提示停用只影响新转写/老稿需重跑。
- 预置域启用时 `revision == effective_revision`；停用后全量 `revision` 保持不变，`effective_revision` 变化，且用户词条仍保留在返回词库中。
- UI 走读确认预置查看、全词条折叠、启用开关、保存函数及 `effective_revision` 展示节点/文案存在。

## 未执行 / 限制

- 未启动浏览器，UI 仅完成读码走读与节点存在性检查，不宣称真实点击和渲染通过。
- 未执行真实重跑或真实笔记更新；重跑链路使用 stub 验证是否调用及参数。

## Fix Attempt Fingerprint

- Task ID: candidate-ui2-qa-2026-09-13
- Root Cause Hypothesis: 本轮为功能复测，无新增缺陷假设。
- Approach: `load_server()` 直测 handler；tmp 合成三组候选、脏数据与预置域；stub 捕获 rerun 参数；静态走读 `app/index.html`。
- Files Changed: 仅新增本报告。
- Verification: 21 项 PASS、0 FAIL。
- Failure Reason: 无。
- Difference From Previous Attempt: 新增并验证三组折叠/默认选择、`rerun_old` 显式 false/true/缺字段兼容、预置域查看/停用与 `effective_revision` 分离。
