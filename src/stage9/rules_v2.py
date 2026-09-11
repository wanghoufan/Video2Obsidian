"""S9-T01: Stage9 new-edition Correction rule table (V1.8 #45 / #29).

Implements STAGE9-PLAN S9-T01, rules half (V1.8 ``# 45`` deterministic
Correction + ``# 29`` normalization profile layering):

* The new table carries the frozen ``corr-v2`` rows verbatim (read at
  import time from ``stage3.normalize.CORRECTION_RULES`` — never
  hand-copied, so the base cannot drift) plus ``ADDED_RULES``: exact-
  substring replacements of highly-determined professional terms only.
  No network, no hosted model, no text-generation service, no
  rewording or guessing anywhere on this path.
* ``RULES_REVISION`` (``s9-corr-v2``) lands only in the ``# 29``
  ``correction_rules_revision`` profile field (new profile hash => new
  Normalization Revision via the stage3 derive API = Case 4). The other
  five profile fields are inherited unchanged, so the bump stays in
  the normalization layer.
* Registration is in-memory only: ``register_rules`` installs the new
  table into the live ``stage3.normalize.CORRECTION_RULES`` mapping so
  the frozen ``apply_corrections`` / profile-hash / two-phase commit
  mechanics are reused as-is. No file under ``src/stage1-8/`` is
  touched (the mapping edit never reaches disk), and nothing here is a
  second copy of those mechanics.
* ``validate_rules`` is a shape gate with a real refusal: entries must
  be short plain-string pairs whose two sides stay close in length
  (casing/spacing fixes pass; a pasted paragraph posed as a
  "replacement" raises ``RulesError``).

Every function here is pure except ``register_rules`` (idempotent
mapping install, fully disclosed in its return dict).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stage3 import normalize as _normalize  # noqa: E402 (read-only reuse)

# New-edition revision key. Lives only in src/stage9/ + central-DB rows
# minted through the stage3 derive API; never written into stage3 files.
RULES_REVISION = "s9-corr-v2"

# The frozen base this edition supersedes (latest frozen table).
BASE_RULES_REVISION = "corr-v2"

# Stage9 additions: highly-determined casing/spacing fixes only.
ADDED_RULES = (
    ("Github", "GitHub"),
    ("Vscode", "VS Code"),
)

MAX_PATTERN_CHARS = 64
MAX_REPLACEMENT_CHARS = 64
# Shape gate: the two sides of a fix must stay close in length.
MAX_SIDE_DELTA = 16


class RulesError(ValueError):
    """FAIL: bad rule entry / live-entry replacement refused."""


def validate_rules(entries) -> tuple:
    """Check the exact-substring shape of a rule table (pure).

    Refuses (``RulesError``): non-pair entries, non-string or empty
    sides, identical sides, over-long sides, or sides whose lengths
    drift apart beyond ``MAX_SIDE_DELTA`` (that shape is a pasted
    passage, not a term fix). Returns the entries as a tuple.
    """
    if not isinstance(entries, (tuple, list)) or not entries:
        raise RulesError("rule table must be a non-empty tuple/list")
    clean = []
    for entry in entries:
        if (
            not isinstance(entry, (tuple, list))
            or len(entry) != 2
        ):
            raise RulesError("each rule must be a (pattern, replacement) pair")
        pattern, replacement = entry
        if not isinstance(pattern, str) or not pattern:
            raise RulesError("rule pattern must be a non-empty string")
        if not isinstance(replacement, str) or not replacement:
            raise RulesError("rule replacement must be a non-empty string")
        if pattern == replacement:
            raise RulesError("rule pattern == replacement (no-op entry refused)")
        if len(pattern) > MAX_PATTERN_CHARS:
            raise RulesError("rule pattern over %d chars" % (MAX_PATTERN_CHARS,))
        if len(replacement) > MAX_REPLACEMENT_CHARS:
            raise RulesError(
                "rule replacement over %d chars" % (MAX_REPLACEMENT_CHARS,)
            )
        if abs(len(replacement) - len(pattern)) > MAX_SIDE_DELTA:
            raise RulesError(
                "rule sides drift apart beyond %d chars"
                " (pasted passage refused)" % (MAX_SIDE_DELTA,)
            )
        clean.append((pattern, replacement))
    return tuple(clean)


def full_table() -> tuple:
    """The new-edition table: frozen base rows + Stage9 additions."""
    try:
        base = tuple(_normalize.CORRECTION_RULES[BASE_RULES_REVISION])
    except KeyError:
        raise RulesError(
            "frozen base table %r absent; refusing to invent one"
            % (BASE_RULES_REVISION,)
        )
    added = validate_rules(ADDED_RULES)
    base_patterns = {pattern for pattern, _ in base}
    for pattern, _ in added:
        if pattern in base_patterns:
            raise RulesError(
                "added pattern %r already in the frozen base" % (pattern,)
            )
    return base + added


def register_rules() -> dict:
    """Install the new table under ``RULES_REVISION`` (idempotent).

    In-memory only; ``src/stage3/`` files stay untouched. A live entry
    under the same key with different content is never replaced
    (``RulesError``); an identical live entry is a no-op success.
    """
    table = full_table()
    live = _normalize.CORRECTION_RULES.get(RULES_REVISION)
    if live is not None:
        if tuple(live) != table:
            raise RulesError(
                "live entry %r differs; refusing replacement" % (RULES_REVISION,)
            )
        return {
            "rules_revision": RULES_REVISION,
            "rules": len(table),
            "added": len(ADDED_RULES),
            "registered": False,
            "idempotent_retry": True,
        }
    _normalize.CORRECTION_RULES[RULES_REVISION] = table
    return {
        "rules_revision": RULES_REVISION,
        "rules": len(table),
        "added": len(ADDED_RULES),
        "registered": True,
        "idempotent_retry": False,
    }


def new_normalization_profile() -> dict:
    """A ``# 29`` profile carrying only the new rules revision."""
    register_rules()
    profile = dict(_normalize.DEFAULT_PROFILE)
    profile["correction_rules_revision"] = RULES_REVISION
    return profile


def apply_v2(segments: list) -> dict:
    """Run the frozen correction engine with the new table (pure)."""
    register_rules()
    return _normalize.apply_corrections(segments, RULES_REVISION)
