"""Stage5: Watch First + Startup Scan + Reconciliation.

Implements STAGE5-PLAN S5-T01..S5-T05 (V1.8 Stage 5):
  - watcher (S5-T01): real watchdog Observer, delivery-only entries.
  - scan (S5-T02): full补扫 behind the Watcher Ready gate.
  - reconcile (S5-T03): initial + periodic対账 over ``reconcile_*``.
  - startup (S5-T04): 11-step assembly to RUNNING + delivery workers.
  - This package (S5-T05): assembly exports + thread-safety复核 helper
    (``triple_race_deliver`` fires the three routes concurrently against
    one file; it adds no persistence semantic of its own —收口 stays
    inside ``discover`` + AUTO UPSERT).

Additive-only w.r.t. Stages 1-4: this package imports ``stage2``
read-only; it never modifies
``src/stage1-4`` and never invokes any later-stage
execution.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import runs as _runs  # noqa: E402
from stage2.candidate import discover as _default_deliver  # noqa: E402

from stage5.reconcile import initial_reconcile, periodic_reconcile  # noqa: E402
from stage5.scan import startup_scan  # noqa: E402
from stage5.startup import (  # noqa: E402
    STARTUP_ORDER,
    DeliveryWorkers,
    run_startup,
    shutdown,
)
from stage5.watcher import (  # noqa: E402
    DEBOUNCE_S,
    VIDEO_SUFFIXES,
    Watcher,
    WatcherNotReadyError,
    canonical,
    find_ready,
    is_video_path,
    iter_video_files,
    start_watch,
)


def triple_race_deliver(
    path: str,
    data_root: str,
    asr_profile_hash: str,
    watcher: Watcher | None = None,
    rounds: int = 5,
) -> dict:
    """Fire the three discovery routes concurrently (S5-T05复核 helper).

    Each round submits three callables at once: the watcher route
    (``watcher.deliver`` when a watcher is given, else a direct
    ``discover`` call standing in for an event投递), the scan route
    (direct ``discover``), and the reconcile route (``discover`` followed
    by ``reconcile_source``收口). No new persistence semantic is added;
    callers assert Source=1 / AUTO Run=1 by direct central-DB count.
    """
    data_abs = os.path.abspath(data_root)
    path_abs = canonical(path)

    def _watch_route():
        if watcher is not None:
            return {"route": "watch", "result": watcher.deliver(path_abs)}
        return {
            "route": "watch",
            "result": _default_deliver(path_abs, data_abs, asr_profile_hash),
        }

    def _scan_route():
        return {
            "route": "scan",
            "result": _default_deliver(path_abs, data_abs, asr_profile_hash),
        }

    def _reconcile_route():
        delivered = _default_deliver(path_abs, data_abs, asr_profile_hash)
        run = None
        source_id = delivered.get("source_id") if isinstance(delivered, dict) else None
        if source_id:
            run = _runs.reconcile_source(
                source_id, asr_profile_hash, data_abs, "triple-race复核"
            )
        return {"route": "reconcile", "result": delivered, "run": run}

    outcomes: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for _ in range(rounds):
            futures = [
                pool.submit(_watch_route),
                pool.submit(_scan_route),
                pool.submit(_reconcile_route),
            ]
            for future in futures:
                try:
                    outcomes.append({"ok": True, "detail": future.result(),
                                     "error": None})
                except Exception as exc:
                    outcomes.append({"ok": False, "detail": None,
                                     "error": repr(exc)})
    return {"path": path_abs, "rounds": rounds, "outcomes": outcomes}


__all__ = [
    "DEBOUNCE_S",
    "STARTUP_ORDER",
    "VIDEO_SUFFIXES",
    "DeliveryWorkers",
    "Watcher",
    "WatcherNotReadyError",
    "canonical",
    "find_ready",
    "initial_reconcile",
    "is_video_path",
    "iter_video_files",
    "periodic_reconcile",
    "run_startup",
    "shutdown",
    "start_watch",
    "startup_scan",
    "triple_race_deliver",
]
