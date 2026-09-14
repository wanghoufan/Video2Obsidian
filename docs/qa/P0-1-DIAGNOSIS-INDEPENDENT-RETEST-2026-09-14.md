# QA 独立复验报告：P0-1 诊断接口

- 日期：2026-09-14
- 基线：`PRODUCT_PLAN_V1.3`
- 范围：`app/server.py` 的 `GET /api/failures/diagnosis`（直接 handler 复验）
- 数据边界：新建系统 tmp 合成库；未触碰真实目录/vault，未启动或重启 8765，未写业务代码
- 总结：**FAIL**

## 验证结果

| 项目 | 结果 | 证据 |
|---|---|---|
| data_root 隔离 | PASS | handler 输入库位于系统 tmp；未使用默认库或真实库 |
| 成功项隔离（D-8） | PASS | 合成 61 条 `SUCCEEDED`，响应 `items=23`，61 条均未进入 items/counts |
| 16 条源位置项 | PASS | 16 条原路径缺失、替代身份 MATCH，均为 `SOURCE_LOCATION_REVIEW`；`source_location_review=16`、`alternate_identity_matches=16` |
| counts 口径 | PASS（已覆盖维度） | `incomplete_or_blocked_total=23`、`auto_retryable_failure_count=3`、`will_call_whisper_count=1`；REUSE/PUBLISH 不计 whisper |
| 七类三轴不互盖 | **FAIL** | `FAILED_PUBLISH_PERMISSION` 被归为 `PRECONDITION_BLOCKED / PERMISSION_OR_SANDBOX / SYSTEM`，未归为 `PUBLISH_BLOCKED / PUBLISH_PERMISSION / PUBLISH`；7 类合成行未保持预期独立分类 |
| 重复诊断稳定性（D-3） | PASS | 两次调用 `diagnosis_snapshot_id` 与所有 `state_fingerprint` 相同 |
| 零副作用（D-3） | PASS | handler 前后 tmp 库、manifest、输入文件的大小/mtime/SHA-256 全部不变；Whisper 未调用 |
| 脱敏 | **FAIL** | 返回顶层 `data_root` 为系统绝对路径；响应绝对路径扫描命中。该字段虽可供页面本机使用，但不满足本次“脱敏零绝对路径”验收口径 |

## BUG

| Bug ID | 优先级 | 复现 | 现象 |
|---|---|---|---|
| QA-P0-1-001 | P0 | 在 tmp 合成 `processing_runs.status=FAILED_PUBLISH_PERMISSION` 后调用诊断接口 | `_diag_action` 先命中 permission/precondition 分支，发布权限场景被错误分类为 `PRECONDITION_BLOCKED`，违反 D-2 七类双轴独立分类 |
| QA-P0-1-002 | P1 | 任意 tmp `data_root` 调用诊断接口并扫描完整 JSON | 响应顶层 `data_root` 回显绝对路径；本次零绝对路径验收不通过 |

## 限制与备注

- 为遵守“禁碰真实目录/vault”，替代路径扫描在测试进程内限定为 tmp 合成候选；身份比对、分类与回包逻辑仍走 `app/server.py` 实现。
- 未进行真机 UI Canary；本任务仅验 server 诊断接口。
