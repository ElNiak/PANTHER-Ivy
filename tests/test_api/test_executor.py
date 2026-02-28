"""Tests for panther_ivy executor API."""
from unittest.mock import MagicMock, patch

import pytest

from panther_ivy.api.executor import IvyExecutor
from panther_ivy.api.types import CommandResult, ExecutionResult


class TestIvyExecutor:
    """Tests for the IvyExecutor hybrid Docker/native execution."""

    def test_create_without_docker_image(self):
        executor = IvyExecutor()
        assert executor.docker_image is None

    def test_create_with_docker_image(self):
        executor = IvyExecutor(docker_image="panther_ivy:latest")
        assert executor.docker_image == "panther_ivy:latest"

    def test_native_fallback_when_no_docker(self):
        """When no docker image is set, should use native execution."""
        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["echo hello"],
            environment={},
            working_dir="/tmp",
        )

        result = executor.execute(cmd)
        assert isinstance(result, ExecutionResult)
        assert result.target == "host"

    @patch("subprocess.run")
    def test_native_execution_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="compiled ok",
            stderr="",
        )

        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["ivyc target=test test.ivy"],
            environment={},
            working_dir="/opt/ivy/include/1.7",
        )

        result = executor.execute(cmd)
        assert result.exit_code == 0
        assert result.stdout == "compiled ok"
        assert result.target == "host"

    @patch("subprocess.run")
    def test_native_execution_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error: test.ivy: line 42: type mismatch",
        )

        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["ivyc target=test test.ivy"],
            environment={},
            working_dir="/opt/ivy/include/1.7",
        )

        result = executor.execute(cmd)
        assert result.exit_code == 1
        assert "type mismatch" in result.stderr

    @patch("subprocess.run")
    def test_native_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ivyc not found")

        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["ivyc target=test test.ivy"],
            environment={},
            working_dir="/opt/ivy/include/1.7",
        )

        result = executor.execute(cmd)
        assert result.exit_code == 127
        assert "not found" in result.stderr.lower()

    @patch("subprocess.run")
    def test_docker_exec_path(self, mock_run):
        """When a running container is found, should use docker exec."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="compiled ok",
            stderr="",
        )

        executor = IvyExecutor(docker_image="panther_ivy:latest")
        executor._docker_available = True

        # Mock _find_running_container to return a container ID
        executor._find_running_container = MagicMock(return_value="abc123")

        cmd = CommandResult(
            commands=["ivyc target=test test.ivy"],
            environment={"BUILD_MODE": "rel-lto"},
            working_dir="/opt/ivy/include/1.7",
        )

        result = executor.execute(cmd)
        assert result.target == "docker"

        # Verify docker exec was called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "exec" in call_args
        assert "abc123" in call_args

    @patch("subprocess.run")
    def test_docker_run_path(self, mock_run):
        """When no running container but image exists, should use docker run."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="compiled ok",
            stderr="",
        )

        executor = IvyExecutor(docker_image="panther_ivy:latest")
        executor._docker_available = True
        executor._find_running_container = MagicMock(return_value=None)
        executor._image_available = MagicMock(return_value=True)

        cmd = CommandResult(
            commands=["ivyc target=test test.ivy"],
            environment={},
            working_dir="/opt/ivy/include/1.7",
        )

        result = executor.execute(cmd, workspace_root="/host/path")
        assert result.target == "docker"

        # Verify docker run was called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "run" in call_args
        assert "--rm" in call_args

    @patch("subprocess.run")
    def test_docker_run_volume_mount(self, mock_run):
        """Docker run should mount the workspace."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr="",
        )

        executor = IvyExecutor(docker_image="panther_ivy:latest")
        executor._docker_available = True
        executor._find_running_container = MagicMock(return_value=None)
        executor._image_available = MagicMock(return_value=True)

        cmd = CommandResult(
            commands=["echo test"],
            environment={},
            working_dir="/opt/ivy/include/1.7",
        )

        executor.execute(cmd, workspace_root="/my/workspace")

        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        vol_idx = call_args.index("-v")
        assert "/my/workspace:/workspace" in call_args[vol_idx + 1]

    @patch("subprocess.run")
    def test_fallback_chain(self, mock_run):
        """When Docker not available, should fall back to native."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="native", stderr="",
        )

        executor = IvyExecutor(docker_image="panther_ivy:latest")
        executor._docker_available = False

        cmd = CommandResult(
            commands=["echo hello"],
            environment={},
            working_dir="/tmp",
        )

        result = executor.execute(cmd)
        assert result.target == "host"

    @patch("subprocess.run")
    def test_multiple_commands_stop_on_failure(self, mock_run):
        """Multiple commands should stop at first failure."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="ok", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="fail"),
        ]

        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["echo setup", "ivyc test.ivy"],
            environment={},
            working_dir="/tmp",
        )

        result = executor.execute(cmd)
        assert result.exit_code == 1
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_environment_variables_passed(self, mock_run):
        """Environment variables should be passed to subprocess."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr="",
        )

        executor = IvyExecutor()
        executor._docker_available = False

        cmd = CommandResult(
            commands=["echo test"],
            environment={"BUILD_MODE": "rel-lto", "Z3_BUILD_MODE": "rel-lto"},
            working_dir="/tmp",
        )

        executor.execute(cmd)

        call_kwargs = mock_run.call_args[1]
        assert "BUILD_MODE" in call_kwargs.get("env", {})
        assert call_kwargs["env"]["BUILD_MODE"] == "rel-lto"


class TestExecutionResult:
    def test_to_dict(self):
        result = ExecutionResult(
            exit_code=0,
            stdout="ok",
            stderr="",
            target="docker",
        )
        d = result.to_dict()
        assert d["exit_code"] == 0
        assert d["target"] == "docker"
