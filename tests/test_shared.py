"""Tests for panther_ivy._shared pure verdict logic and role helpers."""
import pytest

from panther_ivy._shared import (
    VERDICT_IUT_CRASH,
    VERDICT_NO_VIOLATION_FOUND,
    VERDICT_NON_COMPLIANT,
    VERDICT_TESTER_CRASH,
    VERDICT_UNKNOWN,
    detect_role,
    determine_verdict,
    oppose_role,
)


class TestDetermineVerdict:
    def test_assumption_failed_returns_non_compliant(self):
        result = determine_verdict("assumption_failed(test)\n", "")
        assert result["verdict"] == VERDICT_NON_COMPLIANT

    def test_test_completed_returns_no_violation_found(self):
        result = determine_verdict("test_completed\n", "")
        assert result["verdict"] == VERDICT_NO_VIOLATION_FOUND

    def test_protocol_activity_returns_no_violation_found(self):
        result = determine_verdict("> quic_connected\n< quic_packet\n", "")
        assert result["verdict"] == VERDICT_NO_VIOLATION_FOUND

    def test_tester_crash_segfault(self):
        result = determine_verdict("", "Segmentation fault")
        assert result["verdict"] == VERDICT_TESTER_CRASH

    def test_tester_crash_sigabrt(self):
        result = determine_verdict("", "SIGABRT received")
        assert result["verdict"] == VERDICT_TESTER_CRASH

    def test_iut_crash_connection_reset(self):
        result = determine_verdict("", "connection reset")
        assert result["verdict"] == VERDICT_IUT_CRASH

    def test_iut_crash_timed_out(self):
        result = determine_verdict("", "timed out")
        assert result["verdict"] == VERDICT_IUT_CRASH

    def test_empty_output_returns_unknown(self):
        result = determine_verdict("", "")
        assert result["verdict"] == VERDICT_UNKNOWN

    def test_assumption_failed_takes_precedence_over_test_completed(self):
        stdout = "assumption_failed(test)\ntest_completed\n"
        result = determine_verdict(stdout, "")
        assert result["verdict"] == VERDICT_NON_COMPLIANT

    def test_multiple_assumption_failures_collected(self):
        stdout = (
            "assumption_failed(test_a)\n"
            "assumption_failed(test_b)\n"
        )
        result = determine_verdict(stdout, "")
        assert result["verdict"] == VERDICT_NON_COMPLIANT
        assert len(result["assumption_failures"]) == 2

    def test_crash_only_when_no_verdict_markers(self):
        # Crash indicators should NOT override assumption_failed
        stdout = "assumption_failed(test)\n"
        stderr = "Segmentation fault"
        result = determine_verdict(stdout, stderr)
        assert result["verdict"] == VERDICT_NON_COMPLIANT

    def test_details_populated_on_non_compliant(self):
        result = determine_verdict("assumption_failed(test)\n", "")
        assert len(result["details"]) > 0

    def test_details_populated_on_crash(self):
        result = determine_verdict("", "Segmentation fault")
        assert len(result["details"]) > 0


class TestVerdictEquivalence:
    """Verify _shared.determine_verdict matches mixin behavior."""

    @pytest.mark.parametrize(
        "stdout,stderr,expected_verdict",
        [
            ("assumption_failed(test)\n", "", "NON_COMPLIANT"),
            ("test_completed\n", "", "NO_VIOLATION_FOUND"),
            ("> quic_connected\n< quic_packet\n", "", "NO_VIOLATION_FOUND"),
            ("", "Segmentation fault", "TESTER_CRASH"),
            ("", "connection reset", "IUT_CRASH"),
            ("", "", "UNKNOWN"),
        ],
    )
    def test_determine_verdict_matches_mixin(
        self, stdout, stderr, expected_verdict
    ):
        result = determine_verdict(stdout, stderr)
        assert result["verdict"] == expected_verdict


class TestOpposeRole:
    def test_oppose_server_returns_client(self):
        assert oppose_role("server") == "client"

    def test_oppose_client_returns_server(self):
        assert oppose_role("client") == "server"


class TestDetectRole:
    def test_server_in_name(self):
        assert detect_role("quic_server_test_stream") == "server"

    def test_client_in_name(self):
        assert detect_role("quic_client_test_stream") == "client"

    def test_unknown_role(self):
        assert detect_role("quic_test_unknown") == "unknown"

    def test_server_suffix(self):
        assert detect_role("test_server") == "server"
