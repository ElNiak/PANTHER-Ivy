#!/usr/bin/env python3
"""
Test script for flexible path templates in PANTHER-Ivy.

This script demonstrates the functionality of the PathTemplateResolver
and shows how templates are resolved in different scenarios.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to path to import the resolver
sys.path.insert(0, str(Path(__file__).parent))

from path_template_resolver import PathTemplateResolver, get_global_resolver


def test_basic_templates():
    """Test basic template resolution functionality."""
    print("=== Basic Template Resolution ===")
    
    resolver = PathTemplateResolver()
    
    # Test basic variables
    template = "homepath>/protocol-testing"
    result = resolver.resolve_template(template)
    print(f"Template: {template}")
    print(f"Result:   {result}")
    print()
    
    # Test environment variables
    template = "PANTHER_IVY_BASE_DIR>/IVY_PROTOCOL_BASE>"
    result = resolver.resolve_template(template)
    print(f"Template: {template}")
    print(f"Result:   {result}")
    print()


def test_architecture_contexts():
    """Test architecture-specific template resolution."""
    print("=== Architecture Context Resolution ===")
    
    resolver = PathTemplateResolver()
    
    template = "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/data.txt"
    
    # APT architecture
    apt_context = resolver.create_architecture_context(use_apt_protocols=True, protocol_name="quic")
    apt_result = resolver.resolve_template(template, apt_context)
    print(f"Template: {template}")
    print(f"APT Context: {apt_context}")
    print(f"APT Result:  {apt_result}")
    print()
    
    # Individual architecture
    individual_context = resolver.create_architecture_context(use_apt_protocols=False, protocol_name="quic")
    individual_result = resolver.resolve_template(template, individual_context)
    print(f"Individual Context: {individual_context}")
    print(f"Individual Result:  {individual_result}")
    print()


def test_custom_variables():
    """Test custom variable resolution."""
    print("=== Custom Variable Resolution ===")
    
    resolver = PathTemplateResolver()
    
    # Add custom variables
    resolver.add_variables({
        'custom_base': '/my/custom/path',
        'project_name': 'my_project',
        'environment': 'development'
    })
    
    template = "custom_base>/project_name>/environment>/logs/service_name>.log"
    context = {'service_name': 'ivy_client'}
    
    result = resolver.resolve_template(template, context)
    print(f"Template: {template}")
    print(f"Context:  {context}")
    print(f"Result:   {result}")
    print()


def test_nested_resolution():
    """Test nested template resolution."""
    print("=== Nested Template Resolution ===")
    
    resolver = PathTemplateResolver()
    
    # Define nested templates
    config = {
        'BASE_PATH': 'homepath>/projects',
        'PROJECT_PATH': 'BASE_PATH>/project_name>',
        'LOG_PATH': 'PROJECT_PATH>/logs/service_name>.log'
    }
    
    context = {
        'project_name': 'panther_ivy',
        'service_name': 'ivy_client'
    }
    
    for key, template in config.items():
        result = resolver.resolve_template(template, context)
        print(f"{key}: {template} -> {result}")
    print()


def test_validation():
    """Test template validation functionality."""
    print("=== Template Validation ===")
    
    resolver = PathTemplateResolver()
    
    # Valid template
    valid_template = "homepath>/PANTHER_IVY_BASE_DIR>/data"
    is_valid, undefined = resolver.validate_template(valid_template)
    print(f"Template: {valid_template}")
    print(f"Valid: {is_valid}, Undefined: {undefined}")
    print()
    
    # Invalid template
    invalid_template = "homepath>/undefined_var>/data"
    is_valid, undefined = resolver.validate_template(invalid_template)
    print(f"Template: {invalid_template}")
    print(f"Valid: {is_valid}, Undefined: {undefined}")
    print()


def test_configuration_scenarios():
    """Test different deployment configuration scenarios."""
    print("=== Configuration Scenarios ===")
    
    scenarios = [
        {
            'name': 'Development',
            'env': {
                'PANTHER_IVY_BASE_DIR': './dev_protocols',
                'PANTHER_IVY_INSTALL_DIR': './dev_tools'
            }
        },
        {
            'name': 'Production',
            'env': {
                'PANTHER_IVY_BASE_DIR': '/opt/panther_ivy',
                'PANTHER_IVY_INSTALL_DIR': '/usr/local/panther_ivy'
            }
        },
        {
            'name': 'Docker',
            'env': {
                'PANTHER_IVY_BASE_DIR': '/app/protocols',
                'PANTHER_IVY_INSTALL_DIR': '/usr/local/bin'
            }
        }
    ]
    
    template = "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
    
    for scenario in scenarios:
        print(f"{scenario['name']} Scenario:")
        
        # Create resolver with scenario environment
        resolver = PathTemplateResolver(scenario['env'])
        
        # Test both architectures
        for use_apt in [True, False]:
            context = resolver.create_architecture_context(use_apt_protocols=use_apt, protocol_name="quic")
            result = resolver.resolve_template(template, context)
            arch_name = "APT" if use_apt else "Individual"
            print(f"  {arch_name}: {result}")
        print()


def main():
    """Run all template tests."""
    print("PANTHER-Ivy Flexible Template System Test")
    print("=" * 50)
    print()
    
    # Set up test environment
    os.environ.setdefault('SOURCE_DIR', '/app/src')
    
    # Run tests
    test_basic_templates()
    test_architecture_contexts()
    test_custom_variables()
    test_nested_resolution()
    test_validation()
    test_configuration_scenarios()
    
    print("Available Variables in Global Resolver:")
    resolver = get_global_resolver()
    variables = resolver.get_available_variables()
    for name, value in sorted(variables.items()):
        print(f"  {name}: {value}")
    print()
    
    print("Test completed successfully!")


if __name__ == '__main__':
    main()