"""Stage2: Candidate / Source / Processing Run + central SQLite + lock.

S2-T01 store (central DB skeleton) -> S2-T02 candidate (lifecycle) ->
S2-T03 source (Exactly Once promotion) -> S2-T04 runs (AUTO identity) ->
S2-T05 two-layer dedup assembly (discover + reconcile_*) -> S2-T06
instance (Single Instance + startup subset). src/stage1/ is reused
read-only (sha256_file / probe_volume); never modified here.
"""

from stage2.candidate import active_count, discover, reject_candidate
from stage2.instance import (
    acquire,
    check_static_preflight,
    gate_roots,
    holds_lock,
    recovery_bootstrap,
    release,
    startup,
)
from stage2.runs import (
    create_manual_reprocess,
    get_or_create_auto_run,
    get_run,
    mark_failed_retryable,
    mark_no_speech,
    reconcile_run,
    reconcile_source,
)
from stage2.source import promote_candidate, upsert_source
from stage2.store import (
    LockNotHeldError,
    assert_no_transcription_states,
    assert_stage3_tables_empty,
    central_db_path,
    count_auto_runs,
    count_sources,
    init_db,
    lock_path,
    open_db,
    table_counts,
)

__all__ = [
    "LockNotHeldError",
    "acquire",
    "active_count",
    "assert_no_transcription_states",
    "assert_stage3_tables_empty",
    "central_db_path",
    "check_static_preflight",
    "count_auto_runs",
    "count_sources",
    "create_manual_reprocess",
    "discover",
    "gate_roots",
    "get_or_create_auto_run",
    "get_run",
    "holds_lock",
    "init_db",
    "lock_path",
    "mark_failed_retryable",
    "mark_no_speech",
    "open_db",
    "promote_candidate",
    "reconcile_run",
    "reconcile_source",
    "recovery_bootstrap",
    "reject_candidate",
    "release",
    "startup",
    "table_counts",
    "upsert_source",
]
