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
        default_factory=lambda: Parameter(value="1", description="Number of iterations per test")
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
        default_factory=lambda: Parameter(value="DEBUG", description="Log level for Ivy")
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

    def is_test_successful(self, role, test_name: str) -> bool:
        """
        Checks if a test was successful based on the output files.

        Args:
            role: The role (client/server) for which the test was run
            test_name (str): The name of the test to check

        Returns:
            bool: True if the test was successful (PASS found), False otherwise (FAIL found or neither found)
        """
        import logging
        import os
        import glob

        logger = logging.getLogger(__name__)
        logger.info("Checking test success for %s with role %s", test_name, role)

        try:
            # Get the protocol name from the test path
            protocol_dir = os.environ.get("PROTOCOL_TESTED", "apt")
            logger.debug("Protocol directory: %s", protocol_dir)

            # Base path for test outputs - check both with the current directory and absolute path
            base_paths = [
                # Path relative to this file
                os.path.join(os.path.dirname(__file__), "protocol-testing", protocol_dir, "test"),
                # Absolute path in container
                f"/opt/panther_ivy/protocol-testing/{protocol_dir}/test",
                # Path in test environment
                f"/app/panther-ivy/protocol-testing/{protocol_dir}/test",
            ]

            # Extract the base name of the test (without extension)
            test_base_name = test_name
            if test_base_name.endswith(".ivy"):
                test_base_name = test_base_name[:-4]

            logger.debug("Looking for test results for %s", test_base_name)

            for base_path in base_paths:
                if not os.path.exists(base_path):
                    logger.debug("Path does not exist: %s", base_path)
                    continue

                logger.debug("Searching for ivy_stdout.txt files in %s", base_path)

                # Look for ivy_stdout.txt files that might contain the test results
                # The pattern searches recursively for any test output file in the test directory
                search_pattern = os.path.join(base_path, "**", "ivy_stdout.txt")
                output_files = glob.glob(search_pattern, recursive=True)
                logger.debug("Found %s output files", len(output_files))

                if not output_files:
                    continue

                # Sort by modification time (most recent first)
                output_files.sort(key=os.path.getmtime, reverse=True)

                # Try to find a relevant file for this test
                relevant_output_files = []

                for file_path in output_files:
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()
                            # Check if this file contains the test name
                            if test_base_name in content:
                                logger.debug("Found relevant file: %s", file_path)
                                relevant_output_files.append(file_path)
                    except Exception as e:
                        logger.warning("Error reading file %s: %s", file_path, e)

                if relevant_output_files:
                    logger.info("Found %s relevant output files", len(relevant_output_files))

                    # Check the most recent relevant file
                    latest_file = relevant_output_files[0]
                    logger.info("Using most recent file: %s", latest_file)

                    try:
                        with open(latest_file, "r") as file:
                            content = file.read()

                            # Check if PASS or FAIL is at the end of the file
                            if content.strip().endswith("PASS"):
                                logger.info("Test %s PASSED", test_name)
                                return True
                            elif content.strip().endswith("FAIL"):
                                logger.info("Test %s FAILED", test_name)
                                return False
                            else:
                                # If no PASS/FAIL at the end, check if it's in the last few lines
                                lines = content.strip().split("\n")
                                for line in reversed(lines[-10:]):  # Check last 10 lines
                                    if line.strip() == "PASS":
                                        logger.info(
                                            "Test %s PASSED (found in last lines)", test_name
                                        )
                                        return True
                                    elif line.strip() == "FAIL":
                                        logger.info(
                                            "Test %s FAILED (found in last lines)", test_name
                                        )
                                        return False

                                logger.warning("No PASS/FAIL indicator found in %s", latest_file)
                    except Exception as e:
                        logger.error("Error reading test output file: %s", e)

            logger.warning("No suitable output file found for test %s", test_name)
            return False

        except Exception as e:
            logger.error("Error checking test success: %s", e)
            return False

@dataclass
class PantherIvyConfig(ImplementationConfig):
    name: str = "panther_ivy"  # Implementation name
    type: ImplementationType = ImplementationType.TESTERS  # Default type for panther_ivy
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
        version_configs_dir: str = f"{Path(os.path.dirname(__file__))}/version_configs/quic/") -> PantherIvyVersion:
        """Load version configurations dynamically from YAML files."""
        logging.debug("Loading PantherIvy versions from %s", version_configs_dir)
        for version_file in os.listdir(version_configs_dir):
            if version_file.endswith(".yaml"):
                version_path = os.path.join(version_configs_dir, version_file)
                raw_version_config = OmegaConf.load(version_path)
                logging.debug("Loaded raw PantherIvy version config: %s", raw_version_config)
                version_config = OmegaConf.to_object(
                    OmegaConf.merge(PantherIvyVersion, raw_version_config)
                )
                logging.debug("Loaded PantherIvy version %s", version_config)
                return version_config
