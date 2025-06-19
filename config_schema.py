import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from omegaconf import OmegaConf
from pydantic import BaseModel, Field

from panther.config.core.models.plugin import ServicePluginConfig
from panther.config.core.models.service import ImplementationType

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

class EnvironmentVarConfig(BaseModel):
    PROTOCOL_TESTED: str = Field(default="", description="Protocol being tested")
    RUST_LOG: str = Field(default="debug", description="Rust log level")
    RUST_BACKTRACE: str = Field(default="1", description="Enable Rust backtrace")
    SOURCE_DIR: str = Field(default="/opt/", description="Source directory")
    IVY_DIR: str = Field(default="$SOURCE_DIR/panther_ivy", description="Ivy directory")
    PYTHON_IVY_DIR: str = Field(
        default="/usr/local/lib/python3.10/dist-packages/",
        description="Python Ivy directory"
    )
    IVY_INCLUDE_PATH: str = Field(
        default="$IVY_INCLUDE_PATH:/usr/local/lib/python3.10/dist-packages/ivy/include/1.7",
        description="Ivy include path"
    )
    Z3_LIBRARY_DIRS: str = Field(
        default="$IVY_DIR/submodules/z3/build",
        description="Z3 library directories"
    )
    Z3_LIBRARY_PATH: str = Field(
        default="$IVY_DIR/submodules/z3/build",
        description="Z3 library path"
    )
    LD_LIBRARY_PATH: str = Field(
        default="$LD_LIBRARY_PATH:$IVY_DIR/submodules/z3/build",
        description="LD library path"
    )
    PROOTPATH: str = Field(default="$SOURCE_DIR", description="Proot path")
    ADDITIONAL_PYTHONPATH: str = Field(
        default="/app/implementations/quic-implementations/aioquic/src/:$IVY_DIR/submodules/z3/build/python:$PYTHON_IVY_DIR",
        description="Additional Python path"
    )
    ADDITIONAL_PATH: str = Field(
        default="/go/bin:$IVY_DIR/submodules/z3/build",
        description="Additional PATH"
    )

class Parameter(BaseModel):
    """Parameter configuration."""
    value: str = Field(..., description="Parameter value")
    description: str = Field(..., description="Parameter description")


class ParametersConfig(BaseModel):
    tests_output_dir: Parameter = Field(
        default_factory=lambda: Parameter(
            value="temp/", description="Directory where the tests output will be stored"
        ),
        description="Tests output directory" # TODO redirect directly to the network environment shared volume (/app/logs ?)
    )
    tests_build_dir: Parameter = Field(
        default_factory=lambda: Parameter(
            value="build/", description="Directory where the tests will be built"
        ),
        description="Tests build directory"
    )
    iterations_per_test: Parameter = Field(
        default_factory=lambda: Parameter(
            value="1", description="Number of iterations per test"
        ),
        description="Iterations per test"
    )
    internal_iterations_per_test: Parameter = Field(
        default_factory=lambda: Parameter(
            value="300", description="Number of internal iterations per test when running the solver loop"
        ),
        description="Internal iterations per test"
    )
    timeout: Parameter = Field(
        default_factory=lambda: Parameter(
            value="120", description="Timeout for each test (in seconds)"
        ),
        description="Test timeout"
    )
    keep_alive: Parameter = Field(
        default_factory=lambda: Parameter(
            value="False", description="Keep the Ivy process alive after the tests"
        ),
        description="Keep alive flag"
    )
    run_in_docker: Parameter = Field(
        default_factory=lambda: Parameter(
            value="True", description="Run the tests in a Docker container"
        ),
        description="Run in Docker flag"
    )
    get_tests_stats: Parameter = Field(
        default_factory=lambda: Parameter(
            value="True", description="Get the statistics of the tests"
        ),
        description="Get test statistics flag"
    )
    log_level: Parameter = Field(
        default_factory=lambda: Parameter(
            value="DEBUG", description="Log level for Ivy"
        ),
        description="Log level"
    )

class PantherIvyVersion(BaseModel):
    version: str = Field(default="", description="Version string")
    commit: str = Field(default="", description="Git commit hash")
    dependencies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of dependencies"
    )
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
    protocol: str = Field(
        default="quic",
        description="Protocol tested by the implementation"
    )
    version: PantherIvyVersion = Field(
        default_factory=lambda: PantherIvyConfig.load_versions_from_files(),
        description="Version configuration"
    )
    environment: EnvironmentVarConfig = Field(
        default_factory=EnvironmentVarConfig,
        description="Environment variable configuration"
    )
    parameters: ParametersConfig = Field(
        default_factory=ParametersConfig,
        description="Parameters configuration"
    )

    @staticmethod
    def load_versions_from_files(
        version_configs_dir: str = f"{Path(os.path.dirname(__file__))}/version_configs/quic/") -> PantherIvyVersion:
        """Load version configurations dynamically from YAML files."""
        logging.debug("Loading PantherIvy versions from %s", version_configs_dir)
        for version_file in os.listdir(version_configs_dir):
            if version_file.endswith(".yaml"):
                version_path = os.path.join(version_configs_dir, version_file)
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
                    
                version_config = OmegaConf.to_object(merged_config)
                    
                logging.debug("Loaded PantherIvy version %s", version_config)
                return version_config
