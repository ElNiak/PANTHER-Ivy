"""Ivy environment and Docker setup functionality."""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin


class IvyEnvironmentSetup(ErrorHandlerMixin):
    """Handles Ivy environment initialization and Docker setup."""
    
    # Required environment variables for Ivy
    REQUIRED_ENV_VARS = [
        "IVY_Z3_PATH",
        "PYTHONPATH"
    ]
    
    # Default environment configuration
    DEFAULT_ENV_CONFIG = {
        "ivy_workspace": "/app/ivy",
        "z3_path": "/app/ivy/submodules/z3/build",
        "python_path": "/app/ivy",
        "output_directory": "/app/outputs",
        "certificates_directory": "/app/certs"
    }
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        self.environment_config = self.DEFAULT_ENV_CONFIG.copy()
        self.volumes_config = {}
        
    def initialize_ivy_environment(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the Ivy environment with required settings.
        
        Args:
            config: Environment configuration dictionary
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing Ivy environment")
            
            # Update environment configuration
            self._update_environment_config(config)
            
            # Set up environment variables
            self._setup_environment_variables()
            
            # Initialize workspace directories
            self._initialize_workspace_directories()
            
            # Set up Ivy-specific attributes
            self._initialize_ivy_attributes()
            
            # Validate environment setup
            validation_result = self._validate_environment()
            
            if validation_result:
                self.logger.info("Ivy environment initialized successfully")
            else:
                self.logger.error("Ivy environment initialization failed validation")
                
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Ivy environment: {e}")
            return False
    
    def setup_docker_volumes(self, volume_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Set up Docker volume mappings for Ivy.
        
        Args:
            volume_config: Volume configuration dictionary
            
        Returns:
            Dictionary of volume mappings
        """
        volumes = {}
        
        try:
            self.logger.info("Setting up Docker volumes for Ivy")
            
            # Standard volume mappings
            host_base = volume_config.get('host_base_directory', '/tmp/panther_ivy')
            
            volumes.update({
                # Ivy workspace
                f"{host_base}/ivy": "/app/ivy",
                # Output directory
                f"{host_base}/outputs": "/app/outputs",
                # Certificates
                f"{host_base}/certs": "/app/certs",
                # Logs
                f"{host_base}/logs": "/app/logs"
            })
            
            # Protocol-specific volumes
            protocol_volumes = self._get_protocol_specific_volumes(volume_config)
            volumes.update(protocol_volumes)
            
            # Custom volume mappings
            custom_volumes = volume_config.get('custom_volumes', {})
            if isinstance(custom_volumes, dict):
                # Validate custom volume paths
                for host_path, container_path in custom_volumes.items():
                    if self._is_safe_volume_path(host_path, container_path):
                        volumes[host_path] = container_path
                    else:
                        self.logger.warning(f"Skipping unsafe volume mapping: {host_path}:{container_path}")
            
            # Ensure host directories exist
            self._ensure_host_directories_exist(volumes)
            
            self.volumes_config = volumes
            self.logger.info(f"Configured {len(volumes)} Docker volumes")
            
            return volumes
            
        except Exception as e:
            self.logger.error(f"Failed to setup Docker volumes: {e}")
            return {}
    
    def build_submodules(self, force_rebuild: bool = False) -> bool:
        """
        Build Ivy submodules (mainly Z3 solver).
        
        Args:
            force_rebuild: Whether to force a complete rebuild
            
        Returns:
            True if build successful, False otherwise
        """
        try:
            self.logger.info("Building Ivy submodules")
            
            ivy_workspace = Path(self.environment_config["ivy_workspace"])
            z3_build_dir = ivy_workspace / "submodules" / "z3" / "build"
            
            # Check if already built
            if not force_rebuild and z3_build_dir.exists():
                z3_executable = z3_build_dir / "z3"
                if z3_executable.exists():
                    self.logger.info("Z3 already built, skipping build")
                    return True
            
            # Build Z3 solver
            z3_success = self._build_z3_solver(ivy_workspace)
            
            if z3_success:
                self.logger.info("Submodule build completed successfully")
            else:
                self.logger.error("Submodule build failed")
                
            return z3_success
            
        except Exception as e:
            self.logger.error(f"Failed to build submodules: {e}")
            return False
    
    def prepare_environment(self, plugin_manager=None) -> bool:
        """
        Prepare the complete Ivy environment.
        
        Args:
            plugin_manager: Optional plugin manager instance
            
        Returns:
            True if preparation successful, False otherwise
        """
        try:
            self.logger.info("Preparing Ivy environment")
            
            # Step 1: Initialize basic environment
            env_init_success = self.initialize_ivy_environment({})
            if not env_init_success:
                return False
            
            # Step 2: Set up Docker volumes if in containerized environment
            if self._is_containerized():
                volume_config = self._get_volume_config()
                self.setup_docker_volumes(volume_config)
            
            # Step 3: Build submodules if required
            build_submodules = getattr(self.service_manager, 'build_submodules', True)
            if build_submodules:
                build_success = self.build_submodules()
                if not build_success:
                    self.logger.warning("Submodule build failed, continuing anyway")
            
            # Step 4: Set up protocol-specific environment
            protocol_setup_success = self._setup_protocol_environment()
            
            # Step 5: Final validation
            final_validation = self._validate_complete_environment()
            
            success = env_init_success and protocol_setup_success and final_validation
            
            if success:
                self.logger.info("Ivy environment preparation completed successfully")
            else:
                self.logger.error("Ivy environment preparation failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to prepare environment: {e}")
            return False
    
    def _update_environment_config(self, config: Dict[str, Any]) -> None:
        """Update environment configuration with provided values."""
        for key, value in config.items():
            if key in self.DEFAULT_ENV_CONFIG and isinstance(value, str):
                # Validate path safety
                if self._is_safe_path(value):
                    self.environment_config[key] = value
                else:
                    self.logger.warning(f"Unsafe path in config: {key}={value}")
    
    def _setup_environment_variables(self) -> None:
        """Set up required environment variables."""
        # Set Ivy-specific environment variables
        env_vars = {
            "IVY_Z3_PATH": self.environment_config["z3_path"],
            "PYTHONPATH": f"{self.environment_config['python_path']}:{os.environ.get('PYTHONPATH', '')}",
            "IVY_WORKSPACE": self.environment_config["ivy_workspace"],
            "IVY_OUTPUT_DIR": self.environment_config["output_directory"]
        }
        
        for var_name, var_value in env_vars.items():
            os.environ[var_name] = var_value
            self.logger.debug(f"Set environment variable: {var_name}")
    
    def _initialize_workspace_directories(self) -> None:
        """Initialize required workspace directories."""
        directories_to_create = [
            self.environment_config["output_directory"],
            self.environment_config["certificates_directory"],
            f"{self.environment_config['output_directory']}/logs",
            f"{self.environment_config['output_directory']}/traces",
            f"{self.environment_config['output_directory']}/proofs"
        ]
        
        for directory in directories_to_create:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Created directory: {directory}")
            except Exception as e:
                self.logger.warning(f"Failed to create directory {directory}: {e}")
    
    def _initialize_ivy_attributes(self) -> None:
        """Initialize Ivy-specific attributes on the service manager."""
        # Set workspace path
        self.service_manager.ivy_workspace = Path(self.environment_config["ivy_workspace"])
        
        # Set output directory
        self.service_manager.output_directory = Path(self.environment_config["output_directory"])
        
        # Set Z3 path
        self.service_manager.z3_path = Path(self.environment_config["z3_path"])
        
        # Set test-specific attributes
        if hasattr(self.service_manager, 'config'):
            config = self.service_manager.config
            if isinstance(config, dict):
                self.service_manager.test = config.get('test', 'quic_client_test_max')
        
        self.logger.debug("Initialized Ivy-specific attributes")
    
    def _validate_environment(self) -> bool:
        """Validate that the environment is properly set up."""
        # Check required environment variables
        for var_name in self.REQUIRED_ENV_VARS:
            if var_name not in os.environ:
                self.logger.error(f"Missing required environment variable: {var_name}")
                return False
        
        # Check required directories
        ivy_workspace = Path(self.environment_config["ivy_workspace"])
        if not ivy_workspace.exists():
            self.logger.error(f"Ivy workspace does not exist: {ivy_workspace}")
            return False
        
        # Check for Ivy executable
        ivy_check = ivy_workspace / "ivy_check.py"
        if not ivy_check.exists():
            self.logger.warning(f"Ivy check script not found: {ivy_check}")
        
        return True
    
    def _get_protocol_specific_volumes(self, volume_config: Dict[str, Any]) -> Dict[str, str]:
        """Get protocol-specific volume mappings."""
        volumes = {}
        
        protocol_name = self._get_protocol_name()
        if protocol_name == "quic":
            host_base = volume_config.get('host_base_directory', '/tmp/panther_ivy')
            volumes.update({
                f"{host_base}/quic_impl": "/app/quic_impl",
                f"{host_base}/quic_traces": "/app/quic_traces"
            })
        
        return volumes
    
    def _build_z3_solver(self, ivy_workspace: Path) -> bool:
        """Build the Z3 solver."""
        try:
            z3_dir = ivy_workspace / "submodules" / "z3"
            
            if not z3_dir.exists():
                self.logger.error(f"Z3 directory not found: {z3_dir}")
                return False
            
            # Build Z3 using the provided build script
            build_commands = [
                f"cd {z3_dir}",
                "python scripts/mk_make.py --python",
                "cd build",
                "make -j$(nproc)"
            ]
            
            for cmd in build_commands:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )  # python: disable=consider-using-with
                
                if result.returncode != 0:
                    self.logger.error(f"Z3 build command failed: {cmd}")
                    self.logger.error(f"Error: {result.stderr}")
                    return False
            
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("Z3 build timed out")
            return False
        except Exception as e:
            self.logger.error(f"Z3 build failed: {e}")
            return False
    
    def _setup_protocol_environment(self) -> bool:
        """Set up protocol-specific environment."""
        try:
            protocol_name = self._get_protocol_name()
            
            if protocol_name == "quic":
                return self._setup_quic_environment()
            
            # For other protocols, just return True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup protocol environment: {e}")
            return False
    
    def _setup_quic_environment(self) -> bool:
        """Set up QUIC-specific environment."""
        # Set QUIC-specific environment variables
        quic_env_vars = {
            "QUIC_IMPLEMENTATION_PATH": "/app/quic_impl",
            "QUIC_TRACES_PATH": "/app/quic_traces",
            "QUIC_CERTS_PATH": self.environment_config["certificates_directory"]
        }
        
        for var_name, var_value in quic_env_vars.items():
            os.environ[var_name] = var_value
        
        return True
    
    def _validate_complete_environment(self) -> bool:
        """Perform final validation of the complete environment."""
        try:
            # Check all environment variables are set
            basic_validation = self._validate_environment()
            
            # Check Z3 is accessible
            z3_path = Path(self.environment_config["z3_path"]) / "z3"
            z3_accessible = z3_path.exists() or self._check_z3_in_path()
            
            if not z3_accessible:
                self.logger.warning("Z3 solver not found in expected location")
            
            return basic_validation
            
        except Exception as e:
            self.logger.error(f"Final environment validation failed: {e}")
            return False
    
    def _check_z3_in_path(self) -> bool:
        """Check if Z3 is available in system PATH."""
        try:
            result = subprocess.run(
                ["which", "z3"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _get_protocol_name(self) -> str:
        """Get the protocol name safely."""
        protocol_config = getattr(self.service_manager, 'protocol_config', None)
        if protocol_config and hasattr(protocol_config, 'name'):
            return str(protocol_config.name).lower()
        return "quic"
    
    def _is_containerized(self) -> bool:
        """Check if running in a containerized environment."""
        return os.path.exists("/.dockerenv") or os.environ.get("CONTAINER") == "true"
    
    def _get_volume_config(self) -> Dict[str, Any]:
        """Get volume configuration from service manager."""
        config = getattr(self.service_manager, 'config', {})
        return config.get('volumes', {})
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if a path is safe to use."""
        import os.path
        # Prevent directory traversal
        if ".." in path or path.startswith("/etc/") or path.startswith("/var/"):
            return False
        return True
    
    def _is_safe_volume_path(self, host_path: str, container_path: str) -> bool:
        """Check if volume paths are safe."""
        return self._is_safe_path(host_path) and self._is_safe_path(container_path)
    
    def _ensure_host_directories_exist(self, volumes: Dict[str, str]) -> None:
        """Ensure host directories for volumes exist."""
        for host_path in volumes.keys():
            try:
                Path(host_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.logger.warning(f"Failed to create host directory {host_path}: {e}")