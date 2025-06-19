"""Protocol-specific handling for Ivy tests."""
from typing import Dict, List, Optional, Any
from enum import Enum
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin


class SupportedProtocol(Enum):
    """Supported protocols for Ivy testing."""
    QUIC = "quic"
    TCP = "tcp"
    UDP = "udp"
    APT = "apt"  # Advanced Persistent Threat Protocol
    MiniP = "minip"  # Minimal Protocol Testing

class IvyProtocolHandler(ErrorHandlerMixin):
    """Handles protocol-specific configuration and validation for Ivy tests."""
    
    # Protocol-specific test configurations
    PROTOCOL_CONFIGS = {
        SupportedProtocol.QUIC: {
            "default_test": "quic_client_test_max",
            "supported_roles": ["client", "server"],
            "required_features": ["handshake", "data_transfer"],
            "optional_features": ["0rtt", "migration", "multipath"],
            "test_files": [
                "quic_client_test_max.ivy",
                "quic_server_test_max.ivy",
                "quic_handshake_test.ivy"
            ]
        },
        SupportedProtocol.TCP: {
            "default_test": "tcp_basic_test",
            "supported_roles": ["client", "server"],
            "required_features": ["connection", "data_transfer"],
            "optional_features": ["keep_alive", "window_scaling"],
            "test_files": [
            ]
        },
        SupportedProtocol.UDP: {
            "default_test": "udp_basic_test",
            "supported_roles": ["sender", "receiver"],
            "required_features": ["datagram_transfer"],
            "optional_features": ["fragmentation"],
            "test_files": [
            ]
        },
        SupportedProtocol.APT: {
            "default_test": "apt_protocol_test",
            "supported_roles": ["client", "server"],
            "required_features": ["protocol_compliance"],
            "optional_features": ["custom_extensions"],
            "test_files": [
            ]
        },
        SupportedProtocol.MiniP: {
            "default_test": "minip_protocol_test",
            "supported_roles": ["client", "server"],
            "required_features": ["protocol_compliance"],
            "optional_features": ["custom_extensions"],
            "test_files": [
                "minip_client_test.ivy",
                "minip_server_test.ivy"
            ]
        }
    }
    
    # Protocol-specific error codes and messages
    # TODO: Mmove to protocol-specific module if needed
    PROTOCOL_ERROR_MAPPINGS = {
        SupportedProtocol.QUIC: {
            "connection_errors": {
                0x0: "NO_ERROR",
                0x1: "INTERNAL_ERROR",
                0x2: "CONNECTION_REFUSED",
                0x3: "FLOW_CONTROL_ERROR",
                0x4: "STREAM_LIMIT_ERROR",
                0x5: "STREAM_STATE_ERROR",
                0x6: "FINAL_SIZE_ERROR",
                0x7: "FRAME_ENCODING_ERROR",
                0x8: "TRANSPORT_PARAMETER_ERROR",
                0x9: "CONNECTION_ID_LIMIT_ERROR",
                0xA: "PROTOCOL_VIOLATION",
                0xB: "INVALID_TOKEN",
                0xC: "APPLICATION_ERROR",
                0xD: "CRYPTO_BUFFER_EXCEEDED",
                0xE: "KEY_UPDATE_ERROR",
                0xF: "AEAD_LIMIT_REACHED",
                0x10: "NO_VIABLE_PATH"
            },
            "stream_errors": {
                0x0: "STOPPING",
                0x1: "STREAM_LIMIT_ERROR",
                0x2: "STREAM_STATE_ERROR",
                0x3: "FINAL_SIZE_ERROR"
            }
        }
    }
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        self.current_protocol = None
        
    def get_protocol_name(self) -> str:
        """
        Get the current protocol name.
        
        Returns:
            Protocol name as string
        """
        if self.current_protocol:
            return self.current_protocol.value
        
        # Try to get from service manager configuration
        protocol_config = getattr(self.service_manager, 'protocol_config', None)
        if protocol_config and hasattr(protocol_config, 'name'):
            protocol_name = str(protocol_config.name).lower()
            try:
                self.current_protocol = SupportedProtocol(protocol_name)
                return self.current_protocol.value
            except ValueError:
                self.logger.warning(f"Unsupported protocol: {protocol_name}")
        
        # Default to QUIC
        self.current_protocol = SupportedProtocol.QUIC
        return self.current_protocol.value
    
    def validate_protocol_configuration(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate protocol-specific configuration.
        
        Args:
            config: Protocol configuration dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            # Get protocol
            protocol_name = config.get('protocol', self.get_protocol_name())
            try:
                protocol = SupportedProtocol(protocol_name.lower())
            except ValueError:
                errors.append(f"Unsupported protocol: {protocol_name}")
                return errors
            
            protocol_config = self.PROTOCOL_CONFIGS.get(protocol, {})
            
            # Validate role
            role = config.get('role')
            if role:
                supported_roles = protocol_config.get('supported_roles', [])
                if role not in supported_roles:
                    errors.append(f"Unsupported role '{role}' for protocol {protocol_name}")
            
            # Validate test file
            test_file = config.get('test_file')
            if test_file:
                supported_tests = protocol_config.get('test_files', [])
                if test_file not in supported_tests:
                    errors.append(f"Unknown test file '{test_file}' for protocol {protocol_name}")
            
            # Validate required features
            required_features = protocol_config.get('required_features', [])
            config_features = config.get('features', [])
            missing_features = set(required_features) - set(config_features)
            if missing_features:
                errors.append(f"Missing required features: {', '.join(missing_features)}")
            
            self.logger.debug(f"Protocol validation completed with {len(errors)} errors")
            
        except Exception as e:
            self.logger.error(f"Protocol validation failed: {e}")
            errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    def get_default_test_configuration(self, protocol_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get default test configuration for a protocol.
        
        Args:
            protocol_name: Optional protocol name (uses current if not provided)
            
        Returns:
            Default configuration dictionary
        """
        if not protocol_name:
            protocol_name = self.get_protocol_name()
        
        try:
            protocol = SupportedProtocol(protocol_name.lower())
        except ValueError:
            self.logger.warning(f"Unknown protocol {protocol_name}, using QUIC defaults")
            protocol = SupportedProtocol.QUIC
        
        protocol_config = self.PROTOCOL_CONFIGS.get(protocol, {})
        
        return {
            "protocol": protocol.value,
            "test": protocol_config.get("default_test", "basic_test"),
            "role": protocol_config.get("supported_roles", ["client"])[0],
            "features": protocol_config.get("required_features", []),
            "timeout": 300,  # 5 minutes default
            "iterations": 1
        }
    
    def get_protocol_error_description(self, error_code: int, error_type: str = "connection_errors") -> str:
        """
        Get human-readable description for protocol-specific error code.
        
        Args:
            error_code: Numeric error code
            error_type: Type of error (connection_errors, stream_errors, etc.)
            
        Returns:
            Human-readable error description
        """
        protocol_name = self.get_protocol_name()
        
        try:
            protocol = SupportedProtocol(protocol_name)
        except ValueError:
            return f"UNKNOWN_ERROR_{error_code}"
        
        error_mappings = self.PROTOCOL_ERROR_MAPPINGS.get(protocol, {})
        error_category = error_mappings.get(error_type, {})
        
        return error_category.get(error_code, f"UNKNOWN_{error_type.upper()}_{error_code}")
    
    def get_supported_test_files(self, protocol_name: Optional[str] = None) -> List[str]:
        """
        Get list of supported test files for a protocol.
        
        Args:
            protocol_name: Optional protocol name (uses current if not provided)
            
        Returns:
            List of supported test file names
        """
        if not protocol_name:
            protocol_name = self.get_protocol_name()
        
        try:
            protocol = SupportedProtocol(protocol_name.lower())
        except ValueError:
            return []
        
        protocol_config = self.PROTOCOL_CONFIGS.get(protocol, {})
        return protocol_config.get("test_files", [])
    
    def get_protocol_specific_parameters(self, protocol_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get protocol-specific parameters for test configuration.
        
        Args:
            protocol_name: Optional protocol name (uses current if not provided)
            
        Returns:
            Dictionary of protocol-specific parameters
        """
        if not protocol_name:
            protocol_name = self.get_protocol_name()
        
        try:
            protocol = SupportedProtocol(protocol_name.lower())
        except ValueError:
            return {}
        
        # Protocol-specific parameters
        if protocol == SupportedProtocol.QUIC:
            return {
                "transport_parameters": {
                    "max_idle_timeout": 30000,
                    "max_udp_payload_size": 65527,
                    "initial_max_data": 1048576,
                    "initial_max_stream_data_bidi_local": 262144,
                    "initial_max_stream_data_bidi_remote": 262144,
                    "initial_max_stream_data_uni": 262144,
                    "initial_max_streams_bidi": 100,
                    "initial_max_streams_uni": 100
                },
                "supported_versions": ["draft-29", "draft-32", "rfc9000"],
                "cipher_suites": ["TLS_AES_128_GCM_SHA256", "TLS_AES_256_GCM_SHA384"],
                "signature_algorithms": ["rsa_pss_rsae_sha256", "ecdsa_secp256r1_sha256"]
            }
        elif protocol == SupportedProtocol.TCP:
            return {
                "socket_options": {
                    "SO_REUSEADDR": True,
                    "TCP_NODELAY": True,
                    "SO_KEEPALIVE": True
                },
                "buffer_sizes": {
                    "send_buffer": 65536,
                    "receive_buffer": 65536
                }
            }
        elif protocol == SupportedProtocol.UDP:
            return {
                "socket_options": {
                    "SO_REUSEADDR": True,
                    "SO_BROADCAST": False
                },
                "datagram_size": {
                    "max_size": 65507,
                    "default_size": 1472
                }
            }
        
        return {}
    
    def adapt_test_for_protocol(self, base_test_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapt a base test configuration for the current protocol.
        
        Args:
            base_test_config: Base test configuration
            
        Returns:
            Protocol-adapted test configuration
        """
        protocol_name = self.get_protocol_name()
        adapted_config = base_test_config.copy()
        
        try:
            protocol = SupportedProtocol(protocol_name.lower())
        except ValueError:
            self.logger.warning(f"Cannot adapt for unknown protocol: {protocol_name}")
            return adapted_config
        
        # Add protocol-specific defaults
        protocol_defaults = self.get_default_test_configuration(protocol_name)
        for key, value in protocol_defaults.items():
            if key not in adapted_config:
                adapted_config[key] = value
        
        # Add protocol-specific parameters
        protocol_params = self.get_protocol_specific_parameters(protocol_name)
        if protocol_params:
            adapted_config.setdefault("protocol_parameters", {}).update(protocol_params)
        
        self.logger.debug(f"Adapted test configuration for protocol {protocol_name}")
        return adapted_config
    
    def is_protocol_supported(self, protocol_name: str) -> bool:
        """
        Check if a protocol is supported.
        
        Args:
            protocol_name: Protocol name to check
            
        Returns:
            True if protocol is supported, False otherwise
        """
        try:
            SupportedProtocol(protocol_name.lower())
            return True
        except ValueError:
            return False
    
    def get_opposite_role(self, role: str) -> str:
        """
        Get the opposite role for a given role.
        
        Args:
            role: Current role
            
        Returns:
            Opposite role
        """
        role_mappings = {
            "client": "server",
            "server": "client",
            "sender": "receiver",
            "receiver": "sender"
        }
        
        return role_mappings.get(role.lower(), role)