"""
PantherIvy service manager -> mixin-based architecture implementation.

This implementation uses specialized mixins for better maintainability and follows
PANTHER's standard architecture patterns with proper separation of concerns.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING, Union
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from panther.core.docker_builder.plugin_mixin.service_manager_docker_mixin import ServiceManagerDockerMixin
from panther.plugins.services.testers.panther_ivy.config_schema import AvailableTests
from panther.config.core.models import ProtocolConfig
from panther.plugins.services.testers.tester_service_manager_mixin import TesterServiceManagerMixin
from panther.plugins.core.plugin_decorators import register_plugin
from panther.plugins.services.testers.tester_event_mixin import TesterManagerEventMixin
from panther.plugins.core.structures.plugin_type import PluginType
from panther.plugins.services.testers.panther_ivy.ivy_command_mixin import IvyCommandMixin
from panther.plugins.services.testers.panther_ivy.ivy_analysis_mixin import IvyAnalysisMixin
from panther.plugins.services.testers.panther_ivy.ivy_output_pattern_mixin import IvyOutputPatternMixin
from panther.plugins.services.testers.panther_ivy.ivy_protocol_aware_mixin import IvyProtocolAwareMixin
from panther.plugins.services.testers.panther_ivy.ivy_network_resolution_mixin import IvyNetworkResolutionMixin
from panther.plugins.services.testers.panther_ivy.ivy_build_mode_mixin import IvyBuildModeMixin
from panther.plugins.services.testers.panther_ivy.ivy_path_template_resolver import get_global_resolver
from panther.config.core.models.service import ServiceConfig
from panther.core.command_processor.models.shell_command import ShellCommand
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
    external_dependencies=["z3=4.8", "python=3.7"],
    homepage=""
)
class PantherIvyServiceManager(
    TesterServiceManagerMixin, 
    ServiceManagerDockerMixin, 
    TesterManagerEventMixin,
    IvyCommandMixin,
    IvyAnalysisMixin, 
    IvyOutputPatternMixin,
    IvyProtocolAwareMixin,
    IvyNetworkResolutionMixin,
    IvyBuildModeMixin,  # Add build mode management
    ErrorHandlerMixin
):
    """
    Mixin-based PantherIvy service manager with specialized functionality.
    
    This class uses specialized mixins for different concerns:
    -> IvyCommandMixin: Command generation and parameter handling
    -> IvyAnalysisMixin: Output analysis and pattern matching
    -> IvyOutputPatternMixin: Output file organization and collection
    -> IvyProtocolAwareMixin: Protocol-specific configuration handling
    """

    def __init__(self, 
                service_config_to_test: ServiceConfig, 
                service_type: Any,
                protocol: ProtocolConfig,
                implementation_name: str,
                event_manager=None,
                global_config=None,
                test_case=None,  # Reference to parent test case for execution environment access
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
            test_case: Reference to parent test case for execution environment access
        """
        self._original_service_config = service_config_to_test
        # Pre-determine role before any mixin initialization to avoid timing issues
        self._role = self._determine_role_from_config(service_config_to_test, protocol)
        super().__init__(
            service_config_to_test, service_type, protocol, implementation_name, event_manager,
            global_config=global_config, test_case=test_case, **kwargs
        )
        self.standard_tester_initialization(
            service_config_to_test, service_type, protocol, implementation_name, event_manager,
            include_protocol_in_template=True, plugin_dir=Path(__file__).parent
        )
        
        self.protocol = protocol
        
        
        self.targets_implementaions = []
        for targets in getattr(service_config_to_test, 'targets', []):
            pass

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
            # Set test configuration -> use comprehensive multi-level checking
            test_name = ''
            
            # Priority order: test_parameters  plugin_config  implementation  direct attribute
            if hasattr(service_config_to_test, "test_parameters") and service_config_to_test.test_parameters:
                test_name = service_config_to_test.test_parameters.get('test', '')
            elif hasattr(service_config_to_test, "plugin_config") and service_config_to_test.plugin_config:
                # Check plugin_config dict for test -> this is where it actually is!
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
    
            # Initialize available_tests -> for now we'll use empty dict since
            # version information is loaded separately in PantherIvyConfig
            self.available_tests = {}
    
            # Set protocol model paths
            self.protocol = protocol
            self._protocol_name_cache = None
            
            # Initialize protocol-specific data directory for flexible template system
            protocol_name = self._get_protocol_name_from_service_config()
            self.ivy_protocol_data_dir = protocol_name  # e.g., "quic" for QUIC protocol
    
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
    
            # Fix service_name access -> use the correct attribute name from the service manager
            service_name = getattr(self, 'service_name', None) or getattr(service_config_to_test, 'name', 'unknown_service')
            self.logger.info(f"Initialized PantherIvy service manager for {service_name} with role {self.role} and test: {self.test_to_compile}")

    def adapt_environment_paths(self, env_vars: Dict[str, str], use_system_models: bool) -> None:
            """
            Adapt environment variable paths using flexible template resolution.
            
            This method processes environment variables that contain path templates
            and resolves them based on the current architecture configuration.
            
            Args:
                env_vars: Dictionary of environment variables to process
                use_system_models: Whether using system models (APT architecture)
            """
            path_resolver = get_global_resolver()
            protocol_name = self._get_protocol_name_from_service_config()
            
            # Create context for path resolution
            context = path_resolver.create_architecture_context(
                use_apt_protocols=use_system_models,
                protocol_name=protocol_name
            )
            
            # # Add additional context variables
            # context.update({
            #     'homepath': os.path.expanduser('~'),
            #     'service_name': getattr(self, 'service_name', 'unknown'),
            #     'role': str(getattr(self, 'role', 'client')),
            #     'test_name': getattr(self, 'test_to_compile', 'unknown_test'),
            #     'IVY_PROTOCOL_DATA_DIR': getattr(self, 'ivy_protocol_data_dir', self.env_protocol_model_path),
            # })
            
            # CRITICAL FIX: Add template variables to environment variables
            # This ensures the Docker Compose template has access to these variables
            template_vars_to_add = [
                'PROTOCOL_PATH', 
                'USE_APT_PROTOCOLS',
                'PANTHER_IVY_BASE_DIR',
                'PANTHER_IVY_INSTALL_DIR',
                'IVY_PROTOCOL_BASE',
                'IVY_QUIC_DATA_DIR'
            ]
            
            for var_name in template_vars_to_add:
                if var_name in context and var_name not in env_vars:
                    env_vars[var_name] = context[var_name]
                    self.logger.debug(f"Added template variable to environment: {var_name}={context[var_name]}")


            env_vars["TEST_TYPE"] = oppose_role(self.role)  # Set test type based on role

            # # Process environment variables with template resolution
            # for key, value in env_vars.items():
            #     if isinstance(value, str) and '' in value:
            #         # This is a template, resolve it
            #         resolved_value = path_resolver.resolve_template(value, context)
            #         env_vars[key] = resolved_value
            #         self.logger.debug(f"Resolved template {key}: '{value}' -> '{resolved_value}'")


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
            # Try multiple sources for protocol name to improve robustness
            
            # First, try the mixin's protocol detection (which checks self.protocol)
            if hasattr(self, 'get_protocol_name'):
                protocol_name = self.get_protocol_name()
                if protocol_name and protocol_name != "unknown":
                    self.logger.debug(f"Got protocol name from mixin: {protocol_name}")
                    return protocol_name
            
            # Second, try service config protocol
            if hasattr(self.service_config_to_test, 'protocol') and hasattr(self.service_config_to_test.protocol, 'name'):
                protocol_name = getattr(self.service_config_to_test.protocol, 'name', 'unknown')
                if protocol_name and protocol_name != "unknown":
                    self.logger.debug(f"Got protocol name from service config: {protocol_name}")
                    return protocol_name
            
            # Third, try the protocol parameter passed to constructor
            if hasattr(self, 'protocol') and self.protocol:
                if hasattr(self.protocol, 'name'):
                    protocol_name = getattr(self.protocol, 'name', 'unknown')
                    if protocol_name and protocol_name != "unknown":
                        self.logger.debug(f"Got protocol name from constructor protocol: {protocol_name}")
                        return protocol_name
            
            self.logger.warning("Could not determine protocol name from any source, using 'unknown'")
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

    def _get_ivy_environment_variables(self):
            """Get base Ivy environment variables from defaults and config."""
            # Import the default environment variables
            from panther.plugins.services.testers.panther_ivy.config_schema import DEFAULT_ENVIRONMENT_VARIABLES
    
            # Start with defaults and merge in config environment variables
            ivy_env_vars = DEFAULT_ENVIRONMENT_VARIABLES.copy()
    
            if config_env_vars := getattr(self.service_config_to_test, 'environment', {}):
                ivy_env_vars.update(config_env_vars)
    
            return ivy_env_vars

    def _load_version_environment_variables(self):
        """
            Load version-specific environment variables for Ivy with robust parameter extraction.
            Handles cases where implementation parameters might not be available.
            """
            
        super()._load_version_environment_variables()
            
        protocol_name = self.get_protocol_name()

        # Determine whether to use system models (APT) or protocol models (manual architecture)
        use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)
        use_apt_protocols = "1" if use_system_models else "0"

        # Ensure protocol model paths are available
        if not hasattr(self, 'env_protocol_model_path'):
            self.env_protocol_model_path = self.get_protocol_model_path(
                use_system_models=use_system_models
            )

        if not hasattr(self, 'system_protocol_model_path'):
            # Default system protocol model path
            self.system_protocol_model_path = "/opt/panther_ivy/protocol-testing/apt/"

        protocol_model_path = self.system_protocol_model_path if use_system_models else self.env_protocol_model_path

        # Load base Ivy environment variables
        ivy_env_vars = self._get_ivy_environment_variables()

            # Robust parameter extraction helper function with enhanced debugging
        def get_implementation_parameter(param_name: str, default_value=None):
            """Robustly extract parameter from service config implementation."""
            service_config = getattr(self, 'service_config_to_test', None)
            self.logger.debug(f"Looking for parameter '{param_name}', service_config exists: {service_config is not None}")

            if service_config and hasattr(service_config, 'implementation'):
                impl = service_config.implementation
                self.logger.debug(f"Implementation object exists for '{param_name}': {impl is not None}")

                # Path 1: Direct attribute access
                if hasattr(impl, param_name):
                    value = getattr(impl, param_name)
                    self.logger.debug(f"Found '{param_name}' via direct attribute access: {value}")
                    return value

                # Path 2: Check parameters object
                if hasattr(impl, 'parameters') and impl.parameters:
                    params = impl.parameters
                    self.logger.debug(f"Implementation has parameters object for '{param_name}': {params is not None}")
                    if hasattr(params, param_name):
                        param_value = getattr(params, param_name)
                        value = param_value.value if hasattr(param_value, 'value') else param_value
                        self.logger.debug(f"Found '{param_name}' via parameters object: {value}")
                        return value
                    else:
                        self.logger.debug(f"Parameter '{param_name}' not found in parameters object")
                else:
                    self.logger.debug(f"No parameters object found for '{param_name}'")
                    
                # Path 3: Check version parameters
                if hasattr(impl, 'version') and hasattr(impl.version, 'parameters'):
                    version_params = impl.version.parameters
                    self.logger.debug(f"Implementation has version.parameters for '{param_name}': {version_params is not None}")
                    if hasattr(version_params, param_name):
                        param_value = getattr(version_params, param_name)
                        value = param_value.value if hasattr(param_value, 'value') else param_value
                        self.logger.debug(f"Found '{param_name}' via version parameters: {value}")
                        return value
                    else:
                        self.logger.debug(f"Parameter '{param_name}' not found in version parameters")
                else:
                    self.logger.debug(f"No version.parameters found for '{param_name}'")
            else:
                self.logger.debug(f"No service_config.implementation found for '{param_name}'")
                
            self.logger.debug(f"Parameter '{param_name}' not found in any location, using default: {default_value}")
            return default_value

        # Extract parameters with robust handling
        log_level_binary = get_implementation_parameter('log_level_binary', 'DEBUG')
        optimization_level = get_implementation_parameter('optimization_level', 'O0')

        self.logger.debug(f"Extracted log_level_binary: {log_level_binary}")
        self.logger.debug(f"Extracted optimization_level: {optimization_level}")

        env_vars_to_add = ivy_env_vars.copy()

        # Extract build_mode from implementation config (where it's actually stored)
        build_mode = getattr(self.service_config_to_test.implementation, 'build_mode', '')

        # Add architecture-specific variables
        env_vars_to_add.update({
            'PROTOCOL_MODEL_PATH': protocol_model_path,  # Architecture-aware path
            'USE_APT_PROTOCOLS': use_apt_protocols,  # Flag for compile-time path selection
            "PROTOCOL_TESTED": protocol_name,  # Protocol name for testing
            "IVY_DEBUG": "1" if log_level_binary == "DEBUG" else "0",
            "IVY_OPTI": optimization_level or "O0",  # Fallback to O0 if None
            "BUILD_MODE": build_mode  # Build mode for Ivy compilation
        })


        # Adapt environment variable paths based on use_system_models parameter
        # This transforms paths in version configs to match architecture choice
        self.adapt_environment_paths(env_vars_to_add, use_system_models)

        # Batch add all environment variables
        for env_name, env_value in env_vars_to_add.items():
            self.environments[env_name] = env_value
            self.logger.debug(f"Added Ivy environment variable {env_name}={env_value}")

        self.environments["ROLE"] = self.role  # Set role for Ivy service manager

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
            # git submodule foreach --recursive git reset --hard HEAD && \
            # git submodule foreach --recursive git clean -fdx && \
            # git submodule update --recursive
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
            # TODO enable choice of git submodule update --recursive
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to initialize submodules: %s", e)
        finally:
            os.chdir(current_dir)

    def generate_pre_compile_commands(self) -> List[Union[str, ShellCommand]]:
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
            self.logger.error(f"Failed to generate pre-compile commands: {e}", exc_info=True)
            return []


    def generate_compile_commands(self) -> List[Union[str, ShellCommand]]:
        """Generate compile commands using mixin integration."""
        try:
            # Get base commands from parent
            base_commands = []
            if hasattr(super(), 'generate_compile_commands'):
                base_commands = super().generate_compile_commands()
            
            # Use mixin method directly
            ivy_commands = self.generate_ivy_compile_commands()
            
            # Combine base and Ivy-specific commands
            return base_commands + ivy_commands
        except Exception as e:
            self.logger.error(f"Failed to generate compile commands: {e}")
            return base_commands if 'base_commands' in locals() else []


    def generate_run_command(self) -> Dict[str, Any]:
        """Generate run command with delegated deployment args."""
        # Build command structure
        cmd_args = self.generate_ivy_deployment_commands()
        
        command_binary = ""
        if self.test_to_compile:
            build_dir = self._get_build_dir()
            command_binary = f"./{build_dir}/{self.test_to_compile}"
        
        working_dir = self.env_protocol_model_path or \
                      f"/opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/"
        
        self.logger.debug(f"Generated run command for {self.service_name}: {command_binary} with args {cmd_args}")
        return {
            "working_dir": working_dir,
            "command_binary": command_binary,
            "command_args": cmd_args,
            "timeout": getattr(self.service_config_to_test, 'timeout', 120),
            "command_env": {},
        }

    def generate_pre_run_commands(self) -> List[Union[str, ShellCommand]]:
        """Generate pre-run commands with fallback."""
        commands = []
        if hasattr(super(), 'generate_pre_run_commands'):
            commands = super().generate_pre_run_commands()
        
        # IvyCommandGenerator doesn't have this method, so add Ivy-specific commands
        commands.append("source /app/logs/ivy_env.sh || true")
        
        return commands

    def generate_post_compile_commands(self) -> List[Union[str, ShellCommand]]:
        """Generate post-compile commands with fallback."""
        commands = []
        if hasattr(super(), 'generate_post_compile_commands'):
            commands = super().generate_post_compile_commands()
        
        # IvyCommandGenerator doesn't have this method, so add Ivy-specific commands
        commands.extend([
            f"cd {self.env_protocol_model_path}",  
            "pwd  /app/logs/ivy_post_compile.log",  
        ])
        
        return commands
    
        
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


    def generate_post_run_commands(self) -> List[Union[str, ShellCommand]]:
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
                
                # Use externally collected outputs if available (from centralized output collection)
                # This is set via set_collected_outputs() by the OutputAggregator
                if hasattr(self, '_collected_outputs') and self._collected_outputs:
                    outputs = self._collected_outputs
                    self.logger.debug(f"Using externally collected outputs: {len(outputs)} items")
                else:
                    # Fallback to direct collection (should not happen in normal flow)
                    self.logger.warning("No externally collected outputs available, attempting direct collection")
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
            self.logger.warning("No test results available -> tests may not have been run yet")
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
    
    def handle_event(self, event) -> None:
        """
        Handle events sent to this PantherIvy service manager.
        
        This implementation provides basic event handling for Ivy formal verification tests.
        It delegates to parent mixins for common event processing while allowing for
        Ivy-specific event handling extensions.
        
        Args:
            event: The event to handle
        """
        try:
            # Log the event for debugging
            self.logger.debug(f"PantherIvy handling event: {getattr(event, 'name', 'unknown')} (type: {type(event).__name__})")
            
            # Delegate to parent mixin chain for standard event handling
            # This ensures that event mixins in the inheritance chain can process events
            if hasattr(super(), 'handle_event'):
                super().handle_event(event)
            
            # Add any Ivy-specific event handling here if needed in the future
            # For now, the basic delegation to parent mixins is sufficient
            
        except Exception as e:
            self.logger.error(f"Error handling event in PantherIvy service manager: {e}")