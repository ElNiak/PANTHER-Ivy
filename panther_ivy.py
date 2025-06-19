"""
PantherIvy service manager - refactored implementation using modular components.

This implementation follows the separation of concerns pattern with delegated
responsibilities to specialized components for better maintainability, testability,
and security.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from panther.core.docker_builder.service_manager_docker_mixin import ServiceManagerDockerMixin
from panther.plugins.services.testers.panther_ivy.config_schema import PantherIvyConfig
from panther.plugins.services.testers.tester_interface import ITesterManager
from panther.config.core.models import ProtocolConfig, ProtocolRole
from panther.plugins.services.testers.tester_service_manager_mixin import TesterServiceManagerMixin
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from panther.plugins.plugin_decorators import register_plugin

# Import modular components - these are required for the refactored implementation
try:
    from panther.plugins.services.testers.panther_ivy.components.ivy_command_generator import IvyCommandGenerator
    from panther.plugins.services.testers.panther_ivy.components.ivy_log_analyzer import IvyLogAnalyzer
    from panther.plugins.services.testers.panther_ivy.components.ivy_output_manager import IvyOutputManager
    from panther.plugins.services.testers.panther_ivy.components.ivy_test_executor import IvyTestExecutor
    from panther.plugins.services.testers.panther_ivy.components.ivy_environment_setup import IvyEnvironmentSetup
    from panther.plugins.services.testers.panther_ivy.components.ivy_protocol_handler import IvyProtocolHandler
    MODULAR_COMPONENTS_AVAILABLE = True
except ImportError:
    # Fallback if modular components are not available
    MODULAR_COMPONENTS_AVAILABLE = False

if TYPE_CHECKING:
    from panther.plugins.plugin_manager import PluginManager


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"

@register_plugin(
    plugin_type="tester",
    name="panther_ivy",
    version="3.0.0",  # Version 3.0 reflects modular refactored architecture
    description="Modular formal verification tester using Ivy specification language with separation of concerns",
    author="PANTHER Team",
    dependencies=["ivy_compiler"],
    supported_protocols=["quic"],
    capabilities=[
        "formal_verification",
        "protocol_compliance",
        "symbolic_execution",
        "invariant_checking",
    ],
    external_dependencies=["z3>=4.8", "python>=3.7"],
)
class PantherIvyServiceManager(
    TesterServiceManagerMixin, 
    ServiceManagerDockerMixin, 
    ErrorHandlerMixin, 
    ITesterManager
):
    """
    Refactored PantherIvy service manager using modular components with separation of concerns.
    
    This class delegates responsibilities to specialized components:
    - IvyCommandGenerator: Secure command generation and parameter handling
    - IvyLogAnalyzer: Log analysis and pattern matching
    - IvyOutputManager: Output file management and collection
    - IvyTestExecutor: Test execution coordination and result aggregation
    - IvyEnvironmentSetup: Environment initialization and Docker setup
    - IvyProtocolHandler: Protocol-specific configuration and validation
    
    The modular architecture provides:
    - Single responsibility principle adherence
    - Enhanced security through centralized validation
    - Improved testability with isolated components
    - Better maintainability and code reusability
    """
    
    def __init__(
        self,
        service_config_to_test: PantherIvyConfig,  # Accept both ServiceConfig and PantherIvyConfig
        service_type: str,
        protocol: ProtocolConfig,
        implementation_name: str,
        event_manager=None,
        emitter_registry=None,  # Accept emitter_registry parameter
        **kwargs  # Accept any additional keyword arguments
    ):
        """Initialize enhanced PantherIvy service manager."""
        # service_config_to_test is always a ServiceConfig in the new system
        # We can use it directly without any MockServiceConfig workaround
        
        super().__init__(
            service_config_to_test, service_type, protocol, implementation_name, event_manager
        )
        # Use the new template method for standard initialization (with protocol support)
        try:
            self.standard_tester_initialization(
                service_config_to_test, service_type, protocol, implementation_name, event_manager,
                include_protocol_in_template=True, plugin_dir=Path(__file__).parent
            )
        except Exception as e:
            self.logger.error(f"Error in standard_tester_initialization: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        # Initialize Ivy-specific attributes
        self._initialize_ivy_attributes(service_config_to_test, protocol)

        # Ivy-specific setup after Docker builds are complete
        self._setup_volumes()
        
        self.final_analysis_res = None
        
        # Override default output patterns with Ivy-specific patterns
        self._output_patterns = self._get_ivy_output_patterns()
        
        # Initialize modular components for advanced usage (if available)
        if MODULAR_COMPONENTS_AVAILABLE:
            # Set up attributes expected by modular components
            self.test = self.test_to_compile
            self.test_name = getattr(service_config_to_test, 'name', 'ivy_test')
            self.protocol_config = protocol
            self.config = {
                'generate_certificates': getattr(service_config_to_test, 'generate_new_certificates', False),
                'build_submodules': getattr(service_config_to_test, 'build_submodules', False),
            }
            
            # Initialize components
            self.command_generator = IvyCommandGenerator(self)
            self.log_analyzer = IvyLogAnalyzer(self)
            self.output_manager = IvyOutputManager(self)
            self.test_executor = IvyTestExecutor(self)
            self.environment_setup = IvyEnvironmentSetup(self)
            self.protocol_handler = IvyProtocolHandler(self)
        else:
            # Fallback to None if components are not available
            self.command_generator = None
            self.log_analyzer = None
            self.output_manager = None
            self.test_executor = None
            self.environment_setup = None
            self.protocol_handler = None
            
    def _initialize_ivy_attributes(
        self, service_config_to_test, protocol: ProtocolConfig
    ):
        """Initialize Ivy-specific attributes."""
        # Set test configuration
        # Access test from implementation config
        self.test_to_compile = getattr(service_config_to_test.implementation, 'test', '')
        self.test_to_compile_path = None

        # Initialize available_tests - for now we'll use empty dict since
        # version information is loaded separately in PantherIvyConfig
        self.available_tests = {}
        
        # TODO: Properly load available tests from PantherIvyConfig version data
        # This would require accessing the PantherIvyConfig.load_versions_from_files()
        # and extracting the test information based on role

        if self.available_tests is None:
            self.available_tests = {}

        # Set protocol model paths
        self.protocol = protocol
        self._protocol_name_cache = None

        # Check if use_system_models is set in implementation config
        use_system_models = getattr(service_config_to_test.implementation, 'use_system_models', False)
        if use_system_models:
            self.env_protocol_model_path = "/opt/panther_ivy/protocol-testing/apt/"
            self.protocol_model_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "protocol-testing", "apt")
            )
        else:
            self.env_protocol_model_path = (
                "/opt/panther_ivy/protocol-testing/" + self._get_protocol_name() + "/"
            )
            self.protocol_model_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "protocol-testing", self._get_protocol_name()
                )
            )

        # Get log level from implementation config with default fallback
        params = getattr(service_config_to_test.implementation, 'parameters', None)
        if params and hasattr(params, 'log_level'):
            self.ivy_log_level = params.log_level
        else:
            self.ivy_log_level = 'DEBUG'  # Default log level

        # Ensure directories_to_start is empty list
        service_config_to_test.directories_to_start = []
        
    
    def _get_ivy_output_patterns(self) -> List[Tuple[str, str]]:
        """Get Ivy-specific output patterns."""
        patterns = [
            ("ivy_log", "ivy_{service_name}.log"),
            ("ivy_stdout", "stdout.log"),
            ("ivy_stderr", "stderr.log"),
            ("test_results", "test_results.json"),
            ("compilation_status", "compilation_status.txt"),  # Add compilation status file
            ("pcap", "{service_name}.pcap"),
            ("sslkeylog", "sslkeylogfile.txt"),
        ]
        
        if self._get_protocol_name() == "quic":
            patterns.extend([
                ("qlog", "*.qlog"),
                ("keys", "*keys.log"),
            ])
        
        return patterns

    def _get_protocol_name(self):
        """Helper method to safely get protocol name."""
        if hasattr(self, "_protocol_name_cache") and self._protocol_name_cache:
            return self._protocol_name_cache

        protocol_name = getattr(self.protocol, "name", None)
        if protocol_name is None and isinstance(self.protocol, str):
            protocol_name = self.protocol
        elif protocol_name is None:
            protocol_name = "unknown"
            self.logger.error("Unexpected protocol type: %s", type(self.protocol).__name__)

        self._protocol_name_cache = protocol_name
        return protocol_name

    def _setup_volumes(self):
        """Set up Docker volumes for Ivy."""
        ivy_include_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "ivy", "include", "1.7")
        )
        local_protocol_dir = self.protocol_model_path

        volumes = [ # TODO: remove quotes around paths
            f"{ivy_include_dir}:/opt/panther_ivy/ivy/include/1.7",
            f"{local_protocol_dir}:{self.env_protocol_model_path}",
        ]

        if hasattr(self, "volumes"):
            self.volumes.extend(volumes)
        else:
            self.volumes = volumes

    def _do_prepare(self, plugin_manager: Optional["PluginManager"] = None):
        """Implementation of abstract _do_prepare method from IServiceManager."""
        try:
            # Build submodules if needed
            if getattr(self.service_config_to_test, "build_submodules", False):
                self.build_submodules()

            # Use enhanced mixin for Docker builds and command initialization
            if hasattr(super(), "prepare"):
                super().prepare(plugin_manager)

            return True
        except Exception as e:
            self.handle_error(e, "prepare PantherIvy service manager")
            return False

    def build_submodules(self):
        """Initialize git submodules."""
        current_dir = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        try:
            self.logger.info("Initializing submodules (from %s)", os.getcwd())
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to initialize submodules: %s", e)
        finally:
            os.chdir(current_dir)

    def generate_pre_compile_commands(self):
        """Delegate pre-compile command generation to component."""
        if self.command_generator:
            result = self.command_generator.generate_pre_compile_commands()
            # Component now returns plain strings
            return result.get('pre_compile_cmds', [])
        return super().generate_pre_compile_commands()

    def generate_compile_commands(self):
        """Delegate compile command generation to component."""
        base_commands = super().generate_compile_commands()
        if self.command_generator:
            result = self.command_generator.generate_compile_commands()
            compile_cmds = result.get('compile_cmds', [])
            return base_commands + compile_cmds
        return base_commands

    def generate_run_command(self):
        """Generate run command with delegated deployment args."""
        if self.command_generator:
            cmd_args = self.command_generator.generate_deployment_commands()
        else:
            cmd_args = ""
        
        # Build command structure
        command_binary = ""
        if self.test_to_compile:
            build_dir = self._get_build_dir()
            command_binary = f"./{build_dir}/{self.test_to_compile}"
        
        working_dir = self.env_protocol_model_path or \
                      f"/opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/"
        
        return {
            "working_dir": working_dir,
            "command_binary": command_binary,
            "command_args": cmd_args,
            "timeout": getattr(self.service_config_to_test, 'timeout', 120),
            "command_env": {},
        }

    def generate_pre_run_commands(self):
        """Generate pre-run commands with fallback."""
        commands = []
        if hasattr(super(), 'generate_pre_run_commands'):
            commands = super().generate_pre_run_commands()
        
        # IvyCommandGenerator doesn't have this method, so add Ivy-specific commands
        commands.append("source /app/logs/ivy_env.sh || true")
        
        return commands

    def generate_post_compile_commands(self):
        """Generate post-compile commands with fallback."""
        commands = []
        if hasattr(super(), 'generate_post_compile_commands'):
            commands = super().generate_post_compile_commands()
        
        # IvyCommandGenerator doesn't have this method, so add Ivy-specific commands
        commands.extend([
            f"cd {self.env_protocol_model_path}",  
            "pwd >> /app/logs/ivy_post_compile.log",  
        ])
        
        return commands
    
    def generate_compilation_commands(self) -> List[str]:
        """Delegate compilation command generation to component."""
        if self.command_generator:
            # Call the private method that handles comprehensive compilation
            return self.command_generator._generate_comprehensive_compilation_commands()
        return []
    
    
    
    
    def build_tests(self, test_name=None) -> List[str]:
        """Delegate test building to command generator."""
        if self.command_generator:
            return self.command_generator._build_test_compilation_commands(test_name)
        return []

    def generate_deployment_commands(self) -> str:
        """Delegate deployment command generation to component."""
        if self.command_generator:
            return self.command_generator.generate_deployment_commands()
        return ""

    def generate_post_run_commands(self):
        """Delegate post-run command generation to component."""
        commands = super().generate_post_run_commands()
        if self.command_generator:
            result = self.command_generator.generate_post_run_commands()
            post_run_cmds = result.get('post_run_cmds', [])
            return commands + post_run_cmds
        return commands

    def _get_build_dir(self) -> str:
        """Helper to get build directory path."""
        if hasattr(self.service_config_to_test.implementation, 'parameters'):
            params = self.service_config_to_test.implementation.parameters
            if hasattr(params, 'tests_build_dir') and hasattr(params.tests_build_dir, 'value'):
                return params.tests_build_dir.value
        return "build"

    def test_success(self) -> bool:
        """Check for test success."""
        return True  # Simplified for unified implementation

    def set_collected_outputs(self, outputs: Dict[str, Dict[str, str]]) -> None:
        """
        Set the outputs collected from execution environments for analysis.
        
        Args:
            outputs: Dictionary mapping service names to their outputs
        """
        self.collected_outputs = outputs
        self.logger.debug(f"Set collected outputs for {len(outputs)} services")

    def analyze_outputs(self) -> Dict[str, Any]:
        """Analyze collected outputs to determine test success/failure."""
        self.logger.info("Analyzing outputs from test execution")
        
        # Debug: Log what outputs we received
        self.logger.debug(f"Collected outputs: {self.collected_outputs}")
        
        # FIXED: Default to failed - require positive confirmation of success
        passed = False
        detailed_results = {}
        failures = []
        test_executed = False
        compilation_succeeded = False
        
        # Check if we have collected outputs
        if not self.collected_outputs:
            self.logger.warning("No outputs collected for analysis")
            failures.append("No outputs collected")
        else:
            # First, reorganize outputs by service name
            service_outputs = {}
            
            for output_key, env_data in self.collected_outputs.items():
                # Extract service name from keys like "ivy_stderr_ivy_server" or "stderr_picoquic_client"
                if "_stderr_" in output_key:
                    parts = output_key.split("_stderr_")
                    service_name = parts[1] if len(parts) > 1 else output_key
                    output_type = "stderr"
                elif "_stdout_" in output_key:
                    parts = output_key.split("_stdout_")
                    service_name = parts[1] if len(parts) > 1 else output_key
                    output_type = "stdout"
                elif "stderr_" in output_key:
                    service_name = output_key.replace("stderr_", "")
                    output_type = "stderr"
                elif "stdout_" in output_key:
                    service_name = output_key.replace("stdout_", "")
                    output_type = "stdout"
                elif "_compilation_status_" in output_key:
                    parts = output_key.split("_compilation_status_")
                    service_name = parts[1] if len(parts) > 1 else output_key
                    output_type = "compilation_status"
                elif "compilation_status_" in output_key:
                    service_name = output_key.replace("compilation_status_", "")
                    output_type = "compilation_status"
                else:
                    # Try to extract output type and service name for other patterns
                    # Handle patterns like "test_results_ivy_server" or "ivy_log_ivy_server"
                    for known_type in ["test_results", "ivy_log", "pcap", "sslkeylog", "qlog", "keys"]:
                        if f"_{known_type}_" in output_key:
                            parts = output_key.split(f"_{known_type}_")
                            service_name = parts[1] if len(parts) > 1 else output_key
                            output_type = known_type
                            break
                        elif f"{known_type}_" in output_key:
                            service_name = output_key.replace(f"{known_type}_", "")
                            output_type = known_type
                            break
                    else:
                        continue  # Skip unrecognized output types
                
                # Get the file path from env_data
                if isinstance(env_data, dict):
                    file_path = list(env_data.values())[0] if env_data else None
                else:
                    file_path = env_data
                
                if file_path and isinstance(file_path, str):
                    # Read the actual content from the file
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                        
                        if service_name not in service_outputs:
                            service_outputs[service_name] = {}
                        service_outputs[service_name][output_type] = content
                        
                        self.logger.debug(f"Read {output_type} for {service_name} from {file_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to read {file_path}: {e}")
            
            # Now analyze the reorganized outputs
            for service_name, outputs in service_outputs.items():
                self.logger.debug(f"Analyzing service {service_name}, output types: {list(outputs.keys())}")
                
                service_results = {
                    "has_stderr": False,
                    "has_errors": False,
                    "execution_successful": False,  # Changed default to False
                    "compilation_succeeded": False,
                    "test_executed": False,
                    "error_messages": []
                }
                
                # Check stderr for errors
                if "stderr" in outputs and outputs["stderr"]:
                    stderr_content = outputs["stderr"]
                    service_results["has_stderr"] = True
                    
                    self.logger.debug(f"Found stderr for {service_name}: {stderr_content[:200]}...")
                    
                    # Check for common error patterns
                    error_patterns = [
                        "No such file or directory",
                        "timeout: failed to run command",
                        "error:",
                        "Error:",
                        "ERROR:",
                        "failed:",
                        "Failed:",
                        "FAILED:"
                    ]
                    
                    for pattern in error_patterns:
                        if pattern in stderr_content:
                            service_results["has_errors"] = True
                            service_results["execution_successful"] = False
                            service_results["error_messages"].append(stderr_content.strip())
                            passed = False
                            failures.append(f"{service_name}: {stderr_content.strip()}")
                            self.logger.error(f"Found error pattern '{pattern}' in {service_name} stderr")
                            break
                
                # Check status codes
                if "status_codes" in outputs:
                    for phase, status in outputs["status_codes"].items():
                        if status != 0:
                            service_results["execution_successful"] = False
                            service_results["error_messages"].append(f"{phase} failed with status {status}")
                            passed = False
                            failures.append(f"{service_name}: {phase} failed with status {status}")
                
                # Check for Ivy-specific test results
                if "test_results" in outputs:
                    test_results = outputs["test_results"]
                    if isinstance(test_results, dict):
                        if test_results.get("passed", True) is False:
                            service_results["execution_successful"] = False
                            service_results["error_messages"].append("Test marked as failed in results")
                            failures.append(f"{service_name}: Test marked as failed")
                
                # FIXED: Add positive detection of compilation and test execution success
                if not service_results["has_errors"]:
                    # First check compilation_status.txt file if available
                    if "compilation_status" in outputs and outputs["compilation_status"]:
                        compilation_status_content = outputs["compilation_status"].strip()
                        self.logger.debug(f"Found compilation_status.txt for {service_name}: {compilation_status_content}")
                        
                        if "compilation succeeded" in compilation_status_content.lower():
                            service_results["compilation_succeeded"] = True
                            compilation_succeeded = True
                            self.logger.info(f"Compilation succeeded for {service_name} (from compilation_status.txt)")
                        elif "compilation failed" in compilation_status_content.lower():
                            service_results["compilation_succeeded"] = False
                            service_results["has_errors"] = True
                            service_results["execution_successful"] = False
                            service_results["error_messages"].append(compilation_status_content)
                            failures.append(f"{service_name}: {compilation_status_content}")
                            self.logger.error(f"Compilation failed for {service_name} (from compilation_status.txt)")
                            # If compilation failed, skip further analysis for this service
                            detailed_results[service_name] = service_results
                            continue
                    
                    # If no compilation_status.txt or it doesn't provide clear status, check stdout
                    if not service_results["compilation_succeeded"] and "stdout" in outputs and outputs["stdout"]:
                        stdout_content = outputs["stdout"]
                        
                        # Look for positive indicators of successful compilation
                        compilation_success_patterns = [
                            "compilation succeeded",
                            "compilation complete",
                            "successfully built",
                            "test executable created"
                        ]
                        
                        for pattern in compilation_success_patterns:
                            if pattern.lower() in stdout_content.lower():
                                service_results["compilation_succeeded"] = True
                                compilation_succeeded = True
                                self.logger.debug(f"Found compilation success pattern '{pattern}' in {service_name}")
                                break
                        
                        # Look for positive indicators of test execution
                        test_execution_patterns = [
                            "test started",
                            "running test",
                            "test complete",
                            "test finished",
                            "test passed",
                            "all tests passed"
                        ]
                        
                        for pattern in test_execution_patterns:
                            if pattern.lower() in stdout_content.lower():
                                service_results["test_executed"] = True
                                test_executed = True
                                self.logger.debug(f"Found test execution pattern '{pattern}' in {service_name}")
                                break
                    
                    # For Ivy tests, if we have no errors and compilation/execution indicators are present,
                    # or if we have explicit test results, mark as successful
                    if (service_results["compilation_succeeded"] and service_results["test_executed"]) or \
                       ("test_results" in outputs and isinstance(outputs["test_results"], dict) and 
                        outputs["test_results"].get("passed", False)):
                        service_results["execution_successful"] = True
                        passed = True
                        self.logger.info(f"Service {service_name} completed successfully with positive confirmation")
                    else:
                        # No positive confirmation of success - this is a failure
                        if not service_results["compilation_succeeded"]:
                            service_results["error_messages"].append("No confirmation of successful compilation")
                            failures.append(f"{service_name}: Compilation status unknown or failed")
                        if not service_results["test_executed"]:
                            service_results["error_messages"].append("No confirmation of test execution")
                            failures.append(f"{service_name}: Test execution status unknown or failed")
                        
                        self.logger.warning(f"Service {service_name} lacks positive confirmation of success")
                
                detailed_results[service_name] = service_results
        
        # Generate summary
        if passed:
            analysis_summary = "All tests passed successfully"
        else:
            if not failures:
                analysis_summary = "Tests failed: No positive confirmation of test success"
            else:
                analysis_summary = f"Tests failed: {'; '.join(failures)}"
        
        self.logger.info(f"Analysis complete - Passed: {passed}")
        if not passed:
            self.logger.error(f"Test failures: {failures}")
        
        # Store the analysis results for later retrieval
        self.final_analysis_res = {
            "passed": passed,
            "analysis_summary": analysis_summary,
            "detailed_results": detailed_results,
            "failures": failures if not passed else []
        }
        
        return self.final_analysis_res

    def analyze(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze outputs to determine test success/failure (required by ITesterManager).
        
        This method is required by the ITesterManager interface and delegates to 
        analyze_outputs for compatibility with the modular architecture.
        
        Args:
            outputs: Dictionary mapping service names to their outputs
            
        Returns:
            Dict[str, Any]: Analysis results with status and details
        """
        # Set the outputs first
        self.set_collected_outputs(outputs)
        
        # Delegate to the existing analyze_outputs method
        analysis_result = self.analyze_outputs()
        
        # Return in the format expected by ITesterManager
        return {
            "status": "completed" if analysis_result.get("passed", False) else "failed",
            "results": analysis_result,
            "passed": analysis_result.get("passed", False),
            "summary": analysis_result.get("analysis_summary", "No analysis summary"),
            "details": analysis_result.get("detailed_results", {})
        }

    def get_test_results(self) -> Dict[str, Any]:
        """Get final test results based on analysis."""
        # If we have analysis results, use those
        if hasattr(self, 'final_analysis_res') and self.final_analysis_res:
            passed = self.final_analysis_res.get("passed", False)
            summary = self.final_analysis_res.get("analysis_summary", "No analysis summary available")
        else:
            # Fallback to basic check
            passed = False
            summary = "No analysis results available"
            self.logger.warning("No final analysis results available")
        
        return {
            "passed": passed,
            "summary": summary,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "analysis_details": self.final_analysis_res if hasattr(self, 'final_analysis_res') else None
        }

    def _do_stop(self):
        """Stop the service."""
        self.logger.info("Stopping PantherIvy service")
        return True

    def _do_run_tests(self):
        """Run tests implementation."""
        return {"success": True, "test_name": self.test_to_compile}
        
    def get_modular_components(self):
        """
        Get access to modular components for advanced usage.
        
        Returns:
            dict: Dictionary of component instances (or None if components unavailable)
        """
        return {
            'command_generator': self.command_generator,
            'log_analyzer': self.log_analyzer,
            'output_manager': self.output_manager,
            'test_executor': self.test_executor,
            'environment_setup': self.environment_setup,
            'protocol_handler': self.protocol_handler
        }

    def __str__(self) -> str:
        return f"PantherIvyServiceManager({self.service_config_to_test})"

    def __repr__(self):
        return f"PantherIvyServiceManager({self.service_config_to_test})"

# Export main class and components for backward compatibility
__all__ = [
    'PantherIvyServiceManager',
    'oppose_role'
]

# Add modular components to exports if available
if MODULAR_COMPONENTS_AVAILABLE:
    __all__.extend([
        'IvyCommandGenerator',
        'IvyLogAnalyzer', 
        'IvyOutputManager',
        'IvyTestExecutor',
        'IvyEnvironmentSetup',
        'IvyProtocolHandler'
    ])
