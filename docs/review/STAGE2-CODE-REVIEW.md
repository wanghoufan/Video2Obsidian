
# CODE REVIEW

- Task: Stage2 builder复核（src/stage2/：store.py/candidate.py/source.py/runs.py/instance.py + __init__.py，对照STAGE2-PLAN S2-T01~T07验收 + STOP EXPANSION（Stage2 only）+ G1/G2延续）
- Commit: n/a（非git仓库；复核对象为工作区src/stage2/共6文件现状）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（PASS，无P0/P1；P2×4+P3×5共9项 backlog，不卡Stage2，转后续Stage）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无。S2-T01~T06验收全过，STOP EXPANSION硬门全过，G1/G2延续全过，QA 27/27双轮exit 0旁证（见下方证据）：
  - S2-T01：中央库`<data_root>/data/state.db` 9表DDL（discovery_candidates/sources/processing_runs/artifacts/state_events全字段 + normalization_revisions/render_revisions/publish_records/archive_commits schema-only）+ `ux_auto_processing_run` §15逐字（IF NOT EXISTS为幂等前缀，语义逐字）+ 活跃Candidate Provisional Partial UNIQUE §20范围逐字（DISCOVERED/WAITING_FOR_STABLE_FILE/IDENTIFYING_SOURCE，终态不占）+ WAL + FK=ON + `open_db()`/`init_db()`获锁断言（无锁写即LockNotHeldError）。全仓仅`src/stage2/store.py`一处DDL，无第二建表点。
  - S2-T02：`discover(path)`直接API（无监听线程）+ DISCOVERED→WAITING_FOR_STABLE_FILE（size/mtime两轮稳定，抖动停留）→IDENTIFYING_SOURCE→PROMOTED主链 + MERGED（活跃Provisional冲突并入）/REJECTED（仅活跃可拒）/SOURCE_MISSING（stat失败两处映射）旁路。Candidate内无ASR/import（仅Strong SHA256 promotion hash经source→stage1.sha256_file只读）。
  - S2-T03：Strong SHA256复用`stage1.sha256_file`只读 + content_identity=`sha256:hex` + logical=`path_key|content` + `INSERT…ON CONFLICT(logical_source_identity) DO UPDATE last_seen`原子UPSERT（无SELECT-then-INSERT，冲突返回既有行）+ path_identity_key=abspath原样（无NFC/casefold/slugify）。Case 13（同path+size+mtime不同bytes）走Strong Hash产生新Source、旧行保留（QA P0-3 nsrc=2实证）。
  - S2-T04：`auto_run_identity=source_id|hash` + §15 Partial UPSERT单语句`ON CONFLICT(source_id,asr_profile_hash) WHERE creation_mode='AUTO' DO NOTHING`（其后SELECT仅取行返显，非竞争门，注释明示）+ creation_mode=AUTO落库 + MANUAL_REPROCESS仅CHECK允许值、`create_manual_reprocess()`抛NotImplementedError（§14预留语义）+ 新Run恒QUEUED（§9头，转写状态机不动）。SQL审计：runs/source两文件INSERT路径均无SELECT→不存在→INSERT竞争门（candidate的SELECT是优化预查+UNIQUE+IntegrityError回退，见P2-3备注）。
  - S2-T05：两层去重装配（Candidate层MERGED + Run层返回既有）+ `reconcile_run`（FAILED_RETRYABLE→同run_id retry_count+1不建新Run；NO_SPEECH_DETECTED→同终态行返回；QUEUED→原样返回）+ `reconcile_source`（ensure旧Run再收敛）。Triple Race三线程真并发Source=1/Run=1、NO_SPEECH×10 Count=1、RETRYABLE同id递增（QA P0-6a/b/c实证）。
  - S2-T06：`fcntl.flock LOCK_EX|LOCK_NB`于`<data_root>/data/.lock`（STORE.LOCK_RELPATH=`data/.lock`运行时断言）+ 第二实例SecondInstanceError→CLI exit 3（DB mtime纳秒级不变）+ 启动子序列Static Preflight→Acquire Lock→Open SQLite→Volume Preflight→Recovery Bootstrap五步有序（QA HAPPY-ORDER实证）+ Static Preflight纯路径事实（db_touched=False，不碰DB/不Repair/不起Worker）+ Root门复用`stage1.probe_volume`（任一非ALLOW即RootBlocked→CLI exit 2，Case 11实证）。
  - STOP EXPANSION：无Whisper/mlx/ffmpeg转写调用（全文grep零命中，转写调用恒0）+ 无threading/multiprocessing/concurrent后台监听（Race并发仅QA外部Runner线程，源码无）+ 无云/LLM/队列/向量 import（import表仅stdlib+sqlite3+fcntl+argparse+stage1只读两函数）+ Stage3+四表零写入（assert门+QA每happy库反查0/0/0/0）+ Run状态不出QUEUED/FAILED_RETRYABLE/NO_SPEECH_DETECTED（assert门）+ Watcher/Scan/Workers函数不存在 + `src/stage1/`零改（本轮非git仓库，git diff口径N/A；stage1仅被只读import sha256_file/probe_volume，无写回）。
  - G1延续：Source→Run NOT NULL链（sources.source_id先行 deterministically，processing_runs.source_id NOT NULL REFERENCES + FK=ON + 未知source IntegrityError转ValueError拒绝孤儿Run；顺序Source行先Run行后）。
  - G2延续：fstat复用（candidate存device/inode/size/mtime_ns；source promotion用stat+stage1.sha256_file；裁决只认SHA256，size/mtime仅Stable信号；identical-bytes重发现按content折叠MERGED）。
  - G3延续：仅记录未实现（archive_commits空schema，无Archive/Publish代码；current_path=path_key原样，§56-59不动）。
  - 自验：py_compile 6文件OK；禁项grep仅命中注释/列名/Stage3表名；§15/§20 DDL逐字可grep；`require_lock_held=False`逃生口内部零调用（全部写路径走默认True）。

## P2 / P3 Backlog Findings

- P2-1 source.py:85 `is_new = cur.rowcount == 1`对UPSERT不可靠（sqlite3里INSERT…ON CONFLICT DO UPDATE命中冲突时rowcount同样为1，新旧同值；返回值撒谎）。现状无调用方消费（candidate取`_is_new`丢弃），功能正确。改法：换`INSERT…ON CONFLICT DO NOTHING` + `con.total_changes()`/`changes()==1`判新旧（同等原子），或直接删is_new返回改查行比对；后续Stage有人消费前必须先修。
- P2-2 source.py:129 `promote_candidate`内`os.stat`裸抛（stable门之后文件被删→FileNotFoundError外泄，candidate永久卡在IDENTIFYING_SOURCE活跃态；后继同key重discover会被MERGED进这个孤儿行）。合成测试撞不见，真机可撞。改法：except (FileNotFoundError,OSError)→置SOURCE_MISSING+记event+commit，与candidate.py两处_missing_candidate同语义。
- P2-3 candidate.py:145-160 活跃冲突MERGED分支`run_id`恒None（带asr_profile_hash的Triple-Race loser若撞上winner仍在活跃态，返回值里看不到共享Run，只能再调一次discover/reconcile；identical-bytes MERGED分支已ensure run，前后不一致）。Count口径不受影响（QA 1/1实证），只是返回口径缺口。改法：文档注明“MERGED-active+hash调用方需重调一次取run”，或winner PROMOTED后loser侧补ensure（注意跨连接时序，宁可文档化也别加锁等待）。
- P2-4 candidate.py:227 + source.py:130 同一次discover算两遍SHA256（prior检查一遍，promote里又一遍；大视频双倍IO）。正确性无影响，纯浪费。改法：promote_candidate加可选`content_hex`入参，candidate把已算好的hex透进去，promote跳过重算（校验size未变即可）。
- P3-1 store.py:69 `Stage3WriteBlocked`定义了从未raise（Stage3+零写门实际靠QA反查+recovery_bootstrap断言，无写时触发器；类是死代码）。改法：要么删类（断言即门，注释写清），要么在各写入口加表名白名单检查并raise它，二选一别留着唬人。
- P3-2 store.py:232 `ux_sources_logical`冗余索引（logical_source_identity列已UNIQUE自带索引，再建同键UNIQUE INDEX纯占空间）。无害。改法：删该行，留列级UNIQUE即可；或注释写明“显式命名索引有意为之”。
- P3-3 source.py:65-66 `DO UPDATE SET last_seen_at`只刷last_seen（size/mtime/device/inode冻结在首次；identical-bytes MERGED路径连last_seen都不刷）。Status语义无影响，纯画像陈旧。改法：UPSERT时同步刷新size/mtime/device/inode/current_path；identical-bytes MERGED分支补一次sources.last_seen_at更新。
- P3-4 runs.py:99-100 IntegrityError一律转`ValueError("unknown source_id")`（CHECK等其它约束违规也被报成未知source，误导排障）。极罕见。改法：先查source存在性再映射，无source才报unknown，否则原样抛IntegrityError。
- P3-5 instance.py:84-86 `acquire()`先makedirs+`open(a+b)`再flock（第二实例在得知锁被占之前已触碰锁文件atime/可能建空data目录；“零写盘”实际只对DB成立）。QA以DB mtime为据，可接受。改法：注释把“零写盘”精确为“零DB/内容写（锁文件atime触碰除外）”，或把SecondInstanceError文案同步；gate_roots顺手加require_lock注释（只读无害，顺序由startup保证即可）。
