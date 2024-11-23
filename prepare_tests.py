import logging
import subprocess
import sys
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

logging.basicConfig(level=logging.INFO)

SOURCE_DIR = "/app"
IMPLEM_DIR = os.path.join(SOURCE_DIR, "implementations", "$PROT-implementations")
RESULT_DIR = os.path.join(
    SOURCE_DIR, "panther-ivy", "protocol-testing", "$PROT", "test"
)
IVY_DIR = os.path.join(SOURCE_DIR, "panther-ivy")

# Ivy related
IVY_INCLUDE_PATH = os.path.join(SOURCE_DIR, "panther-ivy", "ivy", "include", "1.7")
MODEL_DIR = os.path.join(SOURCE_DIR, "panther-ivy", "protocol-testing")

# QUIC related
TLS_KEY_PATH = os.path.join(SOURCE_DIR, "tls-keys")
QUIC_TICKET_PATH = os.path.join(SOURCE_DIR, "tickets")
QLOGS_PATH = os.path.join(SOURCE_DIR, "qlogs")

logging.info(f"SOURCE_DIR: {SOURCE_DIR}")
logging.info(f"IMPLEM_DIR: {IMPLEM_DIR}")
logging.info(f"RESULT_DIR: {RESULT_DIR}")
logging.info(f"IVY_DIR: {IVY_DIR}")
logging.info(f"MODEL_DIR: {MODEL_DIR}")
logging.info(f"IVY_INCLUDE_PATH: {IVY_INCLUDE_PATH}")
logging.info(f"TLS_KEY_PATH: {TLS_KEY_PATH}")
logging.info(f"QUIC_TICKET_PATH: {QUIC_TICKET_PATH}")
logging.info(f"QLOGS_PATH: {QLOGS_PATH}")

def setup_environment(config):
    """Set up environment variables and logging."""
    log_level = int(os.environ["LOG_LEVEL"])
    logging.basicConfig(level=log_level)
    log = logging.getLogger("panther-compiler")

    log.info(f"Log level {log_level}")

    for env_var, value in ENV_VAR.items():
        os.environ[env_var] = str(value)
        log.debug(f"Set ENV_VAR {env_var}={value}")

    return log

def find_ivy_files(root_folder):
    """Recursively find all .ivy files, excluding those with 'test' in the filename."""
    ivy_files = []
    for dirpath, _, filenames in os.walk(root_folder):
        for f in filenames:
            if f.endswith(".ivy") and "test" not in f:
                ivy_files.append(os.path.join(dirpath, f))
    return ivy_files

def update_ivy_tool(log):
    """Update Ivy tool and include paths."""
    log.info("Updating Ivy tool...")
    os.chdir(SOURCE_DIR + "/panther-ivy/")
    execute_command("sudo python3.10 setup.py install")
    execute_command("sudo cp lib/libz3.so submodules/z3/build/python/z3")
    log.info("Ivy tool updated.")
    os.chdir(SOURCE_DIR)

def build_tests(log, config, tests_enabled):
    """Compile and prepare the tests."""
    log.info("Compiling tests...")
    for mode, test_files in tests_enabled.items():
        log.info(f"Mode: {mode}, Number of tests: {len(test_files)}")
        for file in test_files:
            file_path = os.path.join(config["global_parameters"]["tests_dir"], mode, file + ".ivy")
            log.debug(f"Building file: {file_path}")
            compile_file(log, config, file_path)
    log.info("Tests compiled.")

def compile_file(log, config, file_path):
    """Compile a single test file."""
    if config["global_parameters"].getboolean("compile"):
        log.info(f"Compiling: {file_path}")
        cmd = f"ivyc trace=false show_compiled=false target=test test_iters={config['global_parameters']['internal_iteration']} {file_path}"
        result = subprocess.run(cmd, shell=True, executable="/bin/bash")
        if result.returncode != 0:
            log.error("Compilation failed.")
            sys.exit(1)

        # Move built files to build directory
        build_dir = config["global_parameters"]["build_dir"]
        base_name = file_path.replace(".ivy", "")
        for ext in ["", ".cpp", ".h"]:
            src = f"{base_name}{ext}"
            dest = os.path.join(build_dir, os.path.basename(src))
            log.info(f"Moving {src} to {dest}")
            execute_command(f"/bin/cp {src} {dest}")
            execute_command(f"/bin/rm {src}")

def execute_command(command, must_pass=True):
    """Execute a shell command."""
    result = subprocess.run(command, shell=True, executable="/bin/bash")
    if must_pass and result.returncode != 0:
        raise RuntimeError(f"Command failed: {command}")
    return result.returncode

def launch_experiments(args):
    """Launch the experiments based on the configuration."""
    log = setup_environment({})
    log.info("Launching experiments...")

    config = get_experiment_config(args.current_protocol, False, False)
    tests_enabled = config[2]
    update_ivy_tool(log)
    build_tests(log, config, tests_enabled)

    log.info("Experiments completed.")

def main():
    """Main entry point for the script."""
    args = ArgumentParserRunner().parse_arguments()
    launch_experiments(args)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        sys.exit(1)
