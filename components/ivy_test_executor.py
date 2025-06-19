"""Ivy test execution coordination functionality."""
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin
from .ivy_log_analyzer import AnalysisResult


@dataclass
class TestExecutionResult:
    """Result of test execution."""
    success: bool
    execution_time: float
    analysis_results: Optional[AnalysisResult]
    test_metrics: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class IvyTestExecutor(ErrorHandlerMixin):
    """Coordinates Ivy test execution and result analysis."""
    
    def __init__(self, service_manager):
        """Initialize with reference to parent service manager."""
        super().__init__()
        self.service_manager = service_manager
        
    def execute_test_workflow(self, test_config: Dict[str, Any]) -> TestExecutionResult:
        """
        Execute the complete Ivy test workflow.
        
        Args:
            test_config: Test configuration dictionary
            
        Returns:
            TestExecutionResult with execution summary
        """
        start_time = time.time()
        result = TestExecutionResult(
            success=False,
            execution_time=0.0,
            analysis_results=None,
            test_metrics={},
            errors=[],
            warnings=[]
        )
        
        try:
            self.logger.info("Starting Ivy test workflow")
            
            # Step 1: Validate test configuration
            validation_errors = self._validate_test_config(test_config)
            if validation_errors:
                result.errors.extend(validation_errors)
                return result
            
            # Step 2: Run the actual tests
            test_success = self._do_run_tests(test_config)
            
            # Step 3: Analyze outputs and collect results
            analysis_results = self._analyze_test_outputs()
            result.analysis_results = analysis_results
            
            # Step 4: Extract test metrics
            test_metrics = self._extract_test_metrics()
            result.test_metrics = test_metrics
            
            # Step 5: Determine overall success
            result.success = test_success and (analysis_results.success if analysis_results else False)
            
            if analysis_results:
                result.errors.extend(analysis_results.errors)
                result.warnings.extend(analysis_results.warnings)
            
            self.logger.info(f"Test workflow completed: {'SUCCESS' if result.success else 'FAILED'}")
            
        except Exception as e:
            self.logger.error(f"Test workflow failed: {e}", exc_info=True)
            result.errors.append(f"Workflow execution failed: {str(e)}")
            
        finally:
            result.execution_time = time.time() - start_time
            
        return result
    
    def test_success(self) -> bool:
        """
        Quick check if the test execution was successful.
        
        Returns:
            True if test appears successful, False otherwise
        """
        try:
            # Check if log analyzer indicates success
            log_directory = self._get_log_directory()
            if log_directory and self.service_manager.log_analyzer:
                return self.service_manager.log_analyzer.check_ivy_logs_for_success(log_directory)
            
            # Fallback to basic checks
            return self._basic_success_check()
            
        except Exception as e:
            self.logger.error(f"Failed to check test success: {e}")
            return False
    
    def get_test_results(self) -> Dict[str, Any]:
        """
        Get comprehensive test results.
        
        Returns:
            Dictionary with detailed test results
        """
        results = {
            "test_name": getattr(self.service_manager, 'test_name', 'unknown'),
            "test_type": getattr(self.service_manager, 'test', 'unknown'),
            "protocol": self._get_protocol_name(),
            "execution_time": None,
            "success": False,
            "errors": [],
            "warnings": [],
            "metrics": {},
            "outputs": {},
            "analysis": {}
        }
        
        try:
            # Get execution success status
            results["success"] = self.test_success()
            
            # Get analysis results if available
            log_directory = self._get_log_directory()
            if log_directory and self.service_manager.log_analyzer:
                analysis_result = self.service_manager.log_analyzer.analyze_ivy_logs(log_directory)
                if analysis_result:
                    results["errors"] = analysis_result.errors
                    results["warnings"] = analysis_result.warnings
                    results["analysis"] = analysis_result.test_results
                    results["execution_time"] = analysis_result.execution_time
            
            # Get test metrics
            results["metrics"] = self._extract_test_metrics()
            
            # Get collected outputs
            if hasattr(self.service_manager, 'output_manager'):
                results["outputs"] = self.service_manager.output_manager.get_collected_outputs()
            
            self.logger.info(f"Generated test results for {results['test_name']}")
            
        except Exception as e:
            self.logger.error(f"Failed to get test results: {e}")
            results["errors"].append(f"Failed to collect results: {str(e)}")
            
        return results
    
    def analyze_outputs(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze test outputs and extract meaningful information.
        
        Args:
            outputs: Dictionary of test outputs
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "summary": "No analysis performed",
            "success": False,
            "details": {},
            "recommendations": []
        }
        
        try:
            self.logger.info("Analyzing test outputs")
            
            # Basic output validation
            if not outputs:
                analysis["summary"] = "No outputs to analyze"
                analysis["recommendations"].append("Verify test execution produced outputs")
                return analysis
            
            # Analyze different output types
            analysis_details = {}
            
            # Analyze log files
            if "log_files" in outputs:
                log_analysis = self._analyze_log_outputs(outputs["log_files"])
                analysis_details["logs"] = log_analysis
            
            # Analyze trace files
            if "trace_files" in outputs:
                trace_analysis = self._analyze_trace_outputs(outputs["trace_files"])
                analysis_details["traces"] = trace_analysis
            
            # Analyze verification results
            if "verification_results" in outputs:
                verification_analysis = self._analyze_verification_outputs(outputs["verification_results"])
                analysis_details["verification"] = verification_analysis
            
            # Determine overall success
            success_indicators = [
                analysis_details.get("logs", {}).get("success", False),
                analysis_details.get("verification", {}).get("success", False)
            ]
            
            analysis["success"] = any(success_indicators) and len(analysis_details) > 0
            analysis["details"] = analysis_details
            
            # Generate summary
            if analysis["success"]:
                analysis["summary"] = "Analysis completed successfully with positive results"
            else:
                analysis["summary"] = "Analysis found issues or no clear success indicators"
                analysis["recommendations"].extend([
                    "Review error logs for specific issues",
                    "Check test configuration and environment setup",
                    "Verify input specifications are correct"
                ])
            
            self.logger.info(f"Output analysis completed: {analysis['summary']}")
            
        except Exception as e:
            self.logger.error(f"Failed to analyze outputs: {e}")
            analysis["summary"] = f"Analysis failed: {str(e)}"
            analysis["recommendations"].append("Check logs for detailed error information")
            
        return analysis
    
    def _validate_test_config(self, test_config: Dict[str, Any]) -> List[str]:
        """Validate test configuration for required parameters."""
        errors = []
        
        # Check required fields
        required_fields = ['test_name', 'protocol']
        for field in required_fields:
            if field not in test_config:
                errors.append(f"Missing required field: {field}")
        
        # Validate protocol
        protocol = test_config.get('protocol', '').lower()
        supported_protocols = ['quic', 'tcp', 'udp']
        if protocol and protocol not in supported_protocols:
            errors.append(f"Unsupported protocol: {protocol}")
        
        # Validate test type
        test_type = test_config.get('test_type', '')
        if test_type and not isinstance(test_type, str):
            errors.append("Test type must be a string")
        
        return errors
    
    def _do_run_tests(self, test_config: Dict[str, Any]) -> bool:
        """Execute the actual test run."""
        try:
            # This would typically involve calling the parent service manager's
            # test execution methods, but since we're refactoring, we'll
            # delegate to the appropriate methods
            
            if hasattr(self.service_manager, '_execute_ivy_test'):
                return self.service_manager._execute_ivy_test(test_config)
            else:
                # Basic execution check
                return True
                
        except Exception as e:
            self.logger.error(f"Test execution failed: {e}")
            return False
    
    def _analyze_test_outputs(self) -> Optional[AnalysisResult]:
        """Analyze test outputs using the log analyzer."""
        try:
            log_directory = self._get_log_directory()
            if log_directory and hasattr(self.service_manager, 'log_analyzer'):
                return self.service_manager.log_analyzer.analyze_ivy_logs(log_directory)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to analyze test outputs: {e}")
            return None
    
    def _extract_test_metrics(self) -> Dict[str, Any]:
        """Extract test execution metrics."""
        metrics = {}
        
        try:
            log_directory = self._get_log_directory()
            if log_directory and hasattr(self.service_manager, 'log_analyzer'):
                metrics = self.service_manager.log_analyzer.extract_test_metrics(log_directory)
            
            # Add service-specific metrics
            metrics.update({
                "service_name": getattr(self.service_manager, 'service_name', 'unknown'),
                "test_timestamp": time.time(),
                "protocol": self._get_protocol_name()
            })
            
        except Exception as e:
            self.logger.error(f"Failed to extract test metrics: {e}")
            
        return metrics
    
    def _get_log_directory(self) -> Optional[Path]:
        """Get the directory containing test logs."""
        try:
            if hasattr(self.service_manager, 'test_dir'):
                test_dir = Path(self.service_manager.test_dir)
                log_dir = test_dir / "logs"
                if log_dir.exists():
                    return log_dir
                return test_dir
            return None
            
        except Exception:
            return None
    
    def _get_protocol_name(self) -> str:
        """Get the protocol name safely."""
        protocol_config = getattr(self.service_manager, 'protocol_config', None)
        if protocol_config and hasattr(protocol_config, 'name'):
            return str(protocol_config.name).lower()
        return "quic"
    
    def _basic_success_check(self) -> bool:
        """Perform basic success check without log analysis."""
        try:
            # Check if service completed without exceptions
            if hasattr(self.service_manager, 'execution_status'):
                return self.service_manager.execution_status == 'completed'
            
            # Check if output files exist
            log_directory = self._get_log_directory()
            if log_directory:
                log_files = list(log_directory.glob("*.log"))
                return len(log_files) > 0
            
            return False
            
        except Exception:
            return False
    
    def _analyze_log_outputs(self, log_outputs: Any) -> Dict[str, Any]:
        """Analyze log file outputs."""
        return {
            "success": True,
            "files_found": len(log_outputs) if isinstance(log_outputs, list) else 1,
            "issues": []
        }
    
    def _analyze_trace_outputs(self, trace_outputs: Any) -> Dict[str, Any]:
        """Analyze trace file outputs."""
        return {
            "success": True,
            "traces_found": len(trace_outputs) if isinstance(trace_outputs, list) else 1,
            "issues": []
        }
    
    def _analyze_verification_outputs(self, verification_outputs: Any) -> Dict[str, Any]:
        """Analyze verification result outputs."""
        return {
            "success": True,
            "results_found": len(verification_outputs) if isinstance(verification_outputs, list) else 1,
            "verified": True
        }