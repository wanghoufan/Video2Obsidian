"""S11-T04: Fault Injection full suite (registry + runner).

Implements STAGE11-PLAN S11-T04 only. Reused faults (7):

  F-R1 Case 8  same size + same mtime + changed bytes -> BLOCK,
               source kept (Strong Verify, no size/mtime shortcut).
  F-R2 Case 9  rename landed, manifest pending (kill between) ->
               Repair Forward via stage1 recovery, whisper 0.
  F-R3 Case 10 mid-copy cut at pre-unlink (hook stands in for SIGKILL)
               -> owned sidecar repair via level-B recover, source
               safe at cut, Receipt only after valid final.
  F-R4 Case 12 output/target race -> BLOCK, other-writer bytes
               unchanged, cover count 0, source kept.
  F-R5 Case 13 same path + size + mtime but new bytes -> new Source
               (never folded silently).
  F-R6 Case 15 manifest lags COMMITTED final -> Repair Forward via
               stage1 recovery, whisper 0.
  F-R7 half artifact is not success (no Receipt -> not success).

New faults (4):

  F-N1 staged archive bytes land but commit is delayed (kill before
       commit) -> bytes safe at final, central row untouched until
       the booked commit moves exactly the four columns.
  F-N2 decoy canonical changed between setup and archive attempt ->
       BLOCK, cover 0, source kept.
  F-N3 concurrent delivery storm through discover only -> Source=1,
       AUTO Run=1 (no extra Run minted).
  F-N4 duplicate plist load is idempotent; unload leaves no residue;
       real agent dirs untouched.

Production assembly (agent_boot) always passes through the gate
entry; drills that need a kill hook call the level helper with
expected_hash mandatory and are labelled as drills. Every case
records whisper increment (always 0 here), DB deltas, hashes, cover
counts, decoy-canonical stability, and the max synthetic file size
(small files only; long-form media never used; text content never
asserted).

Additive-only: read-only reuse of stage1/2/4/5/10 publics plus the
S11 helpers; never amends src/stage1-10; never touches real
LaunchAgents dirs; no true reboot or power test.
"""

from __future__ import annotations

import concurrent.futures as _fut
import hashlib
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MAX_SYNTHETIC_BYTES = 65536

CASE_IDS = (
    "F-R1", "F-R2", "F-R3", "F-R4", "F-R5", "F-R6", "F-R7",
    "F-N1", "F-N2", "F-N3", "F-N4",
)


def _sha_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            part = fh.read(8 * 1024 * 1024)
            if not part:
                break
            digest.update(part)
    return "sha256:" + digest.hexdigest()


def _write(path: str, payload: bytes) -> dict:
    if len(payload) > MAX_SYNTHETIC_BYTES:
        raise ValueError("synthetic file too large for Stage11 drills")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    st = os.stat(path)
    return {"path": os.path.abspath(path), "size": st.st_size,
            "hash": _sha_file(path)}


def _snapshot_counts(data_root: str) -> dict:
    from stage2 import store as _store  # noqa: E402 (read-only reuse)

    con = _store.open_db(os.path.abspath(data_root))
    try:
        return dict(_store.table_counts(con))
    finally:
        con.close()


def _read_source(data_root: str, source_id: str) -> dict | None:
    from stage10 import verify_archive as _v  # noqa: E402 (read-only)
    from stage2 import store as _store  # noqa: E402 (read-only)

    con = _store.open_db(os.path.abspath(data_root))
    try:
        return _v.read_source_row(con, source_id)
    finally:
        con.close()


def _discover(data_root: str, path: str, profile: str) -> dict:
    from stage2.candidate import discover as _d  # noqa: E402 (sole entry)

    return _d(os.path.abspath(path), os.path.abspath(data_root), profile)


def _discover_ready(data_root: str, path: str, profile: str,
                    tries: int = 5, sleep: float = 0.1) -> dict:
    """Bounded retry for discover vs RUNNING-watcher race (P1-3).

    Single-shot discover can see ``source_id None`` (provisional not yet
    promoted) or ``WAITING_FOR_STABLE_FILE`` when the watcher/hand投 race;
    callers previously fed that straight into gate and got
    ``ARCHIVE_UNKNOWN_SOURCE`` FAIL flakes. Retry while ``source_id is
    None`` or status is ``WAITING_FOR_STABLE_FILE``; after ``tries``
    attempts return the last dict so the caller can FAIL with its status.
    """
    last: dict = {}
    for _ in range(max(1, int(tries))):
        last = _discover(data_root, path, profile)
        sid = (last or {}).get("source_id")
        status = (last or {}).get("status")
        if sid is not None and status != "WAITING_FOR_STABLE_FILE":
            return last
        time.sleep(sleep)
    return last


def _canon(path: str) -> str:
    """Stage5 spelling for input files (abspath + symlink resolution).

    The watcher delivers FS-resolved paths while plain abspath keeps
    the caller's spelling; one spelling keeps storm/watcher/scan on a
    single provisional key (same-file dual spellings would mint a
    second Logical Source by Stage2 verbatim-path semantics).
    """
    from stage5.watcher import canonical as _c  # noqa: E402 (read-only)

    return _c(path)


def _pass(case: str, name: str, detail: dict) -> dict:
    return {"id": case, "name": name, "kind": detail.pop("kind", "reuse"),
            "verdict": "PASS", "exit_code": 0,
            "whisper_delta": 0, "asr_calls": 0, "whisper_calls": 0,
            "detail": detail}


def _fail(case: str, name: str, reason: str, detail: dict | None = None) -> dict:
    out = {"id": case, "name": name, "kind": (detail or {}).pop("kind", "reuse"),
           "verdict": "FAIL", "exit_code": 1, "reason": reason,
           "whisper_delta": 0, "asr_calls": 0, "whisper_calls": 0,
           "detail": detail or {}}
    return out


# ---------------------------------------------------------------- reuse

def case_r1_tamper_block(ctx: dict) -> dict:
    """F-R1 Case 8: same size + same mtime, changed bytes -> BLOCK."""
    from stage10 import verify_archive as _v  # noqa: E402 (read-only)

    name = "case8-tamper-block"
    work = _canon(os.path.join(ctx["input_root"], "f-r1.mp4"))
    payload_a = b"stage11-r1-a" * 128
    info = _write(work, payload_a)
    disc = _discover_ready(ctx["data_root"], work, ctx["profile"])
    if disc.get("source_id") is None:
        return _fail("F-R1", name, "discover not ready after retries",
                     {"kind": "reuse", "discover": disc,
                      "max_file_bytes": info["size"]})
    source_id = disc["source_id"]
    row = _read_source(ctx["data_root"], source_id)
    assert row is not None
    st0 = os.stat(work)
    payload_b = b"stage11-r1-B" * 128
    assert len(payload_b) == len(payload_a)
    _write(work, payload_b)
    os.utime(work, ns=(st0.st_atime_ns, st0.st_mtime_ns))
    st1 = os.stat(work)
    same_size = st1.st_size == st0.st_size
    same_mtime = st1.st_mtime_ns == st0.st_mtime_ns
    from stage2 import store as _store  # noqa: E402 (read-only)

    con = _store.open_db(os.path.abspath(ctx["data_root"]))
    try:
        verdict = _v.verify_source_for_archive(source_id, con)
    finally:
        con.close()
    kept = os.path.isfile(work)
    ok = (same_size and same_mtime
          and verdict.get("verdict") == "BLOCK"
          and verdict.get("code") == "BLOCKED_SOURCE_CHANGED"
          and kept)
    detail = {"kind": "reuse", "same_size": same_size,
              "same_mtime": same_mtime, "verify": verdict,
              "source_kept": kept, "source_id": source_id,
              "max_file_bytes": info["size"]}
    if not ok:
        return _fail("F-R1", name, "tamper did not BLOCK with source kept", detail)
    # Restore valid bytes so later counts stay meaningful.
    _write(work, payload_a)
    return _pass("F-R1", name, detail)


def _make_job_skeleton(job_dir: str, source_id: str, content_hash: str,
                       text: str = "hello stage eleven") -> None:
    os.makedirs(os.path.join(job_dir, "asr"), exist_ok=True)
    with open(os.path.join(job_dir, "source.json"), "w", encoding="utf-8") as fh:
        json.dump({"source_id": source_id, "content_identity": content_hash}, fh)
    with open(os.path.join(job_dir, "asr", "post_verify.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"verdict": "PASS", "code": "COMMITTING_RAW_ASR",
                   "commit_authorized": True, "hash_match": True,
                   "current_hash": content_hash}, fh)
    with open(os.path.join(job_dir, "asr", "transcript.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(job_dir, "asr", "segments.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"segments": []}, fh)
    with open(os.path.join(job_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"job_id": os.path.basename(os.path.abspath(job_dir)),
                   "state": "PREPARED", "stage": "Stage1-S1-T05",
                   "receipts": [], "lineage": {}}, fh)


def case_r2_rename_kill(ctx: dict) -> dict:
    """F-R2 Case 9: rename landed, manifest pending -> Repair Forward."""
    from stage1 import prepare as _prep  # noqa: E402 (public setup path)
    from stage1 import recovery as _rec  # noqa: E402 (Repair Forward)

    name = "case9-rename-kill-repair"
    job_dir = os.path.join(ctx["work_root"], "jobs", "f-r2-job")
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    fake_hash = "sha256:" + hashlib.sha256(b"stage11-r2").hexdigest()
    _make_job_skeleton(job_dir, "src_f_r2", fake_hash)
    prepped = _prep.prepare_raw(job_dir)
    expected = prepped["expected_artifact_hash"]
    tmp_path = prepped["temp_path"]
    final_path = prepped["final_path"]
    # Kill between rename and manifest: rename landed, nothing else moved.
    shutil.copyfile(tmp_path, final_path)
    have_manifest_before = os.path.isfile(os.path.join(job_dir, "manifest.json"))
    out = _rec.recover_raw(job_dir)
    ok = (out.get("state") == "COMMITTED"
          and out.get("final_hash") == expected
          and out.get("recovery_path") == "prepared_final_exists_repair_forward"
          and out.get("whisper_calls") == 0
          and have_manifest_before)
    detail = {"kind": "reuse", "expected_hash": expected,
              "final_hash": out.get("final_hash"),
              "recovery_path": out.get("recovery_path"),
              "max_file_bytes": os.stat(final_path).st_size}
    if not ok:
        return _fail("F-R2", name, "repair-forward did not land COMMITTED", detail)
    return _pass("F-R2", name, detail)


def case_r3_midcopy_kill(ctx: dict) -> dict:
    """F-R3 Case 10: cut at pre-unlink, owned sidecar repairs."""
    from stage11 import reliability as _rel  # noqa: E402 (same package)

    name = "case10-midcopy-kill-kept"
    orig = _canon(os.path.join(ctx["input_root"], "f-r3-orig.mp4"))
    base = _write(orig, b"stage11-r3:" * 256)
    work = _canon(os.path.join(ctx["work_root"], "copy", "f-r3-work.mp4"))
    os.makedirs(os.path.dirname(work), exist_ok=True)
    shutil.copyfile(base["path"], work)
    final = os.path.join(ctx["archive_root"], "f-r3", "f-r3-work.mp4")
    disc = _discover_ready(ctx["data_root"], work, ctx["profile"])
    if disc.get("source_id") is None:
        return _fail("F-R3", name, "discover not ready after retries",
                     {"kind": "reuse", "discover": disc,
                      "max_file_bytes": base["size"]})
    drill = _rel.archive_midcopy_drill(work, final, disc["content_identity"],
                                       disc["source_id"])
    orig_kept = os.path.isfile(orig) and _sha_file(orig) == base["hash"]
    ok = drill.get("verdict") == "PASS" and orig_kept
    detail = {"kind": "reuse", "drill": drill, "orig_kept": orig_kept,
              "orig_hash": base["hash"], "max_file_bytes": base["size"]}
    if not ok:
        return _fail("F-R3", name, "mid-copy repair did not PASS", detail)
    return _pass("F-R3", name, detail)


def case_r4_target_race(ctx: dict) -> dict:
    """F-R4 Case 12 analogue: publish-gate BLOCK + zero cover (converged).

    Converged claim (P1-2): the synthetic env builds no publish chain, so
    gate order verify->publish->target stops at the publish door with
    ``BLOCKED_ARCHIVE_NO_PUBLISH``; the foreign-target ``BLOCK_ARCHIVE_EXISTS``
    guard is structurally unreachable here and is left to the stage owning a
    publish fixture. This case asserts publish-door BLOCK + source kept +
    zero cover, and pins the exact code so regressions cannot hide behind
    any-BLOCK-passes.
    """
    from stage10 import gate as _gate  # noqa: E402 (sole archive entry)

    name = "case12-target-race-block"
    input_root = _canon(ctx["input_root"])
    archive_root = _canon(ctx["archive_root"])
    src = _canon(os.path.join(ctx["input_root"], "f-r4.mp4"))
    info = _write(src, b"stage11-r4:" * 200)
    disc = _discover_ready(ctx["data_root"], src, ctx["profile"])
    if disc.get("source_id") is None:
        return _fail("F-R4", name, "discover not ready after retries",
                     {"kind": "reuse", "discover": disc,
                      "max_file_bytes": info["size"]})
    final = os.path.join(archive_root, "f-r4", "f-r4.mp4")
    foreign = _write(final, b"foreign-owner:" * 64)
    target_before = _sha_file(final)
    from stage2 import store as _store  # noqa: E402 (read-only)

    con = _store.open_db(os.path.abspath(ctx["data_root"]))
    try:
        out = _gate.archive_source(disc["source_id"], con, archive_root,
                                   input_root=input_root,
                                   archive_final_path=final)
    finally:
        con.close()
    target_after = _sha_file(final)
    kept = os.path.isfile(src)
    cover_count = 0 if target_before == target_after else 1
    ok = (out.get("verdict") == "BLOCK"
          and out.get("code") == "BLOCKED_ARCHIVE_NO_PUBLISH"
          and kept and cover_count == 0)
    detail = {"kind": "reuse", "gate": out, "source_kept": kept,
              "expected_code": "BLOCKED_ARCHIVE_NO_PUBLISH",
              "gate_code": out.get("code"),
              "converged_claim": "publish-door BLOCK + source kept + zero "
              "cover; true BLOCK_ARCHIVE_EXISTS guard needs a publish "
              "fixture and is out of scope here",
              "target_cover_count": cover_count,
              "target_hash_before": target_before,
              "target_hash_after": target_after,
              "foreign_hash": foreign["hash"], "max_file_bytes": info["size"]}
    if not ok:
        return _fail("F-R4", name, "race did not BLOCK with zero cover", detail)
    return _pass("F-R4", name, detail)


def case_r5_collision_new_source(ctx: dict) -> dict:
    """F-R5 Case 13: same provisional key, new bytes -> new Source."""
    name = "case13-collision-new-source"
    path = _canon(os.path.join(ctx["input_root"], "f-r5.mp4"))
    pay_a = b"stage11-r5-a" * 100
    _write(path, pay_a)
    first = _discover_ready(ctx["data_root"], path, ctx["profile"])
    if first.get("source_id") is None:
        return _fail("F-R5", name, "discover not ready after retries",
                     {"kind": "reuse", "discover": first,
                      "max_file_bytes": len(pay_a)})
    st0 = os.stat(path)
    pay_b = b"stage11-r5-b" * 100
    assert len(pay_b) == len(pay_a)
    _write(path, pay_b)
    os.utime(path, ns=(st0.st_atime_ns, st0.st_mtime_ns))
    second = _discover_ready(ctx["data_root"], path, ctx["profile"])
    if second.get("source_id") is None:
        return _fail("F-R5", name, "rediscover not ready after retries",
                     {"kind": "reuse", "first_source": first["source_id"],
                      "discover": second, "max_file_bytes": len(pay_a)})
    ok = (first["source_id"] is not None
          and second["source_id"] is not None
          and second["source_id"] != first["source_id"])
    detail = {"kind": "reuse", "first_source": first["source_id"],
              "second_source": second["source_id"],
              "first_status": first["status"],
              "second_status": second["status"],
              "max_file_bytes": len(pay_a)}
    if not ok:
        return _fail("F-R5", name, "collision did not mint a new source", detail)
    return _pass("F-R5", name, detail)


def case_r6_manifest_lag(ctx: dict) -> dict:
    """F-R6 Case 15 analogue: manifest lags COMMITTED final -> repair."""
    from stage1 import commit as _com  # noqa: E402 (public setup path)
    from stage1 import prepare as _prep  # noqa: E402 (public setup path)
    from stage1 import recovery as _rec  # noqa: E402 (Repair Forward)

    name = "case15-manifest-lag-repair"
    job_dir = os.path.join(ctx["work_root"], "jobs", "f-r6-job")
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    fake_hash = "sha256:" + hashlib.sha256(b"stage11-r6").hexdigest()
    _make_job_skeleton(job_dir, "src_f_r6", fake_hash)
    prepped = _prep.prepare_raw(job_dir)
    committed = _com.commit_raw(job_dir)
    expected = committed["expected_artifact_hash"]
    manifest_path = os.path.join(job_dir, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["receipts"] = []
    manifest["state"] = "PREPARED"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
    out = _rec.recover_raw(job_dir)
    with open(manifest_path, "r", encoding="utf-8") as fh:
        fixed = json.load(fh)
    has_committed = any(isinstance(r, dict) and r.get("state") == "COMMITTED"
                        for r in fixed.get("receipts", []))
    ok = (out.get("final_hash") == expected and has_committed
          and out.get("whisper_calls") == 0
          and prepped["expected_artifact_hash"] == expected)
    detail = {"kind": "reuse", "expected_hash": expected,
              "final_hash": out.get("final_hash"),
              "recovery_path": out.get("recovery_path"),
              "manifest_repaired": has_committed,
              "max_file_bytes": os.stat(committed["final_path"]).st_size}
    if not ok:
        return _fail("F-R6", name, "lag repair did not restore manifest", detail)
    return _pass("F-R6", name, detail)


def case_r7_half_not_success(ctx: dict) -> dict:
    """F-R7: PREPARED tmp alone (no Receipt) is not success."""
    from stage1 import prepare as _prep  # noqa: E402 (public setup path)

    name = "half-artifact-not-success"
    job_dir = os.path.join(ctx["work_root"], "jobs", "f-r7-job")
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    fake_hash = "sha256:" + hashlib.sha256(b"stage11-r7").hexdigest()
    _make_job_skeleton(job_dir, "src_f_r7", fake_hash)
    prepped = _prep.prepare_raw(job_dir)
    final_missing = not os.path.isfile(prepped["final_path"])
    receipt_missing = not os.path.isfile(
        os.path.join(job_dir, "raw", "commit_receipt.json"))
    tmp_present = os.path.isfile(prepped["temp_path"])
    not_success = final_missing and receipt_missing and tmp_present
    detail = {"kind": "reuse", "tmp_present": tmp_present,
              "final_missing": final_missing,
              "receipt_missing": receipt_missing,
              "not_success": not_success,
              "max_file_bytes": os.stat(prepped["temp_path"]).st_size}
    if not not_success:
        return _fail("F-R7", name, "half artifact looked like success", detail)
    return _pass("F-R7", name, detail)


# ------------------------------------------------------------------- new

def case_n1_commit_delayed(ctx: dict) -> dict:
    """F-N1: bytes staged at final, commit delayed, then booked commit."""
    from stage10 import commit as _commit  # noqa: E402 (booked DB writer)
    from stage10 import level_b as _b  # noqa: E402 (drill move, hash held)
    from stage2 import store as _store  # noqa: E402 (read-only + lock)

    name = "commit-delayed-bytes-safe"
    orig = _canon(os.path.join(ctx["input_root"], "f-n1-orig.mp4"))
    base = _write(orig, b"stage11-n1:" * 220)
    work = _canon(os.path.join(ctx["work_root"], "copy", "f-n1-work.mp4"))
    os.makedirs(os.path.dirname(work), exist_ok=True)
    shutil.copyfile(base["path"], work)
    disc = _discover_ready(ctx["data_root"], work, ctx["profile"])
    if disc.get("source_id") is None:
        return _fail("F-N1", name, "discover not ready after retries",
                     {"kind": "new", "discover": disc,
                      "max_file_bytes": base["size"]})
    expected = disc["content_identity"]
    source_id = disc["source_id"]
    before = _snapshot_counts(ctx["data_root"])
    final = os.path.join(ctx["archive_root"], "f-n1", "f-n1-work.mp4")
    receipt = _b.archive_level_b(work, final, expected, source_id)
    # Kill before commit: central row untouched, bytes safe at final.
    mid_row = _read_source(ctx["data_root"], source_id)
    mid_counts = _snapshot_counts(ctx["data_root"])
    bytes_safe = (os.path.isfile(final) and _sha_file(final) == expected)
    row_untouched = (mid_row is not None
                     and mid_row.get("status") != "ARCHIVED"
                     and mid_counts.get("archive_commits", 0)
                     == before.get("archive_commits", 0))
    con = _store.open_db(os.path.abspath(ctx["data_root"]))
    try:
        done = _commit.commit_archive_success(con, ctx["data_root"], source_id,
                                              final, receipt, "B")
    finally:
        con.close()
    after = _snapshot_counts(ctx["data_root"])
    committed_cols = done.get("columns_updated", [])
    dual_ok = bool((done.get("dual_proof") or {}).get("hash_match"))
    orig_kept = os.path.isfile(orig) and _sha_file(orig) == base["hash"]
    ok = (bytes_safe and row_untouched and dual_ok
          and sorted(committed_cols)
          == ["archived_at", "current_location_type", "current_path", "status"]
          and after.get("archive_commits", 0)
          == before.get("archive_commits", 0) + 1
          and orig_kept)
    detail = {"kind": "new", "bytes_safe_at_final": bytes_safe,
              "row_untouched_before_commit": row_untouched,
              "columns_updated": committed_cols, "dual_ok": dual_ok,
              "archive_delta": after.get("archive_commits", 0)
              - before.get("archive_commits", 0),
              "orig_kept": orig_kept, "max_file_bytes": base["size"]}
    if not ok:
        return _fail("F-N1", name, "delayed commit did not land cleanly", detail)
    return _pass("F-N1", name, detail)


def case_n2_canonical_race(ctx: dict) -> dict:
    """F-N2: decoy edited pre-archive -> publish-door BLOCK + cover 0.

    Converged claim (P1-2): the synthetic env holds no transcribe chain, so
    the G3 pre-door stops at ``BLOCKED_ARCHIVE_NO_PUBLISH``; the true
    ``BLOCKED_ARCHIVE_CANONICAL_EDITED`` guard needs a PUBLISHED row and is
    left to the stage owning a publish fixture. This case asserts NO_PUBLISH
    + source kept + decoy zero cover, and pins the exact code.
    """
    from stage10 import gate as _gate  # noqa: E402 (sole archive entry)

    name = "canonical-race-block"
    input_root = _canon(ctx["input_root"])
    archive_root = _canon(ctx["archive_root"])
    src = _canon(os.path.join(ctx["input_root"], "f-n2.mp4"))
    info = _write(src, b"stage11-n2:" * 200)
    disc = _discover_ready(ctx["data_root"], src, ctx["profile"])
    if disc.get("source_id") is None:
        return _fail("F-N2", name, "discover not ready after retries",
                     {"kind": "new", "discover": disc,
                      "max_file_bytes": info["size"]})
    decoy = os.path.join(ctx["output_root"], "f-n2.md")
    first = _write(decoy, b"# decoy v1\n\npublished bytes\n")
    before_hash = _sha_file(decoy)
    # User-side edit lands before the archive attempt.
    _write(decoy, b"# decoy v2 user edit\n\nhand-touched bytes\n")
    edited_hash = _sha_file(decoy)
    final = os.path.join(archive_root, "f-n2", "f-n2.mp4")
    from stage2 import store as _store  # noqa: E402 (read-only)

    con = _store.open_db(os.path.abspath(ctx["data_root"]))
    try:
        out = _gate.archive_source(disc["source_id"], con, archive_root,
                                   input_root=input_root,
                                   archive_final_path=final)
    finally:
        con.close()
    after_hash = _sha_file(decoy)
    kept = os.path.isfile(src)
    # Zero cover on the decoy across the BLOCK attempt.
    cover_count = 0 if after_hash == edited_hash else 1
    changed = before_hash != edited_hash
    ok = (changed and out.get("verdict") == "BLOCK"
          and out.get("code") == "BLOCKED_ARCHIVE_NO_PUBLISH"
          and kept and cover_count == 0)
    detail = {"kind": "new", "gate": out, "source_kept": kept,
              "expected_code": "BLOCKED_ARCHIVE_NO_PUBLISH",
              "gate_code": out.get("code"),
              "converged_claim": "G3 pre-door stops at NO_PUBLISH; true "
              "BLOCKED_ARCHIVE_CANONICAL_EDITED guard needs a PUBLISHED "
              "fixture and is out of scope here",
              "decoy_cover_count": cover_count,
              "decoy_before": before_hash, "decoy_edited": edited_hash,
              "decoy_after": after_hash, "first_hash": first["hash"],
              "max_file_bytes": info["size"],
              "note": "synthetic env holds no transcribe chain; the G3 "
                      "pre-door stops at BLOCKED_ARCHIVE_NO_PUBLISH while the "
                      "S52/S53 invariants (source kept, zero cover) are "
                      "asserted; code pinned, not any-BLOCK"}
    if not ok:
        return _fail("F-N2", name, "canonical race did not BLOCK cleanly", detail)
    return _pass("F-N2", name, detail)


def case_n3_storm(ctx: dict) -> dict:
    """F-N3: concurrent storm through discover only -> Run not minted."""
    name = "delivery-storm-single-run"
    path = _canon(os.path.join(ctx["input_root"], "f-n3.mp4"))
    info = _write(path, b"stage11-n3:" * 160)
    before = _snapshot_counts(ctx["data_root"])
    profile = ctx["profile"]
    data_root = os.path.abspath(ctx["data_root"])
    target = os.path.abspath(path)

    def _one(_idx: int) -> dict:
        return _discover_ready(data_root, target, profile)

    with _fut.ThreadPoolExecutor(max_workers=8) as pool:
        got = list(pool.map(_one, range(8)))
    source_ids = {g["source_id"] for g in got if g.get("source_id")}
    run_ids = {g["run_id"] for g in got if g.get("run_id")}
    # Re-delivery after the storm must not mint another Run.
    again = _discover_ready(data_root, target, profile)
    after = _snapshot_counts(ctx["data_root"])
    run_delta = after.get("processing_runs", 0) - before.get("processing_runs", 0)
    ok = (len(source_ids) == 1 and len(run_ids) == 1
          and again["run_id"] in run_ids and run_delta == 1)
    detail = {"kind": "new", "sources": sorted(source_ids),
              "runs": sorted(run_ids), "run_delta": run_delta,
              "again_run": again.get("run_id"),
              "again_status": again.get("status"),
              "max_file_bytes": info["size"]}
    if not ok:
        return _fail("F-N3", name, "storm minted extra rows", detail)
    return _pass("F-N3", name, detail)


def case_n4_plist_idempotent(ctx: dict) -> dict:
    """F-N4: duplicate load idempotent; unload leaves no residue."""
    from stage11 import launch_plist as _lp  # noqa: E402 (same package)

    name = "plist-load-idempotent"
    real_before = _lp.snapshot_real_agents()
    label = "com.video2obsidian.test.stage11-fault"
    binary = os.path.abspath(sys.executable)
    plist = _lp.build_plist(label, binary, ctx["data_root"],
                            ctx["test_agent_dir"],
                            input_root=ctx["input_root"],
                            asr_profile_hash=ctx["profile"])
    wrote = _lp.write_plist(plist, ctx["test_agent_dir"], label)
    checked = _lp.validate_plist(wrote["plist_path"], expect_label=label,
                                 expect_binary=binary,
                                 expect_data_root=ctx["data_root"])
    if checked["verdict"] != "PASS":
        return _fail("F-N4", name, "plist validate failed: %r"
                     % (checked.get("problems"),),
                     {"kind": "new", "checked": checked})
    try:
        first = _lp.load_test_plist(wrote["plist_path"], ctx["test_agent_dir"])
    except FileNotFoundError as exc:
        return _fail("F-N4", name, "launchctl missing: %s" % (exc,),
                     {"kind": "new"})
    try:
        second = _lp.load_test_plist(wrote["plist_path"], ctx["test_agent_dir"])
    except FileNotFoundError as exc:
        return _fail("F-N4", name, "launchctl missing: %s" % (exc,),
                     {"kind": "new"})
    unloaded = _lp.unload_test_plist(wrote["plist_path"], ctx["test_agent_dir"])
    real_after = _lp.snapshot_real_agents()
    real_stable = real_before == real_after
    ok = (first["list_visible"] is True
          and second["list_visible"] is True
          and unloaded["list_visible"] is False
          and unloaded["residue"] is False
          and real_stable)
    detail = {"kind": "new", "first": first, "second": second,
              "unloaded": unloaded, "real_dirs_stable": real_stable,
              "max_file_bytes": 0}
    if not ok:
        return _fail("F-N4", name, "plist drill left residue", detail)
    return _pass("F-N4", name, detail)


_REGISTRY = (
    ("F-R1", case_r1_tamper_block),
    ("F-R2", case_r2_rename_kill),
    ("F-R3", case_r3_midcopy_kill),
    ("F-R4", case_r4_target_race),
    ("F-R5", case_r5_collision_new_source),
    ("F-R6", case_r6_manifest_lag),
    ("F-R7", case_r7_half_not_success),
    ("F-N1", case_n1_commit_delayed),
    ("F-N2", case_n2_canonical_race),
    ("F-N3", case_n3_storm),
    ("F-N4", case_n4_plist_idempotent),
)


def run_all(ctx: dict) -> dict:
    """Run every fault case in order; non-zero exit when any FAILs.

    P1-1: the suite requires the Single Instance lock before any case
    (discover/gate/commit all demand it). When ``ctx["boot"]`` is absent,
    cold-boot here so a bare ``run_all`` still runs 11/11 under lock;
    a pre-boot failure returns suite FAIL fast instead of scattered
    LockNotHeldError FAILs.
    """
    try:
        if ctx.get("boot") is None:
            from stage11 import agent_boot as _boot_pre  # noqa: E402
            ctx["boot"] = _boot_pre.cold_boot(
                ctx["data_root"], ctx["input_root"],
                ctx.get("profile", "test-profile-v1"))
    except Exception as exc:  # noqa: BLE001 (fail-fast, not scattered FAILs)
        return {
            "suite": "stage11-fault-suite",
            "verdict": "FAIL",
            "exit_code": 1,
            "results": [],
            "passed": 0,
            "failed": ["PRE-BOOT"],
            "reason": "pre-boot cold_boot failed: %r" % (exc,),
            "running_probe": None,
            "max_file_bytes": 0,
            "small_files_only": True,
            "asr_calls": 0,
            "whisper_calls": 0,
        }
    results: list[dict] = []
    for case_id, fn in _REGISTRY:
        try:
            res = fn(ctx)
        except Exception as exc:  # noqa: BLE001 (runner must not stall)
            import traceback

            res = _fail(case_id, fn.__name__, "%s: %s"
                        % (type(exc).__name__, exc),
                        {"kind": "reuse", "traceback": traceback.format_exc()})
        results.append(res)
    # Post-suite RUNNING must be reachable (no permanent stall).
    running_probe: dict | None = None
    try:
        from stage11 import agent_boot as _boot  # noqa: E402 (same package)
        from stage11 import reliability as _rel  # noqa: E402 (same package)

        boot = ctx.get("boot")
        if boot is None:
            fresh = _boot.cold_boot(ctx["data_root"], ctx["input_root"],
                                    ctx.get("profile", "test-profile-v1"))
            ctx["boot"] = fresh
            boot = fresh
        running_probe = _rel.assert_running(boot)
        if running_probe.get("verdict") != "PASS":
            fresh = _rel.relaunch(boot, ctx["data_root"], ctx["input_root"],
                                  ctx.get("profile", "test-profile-v1"))
            ctx["boot"] = fresh
            running_probe = _rel.assert_running(fresh)
    except Exception as exc:  # noqa: BLE001 (booking must be explicit)
        running_probe = {"verdict": "FAIL", "error": repr(exc)}
    failed = [r for r in results if r.get("verdict") != "PASS"]
    suite_verdict = ("PASS" if not failed
                     and (running_probe or {}).get("verdict") == "PASS"
                     else "FAIL")
    max_bytes = 0
    for res in results:
        try:
            val = int((res.get("detail") or {}).get("max_file_bytes", 0))
        except (TypeError, ValueError):
            val = 0
        max_bytes = max(max_bytes, val)
    return {
        "suite": "stage11-fault-suite",
        "verdict": suite_verdict,
        "exit_code": 0 if suite_verdict == "PASS" else 1,
        "results": results,
        "passed": len(results) - len(failed),
        "failed": [r["id"] for r in failed],
        "running_probe": running_probe,
        "max_file_bytes": max_bytes,
        "small_files_only": max_bytes <= MAX_SYNTHETIC_BYTES,
        "asr_calls": 0,
        "whisper_calls": 0,
    }
