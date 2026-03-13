"""
Core mixins for PantherIvy service manager following PANTHER architectural standards.

This module provides focused mixins that extract common functionality from the main
PantherIvy service manager, promoting code reuse and maintaining separation of concerns.
"""

import logging
import os
from pathlib import Path
from typing import Optional


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
        if hasattr(self, "protocol") and self.protocol:
            if hasattr(self.protocol, "name"):
                protocol_name = getattr(self.protocol, "name", None)
                if hasattr(self, "logger"):
                    self.logger.debug(
                        f"Found protocol name from self.protocol.name: {protocol_name}"
                    )
            elif isinstance(self.protocol, str):
                protocol_name = self.protocol
                if hasattr(self, "logger"):
                    self.logger.debug(
                        f"Found protocol name from self.protocol string: {protocol_name}"
                    )

        # Method 2: Check service config protocol
        if protocol_name is None and hasattr(self, "service_config_to_test"):
            if hasattr(self.service_config_to_test, "protocol") and hasattr(
                self.service_config_to_test.protocol, "name"
            ):
                protocol_name = getattr(
                    self.service_config_to_test.protocol, "name", None
                )
                if hasattr(self, "logger"):
                    self.logger.debug(
                        f"Found protocol name from service config: {protocol_name}"
                    )

        # Method 3: Check _original_service_config if available (fallback)
        if protocol_name is None and hasattr(self, "_original_service_config"):
            if hasattr(self._original_service_config, "protocol") and hasattr(
                self._original_service_config.protocol, "name"
            ):
                protocol_name = getattr(
                    self._original_service_config.protocol, "name", None
                )
                if hasattr(self, "logger"):
                    self.logger.debug(
                        f"Found protocol name from original service config: {protocol_name}"
                    )

        if protocol_name is None:
            protocol_name = "unknown"
            if hasattr(self, "logger"):
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
        base_path = os.getenv(
            "PANTHER_IVY_BASE_PATH", "/opt/panther_ivy/protocol-testing"
        )

        if use_system_models:
            # Get APT subpath from environment variable or use default
            apt_subpath = os.getenv("PANTHER_IVY_APT_SUBPATH", "apt/apt_protocols")
            return f"{base_path}/{apt_subpath}/{protocol_name}"
        else:
            # Get standard subpath from environment variable (empty by default)
            standard_subpath = os.getenv("PANTHER_IVY_STANDARD_SUBPATH", "")
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
        local_base_path = os.getenv("PANTHER_IVY_LOCAL_BASE_PATH")
        if local_base_path:
            base_path = Path(local_base_path)
        else:
            base_path = Path(__file__).parent / "protocol-testing"

        protocol_name = self.get_protocol_name()

        if use_system_models:
            # Get local APT subpath from environment variable or use default
            apt_subpath = os.getenv(
                "PANTHER_IVY_LOCAL_APT_SUBPATH", "apt/apt_protocols"
            )
            return str(base_path / apt_subpath / protocol_name)
        else:
            # Get local standard subpath from environment variable (empty by default)
            standard_subpath = os.getenv("PANTHER_IVY_LOCAL_STANDARD_SUBPATH", "")
            if standard_subpath:
                return str(base_path / standard_subpath / protocol_name)
            return str(base_path / protocol_name)
