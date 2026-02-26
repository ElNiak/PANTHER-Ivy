"""Tests for panther_ivy API data types."""
import pytest
from panther_ivy.api.types import (
    CommandResult,
    CompileResult,
    DiagnosticItem,
    ExecutionResult,
    TestInfo,
    TestRunResult,
)


class TestCommandResult:
    def test_create_with_defaults(self):
        result = CommandResult(
            commands=["echo hello"],
            environment={"FOO": "bar"},
            working_dir="/tmp",
        )
        assert result.commands == ["echo hello"]
        assert result.environment == {"FOO": "bar"}
        assert result.working_dir == "/tmp"

    def test_empty_commands(self):
        result = CommandResult(commands=[], environment={}, working_dir=".")
        assert result.commands == []

    def test_to_dict(self):
        result = CommandResult(
            commands=["ivyc target=test foo.ivy"],
            environment={"Z3_LIB": "/opt/z3/lib"},
            working_dir="/opt/panther_ivy",
        )
        d = result.to_dict()
        assert d["commands"] == ["ivyc target=test foo.ivy"]
        assert d["environment"]["Z3_LIB"] == "/opt/z3/lib"


class TestCompileResult:
    def test_create(self):
        setup = CommandResult(
            commands=["mkdir -p build"], environment={}, working_dir="."
        )
        compile_cmd = CommandResult(
            commands=["ivyc target=test foo.ivy"],
            environment={"Z3_LIB": "/opt/z3/lib"},
            working_dir="/opt/panther_ivy/protocol-testing/quic",
        )
        result = CompileResult(setup_commands=setup, compile_commands=compile_cmd)
        assert "ivyc" in result.compile_commands.commands[0]


class TestDiagnosticItem:
    def test_create(self):
        diag = DiagnosticItem(
            file="test.ivy",
            line=42,
            column=8,
            severity="error",
            message="type mismatch",
        )
        assert diag.severity == "error"
        assert diag.line == 42

    def test_to_dict(self):
        diag = DiagnosticItem(
            file="test.ivy",
            line=1,
            column=0,
            severity="warning",
            message="unused",
        )
        d = diag.to_dict()
        assert d["file"] == "test.ivy"
        assert d["severity"] == "warning"


class TestTestInfo:
    def test_create(self):
        info = TestInfo(
            name="quic_server_test_stream",
            protocol="quic",
            version="rfc9000",
            role="server",
            ivy_file="/path/to/test.ivy",
        )
        assert info.protocol == "quic"
        assert info.role == "server"


class TestTestRunResult:
    def test_create(self):
        compile_res = CompileResult(
            setup_commands=CommandResult(
                commands=[], environment={}, working_dir="."
            ),
            compile_commands=CommandResult(
                commands=["ivyc target=test foo.ivy"],
                environment={},
                working_dir=".",
            ),
        )
        run_cmds = CommandResult(
            commands=["./foo"], environment={}, working_dir="."
        )
        result = TestRunResult(compile=compile_res, run_commands=run_cmds)
        assert result.run_commands.commands == ["./foo"]


class TestExecutionResult:
    def test_create(self):
        result = ExecutionResult(
            exit_code=0, stdout="ok", stderr="", target="docker"
        )
        assert result.exit_code == 0
        assert result.target == "docker"
