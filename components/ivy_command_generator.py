"""Ivy command generation functionality - restored from original implementation."""
import os
import re
from typing import Dict, List, Optional
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from panther.core.command_processor.command_utils import CommandUtils
from panther.core.command_processor.command import ShellCommand
from panther.plugins.services.base.service_command_builder import ServiceCommandBuilder

# Variable assignment prefixes that need special handling in templates
VARIABLE_ASSIGNMENT_PREFIXES = [
    "TARGET_IP=",
    "TARGET_IP_DEC=", 
    "TARGET_IP_HEX=",
    "IVY_IP=",
    "IVY_IP_DEC=",
    "IVY_IP_HEX=",
    "export "
]


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"


class IvyCommandGenerator(ErrorHandlerMixin):
    """
    Handles all Ivy command generation with complete functionality from original implementation.
    
    This class restores the full command generation logic including IP resolution,
    environment setup, Ivy tool updates, library management, and template-based
    deployment command generation.
    """
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        
    def generate_pre_compile_commands(self) -> Dict[str, List[ShellCommand]]:
        """
        Generate pre-compilation commands with full IP resolution and environment setup.
        
        This restores the original complex logic for hostname resolution, environment
        variable persistence, and conditional setup based on service role.
        
        Returns:
            Dictionary with 'pre_compile_cmds' key containing list of ShellCommand objects
        """
        commands = []
        
        try:
            # Initialize environment file
            commands.append("echo '# Ivy environment variables' > /app/logs/ivy_env.sh")
            
            # Get service information
            service_targets = getattr(self.service_manager, 'service_targets', None)
            service_name = getattr(self.service_manager, 'service_name', 'ivy_service')
            
            # IP Resolution Logic - Only resolve target if we have one (clients have targets, servers don't)
            if service_targets:
                # Structured commands for target IP resolution - Jinja template safe
                # Use single $ as Jinja will pass it through correctly
                commands.extend([
                    f"TARGET_IP=$(resolve_hostname {service_targets})",
                    f"TARGET_IP_DEC=$(resolve_hostname {service_targets} decimal)",
                    f"TARGET_IP_HEX=$(resolve_hostname {service_targets} hex)",
                    "echo \"export TARGET_IP='$TARGET_IP'\" >> /app/logs/ivy_env.sh",
                    "echo \"export TARGET_IP_DEC='$TARGET_IP_DEC'\" >> /app/logs/ivy_env.sh", 
                    "echo \"export TARGET_IP_HEX='$TARGET_IP_HEX'\" >> /app/logs/ivy_env.sh",
                    "export TARGET_IP TARGET_IP_DEC TARGET_IP_HEX",
                    f"echo \"Resolved {service_targets} to IP: $TARGET_IP (decimal: $TARGET_IP_DEC, hex: $TARGET_IP_HEX)\" >> /app/logs/ivy_setup.log"
                ])
            else:
                # For servers, use placeholder values - Jinja template safe
                # Use double $$ to escape shell variables from Jinja interpretation  
                commands.extend([
                    "export TARGET_IP='null'",
                    "export TARGET_IP_DEC='null'", 
                    "export TARGET_IP_HEX='null'",
                    "echo \"export TARGET_IP='null'\" >> /app/logs/ivy_env.sh",
                    "echo \"export TARGET_IP_DEC='null'\" >> /app/logs/ivy_env.sh",
                    "echo \"export TARGET_IP_HEX='null'\" >> /app/logs/ivy_env.sh",
                    "echo \"Server mode: target IP will be determined at runtime\" >> /app/logs/ivy_setup.log"
                ])
            
            # Always get local IVY IP - structured commands for template safety
            # Use single $ as Jinja will pass it through correctly
            commands.extend([
                f"IVY_IP=$(resolve_hostname {service_name})",
                f"IVY_IP_DEC=$(resolve_hostname {service_name} decimal)", 
                f"IVY_IP_HEX=$(resolve_hostname {service_name} hex)",
                "echo \"export IVY_IP='$IVY_IP'\" >> /app/logs/ivy_env.sh",
                "echo \"export IVY_IP_DEC='$IVY_IP_DEC'\" >> /app/logs/ivy_env.sh",
                "echo \"export IVY_IP_HEX='$IVY_IP_HEX'\" >> /app/logs/ivy_env.sh", 
                "export IVY_IP IVY_IP_DEC IVY_IP_HEX",
                f"echo \"Local {service_name} IP: $IVY_IP (decimal: $IVY_IP_DEC, hex: $IVY_IP_HEX)\" >> /app/logs/ivy_setup.log"
            ])
            
            # Add clean build directory command with proper path quoting
            use_system_models = getattr(self.service_manager, 'use_system_models', False)
            if use_system_models:
                commands.append("rm -rf '/opt/panther_ivy/protocol-testing/apt/build/'*")
            else:
                protocol_name = self._get_protocol_name()
                commands.append(f"rm -rf '/opt/panther_ivy/protocol-testing/{protocol_name}/build/'*")
            
            # Use smart command logging
            CommandUtils.log_command_generation(self.logger, "pre-compile", commands)
            
            # Return plain strings - the main class will handle ShellCommand conversion if needed
            return {
                "pre_compile_cmds": commands
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate pre-compile commands: {e}")
            raise
    
    def generate_compile_commands(self) -> Dict[str, List[ShellCommand]]:
        """
        Generate compilation commands with complete Ivy tool updates and library management.
        
        This restores the original comprehensive compilation logic including Ivy tool
        installation, library copying, QUIC setup, and actual test compilation.
        
        Returns:
            Dictionary with 'compile_cmds' key containing list of ShellCommand objects
        """
        commands = []
        
        try:
            # Emit command generation started event (if available)
            if hasattr(self.service_manager, 'emit_command_generation_started'):
                self.service_manager.emit_command_generation_started("compile")
            
            # Build comprehensive compilation commands
            compilation_commands = self._generate_comprehensive_compilation_commands()
            commands.extend(compilation_commands)
            
            # Notify compilation started (if available)
            if hasattr(self.service_manager, 'notify_service_event'):
                protocol_name = self._get_protocol_name()
                test_to_compile = getattr(self.service_manager, 'test_to_compile', 'unknown_test')
                self.service_manager.notify_service_event(
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
            if hasattr(self.service_manager, 'emit_command_generated'):
                self.service_manager.emit_command_generated("compile", str(commands))
            
            # Use smart command logging
            CommandUtils.log_command_generation(self.logger, "compile", commands)
            
            # Return plain strings - the main class will handle ShellCommand conversion if needed
            return {
                "compile_cmds": commands
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate compile commands: {e}")
            raise
    
    def generate_run_command(self, **kwargs) -> str:
        """
        Generate the run command for Ivy test execution.
        
        This method generates the actual executable command string for running
        the compiled Ivy test binary with the appropriate arguments.
        
        Args:
            **kwargs: Optional parameters including timeout, protocol, test_name, role
            
        Returns:
            str: The complete run command string
        """
        try:
            # Get parameters from kwargs or service manager
            timeout = kwargs.get('timeout', None)
            protocol = kwargs.get('protocol', self._get_protocol_name())
            test_name = kwargs.get('test_name', getattr(self.service_manager, 'test_to_compile', 'test_binary'))
            role = kwargs.get('role', getattr(self.service_manager, 'role', None))
            
            # Get service configuration
            service_config = getattr(self.service_manager, 'service_config_to_test', None)
            if not timeout and service_config:
                timeout = getattr(service_config, 'timeout', 120)
            
            # Get working directory
            env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
            if env_protocol_model_path:
                working_dir = env_protocol_model_path
            else:
                working_dir = f"/opt/panther_ivy/protocol-testing/{protocol}/"
            
            # Get build directory
            tests_build_dir = "build"
            if service_config and hasattr(service_config, 'implementation'):
                impl_params = getattr(service_config.implementation, 'parameters', None)
                if impl_params and hasattr(impl_params, 'tests_build_dir'):
                    if hasattr(impl_params.tests_build_dir, 'value'):
                        tests_build_dir = impl_params.tests_build_dir.value
                    else:
                        tests_build_dir = str(impl_params.tests_build_dir)
            
            # Construct the command
            binary_path = f"{working_dir}/{tests_build_dir}/{test_name}"
            
            # Generate deployment arguments
            deployment_args = self.generate_deployment_commands(**kwargs)
            
            # Build the complete command
            if timeout:
                command = f"timeout {timeout} {binary_path} {deployment_args}".strip()
            else:
                command = f"{binary_path} {deployment_args}".strip()
            
            self.logger.debug(f"Generated run command: {command}")
            return command
            
        except Exception as e:
            self.logger.error(f"Failed to generate run command: {e}")
            # Return a basic fallback command
            return f"./test_binary"

    def generate_deployment_commands(self, **kwargs) -> str:
        """
        Generate deployment command arguments for Ivy test execution.
        
        This restores the original template-based parameter generation logic that
        creates complex command argument strings based on role and configuration.
        """
        try:
            self.logger.debug(f"Generating deployment commands for service: {getattr(self.service_manager, 'service_name', 'unknown')}")
            
            # Get role from service manager
            role = getattr(self.service_manager, 'role', None)
            if not role:
                self.logger.warning("No role found in service manager")
                return ""
            
            # Get service configuration
            service_config = getattr(self.service_manager, 'service_config_to_test', None)
            if not service_config:
                self.logger.warning("No service configuration found")
                return ""
            
            # Get role-specific parameters
            params = {}
            if hasattr(role, 'name'):
                role_name = role.name
            else:
                role_name = str(role)
                
            if role_name == "server":
                # Get server parameters if available
                if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'version'):
                    if hasattr(service_config.implementation.version, 'server'):
                        params.update(service_config.implementation.version.server or {})
            else:
                # Get client parameters if available
                if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'version'):
                    if hasattr(service_config.implementation.version, 'client'):
                        params.update(service_config.implementation.version.client or {})
            
            # Add additional parameters from implementation
            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'parameters'):
                impl_params = service_config.implementation.parameters
                if hasattr(impl_params, '__dict__'):
                    for param_name, param_obj in impl_params.__dict__.items():
                        if hasattr(param_obj, 'value'):
                            params[param_name] = param_obj.value
                        else:
                            params[param_name] = param_obj
            
            # Add version parameters if available
            if hasattr(service_config, 'implementation') and hasattr(service_config.implementation, 'version'):
                version_params = getattr(service_config.implementation.version, 'parameters', {})
                if hasattr(version_params, '__dict__'):
                    for param_name, param_obj in version_params.__dict__.items():
                        if hasattr(param_obj, 'value'):
                            params[param_name] = param_obj.value
                        else:
                            params[param_name] = param_obj
                elif isinstance(version_params, dict):
                    for param_name, param_data in version_params.items():
                        if isinstance(param_data, dict) and 'value' in param_data:
                            params[param_name] = param_data['value']
                        else:
                            params[param_name] = param_data
            
            # Set network parameters (Ivy uses decimal IP representation)
            # Use single $ as Jinja will pass it through correctly
            if hasattr(service_config, 'protocol') and hasattr(service_config.protocol, 'target'):
                params["target"] = service_config.protocol.target
            else:
                params["target"] = None
                
            params["server_addr"] = (
                "$TARGET_IP_DEC" if oppose_role(role_name) == "server" else "$IVY_IP_DEC"
            )
            params["client_addr"] = (
                "$TARGET_IP_DEC" if oppose_role(role_name) == "client" else "$IVY_IP_DEC"
            )
            params["is_client"] = oppose_role(role_name) == "client"
            
            # Set test information
            test_to_compile = getattr(self.service_manager, 'test_to_compile', None)
            params["test_name"] = test_to_compile
            
            # Set timeout command
            timeout = getattr(service_config, 'timeout', 120)
            params["timeout_cmd"] = f"timeout {timeout} "
            
            # Set working directory
            env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
            if env_protocol_model_path:
                working_dir = env_protocol_model_path
            else:
                working_dir = f"/opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/"
            
            # Remove network interface if not needed
            if "network" in params and isinstance(params["network"], dict):
                params["network"].pop("interface", None)
            
            # Log params for debugging
            self.logger.debug(f"Template params: {params}")
            
            # Use template rendering to generate arguments
            try:
                # Use the same template as the old version
                template_name = f"{oppose_role(role_name)}_command.jinja"
                
                # Get template renderer from service manager
                template_renderer = getattr(self.service_manager, 'template_renderer', None)
                if template_renderer:
                    cmd_args = template_renderer.render_template(template_name, params)
                    
                    # The template returns the command arguments string
                    # For Ivy, this is parameters like "seed=X the_cid=Y server_port=Z ..."
                    if cmd_args:
                        self.logger.debug(f"Generated command args from template: {cmd_args.strip()}")
                        return cmd_args.strip()
                    else:
                        self.logger.warning("No command arguments generated from template")
                        return ""
                else:
                    self.logger.warning("No template renderer available")
                    # Fall through to manual construction
                    
            except Exception as e:
                self.logger.warning(f"Failed to render command template: {e}")
                # Fall through to fallback logic
            
            # Fallback to constructing basic arguments manually
            # Return structured command data for template safety
            args = []
            if "seed" in params:
                args.append(f"seed={params['seed']}")
            else:
                args.append("seed=1")  # Default seed
                
            if "server_addr" in params:
                args.append(f"server_addr={params['server_addr']}")
            if "client_addr" in params:
                args.append(f"client_addr={params['client_addr']}")
            if "server_port" in params:
                args.append(f"server_port={params.get('server_port', 4443)}")
            else:
                args.append("server_port=4443")  # Default port
                
            # Add default QUIC parameters if not present
            if "the_cid" not in params:
                args.append("the_cid=1")
            if "iversion" not in params:
                args.append("iversion=1")
            
            # Return space-separated string but ensure it's template-safe
            command_args = " ".join(args)
            self.logger.debug(f"Generated fallback command args: {command_args}")
            return command_args
            
        except Exception as e:
            self.logger.error(f"Failed to generate deployment commands: {e}")
            return "seed=1 server_port=4443"  # Minimal fallback
    
    def generate_post_run_commands(self) -> Dict[str, List[ShellCommand]]:
        """Generate post-run cleanup commands (restored from original).
        
        Returns:
            Dictionary with 'post_run_cmds' key containing list of ShellCommand objects
        """
        commands = []
        
        try:
            # Get test information
            test_to_compile = getattr(self.service_manager, 'test_to_compile', None)
            env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
            
            if test_to_compile and env_protocol_model_path:
                # Get build directory path
                service_config = getattr(self.service_manager, 'service_config_to_test', None)
                tests_build_dir = "build"  # Default
                
                if service_config and hasattr(service_config, 'implementation'):
                    impl_params = getattr(service_config.implementation, 'parameters', None)
                    if impl_params and hasattr(impl_params, 'tests_build_dir'):
                        if hasattr(impl_params.tests_build_dir, 'value'):
                            tests_build_dir = impl_params.tests_build_dir.value
                        else:
                            tests_build_dir = str(impl_params.tests_build_dir)
                
                # Copy test binary and cleanup with proper path quoting for template safety
                test_path = os.path.join(env_protocol_model_path, tests_build_dir, test_to_compile)
                commands.extend([
                    f"cp '{test_path}' '/app/logs/{test_to_compile}'",
                    f"rm '{test_path}'*"
                ])
            
            # Use smart command logging
            CommandUtils.log_command_generation(self.logger, "post-run", commands)
            
            # Return plain strings - the main class will handle ShellCommand conversion if needed
            return {
                "post_run_cmds": commands
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate post-run commands: {e}")
            # Return empty command list in expected structure
            return {
                "post_run_cmds": []
            }
    
    def _generate_comprehensive_compilation_commands(self) -> List[str]:
        """Generate comprehensive compilation commands (restored from original)."""
        self.logger.debug(f"Generating compilation commands for service: {getattr(self.service_manager, 'service_name', 'unknown')}")
        
        # Set up environments
        service_config = getattr(self.service_manager, 'service_config_to_test', None)
        if not service_config:
            return []
            
        # Get environment configurations
        protocol_env = {}
        
        if hasattr(service_config, 'implementation'):
            if hasattr(service_config.implementation, 'version') and hasattr(service_config.implementation.version, 'env'):
                protocol_env = service_config.implementation.version.env or {}
        
        # Adjust protocol environment for non-system models
        use_system_models = getattr(service_config.implementation, 'use_system_models', False) if hasattr(service_config, 'implementation') else False
        if not use_system_models:
            for key in protocol_env:
                if isinstance(protocol_env[key], str):
                    protocol_env[key] = protocol_env[key].replace("/apt/apt_protocols", "")
        
        # Note: environments and role were extracted here in original but not used
        # The environment variables are handled through shell export commands instead
        
        # Set test path
        test_to_compile = getattr(self.service_manager, 'test_to_compile', None)
        self.logger.info(f"Setting test path to: {test_to_compile}")
        
        # Build Ivy tool update commands
        update_commands = self._build_comprehensive_ivy_update_commands()
        
        # Build test compilation commands
        test_commands = self._build_test_compilation_commands(test_to_compile)
        
        return update_commands + test_commands
    
    def _build_comprehensive_ivy_update_commands(self) -> List[str]:
        """Build comprehensive Ivy tool update commands (restored from original)."""
        commands = []
        
        # Update Ivy tool
        commands.extend([
            "echo 'Updating Ivy tool...' >> /app/logs/ivy_setup.log",
            "cd /opt/panther_ivy && sudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1",
            "cd /opt/panther_ivy && cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 || true",
        ])
        
        # Copy Ivy files with proper path quoting for template safety
        commands.extend([
            "echo 'Copying updated Ivy files...' >> /app/logs/ivy_setup.log",
            "find '/opt/panther_ivy/ivy/include/1.7/' -type f -name '*.ivy' -exec cp {} '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' \\; >> /app/logs/ivy_setup.log 2>&1",
        ])
        
        # Protocol-specific setup
        protocol_name = self._get_protocol_name()
        if protocol_name in ["quic", "apt"]:
            commands.extend(self._build_comprehensive_quic_setup_commands())
        
        # Set up Ivy model
        commands.extend(self._build_ivy_model_setup_commands())
        
        return commands
    
    def _build_comprehensive_quic_setup_commands(self) -> List[str]:
        """Build comprehensive QUIC-specific setup commands with proper path quoting."""
        commands = [
            "echo 'Copying QUIC libraries...' >> /app/logs/ivy_setup.log",
            "cp -f -a '/opt/picotls/'*.a '/usr/local/lib/python3.10/dist-packages/ivy/lib/'",
            "cp -f -a '/opt/picotls/'*.a '/opt/panther_ivy/ivy/lib/'",
            "cp -f '/opt/picotls/include/picotls.h' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls.h'",
            "cp -f '/opt/picotls/include/picotls.h' '/opt/panther_ivy/ivy/include/picotls.h'",
            "cp -r -f '/opt/picotls/include/picotls/.' '/usr/local/lib/python3.10/dist-packages/ivy/include/picotls'",
        ]
        
        # Add quic_ser_deser.h copy
        service_config = getattr(self.service_manager, 'service_config_to_test', None)
        use_system_models = False
        if service_config and hasattr(service_config, 'implementation'):
            use_system_models = getattr(service_config.implementation, 'use_system_models', False)
        
        env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
        if env_protocol_model_path:
            if use_system_models:
                quic_ser_deser_path = f"{env_protocol_model_path}/apt_protocols/quic/quic_utils/quic_ser_deser.h"
            else:
                quic_ser_deser_path = f"{env_protocol_model_path}/quic_utils/quic_ser_deser.h"
            
            commands.append(
                f"cp -f '{quic_ser_deser_path}' '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/'"
            )
        
        return commands
    
    def _build_ivy_model_setup_commands(self) -> List[str]:
        """Build Ivy model setup commands (restored from original)."""
        env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
        if not env_protocol_model_path:
            return []
            
        commands = [
            "echo 'Setting up Ivy model...' >> /app/logs/ivy_setup.log",
            f"echo 'Updating include path from {env_protocol_model_path}' >> /app/logs/ivy_setup.log",
            # Use string concatenation to avoid f-string issues with {}
            "find '" + env_protocol_model_path + "' -type f -name '*.ivy' -exec cp -f {} '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' \\;",
            "ls -l '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/' >> /app/logs/ivy_setup.log",
        ]
        
        return commands
    
    def _build_test_compilation_commands(self, test_name: Optional[str] = None) -> List[str]:
        """Build test compilation commands (restored from original)."""
        if not test_name:
            test_name = getattr(self.service_manager, 'test_to_compile', None)
        
        if not test_name:
            self.logger.warning("No test name specified for compilation")
            return []
        
        self.logger.info("Compiling tests...")
        
        # Determine file path
        service_config = getattr(self.service_manager, 'service_config_to_test', None)
        use_system_models = False
        if service_config and hasattr(service_config, 'implementation'):
            use_system_models = getattr(service_config.implementation, 'use_system_models', False)
        
        if use_system_models:
            base_path = "/opt/panther_ivy/protocol-testing/apt/"
        else:
            env_protocol_model_path = getattr(self.service_manager, 'env_protocol_model_path', None)
            if env_protocol_model_path:
                base_path = env_protocol_model_path
            else:
                base_path = f"/opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/"
        
        # Get tests directory
        tests_dir = "tests"  # Default
        if service_config and hasattr(service_config, 'implementation'):
            version = getattr(service_config.implementation, 'version', None)
            if version and hasattr(version, 'parameters'):
                version_params = version.parameters
                if isinstance(version_params, dict) and "tests_dir" in version_params:
                    tests_dir_info = version_params["tests_dir"]
                    if isinstance(tests_dir_info, dict) and "value" in tests_dir_info:
                        tests_dir = tests_dir_info["value"]
        
        # Get role information
        role = getattr(self.service_manager, 'role', None)
        role_name = role.name if hasattr(role, 'name') else str(role) if role else 'unknown'
        
        file_path = os.path.join(base_path, tests_dir, f"{oppose_role(role_name)}_tests")
        
        # Log the path we're trying to use for debugging
        self.logger.info(f"Attempting to compile test in directory: {file_path}")
        self.logger.info(f"Role: {role_name}, Oppose role: {oppose_role(role_name)}, Test: {test_name}")
        
        # Safety check - if the oppose_role directory doesn't exist, try the same role directory
        if not os.path.exists(file_path):
            alternative_path = os.path.join(base_path, tests_dir, f"{role_name}_tests")
            self.logger.warning(f"Directory {file_path} doesn't exist, trying {alternative_path}")
            if os.path.exists(alternative_path):
                file_path = alternative_path
                self.logger.info(f"Using alternative path: {file_path}")
            else:
                self.logger.error(f"Neither {file_path} nor {alternative_path} exist")
                # List available directories for debugging
                try:
                    tests_base = os.path.join(base_path, tests_dir)
                    if os.path.exists(tests_base):
                        available_dirs = [d for d in os.listdir(tests_base) if os.path.isdir(os.path.join(tests_base, d))]
                        self.logger.info(f"Available directories in {tests_base}: {available_dirs}")
                    else:
                        self.logger.error(f"Tests base directory {tests_base} doesn't exist")
                except Exception as e:
                    self.logger.error(f"Failed to list directories: {e}")
        
        # Get internal iterations parameter
        internal_iterations = 1  # Default
        if service_config and hasattr(service_config, 'implementation'):
            impl_params = getattr(service_config.implementation, 'parameters', None)
            if impl_params and hasattr(impl_params, 'internal_iterations_per_test'):
                if hasattr(impl_params.internal_iterations_per_test, 'value'):
                    internal_iterations = impl_params.internal_iterations_per_test.value
                else:
                    internal_iterations = impl_params.internal_iterations_per_test
        
        # Build compilation command
        compile_cmd = (
            f"cd '{file_path}' ; "
            f"PYTHONPATH=$PYTHON_IVY_DIR ivyc trace=false show_compiled=false "
            f"target=test test_iters={internal_iterations} "
            f"{test_name}.ivy >> /app/logs/ivy_setup.log 2>&1 || exit 1"
        )
        
        # Build directory and copy commands
        tests_build_dir = "build"  # Default
        if service_config and hasattr(service_config, 'implementation'):
            impl_params = getattr(service_config.implementation, 'parameters', None)
            if impl_params and hasattr(impl_params, 'tests_build_dir'):
                if hasattr(impl_params.tests_build_dir, 'value'):
                    tests_build_dir = impl_params.tests_build_dir.value
                else:
                    tests_build_dir = str(impl_params.tests_build_dir)
        
        build_dir = os.path.join(base_path, tests_build_dir)
        
        commands = [
            compile_cmd,
            "ls >> /app/logs/ivy_setup.log 2>&1",
            f"mkdir -p '{build_dir}'",
            f"cp '{os.path.join(file_path, test_name)}'* '{build_dir}'",
            f"ls '{build_dir}' >> /app/logs/ivy_setup.log 2>&1",
        ]
        
        return commands
    
    def _get_protocol_name(self) -> str:
        """Get the protocol name safely."""
        # Try multiple ways to get protocol name
        service_manager = self.service_manager
        
        # Try protocol_config first
        protocol_config = getattr(service_manager, 'protocol_config', None)
        if protocol_config and hasattr(protocol_config, 'name'):
            return str(protocol_config.name).lower()
        
        # Try protocol attribute
        protocol = getattr(service_manager, 'protocol', None)
        if protocol and hasattr(protocol, 'name'):
            return str(protocol.name).lower()
        elif isinstance(protocol, str):
            return protocol.lower()
        
        # Try service config protocol
        service_config = getattr(service_manager, 'service_config_to_test', None)
        if service_config and hasattr(service_config, 'protocol'):
            protocol = service_config.protocol
            if hasattr(protocol, 'name'):
                return str(protocol.name).lower()
            elif isinstance(protocol, str):
                return protocol.lower()
        
        return "quic"  # Default protocol
    
    def _sanitize_command(self, command: str) -> str:
        """Sanitize a command for safe execution."""
        
        # Remove any dangerous patterns
        dangerous_patterns = [
            r'rm\s+-rf\s+/',  # rm -rf /
            r';\s*rm\s+',     # ; rm
            r'\$\([^)]*[;&|][^)]*\)',  # Command substitution with dangerous chars
            r'`[^`]*`',       # Backticks
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                self.logger.error(f"Dangerous pattern detected in command: {command}")
                raise ValueError(f"Command contains dangerous pattern: {pattern}")
        
        # Basic sanitization
        command = command.strip()
        
        # Ensure command doesn't contain null bytes
        if '\x00' in command:
            raise ValueError("Command contains null bytes")
        
        return command