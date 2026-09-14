# P0-2 Recovery QA｜2026-09-14

## 结论

**PASS**。本轮为进程内逻辑复验；未启动服务、未访问 8765，未扫描真实 `~/Downloads`，未触碰真实目录或 vault，未修改业务代码。

## 覆盖与结果

- 临时候选路径桩：身份匹配 `MATCH`，分类为 `SOURCE_LOCATION_REVIEW`。
- dry-run：选中 77 条，`61 eligible + 16 excluded`；汇总可由逐项结果复算；三策略为 `RETRANSCRIBE=20`、`REUSE_DERIVED=20`、`PUBLISH_ONLY=21`。
- 批量执行：仅确认 61 条 eligible 项，三策略均正确分发；终态汇总 61 recovered、`whisper_calls=0`。
- 幂等：同 token 返回同一 job，`idempotent=true`，未重复执行。
- 快照/安全门：状态漂移、token 过期、跨 data_root 均返回 `409`，零执行。
- 中断：`RUNNING` job 读取后转为 `INTERRUPTED` 并持久化，不自动续跑。
- No-Clobber：既有 canonical 目标返回 `SKIPPED`，原有内容保持不变。
- RETRANSCRIBE 两路：坏/空源为 `FAILED`，可读源为 `NEEDS_HUMAN`；两路均 `whisper_calls=0`。
- 真实 `_diag_alternate_paths`：使用 tmp 深目录夹具，返回约 **54.2ms**、0 候选；超预算 fail-closed。

## BUG

无新增 BUG。

## 备注

真实 16 条和 61 条业务数据未直接读取；按本轮约束使用进程内诊断桩和 tmp 合成夹具复验逻辑契约。未进行真机 UI QA，本报告不宣称真机通过。
