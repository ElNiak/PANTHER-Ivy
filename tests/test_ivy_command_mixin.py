"""Tests for IvyCommandMixin._build_ivy_model_setup_commands().

We cannot directly import IvyCommandMixin because it depends on panther.core
infrastructure.  Instead, we import the pure helper (classify_endpoint_type)
from _shared and reimplement the method logic in a lightweight fake class so
the tests run in isolation without PANTHER core on the path.
"""
import pytest
from typing import List
from unittest.mock import MagicMock

from .._shared import classify_endpoint_type


class FakeIvyCommandMixin:
    """Minimal harness reproducing _build_ivy_model_setup_commands logic."""

    def __init__(
        self,
        model_path=None,
        protocol="quic",
        role_name="server",
        test_name="",
    ):
        if model_path is not None:
            self.env_protocol_model_path = model_path
        self.role = MagicMock()
        self.role.name = role_name
        self.test_to_compile = test_name
        self.logger = MagicMock()
        self._protocol_name = protocol

    def get_protocol_name(self):
        return self._protocol_name

    # ---------- reimplementation matching ivy_command_mixin.py ----------

    def _build_ivy_model_setup_commands(self) -> List[str]:
        if not hasattr(self, "env_protocol_model_path"):
            self.logger.warning(
                "env_protocol_model_path is not set \u2014 skipping Ivy model setup commands"
            )
            return []

        model_path = self.env_protocol_model_path
        protocol_name = self.get_protocol_name()
        tests_dir = f"{protocol_name}_tests"
        tests_path = f"{model_path}/{tests_dir}"

        role = getattr(self, "role", None)
        role_name = (
            role.name
            if hasattr(role, "name")
            else str(role) if role else "server"
        )
        test_name = getattr(self, "test_to_compile", "")
        endpoint_type = classify_endpoint_type(test_name, role_name)

        _parts = test_name.lower().split("_")
        _pre_test = (
            _parts[: _parts.index("test")] if "test" in _parts else _parts
        )
        if not {"mim", "client", "server", "attacker"}.intersection(_pre_test):
            self.logger.warning(
                f"No endpoint keyword in test name '{test_name}'; "
                f"inferred '{endpoint_type}' from role '{role_name}'"
            )
        target_test_subdir = f"{endpoint_type}_tests"

        commands = [
            "echo 'Setting up Ivy model (endpoint-type-aware)...' >> /app/logs/compile/ivy_setup.log",
            f"echo 'Protocol: {protocol_name}, endpoint type: {endpoint_type}, test subdir: {target_test_subdir}' >> /app/logs/compile/ivy_setup.log",
            f"echo 'Updating include path from {model_path}' >> /app/logs/compile/ivy_setup.log",
            f"find '{model_path}' -path '{tests_path}' -prune -o -type f -name '*.ivy'"
            f" -exec echo {{}} ';' >> '/app/logs/compile/copied_ivy_files.list' 2>> /app/logs/compile/ivy_setup.log",
            f"find '{model_path}' -path '{tests_path}' -prune -o -type f -name '*.ivy' -print"
            f" -exec cp -f {{}} $PYTHON_IVY_DIR/ivy/include/1.7/ ';' >> /app/logs/compile/ivy_setup.log 2>&1",
            f"echo 'Copied non-test .ivy files from {model_path}' >> /app/logs/compile/ivy_setup.log",
            f"if [ -d '{tests_path}/{target_test_subdir}' ]; then "
            f"find '{tests_path}/{target_test_subdir}' -type f -name '*.ivy'"
            f" -exec echo {{}} ';' >> '/app/logs/compile/copied_ivy_files.list' 2>> /app/logs/compile/ivy_setup.log && "
            f"find '{tests_path}/{target_test_subdir}' -type f -name '*.ivy'"
            f" -exec cp -f {{}} $PYTHON_IVY_DIR/ivy/include/1.7/ ';' >> /app/logs/compile/ivy_setup.log 2>&1 && "
            f"echo 'Copied test files from {tests_path}/{target_test_subdir}' >> /app/logs/compile/ivy_setup.log; "
            f"else echo 'WARNING: test subdir {tests_path}/{target_test_subdir} not found \u2014 falling back to full tests copy' >> /app/logs/compile/ivy_setup.log && "
            f"find '{tests_path}' -type f -name '*.ivy'"
            f" -exec echo {{}} ';' >> '/app/logs/compile/copied_ivy_files.list' 2>> /app/logs/compile/ivy_setup.log && "
            f"find '{tests_path}' -type f -name '*.ivy'"
            f" -exec cp -f {{}} $PYTHON_IVY_DIR/ivy/include/1.7/ ';' >> /app/logs/compile/ivy_setup.log 2>&1; "
            f"fi",
            "ls -l $PYTHON_IVY_DIR/ivy/include/1.7/ >> /app/logs/compile/ivy_setup.log",
        ]
        return commands


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildIvyModelSetupCommands:
    """Unit tests for _build_ivy_model_setup_commands()."""

    def test_missing_model_path_returns_empty(self):
        """When env_protocol_model_path is not set, returns empty list and warns."""
        obj = FakeIvyCommandMixin()  # model_path=None -> attribute not set
        assert obj._build_ivy_model_setup_commands() == []
        obj.logger.warning.assert_called_once()

    def test_server_test_targets_server_tests_subdir(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
            role_name="client",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("server_tests" in cmd for cmd in commands)
        assert not any("client_tests" in cmd for cmd in commands)

    def test_client_test_targets_client_tests_subdir(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_client_test_stream",
            role_name="server",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("client_tests" in cmd for cmd in commands)

    def test_mim_test_targets_mim_tests_subdir(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_mim_test_forward",
            role_name="server",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("mim_tests" in cmd for cmd in commands)

    def test_commands_contain_python_ivy_dir_ref(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("$PYTHON_IVY_DIR" in cmd for cmd in commands)

    def test_commands_contain_prune_for_tests_dir(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("-prune" in cmd for cmd in commands)

    def test_fallback_logged_when_no_keyword_matches(self):
        """When no endpoint keyword in test name, logger.warning should be called."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_test_unknown",
            role_name="server",
        )
        obj._build_ivy_model_setup_commands()
        obj.logger.warning.assert_called()

    def test_no_fallback_warning_for_known_endpoint(self):
        """When endpoint keyword is present, no warning should be logged."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
            role_name="client",
        )
        obj._build_ivy_model_setup_commands()
        obj.logger.warning.assert_not_called()

    def test_commands_are_non_empty_list_of_strings(self):
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0
        assert all(isinstance(cmd, str) for cmd in commands)

    def test_attacker_test_maps_to_server_tests_subdir(self):
        """Attacker keyword maps to 'server' endpoint type."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_attacker_test_replay",
            role_name="client",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("server_tests" in cmd for cmd in commands)

    def test_protocol_name_appears_in_tests_path(self):
        """The generated commands reference {protocol}_tests as the tests dir."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            protocol="quic",
            test_name="quic_server_test_stream",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("quic_tests" in cmd for cmd in commands)

    def test_different_protocol_uses_correct_tests_dir(self):
        """With a different protocol name, the tests dir changes accordingly."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/tls",
            protocol="tls",
            test_name="tls_server_test_handshake",
        )
        commands = obj._build_ivy_model_setup_commands()
        assert any("tls_tests" in cmd for cmd in commands)

    def test_fallback_else_branch_in_if_command(self):
        """The if/else command includes a fallback when the subdir is missing."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_server_test_stream",
        )
        commands = obj._build_ivy_model_setup_commands()
        # The last shell command before ls should contain an else clause
        assert any("else echo 'WARNING:" in cmd for cmd in commands)

    def test_inferred_endpoint_from_role_when_no_keyword(self):
        """No endpoint keyword + server role -> inferred 'client' via oppose_role."""
        obj = FakeIvyCommandMixin(
            model_path="/opt/panther_ivy/protocol-testing/quic",
            test_name="quic_test_something",
            role_name="server",
        )
        commands = obj._build_ivy_model_setup_commands()
        # Should fall back to client (oppose of server)
        assert any("client_tests" in cmd for cmd in commands)
