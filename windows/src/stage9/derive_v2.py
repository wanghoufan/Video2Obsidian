"""S9-T01/T02 assembly: Case 4 + Case 5 through the stage3 derive API.

Implements the derive half of STAGE9-PLAN S9-T01 (Case 4, ``# 45`` /
``# 29``) and S9-T02 (Case 5, ``# 47`` / ``# 30``):

* ``derive_case4``: new-edition Correction profile (``rules_v2``) over
  the same COMMITTED Raw => new Normalization Revision + downstream
  new Rendered artifact. The downstream render keeps the frozen
  formatter, so Case 4 isolates the Correction change. Never calls the
  transcription engine (every result carries ``whisper_calls == 0``
  from the stage3 layer).
* ``derive_case5``: new-edition formatter profile (``formatter_v2``)
  over the same Normalized artifact => only a new Render Revision
  (the stage3 layer raises unless the Normalization Revision count is
  unchanged). Raw bytes and the Normalized artifact are reused
  untouched.
* Case 6 falls out by construction: neither path reads the
  Processing Run row for mutation nor writes it, Raw finals stay
  read-only, and the canonical decoy is only probed for a verdict —
  zero bytes reach any canonical path. Publish paths are never called.

Hard limits for this module (audited by grep + row counts, see the
Stage9 plan P0-4):

* only the stage3 ``derive`` / ``normalize`` / ``render`` public API is
  called — no second copy of the mechanics lives here;
* no handle of its own is ever opened here: the caller-supplied
  lock-gated handle passes straight into the stage3 API, and every row
  effect below is owned and disclosed by that layer;
* the Stage1 transcription entry point is never imported here;
* Stage10+ semantics (commit-table writes, canonical backfill,
  background launchers, desktop status UI) have no entry point here —
  not as code, not as names.
"""

from __future__ import annotations

import os
import sys

from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage3 import derive as _derive  # noqa: E402 (read-only reuse)
from stage3 import render as _render  # noqa: E402 (frozen profile reuse)

from . import formatter_v2 as _formatter_v2  # noqa: E402
from . import rules_v2 as _rules_v2  # noqa: E402


class DeriveV2Error(ValueError):
    """FAIL: bad derive input (fail-closed, nothing persisted)."""


def derive_case4(
    con: Any,
    job_dir: str,
    raw_artifact_id: str,
    title: str | None = None,
    canonical_probe_path: str | None = None,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Case 4: new-edition Correction => new NormRev + new Rendered."""
    if not raw_artifact_id:
        raise DeriveV2Error("raw_artifact_id must be a non-empty string")
    norm_profile = _rules_v2.new_normalization_profile()
    frozen_render = dict(_render.DEFAULT_PROFILE)
    out = _derive.derive_on_correction_change(
        con,
        job_dir,
        raw_artifact_id,
        norm_profile,
        render_profile=frozen_render,
        title=title,
        canonical_probe_path=canonical_probe_path,
        source_id=source_id,
        run_id=run_id,
    )
    out["stage9_rules_revision"] = _rules_v2.RULES_REVISION
    out["stage9_base_rules_revision"] = _rules_v2.BASE_RULES_REVISION
    out["stage9_render_profile_is_frozen"] = True
    return out


def derive_case5(
    con: Any,
    job_dir: str,
    normalized_artifact_id: str,
    title: str | None = None,
    canonical_probe_path: str | None = None,
    source_id: str | None = None,
    run_id: str | None = None,
) -> dict:
    """Case 5: new-edition formatter => only a new RenderRev."""
    if not normalized_artifact_id:
        raise DeriveV2Error("normalized_artifact_id must be a non-empty string")
    render_profile = _formatter_v2.new_render_profile()
    out = _derive.derive_on_formatter_change(
        con,
        job_dir,
        normalized_artifact_id,
        render_profile,
        title=title,
        canonical_probe_path=canonical_probe_path,
        source_id=source_id,
        run_id=run_id,
    )
    out["stage9_formatter_version"] = _formatter_v2.FORMATTER_VERSION
    out["stage9_rule_order"] = list(_formatter_v2.RULE_ORDER)
    return out
