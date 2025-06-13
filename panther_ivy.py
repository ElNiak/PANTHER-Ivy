from pathlib import Path
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from panther.core.exceptions.InvalidCommandFormatError import InvalidCommandFormatError
from panther.plugins.services.testers.panther_ivy.config_schema import PantherIvyConfig
from panther.plugins.services.testers.tester_interface import ITesterManager
from panther.plugins.protocols.config_schema import ProtocolConfig, RoleEnum
from panther.core.events import BaseEvent
from panther.plugins.plugin_decorators import register_plugin
from panther.core.utils.service_manager_utils import TesterServiceManagerMixin
from panther.core.utils import (
    ServiceCommandBuilder,
    ServiceTemplateRenderer,
    ServiceManagerDockerMixin,
    ErrorHandlerMixin
)
import os
import subprocess
import traceback
import re
import time

if TYPE_CHECKING:
    from panther.plugins.plugin_manager import PluginManager


def is_func_def(command_entry: dict) -> bool:
    """
    Helper function to check if a command entry is a function definition.

    Args:
        command_entry (dict): The command entry to check

    Returns:
        bool: True if the command entry is a function definition, False otherwise

    Raises:
        InvalidCommandFormatError: If is_function_definition is missing or not a boolean
    """
    try:
        if "is_function_definition" not in command_entry:
            raise InvalidCommandFormatError(
                f"Missing is_function_definition flag in command: {command_entry}"
            )
        if not isinstance(command_entry["is_function_definition"], bool):
            raise InvalidCommandFormatError(
                f"is_function_definition must be a bool, got {type(command_entry['is_function_definition']).__name__} for command: {command_entry}"
            )
        return bool(command_entry["is_function_definition"])
    except KeyError as exc:
        raise InvalidCommandFormatError(
            f"Missing is_function_definition flag in command: {command_entry}"
        ) from exc


def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    return "client" if role == "server" else "server"


@register_plugin(
    plugin_type="tester",
    name="panther_ivy",
    version="1.0.0",
    description="Formal verification tester using Ivy specification language",
    author="PANTHER Team",
    dependencies=["ivy_compiler"],
    supported_protocols=["quic"],
    capabilities=["formal_verification", "protocol_compliance", "symbolic_execution", "invariant_checking"],
    external_dependencies=["z3>=4.8", "python>=3.7"]
)
class PantherIvyServiceManager(
    TesterServiceManagerMixin,
    ServiceManagerDockerMixin,
    ErrorHandlerMixin,
    ITesterManager
):
    """
    Manages the Ivy testers service for the Panther project.

    This class is responsible for configuring, preparing, compiling, and running Ivy tests
    for a given protocol implementation. It interacts with Docker, manages environment
    variables, and handles the setup of necessary directories and files.
    """
    
    def __init__(
        self,
        service_config_to_test: PantherIvyConfig,
        service_type: str,
        protocol: ProtocolConfig,
        implementation_name: str,
        event_manager=None,
    ):
        super().__init__(
            service_config_to_test, service_type, protocol, implementation_name, event_manager
        )
        
        # Use standardized initialization from mixin
        self.standardized_initialization(
            service_config_to_test, service_type, protocol, implementation_name, event_manager
        )
        
        # Set up tester-specific attributes
        self.setup_tester_specific_attributes(service_config_to_test)
        
        # Initialize template renderer
        plugin_dir = Path(__file__).parent
        self.template_renderer = ServiceTemplateRenderer(plugin_dir, protocol.name)

        # Set Docker attributes for ServiceManagerDockerMixin
        self.docker_image_name = f"panther_ivy:latest"
        self.docker_file_path = plugin_dir / "Dockerfile"
        
        # Initialize Ivy-specific attributes
        self._initialize_ivy_attributes(service_config_to_test, protocol)

        # Ivy-specific setup after Docker builds are complete
        self._setup_volumes()

    def _initialize_ivy_attributes(self, service_config_to_test: PantherIvyConfig, protocol: ProtocolConfig):
        """Initialize Ivy-specific attributes."""
        # Set test configuration
        self.test_to_compile = service_config_to_test.implementation.test
        self.test_to_compile_path = None
        
        # Initialize available_tests based on role
        if hasattr(self, "role") and self.role == RoleEnum.server:
            self.available_tests = service_config_to_test.implementation.version.server.get("tests", {})
        else:
            self.available_tests = service_config_to_test.implementation.version.client.get("tests", {})
        
        if self.available_tests is None:
            self.available_tests = {}
        
        # Set protocol model paths
        self.protocol = protocol
        self._protocol_name_cache = None
        
        if service_config_to_test.implementation.use_system_models:
            self.env_protocol_model_path = "/opt/panther_ivy/protocol-testing/apt/"
            self.protocol_model_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "protocol-testing", "apt")
            )
        else:
            self.env_protocol_model_path = (
                "/opt/panther_ivy/protocol-testing/" + self._get_protocol_name() + "/"
            )
            self.protocol_model_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "protocol-testing", self._get_protocol_name())
            )
        
        self.ivy_log_level = service_config_to_test.implementation.parameters.log_level
        
        # Ensure directories_to_start is empty list
        service_config_to_test.directories_to_start = []

    def generate_pre_compile_commands(self):
        """Generates pre-compile commands using the new chain architecture."""
        # Get base commands from parent
        base_commands = super().generate_pre_compile_commands()
        
        # Use the new chain architecture: CommandBuilder -> CommandProcessor
        builder = ServiceCommandBuilder(self.role)
        
        # Simple string commands (CommandProcessor will analyze and categorize)
        # Use the enhanced resolve_hostname function from entrypoint template
        commands = []
        
        # Only resolve target if we have one (clients have targets, servers don't)
        if self.service_targets:
            commands.extend([
                # Resolve target hostname to IP, decimal and hex formats
                f"TARGET_IP=$(resolve_hostname {self.service_targets})",
                f"TARGET_IP_DEC=$(resolve_hostname {self.service_targets} decimal)",
                f"TARGET_IP_HEX=$(resolve_hostname {self.service_targets} hex)",
                f'echo "Resolved {self.service_targets} to IP: $TARGET_IP (decimal: $TARGET_IP_DEC, hex: $TARGET_IP_HEX)" >> /app/logs/ivy_setup.log',
            ])
        else:
            # For servers, we'll use a placeholder that will be resolved later
            commands.extend([
                "TARGET_IP=null",
                "TARGET_IP_DEC=null",
                "TARGET_IP_HEX=null",
                'echo "Server mode: target IP will be determined at runtime" >> /app/logs/ivy_setup.log',
            ])
        
        # Always get local IVY IP
        # First try to get non-loopback IP, if none found, use loopback
        commands.extend([
            "IVY_IP=$(hostname -i | grep -v '^127' | head -n 1)",
            # Use resolve_hostname function which handles decimal and hex conversion properly
            'IVY_IP_DEC=$(resolve_hostname "$IVY_IP" decimal)',
            'IVY_IP_HEX=$(resolve_hostname "$IVY_IP" hex)',
            f'echo "Local {self.service_name} IP: $IVY_IP (decimal: $IVY_IP_DEC, hex: $IVY_IP_HEX)" >> /app/logs/ivy_setup.log',
        ])
        
        # Add clean build directory command
        if self.service_config_to_test.implementation.use_system_models:
            commands.append("rm -rf /opt/panther_ivy/protocol-testing/apt/build/*")
        else:
            commands.append(f"rm -rf /opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/build/*")
        
        # Add simple commands to builder
        for cmd in commands:
            builder.add_command(cmd)
        
        # Use the chain: builder -> process -> return processed commands
        processed_commands = builder.process_commands("panther_ivy")
        
        return base_commands + processed_commands

    # Note: _add_utility_functions_to_builder is no longer needed
    # Function definitions are now handled directly in generate_pre_compile_commands
    # using the CommandBuilder -> CommandProcessor chain which automatically
    # detects function definitions, multiline commands, etc.

    def generate_compile_commands(self):
        """Generates compile commands."""
        # Emit command generation started event
        self.emit_command_generation_started("compile")
        
        base_commands = super().generate_compile_commands()
        compilation_commands = self.generate_compilation_commands()
        
        # Notify compilation started
        self.notify_service_event("compilation_started", {
            "protocol": self.protocol.name if hasattr(self.protocol, 'name') else str(self.protocol),
            "test": self.test_to_compile
        })
        
        # Add ready file creation
        if compilation_commands:
            compilation_commands.append("touch /app/sync_logs/ivy_ready.log")
        else:
            compilation_commands = ["touch /app/sync_logs/ivy_ready.log"]
        
        # Emit command generated event
        self.emit_command_generated("compile", str(compilation_commands))
        
        return base_commands + compilation_commands

    def generate_post_compile_commands(self):
        """Generates post-compile commands using the new chain architecture."""
        base_commands = super().generate_post_compile_commands()
        
        # Use simple string commands - CommandProcessor will handle the rest
        additional_commands = [
            f"cd {self.env_protocol_model_path}",  # Removed semicolon - CommandProcessor handles this
            "pwd >> /app/logs/ivy_post_compile.log",  # Add some logging for debugging
        ]
        
        return base_commands + additional_commands

    def generate_run_command(self):
        """Generates the run command using structured command building."""
        # Emit command generation started
        self.emit_command_generation_started("run")
        
        # Get deployment commands
        cmd_args = self.generate_deployment_commands()
        
        # Notify test execution started
        self.notify_service_event("test_execution_started", {
            "test_name": self.test_to_compile,
            "protocol": self._get_protocol_name()
        })
        
        # Build command binary path
        command_binary = ""
        if self.test_to_compile:
            command_binary = os.path.join(
                self.service_config_to_test.implementation.parameters.tests_build_dir.value,
                self.test_to_compile
            )
            command_binary = "./" + command_binary
        
        # Ensure working directory is set
        working_dir = self.env_protocol_model_path or f"/opt/panther_ivy/protocol-testing/{self._get_protocol_name()}/"
        
        run_command = {
            "working_dir": working_dir,
            "command_binary": command_binary,
            "command_args": cmd_args if cmd_args else [],
            "timeout": self.service_config_to_test.timeout,
            "environment": {},
        }
        
        # Debug logging
        self.logger.info("Run command structure: binary='%s', args='%s'", command_binary, cmd_args)
        
        # Emit command generated
        self.emit_command_generated("run", str(run_command))
        
        return run_command

    def generate_post_run_commands(self):
        """Generates post-run commands."""
        commands = super().generate_post_run_commands()
        
        # Add Ivy-specific post-run commands
        test_path = os.path.join(
            self.env_protocol_model_path,
            self.service_config_to_test.implementation.parameters.tests_build_dir.value,
            self.test_to_compile
        )
        
        commands.extend([
            f"cp {test_path} /app/logs/{self.test_to_compile}",
            f"rm {test_path}*"
        ])
        
        return commands

    def _do_prepare(self, plugin_manager: Optional["PluginManager"] = None):
        """
        Implementation of abstract _do_prepare method from IServiceManager.
        
        Performs Ivy-specific preparation steps that work with the mixins.
        
        Args:
            plugin_manager: Optional plugin manager for Docker operations
        """
        try:
            # Build submodules if needed
            if getattr(self.service_config_to_test, "build_submodules", False):
                self.build_submodules()
            
            # Use enhanced mixin for Docker builds and command initialization
            # This is now properly delegated to ServiceManagerDockerMixin
            if hasattr(super(), 'prepare'):
                super().prepare(plugin_manager)
            
            return True
        except Exception as e:
            self.handle_error(e, "prepare PantherIvy service manager")
            return False

    def _setup_volumes(self):
        """Set up Docker volumes for Ivy."""
        ivy_include_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "ivy", "include", "1.7")
        )
        local_protocol_dir = self.protocol_model_path
        
        volumes = [
            f"{ivy_include_dir}:/opt/panther_ivy/ivy/include/1.7",
            f"{local_protocol_dir}:{self.env_protocol_model_path}",
            "shared_logs:/app/sync_logs"
        ]
        
        if hasattr(self, "volumes"):
            self.volumes.extend(volumes)
        else:
            self.volumes = volumes

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

    def generate_compilation_commands(self) -> List[str]:
        """Generates compilation commands using structured approach."""
        self.logger.debug("Generating compilation commands for service: %s", self.service_name)
        
        # Set up environments
        protocol_env = self.service_config_to_test.implementation.version.env
        if not self.service_config_to_test.implementation.use_system_models:
            for key in protocol_env:
                protocol_env[key] = protocol_env[key].replace("/apt/apt_protocols", "")
        
        global_env = self.service_config_to_test.implementation.environment
        self.environments = {
            **global_env,
            **protocol_env,
            "TEST_TYPE": ("client" if self.role.name == "server" else "server"),
        }
        
        # Set test path
        self.test_to_compile_path = self.test_to_compile
        self.logger.info("Setting test path to: %s", self.test_to_compile_path)
        
        # Build Ivy tool update commands
        update_commands = self._build_ivy_update_commands()
        
        # Build test compilation commands
        test_commands = self.build_tests()
        
        return update_commands + test_commands

    def _build_ivy_update_commands(self) -> List[str]:
        """Build Ivy tool update commands using structured approach."""
        commands = []
        
        # Update Ivy tool
        commands.extend([
            "echo 'Updating Ivy tool...' >> /app/logs/ivy_setup.log",
            "cd /opt/panther_ivy",
            "sudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1",
            "cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1"
        ])
        
        # Copy Ivy files
        commands.extend([
            "echo 'Copying updated Ivy files...' >> /app/logs/ivy_setup.log",
            "find /opt/panther_ivy/ivy/include/1.7/ -type f -name '*.ivy' -exec cp {} /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/ \\; >> /app/logs/ivy_setup.log 2>&1"
        ])
        
        # Protocol-specific setup
        if self.protocol.name in ["quic", "apt"]:
            commands.extend(self._build_quic_setup_commands())
        
        # Set up Ivy model
        commands.extend(self._build_ivy_model_setup_commands())
        
        return commands

    def _build_quic_setup_commands(self) -> List[str]:
        """Build QUIC-specific setup commands."""
        commands = [
            "echo 'Copying QUIC libraries...' >> /app/logs/ivy_setup.log",
            "cp -f -a /opt/picotls/*.a /usr/local/lib/python3.10/dist-packages/ivy/lib/",
            "cp -f -a /opt/picotls/*.a /opt/panther_ivy/ivy/lib/",
            "cp -f /opt/picotls/include/picotls.h /usr/local/lib/python3.10/dist-packages/ivy/include/picotls.h",
            "cp -f /opt/picotls/include/picotls.h /opt/panther_ivy/ivy/include/picotls.h",
            "cp -r -f /opt/picotls/include/picotls/. /usr/local/lib/python3.10/dist-packages/ivy/include/picotls"
        ]
        
        # Add quic_ser_deser.h copy
        if self.service_config_to_test.implementation.use_system_models:
            quic_ser_deser_path = f"{self.env_protocol_model_path}/apt_protocols/quic/quic_utils/quic_ser_deser.h"
        else:
            quic_ser_deser_path = f"{self.env_protocol_model_path}/quic_utils/quic_ser_deser.h"
        
        commands.append(
            f"cp -f {quic_ser_deser_path} /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/"
        )
        
        return commands

    def _build_ivy_model_setup_commands(self) -> List[str]:
        """Build Ivy model setup commands."""
        commands = [
            "echo 'Setting up Ivy model...' >> /app/logs/ivy_setup.log",
            f"echo 'Updating include path from {self.env_protocol_model_path}' >> /app/logs/ivy_setup.log",
            f"find {self.env_protocol_model_path} -type f -name '*.ivy' -exec cp -f {{}} /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/ \\;",
            "ls -l /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/ >> /app/logs/ivy_setup.log"
        ]
        
        return commands

    def build_tests(self, test_name=None) -> List[str]:
        """Builds test compilation commands."""
        self.logger.info("Compiling tests...")
        
        # Determine file path
        if self.service_config_to_test.implementation.use_system_models:
            base_path = "/opt/panther_ivy/protocol-testing/apt/"
        else:
            base_path = self.env_protocol_model_path
        
        tests_dir = self.service_config_to_test.implementation.version.parameters["tests_dir"]["value"]
        file_path = os.path.join(base_path, tests_dir, f"{oppose_role(self.role.name)}_tests")
        
        # Build compilation command
        test_to_compile = test_name or self.test_to_compile
        compile_cmd = (
            f"cd {file_path} ; "
            f"PYTHONPATH=$PYTHON_IVY_DIR ivyc trace=false show_compiled=false "
            f"target=test test_iters={self.service_config_to_test.implementation.parameters.internal_iterations_per_test.value} "
            f"{test_to_compile}.ivy >> /app/logs/ivy_setup.log 2>&1 || exit 1"
        )
        
        # Build directory and copy commands
        build_dir = os.path.join(base_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value)
        
        commands = [
            compile_cmd,
            "ls >> /app/logs/ivy_setup.log 2>&1",
            f"mkdir -p {build_dir}",
            f"cp {os.path.join(file_path, test_to_compile)}* {build_dir}",
            f"ls {build_dir} >> /app/logs/ivy_setup.log 2>&1"
        ]
        
        return commands

    def generate_deployment_commands(self) -> str:
        """Generates deployment command arguments for Ivy test execution."""
        self.logger.debug("Generating deployment commands for service: %s", self.service_name)
        
        # Get role-specific parameters
        if self.role == RoleEnum.server:
            params = self.service_config_to_test.implementation.version.server
        else:
            params = self.service_config_to_test.implementation.version.client
        
        # Add additional parameters
        for param in self.service_config_to_test.implementation.parameters:
            params[param] = self.service_config_to_test.implementation.parameters[param].value
        
        for param in self.service_config_to_test.implementation.version.parameters:
            params[param] = self.service_config_to_test.implementation.version.parameters[param].value
        
        # Set network parameters (Ivy uses decimal IP representation)
        params["target"] = self.service_config_to_test.protocol.target
        params["server_addr"] = "$TARGET_IP_DEC" if oppose_role(self.role.name) == "server" else "$IVY_IP_DEC"
        params["client_addr"] = "$TARGET_IP_DEC" if oppose_role(self.role.name) == "client" else "$IVY_IP_DEC"
        params["is_client"] = oppose_role(self.role.name) == "client"
        params["test_name"] = self.test_to_compile
        params["timeout_cmd"] = f"timeout {self.service_config_to_test.timeout} "
        
        self.working_dir = self.env_protocol_model_path
        
        # Remove network interface if not needed
        params.get("network", {}).pop("interface", None)
        
        # Log params for debugging
        self.logger.debug("Template params: %s", params)
        
        # Use the original command template to generate arguments
        try:
            # Use the same template as the old version
            template_name = f"{oppose_role(self.role.name)}_command.jinja"
            cmd_args = self.template_renderer.render_template(template_name, params)
            
            # The template returns the command arguments string
            # For Ivy, this is parameters like "seed=X the_cid=Y server_port=Z ..."
            if cmd_args:
                self.logger.debug("Generated command args from template: %s", cmd_args.strip())
                return cmd_args.strip()
            else:
                self.logger.warning("No command arguments generated from template")
                return ""
        except Exception as e:
            self.logger.warning("Failed to render command template: %s", e)
            # Fall back to constructing basic arguments
            args = []
            if "seed" in params:
                args.append(f"seed={params['seed']}")
            if "server_addr" in params:
                args.append(f"server_addr={params['server_addr']}")
            if "client_addr" in params:
                args.append(f"client_addr={params['client_addr']}")
            if "server_port" in params:
                args.append(f"server_port={params.get('server_port', 4443)}")
            return " ".join(args)

    def test_success(self) -> bool:
        """Register test success using standardized event notification."""
        self.logger.info("Checking for test success in %s", self.test_to_compile)
        
        # Notify test execution
        self.notify_service_event("test_execution_started", {
            "test_name": self.test_to_compile
        })
        
        # Check for success
        success = self.check_ivy_logs_for_success()
        
        # Notify completion
        self.notify_service_event("test_execution_completed", {
            "test_name": self.test_to_compile,
            "success": success,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        if success:
            # Create success marker
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            success_file = f"/app/logs/ivy_test_success_{timestamp}.marker"
            
            try:
                with open(success_file, "w", encoding="utf-8") as f:
                    f.write(f"Test {self.test_to_compile} successful at {timestamp}\n")
                    f.write(f"Role: {self.role.name if hasattr(self, 'role') else 'unknown'}\n")
                    f.write(f"Protocol: {self._get_protocol_name()}\n")
                    f.write(f"Implementation: {self.implementation_name}\n")
                
                self.logger.info("Created success marker file: %s", success_file)
                
                # Notify success
                self.notify_service_event("test_success", {
                    "test_name": self.test_to_compile,
                    "timestamp": timestamp,
                    "marker_file": success_file
                })
                
                return True
            except IOError as e:
                self.logger.error("Failed to create success marker file: %s", e)
                return False
        else:
            self.logger.warning("No success indicators found in logs for %s", self.test_to_compile)
            return False

    def check_ivy_logs_for_success(self) -> bool:
        """Analyzes Ivy test logs for success indicators."""
        success_patterns = [
            r"test\s+passed",
            r"verification\s+successful",
            r"no\s+counterexample\s+found",
            r"PASS",
            r"Success",
            r"test\s+completed\s+successfully"
        ]
        
        log_file = f"/app/logs/{self.service_name}.log"
        
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    log_content = f.read()
                    for pattern in success_patterns:
                        if re.search(pattern, log_content, re.IGNORECASE):
                            self.logger.info("Found success pattern '%s' in logs", pattern)
                            return True
            
            # Check compilation log as fallback
            compilation_log = "/app/logs/ivy_compilation.log" # TODO: For now we are not sure that the compilation log is like that -> make more flexible and resilient
            if os.path.exists(compilation_log):
                with open(compilation_log, "r", encoding="utf-8") as f:
                    comp_content = f.read()
                    for pattern in success_patterns:
                        if re.search(pattern, comp_content, re.IGNORECASE):
                            self.logger.info("Found success pattern '%s' in compilation log", pattern)
                            return True
        
        except (IOError, OSError) as e:
            self.logger.error("Error checking log files for success: %s", e)
        
        return False

    def set_collected_outputs(self, outputs: Dict[str, Dict[str, str]]) -> None:
        """Set collected outputs for analysis."""
        self.collected_outputs = outputs
        self.logger.info(f"Received {len(outputs)} output types for analysis: {list(outputs.keys())}")
        
        # Notify outputs received
        self.notify_service_event("outputs_received", {
            "output_types": list(outputs.keys()),
            "total_files": sum(len(env_files) for env_files in outputs.values())
        })

    def analyze_outputs(self) -> Dict[str, Any]:
        """Analyze collected outputs."""
        self.logger.info(f"Starting output analysis for {self.service_name}")
        
        # Notify analysis started
        self.notify_service_event("analysis_started", {
            "test_name": self.test_to_compile
        })
        
        analysis_results = {
            "passed": False,
            "failed_checks": [],
            "warnings": [],
            "detailed_results": {},
            "analysis_summary": ""
        }
        
        try:
            # Analyze trace files
            if "trace" in self.collected_outputs:
                trace_analysis = self._analyze_trace_files(self.collected_outputs["trace"])
                analysis_results["detailed_results"]["trace_analysis"] = trace_analysis
                if not trace_analysis.get("valid", True):
                    analysis_results["failed_checks"].append("Invalid system call patterns in trace")
            
            # Analyze CPU profiles
            if "cpu_profile" in self.collected_outputs:
                cpu_analysis = self._analyze_cpu_profiles(self.collected_outputs["cpu_profile"])
                analysis_results["detailed_results"]["cpu_analysis"] = cpu_analysis
                if cpu_analysis.get("excessive_cpu_usage", False):
                    analysis_results["warnings"].append("High CPU usage detected during test")
            
            # Analyze Ivy logs
            ivy_log_analysis = self._analyze_ivy_logs()
            analysis_results["detailed_results"]["ivy_analysis"] = ivy_log_analysis
            
            # Check success
            ivy_success = ivy_log_analysis.get("test_passed", False)
            compilation_success = ivy_log_analysis.get("compilation_success", False)
            
            if not compilation_success:
                analysis_results["failed_checks"].append("Ivy compilation failed")
            
            if not ivy_success:
                analysis_results["failed_checks"].append("Ivy test execution failed or no success pattern found")
            
            # Determine overall result
            analysis_results["passed"] = (
                compilation_success and
                ivy_success and
                len(analysis_results["failed_checks"]) == 0
            )
            
            # Create summary
            if analysis_results["passed"]:
                analysis_results["analysis_summary"] = (
                    f"Ivy test '{self.test_to_compile}' passed successfully. "
                    f"Compilation and execution completed without errors."
                )
            else:
                failed_reasons = "; ".join(analysis_results["failed_checks"])
                analysis_results["analysis_summary"] = (
                    f"Ivy test '{self.test_to_compile}' failed. Reasons: {failed_reasons}"
                )
            
            # Notify analysis completed
            self.notify_service_event("analysis_completed", {
                "test_name": self.test_to_compile,
                "passed": analysis_results["passed"],
                "failed_checks": analysis_results["failed_checks"],
                "warnings": analysis_results["warnings"]
            })
            
            self.logger.info(f"Analysis completed: {analysis_results['analysis_summary']}")
            return analysis_results
            
        except Exception as e:
            error_msg = f"Error during output analysis: {str(e)}"
            self.logger.error(error_msg)
            
            # Notify error
            self.notify_service_error(
                error_type="analysis_error",
                error_message=error_msg,
                details={"traceback": traceback.format_exc()}
            )
            
            return {
                "passed": False,
                "failed_checks": [error_msg],
                "warnings": [],
                "detailed_results": {"error": str(e)},
                "analysis_summary": f"Analysis failed due to error: {str(e)}"
            }

    def get_test_results(self) -> Dict[str, Any]:
        """Get final test results."""
        # Check if we have analysis results
        if not hasattr(self, 'collected_outputs') or not self.collected_outputs:
            self.logger.warning("No collected outputs available for analysis")
            analysis_results = {
                "passed": False,
                "failed_checks": ["No outputs collected for analysis"],
                "warnings": [],
                "detailed_results": {},
                "analysis_summary": "No outputs were collected for analysis"
            }
        else:
            analysis_results = self.analyze_outputs()
        
        # Get execution results
        execution_results = {
            "test_compiled": True,
            "test_executed": True,
            "log_success_detected": self.check_ivy_logs_for_success(),
            "test_name": self.test_to_compile,
            "protocol": self._get_protocol_name(),
            "implementation": self.implementation_name
        }
        
        # Overall pass determination
        overall_passed = (
            execution_results["log_success_detected"] and
            analysis_results["passed"]
        )
        
        # Create summary
        if overall_passed:
            summary = (
                f"Ivy test '{self.test_to_compile}' completed successfully. "
                f"Both execution and output analysis passed."
            )
        else:
            failure_reasons = []
            if not execution_results["log_success_detected"]:
                failure_reasons.append("No success pattern found in execution logs")
            if not analysis_results["passed"]:
                failure_reasons.extend(analysis_results["failed_checks"])
            
            summary = (
                f"Ivy test '{self.test_to_compile}' failed. "
                f"Reasons: {'; '.join(failure_reasons)}"
            )
        
        test_results = {
            "passed": overall_passed,
            "execution_results": execution_results,
            "analysis_results": analysis_results,
            "summary": summary,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "service_name": self.service_name
        }
        
        # Store results
        self.test_results = test_results
        
        # Notify results ready
        self.notify_service_event("test_results_ready", {
            "test_name": self.test_to_compile,
            "overall_passed": overall_passed,
            "summary": summary
        })
        
        self.logger.info(f"Final test results: {summary}")
        return test_results

    def _analyze_trace_files(self, trace_outputs: Dict[str, str]) -> Dict[str, Any]:
        """Analyze system call trace files."""
        trace_analysis = {
            "valid": True,
            "suspicious_calls": [],
            "file_count": len(trace_outputs),
            "details": {}
        }
        
        suspicious_patterns = [
            r"SIGSEGV",
            r"SIGABRT",
            r"failed.*ENOENT",
            r"failed.*ECONNREFUSED",
            r"failed.*ETIMEDOUT"
        ]
        
        for env_name, trace_file in trace_outputs.items():
            try:
                if os.path.exists(trace_file):
                    with open(trace_file, "r", encoding="utf-8") as f:
                        trace_content = f.read()
                    
                    env_analysis = {
                        "file_size": len(trace_content),
                        "suspicious_patterns": []
                    }
                    
                    for pattern in suspicious_patterns:
                        matches = re.findall(pattern, trace_content, re.IGNORECASE)
                        if matches:
                            env_analysis["suspicious_patterns"].append({
                                "pattern": pattern,
                                "matches": len(matches)
                            })
                            trace_analysis["suspicious_calls"].extend(matches)
                    
                    if env_analysis["suspicious_patterns"]:
                        trace_analysis["valid"] = False
                    
                    trace_analysis["details"][env_name] = env_analysis
                else:
                    self.logger.warning(f"Trace file not found: {trace_file}")
                    trace_analysis["details"][env_name] = {"error": "File not found"}
            
            except Exception as e:
                self.logger.error(f"Error analyzing trace file {trace_file}: {e}")
                trace_analysis["details"][env_name] = {"error": str(e)}
        
        return trace_analysis

    def _analyze_cpu_profiles(self, cpu_outputs: Dict[str, str]) -> Dict[str, Any]:
        """Analyze CPU profiling data."""
        cpu_analysis = {
            "excessive_cpu_usage": False,
            "profile_count": len(cpu_outputs),
            "details": {}
        }
        
        for env_name, profile_file in cpu_outputs.items():
            try:
                if os.path.exists(profile_file):
                    stat_info = os.stat(profile_file)
                    file_size = stat_info.st_size
                    
                    env_analysis = {
                        "file_size": file_size,
                        "analysis": "basic"
                    }
                    
                    if file_size > 10 * 1024 * 1024:  # 10MB threshold
                        cpu_analysis["excessive_cpu_usage"] = True
                        env_analysis["warning"] = "Large profile file detected"
                    
                    cpu_analysis["details"][env_name] = env_analysis
                else:
                    self.logger.warning(f"CPU profile file not found: {profile_file}")
                    cpu_analysis["details"][env_name] = {"error": "File not found"}
            
            except Exception as e:
                self.logger.error(f"Error analyzing CPU profile {profile_file}: {e}")
                cpu_analysis["details"][env_name] = {"error": str(e)}
        
        return cpu_analysis

    def _analyze_ivy_logs(self) -> Dict[str, Any]:
        """Analyze Ivy-specific log files."""
        ivy_analysis = {
            "compilation_success": False,
            "test_passed": False,
            "errors_found": [],
            "warnings_found": []
        }
        
        log_files_to_check = [
            "/app/logs/ivy_setup.log",
            "/app/logs/ivy_compilation.log",
            f"/app/logs/{self.service_name}.log",
            "/app/logs/stdout.log",
            "/app/logs/stderr.log"
        ]
        
        error_patterns = [
            r"error:",
            r"Error:",
            r"ERROR:",
            r"compilation failed",
            r"Compilation failed",
            r"ivy compilation failed",
            r"exit_code.*[^0]",
            r"Traceback",
            r"Exception:"
        ]
        
        compilation_success_patterns = [
            r"compilation.*success",
            r"successfully.*compiled",
            r"ivy.*compilation.*complete"
        ]
        
        test_success_patterns = [
            r"test.*passed",
            r"verification.*successful",
            r"no.*counterexample.*found",
            r"PASS",
            r"Success",
            r"test.*completed.*successfully"
        ]
        
        for log_file in log_files_to_check:
            try:
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as f:
                        log_content = f.read()
                    
                    # Check for errors
                    for pattern in error_patterns:
                        matches = re.findall(pattern, log_content, re.IGNORECASE)
                        if matches:
                            ivy_analysis["errors_found"].extend(matches)
                    
                    # Check for compilation success
                    for pattern in compilation_success_patterns:
                        if re.search(pattern, log_content, re.IGNORECASE):
                            ivy_analysis["compilation_success"] = True
                            break
                    
                    # Check for test success
                    for pattern in test_success_patterns:
                        if re.search(pattern, log_content, re.IGNORECASE):
                            ivy_analysis["test_passed"] = True
                            break
            
            except Exception as e:
                self.logger.error(f"Error analyzing log file {log_file}: {e}")
                ivy_analysis["warnings_found"].append(f"Could not read {log_file}: {str(e)}")
        
        # If no explicit compilation success found but no compilation errors, assume success
        if not ivy_analysis["compilation_success"] and not any("compilation" in error.lower() for error in ivy_analysis["errors_found"]):
            ivy_analysis["compilation_success"] = True
        
        # Use existing check method as fallback
        if not ivy_analysis["test_passed"]:
            ivy_analysis["test_passed"] = self.check_ivy_logs_for_success()
        
        return ivy_analysis

    def _do_stop(self):
        """Stop the service."""
        self.logger.info("Stopping PantherIvyServiceManager service")
        try:
            # Check for test success before stopping
            test_success = self.check_ivy_logs_for_success()
            
            # Store status (use attribute name that doesn't conflict with method)
            self._test_success_status = test_success
            
            return True
        except Exception as e:
            self.logger.error("Error stopping PantherIvy service: %s", e)
            raise

    def _do_run_tests(self):
        """Run tests implementation."""
        self.logger.info("Running Ivy tests for %s", self.test_to_compile)
        
        try:
            # Check test success
            success = self.test_success()
            
            # Prepare results
            test_results = {
                "success": success,
                "test_name": self.test_to_compile,
                "service_name": self.service_name,
                "protocol": self._get_protocol_name(),
                "role": self.role.name if hasattr(self, "role") else "unknown",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Analyze outputs if available
            if hasattr(self, "collected_outputs") and self.collected_outputs:
                analysis_results = self.analyze_outputs()
                test_results["analysis"] = analysis_results
                test_results["success"] = test_results["success"] and analysis_results.get("passed", False)
            
            # Store results
            self.test_results = test_results
            
            return test_results
            
        except Exception as e:
            self.logger.error("Error running Ivy tests: %s", e)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "test_name": self.test_to_compile,
                "service_name": self.service_name,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def handle_event(self, event: BaseEvent) -> None:
        """Handle events sent to this plugin."""
        event_type = type(event).__name__
        self.logger.debug("Received event: %s", event_type)
        
        try:
            if event_type == "ServiceStartedEvent":
                self.logger.info("Service started event received")
            elif event_type == "ServiceStoppedEvent":
                self.logger.info("Service stopped event received")
            elif event_type == "OutputCollectedEvent":
                self.logger.info("Output collected event received")
                if hasattr(event, "outputs"):
                    self.set_collected_outputs(event.outputs)
            elif event_type == "TestRunRequestedEvent":
                self.logger.info("Test run requested event received")
            else:
                self.logger.debug("Unhandled event type: %s", event_type)
        
        except Exception as e:
            self.logger.error("Error handling event %s: %s", event_type, e)
            self.notify_service_error(
                error_type="event_handling_error",
                error_message=str(e),
                details={"event_type": event_type, "traceback": traceback.format_exc()}
            )

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

    def get_available_tests(self) -> List[dict]:
        """Returns available tests."""
        if self.available_tests is None:
            raise ValueError("Available tests are not loaded. Call prepare() first.")
        return self.available_tests

    def __str__(self) -> str:
        return f"PantherIvyServiceManager({self.service_config_to_test})"

    def __repr__(self):
        return f"PantherIvyServiceManager({self.service_config_to_test})"