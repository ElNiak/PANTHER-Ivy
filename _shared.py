"""Shared pure functions for panther_ivy verdict determination and role helpers.

Single source of truth for verdict logic, regex patterns, crash indicators,
and role utilities. Zero PANTHER imports - these are standalone pure functions.
"""
import re
from typing import Dict, List

# -- Verdict constants --
VERDICT_NON_COMPLIANT = "NON_COMPLIANT"
VERDICT_NO_VIOLATION_FOUND = "NO_VIOLATION_FOUND"
VERDICT_TESTER_CRASH = "TESTER_CRASH"
VERDICT_IUT_CRASH = "IUT_CRASH"
VERDICT_UNKNOWN = "UNKNOWN"

# -- Pre-compiled patterns --
ASSUMPTION_FAILED_PATTERN = re.compile(r"assumption_failed\(([^)]*)\)")
TEST_COMPLETED_PATTERN = re.compile(r"test_completed")
PROTOCOL_ACTIVITY_PATTERN = re.compile(r"^[<>]\s", re.MULTILINE)

# -- Crash indicators --
CRASH_INDICATORS_TESTER = [
    "segmentation fault",
    "sigsegv",
    "sigabrt",
    "core dumped",
    "aborted",
    "std::bad_alloc",
]

CRASH_INDICATORS_IUT = [
    "connection reset",
    "connection refused",
    "broken pipe",
    "timed out",
]


def determine_verdict(stdout: str, stderr: str) -> Dict[str, object]:
    """Determine Ivy test verdict from stdout/stderr output.

    Verdict precedence:
    1. assumption_failed(...) in stdout -> NON_COMPLIANT
    2. test_completed in stdout (no assumption_failed) -> NO_VIOLATION_FOUND
    3. Protocol activity (</>  lines, no assumption_failed) -> NO_VIOLATION_FOUND
    4. Tester crash (segfault/SIGSEGV, no markers) -> TESTER_CRASH
    5. IUT crash (connection reset/timeout, no markers) -> IUT_CRASH
    6. No output -> UNKNOWN

    Args:
        stdout: Standard output from the test binary.
        stderr: Standard error from the test binary.

    Returns:
        Dict with keys: verdict (str), details (list[str]),
        assumption_failures (list[str]).
    """
    verdict = VERDICT_UNKNOWN
    details: List[str] = []
    assumption_failures: List[str] = []

    has_stdout = bool(stdout and stdout.strip())
    has_stderr = bool(stderr and stderr.strip())

    if not has_stdout and not has_stderr:
        return {
            "verdict": VERDICT_UNKNOWN,
            "details": ["No stdout/stderr output available"],
            "assumption_failures": [],
        }

    # --- Check stdout for Ivy-specific markers ---
    if has_stdout:
        for match in ASSUMPTION_FAILED_PATTERN.finditer(stdout):
            assumption_failures.append(match.group(0))

        has_test_completed = TEST_COMPLETED_PATTERN.search(stdout) is not None

        if assumption_failures:
            verdict = VERDICT_NON_COMPLIANT
            details.append(f"Found {len(assumption_failures)} assumption failure(s)")
        elif has_test_completed:
            verdict = VERDICT_NO_VIOLATION_FOUND
            details.append("test_completed marker found, no assumption failures")
        elif PROTOCOL_ACTIVITY_PATTERN.search(stdout):
            verdict = VERDICT_NO_VIOLATION_FOUND
            details.append("Protocol activity detected without assumption failures")

    # --- Check for crash indicators (only if no verdict markers found) ---
    if verdict == VERDICT_UNKNOWN:
        combined = ((stdout or "") + "\n" + (stderr or "")).lower()

        for indicator in CRASH_INDICATORS_TESTER:
            if indicator in combined:
                verdict = VERDICT_TESTER_CRASH
                details.append(f"Crash indicator: {indicator}")
                break

        if verdict == VERDICT_UNKNOWN:
            for indicator in CRASH_INDICATORS_IUT:
                if indicator in combined:
                    verdict = VERDICT_IUT_CRASH
                    details.append(f"IUT crash indicator: {indicator}")
                    break

    return {
        "verdict": verdict,
        "details": details,
        "assumption_failures": assumption_failures,
    }


def oppose_role(role: str) -> str:
    """Return the opposite role.

    When testing a server IUT, Ivy acts as client (and vice versa).
    """
    return "client" if role == "server" else "server"


def detect_role(test_name: str) -> str:
    """Infer role from test name convention: *_server_* or *_client_*."""
    if "_server_" in test_name or test_name.endswith("_server"):
        return "server"
    if "_client_" in test_name or test_name.endswith("_client"):
        return "client"
    return "unknown"
