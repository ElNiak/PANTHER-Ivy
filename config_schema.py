from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from omegaconf import OmegaConf

from panther.plugins.services.iut.config_schema import ImplementationConfig, Parameter, VersionBase
from panther.plugins.services.iut.config_schema import ImplementationType


@dataclass
class EnvironmentConfig:
    PROTOCOL_TESTED: str = ""
    RUST_LOG: str = "debug"
    RUST_BACKTRACE: str = "1"
    SOURCE_DIR: str = "/opt/"
    IVY_DIR: str = "$SOURCE_DIR/panther_ivy"
    PYTHON_IVY_DIR: str = "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/"
    IVY_INCLUDE_PATH: str = "$IVY_INCLUDE_PATH:/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7"
    Z3_LIBRARY_DIRS: str = "$IVY_DIR/submodules/z3/build"
    Z3_LIBRARY_PATH: str = "$IVY_DIR/submodules/z3/build"
    LD_LIBRARY_PATH: str = "$LD_LIBRARY_PATH:$IVY_DIR/submodules/z3/build"
    PROOTPATH: str = "$SOURCE_DIR"
    ADDITIONAL_PYTHONPATH: str = "/app/implementations/quic-implementations/aioquic/src/:$IVY_DIR/submodules/z3/build/python:$PYTHON_IVY_DIR"
    ADDITIONAL_PATH: str = "/go/bin:$IVY_DIR/submodules/z3/build"


@dataclass
class ParametersConfig:
    tests_output_dir: Parameter = Parameter(value="temp/",
                                            description="Directory where the tests output will be stored")
    tests_build_dir: Parameter = Parameter(value="build/", description="Directory where the tests will be built")
    iterations_per_test: Parameter = Parameter(value="1", description="Number of iterations per test")
    internal_iterations_per_test: Parameter = Parameter(value="100",
                                                        description="Number of internal iterations per test")
    timeout: Parameter = Parameter(value="120", description="Timeout for each test (in seconds)")
    keep_alive: Parameter = Parameter(value="False", description="Keep the Ivy process alive after the tests")
    run_in_docker: Parameter = Parameter(value="True", description="Run the tests in a Docker container")
    get_tests_stats: Parameter = Parameter(value="True", description="Get the statistics of the tests")
    log_level: Parameter = Parameter(value="DEBUG", description="Log level for Ivy")


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
    type: ImplementationType = ImplementationType.testers  # Default type for panther_ivy
    test: str = field(default="")  # Test name for testers
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
            version_configs_dir: str = f"{Path(os.path.dirname(__file__))}/version_configs/quic/"
    ) -> PantherIvyVersion:
        """Load version configurations dynamically from YAML files."""
        logging.debug(f"Loading PantherIvy versions from {version_configs_dir}")
        for version_file in os.listdir(version_configs_dir):
            if version_file.endswith(".yaml"):
                version_path = os.path.join(version_configs_dir, version_file)
                raw_version_config = OmegaConf.load(version_path)
                logging.debug(f"Loaded raw PantherIvy version config: {raw_version_config}")
                version_config = OmegaConf.to_object(OmegaConf.merge(PantherIvyVersion, raw_version_config))
                logging.debug(f"Loaded PantherIvy version {version_config}")
                return version_config
