"""Stage1 specified-path ingest (S1-T01 scaffold + S1-T02 verification
+ S1-T03 frozen single-file ASR + S1-T04 post-transcription Strong verify
+ S1-T05 Raw PREPARE + S1-T06 Raw COMMIT/Immutable
+ S1-T07 Recovery Repair-Forward).

Scope: S1-T01 job-scoped namespace + minimal Logical Source registration
+ single Processing Run, plus S1-T02 pre-transcription Fast Verification
(§24), plus S1-T03 frozen ASR (temp-wav 16k mono + large-v3-turbo pinned
revision, single file direct pass, VAD observe-only), plus S1-T04
post-transcription Mandatory Strong SHA256 + G2 compare (§25,
VERIFYING_SOURCE_AFTER_TRANSCRIPTION -> COMMITTING_RAW_ASR or
BLOCKED_SOURCE_CHANGED_DURING_TRANSCRIPTION, diagnostic-only quarantine),
plus S1-T05 Raw PREPARE (§38: raw.json.tmp -> flush -> fsync(file) ->
schema validation -> expected_artifact_hash -> SQLite artifacts PREPARED
-> COMMIT transaction; non-PASS verdicts refused), plus S1-T06 Raw COMMIT
(§39: PREPARED -> atomic rename -> fsync(parent) -> final hash verify ->
manifest COMMITTED -> SQLite COMMITTED) + Immutable (§3.8: committed Raw
read-only, any further Raw write refused; final hash mismatch never valid)
+ S1-T07 Recovery (§40-41: PREPARED+Final+HashMatch Repair Forward,
PREPARED+tmp-only continue Commit, Truth Model hard-coded, zero ASR).
T08 (Acceptance) is explicitly NOT implemented here (STOP EXPANSION).
"""

from .asr import (
    FROZEN_MODEL_REPO,
    FROZEN_MODEL_REVISION,
    run_asr_single_file,
    run_job as run_asr_job,
)

from .commit import (
    STATE_COMMITTED as COMMIT_STATE,
    CommitError,
    CommitRefused,
    RawImmutableError,
    assert_raw_mutable,
    commit_raw,
    guarded_open_raw_for_write,
    is_committed,
)
from .ingest import (
    G1Violation,
    VolumeBlocked,
    create_run,
    fstat_capture,
    ingest_specified_path,
    probe_volume,
    register_source,
    sha256_file,
)
from .post_verify import (
    BLOCK_CODE as POST_BLOCK_CODE,
    PASS_NEXT as POST_PASS_NEXT,
    STATE as POST_STATE,
    PostVerifyError,
    count_formal_raw_commits,
    quarantine_to_diagnostic,
    resolve_fstat_before,
    verify_source_after_transcription,
)
from .prepare import (
    ARTIFACT_TYPE_RAW as PREPARE_ARTIFACT_TYPE,
    STATE_PREPARED as PREPARE_STATE,
    PrepareError,
    PrepareRefused,
    build_raw_content,
    prepare_raw,
    validate_raw_artifact,
)
from .recovery import (
    RECOVER_RECEIPT_NAME as RECOVER_RECEIPT,
    RecoveryError,
    RecoveryRefused,
    recover_raw,
)
from .verify import (
    BLOCK_CODE,
    STATE,
    SourceRecordError,
    gate_transcription,
    load_source_record,
    verify_source_for_transcription,
)

__all__ = [
    "BLOCK_CODE",
    "COMMIT_STATE",
    "FROZEN_MODEL_REPO",
    "FROZEN_MODEL_REVISION",
    "G1Violation",
    "POST_BLOCK_CODE",
    "POST_PASS_NEXT",
    "POST_STATE",
    "PREPARE_ARTIFACT_TYPE",
    "PREPARE_STATE",
    "STATE",
    "CommitError",
    "CommitRefused",
    "PostVerifyError",
    "PrepareError",
    "PrepareRefused",
    "RawImmutableError",
    "RecoveryError",
    "RecoveryRefused",
    "SourceRecordError",
    "VolumeBlocked",
    "assert_raw_mutable",
    "build_raw_content",
    "commit_raw",
    "count_formal_raw_commits",
    "create_run",
    "fstat_capture",
    "gate_transcription",
    "guarded_open_raw_for_write",
    "ingest_specified_path",
    "is_committed",
    "load_source_record",
    "prepare_raw",
    "probe_volume",
    "quarantine_to_diagnostic",
    "recover_raw",
    "register_source",
    "resolve_fstat_before",
    "run_asr_job",
    "run_asr_single_file",
    "sha256_file",
    "validate_raw_artifact",
    "verify_source_after_transcription",
    "verify_source_for_transcription",
]
