"""Ivy log analysis functionality."""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin


@dataclass
class AnalysisResult:
    """Result of log analysis."""
    success: bool
    errors: List[str]
    warnings: List[str]
    test_results: Dict[str, Any]
    execution_time: Optional[float] = None
    
    def add_error(self, error: str) -> None:
        """Add an error to the analysis result."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the analysis result."""
        self.warnings.append(warning)


class IvyLogAnalyzer(ErrorHandlerMixin):
    """Analyzes Ivy execution logs and extracts test results."""
    
    # Success indicators in Ivy logs
    SUCCESS_PATTERNS = [
        r"OK\s*$",
        r"PASS\s*$", 
        r"verification\s+succeeded",
        r"proof\s+complete",
        r"all\s+checks\s+passed",
        r"specification\s+verified"
    ]
    
    # Error patterns in Ivy logs
    ERROR_PATTERNS = [
        r"error:\s*(.+)",
        r"Error:\s*(.+)",
        r"ERROR:\s*(.+)",
        r"failed:\s*(.+)",
        r"Failed:\s*(.+)",
        r"FAILED:\s*(.+)",
        r"assertion\s+failed:\s*(.+)",
        r"verification\s+failed:\s*(.+)"
    ]
    
    # Warning patterns in Ivy logs
    WARNING_PATTERNS = [
        r"warning:\s*(.+)",
        r"Warning:\s*(.+)",
        r"WARNING:\s*(.+)",
        r"deprecated:\s*(.+)"
    ]
    
    # QUIC-specific error codes
    QUIC_ERROR_CODES = {
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
    }
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        
    def analyze_ivy_logs(self, log_directory: Path) -> AnalysisResult:
        """
        Analyze all Ivy log files in the given directory.
        
        Args:
            log_directory: Directory containing Ivy log files
            
        Returns:
            AnalysisResult with analysis summary
        """
        result = AnalysisResult(
            success=True,
            errors=[],
            warnings=[],
            test_results={}
        )
        
        try:
            if not log_directory.exists():
                result.add_error(f"Log directory does not exist: {log_directory}")
                return result
            
            # Find all log files
            log_files = self._find_log_files(log_directory)
            
            if not log_files:
                result.add_warning("No log files found for analysis")
                return result
            
            self.logger.info(f"Analyzing {len(log_files)} log files")
            
            # Analyze each log file
            for log_file in log_files:
                file_result = self._analyze_single_log_file(log_file)
                self._merge_results(result, file_result, log_file.name)
            
            # Perform overall analysis
            self._perform_overall_analysis(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to analyze Ivy logs: {e}")
            result.add_error(f"Analysis failed: {str(e)}")
            return result
    
    def check_ivy_logs_for_success(self, log_directory: Path) -> bool:
        """
        Quick check if Ivy execution was successful.
        
        Args:
            log_directory: Directory containing Ivy log files
            
        Returns:
            True if execution appears successful, False otherwise
        """
        try:
            analysis_result = self.analyze_ivy_logs(log_directory)
            return analysis_result.success and len(analysis_result.errors) == 0
            
        except Exception as e:
            self.logger.error(f"Failed to check Ivy logs: {e}")
            return False
    
    def extract_test_metrics(self, log_directory: Path) -> Dict[str, Any]:
        """
        Extract performance and execution metrics from logs.
        
        Args:
            log_directory: Directory containing Ivy log files
            
        Returns:
            Dictionary with extracted metrics
        """
        metrics = {
            "execution_time": None,
            "memory_usage": None,
            "verification_steps": 0,
            "assertions_checked": 0,
            "proof_obligations": 0,
            "z3_calls": 0
        }
        
        try:
            log_files = self._find_log_files(log_directory)
            
            for log_file in log_files:
                content = self._read_log_file_safely(log_file)
                if content:
                    self._extract_metrics_from_content(content, metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to extract test metrics: {e}")
            return metrics
    
    def get_quic_error_description(self, error_code: int) -> str:
        """
        Get human-readable description for QUIC error code.
        
        Args:
            error_code: QUIC error code
            
        Returns:
            Human-readable error description
        """
        return self.QUIC_ERROR_CODES.get(error_code, f"UNKNOWN_ERROR_{error_code}")
    
    def _find_log_files(self, log_directory: Path) -> List[Path]:
        """Find all relevant log files in the directory."""
        log_files = []
        
        # Common log file patterns
        log_patterns = [
            "*.log",
            "*.out",
            "ivy_*.txt",
            "verification_*.log",
            "z3_*.log"
        ]
        
        for pattern in log_patterns:
            log_files.extend(log_directory.glob(pattern))
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        return log_files
    
    def _analyze_single_log_file(self, log_file: Path) -> AnalysisResult:
        """Analyze a single log file."""
        result = AnalysisResult(
            success=True,
            errors=[],
            warnings=[],
            test_results={}
        )
        
        try:
            content = self._read_log_file_safely(log_file)
            if not content:
                result.add_warning(f"Could not read log file: {log_file}")
                return result
            
            # Check for success patterns
            success_found = self._check_success_patterns(content)
            
            # Extract errors
            errors = self._extract_errors(content)
            
            # Extract warnings
            warnings = self._extract_warnings(content)
            
            # Extract test-specific results
            test_results = self._extract_test_results(content)
            
            # Set overall success status
            result.success = success_found and len(errors) == 0
            result.errors = errors
            result.warnings = warnings
            result.test_results = test_results
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to analyze log file {log_file}: {e}")
            result.add_error(f"Failed to analyze {log_file.name}: {str(e)}")
            return result
    
    def _read_log_file_safely(self, log_file: Path) -> Optional[str]:
        """Safely read a log file with encoding handling."""
        try:
            # Try UTF-8 first
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            try:
                # Fallback to latin-1
                with open(log_file, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                self.logger.warning(f"Could not read {log_file}: {e}")
                return None
        except Exception as e:
            self.logger.warning(f"Could not read {log_file}: {e}")
            return None
    
    def _check_success_patterns(self, content: str) -> bool:
        """Check if content contains success indicators."""
        for pattern in self.SUCCESS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return True
        return False
    
    def _extract_errors(self, content: str) -> List[str]:
        """Extract error messages from log content."""
        errors = []
        
        for pattern in self.ERROR_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if match.group(1):
                    errors.append(match.group(1).strip())
                else:
                    errors.append(match.group(0).strip())
        
        return list(set(errors))  # Remove duplicates
    
    def _extract_warnings(self, content: str) -> List[str]:
        """Extract warning messages from log content."""
        warnings = []
        
        for pattern in self.WARNING_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if match.group(1):
                    warnings.append(match.group(1).strip())
                else:
                    warnings.append(match.group(0).strip())
        
        return list(set(warnings))  # Remove duplicates
    
    def _extract_test_results(self, content: str) -> Dict[str, Any]:
        """Extract test-specific results from log content."""
        results = {}
        
        # Extract execution time
        time_match = re.search(r"total\s+time:\s*([0-9.]+)\s*(s|seconds|ms|milliseconds)", content, re.IGNORECASE)
        if time_match:
            time_value = float(time_match.group(1))
            time_unit = time_match.group(2).lower()
            if time_unit.startswith('ms'):
                time_value /= 1000  # Convert to seconds
            results['execution_time'] = time_value
        
        # Extract verification results
        verification_match = re.search(r"verified\s+(\d+)\s+assertion", content, re.IGNORECASE)
        if verification_match:
            results['verified_assertions'] = int(verification_match.group(1))
        
        # Extract proof obligations
        proof_match = re.search(r"(\d+)\s+proof\s+obligation", content, re.IGNORECASE)
        if proof_match:
            results['proof_obligations'] = int(proof_match.group(1))
        
        # Extract Z3 solver calls
        z3_match = re.search(r"z3\s+calls:\s*(\d+)", content, re.IGNORECASE)
        if z3_match:
            results['z3_calls'] = int(z3_match.group(1))
        
        return results
    
    def _extract_metrics_from_content(self, content: str, metrics: Dict[str, Any]) -> None:
        """Extract metrics from log content and update metrics dict."""
        # Update execution time if found
        time_match = re.search(r"total\s+time:\s*([0-9.]+)\s*s", content, re.IGNORECASE)
        if time_match and not metrics['execution_time']:
            metrics['execution_time'] = float(time_match.group(1))
        
        # Count verification steps
        step_matches = re.findall(r"verification\s+step", content, re.IGNORECASE)
        metrics['verification_steps'] += len(step_matches)
        
        # Count assertions
        assertion_matches = re.findall(r"assertion\s+checked", content, re.IGNORECASE)
        metrics['assertions_checked'] += len(assertion_matches)
        
        # Count Z3 calls
        z3_matches = re.findall(r"z3\s+call", content, re.IGNORECASE)
        metrics['z3_calls'] += len(z3_matches)
    
    def _merge_results(self, main_result: AnalysisResult, file_result: AnalysisResult, file_name: str) -> None:
        """Merge file-specific results into main result."""
        # Merge errors with file context
        for error in file_result.errors:
            main_result.errors.append(f"[{file_name}] {error}")
        
        # Merge warnings with file context
        for warning in file_result.warnings:
            main_result.warnings.append(f"[{file_name}] {warning}")
        
        # Merge test results
        if file_result.test_results:
            main_result.test_results[file_name] = file_result.test_results
        
        # Update overall success status
        if not file_result.success:
            main_result.success = False
    
    def _perform_overall_analysis(self, result: AnalysisResult) -> None:
        """Perform overall analysis on merged results."""
        # Check if we have meaningful results
        if not result.test_results and result.success:
            result.add_warning("No meaningful test results found in logs")
        
        # Check for common issues
        error_text = " ".join(result.errors).lower()
        
        if "timeout" in error_text:
            result.add_warning("Execution may have timed out")
        
        if "memory" in error_text:
            result.add_warning("Execution may have run out of memory")
        
        if "z3" in error_text:
            result.add_warning("Z3 solver issues detected")
        
        # Set final success status
        result.success = result.success and len(result.errors) == 0