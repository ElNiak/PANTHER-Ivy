# PANTHER-SCP/panther/plugins/services/implementations/ivy_rfc9000/service_manager.py

import subprocess
import logging
import os
from typing import Any, Dict, List, Optional
import yaml
import traceback
from config.config_experiment_schema import ServiceConfig
from plugins.services.testers.panther_ivy.config_schema import PantherIvyConfig
from plugins.services.testers.tester_interface import ITesterManager
from plugins.plugin_loader import PluginLoader
from pathlib import Path
from plugins.protocols.config_schema import ProtocolConfig, RoleEnum


# TODO Tom create test template for QUIC implementations new users
# TODO add more attributes
# TODO make the debug event working
class PantherIvyServiceManager(ITesterManager):
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
        self.test_to_compile = self.service_config_to_test.implementation.test
        self.protocol = protocol
        self.protocol_model_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/", self.protocol.name
        )
        self.ivy_log_level = (
            self.service_config_to_test.implementation.parameters.log_level
        )
        self.initialize_commands()

    def initialize_commands(self):
        """
        Initializes the commands to be executed
        """
        self.run_cmd = {
            "pre_compile_cmds": self.generate_pre_compile_commands(),
            "compile_cmds": self.generate_compile_commands(),
            "pre_run_cmds": self.generate_pre_run_commands(),
            "run_cmd": self.generate_run_command(),
            "post_run_cmds": self.generate_post_run_commands(),
        }
        self.logger.debug(f"Run commands: {self.run_cmd}")

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
            super().generate_compile_commands() + self.generate_compilation_commands() + [" && "] + [" (touch /app/sync_logs/ivy_ready.log ) && "]
        )

    def generate_pre_run_commands(self):
        """
        Generates pre-run commands.
        """
        return super().generate_pre_run_commands() + [f"cd {self.protocol_model_path};"]

    def generate_run_command(self):
        """
        Generates the run command.
        """
        cmd_args = self.generate_deployment_commands()
        return {
            "working_dir": self.protocol_model_path,
            "command_binary": os.path.join(self.service_config_to_test.implementation.parameters.tests_build_dir.value + self.test_to_compile),
            "command_args": cmd_args,
            "timeout": self.service_config_to_test.timeout,
        }

    def generate_post_run_commands(self):
        """
        Generates post-run commands.
        """
        return super().generate_post_run_commands() + [
            f"&& cp {os.path.join(self.service_config_to_test.implementation.parameters.tests_build_dir.value + self.test_to_compile)} /app/logs/{self.test_to_compile};"
        ]

    def get_base_url(self, service_name: str) -> str:
        """
        Returns the base URL for the given service.
        """
        # Assuming services are accessible via localhost and mapped ports
        # You might need to adjust this based on your actual setup
        port_mappings = {
            "ivy_server": 8080,
            "ivy_client": 8081,
        }
        port = port_mappings.get(service_name, None)
        if port:
            return f"http://localhost:{port}/"
        else:
            self.logger.error(f"No port mapping found for service '{service_name}'")
            return ""

    def get_service_name(self) -> str:
        return self.service_name

    def prepare(self, plugin_loader: Optional[PluginLoader] = None):
        """
        Prepares the Ivy testers service manager.
        """
        self.logger.info("Preparing Ivy testers service manager...")
        self.build_submodules()

        protocol_testing_dir = os.path.abspath(
            "plugins/services/testers/panther_ivy/protocol-testing/"
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

        plugin_loader.build_docker_image(self.get_implementation_name())
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

    def prepare_environment():
        pass

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
        """

        # update_ivy_tool() {
        #     echo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;
        #     cd "/opt/panther_ivy" || exit 1;
        #     sudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&
        #     cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&
        #     echo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log &&
        #     find /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ \; >> /app/logs/ivy_setup.log 2>&1 &&
        #     echo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log &&
        #     cp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;
        # }
        # update_ivy_tool &&
        update_command = [
            " ",
            "update_ivy_tool() {",
            '\techo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;',
            '\tcd "/opt/panther_ivy" || exit 1;',
            "\tsudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&",
            "\tcp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&",
            '\techo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log;',
            '\tfind /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ \\; >> /app/logs/ivy_setup.log 2>&1;',
            '\techo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log;',
            '\tcp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;',
            "}",
            " ",
            "update_ivy_tool &&",
        ]

        # echo "Copying QUIC libraries..." >> /app/logs/ivy_setup.log &&
        # cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" &&
        # cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/" &&
        # cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls.h" &&
        # cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h" &&
        # cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls" &&
        # cp -f "{protocol_model_path}/quic_utils/quic_ser_deser.h" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/" &&
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

        # remove_debug_events() {{
        #     echo "Removing debug events..." >> /app/logs/ivy_setup.log;
        #     printf "%s\\n" "$@" | xargs -I {{}} sh -c "
        #         if [ -f \\"\\$1\\" ]; then
        #             sed -i \\"s/^\\\\([^#]*debug_event.*\\\\)/##\\\\1/\\" \\"\$1\\";
        #         else
        #             echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
        #         fi
        #     " _ {{}};
        # }}
        # restore_debug_events() {{
        #     echo "Restoring debug events..." >> /app/logs/ivy_setup.log;
        #     printf "%s\\n" "$@" | xargs -I {{}} sh -c "
        #         if [ -f \\"\\$1\\" ]; then
        #             sed -i \\"s/^##\\\\(.*debug_event.*\\\\)/\\\\1/\\" \\"\\\$1\\";
        #         else
        #             echo \\"File not found - \\$1\\" >> /app/logs/ivy_setup.log;
        #         fi
        #     " _ {{}};
        # }}
        # setup_ivy_model() {{
        #     echo "Setting up Ivy model..." >> /app/logs/ivy_setup.log &&
        #     echo "Updating include path of Python with updated version of the project from {protocol_model_path}" >> /app/logs/ivy_setup.log &&
        #     echo "Finding .ivy files..." >> /app/logs/ivy_setup.log &&
        #     find "{protocol_model_path}" -type f -name "*.ivy" -exec sh -c "
        #         echo \\"Found Ivy file - \\$1\\" >> /app/logs/ivy_setup.log;
        #         if [ {log_level_ivy} -gt 10 ]; then
        #             echo \\"Removing debug events from \\$1\\" >> /app/logs/ivy_setup.log;
        #             remove_debug_events \\"\\$1\\";
        #         fi;
        #         echo \\"Copying Ivy file to include path...\\" >> /app/logs/ivy_setup.log;
        #         cp -f \\"\\$1\\" \\"/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/\\";
        #     " _ {{}} \;;
        #     ls -l /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ >> /app/logs/ivy_setup.log;
        # }}
        # setup_ivy_model &&
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
        self.logger.debug(
            f"Generating compilation commands for service: {self.service_name}"
        )

        self.logger.debug(f"Test to compile: {self.test_to_compile}")

        protocol_env = self.service_config_to_test.implementation.version.env
        global_env = self.service_config_to_test.implementation.environment
        self.environments = {**global_env, **protocol_env}

        # TODO refine the config
        self.environments["TEST_TYPE"] = (
            "client" if self.role.name == "server" else "server"
        )
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
        self.logger.debug(f"Version: {self.service_version}")
        if self.test_to_compile not in available_tests.keys():
            self.logger.error(
                f"Test '{self.test_to_compile}' not found in configuration."
            )
            exit(1)
        return self.update_ivy_tool() + self.build_tests() 

    def oppose_role(self, role):
        # TODO fix logic in ivy itself
        return "client" if role == "server" else "server"

    def build_tests(self) -> List[str]:
        # TODO make more flexible, for now only work in docker "/opt/panther_ivy/"
        """Compile and prepare the tests."""
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
            self.oppose_role(self.role.name) + "_tests",
        )
        self.logger.debug(f"Building file: {file_path}")
        cmd = [
            f"cd {file_path};",
            f"PYTHONPATH=$$PYTHON_IVY_DIR ivyc trace=false show_compiled=false target=test test_iters={self.service_config_to_test.implementation.parameters.internal_iterations_per_test.value} {self.test_to_compile}.ivy >> /app/logs/ivy_setup.log 2>&1; ",
        ]
        self.logger.info(f"Tests compilation command: {cmd}")
        mv_command = [
            f"cp {os.path.join(file_path,self.test_to_compile)}* {os.path.join('/opt/panther_ivy/protocol-testing/',self.protocol.name, self.service_config_to_test.implementation.parameters.tests_build_dir.value)}; "
        ]
        self.logger.info(f"Moving built files: {mv_command}")
        return (
            cmd
            + (["(ls >> /app/logs/ivy_setup.log 2>&1 ;"] if True else ["()"])
            + [" "]
            + mv_command
            + (
                [
                    f"ls {os.path.join('/opt/panther_ivy/protocol-testing/',self.protocol.name, self.service_config_to_test.implementation.parameters.tests_build_dir.value)} >> /app/logs/ivy_setup.log 2>&1 ;) "
                ]
                if True
                else [")"]
            )
        )

    def load_config(self) -> dict:
        """
        Loads the YAML configuration file.
        """
        config_file = Path(self.service_config_to_test_path)
        if not config_file.exists():
            self.logger.error(
                f"Configuration file '{self.service_config_to_test_path}' does not exist."
            )
            return {}
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            self.logger.info(
                f"Loaded configuration from '{self.service_config_to_test_path}'"
            )
            return config
        except Exception as e:
            self.logger.error(
                f"Failed to load configuration: {e}\n{traceback.format_exc()}"
            )
            exit(1)

    def generate_deployment_commands(self) -> str:
        """
        Generates deployment commands and collects volume mappings based on service parameters.

        :param service_params: Parameters specific to the service.
        :param environment: The environment in which the services are being deployed.
        :return: A dictionary with service name as key and a dictionary containing command and volumes.
        """
        # TODO add developper volumes -> do not rebuilt the docker in that case !
        self.logger.debug(
            f"Generating deployment commands for service: {self.service_name} with service parameters: {self.service_config_to_test}"
        )

        self.ivy_log_level = (
            self.service_config_to_test.implementation.parameters.log_level
        )
        # Create the command list
        self.logger.debug(f"Role: {self.role}, Version: {self.service_version}")

        # Determine if network interface parameters should be included based on environment
        # TODO
        # include_interface = environment not in ["docker_compose"]
        include_interface = True

        # Build parameters for the command template
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
            if self.oppose_role(self.role.name) == "server"
            else "$$IVY_IP_HEX"
        )
        params["client_addr"] = (
            "$$TARGET_IP_HEX"
            if self.oppose_role(self.role.name) == "client"
            else "$$IVY_IP_HEX"
        )
        params["is_client"] = self.oppose_role(self.role.name) == "client"
        params["test_name"] = self.test_to_compile
        params["timeout_cmd"] = f"timeout {self.service_config_to_test.timeout} " 
        self.working_dir = self.protocol_model_path
        # Conditionally include network interface parameters
        if not include_interface:
            params["network"].pop("interface", None)

        # Collect volume mappings
        volumes = []
        # Collect volume mappings
        ivy_include_protocol_testing_dir = os.path.abspath(
            "plugins/services/testers/panther_ivy/ivy/include/1.7"
        )
        local_protocol_testing_dir = os.path.abspath(
            "plugins/services/testers/panther_ivy/protocol-testing/"
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
            template_name = f"{str(self.oppose_role(self.role.name))}_command.jinja"
            self.logger.debug(
                f"Rendering command using template '{template_name}' with parameters: {params}"
            )
            template = self.jinja_env.get_template(template_name)
            command = template.render(**params)

            # Clean up the command string
            command_str = command.replace("\t", " ").replace("\n", " ").strip()

            service_name = self.service_config_to_test.name
            self.logger.debug(f"Generated command for '{service_name}': {command_str}")
            return command_str

        except Exception as e:
            self.logger.error(
                f"Failed to render command for service '{self.service_config_to_test.name}': {e}\n{traceback.format_exc()}"
            )
            raise e

        self.logger.debug(
            f"Generating deployment commands for service: {service_params}"
        )

        self.role = service_params.protocol.role
        self.protocol_version = service_params.protocol.version
        self.protocol = service_params.protocol.name
        self.ivy_log_level = (
            self.service_config_to_test.get("panther_ivy")
            .get("parameters")
            .get("log_level")
            .get("value")
        )

        self.protocol_model_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/", self.protocol
        )

        version_config = (
            self.service_config_to_test.get("panther_ivy", {})
            .get(self.protocol, {})
            .get("versions", {})
            .get(self.protocol_version, {})
        )

        # Build parameters for the command template
        params = {
            "test_name": service_params.implementation.name,
            # TODO pass that to the environment
            # "tshark_timeout": self.service_config_to_test.get("panther_ivy").get("parameters").get("timeout").get("value") - 10,
            "timeout_cmd": f"timeout {self.service_config_to_test.get('panther_ivy').get('parameters').get('timeout').get('value')} ",  # Example timeout
            "prefix": "",
            "build_dir": self.service_config_to_test.get("panther_ivy")
            .get("parameters")
            .get("tests_build_dir")
            .get("value"),
            "seed": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("seed")
            .get("value"),
            "the_cid": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("the_cid")
            .get("value"),
            "server_port": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("server_port")
            .get("value"),
            "version": self.protocol_version,
            "iversion": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("iversion")
            .get("value"),
            "server_addr": (
                "$$TARGET_IP_HEX"
                if self.oppose_role(self.role) == "server"
                else "$$IVY_IP_HEX"
            ),  # elf.config.get("panther_ivy").get(self.protocol).get("parameters").get("server_addr").get("value"),
            "server_cid": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("server_cid")
            .get("value"),
            "client_port": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("client_port")
            .get("value"),
            "client_port_alt": self.service_config_to_test.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("client_port_alt")
            .get("value"),
            "client_addr": (
                "$$TARGET_IP_HEX"
                if self.oppose_role(self.role) == "client"
                else "$$IVY_IP_HEX"
            ),  #  self.service_config_to_test.get("panther_ivy").get(self.protocol).get("parameters").get("client_addr").get("value"),
            "modify_packets": "false",
            "name": service_params.name,
            # TODO managed paired tests
            # "paired_tests": self.service_config_to_test.get("ivy", {}).get("paired_tests", {}),
            "iteration": self.service_config_to_test.get("panther_ivy")
            .get("parameters")
            .get("value"),  # Example iteration for testing
            "is_client": self.oppose_role(self.role) == "client",
            "certificates": {
                "cert_param": version_config.get(self.role, {})
                .get("certificates", {})
                .get("cert", {})
                .get("param"),
                "cert_file": version_config.get(self.role, {})
                .get("certificates", {})
                .get("cert", {})
                .get("file"),
                "cert_local_file": version_config.get(self.role, {})
                .get("certificates", {})
                .get("cert", {})
                .get("local_file"),
                "key_param": version_config.get(self.role, {})
                .get("certificates", {})
                .get("key", {})
                .get("param"),
                "key_file": version_config.get(self.role, {})
                .get("certificates", {})
                .get("key", {})
                .get("file"),
                "key_local_file": version_config.get(self.role, {})
                .get("certificates", {})
                .get("key", {})
                .get("local_file"),
            },
            "ticket_file": {
                "param": version_config.get(self.role, {})
                .get("ticket_file", {})
                .get("param"),
                "file": version_config.get(self.role, {})
                .get("ticket_file", {})
                .get("file"),
                "local_file": version_config.get(self.role, {})
                .get("ticket_file", {})
                .get("local_file"),
            },
            "logging": version_config.get(self.role, {}).get("logging", {}),
            "protocol": {
                "alpn": version_config.get(self.role, {})
                .get("protocol", {})
                .get("alpn", {}),
                "additional_parameters": version_config.get(self.role, {})
                .get("protocol", {})
                .get("additional_parameters", ""),
            },
            "network": {
                "interface": version_config.get(self.role, {})
                .get("network", {})
                .get("interface", {}),
                "port": version_config.get(self.role, {})
                .get("network", {})
                .get("port", 4443),
                "destination": service_params.protocol.target,
            },
        }
        # TODO add timeout parameter
        # TODO setup working directory

        # Collect volume mappings
        ivy_include_protocol_testing_dir = os.path.abspath(
            "plugins/services/testers/panther_ivy/ivy/include/1.7"
        )
        local_protocol_testing_dir = os.path.abspath(
            "plugins/services/testers/panther_ivy/protocol-testing/" + self.protocol
        )
        volumes = [
            ivy_include_protocol_testing_dir + ":/opt/panther_ivy/ivy/include/1.7",
            local_protocol_testing_dir
            + ":/opt/panther_ivy/protocol-testing/"
            + self.protocol,
            "shared_logs:/app/sync_logs",
        ]

        # Only add certificate volumes if the user doesn't want to generate new certificates
        # if not service_params.generate_new_certificates:
        #     # Certificates
        #     volumes.append({
        #         "local": os.path.abspath(params["certificates"]["cert_local_file"]),
        #         "container": params["certificates"]["cert_file"]
        #     })
        #     volumes.append({
        #         "local": os.path.abspath(params["certificates"]["key_local_file"]),
        #         "container": params["certificates"]["key_file"]
        #     })

        # Ticket file (if applicable)
        if params["ticket_file"]["local_file"]:
            volumes.append(
                {
                    "local": os.path.abspath(params["ticket_file"]["local_file"]),
                    "container": params["ticket_file"]["file"],
                }
            )

        try:
            template_name = f"{self.oppose_role(self.role)}_command.jinja"
            self.logger.debug(
                f"Rendering command using template '{template_name}' with parameters: {params}"
            )
            template = self.jinja_env.get_template(template_name)
            command = template.render(**params)

            # Generate compilation commands
            compilation_command = ""
            if (
                self.service_config_to_test.get("panther_ivy", {})
                .get("parameters", {})
                .get("compile_tests", {})
                .get("value", False)
            ):
                compilation_command = self.generate_compilation_commands(
                    service_params, environment
                )
            # Clean up the command string
            compilation_command = (
                compilation_command + " && " + " ( touch /app/sync_logs/ivy_ready )"
            )
            command_str = command.replace("\t", " ").replace("\n", " ").strip()
            working_dir = self.protocol_model_path

            service_name = service_params.name
            self.logger.debug(
                f"Generated command for '{service_name}': {command_str} with {compilation_command}"
            )
            return {
                service_name: {
                    "command_binary": params["build_dir"] + "/" + params["test_name"],
                    "args": command_str,
                    "volumes": volumes,
                    "working_dir": working_dir,
                    "compilation_command": compilation_command,
                    "environment": self.environments,
                    "timeout": self.service_config_to_test.get("panther_ivy")
                    .get("parameters")
                    .get("timeout")
                    .get("value"),
                }
            }
        except Exception as e:
            self.logger.error(
                f"Failed to render command: {e}\n{traceback.format_exc()}"
            )
            raise e

    def __str__(self) -> str:
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"

    def __repr__(self):
        return f"(Ivy testers Service Manager - {self.service_config_to_test})"
