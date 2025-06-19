"""Ivy output management functionality."""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin


class IvyOutputManager(ErrorHandlerMixin):
    """Manages Ivy output patterns and file collection."""
    
    # Standard Ivy output patterns
    OUTPUT_PATTERNS = {
        "verification_results": "*.ivy.results",
        "proof_files": "*.proof",
        "trace_files": "*.trace",
        "counterexample_files": "*.cex",
        "log_files": "*.log",
        "z3_output": "z3_*.out",
        "ivy_output": "ivy_*.out",
        "error_logs": "*.err",
        "debug_output": "debug_*.txt",
        "coverage_reports": "coverage_*.html",
        "timing_reports": "timing_*.json"
    }
    
    # QUIC-specific output patterns
    QUIC_OUTPUT_PATTERNS = {
        "quic_traces": "quic_*.pcap",
        "handshake_logs": "handshake_*.log",
        "connection_logs": "connection_*.log",
        "crypto_logs": "crypto_*.log",
        "flow_control_logs": "flow_*.log"
    }
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        self.collected_outputs = {}
        self.output_directories = []
        
    def get_ivy_output_patterns(self) -> Dict[str, str]:
        """
        Get all relevant output patterns based on protocol and configuration.
        
        Returns:
            Dictionary mapping pattern names to file patterns
        """
        patterns = self.OUTPUT_PATTERNS.copy()
        
        # Add protocol-specific patterns
        protocol_name = self._get_protocol_name()
        if protocol_name == "quic":
            patterns.update(self.QUIC_OUTPUT_PATTERNS)
        
        # Add custom patterns from configuration
        custom_patterns = self._get_custom_output_patterns()
        patterns.update(custom_patterns)
        
        self.logger.debug(f"Using {len(patterns)} output patterns")
        return patterns
    
    def configure_environment_outputs(self, environment_config: Dict[str, Any]) -> None:
        """
        Configure output collection based on environment settings.
        
        Args:
            environment_config: Environment configuration dictionary
        """
        try:
            # Set output directories
            base_output_dir = environment_config.get('output_directory', '/app/outputs')
            self.output_directories = [
                Path(base_output_dir),
                Path(base_output_dir) / "ivy",
                Path(base_output_dir) / "logs",
                Path(base_output_dir) / "traces",
                Path(base_output_dir) / "proofs"
            ]
            
            # Ensure directories exist
            for output_dir in self.output_directories:
                output_dir.mkdir(parents=True, exist_ok=True)
            
            # Configure collection parameters
            self.collection_config = {
                'compress_outputs': environment_config.get('compress_outputs', True),
                'preserve_timestamps': environment_config.get('preserve_timestamps', True),
                'max_file_size': environment_config.get('max_output_file_size', 100 * 1024 * 1024),  # 100MB
                'exclude_patterns': environment_config.get('exclude_patterns', ['*.tmp', '*.lock'])
            }
            
            self.logger.info(f"Configured output collection for {len(self.output_directories)} directories")
            
        except Exception as e:
            self.logger.error(f"Failed to configure environment outputs: {e}")
            raise
    
    def register_service_outputs(self, service_outputs: Dict[str, Any]) -> None:
        """
        Register outputs from service execution.
        
        Args:
            service_outputs: Dictionary of service-specific outputs
        """
        try:
            # Validate and sanitize output paths
            sanitized_outputs = {}
            
            for output_name, output_data in service_outputs.items():
                if self._is_valid_output_name(output_name):
                    sanitized_data = self._sanitize_output_data(output_data)
                    if sanitized_data:
                        sanitized_outputs[output_name] = sanitized_data
                    
            # Store registered outputs
            self.collected_outputs.update(sanitized_outputs)
            
            self.logger.info(f"Registered {len(sanitized_outputs)} service outputs")
            
        except Exception as e:
            self.logger.error(f"Failed to register service outputs: {e}")
    
    def set_collected_outputs(self, outputs: Dict[str, Any]) -> None:
        """
        Set the collected outputs dictionary.
        
        Args:
            outputs: Dictionary of collected outputs
        """
        try:
            # Validate and store outputs
            validated_outputs = {}
            
            for output_key, output_value in outputs.items():
                if self._is_safe_output_key(output_key):
                    validated_outputs[output_key] = output_value
                else:
                    self.logger.warning(f"Skipping unsafe output key: {output_key}")
            
            self.collected_outputs = validated_outputs
            self.logger.info(f"Set {len(validated_outputs)} collected outputs")
            
        except Exception as e:
            self.logger.error(f"Failed to set collected outputs: {e}")
    
    def get_collected_outputs(self) -> Dict[str, Any]:
        """
        Get all collected outputs.
        
        Returns:
            Dictionary of collected outputs
        """
        return self.collected_outputs.copy()
    
    def collect_ivy_outputs(self, ivy_workspace: Path) -> Dict[str, List[Path]]:
        """
        Collect all Ivy output files from the workspace.
        
        Args:
            ivy_workspace: Path to Ivy workspace directory
            
        Returns:
            Dictionary mapping output types to lists of file paths
        """
        collected = {}
        
        try:
            if not ivy_workspace.exists():
                self.logger.warning(f"Ivy workspace does not exist: {ivy_workspace}")
                return collected
            
            patterns = self.get_ivy_output_patterns()
            
            # Collect files for each pattern
            for pattern_name, file_pattern in patterns.items():
                matching_files = self._find_files_by_pattern(ivy_workspace, file_pattern)
                
                if matching_files:
                    # Filter and validate files
                    valid_files = []
                    for file_path in matching_files:
                        if self._is_valid_output_file(file_path):
                            valid_files.append(file_path)
                    
                    if valid_files:
                        collected[pattern_name] = valid_files
                        self.logger.debug(f"Collected {len(valid_files)} files for pattern {pattern_name}")
            
            self.logger.info(f"Collected outputs for {len(collected)} patterns")
            return collected
            
        except Exception as e:
            self.logger.error(f"Failed to collect Ivy outputs: {e}")
            return collected
    
    def archive_outputs(self, output_directory: Path, archive_name: str = "ivy_outputs.tar.gz") -> Optional[Path]:
        """
        Archive collected outputs into a compressed file.
        
        Args:
            output_directory: Directory to store the archive
            archive_name: Name of the archive file
            
        Returns:
            Path to created archive or None if failed
        """
        try:
            import tarfile
            
            archive_path = output_directory / archive_name
            
            with tarfile.open(archive_path, "w:gz") as tar:
                # Add collected output files
                for pattern_name, file_list in self.collected_outputs.items():
                    if isinstance(file_list, list):
                        for file_path in file_list:
                            if isinstance(file_path, (str, Path)) and Path(file_path).exists():
                                tar.add(file_path, arcname=f"{pattern_name}/{Path(file_path).name}")
            
            self.logger.info(f"Created output archive: {archive_path}")
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Failed to archive outputs: {e}")
            return None
    
    def _get_protocol_name(self) -> str:
        """Get the protocol name safely."""
        protocol_config = getattr(self.service_manager, 'protocol_config', None)
        if protocol_config and hasattr(protocol_config, 'name'):
            return str(protocol_config.name).lower()
        return "quic"  # Default protocol
    
    def _get_custom_output_patterns(self) -> Dict[str, str]:
        """Get custom output patterns from configuration."""
        custom_patterns = {}
        
        config = getattr(self.service_manager, 'config', {})
        if isinstance(config, dict):
            patterns = config.get('custom_output_patterns', {})
            if isinstance(patterns, dict):
                # Validate pattern names and values
                for name, pattern in patterns.items():
                    if self._is_valid_pattern_name(name) and self._is_valid_file_pattern(pattern):
                        custom_patterns[name] = pattern
        
        return custom_patterns
    
    def _find_files_by_pattern(self, directory: Path, pattern: str) -> List[Path]:
        """Find files matching a glob pattern in the directory."""
        try:
            # Use pathlib's glob for safe pattern matching
            matching_files = list(directory.glob(pattern))
            
            # Also search in subdirectories for some patterns
            if not matching_files and not pattern.startswith('**/'):
                matching_files = list(directory.glob(f"**/{pattern}"))
            
            return matching_files
            
        except Exception as e:
            self.logger.warning(f"Failed to find files with pattern {pattern}: {e}")
            return []
    
    def _is_valid_output_name(self, name: str) -> bool:
        """Check if output name is valid and safe."""
        import re
        # Allow alphanumeric, underscore, hyphen, and dot
        return isinstance(name, str) and re.match(r'^[a-zA-Z0-9_\-\.]+$', name) and len(name) <= 100
    
    def _is_safe_output_key(self, key: str) -> bool:
        """Check if output key is safe to use."""
        import re
        # Allow alphanumeric, underscore, hyphen, and forward slash for nested keys
        return isinstance(key, str) and re.match(r'^[a-zA-Z0-9_\-/]+$', key) and len(key) <= 200
    
    def _is_valid_pattern_name(self, name: str) -> bool:
        """Check if pattern name is valid."""
        import re
        return isinstance(name, str) and re.match(r'^[a-zA-Z0-9_]+$', name) and len(name) <= 50
    
    def _is_valid_file_pattern(self, pattern: str) -> bool:
        """Check if file pattern is valid and safe."""
        import re
        # Allow basic glob patterns but prevent directory traversal
        if not isinstance(pattern, str) or len(pattern) > 100:
            return False
        
        # Disallow dangerous patterns
        dangerous_patterns = ['../', '../', '~/', '/etc/', '/var/', '/usr/']
        for dangerous in dangerous_patterns:
            if dangerous in pattern:
                return False
        
        # Allow basic glob characters
        return re.match(r'^[a-zA-Z0-9_\-\*\?\.\[\]/]+$', pattern)
    
    def _is_valid_output_file(self, file_path: Path) -> bool:
        """Check if output file is valid for collection."""
        try:
            # Check if file exists and is readable
            if not file_path.exists() or not file_path.is_file():
                return False
            
            # Check file size limits
            max_size = getattr(self, 'collection_config', {}).get('max_file_size', 100 * 1024 * 1024)
            if file_path.stat().st_size > max_size:
                self.logger.warning(f"File too large to collect: {file_path}")
                return False
            
            # Check if file is in excluded patterns
            exclude_patterns = getattr(self, 'collection_config', {}).get('exclude_patterns', [])
            for pattern in exclude_patterns:
                if file_path.match(pattern):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Could not validate output file {file_path}: {e}")
            return False
    
    def _sanitize_output_data(self, data: Any) -> Any:
        """Sanitize output data for safe storage."""
        if isinstance(data, str):
            # Limit string length and remove control characters
            sanitized = ''.join(char for char in data if ord(char) >= 32 or char in '\n\t')
            return sanitized[:10000]  # Limit to 10KB
        elif isinstance(data, (int, float, bool)):
            return data
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_output_data(item) for item in data[:100]]  # Limit list size
        elif isinstance(data, dict):
            sanitized_dict = {}
            for key, value in list(data.items())[:50]:  # Limit dict size
                if self._is_safe_output_key(str(key)):
                    sanitized_dict[key] = self._sanitize_output_data(value)
            return sanitized_dict
        else:
            # Convert unknown types to string representation
            return str(data)[:1000]
        
    def _generate_sequence_diagram(self, sequence_data: Dict[str, Any]) -> str:
        """
        Generate a sequence diagram from the provided data.
        
        Args:
            sequence_data: Dictionary containing sequence data
            
        Returns:
            String representation of the sequence diagram
        """
        try:
            # Placeholder for actual diagram generation logic
            return "Generated sequence diagram based on provided data."
        except Exception as e:
            self.logger.error(f"Failed to generate sequence diagram: {e}")
            return ""
    
    def _generate_timing_report(self, timing_data: Dict[str, Any]) -> str:
        """
        Generate a timing report from the provided data.
        
        Args:
            timing_data: Dictionary containing timing data
            
        Returns:
            String representation of the timing report
        """
        try:
            # Placeholder for actual report generation logic
            return "Generated timing report based on provided data."
        except Exception as e:
            self.logger.error(f"Failed to generate timing report: {e}")
            return ""