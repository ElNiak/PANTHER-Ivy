"""Shared utilities re-exported from package root for API layer.

This module re-exports panther_ivy._shared names that the API layer
depends on, preserving the zero-PANTHER-imports contract while
eliminating code duplication.

The root _shared.py is the single source of truth for verdict logic,
regex patterns, crash indicators, and role utilities.
"""

from .._shared import (  # relative import: api/ -> parent package -> _shared.py
    ASSUMPTION_FAILED_PATTERN,
    CRASH_INDICATORS_IUT,
    CRASH_INDICATORS_TESTER,
    PROTOCOL_ACTIVITY_PATTERN,
    TEST_COMPLETED_PATTERN,
    VERDICT_IUT_CRASH,
    VERDICT_NON_COMPLIANT,
    VERDICT_NO_VIOLATION_FOUND,
    VERDICT_TESTER_CRASH,
    VERDICT_UNKNOWN,
    classify_endpoint_type,
    detect_role,
    determine_verdict,
    oppose_role,
)

__all__ = [
    "ASSUMPTION_FAILED_PATTERN",
    "CRASH_INDICATORS_IUT",
    "CRASH_INDICATORS_TESTER",
    "PROTOCOL_ACTIVITY_PATTERN",
    "TEST_COMPLETED_PATTERN",
    "VERDICT_IUT_CRASH",
    "VERDICT_NON_COMPLIANT",
    "VERDICT_NO_VIOLATION_FOUND",
    "VERDICT_TESTER_CRASH",
    "VERDICT_UNKNOWN",
    "classify_endpoint_type",
    "detect_role",
    "determine_verdict",
    "oppose_role",
]
