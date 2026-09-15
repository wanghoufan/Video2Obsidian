"""Stage9 Normalization + Paragraph, new editions (S9-T01~T02)."""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stage9.rules_v2 import (
    ADDED_RULES,
    BASE_RULES_REVISION,
    RULES_REVISION,
    RulesError,
    apply_v2,
    full_table,
    new_normalization_profile,
    register_rules,
    validate_rules,
)
from stage9.formatter_v2 import (
    BASE_FORMATTER_VERSION,
    FORMATTER_VERSION,
    PARA_PARAMS_V2,
    RULE_ORDER,
    WEAK_SPLIT_PUNCT,
    FormatterError,
    check_rule_order,
    new_render_profile,
    postprocess_paragraphs,
    render_with_v2,
    split_segments_for_engine,
)
from stage9.derive_v2 import (
    DeriveV2Error,
    derive_case4,
    derive_case5,
)

__all__ = [
    "ADDED_RULES",
    "BASE_FORMATTER_VERSION",
    "BASE_RULES_REVISION",
    "FORMATTER_VERSION",
    "PARA_PARAMS_V2",
    "RULE_ORDER",
    "RULES_REVISION",
    "WEAK_SPLIT_PUNCT",
    "DeriveV2Error",
    "FormatterError",
    "RulesError",
    "apply_v2",
    "check_rule_order",
    "derive_case4",
    "derive_case5",
    "full_table",
    "new_normalization_profile",
    "new_render_profile",
    "postprocess_paragraphs",
    "register_rules",
    "render_with_v2",
    "split_segments_for_engine",
    "validate_rules",
]
