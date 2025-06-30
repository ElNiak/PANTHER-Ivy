"""
Flexible path template resolver for PANTHER-Ivy.

This module provides a template-based path resolution system that allows
for dynamic path construction using configurable template variables.
"""

import os
import re
from typing import Dict, Any, Optional
from pathlib import Path
from panther.core.utils.logging_mixin import LoggerMixin

class PathTemplateResolver(LoggerMixin):
    """
    Resolves flexible path templates with configurable variables.
    
    Supports template variables in the format variable_name and provides
    dynamic resolution based on runtime configuration.
    """
    
    def __init__(self, base_variables: Optional[Dict[str, str]] = None):
        """
        Initialize the path template resolver.
        
        Args:
            base_variables: Dictionary of base template variables to use
        """
        self.variables = base_variables or {}
        self._setup_default_variables()
    
    def _setup_default_variables(self):
        """Set up default template variables."""
        # Get SOURCE_DIR with fallback
        source_dir = os.getenv('SOURCE_DIR', '/opt')
        
        defaults = {
            'homepath': os.path.expanduser('~'),
            'SOURCE_DIR': source_dir,
            'PANTHER_IVY_BASE_DIR': os.getenv('PANTHER_IVY_BASE_DIR', f'{source_dir}/panther_ivy'),
            'PANTHER_IVY_INSTALL_DIR': os.getenv('PANTHER_IVY_INSTALL_DIR', '/opt/panther_ivy'),
            'IVY_PROTOCOL_BASE': os.getenv('IVY_PROTOCOL_BASE', 'protocol-testing/apt/apt_protocols'),
            'IVY_PROTOCOL_DATA_DIR': os.getenv('IVY_PROTOCOL_DATA_DIR', 'quic'),
        }
        
        # Merge defaults with existing variables (existing take precedence)
        for key, value in defaults.items():
            if key not in self.variables:
                self.variables[key] = value
    
    def add_variable(self, name: str, value: str):
        """Add or update a template variable."""
        self.variables[name] = value
    
    def add_variables(self, variables: Dict[str, str]):
        """Add or update multiple template variables."""
        self.variables.update(variables)
    
    def resolve_template(self, template: str, context: Optional[Dict[str, str]] = None) -> str:
        """
        Resolve a path template with variables.
        
        Args:
            template: Template string with variables in format variable_name
            context: Additional context variables for this resolution
            
        Returns:
            Resolved path string
            
        Examples:
            homepath/protocol-testing/IS_APT_PATH/quic/data
            PANTHER_IVY_BASE_DIR/IVY_PROTOCOL_BASE/IVY_QUIC_DATA_DIR
        """
        # Combine instance variables with context
        all_variables = self.variables.copy()
        if context:
            all_variables.update(context)
        
        # Find all template variables in format variable_name
        template_pattern = r'<\$([a-zA-Z_][a-zA-Z0-9_]*?)'
        
        def replace_variable(match):
            var_name = match.group(1)
            if var_name in all_variables:
                return str(all_variables[var_name])
            else:
                # Keep original if variable not found
                return match.group(0)
        
        # Perform substitution
        resolved = re.sub(template_pattern, replace_variable, template)
        
        # Handle any remaining environment variable references (${VAR} format)
        resolved = os.path.expandvars(resolved)
        
        # Normalize path separators
        resolved = os.path.normpath(resolved)
        
        return resolved
    
    def resolve_template_dict(self, template_dict: Dict[str, Any], context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Recursively resolve templates in a dictionary structure.
        
        Args:
            template_dict: Dictionary potentially containing template strings
            context: Additional context variables for this resolution
            
        Returns:
            Dictionary with resolved template strings
        """
        if not isinstance(template_dict, dict):
            if isinstance(template_dict, str):
                return self.resolve_template(template_dict, context)
            return template_dict
        
        resolved = {}
        for key, value in template_dict.items():
            if isinstance(value, str):
                resolved[key] = self.resolve_template(value, context)
            elif isinstance(value, dict):
                resolved[key] = self.resolve_template_dict(value, context)
            elif isinstance(value, list):
                resolved[key] = [
                    self.resolve_template(item, context) if isinstance(item, str)
                    else self.resolve_template_dict(item, context) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved
    
    def create_architecture_context(self, use_apt_protocols: bool = False, protocol_name: str = "quic") -> Dict[str, str]:
        """
        Create context variables for different architectural configurations.
        
        Args:
            use_apt_protocols: Whether to use APT protocol architecture
            protocol_name: Name of the protocol being used
            
        Returns:
            Dictionary of context variables
        """
        # Get base directories
        # TODO: should be configurable via environment variables
        project_root = os.getenv('PROJECT_ROOT', '/opt/panther_ivy')
        
        context = {
            'protocol_name': protocol_name,
        }

        if use_apt_protocols:
            # APT architecture: centralized protocols in apt_protocols/{protocol}
            # APT: PANTHER_IVY_BASE_DIR = "$PROJECT_ROOT/protocol-testing/apt/apt_protocols/$PROTOCOL"
            self.logger.debug(f"Using APT protocol architecture for {protocol_name}")
            base_dir = f"{project_root}/protocol-testing/apt/apt_protocols/{protocol_name}"
            context |= {
                'IS_APT_PATH': 'apt/apt_protocols',
                'PROTOCOL_PATH': f'apt/apt_protocols/{protocol_name}',
                'USE_APT_PROTOCOLS': '1',
                'PANTHER_IVY_BASE_DIR': base_dir,
            }
        else:
            # PANTHER_IVY_BASE_DIR = "$PROJECT_ROOT/protocol-testing/$PROTOCOL"
            # Individual protocol architecture: protocol root directory
            self.logger.debug(f"Using individual protocol architecture for {protocol_name}")
            base_dir = f"{project_root}/protocol-testing/{protocol_name}"
            context |= {
                'IS_APT_PATH': '',  # Empty for individual protocols to avoid duplication
                'PROTOCOL_PATH': protocol_name,
                'USE_APT_PROTOCOLS': '0',
                'PANTHER_IVY_BASE_DIR': base_dir,
            }

        return context
    
    def get_available_variables(self) -> Dict[str, str]:
        """Get all available template variables."""
        return self.variables.copy()


# Global resolver instance for easy access
_global_resolver = None


def get_global_resolver() -> PathTemplateResolver:
    """Get the global path template resolver instance."""
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = PathTemplateResolver()
    return _global_resolver


def resolve_path_template(template: str, context: Optional[Dict[str, str]] = None) -> str:
    """
    Convenience function to resolve a path template using the global resolver.
    
    Args:
        template: Template string with variables
        context: Additional context variables
        
    Returns:
        Resolved path string
    """
    return get_global_resolver().resolve_template(template, context)


def create_apt_context(protocol_name: str = "quic") -> Dict[str, str]:
    """Create context for APT protocol architecture."""
    return get_global_resolver().create_architecture_context(use_apt_protocols=True, protocol_name=protocol_name)


def create_individual_context(protocol_name: str = "quic") -> Dict[str, str]:
    """Create context for individual protocol architecture."""
    return get_global_resolver().create_architecture_context(use_apt_protocols=False, protocol_name=protocol_name)