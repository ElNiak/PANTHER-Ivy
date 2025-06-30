"""
Core mixins for PantherIvy service manager following PANTHER architectural standards.

This module provides focused mixins that extract common functionality from the main
PantherIvy service manager, promoting code reuse and maintaining separation of concerns.
"""

import os
from pathlib import Path
from typing import Optional
import logging



class IvyProtocolAwareMixin:
    """
    Mixin for protocol-aware functionality to eliminate duplication.
    
    This mixin centralizes protocol name and path resolution logic that was
    previously duplicated across multiple component files.
    """
    
    _protocol_name_cache: Optional[str] = None
    
    def get_protocol_name(self) -> str:
            """
            Centralized protocol name resolution with caching.
            
            Returns:
                str: Protocol name or 'unknown' if not determinable
            """
            if self._protocol_name_cache:
                return self._protocol_name_cache
                
            protocol_name = None
            
            # Method 1: Check self.protocol object
            if hasattr(self, 'protocol') and self.protocol:
                if hasattr(self.protocol, 'name'):
                    protocol_name = getattr(self.protocol, 'name', None)
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Found protocol name from self.protocol.name: {protocol_name}")
                elif isinstance(self.protocol, str):
                    protocol_name = self.protocol
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Found protocol name from self.protocol string: {protocol_name}")
            
            # Method 2: Check service config protocol
            if protocol_name is None and hasattr(self, 'service_config_to_test'):
                if hasattr(self.service_config_to_test, 'protocol') and hasattr(self.service_config_to_test.protocol, 'name'):
                    protocol_name = getattr(self.service_config_to_test.protocol, 'name', None)
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Found protocol name from service config: {protocol_name}")
            
            # Method 3: Check _original_service_config if available (fallback)
            if protocol_name is None and hasattr(self, '_original_service_config'):
                if hasattr(self._original_service_config, 'protocol') and hasattr(self._original_service_config.protocol, 'name'):
                    protocol_name = getattr(self._original_service_config.protocol, 'name', None)
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Found protocol name from original service config: {protocol_name}")
            
            if protocol_name is None:
                protocol_name = "unknown"
                if hasattr(self, 'logger'):
                    self.logger.warning("Could not determine protocol name from any source")
                
            self._protocol_name_cache = protocol_name
            return protocol_name

    
    def get_protocol_model_path(self, use_system_models: bool = False) -> str:
        """
        Get protocol model path based on architecture choice with environment variable support.
        
        Environment variables:
        - PANTHER_IVY_BASE_PATH: Base path for protocol testing (default: /opt/panther_ivy/protocol-testing)
        - PANTHER_IVY_APT_SUBPATH: Subpath for APT models (default: apt/apt_protocols)
        - PANTHER_IVY_STANDARD_SUBPATH: Subpath for standard models (default: empty)
        
        Args:
            use_system_models: Whether to use APT system models
            
        Returns:
            str: Protocol model path
        """
        protocol_name = self.get_protocol_name()
        
        # Get base path from environment variable or use default
        base_path = os.getenv('PANTHER_IVY_BASE_PATH', '/opt/panther_ivy/protocol-testing')
        
        if use_system_models:
            # Get APT subpath from environment variable or use default
            apt_subpath = os.getenv('PANTHER_IVY_APT_SUBPATH', 'apt/apt_protocols')
            return f"{base_path}/{apt_subpath}/{protocol_name}"
        else:
            # Get standard subpath from environment variable (empty by default)
            standard_subpath = os.getenv('PANTHER_IVY_STANDARD_SUBPATH', '')
            if standard_subpath:
                return f"{base_path}/{standard_subpath}/{protocol_name}"
            return f"{base_path}/{protocol_name}"
    
    def get_local_protocol_model_path(self, use_system_models: bool = False) -> str:
        """
        Get local protocol model path for volume mounting with environment variable support.
        
        Environment variables:
        - PANTHER_IVY_LOCAL_BASE_PATH: Local base path for protocol testing (default: auto-detected)
        - PANTHER_IVY_LOCAL_APT_SUBPATH: Local subpath for APT models (default: apt/apt_protocols)  
        - PANTHER_IVY_LOCAL_STANDARD_SUBPATH: Local subpath for standard models (default: empty)
        
        Args:
            use_system_models: Whether to use APT system models
            
        Returns:
            str: Local protocol model path for host machine
        """
        # Get local base path from environment variable or auto-detect
        local_base_path = os.getenv('PANTHER_IVY_LOCAL_BASE_PATH')
        if local_base_path:
            base_path = Path(local_base_path)
        else:
            base_path = Path(__file__).parent / "protocol-testing"
        
        protocol_name = self.get_protocol_name()
        
        if use_system_models:
            # Get local APT subpath from environment variable or use default
            apt_subpath = os.getenv('PANTHER_IVY_LOCAL_APT_SUBPATH', 'apt/apt_protocols')
            return str(base_path / apt_subpath / protocol_name)
        else:
            # Get local standard subpath from environment variable (empty by default)
            standard_subpath = os.getenv('PANTHER_IVY_LOCAL_STANDARD_SUBPATH', '')
            if standard_subpath:
                return str(base_path / standard_subpath / protocol_name)
            return str(base_path / protocol_name)

    def adapt_environment_paths(self, env_vars: dict, use_system_models: bool) -> int:
            """
            Adapt environment variable paths using simplified single-variable approach.
            
            Instead of complex path building, sets PANTHER_IVY_BASE_DIR to complete path:
            - APT: $PROJECT_ROOT/protocol-testing/apt/apt_protocols/$PROTOCOL  
            - Standard: $PROJECT_ROOT/protocol-testing/$PROTOCOL
            
            Args:
                env_vars: Dictionary of environment variables to modify
                use_system_models: Whether using APT system models architecture
                
            Returns:
                int: Number of environment variables that were set
            """
            protocol_name = self.get_protocol_name()
            
            # Get project root from environment or use default
            project_root = os.getenv('PROJECT_ROOT', '/opt/panther_ivy')
            
            if use_system_models:
                # APT Architecture: centralized protocols under apt_protocols
                base_dir = f"{project_root}/protocol-testing/apt/apt_protocols/{protocol_name}"
                apt_path = "protocol-testing/apt/apt_protocols"
            else:
                # Standard Architecture: protocol in its own directory
                base_dir = f"{project_root}/protocol-testing/{protocol_name}"
                apt_path = ""
            
            # Set the simplified environment variables
            simplified_env_vars = {
                'PANTHER_IVY_BASE_DIR': base_dir,
                'USE_APT_PROTOCOLS': '1' if use_system_models else '0',
                'IS_APT_PATH': apt_path,  # Keep for backward compatibility
                'PROJECT_ROOT': project_root,
                'PROTOCOL': protocol_name,
                'IVY_INCLUDE_PATH': '/usr/local/lib/python3.10/dist-packages/ivy/include/1.7',
                'PANTHER_IVY_ARCHITECTURE': 'apt' if use_system_models else 'standard',
            }
            
            # Apply the environment variables
            adapted_count = 0
            for var_name, var_value in simplified_env_vars.items():
                env_vars[var_name] = var_value
                adapted_count += 1
                if hasattr(self, 'logger'):
                    self.logger.debug(f"Set simplified environment variable {var_name}={var_value}")
            
            if hasattr(self, 'logger'):
                architecture = 'APT' if use_system_models else 'standard'
                self.logger.info(f"Set {adapted_count} simplified environment variables for {architecture} architecture")
                self.logger.info(f"PANTHER_IVY_BASE_DIR={base_dir}")
            
            return adapted_count




