"""Tests for panther_ivy compiler API."""
from pathlib import Path

import pytest

from panther_ivy.api.compiler import (
    generate_compile_commands,
    parse_compile_output,
)
from panther_ivy.api.types import CommandResult, CompileResult, DiagnosticItem


SUBMODULE_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_TESTING_DIR = SUBMODULE_ROOT / "protocol-testing"


class TestGenerateCompileCommands:
    """Tests using explicit base_path (required parameter)."""

    BASE_PATH = "/opt/panther_ivy/protocol-testing"

    def test_basic_compile(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path=self.BASE_PATH,
        )
        assert isinstance(result, CompileResult)
        assert isinstance(result.compile_commands, CommandResult)
        # Must contain ivyc invocation
        compile_cmd = " ".join(result.compile_commands.commands)
        assert "ivyc" in compile_cmd
        assert "target=test" in compile_cmd
        assert "quic_server_test_stream" in compile_cmd

    def test_compile_includes_test_iters(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            test_iters=500,
            base_path=self.BASE_PATH,
        )
        compile_cmd = " ".join(result.compile_commands.commands)
        assert "test_iters=500" in compile_cmd

    def test_compile_working_dir_is_protocol_dir(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path=self.BASE_PATH,
        )
        # Working dir should point to the protocol model directory
        assert "quic" in result.compile_commands.working_dir

    def test_compile_setup_creates_build_dir(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path=self.BASE_PATH,
        )
        setup_cmd = " ".join(result.setup_commands.commands)
        assert "mkdir" in setup_cmd

    def test_compile_auto_detects_protocol(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            base_path=self.BASE_PATH,
        )
        compile_cmd = " ".join(result.compile_commands.commands)
        assert "quic_server_test_stream" in compile_cmd

    def test_compile_with_build_mode(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            build_mode="debug-asan",
            base_path=self.BASE_PATH,
        )
        assert isinstance(result.compile_commands.environment, dict)
        assert result.compile_commands.environment.get("BUILD_MODE") == "debug-asan"

    def test_compile_nonexistent_protocol_raises(self):
        with pytest.raises(ValueError):
            generate_compile_commands(
                ivy_file=Path("/random/path/test.ivy"),
                base_path="/some/path",
            )


class TestGenerateCompileCommandsPathAgnostic:
    def test_generate_compile_commands_requires_base_path(self):
        """base_path is required; calling without it raises TypeError."""
        with pytest.raises(TypeError):
            generate_compile_commands(
                ivy_file=Path(
                    "protocol-testing/quic/quic_tests/"
                    "quic_server_test_stream.ivy"
                ),
                protocol="quic",
            )

    def test_generate_compile_commands_with_explicit_base_path(self):
        result = generate_compile_commands(
            ivy_file=Path(
                "protocol-testing/quic/quic_tests/"
                "quic_server_test_stream.ivy"
            ),
            protocol="quic",
            base_path="/custom/path",
        )
        assert "/custom/path" in result.compile_commands.working_dir

    def test_generate_compile_commands_raises_without_base_path(self):
        """Passing base_path=None explicitly should raise ValueError."""
        with pytest.raises(ValueError, match="base_path"):
            generate_compile_commands(
                ivy_file=Path(
                    "protocol-testing/quic/quic_tests/"
                    "quic_server_test_stream.ivy"
                ),
                protocol="quic",
                base_path=None,
            )


class TestParseCompileOutput:
    def test_parse_success_no_errors(self):
        stdout = "Compiling quic_server_test_stream.ivy...\nDone.\n"
        stderr = ""
        diags = parse_compile_output(stdout, stderr)
        assert diags == []

    def test_parse_error_with_line_number(self):
        stderr = (
            "error: quic_server_test_stream.ivy: "
            "line 42: type mismatch in assignment"
        )
        diags = parse_compile_output("", stderr)
        assert len(diags) >= 1
        assert diags[0].severity == "error"
        assert diags[0].line == 42
        assert "type mismatch" in diags[0].message

    def test_parse_multiple_errors(self):
        stderr = (
            'error: test.ivy: line 10: undefined symbol "foo"\n'
            "error: test.ivy: line 20: type mismatch\n"
        )
        diags = parse_compile_output("", stderr)
        assert len(diags) == 2
        assert diags[0].line == 10
        assert diags[1].line == 20

    def test_parse_warning(self):
        stderr = 'warning: test.ivy: line 5: unused variable "x"'
        diags = parse_compile_output("", stderr)
        assert len(diags) >= 1
        assert diags[0].severity == "warning"

    def test_parse_ivy_error_format(self):
        # Ivy sometimes outputs: "file.ivy: line N: error: message"
        stderr = (
            "quic_server_test_stream.ivy: line 100: "
            'error: cannot resolve type "frame"'
        )
        diags = parse_compile_output("", stderr)
        assert len(diags) >= 1
        assert diags[0].line == 100
        assert diags[0].severity == "error"

    def test_parse_empty_output(self):
        diags = parse_compile_output("", "")
        assert diags == []
