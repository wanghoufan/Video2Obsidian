
# CODE REVIEW

- Task: Stage1 builder复核（src/stage1/：ingest.py/verify.py/asr.py/post_verify.py/prepare.py/commit.py/recovery.py + __init__.py，对照STAGE1-PLAN S1-T01~T07验收 + V1.8 STOP EXPANSION + G1/G2/G3）
- Commit: n/a（非git仓库；复核对象为工作区src/stage1/共8文件现状）
- Reviewer: code-reviewer（opencode-go/glm-5.3-flash）
- Result: 过（PASS，无P0/P1；P2/P3共6项 backlog，不卡Stage1，转QA/T08与后续Stage）

> Dispatch / Evidence ID 系字段 2.0 已废弃，不填。

## P0 / P1 Findings

- 无。S1-T01~T07验收全过，STOP EXPANSION硬门全过，G1/G2/G3全过（见下方证据）：
  - S1-T01：指定路径ingest + job-scoped namespace（source.json/run.json/manifest.json/raw/占位+job.sqlite）+首次Strong SHA256即content_identity + G1先Source后Run（无Source/无source.json/creation_mode=AUTO即G1Violation FAIL；namespace偏离即FAIL结构对不上）。Volume门：iCloud标记/nfs-smbfs-afpwebdav-fuse/缺local旗/mount不可读一律BLOCK fail-closed。
  - S1-T02：VERIFYING_SOURCE_FOR_TRANSCRIPTION按§24（fstat不变→PASS不重算；变化→重SHA256；mismatch→BLOCKED_SOURCE_CHANGED_BEFORE_TRANSCRIPTION不进ASR）。gate_transcription仅PASS调一次，BLOCK时asr_calls=0（计数stub实测）。
  - S1-T03：冻结值硬常量（large-v3-turbo@a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb、temp-wav 16k mono落盘可重跑、word默认OFF偏离无S1_T03_WORD_ON_DECLARED=1即FAIL、nst 0.6偏离即FAIL、revision走HF cache refs/main比对从不下载mismatch即FAIL）。单文件直转一次transcribe、无切分、无prompt装配（initial_prompt=None/prompt_chars=0/chunk.executed=False/prompt.executed=False仅记录）、worker=1串行、VAD advisory-only（filtering_applied恒False，失败SKIPPED不BLOCK，转写吃完整wav）。
  - S1-T04：转写后无条件重算SHA256（fstat不变也不跳过，Case8杀手）+前后fstat对比仅信号、裁决只认SHA256（§3.5）。相等→COMMITTING_RAW_ASR，不等/不可读→BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION。BLOCK产物只进diagnostic_only/BLOCK码+DIAGNOSTIC-ONLY单文件，不碰raw/manifest/sqlite；count_formal_raw_commits只认raw/raw.json+manifest COMMITTED，During-BLOCK恒Raw Commit=0。
  - S1-T05：门控T04 PASS四件套（verdict/code/commit_authorized/hash_match）任一不符即PrepareRefused（exit 2），BLOCK永不到tmp。顺序tmp→flush→fsync(file)→重读+schema validation→expected_artifact_hash→SQLite artifacts PREPARED单事务COMMIT→一致性复验→PREPARED Receipt。validation缺失/expected未持久化/SQLite-vs-tmp不一致即FAIL（tmp unlink清理；final已存在即FAIL，T05永不建final）。
  - S1-T06：PREPARED→验tmp hash→atomic rename→fsync(parent)→验final hash→Manifest COMMITTED→SQLite COMMITTED→chmod 0444+Receipt。Final!=Expected永不有效FAIL。幂等：已COMMITTED+final有效→幂等成功+补manifest；PREPARED+final有效→Repair Forward；tmp+final双缺→FAIL不编造。Immutable：0444 + assert_raw_mutable/is_committed（SQLite COMMITTED或manifest COMMITTED或0444只读）+ guarded_open，改已COMMITTED Raw拒绝且hash不变。
  - S1-T07：Truth Model硬编码（Filesystem Valid+Expected Hash=Truth；SQLite恒落后方只许Repair Forward）。PREPARED+Final+Match→补Manifest/SQLite；PREPARED+tmp-only→验tmp后委托commit_raw（顺序不分叉）；双缺/Final mismatch/收敛tmp分叉一律FAIL不COMMIT。零ASR（无asr/ffmpeg import，成功结果asr_calls==0/whisper_calls==0）。kill-9（rename后manifest前杀）与SQLite落后（COMMITTED文件在但SQLite仍PREPARED）均Repair Forward，Whisper计数不变。
  - STOP EXPANSION：rg全仓查无pipe（ffmpeg仅文件到文件单调用）、无多worker（无threading/multiprocessing/concurrent/Pool，worker恒1）、无VAD过滤（vad结果永不回灌音频选择）、无ChunkMerge（仅记录size/overlap+executed=False）、无完整PromptBuilder（initial_prompt=None+executed=False）、无云/LLM（重型import仅mlx_whisper/numpy/silero且懒加载venv内，无requests/openai/http）、无Archive/Publish/Watch-Scan-Reconcile实现（仅注释/隔离警告提及）。T08未实现（__init__明示STOP）。
  - G1：Source→Run NOT NULL链（validate_source_record + source.json落盘存在性 + SQLite FK sources→processing_runs，顺序Source行先Run行后单事务）。
  - G2：fstat_capture（device/inode/size/mtime_ns）T01采集、T02/T04/ASR复用同一函数；ASR记before/after；T04记before/after+stored/after双diff但裁决只认SHA256；Case8（同size+同mtime_ns不同bytes）实测BLOCK。
  - G3：仅记录未实现（无Archive/Publish代码，commit/recovery均未提前实现）。
  - 自验：py_compile 8文件OK；rg禁项仅命中注释/iCloud-BLOCK必需标记；/tmp隔离功能冒烟全过（T01→T02 happy/BLOCK+gate0→T04 happy/Case8-BLOCK→T05 OK/Refuse-BLOCK→T06 OK/Immutable/Final-mismatch FAIL→T07 kill-9修复/SQLite落后修复asr0→diagnostic隔离RawCommit0）；CLI exit码PASS=0/BLOCK=2/REFUSED=2与ingest/verify/post_verify一致，QA可按exit码判坏例。

## P2 / P3 Backlog Findings

- P2-1 prepare.py:391 `open(tmp_path,"rb").read()`未用with（fd未显式关；功能正确，资源整洁度问题；改法：换`with open(...) as fh: fh.read()`，与文件内其它读写一致）。
- P2-2 commit.py:233 `target = tmp_path if "tmp" in artifact_id or True else final_path`恒为真死条件（行为安全：恒选tmp即唯一合法预COMMIT写位；改法：删`or True`分支或直写`target = tmp_path`并注释“COMMITTED后无合法写位”）。
- P2-3 ingest T01的source.json/run.json/manifest.json/SQLite写盘无fsync（raw路径§38/39的fsync已做，T01无此验收；改法：后续Stage统一落盘耐久策略时再收紧，本Stage不改）。
- P2-4 ingest init_sqlite用INSERT OR REPLACE（同source_id重ingest覆盖而非报错；Stage2去重/Exactly Once拥有该语义，本Stage保持现状；改法：Stage2收紧为INSERT+冲突显式FAIL）。
- P3-1 verify.py:11 docstring拼写“Sinneue duplication”（纯注释typo；改法：改“no duplicate”）。
- P3-2 `python -m src.stage1.*`触发RuntimeWarning（包先import后exec的双载警告，功能无影响；改法：后续要消警告再动CLI包装，本Stage不动）。
