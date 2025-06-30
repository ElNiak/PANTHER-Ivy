"""
Network resolution mixin for PantherIvy service manager.

This mixin provides dynamic service target resolution for network placeholders,
replacing hardcoded IP addresses with environment-aware placeholders that resolve
to the correct target services based on experiment context and service roles.
"""

from typing import Dict, List, Optional, Any
import re


class IvyNetworkResolutionMixin:
    """
    Mixin for dynamic network resolution in PantherIvy service manager.
    
    This mixin provides methods to:
    1. Resolve role-based placeholders to actual service names
    2. Replace hardcoded IP addresses with dynamic network placeholders
    3. Handle different network environments (localhost, docker, shadow_ns)
    4. Maintain separation of concerns between service logic and network resolution
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize network resolution mixin."""
        super().__init__(*args, **kwargs)
        self._network_placeholder_cache = {}
        self._service_target_mapping = {}
    
    def resolve_service_target_placeholders(self, template_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve service-role placeholders to actual service names in template context.
        
        This method replaces role-based placeholders like @{server_service:ip:decimal}
        with actual service-specific placeholders like @{picoquic_server:ip:decimal}
        based on the experiment context and service targets.
        
        Args:
            template_context: Jinja template context with configuration parameters
            
        Returns:
            Updated template context with resolved network placeholders
        """
        if not template_context:
            return template_context
            
        # Get service targets from experiment context
        service_targets = self._get_service_targets()
        
        # Create mapping from roles to actual service names
        role_to_service_mapping = self._build_role_to_service_mapping(service_targets)
        
        # Clone context to avoid modifying original
        resolved_context = template_context.copy()
        
        # Resolve placeholders in context values
        for key, value in template_context.items():
            if isinstance(value, str):
                resolved_value = self._resolve_placeholders_in_string(value, role_to_service_mapping)
                if resolved_value != value:
                    resolved_context[key] = resolved_value
                    self.logger.debug(f"Resolved {key}: {value} -> {resolved_value}")
        
        return resolved_context
    
    def _get_service_targets(self) -> List[str]:
        """
        Get list of target services for this ivy tester.
        
        Returns:
            List of service names that this ivy service will test
        """
        # Check multiple sources for service targets
        targets = []

        # 1. Check service_targets attribute (if available)
        if hasattr(self, 'service_targets') and self.service_targets:
            self.logger.debug(f"Using service_targets: {self.service_targets}")
            if isinstance(self.service_targets, list):
                targets.extend(self.service_targets)
            elif isinstance(self.service_targets, str):
                targets.append(self.service_targets)
            else:
                self.logger.warning(f"Unexpected type for service_targets: {type(self.service_targets)}")

        # 2. Check targets in original service config
        if hasattr(self, '_original_service_config'):
            config_targets = getattr(self._original_service_config, 'targets', [])
            self.logger.debug(f"Using _original_service_config targets: {config_targets}")
            if config_targets:
                # Extract service names from target configs
                if isinstance(config_targets, list):
                    for target in config_targets:
                        if hasattr(target, 'service_name'):
                            targets.append(target.service_name)
                        elif isinstance(target, dict) and 'service_name' in target:
                            targets.append(target['service_name'])
                        elif isinstance(target, str):
                            targets.append(target)
                elif isinstance(config_targets, dict):
                    # If config_targets is a dict, extract service names directly
                    targets.extend(iter(config_targets.keys()))
                elif isinstance(config_targets, str):
                    # If it's a single string, treat it as a single target
                    targets.append(config_targets)
                else:
                    self.logger.warning(f"Unexpected type for _original_service_config.targets: {type(config_targets)}")

        # 3. Check global experiment context (if available)
        if hasattr(self, 'global_config') and self.global_config:
            # Handle both dict and object types for global_config
            if isinstance(self.global_config, dict):
                experiment_services = self.global_config.get('services', {})
            else:
                # GlobalConfig object - check if it has services attribute
                experiment_services = getattr(self.global_config, 'services', {})
                
            self.logger.debug(f"Using global_config services: {experiment_services}")

            # Filter for non-tester services (potential targets)
            if experiment_services:
                for service_name, service_config in experiment_services.items():
                    if isinstance(service_config, dict):
                        service_type = service_config.get('type', '').lower()
                    else:
                        service_type = getattr(service_config, 'type', '').lower()

                    if service_type not in ['tester', 'testers'] and service_name != getattr(self, 'service_name', ''):
                        targets.append(service_name)

        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        
        for target in targets:
            if target not in seen:
                seen.add(target)
                unique_targets.append(target)

        self.logger.debug(f"Resolved service targets: {unique_targets}")
        return unique_targets
    
    def _build_role_to_service_mapping(self, service_targets: List[str]) -> Dict[str, str]:
        """
        Build mapping from service roles to actual service names.
        
        Args:
            service_targets: List of target service names
            
        Returns:
            Dictionary mapping role placeholders to service names
        """
        mapping = {}
    
        # For ivy tests, we typically have one main target service
        # TODO for now we assume one primary target service
        # This can be extended to support multiple targets if needed
        primary_target = service_targets[0] if service_targets else "target_service"
        
        # Determine role-based mapping based on ivy role and target roles
        ivy_role = getattr(self, 'role', 'unknown')
        self.logger.debug(f"Building role mapping for ivy role: {ivy_role} with primary target: {primary_target}")
        
        if ivy_role == 'client':
            # Ivy client tests the server implementation
            mapping['server_service'] = primary_target
            mapping['client_service'] = getattr(self, 'service_name', 'ivy_client')
        elif ivy_role == 'server':
            # Ivy server tests the client implementation  
            mapping['client_service'] = primary_target
            mapping['server_service'] = getattr(self, 'service_name', 'ivy_server')
        else:
            # Generic mapping for unknown roles
            mapping['target_service'] = primary_target
            mapping['server_service'] = primary_target
            mapping['client_service'] = getattr(self, 'service_name', 'ivy_service')
        
        self.logger.debug(f"Built role mapping for {ivy_role}: {mapping}")
        return mapping
    
    def _resolve_placeholders_in_string(self, text: str, role_mapping: Dict[str, str]) -> str:
        """
        Resolve role-based placeholders in a string with actual service names.
        
        Args:
            text: String containing potential placeholders
            role_mapping: Mapping from role names to service names
            
        Returns:
            String with resolved placeholders
        """
        
        self.logger.debug(f"Resolving placeholders in text: {text}")
        if not isinstance(text, str) or '@{' not in text:
            return text
        
        resolved_text = text
        
        # Pattern to match @{role_service:attribute:format}
        placeholder_pattern = r'@\{(\w+_service):([^:}]+):([^}]+)\}'
        
        def replace_placeholder(match):
            role_service = match.group(1)  # e.g., "server_service"
            attribute = match.group(2)     # e.g., "ip"
            format_type = match.group(3)   # e.g., "decimal"
            
            # Resolve role to actual service name
            actual_service = role_mapping.get(role_service, role_service)
            
            # Create resolved placeholder
            resolved_placeholder = f"@{{{actual_service}:{attribute}:{format_type}}}"
            
            self.logger.debug(f"Resolved placeholder: {match.group(0)} -> {resolved_placeholder}")
            return resolved_placeholder
        
        resolved_text = re.sub(placeholder_pattern, replace_placeholder, resolved_text)
        return resolved_text
    
    def get_network_placeholder_summary(self) -> Dict[str, Any]:
        """
        Get summary of network placeholder resolution for debugging.
        
        Returns:
            Dictionary with placeholder resolution details
        """
        service_targets = self._get_service_targets()
        role_mapping = self._build_role_to_service_mapping(service_targets)
        
        return {
            'ivy_service_name': getattr(self, 'service_name', 'unknown'),
            'ivy_role': getattr(self, 'role', 'unknown'),
            'service_targets': service_targets,
            'role_to_service_mapping': role_mapping,
            'cache_size': len(self._network_placeholder_cache)
        }
    
    def preprocess_template_context_with_network_resolution(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess template context to resolve network placeholders before Jinja rendering.
        
        This method should be called before passing context to Jinja templates
        to ensure network placeholders are properly resolved.
        
        Args:
            context: Original template context
            
        Returns:
            Template context with resolved network placeholders
        """
        # # Cache key for this context (simplified)
        # cache_key = str(sorted(context.items()))
        
        # if cache_key in self._network_placeholder_cache:
        #     return self._network_placeholder_cache[cache_key]
        
        # Resolve placeholders
        resolved_context = self.resolve_service_target_placeholders(context)
        
        # Cache result
        # self._network_placeholder_cache[cache_key] = resolved_context
        
        return resolved_context