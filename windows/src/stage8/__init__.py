"""Stage8 VAD advisory + Chunk + Absolute Timeline (S8-T01~T04)."""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage8.vad import (
    VAD_ENGINE,
    VAD_MODE,
    VAD_THRESHOLDS,
    VadError,
    is_advisory_only,
    observe_vad,
    observe_vad_all,
    vad_profile,
)
from stage8.chunk_planner import (
    CHUNK_OVERLAP_S,
    CHUNK_SIZE_S,
    CHUNK_STRATEGY,
    ChunkPlanError,
    chunking_profile,
    plan_chunks,
)
from stage8.timeline import (
    TimelineError,
    check_monotonic,
    to_absolute,
)
from stage8.merge import (
    PRIORITY,
    MergeError,
    merge_chunks,
)
from stage8.transcribe_chunks import (
    WORKER,
    ChunkTranscribeError,
    assert_asr_layer_only,
    build_chunk_asr_profile,
    chunk_asr_profile_hash,
    chunk_asr_profile_hash_input,
    frozen_alignment,
    run_chunks,
)

__all__ = [
    "CHUNK_OVERLAP_S",
    "CHUNK_SIZE_S",
    "CHUNK_STRATEGY",
    "PRIORITY",
    "VAD_ENGINE",
    "VAD_MODE",
    "VAD_THRESHOLDS",
    "WORKER",
    "ChunkPlanError",
    "ChunkTranscribeError",
    "MergeError",
    "TimelineError",
    "VadError",
    "assert_asr_layer_only",
    "build_chunk_asr_profile",
    "check_monotonic",
    "chunk_asr_profile_hash",
    "chunk_asr_profile_hash_input",
    "chunking_profile",
    "frozen_alignment",
    "is_advisory_only",
    "merge_chunks",
    "observe_vad",
    "observe_vad_all",
    "plan_chunks",
    "run_chunks",
    "to_absolute",
    "vad_profile",
]
