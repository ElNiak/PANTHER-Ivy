from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from panther.core.exceptions.InvalidCommandFormatError import InvalidCommandFormatError
from panther.core.exceptions.ServiceCommandGenerationException import (
    ServiceCommandGenerationException,
)
from panther.plugins.services.testers.panther_ivy.config_schema import (
    AvailableTests,
    PantherIvyConfig,
)
from panther.plugins.services.testers.tester_interface import ITesterManager
from panther.plugins.plugin_loader import PluginLoader
from panther.plugins.protocols.config_schema import ProtocolConfig, RoleEnum
from panther.utils.command import ShellCommand
# Add imports for event emission support
from panther.plugins.services.service_event_methods import ServiceManagerEventMixin
from panther.core.observer.events import (
    ServiceStartedEvent,
    ServiceStoppedEvent,
    ServiceErrorEvent,
    StepProgressEvent
)
import os
import subprocess
import traceback
import re
import time


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


# TODO add more attributes
# TODO make the debug event working
def oppose_role(role):
    """
    quic_server_test -> We test the server, so we need the client implementation (ivy_client)
    quic_client_test -> We test the client, so we need the server implementation (ivy_server)
    """
    # TODO fix logic in ivy itself
    return "client" if role == "server" else "server"


class PantherIvyServiceManager(ITesterManager, ServiceManagerEventMixin):
    """
    Manages the Ivy testers service for the Panther project.

    This class is responsible for configuring, preparing, compiling, and running Ivy tests
    for a given protocol implementation. It interacts with Docker, manages environment
    variables, and handles the setup of necessary directories and files.

    Attributes:
        service_config_to_test (PantherIvyConfig): Configuration for the service to be tested.
        service_type (str): Type of the service.
        protocol (ProtocolConfig): Protocol configuration.
        implementation_name (str): Name of the implementation.
        test_to_compile (str): Test to be compiled.
        env_protocol_model_path (str): Path to the protocol model.
        ivy_log_level (str): Log level for Ivy.
        event_emitter: Event emitter for sending standardized events.

    Methods:
        generate_pre_compile_commands(): Generates pre-compile commands.
        generate_compile_commands(): Generates compile commands.
        generate_post_compile_commands(): Generates post-compile commands.
        generate_run_command(): Generates the run command.
        generate_post_run_commands(): Generates post-run commands.
        prepare(plugin_loader: Optional[PluginLoader] = None): Prepares the Ivy testers service manager.
        build_submodules(): Initializes git submodules.
        pair_compile_file(file, replacements): Replaces file names and compiles the file.
        update_ivy_tool() -> List[str]: Updates the Ivy tool and includes paths.
        generate_compilation_commands() -> list[str]: Generates compilation commands.
        build_tests() -> List[str]: Compiles and prepares the tests.
        generate_deployment_commands() -> str: Generates deployment commands and collects volume mappings.
    """
    def __init__(
        self,
        service_config_to_test: PantherIvyConfig,
        service_type: str,
        protocol: ProtocolConfig,
        implementation_name: str,
        event_manager=None,
    ):
        super().__init__(service_config_to_test, service_type, protocol, implementation_name, event_manager)
        # Initialize event_emitter if event_manager is provided
        self.event_emitter = None if event_manager is None else EventEmitter(event_manager)
        
        # Set service name for event identification
        self.service_name = f"ivy_{implementation_name}"

        # Initialize structured_commands dictionary for command phases
        self.structured_commands = {
            "pre_compile": [],
            "compile": [],
            "post_compile": [],
            "pre_run": [],
            "run": [],
            "post_run": [],
        }

        # TODO
        service_config_to_test.directories_to_start = []

        self.available_tests = None
        self.test_to_compile = self.service_config_to_test.implementation.test
        self.test_to_compile_path = None
        self.protocol = protocol
        if self.service_config_to_test.implementation.use_system_models:
            self.env_protocol_model_path = "/opt/panther_ivy/protocol-testing/apt/"
            self.protocol_model_path = os.path.abspath(
                f"{str(self._plugin_dir)}/testers/panther_ivy/protocol-testing/" + "apt"
            )
        else:
            self.env_protocol_model_path = (
                "/opt/panther_ivy/protocol-testing/" + self.protocol.name + "/"
            )
            self.protocol_model_path = os.path.abspath(
                f"{str(self._plugin_dir)}/testers/panther_ivy/protocol-testing/"
                + self.protocol.name
            )
        self.ivy_log_level = self.service_config_to_test.implementation.parameters.log_level

    def generate_pre_compile_commands(self):
        """
        Generates pre-compile commands.
        Note: $ is for docker compose 
        """
        # First, call the parent class method to get any base commands
        base_commands = super().generate_pre_compile_commands()
        
        # Define the IP utility functions as proper multiline function blocks
        ip_to_hex_function = """ip_to_hex() {
    echo "$1" | awk -F. '{printf("%02X%02X%02X%02X", $1, $2, $3, $4)}';
}"""

        ip_to_decimal_function = """ip_to_decimal() {
    echo "$1" | awk -F. '{printf("%.0f", ($1 * 256 * 256 * 256) + ($2 * 256 * 256) + ($3 * 256) + $4)}';
}"""
        
        # Use the add_command method to properly add these function definitions
        self.add_command(
            phase="pre_compile",
            command=ip_to_hex_function,
            description="Function: ip_to_hex",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command=ip_to_decimal_function,
            description="Function: ip_to_decimal",
            is_function_definition=True,
            is_multiline=True,
        )
        
        # Add target IP resolution command
        self.add_command(
            phase="pre_compile",
            command="TARGET_IP=$(getent hosts " + self.service_targets + " | awk '{print $1}' | grep -v '^127' | head -n 1)",
            description="Resolve target IP address",
            is_critical=True,
            is_variable_assignment=True,
            is_function_call=True,
        )
        
        # Add echo target IP command
        self.add_command(
            phase="pre_compile",
            command='echo "Resolved ' + self.service_targets + ' TARGET_IP IP - $TARGET_IP" >> /app/logs/ivy_setup.log',
            description="Log target IP address",
            is_critical=False,
        )
        
        # Add ivy IP resolution command
        self.add_command(
            phase="pre_compile",
            command="IVY_IP=$(hostname -I | awk '{print $1}' | grep -v '^127' | head -n 1)",
            description="Resolve Ivy IP address",
            is_critical=True,
            is_variable_assignment=True,
            is_function_call=True,
        )
        
        # Add echo ivy IP command
        self.add_command(
            phase="pre_compile",
            command='echo "Resolved  ' + self.service_name + ' IVY_IP IP - $IVY_IP" >> /app/logs/ivy_setup.log',
            description="Log Ivy IP address",
            is_critical=False,
        )
      
        # Convert target IP to hex
        self.add_command(
            phase="pre_compile",
            command="TARGET_IP_HEX=$(ip_to_decimal $TARGET_IP)",
            description="Convert target IP to decimal format",
            is_critical=True,
            is_function_call=True,
        )
        
        # Convert ivy IP to hex
        self.add_command(
            phase="pre_compile",
            command="IVY_IP_HEX=$(ip_to_decimal $IVY_IP)",
            description="Convert Ivy IP to decimal format",
            is_critical=True,
            is_function_call=True,
        )
        
        # Log target IP hex
        self.add_command(
            phase="pre_compile",
            command='echo "Resolved ' + self.service_targets + ' IP in hex - $TARGET_IP_HEX" >> /app/logs/ivy_setup.log',
            description="Log target IP in hex format",
            is_critical=False,
        )
        
        # Log ivy IP hex
        self.add_command(
            phase="pre_compile",
            command='echo "Resolved ' + self.service_name + ' IP in hex - $IVY_IP_HEX" >> /app/logs/ivy_setup.log',
            description="Log Ivy IP in hex format",
            is_critical=False,
        )
        
      
        # Clean build directory
        if self.service_config_to_test.implementation.use_system_models:
            clean_cmd = "rm -rf /opt/panther_ivy/protocol-testing/apt/build/*"
        else:
            clean_cmd = "rm -rf /opt/panther_ivy/protocol-testing/{}/build/*".format(self.protocol.name)
            
        self.add_command(
            phase="pre_compile",
            command=clean_cmd,
            description="Clean build directory",
            is_critical=True,
        )
        
        # Return base commands to maintain compatibility
        # Note: The commands are already added to self.structured_commands["pre_compile"]
        return base_commands

    def generate_compile_commands(self):
        """
        Generates compile commands.
        """
        # Get base commands from parent class and our compilation commands
        base_commands = super().generate_compile_commands() 
        compilation_commands = self.generate_compilation_commands()
        
        # Emit service started event to notify that compilation is beginning
        if hasattr(self, "event_emitter") and self.event_emitter:
            self.event_emitter.emit_service_started(
                service_name=self.service_name, 
                details={
                    "action": "compilation_started",
                    "protocol": self.protocol.name,
                    "test": self.test_to_compile
                }
            )
        
        # If we have compilation commands, add the ready file command properly
        if compilation_commands:
            # Append the touch command to the last compilation command
            if isinstance(compilation_commands[-1], str):
                # Add the touch command to the last string command
                last_command = compilation_commands[-1]
                # Check if the command already has a trailing &&
                if last_command.strip().endswith("&&"):
                    # If it ends with &&, just add the touch command
                    modified_command = f"{last_command} (touch /app/sync_logs/ivy_ready.log)"
                else:
                    # Otherwise add with && before the touch command
                    modified_command = f"{last_command} && (touch /app/sync_logs/ivy_ready.log)"
                compilation_commands[-1] = modified_command
            else:
                # Add as a separate command if the last item is not a string
                compilation_commands.append("(touch /app/sync_logs/ivy_ready.log)")
        else:
            # If no compilation commands, just add the touch command as a separate command
            compilation_commands = ["(touch /app/sync_logs/ivy_ready.log)"]
            
        # Return the combined commands
        return base_commands + compilation_commands

    def generate_post_compile_commands(self):
        """
        Generates post-compile commands.
        """
        return super().generate_post_compile_commands() + [f"cd {self.env_protocol_model_path};"]

    def generate_run_command(self):
        """
        Generates the run command.
        """
        cmd_args = self.generate_deployment_commands()
        
        # Emit service event for test execution
        if self.event_emitter:
            self.notify_service_event("test_execution_started", {
                "test_name": self.test_to_compile,
                "protocol": self.protocol.name
            })
        
        # Check if test_to_compile exists before creating the command
        command_binary = ""
        if hasattr(self, "test_to_compile") and self.test_to_compile:
            command_binary = os.path.join(
                self.service_config_to_test.implementation.parameters.tests_build_dir.value,
                self.test_to_compile)
            command_binary = "./" + command_binary
        
        # Make sure command_args is not None and is a valid type (list or str)
        if cmd_args is None:
            self.logger.warning("Command arguments are None, using empty list")
            cmd_args = []
        elif isinstance(cmd_args, str):
            # If it's a string, clean it and convert to list if needed
            cmd_args = cmd_args.replace("\n", "").strip()
            if not cmd_args:  # If empty after cleaning
                cmd_args = []
        
        # Make sure working_dir is always set
        working_dir = self.env_protocol_model_path
        if working_dir is None:
            # Fallback for safety
            self.logger.warning("Protocol model path is not set, using fallback working directory")
            if self.service_config_to_test.implementation.use_system_models:
                working_dir = "/opt/panther_ivy/protocol-testing/apt/"
            else:
                working_dir = f"/opt/panther_ivy/protocol-testing/{self.protocol.name}/"
            
        return {
            "working_dir": working_dir,
            "command_binary": command_binary,
            "command_args": cmd_args,
            "timeout": self.service_config_to_test.timeout,
            "environment": {},  # Changed from command_env to environment to match what's expected
        }

    def generate_post_run_commands(self):
        """
        Generates post-run commands.
        """
        return super().generate_post_run_commands() + [
            f"cp {os.path.join(self.env_protocol_model_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value, self.test_to_compile)} /app/logs/{self.test_to_compile} && ",
            f"rm {os.path.join(self.env_protocol_model_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value, self.test_to_compile)}*;",
        ]

    def prepare(self, plugin_loader: Optional[PluginLoader] = None):
        """
        Prepares the Panther Ivy testers service manager, handling directories, git repositories, etc.

        Args:
            plugin_loader: Optional plugin loader to configure parameters.
        """
        self.logger.info("Preparing PantherIvy service manager for %s", self.service_name)
        
        # Notify service preparation started using both standard mixin method and more detailed event
        self.notify_service_event("preparation_started", {
            "service_name": self.service_name,
            "service_type": self.service_type,
            "implementation": self.implementation_name,
            "test": self.test_to_compile
        })
        
        try:
            # Performing basic setup
            super().prepare(plugin_loader)
            
            # Check if the Ivy path is set and exists
            if self.env_protocol_model_path:
                if os.path.exists(self.env_protocol_model_path):
                    self.protocol_model_path = self.env_protocol_model_path
                else:
                    self.logger.warning("Protocol model path %s does not exist", self.env_protocol_model_path)
            
            if not hasattr(self, "protocol_model_path") or not self.protocol_model_path:
                # Get the plugin directory path
                self._plugin_dir = plugin_loader.get_plugin_path(
                    "services", "testers", "panther_ivy"
                )
                self.protocol_model_path = os.path.abspath(
                    f"{str(self._plugin_dir)}/testers/panther_ivy/protocol-testing/"
                    + self.protocol.name
                )
            
            # Set logging level from configuration
            self.ivy_log_level = self.service_config_to_test.implementation.parameters.log_level
            
            # Build git submodules if necessary
            if hasattr(self.service_config_to_test, "build_submodules") and self.service_config_to_test.build_submodules:
                self.build_submodules()
            
            # Notify service preparation completed successfully
            self.notify_service_event("prepared", {
                "service_name": self.service_name,
                "protocol_model_path": self.protocol_model_path,
                "log_level": self.ivy_log_level,
            })
            
        except Exception as e:
            # Notify service preparation failed
            self.notify_service_error(
                error_type="preparation_error",
                error_message=str(e),
                details={
                    "traceback": traceback.format_exc(),
                    "service_name": self.service_name
                }
            )
            self.logger.error("Failed to prepare PantherIvy service manager: %s", e)
            raise

    def build_submodules(self):
        """
        Initialize git submodules.

        This method initializes and updates git submodules required by the Ivy service.
        """
        current_dir = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        try:
            self.logger.info("Initializing submodules (from %s)", os.getcwd())
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error("Failed to initialize submodules: %s", e)
        finally:
            os.chdir(current_dir)

    def pair_compile_file(self, file, replacements):
        """_summary_

        Args:
            file (_type_): _description_
            replacements (_type_): _description_
        """
        for old_name, new_name in replacements.items():
            if old_name in file:
                file = file.replace(old_name, new_name)
                self.compile_file(file)

    def update_ivy_tool(self) -> List[str]:
        """
        Update Ivy tool and include paths.
        Note: ":" cannot be used in the command as it is used to separate commands.
        This script is compatible with /bin/sh syntax.

        This method constructs a series of shell commands to update the Ivy tool,
        copy necessary libraries and headers, and set up the Ivy model. The commands
        are logged to a specified log file for debugging purposes.

        The update process includes:
        - Installing the Ivy tool.
        - Copying updated Ivy and Z3 files.
        - Copying QUIC libraries if the protocol is "quic" or "apt".
        - Removing and restoring debug events in Ivy files based on the log level.
        - Setting up the Ivy model by copying Ivy files to the include path.

        Returns:
            List[str]: A list of shell commands to be executed for updating the Ivy tool.
        """
        # Define all function definitions as complete multi-line blocks
        # This ensures they're handled correctly by the entrypoint script

        # Mark the function definition with a special comment so the entrypoint can handle it properly
        update_ivy_tool_function = """update_ivy_tool() {
    echo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;
    cd "/opt/panther_ivy" || exit 1;
    cat setup.py >> /app/logs/ivy_setup.log;
    sudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&
    cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&
    echo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log;
    find /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/ \\; >> /app/logs/ivy_setup.log 2>&1;
    echo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log 2>&1;
    cp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;
}"""

        remove_debug_events_function = """remove_debug_events() {
    echo "Removing debug events..." >> /app/logs/ivy_setup.log;
    printf "%s\\n" "$@" | xargs -I {} sh -c "
        if [ -f \\"\\$1\\" ]; then
            sed -i \\"s/^\\\\([^#]*debug_event.*\\\\)/##\\\\1/\\" \\"\\$1\\";
        else
            echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
        fi
    " _ {};
}"""

        restore_debug_events_function = """restore_debug_events() {
    echo "Restoring debug events..." >> /app/logs/ivy_setup.log;
    printf "%s\\n" "$@" | xargs -I {} sh -c "
        if [ -f \\"\\$1\\" ]; then
            sed -i \\"s/^##\\\\(.*debug_event.*\\\\)/\\\\1/\\" \\"\\$1\\";
        else
            echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
        fi
    " _ {};
}"""

        # First prepare the variables we want to inject
        env_path_value = self.env_protocol_model_path
        log_level_value = "1" if self.ivy_log_level == "DEBUG" else "10"

        # Create the function with explicit variables to avoid string formatting issues
        setup_ivy_model_function = f"""setup_ivy_model() {{
    echo "Setting up Ivy model..." >> /app/logs/ivy_setup.log &&
    echo "Updating include path of Python with updated version of the project from {env_path_value}" >> /app/logs/ivy_setup.log &&
    echo "Finding .ivy files..." >> /app/logs/ivy_setup.log &&
    find "{env_path_value}" -type f -name "*.ivy" -exec sh -c "
        echo \\"Found Ivy file - \\$1\\" >> /app/logs/ivy_setup.log;
        if [ {log_level_value} -gt 10 ]; then
            echo \\"Removing debug events from \\$1\\" >> /app/logs/ivy_setup.log;
            remove_debug_events \\"\\$1\\";
        fi;
        echo \\"Copying Ivy file to include path...\\" >> /app/logs/ivy_setup.log;
        cp -f \\"\\$1\\" \\"/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/\\";
    " _ {{}} \\;;
    ls -l /usr/local/lib/python3.10/dist-packages/ivy/include/1.7/ >> /app/logs/ivy_setup.log;
}}"""

        # Define QUIC library function if needed
        quic_lib_function = None
        # Prepare the path for quic_ser_deser.h
        if self.service_config_to_test.implementation.use_system_models:
            quic_ser_deser_path = (
            f"{self.env_protocol_model_path}/apt_protocols/quic/quic_utils/quic_ser_deser.h"
            )
        else:
            quic_ser_deser_path = f"{self.env_protocol_model_path}/quic_utils/quic_ser_deser.h"
            
        if self.protocol.name in ["quic", "apt"]:
            # Define QUIC library command as a complete function block
            quic_lib_function = f"""quic_lib_setup() {{
        echo "Copying QUIC libraries..." >> /app/logs/ivy_setup.log
        cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ivy/lib/"
        cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/"
        cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ivy/include/picotls.h"
        cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h"
        cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ivy/include/picotls"
        
        # Add the correct path for quic_ser_deser.h based on configuration
        if [ -f "{quic_ser_deser_path}" ]; then
            cp -f "{quic_ser_deser_path}" "/usr/local/lib/python3.10/dist-packages/ivy/include/1.7/"
        else
            echo "Warning: quic_ser_deser.h not found at {quic_ser_deser_path}" >> /app/logs/ivy_setup.log
        fi
    }}"""


        # Use the add_command method to properly add all commands to both phases
        # Add all function definitions to pre_compile phase
        # Add QUIC function if needed
        if quic_lib_function:
            self.add_command(
                phase="pre_compile",
                command=quic_lib_function,
                description="Function: quic_lib_setup",
                is_function_definition=True,
                is_multiline=True,
            )
            
            # Add call to the quic_lib_setup function
            self.add_command(
                phase="pre_compile",
                command="quic_lib_setup",
                description="Call Function: quic_lib_setup",
                is_function_definition=False,
                is_function_call=True,
                is_multiline=False,
            )
            self.add_command(
                phase="pre_compile",
                command="quic_lib_setup &&",
                description="Call Function: quic_lib_setup",
                is_function_definition=False,
                is_function_call=True,
                is_multiline=False,
            )
            
        self.add_command(
            phase="pre_compile",
            command=update_ivy_tool_function,
            description="Function: update_ivy_tool",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command="update_ivy_tool",
            description="Call Function: update_ivy_tool",
            is_function_definition=False,
            is_function_call=True,
            is_multiline=False,
        )

        self.add_command(
            phase="pre_compile",
            command=remove_debug_events_function,
            description="Function: remove_debug_events",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command=restore_debug_events_function,
            description="Function: restore_debug_events",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command=setup_ivy_model_function,
            description="Function: setup_ivy_model",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command="setup_ivy_model",
            description="Call Function: setup_ivy_model",
            is_function_definition=False,
            is_function_call=True,
            is_multiline=False,
        )

        self.add_command(
            phase="pre_compile",
            command=restore_debug_events_function,
            description="Function: restore_debug_events",
            is_function_definition=True,
            is_multiline=True,
        )

        self.add_command(
            phase="pre_compile",
            command=setup_ivy_model_function,
            description="Function: setup_ivy_model",
            is_function_definition=True,
            is_multiline=True,
        )
        
        self.add_command(
            phase="pre_compile",
            command="setup_ivy_model &&",
            description="Call Function: setup_ivy_model",
            is_function_definition=False,
            is_function_call=True,
            is_multiline=False,
        )

        self.logger.info("Updating Ivy tool...")
        self.logger.debug("Added structured commands for updating the Ivy tool")

        # For backward compatibility, return a list of commands that would be used in legacy mode
        legacy_commands = []
        for cmd_phase in ["pre_compile", "compile"]:
            for cmd in self.structured_commands.get(cmd_phase, []):
                if is_func_def(cmd) or cmd.get("is_function_call", False) or cmd.get("is_function_definition", False):
                    legacy_commands.append(cmd.get("command", ""))
                    self.logger.debug(
                        "Processing command in phase %s: is_function_definition=%s, command=%s",
                        cmd_phase,
                        cmd.get("is_function_definition", False),
                        cmd.get("command", "")[:50],
                    )

        return legacy_commands

    def generate_compilation_commands(self) -> list[str]:
        """
        Generates the compilation commands for the service being tested.

        This method constructs the necessary environment variables and determines
        the appropriate tests to compile based on the role (client or server) and
        the service configuration. It logs detailed debug information about the
        compilation process, including the test to compile, available tests,
        environments, protocol, and version. If the specified test to compile is
        not found in the available tests, it logs an error and exits the program.

        Returns:
            list[str]: A list of compilation commands.

        Raises:
            SystemExit: If the test to compile is not found in the available tests.
        """
        self.logger.debug("Generating compilation commands for service: %s", self.service_name)

        self.logger.debug("Test to compile: %s", self.test_to_compile)

        protocol_env = self.service_config_to_test.implementation.version.env
        if not self.service_config_to_test.implementation.use_system_models:
            for key in protocol_env:
                protocol_env[key] = self.service_config_to_test.implementation.version.env[
                    key
                ].replace("/apt/apt_protocols", "")

        global_env = self.service_config_to_test.implementation.environment
        self.environments = {
            **global_env,
            **protocol_env,
            "TEST_TYPE": ("client" if self.role.name == "server" else "server"),
        }

        # TODO refine the config
        # self.environments["ZERORTT_TEST"]

        self.logger.debug("Test to compile: %s", self.test_to_compile)
        self.logger.debug("Test information: %s", self.available_tests)
        self.logger.debug("Environments: %s", self.environments)
        self.logger.debug("Protocol: %s", self.protocol)
        self.logger.debug("Version: %s", self.service_version.name)

        found = False
        for test in self.available_tests:
            if self.test_to_compile in test["name"]:
                found = True
                self.test_to_compile_path = test["path"]

        if not found:
            self.logger.error("Test '%s' not found in configuration.", self.test_to_compile)
            raise ServiceCommandGenerationException(
                self.service_name,
            )

        return self.update_ivy_tool() + self.build_tests()

    def build_tests(self, test_name=None) -> List[str]:
        """
        Builds the test commands for compiling and moving test files.
        This method constructs the necessary shell commands to compile tests using the Ivy compiler
        and move the compiled test files to the appropriate directory. It logs the process at various
        stages for debugging and informational purposes.
        Returns:
            List[str]: A list of shell commands to be executed for compiling and moving the test files.
        """

        self.logger.info("Compiling tests...")
        self.logger.info(
            "Mode: %s for test: %s in %s",
            self.role.name,
            self.test_to_compile,
            self.service_config_to_test.implementation.version.parameters["tests_dir"]["value"]
        )
        file_path = (
            os.path.join("/opt/panther_ivy/protocol-testing/apt/", self.test_to_compile_path)
            if self.service_config_to_test.implementation.use_system_models
            else os.path.join(
                self.env_protocol_model_path,
                self.test_to_compile_path if not test_name else test_name,
            )
        )
        self.logger.debug("Building file: %s", file_path)
        cmd = [
            f"cd {file_path};",
            # run ivyc and capture both stdout and stderr - don't redirect to hide errors
            # we'll tee to the log file so we can both capture the output and check exit code
            (
                f"PYTHONPATH=$PYTHON_IVY_DIR ivyc trace=false show_compiled=false "
                f"target=test test_iters={self.service_config_to_test.implementation.parameters.internal_iterations_per_test.value} "
                f"{self.test_to_compile if not test_name else test_name}.ivy 2>&1 | tee -a /app/logs/ivy_setup.log /app/logs/ivy_compilation.log;"
                f'exit_code=${{PIPESTATUS[0]}}; if [ $exit_code -ne 0 ]; then echo "Ivy compilation failed with code $exit_code" | '
                f"tee -a /app/logs/ivy_compilation_error.log; exit $exit_code; fi"
            ),
        ]
        self.logger.info("Tests compilation command: %s", cmd)
        mv_command = [
            f"cp {os.path.join(file_path, self.test_to_compile)}* {os.path.join('/opt/panther_ivy/protocol-testing/apt/', self.service_config_to_test.implementation.parameters.tests_build_dir.value)}; " if self.service_config_to_test.implementation.use_system_models else f"cp {os.path.join(file_path, self.test_to_compile)}* {os.path.join(self.env_protocol_model_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value)}; "
        ]
        self.logger.info("Moving built files: %s", mv_command)
        return (
            cmd
            + ["ls >> /app/logs/ivy_setup.log 2>&1;"]
            + [" "]
            + mv_command
            + [
                (
                    f"ls {os.path.join('/opt/panther_ivy/protocol-testing/apt/', self.service_config_to_test.implementation.parameters.tests_build_dir.value)} >> /app/logs/ivy_setup.log 2>&1;"
                    if self.service_config_to_test.implementation.use_system_models
                    else f"ls {os.path.join(self.env_protocol_model_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value)} >> /app/logs/ivy_setup.log 2>&1;"
                )
            ]
        )

    def generate_deployment_commands(self) -> str:
        """
        Generates deployment commands for the service based on its configuration and role.
        This method constructs a set of deployment commands by gathering parameters from the service configuration,
        determining the appropriate network interface parameters, and rendering a command template.
        Returns:
            str: The rendered deployment command string.
        Raises:
            Exception: If there is an error in rendering the command template.
        Logs:
            - Debug: When generating deployment commands for the service.
            - Debug: The role and version of the service.
            - Error: If there is a failure in rendering the command template.
        Notes:
            - The method conditionally includes network interface parameters based on the environment.
            - The method sets up volume mappings for protocol testing directories.
        """

        self.logger.debug(
            "Generating deployment commands for service: %s with service parameters: %s",
            self.service_name,
            self.service_config_to_test
        )

        self.ivy_log_level = self.service_config_to_test.implementation.parameters.log_level
        # Create the command list
        self.logger.debug("Role: %s, Version: %s", self.role, self.service_version.name)

        # Determine if network interface parameters should be included based on environment
        include_interface = True
        params = None
        # TODO ensure that the parameters are correctly set
        if self.role == RoleEnum.server:
            params = self.service_config_to_test.implementation.version.server
        # For the client, include target and message if available
        elif self.role == RoleEnum.client:
            params = self.service_config_to_test.implementation.version.client

        if not params:
            raise ValueError(f"Invalid role '{self.role.name}' for service '{self.service_name}'.")

        for param in self.service_config_to_test.implementation.parameters:
            params[param] = self.service_config_to_test.implementation.parameters[param].value

        for param in self.service_config_to_test.implementation.version.parameters:
            params[param] = self.service_config_to_test.implementation.version.parameters[
                param
            ].value

        params["target"] = self.service_config_to_test.protocol.target
        params["server_addr"] = (
            "$TARGET_IP_HEX" if oppose_role(self.role.name) == "client" else "$IVY_IP_HEX"
        )
        params["client_addr"] = (
            "$TARGET_IP_HEX" if oppose_role(self.role.name) == "server" else "$IVY_IP_HEX"
        )
        params["is_client"] = oppose_role(self.role.name) == "client"
        params["test_name"] = self.test_to_compile
        params["timeout_cmd"] = f"timeout {self.service_config_to_test.timeout} "
        self.working_dir = self.env_protocol_model_path

        # Conditionally include network interface parameters
        if not include_interface:
            params["network"].pop("interface", None)

        ivy_include_protocol_testing_dir = os.path.abspath(
            f"{str(self._plugin_dir)}/testers/panther_ivy/ivy/include/1.7"
        )
        local_protocol_testing_dir = self.protocol_model_path
        self.volumes = self.volumes + [
            ivy_include_protocol_testing_dir + ":/opt/panther_ivy/ivy/include/1.7",
            local_protocol_testing_dir
            + (
                ":/opt/panther_ivy/protocol-testing/apt"
                if self.service_config_to_test.implementation.use_system_models
                else f":/opt/panther_ivy/protocol-testing/{self.protocol.name}"
            ),
            "shared_logs:/app/sync_logs",
        ]

        # Render the appropriate template
        try:
            template_name = f"{self.protocol.name}/{str(oppose_role(self.role.name))}_command.jinja"
            return super().render_commands(params, template_name)

        except Exception as e:
            self.logger.error(
                "Failed to render command for service '%s': %s\n%s",
                self.service_config_to_test.name,
                e,
                traceback.format_exc()
            )
            raise e

    def __str__(self) -> str:
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"

    def __repr__(self):
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"

    def get_available_tests(self) -> List[dict]:
        """
        Returns the available tests for the service.
        Returns:
            List[dict]: A list of available tests with their details.
        """
        if self.available_tests is None:
            raise ValueError("Available tests are not loaded. Call prepare() first.")
        return self.available_tests

    def add_command(
        self,
        phase: str,
        command: str | ShellCommand,
        description: str = "",
        is_critical: bool = True,
        is_multiline: bool = False,
        is_function_definition: bool = False,
        is_variable_assignment: bool = False,
        is_function_call: bool = False,
        working_dir: str = None,
        environment: dict = None,
        timeout: int = None,
    ):
        """
        Adds a command to the structured_commands dictionary for the specified phase.
        This method also calls the parent class add_command to maintain compatibility.

        Args:
            phase (str): The execution phase ('pre_compile', 'compile', 'post_compile', 'pre_run', 'run', 'post_run')
            command (str or ShellCommand): The command to execute
            description (str): Description of what the command does
            is_critical (bool): Whether command failure should stop further execution
            is_multiline (bool): Whether the command contains multiple lines
            is_function_definition (bool): Whether the command defines a shell function
            working_dir (str): Working directory for the command
            environment (dict): Environment variables for the command
            timeout (int): Command timeout in seconds

        Raises:
            TypeError: If any boolean flag is not of type bool
        """
        if phase not in self.structured_commands:
            self.logger.warning(
                "Unknown command phase: %s, skipping command: %s",
                phase,
                command if isinstance(command, str) else command.command[:50],
            )
            return

        # Process the command based on its type
        if isinstance(command, ShellCommand):
            # Use the existing ShellCommand object
            shell_cmd = command
            cmd_str = shell_cmd.command
        else:
            # Validate boolean types for string commands
            if not isinstance(is_critical, bool):
                raise TypeError("is_critical must be a bool for command: %s" % command)
            if not isinstance(is_multiline, bool):
                raise TypeError("is_multiline must be a bool for command: %s" % command)
            if not isinstance(is_function_definition, bool):
                raise TypeError("is_function_definition must be a bool for command: %s" % command)
            if not isinstance(is_function_call, bool):
                raise TypeError("is_function_call must be a bool for command: %s" % command)
            if not isinstance(is_variable_assignment, bool):
                raise TypeError("is_variable_assignment must be a bool for command: %s" % command)
       
            # Create a ShellCommand object
            shell_cmd = ShellCommand(
                command=command,
                description=description,
                is_critical=is_critical,
                is_multiline=is_multiline,
                is_function_definition=is_function_definition,
                is_function_call=is_function_call,
                is_variable_assignment=is_variable_assignment,
                working_dir=working_dir,
                environment=environment,
                timeout=timeout,
            )
            cmd_str = command

        # Add to local structured commands for PantherIvy
        self.structured_commands[phase].append(shell_cmd.to_dict())

        # Call parent's add_command with the ShellCommand object
        # The phase names are already compatible with the parent class
        super().add_command(
            phase=phase,
            command=command,
            description=description,
            is_function_definition=is_function_definition,
            is_multiline=is_multiline,
            is_critical=is_critical,
            is_function_call=is_function_call,
            working_dir=working_dir,
            environment=environment,
            timeout=timeout,
        )

        self.logger.debug("Added command to %s: %.50s...", phase, cmd_str)

    def get_structured_commands(self):
        """
        Returns the structured commands dictionary containing all commands for all phases.

        Returns:
            dict: A dictionary of commands organized by phase
        """
        return self.structured_commands
    
    def test_success(self):
        """
        Register test success to the network environment.
        
        This method is called when the test is successful and allows the network environment
        to detect the success status. It:
        1. Creates a success marker file in the shared logs directory
        2. Verifies success by analyzing log content
        3. Emits events to notify the system of test execution status
        
        Returns:
            bool: True if success was detected and registered, False otherwise
        """
        self.logger.info("Checking for test success in %s", self.test_to_compile)
        
        # Emit test execution started event
        if hasattr(self, "event_emitter") and self.event_emitter:
            self.event_emitter.emit_service_event("test_execution_started", {
                "service_name": self.service_name,
                "test_name": self.test_to_compile
            })
        
        # Verify success by analyzing log content
        success = self.check_ivy_logs_for_success()
        
        # Emit test execution completed event
        if hasattr(self, "event_emitter") and self.event_emitter:
            self.event_emitter.emit_service_event("test_execution_completed", {
                "service_name": self.service_name,
                "test_name": self.test_to_compile,
                "success": success,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        if success:
            # Create a success marker file in the shared logs directory
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            success_file = f"/app/logs/ivy_test_success_{timestamp}.marker"
            
            try:
                with open(success_file, "w", encoding="utf-8") as f:
                    f.write(f"Test {self.test_to_compile} successful at {timestamp}\n")
                    f.write(f"Role: {self.role.name}\n")
                    f.write(f"Protocol: {self.protocol.name}\n")
                    f.write(f"Implementation: {self.implementation_name}\n")
                    if hasattr(self, "service_version"):
                        f.write(f"Version: {self.service_version.name}\n")
                self.logger.info("Created success marker file: %s", success_file)
                
                # Emit success event
                if hasattr(self, "event_emitter") and self.event_emitter:
                    self.event_emitter.emit_service_event("test_success", {
                        "service_name": self.service_name,
                        "test_name": self.test_to_compile,
                        "timestamp": timestamp,
                        "marker_file": success_file
                    })
                
                # Legacy notification support for backward compatibility
                if hasattr(self, "notification_callback") and callable(self.notification_callback):
                    self.notification_callback("test_success", {
                        "service": self.service_name,
                        "test": self.test_to_compile,
                        "timestamp": timestamp,
                        "marker_file": success_file
                    })
                    self.logger.debug("Triggered test_success notification")
                
                return True
            except IOError as e:
                self.logger.error("Failed to create success marker file: %s", e)
                return False
        else:
            self.logger.warning("No success indicators found in logs for %s", self.test_to_compile)
            return False

    def check_ivy_logs_for_success(self):
        """
        Analyzes Ivy test logs for success indicators.
        
        Looks for patterns in the log output that indicate a successful test run,
        such as "test passed", "verification successful", etc.
        
        Returns:
            bool: True if success indicators were found, False otherwise
        """
        # Patterns that indicate success in Ivy test output
        success_patterns = [
            r"test\s+passed",
            r"verification\s+successful", 
            r"no\s+counterexample\s+found",
            r"PASS",
            r"Success",
            r"test\s+completed\s+successfully"
        ]
        
        # Check the current log file
        log_file = f"/app/logs/{self.service_name}.log"
        
        try:
            if not os.path.exists(log_file):
                self.logger.warning("Log file %s does not exist", log_file)
                return False
                
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
                for pattern in success_patterns:
                    if re.search(pattern, log_content, re.IGNORECASE):
                        self.logger.info("Found success pattern '%s' in logs", pattern)
                        return True
                        
            # Check compilation log as a fallback
            compilation_log = "/app/logs/ivy_compilation.log"
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
        
    def stop(self):
        """
        Stops the PantherIvyServiceManager service.
        
        This method is called by the TestCase's teardown_services method to properly
        stop the service if it's running. It uses the ServiceManagerEventMixin to emit
        events about the service stopping process.
        """
        self.logger.info("Stopping PantherIvyServiceManager service")
        try:
            # Emit service stopping event
            self.notify_service_event("stopping", {
                "service_name": self.service_name,
                "service_type": self.service_type,
                "implementation": self.implementation_name
            })
            
            # Actual stop logic would go here if needed
            # For example: stopping running processes, cleaning up resources, etc.
            
            # Check for test success in logs before stopping
            test_success = self.check_ivy_logs_for_success()
            
            # Emit service stopped event
            self.notify_service_stopped(
                success=True,
                details={
                    "test_success": test_success,
                    "service_name": self.service_name
                }
            )
            
            return True
        except Exception as e:
            # Emit service error event
            self.notify_service_error(
                error_type="stop_error",
                error_message=str(e),
                details={
                    "traceback": traceback.format_exc(),
                    "service_name": self.service_name
                }
            )
            self.logger.error("Error stopping PantherIvy service: %s", e)
            return False
