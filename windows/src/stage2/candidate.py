"""S2-T02: Candidate lifecycle + Stable File gate.

Implements STAGE2-PLAN S2-T02 only:
  - discover(path) direct API (no Watch/Scan/Reconcile, no filesystem
    listening threads).
  - DISCOVERED -> WAITING_FOR_STABLE_FILE (size/mtime two-round stable,
    jitter stays waiting) -> IDENTIFYING_SOURCE -> PROMOTED, plus
    MERGED (active-provisional conflict folds into the existing row) /
    REJECTED (explicit) / SOURCE_MISSING (file gone).
  - Provisional key = abspath-verbatim path_identity_key + size + mtime_ns.
  - Repeat discovery of identical bytes folds to MERGED (active count stays
    1); Case 13 (same path+size+mtime, different bytes) is NOT swallowed —
    it proceeds through Strong Hash to a new Source (see stage2.source).
  - Zero transcription-engine invocations in this module: the only hash used
    is the Strong SHA256 promotion hash (via stage2.source ->
    stage1.sha256_file). No later-stage (Stage3+) imports or invocations
    exist here (FAIL gate, P0-2).

STOP EXPANSION: AUTO run creation is runs.py's job; discover() only calls it
when the caller passes an explicit profile hash string (opaque identity
input, never executed as a model).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage2 import source as _source  # noqa: E402
from stage2 import store  # noqa: E402

ACTIVE = store.ACTIVE_CANDIDATE_STATUSES
STABLE_ROUNDS_SLEEP = 0.05
_DB_RETRIES = 80


def _retry_locked(fn, *args, **kwargs):
    last = None
    for _ in range(_DB_RETRIES):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "race-retry" not in str(exc).lower():
                raise
            last = exc
            time.sleep(0.05)
    raise last  # type: ignore[misc]


def _missing_candidate(con, path_key, reason):
    now = store.utc_now_iso()
    cid = store.new_id("cand")
    con.execute(
        "INSERT INTO discovery_candidates (candidate_id, path_identity_key, size,"
        " mtime_ns, device, inode, status, content_identity, source_id,"
        " merged_into, observed_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, path_key, -1, -1, None, None, "SOURCE_MISSING", None, None, None, now, now),
    )
    store.record_event(con, "candidate", cid, None, "SOURCE_MISSING", reason)
    con.commit()
    row = con.execute(
        "SELECT * FROM discovery_candidates WHERE candidate_id=?", (cid,)
    ).fetchone()
    return {
        "candidate_id": cid,
        "status": "SOURCE_MISSING",
        "source_id": None,
        "run_id": None,
        "merged_into": None,
        "content_identity": None,
        "provisional": {"path_identity_key": path_key, "size": -1, "mtime_ns": -1},
        "candidate": dict(row),
    }


def _insert_merged(con, path_key, size, mtime_ns, device, inode, target_id, reason):
    now = store.utc_now_iso()
    cid = store.new_id("cand")
    con.execute(
        "INSERT INTO discovery_candidates (candidate_id, path_identity_key, size,"
        " mtime_ns, device, inode, status, content_identity, source_id,"
        " merged_into, observed_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, path_key, size, mtime_ns, device, inode, "MERGED", None, None,
         target_id, now, now),
    )
    store.record_event(con, "candidate", cid, None, "MERGED", reason)
    return cid


def discover(path: str, data_root: str, asr_profile_hash: str | None = None) -> dict:
    """Direct-API discovery of one path. Returns a result dict.

    asr_profile_hash, when given, is an opaque frozen profile-hash string
    (Stage0/Stage1 value passed through, never parsed, never executed);
    after a successful promotion the AUTO run for (source, hash) is ensured
    so Triple-Race callers converging on discover() observe Source=1/Run=1.
    """
    store.require_lock(data_root)
    path_key = os.path.abspath(path)  # verbatim (§23): no NFC/casefold/slugify

    try:
        s1 = os.stat(path_key)
    except (FileNotFoundError, OSError):

        def _m():
            con = store.open_db(data_root)
            try:
                return _missing_candidate(con, path_key, "stat failed at discover()")
            finally:
                con.close()

        return _retry_locked(_m)
    time.sleep(STABLE_ROUNDS_SLEEP)
    try:
        s2 = os.stat(path_key)
    except (FileNotFoundError, OSError):

        def _m2():
            con = store.open_db(data_root)
            try:
                return _missing_candidate(con, path_key, "file vanished during stable gate")
            finally:
                con.close()

        return _retry_locked(_m2)

    size, mtime_ns, device, inode = s2.st_size, s2.st_mtime_ns, s2.st_dev, s2.st_ino
    stable = (s1.st_size == s2.st_size) and (s1.st_mtime_ns == s2.st_mtime_ns)

    def _once():
        con = store.open_db(data_root)
        try:
            active = con.execute(
                "SELECT * FROM discovery_candidates WHERE path_identity_key=?"
                " AND size=? AND mtime_ns=? AND status IN"
                " ('DISCOVERED','WAITING_FOR_STABLE_FILE','IDENTIFYING_SOURCE')",
                (path_key, size, mtime_ns),
            ).fetchone()
            if active is not None:
                cid = _insert_merged(
                    con, path_key, size, mtime_ns, device, inode,
                    active["candidate_id"], "active provisional conflict -> MERGED",
                )
                con.commit()
                return {
                    "candidate_id": cid,
                    "status": "MERGED",
                    "source_id": active["source_id"],
                    "run_id": None,
                    "merged_into": active["candidate_id"],
                    "content_identity": None,
                    "provisional": {"path_identity_key": path_key, "size": size,
                                    "mtime_ns": mtime_ns},
                }
            now = store.utc_now_iso()
            cid = store.new_id("cand")
            try:
                con.execute(
                    "INSERT INTO discovery_candidates (candidate_id, path_identity_key,"
                    " size, mtime_ns, device, inode, status, content_identity,"
                    " source_id, merged_into, observed_at, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, path_key, size, mtime_ns, device, inode, "DISCOVERED",
                     None, None, None, now, now),
                )
            except sqlite3.IntegrityError:
                # Lost the atomic race: someone else holds this provisional key.
                other = con.execute(
                    "SELECT * FROM discovery_candidates WHERE path_identity_key=?"
                    " AND size=? AND mtime_ns=? AND status IN"
                    " ('DISCOVERED','WAITING_FOR_STABLE_FILE','IDENTIFYING_SOURCE')",
                    (path_key, size, mtime_ns),
                ).fetchone()
                if other is None:  # winner already left active set; retry outer
                    con.rollback()
                    raise sqlite3.OperationalError("provisional race-retry")
                cid2 = _insert_merged(
                    con, path_key, size, mtime_ns, device, inode,
                    other["candidate_id"], "lost provisional race -> MERGED",
                )
                con.commit()
                return {
                    "candidate_id": cid2,
                    "status": "MERGED",
                    "source_id": other["source_id"],
                    "run_id": None,
                    "merged_into": other["candidate_id"],
                    "content_identity": None,
                    "provisional": {"path_identity_key": path_key, "size": size,
                                    "mtime_ns": mtime_ns},
                }
            store.record_event(con, "candidate", cid, None, "DISCOVERED", "direct API")
            con.execute(
                "UPDATE discovery_candidates SET status='WAITING_FOR_STABLE_FILE',"
                " updated_at=? WHERE candidate_id=?", (now, cid),
            )
            if not stable:
                store.record_event(
                    con, "candidate", cid, "DISCOVERED", "WAITING_FOR_STABLE_FILE",
                    "size/mtime jitter between two rounds; stays waiting",
                )
                con.commit()
                return {
                    "candidate_id": cid,
                    "status": "WAITING_FOR_STABLE_FILE",
                    "source_id": None,
                    "run_id": None,
                    "merged_into": None,
                    "content_identity": None,
                    "provisional": {"path_identity_key": path_key, "size": size,
                                    "mtime_ns": mtime_ns},
                }
            con.execute(
                "UPDATE discovery_candidates SET status='IDENTIFYING_SOURCE',"
                " updated_at=? WHERE candidate_id=?", (store.utc_now_iso(), cid),
            )
            con.commit()
            # Strong Hash (read-only) BEFORE deciding MERGED-vs-new (Case 13).
            from stage1 import sha256_file as _sha  # local: keeps module import graph clean

            content_hex = _sha(path_key)
            content_identity = "sha256:" + content_hex
            # Identical bytes under the same path rediscovered (same mtime or
            # merely touched): fold into the prior promotion — no new Source.
            prior = con.execute(
                "SELECT * FROM discovery_candidates WHERE path_identity_key=?"
                " AND status='PROMOTED' AND content_identity=?"
                " ORDER BY observed_at LIMIT 1",
                (path_key, content_identity),
            ).fetchone()
            if prior is not None:
                # Identical bytes rediscovered: fold into the prior promotion.
                con.execute(
                    "UPDATE discovery_candidates SET status='MERGED',"
                    " content_identity=?, source_id=?, merged_into=?,"
                    " updated_at=? WHERE candidate_id=?",
                    (content_identity, prior["source_id"], prior["candidate_id"],
                     store.utc_now_iso(), cid),
                )
                store.record_event(
                    con, "candidate", cid, "IDENTIFYING_SOURCE", "MERGED",
                    "identical-bytes rediscovery -> %s" % (prior["candidate_id"],),
                )
                run_id = None
                if asr_profile_hash is not None:
                    from stage2 import runs as _runs

                    run_id = _runs.get_or_create_auto_run(
                        prior["source_id"], asr_profile_hash, data_root, _con=con
                    )["run_id"]
                con.commit()
                return {
                    "candidate_id": cid,
                    "status": "MERGED",
                    "source_id": prior["source_id"],
                    "run_id": run_id,
                    "merged_into": prior["candidate_id"],
                    "content_identity": content_identity,
                    "provisional": {"path_identity_key": path_key, "size": size,
                                    "mtime_ns": mtime_ns},
                }
            # New bytes for this provisional key (happy path or Case 13):
            # promote to a (possibly new) Logical Source.
            cand_row, src_row, _is_new = _source.promote_candidate(cid, data_root)
            run_id = None
            if asr_profile_hash is not None:
                from stage2 import runs as _runs

                run_id = _runs.get_or_create_auto_run(
                    src_row["source_id"], asr_profile_hash, data_root
                )["run_id"]
            return {
                "candidate_id": cid,
                "status": "PROMOTED",
                "source_id": src_row["source_id"],
                "run_id": run_id,
                "merged_into": None,
                "content_identity": src_row["content_identity"],
                "provisional": {"path_identity_key": path_key, "size": size,
                                "mtime_ns": mtime_ns},
            }
        finally:
            con.close()

    return _retry_locked(_once)


def reject_candidate(candidate_id: str, data_root: str, reason: str = "explicit reject") -> dict:
    """Move an active candidate to REJECTED. Terminal candidates refuse."""
    store.require_lock(data_root)

    def _once():
        con = store.open_db(data_root)
        try:
            row = con.execute(
                "SELECT * FROM discovery_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise KeyError("candidate not found: %r" % (candidate_id,))
            if row["status"] not in ACTIVE:
                raise ValueError(
                    "candidate %r not active (is %r); refuse REJECTED"
                    % (candidate_id, row["status"])
                )
            con.execute(
                "UPDATE discovery_candidates SET status='REJECTED', updated_at=?"
                " WHERE candidate_id=?", (store.utc_now_iso(), candidate_id),
            )
            store.record_event(con, "candidate", candidate_id, row["status"], "REJECTED", reason)
            con.commit()
            out = con.execute(
                "SELECT * FROM discovery_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return dict(out)
        finally:
            con.close()

    return _retry_locked(_once)


def active_count(con: sqlite3.Connection) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM discovery_candidates WHERE status IN"
        " ('DISCOVERED','WAITING_FOR_STABLE_FILE','IDENTIFYING_SOURCE')"
    ).fetchone()[0]
