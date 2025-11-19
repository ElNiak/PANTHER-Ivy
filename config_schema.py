import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from omegaconf import OmegaConf
from pydantic import BaseModel, Field

from panther.config.core.models.plugin import ServicePluginConfig
from panther.config.core.models.service import ImplementationType, VersionBase

class AvailableTests(BaseModel):
    tests: List[Dict[str, str]] = Field(default_factory=list, description="List of available tests")

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
    "TEST_IMPL":"",
    "IVY_DEBUG": "1",
    "RUST_LOG": "debug", 
    "RUST_BACKTRACE": "1",
    "SOURCE_DIR": "/opt/",
    "IVY_DIR": "$SOURCE_DIR/panther_ivy",
    "PYTHON_IVY_DIR": "/root/.pyenv/versions/3.10.12/lib/python3.10/site-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/",
    "IVY_INCLUDE_PATH": "/opt/panther_ivy/ivy/include/1.7",
    "Z3_LIBRARY_DIRS": "$IVY_DIR/submodules/z3/build",
    "Z3_LIBRARY_PATH": "$IVY_DIR/submodules/z3/build", 
    "LD_LIBRARY_PATH": "$LD_LIBRARY_PATH:$IVY_DIR/submodules/z3/build",
    "PROOTPATH": "$SOURCE_DIR",
    "PYTHONPATH": "$PYTHONPATH:/opt/aioquic/src/:$IVY_DIR/submodules/z3/build/python",
    "ADDITIONAL_PATH": "/root/.pyenv/versions/3.10.12/bin:/go/bin:$IVY_DIR/submodules/z3/build:/root/.pyenv/plugins/pyenv-virtualenv/shims:/root/.pyenv/shims:/root/.pyenv/bin:/root/.pyenv/bin:/snap/bin",
    "ADDITIONAL_PYTHONPATH": "/app/implementations/quic-implementations/aioquic/src/:$IVY_DIR/submodules/z3/build/python:$PYTHON_IVY_DIR",
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
    "PANTHER_IVY_TICKET_PATH": "$PANTHER_IVY_BASE_PATH/$PROTOCOL_TESTED/last_session_ticket.txt"
}

# Direct parameter fields following PANTHER patterns

class PantherIvyVersion(VersionBase):
    """Version information for PantherIvy following PANTHER standards. (TODO not used)"""
    # Provide defaults for required base fields
    version: str = Field(default="", description="Version string")
    commit: str  = Field(default="", description="Git commit hash")
    dependencies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of dependencies"
    )
    
    # Additional fields beyond VersionBase
    env: Optional[Dict] = Field(default_factory=dict, description="Environment variables")
    parameters: Optional[Dict] = Field(default_factory=dict, description="Parameters")
    client: Optional[Dict] = Field(default_factory=dict, description="Client configuration")
    server: Optional[Dict] = Field(default_factory=dict, description="Server configuration")
    
class PantherIvyConfig(ServicePluginConfig):
    """Configuration for Panther Ivy tester service."""

    name: str = Field(default="panther_ivy", description="Implementation name")
    type: ImplementationType = Field(
        default=ImplementationType.TESTERS,
        description="Implementation type"
    )
    test: str = Field(default="", description="Test name for testers")
    use_system_models: bool = Field(
        default=False,
        description="Use system models for the test"
    )
    shadow_compatible: bool = Field(
        default=True,
        description="Whether compatible with Shadow network simulator"
    )
    gperf_compatible: bool = Field(
        default=True,
        description="Whether compatible with gperf profiling"
    )
    
    # protocol: str = Field(
    #     default="quic",
    #     description="Protocol tested by the implementation"
    # )
    # version: PantherIvyVersion = Field(
    #     default_factory=lambda: PantherIvyConfig.load_versions_from_files(),
    #     description="Version configuration"
    # )
    
    environment: Dict[str, str] = Field(
        default_factory=lambda: DEFAULT_ENVIRONMENT_VARIABLES.copy(),
        description="Environment variables"
    )
    # Direct parameter fields following PANTHER patterns
    tests_output_dir: str = Field(
        default="temp/",
        description="Directory where the tests output will be stored"
    )
    tests_build_dir: str = Field(
        default="build/",
        description="Directory where the tests will be built"
    )
    iterations_per_test: int = Field(
        default=1,
        description="Number of iterations per test"
    )
    internal_iterations_per_test: int = Field(
        default=300,
        description="Number of internal iterations per test when running the solver loop"
    )
    timeout: int = Field(
        default=120,
        description="Timeout for each test (in seconds)"
    )
    keep_alive: bool = Field(
        default=False,
        description="Keep the Ivy process alive after the tests"
    )
    run_in_docker: bool = Field(
        default=True,
        description="Run the tests in a Docker container"
    )
    get_tests_stats: bool = Field(
        default=True,
        description="Get the statistics of the tests"
    )
    build_mode: Optional[str] = Field(
        default=None,
        description="Build mode for compilation: '' (original/Shadow compatible), 'debug-asan', 'rel-lto', or 'release-static-pgo'",
        pattern=r"^(|debug-asan|rel-lto|release-static-pgo)$"
    )
    log_level_events: str = Field(
        default="DEBUG",
        description="Log level for Ivy events [Present (DEBUG) or Not Present (INFO)]"
    )
    log_level_binary: str = Field(
        default="DEBUG",
        description="Log level for Ivy binary (-g, -fsanitize=address) [Present (DEBUG) or Not Present (INFO)]"
    )
    optimization_level: str = Field(
        default=None,
        description="Optimization level for the Ivy binary (O0, O1, O2, O3) - O0 recommended for debugging"
    )
    

    @staticmethod
    def load_versions_from_files(
        version_configs_dir: str = f"{Path(os.path.dirname(__file__))}/version_configs/",
        protocol: str = "quic",
        version: Optional[str] = None,
        protocol_version_override: str = None) -> PantherIvyVersion:
        """Load version configurations dynamically from YAML files.
        
        Args:
            version_configs_dir: Directory containing version configs (auto-detected if None)
            protocol: Protocol name for version directory (default: quic)
            version: Specific version to load (loads first found if None)
        
        Returns:
            PantherIvyVersion configuration
        """
        import logging
        logging.debug("Loading PantherIvy versions with protocol: %s, version: %s", protocol, version)
        version = version if not protocol_version_override else protocol_version_override
        if version_configs_dir is None:
            # Auto-detect based on protocol
            base_dir = Path(os.path.dirname(__file__)) / "version_configs"
            version_configs_dir = str(base_dir / protocol)
            logging.debug("Using version configs directory: %s", version_configs_dir)
        # Fallback to base directory if protocol-specific directory doesn't exist
        if not os.path.exists(version_configs_dir):
            logging.warning(f"Protocol-specific directory {version_configs_dir} not found, trying base directory")
            version_configs_dir = str(Path(os.path.dirname(__file__)) / "version_configs")
        
        if not os.path.exists(version_configs_dir):
            logging.warning(f"Version configs directory {version_configs_dir} not found, using defaults")
            return PantherIvyVersion()
        
        logging.debug("Loading PantherIvy versions from %s", version_configs_dir)
        
        # Find version files
        version_files = [f for f in os.listdir(version_configs_dir) if f.endswith(".yaml")]
        if not version_files:
            logging.warning(f"No version files found in {version_configs_dir}, using defaults")
            return PantherIvyVersion()
        
        # Select specific version or first available
        target_file = None
        if version:
            target_file = f"{version}.yaml"
            if target_file not in version_files:
                logging.warning(f"Requested version {version} not found, using first available")
                target_file = None
        
        if target_file is None:
            target_file = sorted(version_files)[0]  # Use first available, sorted for determinism
        
        version_path = os.path.join(version_configs_dir, target_file)
        raw_version_config = OmegaConf.load(version_path)
        logging.debug("Loaded raw PantherIvy version config: %s", raw_version_config)
        
        # Create default instance and convert to dict for merging
        default_version = PantherIvyVersion()
        try:
            # Try Pydantic v2 method first
            default_dict = default_version.model_dump()
        except AttributeError:
            # Fall back to Pydantic v1 method
            default_dict = default_version.dict()
        
        merged_config = OmegaConf.merge(default_dict, raw_version_config)
        
        # Ensure client and server are in the config before conversion
        if 'client' not in merged_config or merged_config.client is None:
            merged_config.client = {}
        if 'server' not in merged_config or merged_config.server is None:
            merged_config.server = {}
        
        # Convert OmegaConf to dict and create proper Pydantic model
        version_dict = OmegaConf.to_container(merged_config, resolve=True)
        version_config = PantherIvyVersion(**version_dict)
        
        logging.debug("Loaded PantherIvy version %s from %s", version_config.version if hasattr(version_config, 'version') else 'unknown', target_file)
        return version_config

    @classmethod
    def create_with_protocol_context(cls, protocol=None):
        """Create PantherIvyConfig instance with optional protocol context.
        
        # TODO refactor duplicated code
        
        If protocol version is provided, loads version-specific configuration.
        Otherwise creates standard instance.
        
        Args:
            protocol: Optional protocol configuration containing version info
            
        Returns:
            PantherIvyConfig instance with appropriate version configuration
        """
        logging.debug("Creating PantherIvyConfig with protocol context")
        if protocol and hasattr(protocol, 'version') and protocol.version:
            try:
                version_config = cls.load_versions_from_files(
                    protocol_version_override=protocol.version
                )
                return cls(version=version_config)
            except (FileNotFoundError, ValueError) as e:
                raise ValueError(
                    f"Could not load protocol version {protocol.version}: {e}"
                ) from e
        return cls()
