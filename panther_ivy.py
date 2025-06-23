"""
PantherIvy service manager - mixin-based architecture implementation.

This implementation uses specialized mixins for better maintainability and follows
PANTHER's standard architecture patterns with proper separation of concerns.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from panther.core.docker_builder.service_manager_docker_mixin import ServiceManagerDockerMixin
from panther.plugins.services.testers.panther_ivy.config_schema import AvailableTests, PantherIvyConfig
from panther.plugins.services.testers.tester_interface import ITesterManager
from panther.config.core.models import ProtocolConfig, ProtocolRole
from panther.plugins.services.testers.tester_service_manager_mixin import TesterServiceManagerMixin
from panther.plugins.core.plugin_decorators import register_plugin
from panther.plugins.services.testers.tester_event_mixin import TesterManagerEventMixin
from panther.plugins.core.structures.plugin_type import PluginType
from panther.plugins.services.testers.panther_ivy.ivy_command_mixin import IvyCommandMixin
from panther.plugins.services.testers.panther_ivy.ivy_analysis_mixin import IvyAnalysisMixin
from panther.plugins.services.testers.panther_ivy.ivy_output_pattern_mixin import IvyOutputPatternMixin
from panther.plugins.services.testers.panther_ivy.ivy_protocol_aware_mixin import IvyProtocolAwareMixin
from panther.config.core.models.service import ServiceConfig

if TYPE_CHECKING:
    from panther.plugins.plugin_manager import PluginManager


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"

@register_plugin(
    plugin_type=PluginType.TESTER,
    name="panther_ivy",
    version="3.1.0",  # Version 3.1 reflects mixin-based refactored architecture
    description="Ivy formal verification tester using mixin-based architecture",
    supported_protocols=["quic"],
    external_dependencies=["z3>=4.8", "python>=3.7"],
    homepage=""
)
class PantherIvyServiceManager(
    IvyCommandMixin,
    IvyAnalysisMixin, 
    IvyOutputPatternMixin,
    IvyProtocolAwareMixin,
    TesterServiceManagerMixin, 
    ServiceManagerDockerMixin, 
    TesterManagerEventMixin,
    ITesterManager,
    ErrorHandlerMixin
):
    """
    Mixin-based PantherIvy service manager with specialized functionality.
    
    This class uses specialized mixins for different concerns:
    - IvyCommandMixin: Command generation and parameter handling
    - IvyAnalysisMixin: Output analysis and pattern matching
    - IvyOutputPatternMixin: Output file organization and collection
    - IvyProtocolAwareMixin: Protocol-specific configuration handling
    """

    def __init__(self, 
                service_config_to_test: ServiceConfig, 
                service_type: Any,
                protocol: ProtocolConfig,
                implementation_name: str,
                event_manager=None,
                global_config=None,
                **kwargs):
        """
        Initialize PantherIvy service manager with mixin-based architecture.
        
        This implementation uses the template method pattern to ensure proper
        initialization sequence and avoid duplicate attribute setting.
        
        Args:
            service_config_to_test: Ivy service configuration
            service_type: Type of service (should be 'TESTERS')
            protocol: Protocol configuration object
            implementation_name: Name of the implementation
            event_manager: Event manager instance (optional)
            global_config: Global configuration dictionary (optional)
        """
        self._original_service_config = service_config_to_test
        # Pre-determine role before any mixin initialization to avoid timing issues
        self._role = self._determine_role_from_config(service_config_to_test, protocol)
        # Initialize parent classes - this will call TesterServiceManagerMixin.__init__
        # which sets up basic attributes but does NOT call standardized_initialization
        # Debug: Check global_config parameter
        print(f"DEBUG [PantherIvyServiceManager]: global_config parameter: {global_config}")
        print(f"DEBUG [PantherIvyServiceManager]: global_config type: {type(global_config)}")
        if global_config and hasattr(global_config, 'docker'):
            print(f"DEBUG [PantherIvyServiceManager]: docker config: {global_config.docker}")
            print(f"DEBUG [PantherIvyServiceManager]: force_build_docker_image: {getattr(global_config.docker, 'force_build_docker_image', 'NOT_FOUND')}")
        
        super().__init__(
            service_config_to_test, service_type, protocol, implementation_name, event_manager,
            global_config=global_config, **kwargs
        )
        # Use the template method for complete initialization
        # This handles all setup including standardized_initialization, role setup,
        # template renderer, and Docker attributes in the correct order
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

        # Initialize Ivy-specific attributes (after role and protocol are properly set)
        self._initialize_ivy_attributes(service_config_to_test, protocol)

        # Override default output patterns with Ivy-specific patterns
        self._output_patterns = self._get_ivy_output_patterns()

        # Set up Ivy-specific Docker volumes
        self._setup_volumes()
        
        self.outputs = {}
        
        # Cache plugin config for easy access
        self._plugin_config = None

        
    def _initialize_ivy_attributes(
                self, service_config_to_test, protocol: ProtocolConfig
            ):
            """
                Initialize Ivy-specific attributes after role and protocol are set.
                
                This method sets up Ivy-specific configuration including test paths,
                protocol model paths, and environment settings.
                
                Args:
                    service_config_to_test: PantherIvy plugin configuration object
                    protocol: Protocol configuration object
                """
            # Set test configuration - use comprehensive multi-level checking
            test_name = ''
            
            # Priority order: test_parameters > plugin_config > implementation > direct attribute
            if hasattr(service_config_to_test, "test_parameters") and service_config_to_test.test_parameters:
                test_name = service_config_to_test.test_parameters.get('test', '')
            elif hasattr(service_config_to_test, "plugin_config") and service_config_to_test.plugin_config:
                # Check plugin_config dict for test - this is where it actually is!
                test_name = service_config_to_test.plugin_config.get('test', '')
            elif hasattr(service_config_to_test, "implementation"):
                # Check if the implementation is a dict with 'test' key
                if isinstance(service_config_to_test.implementation, dict) and "test" in service_config_to_test.implementation:
                    test_name = service_config_to_test.implementation["test"]
                # Check if implementation has test attribute
                elif hasattr(service_config_to_test.implementation, "test"):
                    test_name = service_config_to_test.implementation.test
            elif hasattr(service_config_to_test, "test"):
                # Check if service_config has test attribute directly
                test_name = service_config_to_test.test
            else:
                # Final fallback to direct attribute access
                test_name = getattr(service_config_to_test, 'test', '')
            
            self.test_to_compile = test_name
            self.test_to_compile_path = None
    
            # Initialize available_tests - for now we'll use empty dict since
            # version information is loaded separately in PantherIvyConfig
            self.available_tests = {}
    
            # Set protocol model paths
            self.protocol = protocol
            self._protocol_name_cache = None
    
            self.env_protocol_model_path = self.get_protocol_model_path(
                use_system_models=getattr(service_config_to_test, 'use_system_models', False)
            )
    
            self.protocol_model_path = self.get_local_protocol_model_path(
                use_system_models=getattr(service_config_to_test, 'use_system_models', False)
            )
    
            self.available_tests = AvailableTests.load_tests_from_directory(
                f"{self.protocol_model_path}/{self.role}_tests"
            )
    
            # Get log level from PantherIvyConfig with default fallback
            self.ivy_log_level = getattr(service_config_to_test, 'log_level', 'DEBUG')
    
            # Ensure directories_to_start is empty list
            service_config_to_test.directories_to_start = []
    
            self.final_analysis_res = None
    
            # Fix service_name access - use the correct attribute name from the service manager
            service_name = getattr(self, 'service_name', None) or getattr(service_config_to_test, 'name', 'unknown_service')
            self.logger.info(f"Initialized PantherIvy service manager for {service_name} with role {self.role} and test: {self.test_to_compile}")



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
        if protocol_name is None:
            if isinstance(self.protocol, str):
                protocol_name = self.protocol
            else:
                protocol_name = "unknown"
                self.logger.error("Unexpected protocol type: %s", type(self.protocol).__name__)

        self._protocol_name_cache = protocol_name
        return protocol_name

    def _get_protocol_name_from_service_config(self):
        """Helper method to get protocol name from service config during initialization."""
        if hasattr(self.service_config_to_test, 'protocol') and hasattr(self.service_config_to_test.protocol, 'name'):
            return getattr(self.service_config_to_test.protocol, 'name', 'unknown')
        self.logger.warning("Could not determine protocol name from service config, using 'unknown'")
        return 'unknown'

    def _setup_volumes(self):
        """
        Set up Docker volumes for Ivy service manager.
        
        This method configures Docker volume mappings for Ivy include files
        and protocol model directories to enable proper compilation and execution
        within the Docker container environment.
        """
        ivy_include_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "ivy", "include", "1.7")
        )
        local_protocol_dir = self.protocol_model_path

        volumes = [ 
            f"{ivy_include_dir}:/opt/panther_ivy/ivy/include/1.7",
            f"{local_protocol_dir}:{self.env_protocol_model_path}",
        ]

        if hasattr(self, "volumes"):
            self.volumes.extend(volumes)
        else:
            self.volumes = volumes


    def _load_version_environment_variables(self):
            """
            Load environment variables including Ivy-specific ones.
            Maintains environment-specific path flexibility by preserving variable references.
            """
            # Call parent implementation first to get version-specific env vars
            super()._load_version_environment_variables()
            
            # Import the default environment variables
            from panther.plugins.services.testers.panther_ivy.config_schema import DEFAULT_ENVIRONMENT_VARIABLES
            
            # Get environment variables from service config - start with defaults and merge in config
            ivy_env_vars = DEFAULT_ENVIRONMENT_VARIABLES.copy()
            
            # Merge in any environment variables from service config
            config_env_vars = getattr(self.service_config_to_test, 'environment', {})
            if config_env_vars:
                ivy_env_vars.update(config_env_vars)
                self.logger.debug(f"Merged {len(config_env_vars)} environment variables from service config")
            
            # Set PROTOCOL_MODEL_PATH based on architecture choice
            use_system_models = getattr(self.service_config_to_test, 'use_system_models', False)
            protocol_name = self._get_protocol_name_from_service_config()
            
            if use_system_models:
                # APT architecture: centralized models in apt_protocols/{protocol}
                protocol_model_path = f"$SOURCE_DIR/panther_ivy/protocol-testing/apt/apt_protocols/{protocol_name}"
                use_apt_protocols = "1"  # Enable APT protocols flag
            else:
                # Individual protocol architecture: protocol root directory
                protocol_model_path = f"$SOURCE_DIR/panther_ivy/protocol-testing/{protocol_name}"
                use_apt_protocols = "0"  # Disable APT protocols flag
            
            # Use environment variables from configuration (already a dict)
            # Preserving variable references (e.g., $SOURCE_DIR) for environment-specific resolution
            env_vars_to_add = ivy_env_vars.copy()
            
            # Add architecture-specific variables
            env_vars_to_add.update({
                'PROTOCOL_MODEL_PATH': protocol_model_path,  # Architecture-aware path
                'USE_APT_PROTOCOLS': use_apt_protocols,  # Flag for compile-time path selection
            })
            
            # Adapt environment variable paths based on use_system_models parameter
            # This transforms paths in version configs to match architecture choice
            self.adapt_environment_paths(env_vars_to_add, use_system_models)
            
            # Add each environment variable
            for env_name, env_value in env_vars_to_add.items():
                self.environments[env_name] = env_value
                self.logger.debug(f"Added Ivy environment variable {env_name}={env_value}")
            
            # Log total environment variables loaded
            self.logger.info(f"Loaded {len(self.environments)} environment variables for Ivy service {self.service_name}")

    def _determine_role_from_config(self, service_config_to_test, protocol) -> str:
        """
        Determine the role (client/server) from service configuration early in initialization.
        
        This method is called before parent class initialization to ensure role is
        available for command builder setup.
        
        Args:
            service_config_to_test: Service configuration object
            protocol: Protocol configuration object
            
        Returns:
            str: Role ('client' or 'server')
        """
        # Check protocol role first
        if hasattr(protocol, "role"):
            role_obj = protocol.role
            if hasattr(role_obj, 'name'):
                return role_obj.name
            elif isinstance(role_obj, str):
                return role_obj
        
        # Check service config protocol role
        if hasattr(service_config_to_test, 'protocol') and hasattr(service_config_to_test.protocol, 'role'):
            role_obj = service_config_to_test.protocol.role
            if hasattr(role_obj, 'name'):
                return role_obj.name
            elif isinstance(role_obj, str):
                return role_obj
        
        # Fall back to service name analysis
        service_name = getattr(service_config_to_test, 'name', '') or \
                     getattr(service_config_to_test, 'service_name', '')
        if 'client' in service_name.lower():
            return 'client'
        elif 'server' in service_name.lower():
            return 'server'
        
        # Default fallback
        return 'client'

    def _setup_template_renderer(self, plugin_dir=None, include_protocol_in_template=True):
        """
        Override template renderer setup to prevent MRO conflicts.
        
        This method ensures template renderer is set up correctly in the 
        mixin architecture without duplicate calls.
        """
        # Only call super if we haven't already set up the template renderer
        if not hasattr(self, 'template_renderer') or self.template_renderer is None:
            if hasattr(super(), '_setup_template_renderer'):
                super()._setup_template_renderer(plugin_dir, include_protocol_in_template)
                self.logger.debug("Template renderer set up via mixin chain")
            else:
                self.logger.warning("No template renderer setup method found in mixin chain")
        else:
            self.logger.debug("Template renderer already initialized, skipping duplicate setup")

    def _setup_docker_attributes(self):
        """
        Override Docker attributes setup to prevent MRO conflicts.
        
        This method ensures Docker configuration is set up correctly in the
        mixin architecture without duplicate calls.
        """
        # Only call super if we haven't already set up Docker attributes
        if not hasattr(self, '_docker_setup_completed'):
            if hasattr(super(), '_setup_docker_attributes'):
                super()._setup_docker_attributes()
                self.logger.debug("Docker attributes set up via mixin chain")
            else:
                self.logger.debug("No Docker attributes setup method found in mixin chain")
            
            # Mark Docker setup as completed to prevent duplicate calls
            self._docker_setup_completed = True
        else:
            self.logger.debug("Docker attributes already initialized, skipping duplicate setup")
            
    # def _get_plugin_config(self) -> Optional[PantherIvyConfig]:
    #     """
    #     Get plugin config for ServiceManagerDockerMixin integration.
        
    #     This method provides the plugin configuration needed by the Docker mixin
    #     for container setup and volume mapping.
        
    #     Returns:
    #         PantherIvyConfig: The service configuration object
    #     """
    #     # Cache the plugin config to avoid repeated access
    #     if self._plugin_config is None:
    #         try:
    #             self._plugin_config = self.service_config_to_test.get_plugin_config(PantherIvyConfig)
    #         except Exception as e:
    #             self.logger.debug(f"Could not get plugin config, using defaults: {e}")
    #             # Create default config
    #             self._plugin_config = PantherIvyConfig()
        
    #     self.logger.debug(f"Loaded plugin config: {self._plugin_config}")
        
    #     # Get protocol version for version-specific configuration loading
    #     protocol_version = getattr(self.service_config_to_test.protocol, 'version', None)
    #     protocol_name = self._get_protocol_name()
        
    #     self.logger.info(
    #         f"Loading version config for {self.implementation_name}: "
    #         f"protocol={protocol_name}, version={protocol_version}"
    #     )
        
    #     self._plugin_config.load_versions_from_files(
    #         protocol=protocol_name,  
    #         version=protocol_version,
    #     )
    #     return self._plugin_config      
    
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
            self.logger.error(f"Error preparing PantherIvy service manager: {e}")
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
        """Generate pre-compile commands using mixin integration."""
        try:
            # Use mixin method directly instead of command generator delegation
            commands = self.generate_ivy_pre_compile_commands()
            
            # Add base commands from parent if available
            base_commands = []
            if hasattr(super(), 'generate_pre_compile_commands'):
                base_commands = super().generate_pre_compile_commands()
            
            # Combine base and Ivy-specific commands
            return base_commands + commands
            
        except Exception as e:
            self.logger.error(f"Failed to generate pre-compile commands: {e}")
            return []


    def generate_compile_commands(self):
        """Generate compile commands using mixin integration."""
        try:
            # Get base commands from parent
            base_commands = []
            if hasattr(super(), 'generate_compile_commands'):
                base_commands = super().generate_compile_commands()
            
            # Use mixin method directly
            commands = []
            ivy_commands = self.generate_ivy_compile_commands(commands)
            
            # Combine base and Ivy-specific commands
            return base_commands + ivy_commands
            
        except Exception as e:
            self.logger.error(f"Failed to generate compile commands: {e}")
            return base_commands if 'base_commands' in locals() else []


    def generate_run_command(self):
        """Generate run command with delegated deployment args."""
        # Build command structure
        cmd_args = self.generate_ivy_deployment_commands()
        
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
        """Generate compilation commands using mixin integration."""
        try:
            # Use mixin method directly to get comprehensive compilation commands
            return self._generate_comprehensive_compilation_commands()
            
        except Exception as e:
            self.logger.error(f"Failed to generate compilation commands: {e}")
            return []

    def build_tests(self, test_name=None) -> List[str]:
        """Generate test building commands using mixin integration."""
        try:
            # Use mixin method directly to build test compilation commands
            return self._build_test_compilation_commands()
            
        except Exception as e:
            self.logger.error(f"Failed to build tests: {e}")
            return []


    def generate_deployment_commands(self) -> str:
        """Generate deployment commands using mixin integration."""
        try:
            # Use mixin method directly instead of command generator delegation
            return self.generate_ivy_deployment_commands()
            
        except Exception as e:
            self.logger.error(f"Failed to generate deployment commands: {e}")
            return ""


    def generate_post_run_commands(self):
        """Generate post-run commands using mixin integration."""
        try:
            # Get base commands from parent
            base_commands = []
            if hasattr(super(), 'generate_post_run_commands'):
                base_commands = super().generate_post_run_commands()
            
            # Use mixin method directly
            ivy_commands = self.generate_ivy_post_run_commands()
            
            # Combine base and Ivy-specific commands
            return base_commands + ivy_commands
            
        except Exception as e:
            self.logger.error(f"Failed to generate post-run commands: {e}")
            return base_commands if 'base_commands' in locals() else []


    def _get_build_dir(self) -> str:
            """Helper to get build directory path."""
            return getattr(self.service_config_to_test, 'tests_build_dir', 'build')

    
    def _do_run_tests(self) -> Dict[str, Any]:
        """
        Execute Ivy tests and return results.
        
        Implementation of abstract method from ITesterManager.
        This method handles the actual test execution using Ivy formal verification.
        
        Returns:
            Dict[str, Any]: Test execution results including success status and outputs
        """
        try:
            self.logger.info(f"Running Ivy tests for {self.service_name}")
            
            # Initialize results structure
            results = {
                "success": False,
                "test_name": getattr(self, 'test_to_compile', 'unknown'),
                "role": getattr(self, 'role', 'unknown'),
                "outputs": {},
                "analysis": {},
                "errors": []
            }
            
            # Collect outputs from test execution
            outputs = self.collect_outputs()
            results["outputs"] = outputs
            
            # Analyze the collected outputs
            analysis = self.analyze_outputs()
            results["analysis"] = analysis
            
            # Determine success based on analysis
            if analysis.get("success", False):
                results["success"] = True
                self.logger.info(f"Ivy tests completed successfully for {self.service_name}")
            else:
                results["errors"].append(analysis.get("error", "Test execution failed"))
                self.logger.warning(f"Ivy tests failed for {self.service_name}")
            
            # Store results for later retrieval
            self.final_analysis_res = results
            
            return results
            
        except Exception as e:
            error_msg = f"Error running Ivy tests: {e}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "test_name": getattr(self, 'test_to_compile', 'unknown'),
                "role": getattr(self, 'role', 'unknown'),
                "outputs": {},
                "analysis": {},
                "errors": [error_msg]
            }

    def get_test_results(self) -> Dict[str, Any]:
        """
        Get the results of the last test execution.
        
        Implementation of abstract method from ITesterManager.
        
        Returns:
            Dict[str, Any]: Test results or empty dict if no tests have been run
        """
        if hasattr(self, 'final_analysis_res') and self.final_analysis_res:
            return self.final_analysis_res
        else:
            self.logger.warning("No test results available - tests may not have been run yet")
            return {
                "success": False,
                "test_name": getattr(self, 'test_to_compile', 'unknown'),
                "role": getattr(self, 'role', 'unknown'),
                "outputs": {},
                "analysis": {},
                "errors": ["No test results available"]
            }

    def set_collected_outputs(self, outputs: Dict[str, Any]) -> None:
        """
        Set collected outputs for external processing.
        
        Implementation of abstract method from ITesterManager.
        This method allows external components to provide collected outputs.
        
        Args:
            outputs: Dictionary of collected outputs to store
        """
        try:
            if not isinstance(outputs, dict):
                raise ValueError(f"Outputs must be a dictionary, got {type(outputs)}")
            
            self.logger.debug(f"Setting collected outputs for {self.service_name}: {len(outputs)} items")
            
            # Store outputs in instance variable for later processing
            self._collected_outputs = outputs
            
            # If we have outputs, try to analyze them
            if outputs:
                self.outputs = outputs
                analysis = self.analyze_outputs()
                
                # Update final analysis results
                self.final_analysis_res = {
                    "success": analysis.get("success", False),
                    "test_name": getattr(self, 'test_to_compile', 'unknown'),
                    "role": getattr(self, 'role', 'unknown'),
                    "outputs": outputs,
                    "analysis": analysis,
                    "errors": analysis.get("errors", [])
                }
                
                self.logger.info(f"Processed collected outputs for {self.service_name}")
            
        except Exception as e:
            error_msg = f"Error setting collected outputs: {e}"
            self.logger.error(error_msg)
            self._collected_outputs = {}
    
    def collect_outputs(self) -> Dict[str, Any]:
        """
        Collect service outputs using output pattern mixin.
        
        Returns:
            Dict[str, Any]: Collected outputs
        """
        try:
            # Use the output patterns from the mixin
            patterns = self.get_output_patterns()
            collected = {}
            
            for pattern_name, pattern_path in patterns:
                file_path = Path("/app/logs") / pattern_path
                if file_path.exists():
                    try:
                        with open(file_path, 'r') as f:
                            collected[pattern_name] = f.read()
                    except Exception as e:
                        self.logger.warning(f"Could not read {file_path}: {e}")
                        collected[pattern_name] = ""
                else:
                    collected[pattern_name] = ""
            
            return collected
            
        except Exception as e:
            self.logger.error(f"Error collecting outputs: {e}")
            return {}

    def analyze_outputs(self) -> Dict[str, Any]:
        """
        Analyze outputs using analysis mixin.
        
        Args:
            collected_outputs: Dictionary of collected outputs
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        try:
            # Use the analysis mixin method
            return self.analyze_outputs_with_data(self.outputs)
        except Exception as e:
            self.logger.error(f"Error analyzing outputs: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": "Analysis failed due to error"
            }

    def __str__(self) -> str:
        """String representation of the service manager."""
        return f"PantherIvyServiceManager(name={self.service_name}, role={self.role})"

    def __repr__(self) -> str:
        """Detailed representation of the service manager."""
        return (f"PantherIvyServiceManager(service_name='{self.service_name}', "
                f"role='{self.role}', protocol='{self.get_protocol_name()}')")

        