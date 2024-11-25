# PANTHER-SCP/panther/plugins/implementations/ivy_rfc9000/service_manager.py

import subprocess
import logging
import os
from typing import Any, Dict, Optional
import yaml
import traceback    
from core.utils.plugin_loader import PluginLoader
from plugins.implementations.service_manager_interface import IServiceManager
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

# TODO Tom create test template for QUIC implementations new users
# TODO add more attributes
class PantherIvyServiceManager(IServiceManager):
    def __init__(self,implementation_config_path: str = "plugins/implementations/panther_ivy/", 
                      protocol_templates_dir: str     = "plugins/implementations/panther_ivy/templates/"):
        self.process = None
        self.logger = logging.getLogger("IvyServiceManager")
        self.config_path = implementation_config_path
        self.config = self.load_config()
        self.service_name = None
        self.validate_config()
        self.templates_dir = protocol_templates_dir
        self.jinja_env = Environment(loader=FileSystemLoader(self.templates_dir))
        self.jinja_env.trim_blocks   = True
        self.jinja_env.lstrip_blocks = True
        # Debugging: List files in templates_dir
        if not os.path.isdir(self.templates_dir):
            self.logger.error(f"Templates directory '{self.templates_dir}' does not exist.")
        else:
            templates = os.listdir(self.templates_dir)
            self.logger.debug(f"Available templates in '{self.templates_dir}': {templates}")
    
    def get_base_url(self, service_name: str) -> str:
        """
        Returns the base URL for the given service.
        """
        # Assuming services are accessible via localhost and mapped ports
        # You might need to adjust this based on your actual setup
        port_mappings = {
            'ivy_server': 8080,
            'ivy_client': 8081,
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
            '''
            Check if *keys (nested) exists in `element` (dict).
            '''
            if not isinstance(element, dict):
                raise AttributeError('keys_exists() expects dict as first argument.')
            if len(keys) == 0:
                raise AttributeError('keys_exists() expects at least two arguments, one given.')

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
        
        # TODO load the configuration file: get the protocol name and the version + tests + versions
        
        plugin_loader.build_docker_image(self.get_implementation_name())
        self.logger.info("Ivy tester service manager prepared.")

    def build_submodules(self):
        current_dir = os.getcwd()
        os.chdir(os.path.dirname(__file__))
        try:
            self.logger.info(f"Initializing submodules (from {os.getcwd()})")
            subprocess.run(["git", "submodule", "update", "--init", "--recursive"], check=True)
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

    def remove_debug_events(self, files):
        remove_debug_events_cmd = """
        restore_debug_events() {
            echo "Restoring debug events"
            for file in "$@"; do
                if [[ -f "$file" ]]; then
                    while IFS= read -r line; do
                        if [[ "$line" =~ ^##.*debug_event ]]; then
                            echo "${line:2}"
                        else
                            echo "$line"
                        fi
                    done < "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
                else
                    echo "File not found: $file"
                fi
            done
        }
        # restore_debug_events "file1.txt" "file2.txt"
        """
        self.logger.info("Removing debug events")
        for file in files:
            with open(file, "r") as f:
                lines = f.readlines()
            with open(file, "w") as f:
                for line in lines:
                    if "debug_event" in line and not line.lstrip().startswith("##"):
                        self.log.debug(f"Removing debug event: {line}")
                        f.write("##" + line)
                    else:
                        f.write(line)

    def restore_debug_events(self, files):
        self.logger.info("Restoring debug events")
        remove_debug_events_cmd = """
        remove_debug_events() {
            echo "Removing debug events"
            for file in "$@"; do
                if [[ -f "$file" ]]; then
                    while IFS= read -r line; do
                        if [[ "$line" == *"debug_event"* && ! "$line" =~ ^[[:space:]]*## ]]; then
                            echo "##$line"
                        else
                            echo "$line"
                        fi
                    done < "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
                else
                    echo "File not found: $file"
                fi
            done
        }
        # remove_debug_events "file1.txt" "file2.txt"
        """
        
    
    def update_ivy_tool(self):
        """Update Ivy tool and include paths."""
        update_command = """
        update_ivy_tool() {
            echo "Updating Ivy tool..."

            # Change directory to panther_ivy source
            cd "/opt/panther_ivy" || exit

            # Install panther_ivy and copy libraries
            python3.10 setup.py install
            cp lib/libz3.so submodules/z3/build/python/z3

            echo "Updating include path of Python with updated version of the TLS project from /opt/panther_ivy/ivy/include/1.7/"

            # Copy .ivy files to the appropriate include path
            for file in "/opt/panther_ivy/ivy/include/1.7/"/*.ivy; do
                if [[ -f "$file" ]]; then
                    echo "Copying $file..."
                    sudo cp -f "$file" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/"
                fi
            done

            # Copy static libraries
            cd "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/" || exit
            sudo cp -f -a /opt/panther_ivy/lib/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/"
            # Return to source directory
            cd "$SOURCE_DIR" || exit
        }
        update_ivy_tool
        """
        
        update_for_quic_apt_cmd = """
        # Handle QUIC-related files if required
        echo "Copying QUIC libraries..."
        sudo cp -f -a /opt/picotls/*.a "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/lib/"
        sudo cp -f -a /opt/picotls/*.a "/opt/panther_ivy/ivy/lib/"
        sudo cp -f /opt/picotls/include/picotls.h "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls.h"
        sudo cp -f /opt/picotls/include/picotls.h "/opt/panther_ivy/ivy/include/picotls.h"
        sudo cp -r -f /opt/picotls/include/picotls/. "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/picotls"
        """
        
        setup_ivy_model_cmd = """
        setup_ivy_model() {
            echo "Setting up Ivy model..."
            echo "Updating include path of Python with updated version of the project from $PROTOCOL_MODEL_PATH"

            # Find .ivy files
            find "$PROTOCOL_MODEL_PATH" -type f -name "*.ivy" | while IFS= read -r file; do
                echo "Found Ivy file: $file"

                if [[ "$LOG_LEVEL_IVY" -gt 10 ]]; then
                    echo "Removing debug events from $file"
                    remove_debug_events "$file"
                fi

                # Copy Ivy files to the include path
                sudo cp -f "$file" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/"
            done

            # Copy QUIC-related files if required
            if [[ "$(get_config_value "verified_protocol" "quic")" == "true" ]]; then
                sudo cp -f "$PROTOCOL_MODEL_PATH/quic_utils/quic_ser_deser.h" "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7/"
            fi
        }
        setup_ivy_model
        """
        self.logger.info("Updating Ivy tool...")
        self.logger.info(f"Executing command: {update_command}")
        
        
        return update_command + " && " + setup_ivy_model_cmd
 
    def generate_compilation_commands(self, service_params: Dict[str, Any], environment: str) -> Dict[str, Any]:
        self.logger.debug(f"Generating compilation commands for service: {service_params}")
        self.logger.debug(f"Environment: {environment}")
        protocol = service_params.get("protocol").get("name")
        version = service_params.get("protocol").get("version")
        role = service_params.get("role")
        test_to_compile = service_params.get("protocol").get("test")
        environments = self.config.get("panther_ivy", {}).get(protocol,{}).get("env", {})
        test_to_compile_information = self.config.get("panther_ivy", {}).get(protocol,{})\
            .get("versions", {}).get(version,{}) \
            .get(role,{}).get("tests",{}).get(test_to_compile, {})
        self.logger.debug(f"Test to compile: {test_to_compile}")
        self.logger.debug(f"Test information: {test_to_compile_information}")
        self.logger.debug(f"Environments: {environments}")
        self.logger.debug(f"Protocol: {protocol}")
        self.logger.debug(f"Version: {version}")
        if not test_to_compile_information:
            self.logger.error(f"Test '{test_to_compile}' not found in configuration.")
            exit(1)
        return self.build_tests(test_to_compile,role,protocol) # TODO
    

    def build_tests(self, test, mode, protocol):
        # TODO make more flexible, for now only work in docker "/opt/panther_ivy/"
        """Compile and prepare the tests."""
        self.logger.info("Compiling tests...")
        self.logger.info(f"Mode: {mode} for test: {test}")
        file_path = os.path.join("/opt/panther_ivy/protocol-testing/",protocol, self.config["panther_ivy"][protocol]["parameters"]["tests_dir"]["value"], mode + "_tests", test + ".ivy")
        self.logger.debug(f"Building file: {file_path}")
        cmd = f"cd /opt/panther_ivy/; PYTHONPATH=$PYTHONPATH:/opt/panther_ivy/ivy/ ivyc trace=false show_compiled=false target=test test_iters={self.config['panther_ivy']['parameters']['internal_iterations_per_test']['value']} {file_path}"
        self.logger.info(f"Tests compilation command: {cmd}")
        mv_command = f"mv {file_path.replace('.ivy', '')}.* {os.path.join('/opt/panther_ivy/protocol-testing/',protocol, self.config['panther_ivy']['parameters']['tests_build_dir']['value'])}"
        self.logger.info(f"Moving built files: {mv_command}")
        return cmd + " && " + mv_command
        
    def load_config(self) -> dict:
        """
        Loads the YAML configuration file.
        """
        config_file = Path(self.config_path)
        if not config_file.exists():
            self.logger.error(f"Configuration file '{self.config_path}' does not exist.")
            return {}
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            self.logger.info(f"Loaded configuration from '{self.config_path}'")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}\n{traceback.format_exc()}")
            exit(1)

    def generate_deployment_commands(self, service_params: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """
        Generates deployment commands and collects volume mappings based on service parameters.

        :param service_params: Parameters specific to the service.
        :param environment: The environment in which the services are being deployed.
        :return: A dictionary with service name as key and a dictionary containing command and volumes.
        """
        # TODO add developper volumes -> do not rebuilt the docker in that case !
        self.logger.debug(f"Generating deployment commands for service: {service_params}")

        role     = service_params.get("role")
        version  = service_params.get("version", "rfc9000")
        protocol = service_params.get("protocol").get("name")
        version_config = self.config.get("panther_ivy", {}) \
            .get(protocol, {}).get("versions", {}).get(version, {})
            
        # Build parameters for the command template
        params = {
            "test_name": service_params.get("protocol").get("test"),
            "timeout_cmd": f"timeout {self.config.get('panther_ivy').get('parameters').get('timeout').get('value')} ",  # Example timeout
            "prefix": "",
            "build_dir": self.config.get("panther_ivy").get("parameters").get("tests_build_dir").get("value"),
            "seed": self.config.get("panther_ivy").get(protocol).get("parameters").get("seed").get("value"),
            "the_cid": self.config.get("panther_ivy").get(protocol).get("parameters").get("the_cid").get("value"),
            "server_port": self.config.get("panther_ivy").get(protocol).get("parameters").get("server_port").get("value"),
            "version": version,
            "iversion": self.config.get("panther_ivy").get(protocol).get("parameters").get("iversion").get("value"),
            "server_addr": self.config.get("panther_ivy").get(protocol).get("parameters").get("server_addr").get("value"),
            "server_cid": self.config.get("panther_ivy").get(protocol).get("parameters").get("server_cid").get("value"),
            "client_port": self.config.get("panther_ivy").get(protocol).get("parameters").get("client_port").get("value"),
            "client_port_alt": self.config.get("panther_ivy").get(protocol).get("parameters").get("client_port_alt").get("value"),
            "client_addr": self.config.get("panther_ivy").get(protocol).get("parameters").get("client_addr").get("value"),
            "modify_packets": "false",
            "name": service_params.get("name"),
            # TODO managed paired tests
            #"paired_tests": self.config.get("ivy", {}).get("paired_tests", {}),
            "iteration": self.config.get("panther_ivy").get("parameters").get("value"),  # Example iteration for testing
            "is_client": role == "client",
            "certificates": {
                "cert_param": version_config.get(role, {}).get("certificates", {}).get("cert", {}).get("param"),
                "cert_file": version_config.get(role, {}).get("certificates", {}).get("cert", {}).get("file"),
                "cert_local_file": version_config.get(role, {}).get("certificates", {}).get("cert", {}).get("local_file"),
                "key_param": version_config.get(role, {}).get("certificates", {}).get("key", {}).get("param"),
                "key_file": version_config.get(role, {}).get("certificates", {}).get("key", {}).get("file"),
                "key_local_file": version_config.get(role, {}).get("certificates", {}).get("key", {}).get("local_file"),
            },
            "ticket_file": {
                "param": version_config.get(role, {}).get("ticket_file", {}).get("param"),
                "file": version_config.get(role, {}).get("ticket_file", {}).get("file"),
                "local_file": version_config.get(role, {}).get("ticket_file", {}).get("local_file"),
            },
            "logging": version_config.get(role, {}).get("logging", {}),
            "protocol": {
                "alpn": version_config.get(role, {}).get("protocol", {}).get("alpn", {}),
                "additional_parameters": version_config.get(role, {}).get("protocol", {}).get("additional_parameters", ""),
            },
            "network": {
                "interface": version_config.get(role, {}).get("network", {}).get("interface", {}),
                "port": version_config.get(role, {}).get("network", {}).get("port", 4443),
                "destination": service_params.get("target", version_config.get(role, {}).get("network", {}).get("destination", "picoquic_server")),
            },
        }
        # TODO add timeout parameter
        # TODO setup working directory
        
        # Collect volume mappings
        volumes = [
            "shared_logs:/app/sync_logs"
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
            volumes.append({
                "local": os.path.abspath(params["ticket_file"]["local_file"]),
                "container": params["ticket_file"]["file"]
            })

        try:
            template_name = f"{role}_command.j2"
            self.logger.debug(f"Rendering command using template '{template_name}' with parameters: {params}")
            template = self.jinja_env.get_template(template_name)
            command = template.render(**params)

            # Generate compilation commands
            compilation_command = ""
            if self.config.get("panther_ivy",{}).get("parameters", {}).get("compile_tests", {}).get("value", False):
                compilation_command = self.generate_compilation_commands(service_params, environment)
            # Clean up the command string
            compilation_command = compilation_command + \
                          " && " + \
                          " touch /app/sync_logs/tester_ready"
            command_str = "cd " + \
                        os.path.join("/opt/panther_ivy/protocol-testing/",protocol) + \
                        " && " + \
                        command.replace('\t', ' ').replace('\n', ' ').strip()
            working_dir = os.path.join("/opt/panther_ivy/protocol-testing/",protocol)

            service_name = service_params.get("name")
            self.logger.debug(f"Generated command for '{service_name}': {command_str} with {compilation_command}")
            return {service_name: {"command": command_str, "volumes": volumes, "working_dir": working_dir, "compilation_command": compilation_command}}
        except Exception as e:
            self.logger.error(f"Failed to render command: {e}\n{traceback.format_exc()}")
            raise e

    def check_missing_params(self, params: Dict[str, Any], required: list = []) -> list:
        """
        Checks for missing parameters in the params dictionary.

        :param params: Dictionary of parameters.
        :param required: List of required top-level keys.
        :return: List of missing parameter keys.
        """
        missing = []
        # Check top-level required keys
        for key in required:
            if not params.get(key):
                missing.append(key)
        # Recursively check nested dictionaries
        def recurse(d, parent_key=''):
            for k, v in d.items():
                full_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    recurse(v, full_key)
                elif v is None:
                    missing.append(full_key)
        recurse(params)
        return missing
    
    def replace_env_vars(self, value: str) -> str:
        """
        Replaces environment variables in the given string with their actual values.

        :param value: String containing environment variables (e.g., $IMPLEM_DIR).
        :return: String with environment variables replaced by their values.
        """
        try:
            self.logger.debug(f"Replacing environment variables in '{value}'")
            return os.path.expandvars(value)
        except Exception as e:
            self.logger.error(f"Failed to replace environment variables in '{value}': {e}\n{traceback.format_exc()}")
            return value
    
    def start_service(self, parameters: dict):
        """
        Starts the Ivy tester server or client based on the role.
        Parameters should include 'role'.
        # TODO should be in envirnment
        """
        role = parameters.get("role")
        if role not in ['server', 'client']:
            self.logger.error(f"Unknown role '{role}'. Cannot start service.")
            return

        cmd = self.generate_deployment_commands(role)
        if not cmd:
            self.logger.error(f"Failed to generate command for role '{role}'.")
            return

        log_path = self.config.get(role, {}).get("log_path", f"/app/logs/{role}.log")
        self.logger.info(f"Starting Ivy tester {role} with command: {cmd}")
        try:
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                cwd="/opt/ivy",  # Ensure this matches your Dockerfile's WORKDIR
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            self.logger.info(f"Ivy tester {role} started with PID {self.process.pid}")
        except Exception as e:
            self.logger.error(f"Failed to start Ivy tester {role}: {e}\n{traceback.format_exc()}")

    def stop_service(self):
        """
        Stops the Ivy tester service gracefully.
        """
        if self.process:
            self.logger.info(f"Stopping Ivy tester service with PID {self.process.pid}")
            try:
                os.killpg(os.getpgid(self.process.pid), 15)  # SIGTERM
                self.process.wait(timeout=10)
                self.logger.info("Ivy tester service stopped successfully.")
            except Exception as e:
                self.logger.error(f"Failed to stop Ivy tester service: {e}")

    def __str__(self) -> str:
        return super().__str__() + f" (Ivy tester Service Manager - {self.config_path})"