"""S5-T03: Reconcile Third —补漏対账 over FS/DB state.

Implements STAGE5-PLAN S5-T03 only:
  - ``initial_reconcile`` (startup chain) and ``periodic_reconcile``
    (repeatable补漏) share one semantic: enumerate the synthetic input
    root's live video files, deliver each through the ``discover`` entry
    (missed files are thereby补回), then converge the AUTO run of every
    delivered source through ``runs.reconcile_source``:
      - FAILED_RETRYABLE -> same run_id, retry_count+1, no new run;
      - NO_SPEECH_DETECTED -> the same terminal row back, nothing new;
      - QUEUED -> returned unchanged.
  - Files still inside the Stable gate (WAITING, no source yet) are left
    alone for a later round; swallowed deliveries (None) are skipped.
  - Reconciliation never advances execution itself: the only run mutation
    it can produce is the retry_count+1 defined above.

Additive-only: imports ``stage2`` + ``stage5.watcher`` read-only; never
touches ``src/stage1-4`` files.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import runs as _runs  # noqa: E402
from stage2.candidate import discover as _default_deliver  # noqa: E402

from stage5.watcher import canonical, iter_video_files  # noqa: E402


def _reconcile_once(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver,
    reason: str,
) -> list:
    if not asr_profile_hash:
        raise ValueError("asr_profile_hash must be a non-empty frozen hash string")
    input_abs = canonical(input_root)
    data_abs = os.path.abspath(data_root)
    if not os.path.isdir(input_abs):
        raise ValueError("input_root is not a directory: %r" % (input_abs,))
    items: list[dict] = []
    for full in iter_video_files(input_abs, data_abs):
        try:
            delivered = on_deliver(full, data_abs, asr_profile_hash)
            deliver_error = None
        except Exception as exc:
            items.append(
                {"path": full, "delivered": None,
                 "deliver_error": repr(exc), "run": None}
            )
            continue
        run = None
        source_id = None
        if isinstance(delivered, dict):
            source_id = delivered.get("source_id")
        if source_id:
            try:
                run = _runs.reconcile_source(
                    source_id, asr_profile_hash, data_abs, reason
                )
            except Exception as exc:
                items.append(
                    {"path": full, "delivered": delivered,
                     "deliver_error": "run-converge: %r" % (exc,), "run": None}
                )
                continue
        items.append(
            {"path": full, "delivered": delivered,
             "deliver_error": deliver_error, "run": run}
        )
    return items


def initial_reconcile(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver=None,
) -> list:
    """One reconciliation pass for the startup chain (see module docstring)."""
    return _reconcile_once(
        input_root, data_root, asr_profile_hash,
        on_deliver or _default_deliver, "initial-reconciliation",
    )


def periodic_reconcile(
    input_root: str,
    data_root: str,
    asr_profile_hash: str,
    on_deliver=None,
) -> list:
    """Repeatable补漏 pass with identical semantics (see module docstring)."""
    return _reconcile_once(
        input_root, data_root, asr_profile_hash,
        on_deliver or _default_deliver, "periodic-reconciliation",
    )
