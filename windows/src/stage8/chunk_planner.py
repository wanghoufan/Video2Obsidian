"""S8-T02 ChunkPlanner pure split (size 600s, overlap 2s, core ownership).

Pure function over duration only: VAD output never shapes boundaries.
Chunk audio cutting in S8-T04 reuses these boundaries verbatim.
"""

from __future__ import annotations

import math

CHUNK_SIZE_S = 600
CHUNK_OVERLAP_S = 2
CHUNK_STRATEGY = "core-region-ownership"


class ChunkPlanError(ValueError):
    """Raised on illegal duration or size/overlap deviation."""


def chunking_profile() -> dict:
    """Frozen chunking档位 record for the ASR profile layer."""
    return {
        "size_s": CHUNK_SIZE_S,
        "overlap_s": CHUNK_OVERLAP_S,
        "strategy": CHUNK_STRATEGY,
        "unit": "seconds",
    }


def plan_chunks(duration_s, size_s=CHUNK_SIZE_S, overlap_s=CHUNK_OVERLAP_S) -> list:
    """Split duration into overlapped chunks with core region ownership.

    Each item is ``{index, start_s, end_s, core_start_s, core_end_s}``:
    neighbours share exactly ``overlap_s`` seconds while core regions
    partition ``[0, duration)`` seamlessly with no overlap. Short audio
    (<= one size) yields exactly one chunk. Zero/negative/NaN/inf
    durations are refused (fail-closed), as is any size/overlap value
    beside the frozen 600/2 pair. Zero engine contact by construction.
    """
    if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)):
        raise ChunkPlanError("duration_s must be a number, got %r" % (duration_s,))
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ChunkPlanError(
            "duration_s must be finite and positive, got %r" % (duration_s,)
        )
    if size_s != CHUNK_SIZE_S or overlap_s != CHUNK_OVERLAP_S:
        raise ChunkPlanError(
            "size/overlap frozen to %r/%r, got %r/%r"
            % (CHUNK_SIZE_S, CHUNK_OVERLAP_S, size_s, overlap_s)
        )
    duration = float(duration_s)
    step = size_s - overlap_s
    if duration <= size_s:
        bounds = [(0.0, duration)]
    else:
        count = 1 + int(math.ceil((duration - size_s) / step))
        bounds = []
        for i in range(count):
            start = float(i * step)
            end = start + size_s if i < count - 1 else duration
            bounds.append((start, float(end)))
    out = []
    last = len(bounds) - 1
    for i, (start, end) in enumerate(bounds):
        core_start = 0.0 if i == 0 else start + overlap_s
        core_end = end if i == last else bounds[i + 1][0] + overlap_s
        out.append(
            {
                "index": i,
                "start_s": round(start, 3),
                "end_s": round(end, 3),
                "core_start_s": round(core_start, 3),
                "core_end_s": round(core_end, 3),
            }
        )
    return out
