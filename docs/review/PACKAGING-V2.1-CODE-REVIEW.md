
# CODE REVIEW

- Task: 复核 app/ V2.1 改动（worker 按 input_root 前缀过滤 + SKIP 不再计数 + current/queue 进度 + 页面进度条 + runs 表 worker 终态映射 + DB run 状态不动的原因注释）
- Commit: N/A（非 git 仓库；评审对象为工作区现状 app/server.py 809行 / app/index.html 362行 / app/start.sh 现状）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 打回+改法（P0 全 PASS；P1×2 必修，见下；修完可过）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- P0-1 worker 按 input_root 前缀过滤：PASS。`_is_under_root`（server.py:103-112）realpath + `commonpath==input_real`，前缀攻击安全（实测 `input_evil`→False，同级→False，子目录→True）；`_transcribe_worker:623` 查询时过滤 + `_process_one_run:385-387` 防守二次校验，双层一致。顺带修了 V2 P3-3（跨盘 ValueError 现回 False，不再走通用通道）。
- P0-2 SKIP 不再计数：PASS（主体）。SKIP 三处（run vanished:358 / not QUEUED-AUTO:361 / 旧 input 残留:385-387）均不 `_worker_record`；调用方 `644-645 continue` + `654-656` 仅非 SKIP 进 `_worker_done`，`_count_pending:160-161` 同步排除 done，下轮查询 `625` 直接忽略。DB QUEUED 残留不再卡进度，方向正确。
- P0-3 current/queue 进度：PASS（主体）。`_worker_set_current/clear` 覆盖 发现→转写中→标准化→渲染→发布中五段（server.py:390/417/490/496/545），终态全清 + worker 退出清；`_listener_snapshot:188-198` 透出 `current + queue{pending,done}`，`_count_pending:130-169` 按前缀 + 去 done + fail-open 记 0，语义对。
- P0-4 页面进度条：PASS。`#progress/#progText/#progFill`（index.html:89-92/130）+ `renderProgress:249-269`：total=pending+done，pct 四舍五入，有 current 显示“正在X：file（已用时Ns）·排队/已完成”，无则排队/已完成/空闲三态；`textContent` 赋值无 XSS；无外部资源。
- P0-5 runs 表 worker 终态映射：PASS（主体）。`renderLock:275-278` 建 `workerMap`，`dispStatus/dispLabel:206-215` 优先 worker 态并缀“（worker）”，`renderLineage:241` 单独列 worker 终态，`stClass` 对 FAIL/BLOCK 红、QUEUED 黄、PUBLISHED/RENDER_ONLY 绿，DB 全 QUEUED 误导已解。
- P0-6 DB run 状态不动的原因注释：PASS（注释属实）。server.py:524-528 称直接写 PUBLISHED/RENDER_ONLY 会触发 `assert_no_transcription_states` FAIL；已核 `src/stage2/store.py:49-51 ALLOWED_RUN_STATUSES={QUEUED,FAILED_RETRYABLE,NO_SPEECH_DETECTED}` + `310-321` 非允许即 AssertionError，注释与实现一致。当前仅 UPDATE revision id 列（502-509）不碰 status，正确。
- P0-7 回归：PASS。`py_compile + sh -n` 双过；顶层 import 仍仅 stdlib + stage12/stage5（AST 实测）；无 `from stageX import _*` / `stageX._*` 调用；`open(w)` 仅 job 内 manifest/raw；`_handle_browse:252-253` V2 P2-1 fail-open 已修为 400（与 probe 本体 fail-closed 一致）。
- P1-1 worker 外层 except 把未知异常记 done 却无 processed 记录（静默丢任务）：server.py:638-656，`res=None` 起步，`_process_one_run` 若抛（如 `store.open_db` 锁未持 / import 失败 / makedirs 失败，均在 try 外：352/435-436/491），except 只 `note_error + clear_current`，随后 `is_skip=False` → `_worker_done.add(run_id)`。后果：该 run 永不重试，runs 表仍 QUEUED，`processed` 无条目，`queue.done` 不涨，pending 却掉了（done 排除），用户只能在 worker last_error 看一句通用话，定位不到 run。改法（二选一）：① except 内补 `_worker_record({"run_id":run_id,"state":"FAIL","verdict":"worker 异常：%s"%exc})` 再进 done；② 不进 done 留待下轮重试（需防毒丸循环，建议选①）。
- P1-2 `queue.done` 只数 DONE_STATES，FAIL/PUBLISH_BLOCKED 从进度消失：server.py:75 `DONE_STATES=(PUBLISHED,RENDER_ONLY)` + `183-184` done_n 只数此二态，但 `_worker_done` 含 FAIL 全集且 pending 已排除 done（160-161）。后果：2 成功 +1 失败 → pending=0 done=2 pct=100%，“已完成2”藏掉 1 失败；单文件 FAIL → pending=0 done=0，进度条回“空闲：暂无排队视频”，与 worker 行“已处理 1 个 FAIL”自相矛盾。V2.1 头号目标就是进度诚实，此为功能口径错。改法：`queue` 加 `failed` 字段（`processed` 中非 SKIP 非 DONE 即失败），`done=len(done_ids)` 或保持 done=成功数但 total=pending+done+failed，前端文案改为“排队X / 成功Y / 失败Z”，pct 分母用 total。

## P2 / P3 Backlog Findings

- P2-1 workerMap 仅末 20，超 20 个 run 后老 run 终态映射丢失：`_listener_snapshot:177` 只下发 `processed[-20:]`，前端 `workerMap` 仅据此建表；`processed` 上限 100、`_worker_done` 全量，`queue.done` 按全量算但映射按 20 算。21+ 文件场景下老 run 回落显示 DB QUEUED，重现 V2.1 要修的误导。改法：下发 `state_by_run: {run_id: state}` 全量小字典（≤100 项），或 processed 窗口与映射窗口对齐并注释。
- P2-2 `limit` 无上限（V2 P2-2 延续）：`_handle_status:231-233` 只 fallback 20，负数/超大透传 sqlite。改法：`limit=max(1,min(int,200))`。
- P2-3 worker 直写 `UPDATE processing_runs` 无 store 封装（V2 P2-3 延续）：server.py:502-509 手写 revision 列，schema 变即脱钩。改法：store 加 `attach_revisions()` 公开函数，或暂留直写但加行注释声明依赖列名清单。
- P2-4 `started_at` 窗口残留（V2 P2-4 延续）：POST 置 running（742-746）与 `_launch` 填 started_at（674-679）隔线程调度窗。改法：POST 加锁块内顺手填，`_launch` 不覆盖。
- P2-5 打包/启停三件（V2 P2-5 原样）：start.sh `sleep 1 + kill -0` 慢机误判→轮询 `curl /api/start`；PORT 8765 两边硬编码→注释联动；无停止接口（running latch，只能重启进程）。
- P2-6 `_listener_snapshot` 三把锁非原子（V2 P3-2 加重）：server.py:173-185 三次 `with _state_lock` 分取 listener/worker/done，高并发三半错位。改法：合并为一把锁一次快照（`_count_pending` 的 DB 读保持锁外）。
- P3-1 `esc()` 未转义单引号（V2 P3-1 延续，index.html:183）：现渲染位为文本节点 + 双引号属性，无实际 XSS；拼单引号属性前再补。
- P3-2 轮询 `threading.Event().wait(0.1)×50`（V2 P3-4 延续，server.py:657-662）：每周期 50 个 Event 对象。改法：复用单个 Event 或 `time.sleep(0.1)`。
- P3-3 `_worker_done` 无界增长：常驻 worker 跑数千文件即数千 set 项。改法：与 `processed[-100:]` 对齐裁剪，或定期落盘清理（低优）。

证据备注：`open_db(data_root)` 默认 `require_lock_held=True`（store.py:236），worker 依赖 `run_startup` 先 `mark_held`，停止后快照先查 running 再 open，无误报错链；`current_path NOT NULL`（store.py:140）故 `_count_pending` 的 `cur is None` 分支仅覆盖 LEFT JOIN 孤儿 run，语义正确。
