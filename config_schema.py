import logging
import os
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field

from panther.config.core.models.service import (
    ImplementationConfig,
    ImplementationType,
    ProtocolConfig,
    ServiceConfig,
    VersionBase,
)


class AvailableTests(BaseModel):
    tests: List[Dict[str, str]] = Field(
        default_factory=list, description="List of available tests"
    )

    @staticmethod
    def load_tests_from_directory(tests_dir: str) -> "AvailableTests":
        """Load all Ivy files available from protocol-testing folders."""
        logging.debug("Loading tests from %s", tests_dir)
        tests = []
        for root, _, files in os.walk(tests_dir):
            for file in files:
                if file.endswith(".ivy") and "test" in file:  # TODO
                    test_path = os.path.relpath(root, tests_dir)
                    test_type = os.path.basename(root)
                    tests.append(
                        {
                            "path": test_path,
                            "type": test_type.replace("_tests", ""),  # TODO
                            "name": file,
                            "enabled": False,
                            "description": "",
                        }
                    )
                    logging.debug(
                        "Found test: %s, type: %s, name: %s",
                        test_path,
                        test_type.replace("_tests", ""),
                        file,
                    )
        # Sort tests by name to ensure deterministic order
        tests.sort(key=lambda x: x["name"])
        return AvailableTests(tests=tests)


class Test(BaseModel):
    name: str = Field(..., description="Test name")
    protocol: str = Field(..., description="Protocol name")
    endpoint: str = Field(..., description="Test endpoint")


# Standard environment variables following PANTHER patterns with simplified path resolution
DEFAULT_ENVIRONMENT_VARIABLES = {
    "PROTOCOL_TESTED": "",
    "TEST_IMPL": "",
    "IVY_DEBUG": "1",
    "RUST_LOG": "debug",
    "RUST_BACKTRACE": "1",
    "SOURCE_DIR": "/opt/",
    "IVY_DIR": "$SOURCE_DIR/panther_ivy",
    # TODO: This version should be resolved dynamically rather than hardcoded
    "PYTHON_IVY_DIR": "/root/.pyenv/versions/3.10.12/lib/python3.10/site-packages/panther_ms_ivy-1.10.1-py3.10-linux-x86_64.egg/",
    "IVY_INCLUDE_PATH": "/opt/panther_ivy/ivy/include/1.7",
    # Z3_LIBRARY_DIRS, Z3_LIBRARY_PATH, and LD_LIBRARY_PATH are intentionally
    # omitted here. They are only needed when z3_source=local and are added
    # conditionally by PantherIvyServiceManager._get_ivy_environment_variables().
    "PROOTPATH": "$SOURCE_DIR",
    "PYTHONPATH": "$PYTHONPATH:/opt/aioquic/src/",
    "ADDITIONAL_PATH": "/root/.pyenv/versions/3.10.12/bin:/go/bin:/root/.pyenv/plugins/pyenv-virtualenv/shims:/root/.pyenv/shims:/root/.pyenv/bin:/root/.pyenv/bin:/snap/bin",
    "ADDITIONAL_PYTHONPATH": "/app/implementations/quic-implementations/aioquic/src/:$PYTHON_IVY_DIR",
    # Protocol path configuration
    "PANTHER_IVY_BASE_PATH": "$IVY_DIR/protocol-testing",
    "PANTHER_IVY_APT_SUBPATH": "apt/apt_protocols",
    "PANTHER_IVY_STANDARD_SUBPATH": "",
    "PROTOCOL_PATH": "$PANTHER_IVY_BASE_PATH/$PROTOCOL_TESTED",
    "ZRTT_SSLKEYLOGFILE": "$PROTOCOL_PATH/last_tls_key.txt",
    "RETRY_TOKEN_FILE": "$PROTOCOL_PATH/last_retry_token.txt",
    "NEW_TOKEN_FILE": "$PROTOCOL_PATH/last_new_token.txt",
    "ENCRYPT_TICKET_FILE": "$PROTOCOL_PATH/last_encrypt_session_ticket.txt",
    "SESSION_TICKET_FILE": "$PROTOCOL_PATH/last_session_ticket_cb.txt",
    "SAVED_PACKET": "$PROTOCOL_PATH/saved_packet.txt",
    "initial_max_stream_id_bidi": "$PROTOCOL_PATH/initial_max_stream_id_bidi.txt",
    "active_connection_id_limit": "$PROTOCOL_PATH/active_connection_id_limit.txt",
    "initial_max_stream_data_bidi_local": "$PROTOCOL_PATH/initial_max_stream_data_bidi_local.txt",
    "initial_max_stream_data_bidi_remote": "$PROTOCOL_PATH/initial_max_stream_data_bidi_remote.txt",
    "initial_max_stream_data_uni": "$PROTOCOL_PATH/initial_max_stream_data_uni.txt",
    "initial_max_data": "$PROTOCOL_PATH/initial_max_data.txt",
    # Protocol-specific certificate and key paths
    "PANTHER_IVY_CERT_PATH": "$PANTHER_IVY_BASE_PATH/$PROTOCOL_TESTED/leaf_cert.pem",
    "PANTHER_IVY_KEY_PATH": "$PANTHER_IVY_BASE_PATH/$PROTOCOL_TESTED/leaf_cert.key",
    "PANTHER_IVY_TICKET_PATH": "$PANTHER_IVY_BASE_PATH/$PROTOCOL_TESTED/last_session_ticket.txt",
}

# Direct parameter fields following PANTHER patterns


class PantherIvyVersion(VersionBase):
    """Version information for PantherIvy following PANTHER standards."""

    # Provide defaults for required base fields
    version: str = Field(default="", description="Version string")
    commit: str = Field(default="", description="Git commit hash")
    dependencies: List[Dict[str, str]] = Field(
        default_factory=list, description="List of dependencies"
    )

    # Additional fields beyond VersionBase
    env: Optional[Dict] = Field(
        default_factory=dict, description="Environment variables"
    )
    parameters: Optional[Dict] = Field(default_factory=dict, description="Parameters")
    client: Optional[Dict] = Field(
        default_factory=dict, description="Client configuration"
    )
    server: Optional[Dict] = Field(
        default_factory=dict, description="Server configuration"
    )


class PantherIvyConfig(ServiceConfig):
    """Panther-Ivy formal verification tester configuration.

    Integration with Microsoft's Ivy formal verification tool for
    specification-based protocol testing. Ivy generates test traffic from
    formal protocol models and verifies implementation compliance.

    Warning:
        Ivy integration requires formal protocol specifications and is
        intended for advanced users familiar with formal verification.
        First build takes ~30 minutes due to Z3 compilation.

    Z3 Build Modes (``z3_source``):
        - **local** -- builds Z3 from submodule (~30 min), full compatibility
        - **pip** -- uses ``pip install z3-solver`` (faster, limited features)

    Compilation Modes (``build_mode``):
        - **(empty)** -- original method, Shadow NS compatible
        - **debug-asan** -- AddressSanitizer (``-O1 -g -fsanitize=address``)
        - **rel-lto** -- Link Time Optimization (``-O3 -flto``)
        - **release-static-pgo** -- PGO + static linking (``-fprofile-use``)

    Language: C/C++ + Python | Source: panther_ivy submodule
    Build time: ~30 min (first build) | Docker image: ~1GB

    Example YAML::

        services:
          tester:
            implementation:
              name: panther_ivy
              type: testers
            protocol:
              name: quic
              version: rfc9000
              role: server
    """

    VERSION_CLASS: ClassVar[Optional[type]] = PantherIvyVersion

    # Override required fields with plugin-specific defaults
    implementation: ImplementationConfig = Field(
        default_factory=lambda: ImplementationConfig(
            name="panther_ivy", type="testers"
        ),
        description="Implementation configuration",
    )
    protocol: ProtocolConfig = Field(
        default_factory=lambda: ProtocolConfig(name="quic", role="server"),
        description="Protocol configuration",
    )

    # Typed version (loaded from version_configs/)
    version: PantherIvyVersion = Field(
        default_factory=lambda: PantherIvyConfig.load_version(),
        description="Version configuration",
    )

    test: str = Field(default="", description="Test name for testers")
    use_system_models: bool = Field(
        default=False, description="Use system models for the test"
    )

    environment: Dict[str, str] = Field(
        default_factory=lambda: DEFAULT_ENVIRONMENT_VARIABLES.copy(),
        description="Environment variables",
    )
    # Direct parameter fields following PANTHER patterns
    tests_output_dir: str = Field(
        default="temp/", description="Directory where the tests output will be stored"
    )
    tests_build_dir: str = Field(
        default="build/", description="Directory where the tests will be built"
    )
    iterations_per_test: int = Field(
        default=1, description="Number of iterations per test"
    )
    internal_iterations_per_test: int = Field(
        default=300,
        description="Number of internal iterations per test when running the solver loop",
    )
    timeout: int = Field(default=120, description="Timeout for each test (in seconds)")
    keep_alive: bool = Field(
        default=False, description="Keep the Ivy process alive after the tests"
    )
    run_in_docker: bool = Field(
        default=True, description="Run the tests in a Docker container"
    )
    get_tests_stats: bool = Field(
        default=True, description="Get the statistics of the tests"
    )
    build_mode: Optional[str] = Field(
        default=None,
        description="Build mode for compilation: '' (original/Shadow compatible), 'debug-asan', 'rel-lto', or 'release-static-pgo'",
        pattern=r"^(|debug-asan|rel-lto|release-static-pgo)$",
    )
    z3_source: Optional[str] = Field(
        default="local",
        description="Z3 source: 'local' builds from submodule (~30 min), 'pip' uses pip z3-solver only (faster)",
        pattern=r"^(local|pip)$",
    )
    log_level_events: str = Field(
        default="DEBUG",
        description="Log level for Ivy events [Present (DEBUG) or Not Present (INFO)]",
    )
    log_level_binary: str = Field(
        default="DEBUG",
        description="Log level for Ivy binary (-g, -fsanitize=address) [Present (DEBUG) or Not Present (INFO)]",
    )
    optimization_level: str = Field(
        default=None,
        description="Optimization level for the Ivy binary (O0, O1, O2, O3) - O0 recommended for debugging",
    )

    @classmethod
    def load_version(
        cls,
        version_configs_dir: Optional[str] = None,
        version: Optional[str] = None,
        protocol_version_override: Optional[str] = None,
    ):
        """Override to look in ``version_configs/quic/`` subdirectory."""
        if version_configs_dir is None:
            quic_dir = Path(os.path.dirname(__file__)) / "version_configs" / "quic"
            if quic_dir.exists():
                version_configs_dir = str(quic_dir)
        return super().load_version(version_configs_dir, version, protocol_version_override)
