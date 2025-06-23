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
        if hasattr(self, 'protocol'):
            if hasattr(self.protocol, 'name'):
                protocol_name = getattr(self.protocol, 'name', None)
            elif isinstance(self.protocol, str):
                protocol_name = self.protocol
        
        if protocol_name is None:
            protocol_name = "unknown"
            if hasattr(self, 'logger'):
                self.logger.warning("Could not determine protocol name")
            
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
        Adapt environment variable paths based on architecture choice.
        
        This method transforms paths in environment variables to match the selected
        architecture (APT vs standard) using environment variable configuration.
        
        Args:
            env_vars: Dictionary of environment variables to modify
            use_system_models: Whether using APT system models architecture
            
        Returns:
            int: Number of environment variables that were adapted
        """
        protocol_name = self.get_protocol_name()
        
        # Get path configurations from environment variables (with defaults)
        base_path = os.getenv('PANTHER_IVY_BASE_PATH', '$SOURCE_DIR/panther_ivy/protocol-testing')
        
        if use_system_models:
            # APT architecture
            apt_subpath = os.getenv('PANTHER_IVY_APT_SUBPATH', 'apt/apt_protocols')
            target_path = f"{base_path}/{apt_subpath}/{protocol_name}"
        else:
            # Standard architecture  
            standard_subpath = os.getenv('PANTHER_IVY_STANDARD_SUBPATH', '')
            if standard_subpath:
                target_path = f"{base_path}/{standard_subpath}/{protocol_name}"
            else:
                target_path = f"{base_path}/{protocol_name}"
        
        # Define path patterns to replace
        apt_pattern = f"$SOURCE_DIR/panther_ivy/protocol-testing/apt/apt_protocols/{protocol_name}"
        standard_pattern = f"$SOURCE_DIR/panther_ivy/protocol-testing/{protocol_name}"
        
        # Replace paths in environment variables
        adapted_count = 0
        for env_name, env_value in env_vars.items():
            if isinstance(env_value, str):
                original_value = env_value
                adapted_value = env_value
                
                # Replace known patterns with target path
                if apt_pattern in adapted_value:
                    adapted_value = adapted_value.replace(apt_pattern, target_path)
                elif standard_pattern in adapted_value:
                    adapted_value = adapted_value.replace(standard_pattern, target_path)
                
                # Update if changed
                if adapted_value != original_value:
                    env_vars[env_name] = adapted_value
                    adapted_count += 1
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"Adapted path for {env_name}: {original_value} -> {adapted_value}")
        
        if hasattr(self, 'logger'):
            self.logger.info(f"Adapted {adapted_count} environment variable paths for {'APT' if use_system_models else 'standard'} architecture")
        
        return adapted_count


