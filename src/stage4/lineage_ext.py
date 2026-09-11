"""S4-T05: lineage extension to the Canonical Publish ring.

Implements STAGE4-PLAN S4-T05 only (V1.8 ``# 4`` / ``# 41`` / ``# 52``):

* :func:`get_lineage_with_publish` reuses ``stage3.lineage.get_lineage``
  read-only (that module is never modified here) and appends the
  final ring — ``canonical_publish``: one entry per ``publish_records``
  row downstream of the chain's Render Revisions carrying
  ``publish_record_id`` / ``render_revision_id`` /
  ``rendered_artifact_id`` / ``canonical_output_path`` /
  ``expected_hash`` / ``published_hash`` / ``publish_mode`` /
  ``status``. A chain with no publish downstream reports
  ``[{"status": "missing", ...}]`` instead of failing.
* :func:`record_publish_receipt` appends the Publish Receipt plus the
  ``# 52`` Ownership five items
  (``render_revision_id`` / ``rendered_artifact_id`` /
  ``publish_record_id`` / ``expected_output_hash`` /
  ``published_hash``) to the per-job ``manifest.json`` through the
  Stage3 append-only writer — history entries are never rewritten.

Every success dict carries ``whisper_calls == 0``.
"""

from __future__ import annotations

import datetime
import os
import sqlite3

from stage3 import lineage as _s3


def _utc_now_iso() -> str:
    return datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _open_central_ro(data_root: str) -> sqlite3.Connection:
    from stage2.store import central_db_path  # noqa: PLC0415 (read-only)

    db_path = central_db_path(os.path.abspath(data_root))
    if not os.path.isfile(db_path):
        raise _s3.LineageError("central DB missing at %s" % (db_path,))
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def get_lineage_with_publish(key: str, data_root: str) -> dict:
    """Assemble the # 4 full chain plus the Canonical Publish ring."""
    chain = _s3.get_lineage(key, os.path.abspath(data_root))
    render_revs = chain.get("render_revisions")
    ids: list[str] = []
    if isinstance(render_revs, list):
        for rev in render_revs:
            if isinstance(rev, dict) and rev.get("render_revision_id"):
                ids.append(rev["render_revision_id"])
    if not ids:
        chain["canonical_publish"] = [{
            "status": "missing",
            "reason": "no render revision upstream to publish from",
        }]
        return chain
    con = _open_central_ro(data_root)
    try:
        rings: list[dict] = []
        for render_revision_id in ids:
            rendered_artifact_id = None
            hit = con.execute(
                "SELECT rendered_artifact_id FROM render_revisions"
                " WHERE render_revision_id = ?",
                (render_revision_id,),
            ).fetchone()
            if hit is not None:
                rendered_artifact_id = hit[0]
            for prow in con.execute(
                "SELECT publish_record_id, render_revision_id,"
                " canonical_output_path, expected_hash, publish_mode,"
                " status, published_hash, created_at, published_at"
                " FROM publish_records WHERE render_revision_id = ?"
                " ORDER BY created_at",
                (render_revision_id,),
            ).fetchall():
                rings.append({
                    "publish_record_id": prow[0],
                    "render_revision_id": prow[1],
                    "rendered_artifact_id": rendered_artifact_id,
                    "canonical_output_path": prow[2],
                    "expected_hash": prow[3],
                    "publish_mode": prow[4],
                    "status": prow[5],
                    "published_hash": prow[6],
                    "created_at": prow[7],
                    "published_at": prow[8],
                })
    finally:
        con.close()
    chain["canonical_publish"] = rings or [{
        "status": "missing",
        "reason": "no publish record downstream of the render revisions",
    }]
    return chain


def record_publish_receipt(manifest_path: str, *,
                           publish_record_id: str,
                           render_revision_id: str,
                           rendered_artifact_id: str,
                           canonical_output_path: str,
                           expected_output_hash: str,
                           published_hash: str,
                           status: str) -> dict:
    """Append the Publish Receipt + Ownership five items (append-only)."""
    if not publish_record_id or not render_revision_id:
        raise _s3.LineageError("publish receipt needs record + revision ids")
    receipt = {
        "stage": "Stage4-S4-T02",
        "state": status,
        "artifact": os.path.abspath(canonical_output_path),
        "artifact_id": publish_record_id,
        "artifact_type": "canonical",
        "render_revision_id": render_revision_id,
        "rendered_artifact_id": rendered_artifact_id,
        "publish_record_id": publish_record_id,
        "expected_output_hash": expected_output_hash,
        "published_hash": published_hash,
        "canonical_output_path": os.path.abspath(canonical_output_path),
        "ownership": {
            "render_revision_id": render_revision_id,
            "rendered_artifact_id": rendered_artifact_id,
            "publish_record_id": publish_record_id,
            "expected_output_hash": expected_output_hash,
            "published_hash": published_hash,
        },
        "created_at": _utc_now_iso(),
        "whisper_calls": 0,
    }
    return _s3.record_lineage_manifest(
        manifest_path,
        receipts=[receipt],
        metadata={"publish_record_ids": [publish_record_id]},
    )
