"""S3-T05: Artifact Lineage assembly + query.

Implements STAGE3-PLAN S3-T05 only (V1.8 ``# 4`` / ``# 41``):

* ``record_lineage_manifest`` appends Norm/Render receipts plus lineage
  metadata to the per-job ``manifest.json`` — append-only, history
  entries are never rewritten (``Manifest = Commit Receipt + Lineage
  Metadata``, ``# 41``).
* ``get_lineage`` assembles the full chain from the central DB plus
  the per-job manifest/files::

      Source -> Processing Run -> Raw -> Normalization Revision(s)
        -> Normalized artifact(s) -> Render Revision(s)
        -> Rendered artifact(s) -> PublishEvaluation verdict(s)

  Missing links are marked explicitly (``{"status": "missing", ...}``)
  — never fabricated, never an exception for in-chain gaps. (An
  unknown root key itself is a caller error and raises ``KeyError``.)

Lineage evidence for acceptance is reported through the S3-T06
suite (per supervisor note, T05 ships no separate report).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sqlite3

STATE_COMMITTED = "COMMITTED"


class LineageError(ValueError):
    """FAIL: unreadable manifest / DB evidence."""


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _sha256_file_hex(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_fsync_json(path: str, payload: dict) -> None:
    data = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise LineageError("%s is not a JSON object" % (path,))
    return payload


def _receipt_key(receipt: dict) -> tuple:
    return (
        receipt.get("stage"),
        receipt.get("state"),
        receipt.get("artifact"),
        receipt.get("artifact_id"),
        receipt.get("normalization_revision_id")
        or receipt.get("render_revision_id"),
        receipt.get("verdict"),
    )


def record_lineage_manifest(manifest_path: str, receipts: list | None = None,
                            metadata: dict | None = None) -> dict:
    """Append lineage receipts/metadata (never rewrite history)."""
    receipts = receipts or []
    metadata = metadata or {}
    if not os.path.isfile(manifest_path):
        raise LineageError("manifest.json missing at %s" % (manifest_path,))
    manifest = _load_json(manifest_path)
    stored = manifest.get("receipts")
    if not isinstance(stored, list):
        raise LineageError("manifest receipts is not a list")
    known = set()
    for entry in stored:
        if isinstance(entry, dict):
            known.add(_receipt_key(entry))
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise LineageError("lineage receipt must be a dict")
        entry = dict(receipt)
        entry.setdefault("created_at", _utc_now_iso())
        if _receipt_key(entry) not in known:
            stored.append(entry)
            known.add(_receipt_key(entry))
    lineage = manifest.get("lineage")
    if not isinstance(lineage, dict):
        lineage = {}
        manifest["lineage"] = lineage
    for key, value in metadata.items():
        if key not in lineage:
            lineage[key] = value
        elif isinstance(lineage[key], list) and isinstance(value, list):
            for item in value:
                if item not in lineage[key]:
                    lineage[key].append(item)
        # Existing scalar entries win: history is never rewritten.
    _write_fsync_json(manifest_path, manifest)
    return manifest


def _row_dict(row) -> dict | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def _open_central_ro(data_root: str) -> sqlite3.Connection:
    from stage2.store import central_db_path  # noqa: PLC0415 (read-only)

    db_path = central_db_path(data_root)
    if not os.path.isfile(db_path):
        raise LineageError("central DB missing at %s" % (db_path,))
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _job_id_of_raw(raw_artifact_id: str) -> str | None:
    if raw_artifact_id.startswith("raw_"):
        return raw_artifact_id[len("raw_"):]
    return None


def get_lineage(key: str, data_root: str) -> dict:
    """Assemble the ``# 4`` full chain for one source or run id."""
    data_root = os.path.abspath(data_root)
    con = _open_central_ro(data_root)
    try:
        return _assemble(con, key, data_root)
    finally:
        con.close()


def _assemble(con: sqlite3.Connection, key: str, data_root: str) -> dict:
    run = _row_dict(con.execute(
        "SELECT * FROM processing_runs WHERE run_id = ?", (key,)
    ).fetchone())
    source = None
    if run is not None:
        source = _row_dict(con.execute(
            "SELECT * FROM sources WHERE source_id = ?",
            (run.get("source_id"),),
        ).fetchone())
    else:
        source = _row_dict(con.execute(
            "SELECT * FROM sources WHERE source_id = ?", (key,)
        ).fetchone())
        if source is None:
            raise KeyError("unknown source/run id: %r" % (key,))
        run = _row_dict(con.execute(
            "SELECT * FROM processing_runs WHERE source_id = ?"
            " ORDER BY created_at LIMIT 1",
            (source.get("source_id"),),
        ).fetchone())

    chain: dict = {
        "source": source,
        "run": run if run is not None else {
            "status": "missing", "reason": "no processing run for source",
        },
    }

    raw_artifact_id = (run or {}).get("raw_artifact_id")
    raw_node: dict = {"raw_artifact_id": raw_artifact_id}
    job_dir = None
    if raw_artifact_id:
        job_id = _job_id_of_raw(raw_artifact_id)
        if job_id:
            job_dir = os.path.join(data_root, "data", "jobs", job_id)
            raw_path = os.path.join(job_dir, "raw", "raw.json")
            if os.path.isfile(raw_path):
                raw_node["final_path"] = raw_path
                raw_node["final_hash"] = (
                    "sha256:" + _sha256_file_hex(raw_path)
                )
                manifest_path = os.path.join(job_dir, "manifest.json")
                if os.path.isfile(manifest_path):
                    try:
                        manifest = _load_json(manifest_path)
                        raw_node["manifest_receipts"] = [
                            r for r in manifest.get("receipts", [])
                            if isinstance(r, dict)
                            and r.get("artifact_id") == raw_artifact_id
                        ]
                    except LineageError as exc:
                        raw_node["manifest_receipts"] = {
                            "status": "missing", "reason": str(exc),
                        }
            else:
                raw_node["status"] = "missing"
                raw_node["reason"] = "raw.json absent at %s" % (raw_path,)
        else:
            raw_node["status"] = "missing"
            raw_node["reason"] = "raw_artifact_id not job-scoped"
    else:
        raw_node["status"] = "missing"
        raw_node["reason"] = "run.raw_artifact_id is null"
    chain["raw"] = raw_node

    norm_revs = []
    if raw_artifact_id:
        for row in con.execute(
            "SELECT * FROM normalization_revisions WHERE raw_artifact_id = ?"
            " ORDER BY created_at",
            (raw_artifact_id,),
        ).fetchall():
            rev = dict(row)
            art = _row_dict(con.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (rev.get("normalized_artifact_id"),),
            ).fetchone())
            rev["normalized_artifact"] = (
                art if art is not None else {
                    "status": "missing",
                    "reason": "no central artifacts row for %r"
                    % (rev.get("normalized_artifact_id"),),
                }
            )
            if job_dir and art is not None and art.get("path"):
                rev["file_present"] = os.path.isfile(art["path"])
            norm_revs.append(rev)
    chain["normalization_revisions"] = norm_revs or [{
        "status": "missing", "reason": "no normalization revision for raw",
    }]

    render_revs = []
    for rev in norm_revs:
        if not isinstance(rev, dict) or rev.get("status") == "missing":
            continue
        for row in con.execute(
            "SELECT * FROM render_revisions WHERE normalized_artifact_id = ?"
            " ORDER BY created_at",
            (rev.get("normalized_artifact_id"),),
        ).fetchall():
            rrev = dict(row)
            art = _row_dict(con.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (rrev.get("rendered_artifact_id"),),
            ).fetchone())
            rrev["rendered_artifact"] = (
                art if art is not None else {
                    "status": "missing",
                    "reason": "no central artifacts row for %r"
                    % (rrev.get("rendered_artifact_id"),),
                }
            )
            if job_dir and art is not None and art.get("path"):
                rrev["file_present"] = os.path.isfile(art["path"])
            rrev["evaluation"] = _evaluation_for(
                con, job_dir, rrev.get("render_revision_id"),
                rrev.get("rendered_artifact_id"),
            )
            render_revs.append(rrev)
    chain["render_revisions"] = render_revs or [{
        "status": "missing", "reason": "no render revision downstream",
    }]
    return chain


def _evaluation_for(con, job_dir, render_revision_id,
                    rendered_artifact_id) -> dict:
    """Collect the PUBLISH_EVALUATION verdict (receipt first, events next)."""
    if job_dir:
        manifest_path = os.path.join(job_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                manifest = _load_json(manifest_path)
                for receipt in manifest.get("receipts", []):
                    if (
                        isinstance(receipt, dict)
                        and receipt.get("render_revision_id")
                        == render_revision_id
                        and receipt.get("verdict")
                    ):
                        return {
                            "verdict": receipt["verdict"],
                            "canonical_probe": receipt.get("canonical_probe"),
                            "canonical_writes": receipt.get(
                                "canonical_writes", 0),
                            "evidence": "manifest",
                        }
            except LineageError:
                pass
    rows = con.execute(
        "SELECT from_status, to_status, reason, created_at FROM state_events"
        " WHERE entity_type = 'render_revision' AND entity_id = ?"
        " ORDER BY created_at",
        (render_revision_id,),
    ).fetchall()
    for row in reversed(rows):
        reason = (row[2] or "") if not isinstance(row, sqlite3.Row) else row["reason"]
        if "verdict=" in reason:
            verdict = reason.split("verdict=", 1)[1].split(";", 1)[0].strip()
            return {
                "verdict": verdict,
                "reason": reason,
                "evidence": "state_events",
            }
    return {"status": "missing", "reason": "no evaluation verdict recorded"}
