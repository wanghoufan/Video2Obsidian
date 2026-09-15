"""S5-T02: Scan Second — full recursive补扫 after Watcher Ready.

Implements STAGE5-PLAN S5-T02 only:
  - ``startup_scan`` runs only after the Watch First gate: a Ready watcher
    for the same input root must exist (passed explicitly or registered by
    ``start_watch``); otherwise ``WatcherNotReadyError`` is raised and no
    file is touched. Order inversion (Scan before Ready) is a hard error.
  - The scan enumerates every layer of the synthetic input root and delivers
    each video file through the ``discover`` entry. This module keeps no
    seen-set of its own: repeat scans converge inside ``discover`` (identical
    bytes fold to MERGED; changed bytes under a reused provisional key open
    a new logical source, Case 13). Any "same path skip" logic here is a
    FAIL by plan, so there is none.
  - An empty directory returns an empty list (not an error).

Additive-only: imports ``stage2`` + ``stage5.watcher`` read-only; never
touches ``src/stage1-4`` files.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2.candidate import discover as _default_deliver  # noqa: E402

from stage5.watcher import (  # noqa: E402
    WatcherNotReadyError,
    canonical,
    find_ready,
    is_video_path,
    iter_video_files,
)


def _resolve_watcher(input_root: str, watcher=None):
    if watcher is not None:
        if not watcher.is_ready():
            raise WatcherNotReadyError(
                "startup_scan refused: watcher not Ready for %r "
                "(Watch First before Scan Second)" % (os.path.abspath(input_root),)
            )
        return watcher
    found = find_ready(input_root)
    if found is None:
        raise WatcherNotReadyError(
            "startup_scan refused: no Ready watcher for %r "
                "(Watch First before Scan Second)" % (os.path.abspath(input_root),)
        )
    return found


def startup_scan(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    watcher=None,
    on_deliver=None,
) -> list:
    """Full recursive scan delivering every video file via ``discover``.

    Returns one ``{"path", "result", "error"}`` item per file, in sorted
    order. Per-file failures are recorded (not swallowed silently — callers
    assert the error column is clean); the scan continues past them so one
    bad file cannot hide the rest.
    """
    _resolve_watcher(input_root, watcher)
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
    deliver = on_deliver or _default_deliver
    input_abs = canonical(input_root)
    data_abs = os.path.abspath(data_root)
    if not os.path.isdir(input_abs):
        raise ValueError("input_root is not a directory: %r" % (input_abs,))
    items: list[dict] = []
    for full in iter_video_files(input_abs, data_abs):
        assert is_video_path(full)
        try:
            result = deliver(full, data_abs, asr_profile_hash)
            items.append({"path": full, "result": result, "error": None})
        except Exception as exc:
            items.append({"path": full, "result": None, "error": repr(exc)})
    return items
