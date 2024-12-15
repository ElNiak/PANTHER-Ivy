from pathlib import Path
import subprocess
import os
from typing import List, Optional
import traceback
from panther.plugins.services.testers.panther_ivy.config_schema import PantherIvyConfig
from panther.plugins.services.testers.tester_interface import ITesterManager
from panther.plugins.plugin_loader import PluginLoader
from panther.plugins.protocols.config_schema import ProtocolConfig, RoleEnum


# TODO Tom create test template for QUIC implementations new users
# TODO add more attributes
# TODO make the debug event working
def oppose_role(role):
    # TODO fix logic in ivy itself
    return "client" if role == "server" else "server"


class PantherIvyServiceManager(ITesterManager):
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
        protocol_model_path (str): Path to the protocol model.
        ivy_log_level (str): Log level for Ivy.

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
    ):
        super().__init__(
            service_config_to_test, service_type, protocol, implementation_name
        )
        # TODO
        service_config_to_test.directories_to_start = [
        ]
        self.test_to_compile = self.service_config_to_test.implementation.test
        self.protocol = protocol
        self.protocol_model_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/", self.protocol.name
        )
        self.ivy_log_level = (
            self.service_config_to_test.implementation.parameters.log_level
        )
        self.initialize_commands()

    def generate_pre_compile_commands(self):
        """
        Generates pre-compile commands.
        Note: $$ is for docker compose 
        """
        return super().generate_pre_compile_commands() + [
            "TARGET_IP=$(getent hosts "
            + self.service_targets
            + ' | awk "{ print \$1 }");',
            'echo "Resolved '
            + self.service_targets
            + ' IP - $$TARGET_IP" >> /app/logs/ivy_setup.log;',
            'IVY_IP=$(hostname -I | awk "{ print \$1 }");',
            'echo "Resolved  '
            + self.service_name
            + ' IP - $$IVY_IP" >> /app/logs/ivy_setup.log;',
            " ",
            "ip_to_hex() {",
            '  echo $1 | awk -F"." "{ printf(\\"%02X%02X%02X%02X\\", \$1, \$2, \$3, \$4) }";',
            "}",
            " ",
            "ip_to_decimal() {",
            '  echo $1 | awk -F"." "{ printf(\\"%.0f\\", (\$1 * 256 * 256 * 256) + (\$2 * 256 * 256) + (\$3 * 256) + \$4) }";',
            "}",
            " ",
            "TARGET_IP_HEX=$(ip_to_decimal $$TARGET_IP);",
            "IVY_IP_HEX=$(ip_to_decimal $$IVY_IP);",
            'echo "Resolved '
            + self.service_targets
            + ' IP in hex - $$TARGET_IP_HEX" >> /app/logs/ivy_setup.log;',
            'echo "Resolved '
            + self.service_name
            + ' IP in hex - $$IVY_IP_HEX" >> /app/logs/ivy_setup.log;',
        ]

    def generate_compile_commands(self):
        """
        Generates compile commands.
        """
        return (
                super().generate_compile_commands() + self.generate_compilation_commands() + \
                [" && "] + [" (touch /app/sync_logs/ivy_ready.log) && "]
        )

    def generate_post_compile_commands(self):
        """
        Generates post-compile commands.
        """
        return super().generate_post_compile_commands() + [
            f"cd {self.protocol_model_path};"
        ]

    def generate_run_command(self):
        """
        Generates the run command.
        """
        cmd_args = self.generate_deployment_commands()
        return {
            "working_dir": self.protocol_model_path,
            "command_binary": os.path.join(
                self.service_config_to_test.implementation.parameters.tests_build_dir.value + self.test_to_compile),
            "command_args": cmd_args,
            "timeout": self.service_config_to_test.timeout,
            "command_env": {},
        }

    def generate_post_run_commands(self):
        """
        Generates post-run commands.
        """
        return super().generate_post_run_commands() + [
            f"cp {os.path.join(self.protocol_model_path, self.service_config_to_test.implementation.parameters.tests_build_dir.value, self.test_to_compile)} /app/logs/{self.test_to_compile};"
        ]

    def prepare(self, plugin_loader: Optional[PluginLoader] = None):
        """
        Prepares the Ivy testers service manager.
        """
        self.logger.info("Preparing Ivy testers service manager...")
        # self.build_submodules()

        protocol_testing_dir = os.path.abspath(
            str(self._plugin_dir) + "/testers/panther_ivy/protocol-testing/"
        )
        for subdir in os.listdir(protocol_testing_dir):
            subdir_path = os.path.join(protocol_testing_dir, subdir)
            if os.path.isdir(subdir_path):
                build_dir = os.path.join(subdir_path, "build")
                os.makedirs(build_dir, exist_ok=True)
                self.logger.debug(f"Created build directory: {build_dir}")
                temp_dir = os.path.join(subdir_path, "test", "temp")
                os.makedirs(temp_dir, exist_ok=True)
                self.logger.debug(
                    f"Created temporary test results directory: {temp_dir}"
                )

        # TODO load the configuration file: get the protocol name and the version + tests + versions
        plugin_loader.build_docker_image_from_path(Path(os.path.join(
            self._plugin_dir,
            "Dockerfile",
        )), "panther_base", "service")
        plugin_loader.build_docker_image(self.get_implementation_name(),
                                         self.service_config_to_test.implementation.version)
        self.logger.info("Ivy testers service manager prepared.")

    def build_submodules(self):
        current_dir = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        try:
            self.logger.info(f"Initializing submodules (from {os.getcwd()})")
            subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive"], check=True
            )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to initialize submodules: {e}")
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
        
        ----
        
        update_ivy_tool() {
            echo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;
            cd "/opt/panther_ivy" || exit 1;
            python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&
            cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&
            echo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log &&
            find /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ \; >> /app/logs/ivy_setup.log 2>&1 &&
            echo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log &&
            cp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;
        }
        update_ivy_tool &&

        echo "Copying QUIC libraries..." >> /app/logs/ivy_setup.log &&
        cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" &&
        cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/" &&
        cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls.h" &&
        cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h" &&
        cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls" &&
        cp -f "{protocol_model_path}/quic_utils/quic_ser_deser.h" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/" &&

        remove_debug_events() {{
            echo "Removing debug events..." >> /app/logs/ivy_setup.log;
            printf "%s\\n" "$@" | xargs -I {{}} sh -c "
                if [ -f \\"\\$1\\" ]; then
                    sed -i \\"s/^\\\\([^#]*debug_event.*\\\\)/##\\\\1/\\" \\"\$1\\";
                else
                    echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
                fi
            " _ {{}};
        }}
        restore_debug_events() {{
            echo "Restoring debug events..." >> /app/logs/ivy_setup.log;
            printf "%s\\n" "$@" | xargs -I {{}} sh -c "
                if [ -f \\"\\$1\\" ]; then
                    sed -i \\"s/^##\\\\(.*debug_event.*\\\\)/\\\\1/\\" \\"\\\$1\\";
                else
                    echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
                fi
            " _ {{}};
        }}
        setup_ivy_model() {{
            echo "Setting up Ivy model..." >> /app/logs/ivy_setup.log &&
            echo "Updating include path of Python with updated version of the project from {protocol_model_path}" >> /app/logs/ivy_setup.log &&
            echo "Finding .ivy files..." >> /app/logs/ivy_setup.log &&
            find "{protocol_model_path}" -type f -name "*.ivy" -exec sh -c "
                echo \\"Found Ivy file - \\$1\\" >> /app/logs/ivy_setup.log;
                if [ {log_level_ivy} -gt 10 ]; then
                    echo \\"Removing debug events from \\$1\\" >> /app/logs/ivy_setup.log;
                    remove_debug_events \\"\\$1\\";
                fi;
                echo \\"Copying Ivy file to include path...\\" >> /app/logs/ivy_setup.log;
                cp -f \\"\\$1\\" \\"/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/\\";
            " _ {{}} \;;
            ls -l /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ >> /app/logs/ivy_setup.log;
        }}
        setup_ivy_model &&
        """

        update_command = [
            " ",
            "update_ivy_tool() {",
            '\techo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;',
            '\tcd "/opt/panther_ivy" || exit 1;',
            "\tcat setup.py >> /app/logs/ivy_setup.log;", 
            "\tsudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&",
            "\tcp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&",
            '\techo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log;',
            '\tfind /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ \\; >> /app/logs/ivy_setup.log 2>&1;',
            '\techo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log;',
            '\tcp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;',
            "}",
            " ",
            "update_ivy_tool &&",
            ""
        ]

        update_for_quic_apt_cmd = [
            'echo "Copying QUIC libraries..." >> /app/logs/ivy_setup.log &&',
            'cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" &&',
            'cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/" &&',
            'cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls.h" &&',
            'cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h" &&',
            'cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls" &&',
            'cp -f "{protocol_model_path}/quic_utils/quic_ser_deser.h" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/" &&'.format(
                protocol_model_path=self.protocol_model_path,
            ),
        ]

        setup_ivy_model_cmd = [
            " ",
            "remove_debug_events() {",
            '\techo "Removing debug events..." >> /app/logs/ivy_setup.log;',
            '\tprintf "%s\\n" "$@" | xargs -I {} sh -c "',
            '\t\tif [ -f \\"\\$1\\" ]; then',
            '\t\t\tsed -i \\"s/^\\\\([^#]*debug_event.*\\\\)/##\\\\1/\\" \\"\$1\\";',
            "\t\telse",
            '\t\t\techo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;',
            "\t\tfi",
            '\t" _ {};',
            "}",
            " ",
            "restore_debug_events() {",
            '\techo "Restoring debug events..." >> /app/logs/ivy_setup.log;',
            '\tprintf "%s\\n" "$@" | xargs -I {} sh -c "',
            '\t\tif [ -f \\"\\$1\\" ]; then',
            '\t\t\tsed -i \\"s/^##\\\\(.*debug_event.*\\\\)/\\\\1/\\" \\"\$1\\";',
            "\t\telse",
            '\t\t\techo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;',
            "\t\tfi",
            '\t" _ {};',
            "}",
            " ",
            "setup_ivy_model() {",
            '\techo "Setting up Ivy model..." >> /app/logs/ivy_setup.log &&',
            '\techo "Updating include path of Python with updated version of the project from {protocol_model_path}" >> /app/logs/ivy_setup.log &&'.format(
                protocol_model_path=self.protocol_model_path
            ),
            '\techo "Finding .ivy files..." >> /app/logs/ivy_setup.log &&',
            '\tfind "{protocol_model_path}" -type f -name "*.ivy" -exec sh -c "'.format(
                protocol_model_path=self.protocol_model_path
            ),
            '\t\techo \\"Found Ivy file - \\$1\\" >> /app/logs/ivy_setup.log;',
            "\t\tif [ {log_level_ivy} -gt 10 ]; then".format(
                log_level_ivy="1" if self.ivy_log_level == "DEBUG" else "10"
            ),
            '\t\t\techo \\"Removing debug events from \\$1\\" >> /app/logs/ivy_setup.log;',
            '\t\t\tremove_debug_events \\"\\$1\\";',
            "\t\tfi;",
            '\t\techo \\"Copying Ivy file to include path...\\" >> /app/logs/ivy_setup.log;',
            '\t\tcp -f \\"\\$1\\" \\"/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/\\";',
            '\t" _ {} \\;;',
            "\tls -l /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ >> /app/logs/ivy_setup.log;",
            "}",
            " ",
            "setup_ivy_model &&",
        ]

        self.logger.info("Updating Ivy tool...")

        if self.protocol.name in ["quic", "apt"]:
            update_command = update_for_quic_apt_cmd + update_command

        self.logger.info(f"Executing command: {update_command}")

        return update_command + setup_ivy_model_cmd

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
        self.logger.debug(
            f"Generating compilation commands for service: {self.service_name}"
        )

        self.logger.debug(f"Test to compile: {self.test_to_compile}")

        protocol_env = self.service_config_to_test.implementation.version.env
        global_env = self.service_config_to_test.implementation.environment
        self.environments = {**global_env, **protocol_env, "TEST_TYPE": (
            "client" if self.role.name == "server" else "server"
        )}

        # TODO refine the config
        # self.environments["ZERORTT_TEST"]

        if self.role == RoleEnum.server:
            available_tests = (
                self.service_config_to_test.implementation.version.server.tests
            )
        else:
            available_tests = (
                self.service_config_to_test.implementation.version.client.tests
            )

        self.logger.debug(f"Test to compile: {self.test_to_compile}")
        self.logger.debug(f"Test information: {available_tests}")
        self.logger.debug(f"Environments: {self.environments}")
        self.logger.debug(f"Protocol: {self.protocol}")
        self.logger.debug(f"Version: {self.service_version.name}")
        if self.test_to_compile not in available_tests.keys():
            self.logger.error(
                f"Test '{self.test_to_compile}' not found in configuration."
            )
            exit(1)
        return self.update_ivy_tool() + self.build_tests()

    def build_tests(self) -> List[str]:
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
            f"Mode: {self.role.name} for test: {self.test_to_compile} in {self.service_config_to_test.implementation.version.parameters['tests_dir']['value']}"
        )
        file_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/",
            self.protocol.name,
            self.service_config_to_test.implementation.version.parameters["tests_dir"][
                "value"
            ],
            oppose_role(self.role.name) + "_tests",
        )
        self.logger.debug(f"Building file: {file_path}")
        cmd = [
            f"cd {file_path};",
            f"PYTHONPATH=$$PYTHON_IVY_DIR ivyc trace=false show_compiled=false target=test test_iters={self.service_config_to_test.implementation.parameters.internal_iterations_per_test.value} {self.test_to_compile}.ivy >> /app/logs/ivy_setup.log 2>&1; ",
        ]
        self.logger.info(f"Tests compilation command: {cmd}")
        mv_command = [
            f"cp {os.path.join(file_path, self.test_to_compile)}* {os.path.join('/opt/panther_ivy/protocol-testing/', self.protocol.name, self.service_config_to_test.implementation.parameters.tests_build_dir.value)}; "
        ]
        self.logger.info(f"Moving built files: {mv_command}")
        return (
                cmd
                + (["(ls >> /app/logs/ivy_setup.log 2>&1 ;"] if True else ["()"])
                + [" "]
                + mv_command
                + (
                    [
                        f"ls {os.path.join('/opt/panther_ivy/protocol-testing/', self.protocol.name, self.service_config_to_test.implementation.parameters.tests_build_dir.value)} >> /app/logs/ivy_setup.log 2>&1 ;) "
                    ]
                    if True
                    else [")"]
                )
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
            f"Generating deployment commands for service: {self.service_name} with service parameters: {self.service_config_to_test}"
        )

        self.ivy_log_level = (
            self.service_config_to_test.implementation.parameters.log_level
        )
        # Create the command list
        self.logger.debug(f"Role: {self.role}, Version: {self.service_version.name}")

        # Determine if network interface parameters should be included based on environment
        include_interface = True
        # TODO ensure that the parameters are correctly set
        if self.role == RoleEnum.server:
            params = self.service_config_to_test.implementation.version.server
        # For the client, include target and message if available
        elif self.role == RoleEnum.client:
            params = self.service_config_to_test.implementation.version.client

        for param in self.service_config_to_test.implementation.parameters:
            params[param] = self.service_config_to_test.implementation.parameters[
                param
            ].value

        for param in self.service_config_to_test.implementation.version.parameters:
            params[param] = (
                self.service_config_to_test.implementation.version.parameters[
                    param
                ].value
            )

        params["target"] = self.service_config_to_test.protocol.target
        params["server_addr"] = (
            "$$TARGET_IP_HEX"
            if oppose_role(self.role.name) == "server"
            else "$$IVY_IP_HEX"
        )
        params["client_addr"] = (
            "$$TARGET_IP_HEX"
            if oppose_role(self.role.name) == "client"
            else "$$IVY_IP_HEX"
        )
        params["is_client"] = oppose_role(self.role.name) == "client"
        params["test_name"] = self.test_to_compile
        params["timeout_cmd"] = f"timeout {self.service_config_to_test.timeout} "
        self.working_dir = self.protocol_model_path

        # Conditionally include network interface parameters
        if not include_interface:
            params["network"].pop("interface", None)

        ivy_include_protocol_testing_dir = os.path.abspath(
            f"{str(self._plugin_dir)}/testers/panther_ivy/ivy/include/1.7"
        )
        local_protocol_testing_dir = os.path.abspath(
            f"{str(self._plugin_dir)}/testers/panther_ivy/protocol-testing/"
            + self.protocol.name
        )
        self.volumes = self.volumes + [
            ivy_include_protocol_testing_dir + ":/opt/panther_ivy/ivy/include/1.7",
            local_protocol_testing_dir
            + ":/opt/panther_ivy/protocol-testing/"
            + self.protocol.name,
            "shared_logs:/app/sync_logs",
        ]

        # Render the appropriate template
        try:
            template_name = f"{self.protocol.name}/{str(oppose_role(self.role.name))}_command.jinja"
            return super().render_commands(params, template_name)

        except Exception as e:
            self.logger.error(
                f"Failed to render command for service '{self.service_config_to_test.name}': {e}\n{traceback.format_exc()}"
            )
            raise e

    def __str__(self) -> str:
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"

    def __repr__(self):
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"
