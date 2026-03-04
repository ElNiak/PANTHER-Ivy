"""Tests for panther_ivy runner API."""
from pathlib import Path

import pytest

from api.runner import generate_test_commands, parse_test_output
from api.types import TestRunResult


class TestGenerateTestCommands:
    """Tests using explicit base_path (required parameter)."""

    BASE_PATH = "/opt/panther_ivy/protocol-testing"

    def test_basic_test_commands(self):
        result = generate_test_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path=self.BASE_PATH,
        )
        assert isinstance(result, TestRunResult)
        # Should include compile phase
        assert "ivyc" in " ".join(result.compile.compile_commands.commands)
        # Should include run phase
        run_cmd = " ".join(result.run_commands.commands)
        assert "quic_server_test_stream" in run_cmd

    def test_test_commands_with_seed(self):
        result = generate_test_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            seed=42,
            base_path=self.BASE_PATH,
        )
        run_cmd = " ".join(result.run_commands.commands)
        assert "seed=42" in run_cmd

    def test_test_commands_with_iterations(self):
        result = generate_test_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            iterations=5,
            base_path=self.BASE_PATH,
        )
        run_cmd = " ".join(result.run_commands.commands)
        assert "iters=5" in run_cmd

    def test_test_commands_with_target_addr(self):
        result = generate_test_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            target_addr="192.168.1.100",
            base_path=self.BASE_PATH,
        )
        run_cmd = " ".join(result.run_commands.commands)
        assert "192.168.1.100" in run_cmd


class TestParseTestOutput:
    def test_parse_no_violation(self):
        stdout = "test_completed\nNO_VIOLATION_FOUND\n"
        result = parse_test_output(stdout)
        assert result["passed"] is True
        assert result["verdict"] == "NO_VIOLATION_FOUND"

    def test_parse_assumption_failed(self):
        stdout = "assumption_failed(quic_server_test_stream)\n"
        result = parse_test_output(stdout)
        assert result["passed"] is False
        assert result["verdict"] == "NON_COMPLIANT"

    def test_parse_crash(self):
        stdout = ""
        stderr = "Segmentation fault (core dumped)"
        result = parse_test_output(stdout, stderr)
        assert result["passed"] is False
        assert result["verdict"] == "CRASH"

    def test_parse_empty_output(self):
        result = parse_test_output("")
        assert result["passed"] is False
        assert result["verdict"] == "INCONCLUSIVE"

    def test_parse_iut_crash_maps_to_crash(self):
        result = parse_test_output("", "connection reset by peer")
        assert result["passed"] is False
        assert result["verdict"] == "CRASH"

    def test_parse_protocol_activity_no_violation(self):
        stdout = "> quic_connected\n< quic_packet\n"
        result = parse_test_output(stdout)
        assert result["passed"] is True
        assert result["verdict"] == "NO_VIOLATION_FOUND"


class TestGenerateTestCommandsPathAgnostic:
    def test_generate_test_commands_requires_base_path(self):
        """base_path is required; calling without it raises ValueError."""
        with pytest.raises(TypeError):
            generate_test_commands(
                ivy_file=Path(
                    "protocol-testing/quic/quic_tests/"
                    "quic_server_test_stream.ivy"
                ),
                protocol="quic",
            )

    def test_generate_test_commands_with_explicit_base_path(self):
        result = generate_test_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path="/custom/path",
        )
        run_cmd = " ".join(result.run_commands.commands)
        assert "/custom/path" in result.run_commands.working_dir

    def test_generate_test_commands_raises_without_base_path(self):
        """Passing base_path=None explicitly should raise ValueError."""
        with pytest.raises(ValueError, match="base_path"):
            generate_test_commands(
                ivy_file=Path(
                    "protocol-testing/quic/quic_tests/"
                    "quic_server_test_stream.ivy"
                ),
                protocol="quic",
                base_path=None,
            )
