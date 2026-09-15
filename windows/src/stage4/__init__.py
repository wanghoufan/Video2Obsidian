"""Stage4: Initial Canonical Publish + Atomic No-Cover + Output Ownership.

Implements STAGE4-PLAN S4-T01..S4-T05 (V1.8 Stage 4, ``# 69``).

Additive-only w.r.t. Stage1/Stage2/Stage3: this package imports
``stage1`` (read-only volume facts), ``stage2.store`` (central-DB DDL
shape), ``stage3.artifact_commit`` (read-only Rendered validation) and
``stage3.lineage`` (read-only lineage assembly plus the append-only
manifest writer) but never modifies ``src/stage1/``, ``src/stage2/`` or
``src/stage3/``, never invokes Whisper, and never executes any
Stage5+ step.
"""
