"""
Command generation mixin for PantherIvy service manager.

This mixin extracts command generation logic from the IvyCommandGenerator component
to follow standard PANTHER architecture patterns.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from panther.core.command_processor.utils import CommandUtils
from panther.core.command_processor.builders import ServiceCommandBuilder
from panther.core.command_processor.models.shell_command import ShellCommand


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"


class IvyCommandMixin:
    """
    Mixin for Ivy-specific command generation.
    
    This mixin consolidates all command generation logic from the IvyCommandGenerator
    component into methods that can be directly used by the service manager.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize IvyCommandMixin with ServiceCommandBuilder integration."""
        super().__init__(*args, **kwargs)
        self.command_builder = None
        self._initialize_command_builder()      
        
    def _initialize_command_builder(self):
        """Initialize ServiceCommandBuilder if role is available."""
        if not self.command_builder and hasattr(self, 'role'):
            role = getattr(self, 'role', None)
            if role:
                self.command_builder = ServiceCommandBuilder(role)
            else:
                self.logger.warning("No role available for ServiceCommandBuilder initialization") if hasattr(self, 'logger') else None
    
    def generate_ivy_pre_compile_commands(self) -> List[Union[str, ShellCommand]]:
        """
        Generate pre-compilation commands with IP resolution and environment setup.
        
        Returns:
            List of command strings
        """
        commands = []

        # Initialize environment file for logging -> use phase-based structure
        commands.append("echo '# Ivy setup log' >>  /app/logs/pre-compile/ivy_setup.log")

        # Network resolution is handled by placeholders
        target_info = ""
        if hasattr(self, 'service_targets') and self.service_targets:
            target_info = f" (target: {self.service_targets})"

        commands.append(
            f"echo \"Ivy service {self.service_name} using network-aware placeholder resolution{target_info}\" >> /app/logs/pre-compile/ivy_setup.log"
        )

        # Clean build directory (safe operation - create directory if missing and clean)
        use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)
        env_protocol_path = self.get_protocol_model_path(use_system_models)
        commands.append(f"mkdir -p '{env_protocol_path}/build/' && find '{env_protocol_path}/build/' -maxdepth 1 -type f -delete 2>/dev/null || true")

        return self.phase_command_processed(
            commands, "pre-compile"
        )
    
    def generate_ivy_compile_commands(self) -> List[Union[str, ShellCommand]]:
        """
        Generate compilation commands including Ivy tool updates and test compilation.
        
        Returns:
            List of command strings
        """
        commands = []

        try:
            # Emit command generation started event (if available)
            if hasattr(self, 'emit_command_generation_started'):
                self.emit_command_generation_started("compile")

            # Build comprehensive compilation commands
            compilation_commands = self._generate_comprehensive_compilation_commands()
            commands.extend(compilation_commands)

            # Notify compilation started (if available)
            if hasattr(self, 'notify_service_event'):
                protocol_name = self.get_protocol_name()
                test_to_compile = getattr(self, 'test_to_compile', 'unknown_test')
                self.notify_service_event(
                    "compilation_started",
                    {
                        "protocol": protocol_name,
                        "test": test_to_compile,
                    },
                )

            # Signal ivy compilation completion to coordination system
            service_name = getattr(self, 'service_name', 'ivy')
            ready_commands = [
                f'echo "Ivy compilation completed for {service_name}" >> /app/logs/coordination.log',
                f"touch /app/coordination/{service_name}_ivy_ready",
                f'echo "ready_$(date +%s)" > /app/coordination/{service_name}_ivy_ready'
            ]
            
            if compilation_commands:
                commands.extend(ready_commands)
            else:
                commands = ready_commands

            # Emit command generated event (if available)
            if hasattr(self, 'emit_command_generated'):
                self.emit_command_generated("compile", str(commands))

            return self.phase_command_processed(
                commands, "compile"
            )
        except Exception as e:
            self.logger.error(f"Failed to generate compile commands: {e}")
            raise
    
    def generate_ivy_deployment_commands(self) -> str:
        """
        Generate deployment command arguments for Ivy test execution.
        
        Returns:
            str: Command arguments for test execution
        """
        try:
            self.logger.debug(f"Generating deployment commands for service: {getattr(self, 'service_name', 'unknown')}")

            # Get role from service manager
            role = getattr(self, 'role', None)
            if not role:
                self.logger.warning("No role found in service manager")
                raise ValueError("Role is required for deployment command generation")

            # Get service configuration
            service_config = getattr(self, 'service_config_to_test', None)
            if not service_config:
                self.logger.warning("No service configuration found")
                raise ValueError("Service configuration is required for deployment command generation")

            # Get role-specific parameters
            params = {}
            role_name = role.name if hasattr(role, 'name') else str(role)
            self.logger.debug(f"Role name: {role_name}")

            # First, get parameters from the version config 'parameters' section
            if hasattr(service_config, 'implementation') and service_config.implementation.version_config:
                version_config = service_config.implementation.version_config
                self.logger.debug(f"Found version_config: {type(version_config)} - {version_config}")

                # version_config is now a dictionary, extract parameters
                if isinstance(version_config, dict) and 'parameters' in version_config:
                    version_params = version_config['parameters']
                    self.logger.debug(f"Extracting version parameters: {version_params}")
                else:
                    self.logger.warning(f"No 'parameters' found in version_config: {version_config}")
                    version_params = {}

                if isinstance(version_params, dict):
                    # If it's a dictionary
                    self.logger.debug("Processing version_params as dictionary")
                    for param_name, param_data in version_params.items():
                        self.logger.debug(f"Processing param {param_name}: {param_data} (type: {type(param_data)})")
                        if isinstance(param_data, dict) and 'value' in param_data:
                            params[param_name] = param_data['value']
                            self.logger.debug(f"  -> Set {param_name} = {param_data['value']}")
                        else:
                            params[param_name] = param_data
                            self.logger.debug(f"  -> Set {param_name} = {param_data}")
                else:
                    self.logger.warning(f"version_params is neither dict nor object with __dict__: {type(version_params)}")
            else:
                self.logger.warning("service_config.implementation.version_config not available for parameter extraction")


            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, "version"):
                implem_version = service_config.implementation.version
                self.logger.debug(f"Version is: {implem_version}")

            # Get role-specific parameters from version_config
            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'version_config'):
                version_config = service_config.implementation.version_config
                
                if role_name == "server":
                    # Check for server parameters in dict or object
                    server_params = None
                    if isinstance(version_config, dict) and 'server' in version_config:
                        server_params = version_config['server']
                    elif hasattr(version_config, 'server'):
                        server_params = version_config.server
                    
                    if server_params:
                        self.logger.debug("Using server parameters from implementation version")
                        self.logger.debug(f"Server parameters: {server_params}")
                        if isinstance(server_params, dict):
                            params |= server_params
                        elif hasattr(server_params, '__dict__'):
                            params |= server_params.__dict__
                    else:
                        self.logger.warning("No server parameters found in implementation version")
                        raise ValueError("No server parameters found")
                        
                elif role_name == "client":
                    # Check for client parameters in dict or object
                    client_params = None
                    if isinstance(version_config, dict) and 'client' in version_config:
                        client_params = version_config['client']
                    elif hasattr(version_config, 'client'):
                        client_params = version_config.client
                    
                    if client_params:
                        self.logger.debug("Using client parameters from implementation version")
                        self.logger.debug(f"Client parameters: {client_params}")
                        if isinstance(client_params, dict):
                            params |= client_params
                        elif hasattr(client_params, '__dict__'):
                            params |= client_params.__dict__
                    else:
                        self.logger.warning("No client parameters found in implementation version")
                        raise ValueError("No client parameters found")

            # Add additional parameters from implementation
            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'parameters'):
                impl_params = service_config.implementation.parameters
                if hasattr(impl_params, '__dict__'):
                    for param_name, param_obj in impl_params.__dict__.items():
                        if hasattr(param_obj, 'value'):
                            params[param_name] = param_obj.value
                        else:
                            params[param_name] = param_obj

            # Get service name -> this is critical and must not be None
            service_name = getattr(self, 'service_name', None)
            if not service_name:
                self.logger.error("Service name is not set in service manager")
                raise ValueError("Service name is required for network placeholder resolution")

            # Additional validation to ensure it's not None or empty string
            if (
                service_name == "None"
                or service_name == ""
                or not str(service_name).strip()
            ):
                self.logger.error(f"Invalid service name: '{service_name}' -> must be a valid service identifier")
                raise ValueError(f"Service name '{service_name}' is invalid for network placeholder resolution")

            params["service_name"] = service_name

            # Get target service name
            target = None

            # First check protocol configuration
            if hasattr(service_config, 'protocol') and service_config.protocol:
                self.logger.debug(f"Protocol config available: {service_config.protocol}")
                if hasattr(service_config.protocol, 'target'):
                    target = service_config.protocol.target
                    self.logger.info(f"Using target from protocol config: {target}")

            # If no target from protocol, check service_targets
            if not target:
                target = getattr(self, 'service_targets', None)
                if target:
                    self.logger.info(f"Using target from service_targets: {target}")

            # Validate target -> for ivy services, we need a target
            if not target:
                if role_name == "client":
                    self.logger.warning("No target service specified for network resolution")
                    raise ValueError("Target service must be specified for Ivy client role")
                # Fallback to hardcoded defaults
                if role_name == "server":
                    target = "ivy_server"  # Default server service name 

            params["target"] = target
            params["role"] = role_name
            params["implementation"] = self.implementation_name
            params["is_server"] = role_name == "server"
            params["is_client"] = oppose_role(role_name) == "client"
            params["test_name"] = self.test_to_compile
            params["timeout_cmd"] = f"timeout {service_config.timeout} "


            # Validate critical parameters before template rendering
            critical_params = ['service_name', 'target']
            for param_name in critical_params:
                if param_name not in params:
                    self.logger.error(f"Critical parameter '{param_name}' is missing from template params")
                    raise ValueError(f"Parameter '{param_name}' is required for network placeholder resolution")

                param_value = params[param_name]
                if param_value is None:
                    self.logger.error(f"Critical parameter '{param_name}' is None in template params")
                    raise ValueError(f"Parameter '{param_name}' cannot be None for network placeholder resolution")

                # Check for string representations of None or empty values
                if str(param_value) in {"None", "", "null", "undefined"}:
                    self.logger.error(f"Critical parameter '{param_name}' has invalid value: '{param_value}'")
                    raise ValueError(f"Parameter '{param_name}' cannot be '{param_value}' for network placeholder resolution")

            # Use template rendering to generate arguments
            template_name = f"{oppose_role(role_name)}_command.jinja"

            if template_renderer := getattr(self, 'template_renderer', None):
                # Preprocess template context to resolve network placeholders
                if hasattr(self, 'preprocess_template_context_with_network_resolution'):
                    params = self.preprocess_template_context_with_network_resolution(params)
                    self.logger.debug("Preprocessed template context with network resolution")

                cmd_args = template_renderer.render_template(template_name, params)

                # Validate and decode rendered command
                if cmd_args:
                    is_valid, corrected_cmd_args = self._validate_deployment_command(cmd_args)
                    if is_valid:
                        self.logger.debug(f"Generated command args from template: {corrected_cmd_args.strip()}")
                        return corrected_cmd_args.strip()
                    else:
                        self.logger.warning("Command arguments validation failed")
                        raise ValueError("Generated command arguments are invalid")
                else:
                    self.logger.warning("No command arguments generated from template")
                    raise ValueError("Generated command arguments are empty")
            else:
                self.logger.warning("No template renderer available")
                raise ValueError("No template renderer available")

        except Exception as e:
            self.logger.error(f"Failed to generate deployment commands: {e}")
            raise

    def generate_ivy_post_run_commands(self) -> List[Union[str, ShellCommand]]:
        """
        Generate post-run cleanup commands.
        
        Returns:
            List of command strings
        """
        commands = []

        # Copy test binary if needed
        if hasattr(self, 'test_to_compile') and self.test_to_compile and hasattr(self, 'env_protocol_model_path'):
            # Get build directory
            tests_build_dir = self._get_build_dir()
            test_path = os.path.join(self.env_protocol_model_path, tests_build_dir, self.test_to_compile)

            commands.extend([
                f"cp '{test_path}' '/app/logs/artifacts/{self.test_to_compile}'",  # Use phase-based artifacts directory
                f"find '{os.path.dirname(test_path)}' -name '{os.path.basename(test_path)}*' -type f -delete 2>/dev/null || true"
            ])

        return self.phase_command_processed(
            commands, "post-run"
        )

    def phase_command_processed(self, commands, phase) -> List[str]:
        """
        Process commands for the phase command and log the processed commands.

        This method takes a list of commands and processes them, then logs the
        structured command generation with the provided argument.

        Args:
            commands (list): List of commands to be processed.
            phase: Argument to be passed to the structured command generation logger.

        Returns:
            list: The processed commands.
        """
        processed_commands = self._process_commands(commands, phase)
        CommandUtils.log_structured_command_generation(
            self.logger, phase, processed_commands
        )
        return processed_commands
    
    def _build_ivy_update_commands(self) -> List[str]:
        """Build Ivy tool update commands."""
        commands = [
            "echo 'Updating Ivy tool...' >> /app/logs/compile/ivy_setup.log",
            "cd /opt/panther_ivy && sudo python3.10 setup.py install >> /app/logs/compile/ivy_setup.log 2>&1",
            "cd /opt/panther_ivy && cp lib/libz3.so /opt/panther_ivy/submodules/z3/build/python/z3 >> /app/logs/compile/ivy_setup.log 2>&1",
            "echo 'Copying updated Ivy files...' >> /app/logs/compile/ivy_setup.log",
            "find '/opt/panther_ivy/ivy/include/1.7/' -type f -name '*.ivy' -exec cp {} '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' ';' >> /app/logs/compile/ivy_setup.log 2>&1",
        ]

        # Protocol-specific setup
        if self.get_protocol_name() in ["quic", "apt"]:
            commands.extend(self._build_quic_setup_commands())

        # Set up Ivy model
        commands.extend(self._build_ivy_model_setup_commands())

        return commands
    
    def _build_quic_setup_commands(self) -> List[str]:
        """Build QUIC-specific setup commands."""
        commands = [
            "echo 'Copying QUIC libraries...' >> /app/logs/compile/ivy_setup.log",
            "cp -f -a '/opt/picotls/'*.a '/usr/local/lib/python3.10/dist-packages/ivy/lib/' >> /app/logs/compile/ivy_setup.log 2>&1",
            "cp -f -a '/opt/picotls/'*.a '/opt/panther_ivy/ivy/lib/'  >> /app/logs/compile/ivy_setup.log 2>&1",
            "cp -f '/opt/picotls/include/picotls.h' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls.h' >> /app/logs/compile/ivy_setup.log 2>&1",
            "cp -f '/opt/picotls/include/picotls.h' '/opt/panther_ivy/ivy/include/picotls.h' >> /app/logs/compile/ivy_setup.log 2>&1",
            "cp -r -f '/opt/picotls/include/picotls/.' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls' >> /app/logs/compile/ivy_setup.log 2>&1",
        ]

        if hasattr(self, 'env_protocol_model_path'):
            # Add quic_ser_deser.h copy
            use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)
            if use_system_models:
                quic_ser_deser_path = f"{self.env_protocol_model_path}/apt_protocols/quic/quic_utils/quic_ser_deser.h"
            else:
                quic_ser_deser_path = f"{self.env_protocol_model_path}/quic_utils/quic_ser_deser.h"

            commands.append(
                f"cp -f '{quic_ser_deser_path}' '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' >> /app/logs/compile/ivy_setup.log 2>&1"
            )

        return commands
    
    def _build_ivy_model_setup_commands(self) -> List[str]:
        """Build Ivy model setup commands."""
        if not hasattr(self, 'env_protocol_model_path'):
            return []
            
        commands = [
            "echo 'Setting up Ivy model...' >> /app/logs/compile/ivy_setup.log",
            f"echo 'Updating include path from {self.env_protocol_model_path}' >> /app/logs/compile/ivy_setup.log",
            "find '" + self.env_protocol_model_path + "' -type f -name '*.ivy' -exec cp -f {} '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' ';' >> /app/logs/compile/ivy_setup.log 2>&1",
            "ls -l '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' >> /app/logs/compile/ivy_setup.log",
        ]

        return commands
    
    def _build_test_compilation_commands(self):
        """
            Build commands for test compilation using ivy_check.
            
            Returns:
                List[str]: Command sequence for test compilation
            """
        # Store current config for role-based commands
        use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)

        if use_system_models:
            return []

        commands = []
        container_base_path = self.env_protocol_model_path

        # Get role information
        role = self.role
        role_name = role.name if hasattr(role, 'name') else str(role)
        protocol_name = self.get_protocol_name()

        # Get internal iterations parameter with robust extraction
        internal_iterations = 100  # Default
        service_config = getattr(self, 'service_config_to_test', None)

        # Debug the service config structure
        self.logger.debug(f"Service config for test compilation: {type(service_config)}")
        if service_config:
            self.logger.debug(f"Service config attributes: {dir(service_config)}")
            if hasattr(service_config, 'implementation'):
                self.logger.debug(f"Implementation attributes: {dir(service_config.implementation)}")
                if hasattr(service_config.implementation, 'parameters'):
                    params = service_config.implementation.parameters
                    self.logger.debug(f"Implementation parameters: {params}")
                    self.logger.debug(f"Parameters type: {type(params)}")
                    if params:
                        self.logger.debug(f"Parameters attributes: {dir(params)}")

        # Attempt multiple extraction paths for internal_iterations
        if service_config and hasattr(service_config, 'implementation'):
            impl = service_config.implementation

            # Path 1: Direct access to implementation parameters
            if hasattr(impl, 'parameters') and impl.parameters:
                params = impl.parameters
                if hasattr(params, 'internal_iterations_per_test'):
                    param_value = params.internal_iterations_per_test
                    if hasattr(param_value, 'value'):
                        internal_iterations = param_value.value
                    else:
                        internal_iterations = param_value
                    self.logger.debug(f"Found internal_iterations via implementation.parameters: {internal_iterations}")

                # Also check for alternative parameter names
                elif hasattr(params, 'internal_iterations'):
                    param_value = params.internal_iterations
                    if hasattr(param_value, 'value'):
                        internal_iterations = param_value.value
                    else:
                        internal_iterations = param_value
                    self.logger.debug(f"Found internal_iterations via alternative name: {internal_iterations}")

            # Path 2: Check version parameters (as seen in tests)
            if hasattr(impl, 'version') and hasattr(impl.version, 'parameters'):
                version_params = impl.version.parameters
                if hasattr(version_params, 'internal_iterations_per_test'):
                    param_value = version_params.internal_iterations_per_test
                    if hasattr(param_value, 'value'):
                        internal_iterations = param_value.value
                    else:
                        internal_iterations = param_value
                    self.logger.debug(f"Found internal_iterations via version.parameters: {internal_iterations}")

            # Path 3: Direct attribute check on implementation
            if hasattr(impl, 'internal_iterations_per_test'):
                param_value = impl.internal_iterations_per_test
                if hasattr(param_value, 'value'):
                    internal_iterations = param_value.value
                else:
                    internal_iterations = param_value
                self.logger.debug(f"Found internal_iterations via direct implementation attribute: {internal_iterations}")

        self.logger.info(f"Using internal_iterations value: {internal_iterations}")

        # Construct test directory paths
        if use_system_models:
            container_file_path = os.path.join(container_base_path, "apt_tests", f"attacker_{oppose_role(role_name)}_tests")
        else:
            test_dir = self._extract_test_directory_from_name(self.test_to_compile, role_name)
            container_file_path = os.path.join(container_base_path, f"{protocol_name}_tests", test_dir)

        self.logger.info(f"Container path for test compilation: {container_file_path}")

        # Get build directory
        tests_build_dir = self._get_build_dir()

        # Get role information
        role = self.role
        role_name = role.name if hasattr(role, 'name') else str(role)
        protocol_name = self.get_protocol_name()

        # Get internal iterations parameter
        internal_iterations = 100  # Default
        if service_config := getattr(self, 'service_config_to_test', None):
            # Access internal_iterations_per_test directly from PantherIvyConfig
            internal_iterations = getattr(service_config, 'internal_iterations_per_test', 300)

        # Construct test directory paths
        if use_system_models:
            container_file_path = os.path.join(container_base_path, "apt_tests", f"attacker_{oppose_role(role_name)}_tests")
        else:
            test_dir = self._extract_test_directory_from_name(self.test_to_compile, role_name)
            container_file_path = os.path.join(container_base_path, f"{protocol_name}_tests", test_dir)

        self.logger.info(f"Container path for test compilation: {container_file_path}")

        # Get build directory
        tests_build_dir = self._get_build_dir()

        return [
            f"echo 'Compiling test {self.test_to_compile}...' >> /app/logs/compile/ivy_compile.log",
            f"mkdir -p '{container_base_path}/{tests_build_dir}'",
            f"cd $PYTHON_IVY_DIR/ivy/include/1.7 && pwd >> /app/logs/compile/ivy_compile.log 2>&1 && ls -la >> /app/logs/compile/ivy_compile.log 2>&1 && ivyc show_compiled=false trace=false target=test test_iters={internal_iterations} {self.test_to_compile}.ivy >> /app/logs/compile/ivy_compile.log 2>&1",
            "COMPILE_RESULT=$?",
            '(if [ "$' + '{COMPILE_RESULT:-0}" -eq 0 ] 2>/dev/null; then echo "Compilation succeeded"; else echo "Compilation failed with code $' + '{COMPILE_RESULT:-unknown}"; fi) > /app/logs/compile/compilation_status.txt',
            "echo 'Copying executable from ivy include to build directory...' >> /app/logs/compile/ivy_compile.log",
            f"cp '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/{self.test_to_compile}' '{container_base_path}/{tests_build_dir}/' >> /app/logs/compile/ivy_compile.log 2>&1",
            f"ls -la '{container_base_path}/{tests_build_dir}/' >> /app/logs/compile/ivy_compile.log",
        ]

    def _extract_test_directory_from_name(self, test_name: str, role_name: str) -> str:
        """Extract test directory from test name."""
        if "client" in test_name.lower():
            return "client_tests"
        elif "server" in test_name.lower():
            return "server_tests"
        else:
            # Fallback to opposite role
            return f"{oppose_role(role_name)}_tests"
    
    def _get_build_dir(self) -> str:
            """Get build directory from configuration with robust extraction."""
            service_config = getattr(self, 'service_config_to_test', None)
            
            if service_config and hasattr(service_config, 'implementation'):
                impl = service_config.implementation
                
                # Path 1: Direct access to implementation parameters
                if hasattr(impl, 'parameters') and impl.parameters:
                    params = impl.parameters
                    if hasattr(params, 'tests_build_dir'):
                        param_value = params.tests_build_dir
                        if hasattr(param_value, 'value'):
                            return str(param_value.value)
                        return str(param_value)
                
                # Path 2: Check version parameters
                if hasattr(impl, 'version') and hasattr(impl.version, 'parameters'):
                    version_params = impl.version.parameters
                    if hasattr(version_params, 'tests_build_dir'):
                        param_value = version_params.tests_build_dir
                        if hasattr(param_value, 'value'):
                            return str(param_value.value)
                        return str(param_value)
                
                # Path 3: Direct attribute check on implementation
                if hasattr(impl, 'tests_build_dir'):
                    param_value = impl.tests_build_dir
                    if hasattr(param_value, 'value'):
                        return str(param_value.value)
                    return str(param_value)
            
            return "build"

    
    def _generate_comprehensive_compilation_commands(self) -> List[str]:
        """Generate comprehensive compilation commands (restored from original)."""
        self.logger.debug(f"Generating compilation commands for service: {getattr(self, 'service_name', 'unknown')}")
        
        # Set up environments
        service_config = getattr(self, 'service_config_to_test', None)
        if not service_config:
            return []
            
        # Get environment configurations
        protocol_env = {}
        
        if hasattr(service_config, 'implementation') and (hasattr(service_config.implementation, 'version') and hasattr(service_config.implementation.version, 'env')):
            protocol_env = service_config.implementation.version.env or {}
        
        # Adjust protocol environment for non-system models
        use_system_models = getattr(service_config.implementation, 'use_system_models', False) if hasattr(service_config, 'implementation') else False
        if not use_system_models:
            for key in protocol_env:
                if isinstance(protocol_env[key], str):
                    protocol_env[key] = protocol_env[key].replace("/apt/apt_protocols", "")
        
        # Set test path
        test_to_compile = getattr(self, 'test_to_compile', None)
        self.logger.info(f"Setting test path to: {test_to_compile}")
        
        # Build Ivy tool update commands
        update_commands = self._build_ivy_update_commands()
        
        # Build test compilation commands
        test_commands = self._build_test_compilation_commands()
        
        return update_commands + test_commands
    
    def _process_commands(self, commands: List[Union[str, ShellCommand]], phase: str) -> List[Union[str, ShellCommand]]:
        """Process commands through ServiceCommandBuilder."""
        # Ensure command builder is initialized
        if not self.command_builder:
            # Fallback if no command builder available
            return [cmd.strip() for cmd in commands if cmd and cmd.strip()]
        try:
            # Reset builder to start fresh
            self.command_builder.reset()

            # Add commands to builder
            for cmd in commands:
                if cmd and isinstance(cmd, str):
                    # Determine if this is a non-critical command like ls or echo
                    is_non_critical_command = cmd.strip().startswith(('ls', 'echo'))
                    
                    # A command is critical if we're in compile/pre-compile phase AND it's not a simple echo/ls command
                    is_critical = ("compile" in phase or "pre-compile" in phase) and not is_non_critical_command
                    
                    self.command_builder.add_command(
                        cmd.strip(),
                        is_critical=is_critical,
                    )
                elif isinstance(cmd, ShellCommand):
                     # Determine if this is a non-critical command like ls or echo
                    is_non_critical_command = cmd.command.strip().startswith(('ls', 'echo'))

                    # A command is critical if we're in compile/pre-compile phase AND it's not a simple echo/ls command
                    is_critical = ("compile" in phase or "pre-compile" in phase) and not is_non_critical_command
                    
                    cmd.metadata['is_critical'] = is_critical
                    
                    self.command_builder.add_command(cmd.command.strip(), cmd.metadata)

            # Process and return commands
            processed = self.command_builder.process_commands("panther_ivy")

            # Extract command strings from processed format
            # The process_commands returns a list of dicts with command info
            return processed 
        
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Command processing failed: {e}")
            # Fallback to original commands if processing fails
            return [cmd.strip() for cmd in commands if cmd and cmd.strip()]
    
    def _validate_deployment_command(self, cmd_args: str) -> tuple[bool, str]:
        """Validate deployment command for common issues.
        
        Returns:
            Tuple of (is_valid, corrected_command)
        """
        validation_errors = []
        
        self.logger.debug(f"Validating command arguments: {cmd_args}")

        # Decode HTML entities first
        import html
        decoded_cmd_args = html.unescape(cmd_args)
        if decoded_cmd_args != cmd_args:
            self.logger.debug(f"Decoded HTML entities in command: {decoded_cmd_args}")
            cmd_args = decoded_cmd_args

        # Check for @None placeholders
        if "@None" in cmd_args:
            validation_errors.append("Contains @None placeholders")

        # Check for unbalanced braces
        if cmd_args.count('{') != cmd_args.count('}'):
            validation_errors.append("Contains unbalanced braces")

        # Check for empty parameter values
        empty_params = re.findall(r'(\w+)=\s*(?=\s|\}|$)', cmd_args)
        if empty_params:
            validation_errors.append(f"Contains empty parameters: {empty_params}")

        # Check for malformed placeholders - updated to handle service names with valid characters
        valid_placeholder_pattern = r'@\{[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_][a-zA-Z0-9_]*\}'
        all_placeholders = re.findall(r'@\{[^}]+\}', cmd_args)
        if malformed := [
            p
            for p in all_placeholders
            if not re.match(valid_placeholder_pattern, p)
        ]:
            validation_errors.append(f"Contains malformed placeholders: {malformed}")


        if validation_errors:
            self.logger.error(f"Command validation failed: {', '.join(validation_errors)}")
            self.logger.error(f"Generated command: {cmd_args}")
            return False, cmd_args

        return True, cmd_args
    
    def _validate_shell_syntax(self, cmd_args: str) -> List[str]:
        """Validate shell syntax for common errors."""
        errors = []
        
        # Check for malformed redirections
        malformed_redirections = re.findall(r'>\d+/', cmd_args)
        if malformed_redirections:
            errors.append(f"Malformed redirections: {malformed_redirections} (should be '2>/dev/null' or '> /dev/null 2>&1')")
        
        # Check for unmatched quotes
        single_quotes = cmd_args.count("'")
        double_quotes = cmd_args.count('"')
        if single_quotes % 2 != 0:
            errors.append("Unmatched single quotes")
        if double_quotes % 2 != 0:
            errors.append("Unmatched double quotes")
        
        # Check for missing spaces in command chains
        if re.search(r'[^;]\s*;\s*[^;]', cmd_args):
            # This is actually correct, so let's check for missing spaces around operators
            pass
        
        # Check for invalid path patterns
        invalid_paths = re.findall(r'/[^/\s]*[^/\s\w.-][^/\s]*', cmd_args)
        # Filter out valid special characters in paths
        actual_invalid = [p for p in invalid_paths if not re.match(r'^/[\w./-]*$', p)]
        if actual_invalid:
            errors.append(f"Potentially invalid paths: {actual_invalid}")
        
        # Check for command substitution issues
        if '`' in cmd_args and cmd_args.count('`') % 2 != 0:
            errors.append("Unmatched backticks in command substitution")
            
        return errors