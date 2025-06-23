"""
Command generation mixin for PantherIvy service manager.

This mixin extracts command generation logic from the IvyCommandGenerator component
to follow standard PANTHER architecture patterns.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from panther.core.command_processor.command_utils import CommandUtils
from panther.core.command_processor.command_builder import ServiceCommandBuilder


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"


class IvyCommandMixin(ErrorHandlerMixin):
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
            if role := getattr(self, 'role', None):
                self.command_builder = ServiceCommandBuilder(role)
            else:
                self.logger.warning("No role available for ServiceCommandBuilder initialization") if hasattr(self, 'logger') else None
    
    def generate_ivy_pre_compile_commands(self) -> List[str]:
        """
        Generate pre-compilation commands with IP resolution and environment setup.
        
        Returns:
            List of command strings
        """
        # Network resolution is handled by placeholders
        target_info = ""
        if hasattr(self, 'service_targets') and self.service_targets:
            target_info = f" (target: {self.service_targets})"

        commands = [
            "echo '# Ivy setup log' > /app/logs/pre-compile/ivy_setup.log",
            f'echo \"Ivy service {self.service_name} using network-aware placeholder resolution{target_info}\" >> /app/logs/pre-compile/ivy_setup.log',
        ]
        # Clean build directory
        use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)
        env_protocol_path = self.get_protocol_model_path(use_system_models)
        commands.append(f"find '{env_protocol_path}/build/' -maxdepth 1 -type f -delete 2>/dev/null || true")

        return self.generate_ivy_commands(
            commands, "pre-compile"
        )


    def generate_ivy_compile_commands(self, commands):
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

        # Add ready file creation
        if compilation_commands:
            commands.append("touch /app/sync_logs/ivy_ready.log")
        else:
            commands = ["touch /app/sync_logs/ivy_ready.log"]

        # Emit command generated event (if available)
        if hasattr(self, 'emit_command_generated'):
            self.emit_command_generated("compile", str(commands))

        return self.generate_ivy_commands(
            commands, "compile"
        )
    
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
                return ""

            # Get service configuration
            service_config = getattr(self, 'service_config_to_test', None)
            if not service_config:
                self.logger.warning("No service configuration found")
                return ""

            # Get role-specific parameters
            params = {}
            role_name = role.name if hasattr(role, 'name') else str(role)
            self.logger.debug(f"Role name: {role_name}")

            # First, get parameters from the version config 'parameters' section
            if hasattr(service_config, 'implementation') and service_config.implementation.version_config:
                version_config = service_config.implementation.version_config
                self.logger.info(f"Found version_config: {type(version_config)}")

                # version_config is now a dictionary, extract parameters
                if isinstance(version_config, dict) and 'parameters' in version_config:
                    version_params = version_config['parameters']
                    self.logger.info(f"Extracting version parameters: {version_params}")
                else:
                    self.logger.warning(f"No 'parameters' found in version_config: {version_config}")
                    version_params = {}

                if hasattr(version_params, '__dict__'):
                    # If it's an object with attributes
                    self.logger.debug("Processing version_params as object with __dict__")
                    for param_name, param_obj in version_params.__dict__.items():
                        self.logger.debug(f"Processing param {param_name}: {param_obj} (type: {type(param_obj)})")
                        if hasattr(param_obj, 'value'):
                            params[param_name] = param_obj.value
                            self.logger.debug(f"  -> Set {param_name} = {param_obj.value}")
                        else:
                            params[param_name] = param_obj
                            self.logger.debug(f"  -> Set {param_name} = {param_obj}")
                elif isinstance(version_params, dict):
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
                    self.logger.debug(f"version_params is neither dict nor object with __dict__: {type(version_params)}")
            else:
                self.logger.info("service_config.implementation.version_config not available for parameter extraction")

            # Get server parameters if available
            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'version'):
                if role_name == "server":
                    if hasattr(service_config.implementation.version, 'server'):
                        self.logger.debug("Using server parameters from implementation version")
                        server_params = service_config.implementation.version.server or {}
                        if isinstance(server_params, dict):
                            params |= server_params
                        elif hasattr(server_params, '__dict__'):
                            params.update(server_params.__dict__)
                    else:
                        self.logger.debug("No server parameters found in implementation version")
                elif hasattr(service_config.implementation.version, 'client'):
                    self.logger.debug("Using client parameters from implementation version")
                    client_params = service_config.implementation.version.client or {}
                    if isinstance(client_params, dict):
                        params.update(client_params)
                    elif hasattr(client_params, '__dict__'):
                        params.update(client_params.__dict__)
                else:
                    self.logger.debug("No client parameters found in implementation version")

            # Add additional parameters directly from service_config (no nested structure needed)
            # Parameters are now direct fields on PantherIvyConfig
            param_fields = ['tests_output_dir', 'tests_build_dir', 'iterations_per_test', 
                          'internal_iterations_per_test', 'timeout', 'keep_alive', 
                          'run_in_docker', 'get_tests_stats', 'log_level']

            for param_name in param_fields:
                if hasattr(service_config, param_name):
                    params[param_name] = getattr(service_config, param_name)

            # Get service name - this is critical and must not be None
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
                self.logger.error(f"Invalid service name: '{service_name}' - must be a valid service identifier")
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

            # Validate target - for ivy services, we need a target
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

            # DEBUG: Log what target we're using
            self.logger.info(f"Template parameter 'target' set to: '{target}' for role '{role_name}'")

            # Log params for debugging
            self.logger.debug(f"Template params count: {len(params)}")
            self.logger.debug(f"Template params keys: {list(params.keys())}")

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
                cmd_args = template_renderer.render_template(template_name, params)

                # Validate rendered command
                if cmd_args and self._validate_deployment_command(cmd_args):
                    self.logger.debug(f"Generated command args from template: {cmd_args.strip()}")
                    return cmd_args.strip()
                else:
                    self.logger.warning("No command arguments generated from template")
                    return ""
            else:
                self.logger.warning("No template renderer available")
                return ""

        except Exception as e:
            self.logger.error(f"Failed to generate deployment commands: {e}")
            return ""
    
    def generate_ivy_post_run_commands(self) -> List[str]:
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

        return self.generate_ivy_commands(
            commands, "post-run"
        )

    def generate_ivy_commands(self, commands, arg1):
        processed_commands = self._process_commands(commands)
        CommandUtils.log_structured_command_generation(
            self.logger, arg1, processed_commands
        )
        return processed_commands
    
    def _build_ivy_update_commands(self) -> List[str]:
        """Build Ivy tool update commands."""
        commands = [
            "echo 'Updating Ivy tool...' >> /app/logs/compile/ivy_setup.log",
            "cd /opt/panther_ivy && sudo python3.10 setup.py install >> /app/logs/compile/ivy_setup.log 2>&1",
            "cd /opt/panther_ivy && cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/compile/ivy_setup.log 2>&1 || true",
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
            "cp -f -a '/opt/picotls/'*.a '/usr/local/lib/python3.10/dist-packages/ivy/lib/'",
            "cp -f -a '/opt/picotls/'*.a '/opt/panther_ivy/ivy/lib/'",
            "cp -f '/opt/picotls/include/picotls.h' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls.h'",
            "cp -f '/opt/picotls/include/picotls.h' '/opt/panther_ivy/ivy/include/picotls.h'",
            "cp -r -f '/opt/picotls/include/picotls/.' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls'",
        ]

        if hasattr(self, 'env_protocol_model_path'):
            # Add quic_ser_deser.h copy
            use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)
            if use_system_models:
                quic_ser_deser_path = f"{self.env_protocol_model_path}/apt_protocols/quic/quic_utils/quic_ser_deser.h"
            else:
                quic_ser_deser_path = f"{self.env_protocol_model_path}/quic_utils/quic_ser_deser.h"

            commands.append(
                f"cp -f '{quic_ser_deser_path}' '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/'"
            )

        return commands
    
    def _build_ivy_model_setup_commands(self) -> List[str]:
        """Build Ivy model setup commands."""
        if not hasattr(self, 'env_protocol_model_path'):
            return []

        return [
            "echo 'Setting up Ivy model...' >> /app/logs/compile/ivy_setup.log",
            f"echo 'Updating include path from {self.env_protocol_model_path}' >> /app/logs/compile/ivy_setup.log",
            f"find '{self.env_protocol_model_path}' -type f -name '*.ivy' -exec cp -f {{}} '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' ';'",
            "ls -l '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' >> /app/logs/compile/ivy_setup.log",
        ]
    
    def _build_test_compilation_commands(self) -> List[str]:
        """Build test compilation commands."""
        if not hasattr(self, 'test_to_compile') or not self.test_to_compile:
            self.logger.warning("No test name specified for compilation")
            return []

        self.logger.info(f"Compiling test: {self.test_to_compile}")

        # Determine paths
        use_system_models = getattr(self.service_config_to_test.implementation, 'use_system_models', False)

        if use_system_models:
            container_base_path = f"{self.env_protocol_model_path}/apt/"
        else:
            container_base_path = self.env_protocol_model_path

        # Get role information
        role = self.role
        role_name = role.name if hasattr(role, 'name') else str(role)
        protocol_name = self.get_protocol_name()

        # Get internal iterations parameter
        internal_iterations = 100  # Default
        service_config = getattr(self, 'service_config_to_test', None)
        if service_config:
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
            f"cd $PYTHON_IVY_DIR/ivy/include/1.7 && pwd >> /app/logs/compile/ivy_compile.log 2>&1 && ls -la >> /app/logs/compile/ivy_compile.log 2>&1 && PYTHONPATH=$PYTHON_IVY_DIR ivyc show_compiled=false trace=false target=test test_iters={internal_iterations} {self.test_to_compile}.ivy >> /app/logs/compile/ivy_compile.log 2>&1",
            "COMPILE_RESULT=$?",
            "(if [ $COMPILE_RESULT -eq 0 ]; then echo 'Compilation succeeded'; else echo 'Compilation failed with code $COMPILE_RESULT'; fi) > /app/logs/compile/compilation_status.txt",
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
            """Get build directory from configuration."""
            return getattr(self.service_config_to_test, 'tests_build_dir', 'build')

    
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
    
    def _process_commands(self, commands: List[str]) -> List[str]:
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
                if cmd and cmd.strip():
                    self.command_builder.add_command(cmd.strip())

            # Process and return commands
            processed = self.command_builder.process_commands("panther_ivy")

            # Extract command strings from processed format
            # The process_commands returns a list of dicts with command info
            return [item.get('command', '') for item in processed if item.get('command')]

        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Command processing failed: {e}")
            # Fallback to original commands if processing fails
            return [cmd.strip() for cmd in commands if cmd and cmd.strip()]
    
    def _validate_deployment_command(self, cmd_args: str) -> bool:
        """Validate deployment command for common issues."""
        validation_errors = []

        # Check for @None placeholders
        if "@None" in cmd_args:
            validation_errors.append("Contains @None placeholders")

        # Check for unbalanced braces
        if cmd_args.count('{') != cmd_args.count('}'):
            validation_errors.append("Contains unbalanced braces")

        if empty_params := re.findall(r'(\w+)=\s*(?=\s|\}|$)', cmd_args):
            validation_errors.append(f"Contains empty parameters: {empty_params}")

        # Check for malformed placeholders
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
            return False

        return True