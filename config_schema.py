from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from omegaconf import OmegaConf

from panther.plugins.services.iut.config_schema import (
    ImplementationConfig,
    Parameter,
    VersionBase,
)
from panther.plugins.services.iut.config_schema import ImplementationType


@dataclass
class AvailableTests:
    tests: List[str] = field(default_factory=list)

    @staticmethod
    def load_tests_from_directory(tests_dir: str) -> "AvailableTests":
        """Load all Ivy files available from protocol-testing folders."""
        logging.debug(f"Loading tests from {tests_dir}")
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
                        f"Found test: {test_path}, type: {test_type.replace('_tests', '')}, name: {file}"
                    )
        return AvailableTests(tests=tests)


@dataclass
class Test:
    name: str
    protocol: str
    endpoint: str


@dataclass
class EnvironmentConfig:
    PROTOCOL_TESTED: str = ""
    RUST_LOG: str = "debug"
    RUST_BACKTRACE: str = "1"
    SOURCE_DIR: str = "/opt/"
    IVY_DIR: str = "$SOURCE_DIR/panther_ivy"
    PYTHON_IVY_DIR: str = "/usr/local/lib/python3.10/dist-packages/"
    IVY_INCLUDE_PATH: str = (
        "$IVY_INCLUDE_PATH:/usr/local/lib/python3.10/dist-packages/ivy/include/1.7"
    )
    Z3_LIBRARY_DIRS: str = "$IVY_DIR/submodules/z3/build"
    Z3_LIBRARY_PATH: str = "$IVY_DIR/submodules/z3/build"
    LD_LIBRARY_PATH: str = "$LD_LIBRARY_PATH:$IVY_DIR/submodules/z3/build"
    PROOTPATH: str = "$SOURCE_DIR"
    ADDITIONAL_PYTHONPATH: str = (
        "/app/implementations/quic-implementations/aioquic/src/:$IVY_DIR/submodules/z3/build/python:$PYTHON_IVY_DIR"
    )
    ADDITIONAL_PATH: str = "/go/bin:$IVY_DIR/submodules/z3/build"


@dataclass
class ParametersConfig:
    tests_output_dir: Parameter = field(
        default_factory=lambda: Parameter(
            value="temp/", description="Directory where the tests output will be stored"
        )
    )
    tests_build_dir: Parameter = field(
        default_factory=lambda: Parameter(
            value="build/", description="Directory where the tests will be built"
        )
    )
    iterations_per_test: Parameter = field(
        default_factory=lambda: Parameter(
            value="1", description="Number of iterations per test"
        )
    )
    internal_iterations_per_test: Parameter = field(
        default_factory=lambda: Parameter(
            value="300", description="Number of internal iterations per test"
        )
    )
    timeout: Parameter = field(
        default_factory=lambda: Parameter(
            value="120", description="Timeout for each test (in seconds)"
        )
    )
    keep_alive: Parameter = field(
        default_factory=lambda: Parameter(
            value="False", description="Keep the Ivy process alive after the tests"
        )
    )
    run_in_docker: Parameter = field(
        default_factory=lambda: Parameter(
            value="True", description="Run the tests in a Docker container"
        )
    )
    get_tests_stats: Parameter = field(
        default_factory=lambda: Parameter(
            value="True", description="Get the statistics of the tests"
        )
    )
    log_level: Parameter = field(
        default_factory=lambda: Parameter(
            value="DEBUG", description="Log level for Ivy"
        )
    )


@dataclass
class PantherIvyVersion(VersionBase):
    version: str = ""
    commit: str = ""
    dependencies: List[Dict[str, str]] = field(default_factory=list)
    env: Optional[Dict] = field(default_factory=dict)
    parameters: Optional[Dict] = field(default_factory=dict)
    client: Optional[Dict] = field(default_factory=dict)
    server: Optional[Dict] = field(default_factory=dict)


@dataclass
class PantherIvyConfig(ImplementationConfig):
    name: str = "panther_ivy"  # Implementation name
    type: ImplementationType = (
        ImplementationType.testers
    )  # Default type for panther_ivy
    test: str = field(default="")  # Test name for testers
    use_system_models: bool = field(default=False)
    # Use system models for the test
    shadow_compatible: bool = field(default=True)
    gperf_compatible: bool = field(default=True)
    protocol: str = field(default="quic")  # Protocol tested by the implementation
    version: PantherIvyVersion = field(
        default_factory=lambda: PantherIvyConfig.load_versions_from_files()
    )
    environment: EnvironmentConfig = field(default_factory=lambda: EnvironmentConfig())
    parameters: ParametersConfig = field(default_factory=lambda: ParametersConfig())

    @staticmethod
    def load_versions_from_files(
        version_configs_dir: str = f"{Path(os.path.dirname(__file__))}/version_configs/quic/",
    ) -> PantherIvyVersion:
        """Load version configurations dynamically from YAML files."""
        logging.debug(f"Loading PantherIvy versions from {version_configs_dir}")
        for version_file in os.listdir(version_configs_dir):
            if version_file.endswith(".yaml"):
                version_path = os.path.join(version_configs_dir, version_file)
                raw_version_config = OmegaConf.load(version_path)
                logging.debug(
                    f"Loaded raw PantherIvy version config: {raw_version_config}"
                )
                version_config = OmegaConf.to_object(
                    OmegaConf.merge(PantherIvyVersion, raw_version_config)
                )
                logging.debug(f"Loaded PantherIvy version {version_config}")
                return version_config
