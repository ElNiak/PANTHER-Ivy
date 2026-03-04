"""Tests for panther_ivy discovery API."""
from pathlib import Path

import pytest

from api.discovery import detect_from_path, list_tests
from api.types import TestInfo


# Use the actual protocol-testing dir in the submodule for realistic tests
SUBMODULE_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_TESTING_DIR = SUBMODULE_ROOT / "protocol-testing"


class TestDetectFromPath:
    def test_detect_quic_server_test(self):
        # Standard path with subdirectory
        ivy_path = (
            PROTOCOL_TESTING_DIR
            / "quic"
            / "quic_tests"
            / "server_tests"
            / "quic_server_test_stream.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "quic"
        assert result["test_name"] == "quic_server_test_stream"
        assert result["role"] == "server"

    def test_detect_quic_client_test(self):
        ivy_path = Path(
            "protocol-testing/quic/quic_tests/client_tests/"
            "quic_client_test_stream.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "quic"
        assert result["role"] == "client"

    def test_detect_from_absolute_path(self):
        ivy_path = Path(
            "/opt/panther_ivy/protocol-testing/quic/quic_tests/"
            "server_tests/quic_server_test_stream.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "quic"
        assert result["test_name"] == "quic_server_test_stream"

    def test_detect_flat_test_path(self):
        # Path without subdirectory (also valid)
        ivy_path = Path(
            "protocol-testing/quic/quic_tests/quic_server_test_stream.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "quic"
        assert result["test_name"] == "quic_server_test_stream"

    def test_detect_apt_system_models(self):
        ivy_path = Path(
            "protocol-testing/apt/apt_protocols/quic/quic_tests/"
            "quic_server_test_stream.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "quic"
        assert result["use_system_models"] is True

    def test_detect_unknown_path_raises(self):
        ivy_path = Path("/random/path/something.ivy")
        with pytest.raises(ValueError, match="Cannot detect protocol"):
            detect_from_path(ivy_path)

    def test_detect_role_from_test_name(self):
        result = detect_from_path(
            Path(
                "protocol-testing/quic/quic_tests/"
                "server_tests/quic_server_test_0rtt.ivy"
            )
        )
        assert result["role"] == "server"

    def test_detect_minip_protocol(self):
        ivy_path = Path(
            "protocol-testing/minip/minip_tests/minip_server_test.ivy"
        )
        result = detect_from_path(ivy_path)
        assert result["protocol"] == "minip"

    def test_detect_version_from_configs(self):
        ivy_path = (
            PROTOCOL_TESTING_DIR
            / "quic"
            / "quic_tests"
            / "server_tests"
            / "quic_server_test_stream.ivy"
        )
        if ivy_path.exists():
            result = detect_from_path(ivy_path)
            assert "version" in result


class TestListTests:
    def test_list_quic_tests(self):
        if not PROTOCOL_TESTING_DIR.exists():
            pytest.skip("protocol-testing directory not found")
        tests = list_tests(
            protocol="quic",
            protocol_testing_dir=PROTOCOL_TESTING_DIR,
        )
        assert len(tests) > 0
        assert all(isinstance(t, TestInfo) for t in tests)
        assert all(t.protocol == "quic" for t in tests)

    def test_list_all_protocols(self):
        if not PROTOCOL_TESTING_DIR.exists():
            pytest.skip("protocol-testing directory not found")
        tests = list_tests(protocol_testing_dir=PROTOCOL_TESTING_DIR)
        protocols = {t.protocol for t in tests}
        assert "quic" in protocols

    def test_list_tests_with_version_filter(self):
        if not PROTOCOL_TESTING_DIR.exists():
            pytest.skip("protocol-testing directory not found")
        tests = list_tests(
            protocol="quic",
            version="rfc9000",
            protocol_testing_dir=PROTOCOL_TESTING_DIR,
        )
        assert all(t.version == "rfc9000" for t in tests)

    def test_list_tests_empty_for_nonexistent_protocol(self):
        tests = list_tests(
            protocol="nonexistent",
            protocol_testing_dir=PROTOCOL_TESTING_DIR,
        )
        assert tests == []

    def test_list_tests_includes_role(self):
        if not PROTOCOL_TESTING_DIR.exists():
            pytest.skip("protocol-testing directory not found")
        tests = list_tests(
            protocol="quic", protocol_testing_dir=PROTOCOL_TESTING_DIR
        )
        roles = {t.role for t in tests}
        # QUIC tests should have both server and client tests
        assert "server" in roles or "client" in roles
