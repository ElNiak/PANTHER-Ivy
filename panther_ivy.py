# PANTHER-SCP/panther/plugins/services/implementations/ivy_rfc9000/service_manager.py

import subprocess
import logging
import os
from typing import Any, Dict, Optional
import yaml
import traceback
from plugins.services.testers.tester_interface import ITesterManager
from plugins.plugin_loader import PluginLoader
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template


# TODO Tom create test template for QUIC implementations new users
# TODO add more attributes
# TODO make the debug event working
class PantherIvyServiceManager(ITesterManager):
    def __init__(
        self,
        type: str,
        protocol: str,
        implementation_name: str,
    ):
        super().__init__(type, protocol,implementation_name)
        
        self.protocol = None
        self.protocol_version = None
        self.protocol_model_path = None

        

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

    def get_implementation_name(self) -> str:
        return "panther_ivy"

    def get_service_name(self) -> str:
        return self.service_name

    def validate_config(self):
        """
        Validates the loaded implementation configuration.
        """

        def keys_exists(element, keys):
            """
            Check if *keys (nested) exists in `element` (dict).
            """
            if not isinstance(element, dict):
                raise AttributeError("keys_exists() expects dict as first argument.")
            if len(keys) == 0:
                raise AttributeError(
                    "keys_exists() expects at least two arguments, one given."
                )

            _element = element
            for key in keys:
                try:
                    _element = _element[key]
                except KeyError:
                    return False
            return True

        if not self.config:
            self.logger.error("Implementation configuration is empty.")
            raise ValueError("Empty implementation configuration.")
        # Additional validation can be implemented here
        # For example, check required keys are present
        # required_keys = [["client",'seed'], ["client",'seed']]
        # for key in required_keys:
        #     if not keys_exists(self.config, key):
        #         self.logger.error(f"Missing required key '{key}' in configuration.")
        #         raise KeyError(f"Missing required key '{key}' in configuration.")

    def prepare(self, plugin_loader: Optional[PluginLoader] = None):
        """
        Prepares the Ivy tester service manager.
        """
        self.logger.info("Preparing Ivy tester service manager...")
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
        self.logger.info("Ivy tester service manager prepared.")

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

    def update_ivy_tool(self):
        """
        Update Ivy tool and include paths.
        Note: ":" cannot be used in the command as it is used to separate commands.
        This script is compatible with /bin/sh syntax.
        """
        update_command = """
        update_ivy_tool() {
            echo "Updating Ivy tool..." >> /app/logs/ivy_setup.log;
            cd "/opt/panther_ivy" || exit 1;
            sudo python3.10 setup.py install >> /app/logs/ivy_setup.log 2>&1 &&
            cp lib/libz3.so submodules/z3/build/python/z3 >> /app/logs/ivy_setup.log 2>&1 &&
            echo "Copying updated Ivy files..." >> /app/logs/ivy_setup.log &&
            find /opt/panther_ivy/ivy/include/1.7/ -type f -name "*.ivy" -exec cp {} /usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/ \; >> /app/logs/ivy_setup.log 2>&1 &&
            echo "Copying updated Z3 files..." >> /app/logs/ivy_setup.log &&
            cp -f -a /opt/panther_ivy/ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" >> /app/logs/ivy_setup.log 2>&1;
        }

        update_ivy_tool &&
        """

        update_for_quic_apt_cmd = """
        echo "Copying QUIC libraries..." >> /app/logs/ivy_setup.log &&
        cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/" &&
        cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/" &&
        cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls.h" &&
        cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h" &&
        cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls" &&
        cp -f "{protocol_model_path}/quic_utils/quic_ser_deser.h" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/" &&
        """.format(
            protocol_model_path=self.protocol_model_path,
        )

        setup_ivy_model_cmd = """
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
        """.format(
            protocol_model_path=self.protocol_model_path,
            log_level_ivy="1" if self.ivy_log_level == "DEBUG" else "10",
        ).strip()

        self.logger.info("Updating Ivy tool...")

        if self.protocol in {"quic", "apt"}:
            update_command = update_for_quic_apt_cmd + update_command

        self.logger.info(f"Executing command: {update_command}")

        return update_command + setup_ivy_model_cmd

    def generate_compilation_commands(
        self, service_params: Dict[str, Any], environment: str
    ) -> Dict[str, Any]:
        self.logger.debug(
            f"Generating compilation commands for service: {service_params}"
        )
        self.logger.debug(f"Environment: {environment}")

        self.protocol_version = service_params.get("protocol").get("version")
        self.role = service_params.get("role")

        test_to_compile = service_params.get("protocol").get("test")

        protocol_env = (
            self.config.get("panther_ivy", {}).get(self.protocol, {}).get("env", {})
        )
        global_env = self.config.get("panther_ivy", {}).get("env", {})
        self.environments = {**global_env, **protocol_env}

        # TODO refine the config
        self.environments["TEST_TYPE"] = "client" if self.role == "server" else "server"
        # self.environments["ZERORTT_TEST"]

        test_to_compile_information = (
            self.config.get("panther_ivy", {})
            .get(self.protocol, {})
            .get("versions", {})
            .get(self.protocol_version, {})
            .get(self.role, {})
            .get("tests", {})
            .get(test_to_compile, {})
        )

        self.logger.debug(f"Test to compile: {test_to_compile}")
        self.logger.debug(f"Test information: {test_to_compile_information}")
        self.logger.debug(f"Environments: {self.environments}")
        self.logger.debug(f"Protocol: {self.protocol}")
        self.logger.debug(f"Version: {self.protocol_version}")
        if not test_to_compile_information:
            self.logger.error(f"Test '{test_to_compile}' not found in configuration.")
            exit(1)
        return (
            self.update_ivy_tool() + " (" + self.build_tests(test_to_compile) + " )"
        )  # TODO

    def oppose_role(self, role):
        # TODO fix logic in ivy itself
        return "client" if role == "server" else "server"

    def build_tests(self, test):
        # TODO make more flexible, for now only work in docker "/opt/panther_ivy/"
        """Compile and prepare the tests."""
        self.logger.info("Compiling tests...")
        self.logger.info(f"Mode: {self.role} for test: {test}")
        file_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/",
            self.protocol,
            self.config["panther_ivy"][self.protocol]["parameters"]["tests_dir"][
                "value"
            ],
            self.oppose_role(self.role) + "_tests",
        )
        self.logger.debug(f"Building file: {file_path}")
        cmd = f"cd {file_path}; PYTHONPATH=$$PYTHON_IVY_DIR ivyc trace=false show_compiled=false target=test test_iters={self.config['panther_ivy']['parameters']['internal_iterations_per_test']['value']} {test}.ivy >> /app/logs/ivy_setup.log 2>&1; "
        self.logger.info(f"Tests compilation command: {cmd}")
        mv_command = f"cp {os.path.join(file_path,test)}* {os.path.join('/opt/panther_ivy/protocol-testing/',self.protocol, self.config['panther_ivy']['parameters']['tests_build_dir']['value'])}; "
        self.logger.info(f"Moving built files: {mv_command}")
        return (
            cmd
            + ("ls >> /app/logs/ivy_setup.log 2>&1 ;" if True else "")
            + " "
            + mv_command
            + (
                f"ls {os.path.join('/opt/panther_ivy/protocol-testing/',self.protocol, self.config['panther_ivy']['parameters']['tests_build_dir']['value'])} >> /app/logs/ivy_setup.log 2>&1 ; "
                if True
                else ""
            )
        )

    def load_config(self) -> dict:
        """
        Loads the YAML configuration file.
        """
        config_file = Path(self.config_path)
        if not config_file.exists():
            self.logger.error(
                f"Configuration file '{self.config_path}' does not exist."
            )
            return {}
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            self.logger.info(f"Loaded configuration from '{self.config_path}'")
            return config
        except Exception as e:
            self.logger.error(
                f"Failed to load configuration: {e}\n{traceback.format_exc()}"
            )
            exit(1)

    def generate_deployment_commands(
        self, service_params: Dict[str, Any], environment: str
    ) -> Dict[str, Any]:
        """
        Generates deployment commands and collects volume mappings based on service parameters.

        :param service_params: Parameters specific to the service.
        :param environment: The environment in which the services are being deployed.
        :return: A dictionary with service name as key and a dictionary containing command and volumes.
        """
        # TODO add developper volumes -> do not rebuilt the docker in that case !
        self.logger.debug(
            f"Generating deployment commands for service: {service_params}"
        )

        self.role = service_params.get("role")
        self.protocol_version = service_params.get("version", "rfc9000")
        self.protocol = service_params.get("protocol").get("name")
        self.ivy_log_level = (
            self.config.get("panther_ivy")
            .get("parameters")
            .get("log_level")
            .get("value")
        )

        self.protocol_model_path = os.path.join(
            "/opt/panther_ivy/protocol-testing/", self.protocol
        )

        version_config = (
            self.config.get("panther_ivy", {})
            .get(self.protocol, {})
            .get("versions", {})
            .get(self.protocol_version, {})
        )

        # Build parameters for the command template
        params = {
            "test_name": service_params.get("protocol").get("test"),
            # TODO pass that to the environment
            # "tshark_timeout": self.config.get("panther_ivy").get("parameters").get("timeout").get("value") - 10,
            "timeout_cmd": f"timeout {self.config.get('panther_ivy').get('parameters').get('timeout').get('value')} ",  # Example timeout
            "prefix": "",
            "build_dir": self.config.get("panther_ivy")
            .get("parameters")
            .get("tests_build_dir")
            .get("value"),
            "seed": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("seed")
            .get("value"),
            "the_cid": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("the_cid")
            .get("value"),
            "server_port": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("server_port")
            .get("value"),
            "version": self.protocol_version,
            "iversion": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("iversion")
            .get("value"),
            "server_addr": (
                "$$TARGET_IP_HEX"
                if self.oppose_role(self.role) == "server"
                else "$$IVY_IP_HEX"
            ),  # elf.config.get("panther_ivy").get(self.protocol).get("parameters").get("server_addr").get("value"),
            "server_cid": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("server_cid")
            .get("value"),
            "client_port": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("client_port")
            .get("value"),
            "client_port_alt": self.config.get("panther_ivy")
            .get(self.protocol)
            .get("parameters")
            .get("client_port_alt")
            .get("value"),
            "client_addr": (
                "$$TARGET_IP_HEX"
                if self.oppose_role(self.role) == "client"
                else "$$IVY_IP_HEX"
            ),  #  self.config.get("panther_ivy").get(self.protocol).get("parameters").get("client_addr").get("value"),
            "modify_packets": "false",
            "name": service_params.get("name"),
            # TODO managed paired tests
            # "paired_tests": self.config.get("ivy", {}).get("paired_tests", {}),
            "iteration": self.config.get("panther_ivy")
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
                "destination": service_params.get(
                    "target",
                    version_config.get(self.role, {})
                    .get("network", {})
                    .get("destination", "picoquic_server"),
                ),
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
        # if not service_params.get('generate_new_certificates', False):
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
                self.config.get("panther_ivy", {})
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
            command_str =  command.replace("\t", " ").replace("\n", " ").strip()
            working_dir = self.protocol_model_path

            service_name = service_params.get("name")
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
                    "timeout": self.config.get("panther_ivy")
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
        return f"(Ivy tester Service Manager - {self.config})"

    def __repr__(self):
        return f"(Ivy tester Service Manager - {self.config})"
