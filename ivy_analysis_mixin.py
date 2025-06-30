from typing import Any, Dict, List, Optional, Tuple


class IvyAnalysisMixin:
    """
    Mixin for Ivy test output analysis with refactored methods.

    This mixin extracts and refactors the massive 241-line analyze_outputs()
    method into smaller, focused methods following PANTHER conventions.
    """

    def analyze_outputs_with_data(self, collected_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze collected outputs to determine test success/failure.

        Args:
            collected_outputs: Dictionary of collected outputs from services

        Returns:
            Dict[str, Any]: Analysis results
        """
        self.logger.info("Analyzing outputs from test execution")
        self.logger.debug(f"Collected outputs: {collected_outputs}")

        # Organize outputs by service
        service_outputs = self._organize_outputs_by_service(collected_outputs)

        # Analyze each service
        detailed_results = {}
        all_failures = []
        passed = False

        for service_name, outputs in service_outputs.items():
            service_result = self._analyze_service_outputs(service_name, outputs)
            detailed_results[service_name] = service_result

            if service_result["execution_successful"]:
                passed = True
            else:
                all_failures.extend(service_result["error_messages"])

        # Generate summary
        analysis_summary = self._generate_analysis_summary(passed, all_failures)

        return {
            "passed": passed,
            "analysis_summary": analysis_summary,
            "detailed_results": detailed_results,
            "failures": all_failures if not passed else []
        }

    def analyze_ivy_outputs(self) -> Dict[str, Any]:
        """
        Analyze collected outputs for Ivy tests.

        Wrapper method that uses the collected_outputs from the service manager
        and delegates to the core analyze_outputs_with_data method.

        Returns:
            Dict[str, Any]: Analysis results with passed/failed status
        """
        if not hasattr(self, 'collected_outputs') or not self.collected_outputs:
            self.logger.warning("No collected outputs available for analysis")
            return {
                "passed": False,
                "analysis_summary": "No outputs to analyze",
                "detailed_results": {},
                "failures": ["No collected outputs available"]
            }

        return self.analyze_outputs_with_data(self.collected_outputs)

    def _organize_outputs_by_service(self, collected_outputs: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """
        Reorganize outputs by service name for easier analysis.

        Args:
            collected_outputs: Raw collected outputs

        Returns:
            Dict organized by service name
        """
        service_outputs = {}

        for output_key, env_data in collected_outputs.items():
            # Extract service name and output type from key
            service_name, output_type = self._parse_output_key(output_key)

            if not service_name:
                continue

            # Get file content
            content = self._read_output_content(env_data)
            if content is not None:
                if service_name not in service_outputs:
                    service_outputs[service_name] = {}
                service_outputs[service_name][output_type] = content

        return service_outputs

    def _parse_output_key(self, output_key: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse output key to extract service name and output type.

        Args:
            output_key: Key like "ivy_stderr_ivy_server" or "stderr_picoquic_client"

        Returns:
            Tuple of (service_name, output_type) or (None, None)
        """
        # Common patterns to parse
        patterns = [
            ("_stderr_", "stderr"),
            ("_stdout_", "stdout"),
            ("_compile_status_", "compile_status"),  # Changed from compilation_status
            ("_test_results_", "test_results"),
            ("_ivy_log_", "ivy_log"),
        ]

        for pattern, output_type in patterns:
            if pattern in output_key:
                parts = output_key.split(pattern)
                if len(parts) > 1:
                    return parts[1], output_type

        # Fallback patterns
        for prefix in ["stderr_", "stdout_", "compile_status_", "test_results_"]:
            if output_key.startswith(prefix):
                return output_key[len(prefix):], prefix[:-1]

        return None, None

    def _read_output_content(self, env_data: Any) -> Optional[str]:
        """
        Read content from output file.

        Args:
            env_data: Environment data containing file path

        Returns:
            File content or None
        """
        if isinstance(env_data, dict):
            file_path = list(env_data.values())[0] if env_data else None
        else:
            file_path = env_data

        if file_path and isinstance(file_path, str):
            try:
                with open(file_path, 'r') as f:
                    return f.read()
            except Exception as e:
                self.logger.warning(f"Failed to read {file_path}: {e}")

        return None

    def _analyze_service_outputs(self, service_name: str, outputs: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyze outputs for a single service with enhanced details.

        Args:
            service_name: Name of the service
            outputs: Service outputs by type

        Returns:
            Enhanced analysis result for the service
        """
        result = {
            "has_stderr": False,
            "has_errors": False,
            "execution_successful": False,
            "compilation_succeeded": False,
            "test_executed": False,
            "error_messages": [],
            # Enhanced details
            "service_status": "unknown",
            "return_code": None,
            "exit_status": None,
            "runtime_duration": None,
            "connection_events": [],
            "performance_metrics": {},
            "detailed_errors": [],
            "process_lifecycle": {
                "started": False,
                "running": False,
                "completed": False,
                "terminated": False
            }
        }

        # Check for errors and extract detailed information
        if "stderr" in outputs and outputs["stderr"]:
            result["has_stderr"] = True
            
            # Extract basic errors
            errors = self._check_error_patterns(outputs["stderr"])
            if errors:
                result["has_errors"] = True
                result["error_messages"].extend(errors)
            
            # Enhanced stderr analysis
            stderr_analysis = self._analyze_stderr_details(outputs["stderr"], service_name)
            result.update(stderr_analysis)

        # Analyze stdout for additional details
        if "stdout" in outputs and outputs["stdout"]:
            stdout_analysis = self._analyze_stdout_details(outputs["stdout"], service_name)
            result.update(stdout_analysis)

        # Check compilation status
        if not result["has_errors"]:
            result["compilation_succeeded"] = self._check_compilation_status(outputs)
            result["test_executed"] = self._verify_test_execution(outputs)

            # Determine overall success
            if result["compilation_succeeded"] and result["test_executed"]:
                result["execution_successful"] = True
                result["service_status"] = "completed_successfully"
            else:
                if not result["compilation_succeeded"]:
                    result["error_messages"].append("No confirmation of successful compilation")
                    result["service_status"] = "compilation_failed"
                if not result["test_executed"]:
                    result["error_messages"].append("No confirmation of test execution")
                    if result["service_status"] == "unknown":
                        result["service_status"] = "execution_failed"
        else:
            result["service_status"] = "error_detected"

        return result

    def _analyze_stderr_details(self, stderr_content: str, service_name: str) -> Dict[str, Any]:
        """
        Extract detailed information from stderr content.

        Args:
            stderr_content: Content of stderr
            service_name: Name of the service

        Returns:
            Dictionary with detailed stderr analysis
        """
        details = {
            "connection_events": [],
            "detailed_errors": [],
            "performance_metrics": {},
            "process_lifecycle": {
                "started": False,
                "running": False,
                "completed": False,
                "terminated": False
            }
        }

        lines = stderr_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract connection events
            if "binding client id" in line.lower():
                details["connection_events"].append({
                    "type": "client_binding",
                    "details": line,
                    "timestamp": self._extract_timestamp(line)
                })
            elif "socket" in line.lower():
                details["connection_events"].append({
                    "type": "socket_event",
                    "details": line,
                    "timestamp": self._extract_timestamp(line)
                })

            # Extract process lifecycle events
            if "starting runtime phase" in line.lower():
                details["process_lifecycle"]["started"] = True
            elif "call_generating" in line.lower():
                details["process_lifecycle"]["running"] = True
            elif "cycles =" in line.lower():
                # Extract cycle count for performance metrics
                try:
                    cycles = line.split("cycles =")[1].strip().split()[0]
                    details["performance_metrics"]["total_cycles"] = int(cycles)
                except:
                    pass

            # Extract detailed error information
            if any(error_word in line.lower() for error_word in ["error", "failed", "timeout"]):
                details["detailed_errors"].append({
                    "message": line,
                    "timestamp": self._extract_timestamp(line),
                    "severity": self._determine_error_severity(line)
                })

        return details

    def _analyze_stdout_details(self, stdout_content: str, service_name: str) -> Dict[str, Any]:
        """
        Extract detailed information from stdout content.

        Args:
            stdout_content: Content of stdout
            service_name: Name of the service

        Returns:
            Dictionary with detailed stdout analysis
        """
        details = {
            "return_code": None,
            "exit_status": None,
            "runtime_duration": None
        }

        lines = stdout_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract return codes and exit status
            if "exit code" in line.lower() or "return code" in line.lower():
                try:
                    # Try to extract numeric exit code
                    import re
                    code_match = re.search(r'(?:exit|return)\s+code[:\s]+(\d+)', line, re.IGNORECASE)
                    if code_match:
                        details["return_code"] = int(code_match.group(1))
                        details["exit_status"] = "success" if details["return_code"] == 0 else "failure"
                except:
                    pass

            # Extract timing information
            if "duration" in line.lower() or "elapsed" in line.lower():
                try:
                    import re
                    time_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?|ms|milliseconds?)', line, re.IGNORECASE)
                    if time_match:
                        details["runtime_duration"] = time_match.group(1)
                except:
                    pass

        return details

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """
        Extract timestamp from log line if present.

        Args:
            line: Log line

        Returns:
            Timestamp string or None
        """
        import re
        # Look for timestamp patterns like [2025-06-24 03:53:47]
        timestamp_match = re.search(r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]', line)
        if timestamp_match:
            return timestamp_match.group(1)
        return None

    def _determine_error_severity(self, error_line: str) -> str:
        """
        Determine error severity based on keywords.

        Args:
            error_line: Error message line

        Returns:
            Severity level: critical, high, medium, low
        """
        error_line_lower = error_line.lower()
        
        if any(word in error_line_lower for word in ["critical", "fatal", "abort", "crash"]):
            return "critical"
        elif any(word in error_line_lower for word in ["error", "failed", "timeout"]):
            return "high"
        elif any(word in error_line_lower for word in ["warning", "warn"]):
            return "medium"
        else:
            return "low"

    def _check_error_patterns(self, stderr_content: str) -> List[str]:
        """
        Check stderr for error patterns.

        Args:
            stderr_content: Content of stderr

        Returns:
            List of error messages found
        """
        error_patterns = [
            "No such file or directory",
            "timeout: failed to run command",
            "error:",
            "Error:",
            "ERROR:",
            "failed:",
            "Failed:",
            "FAILED:"
        ]

        errors = []
        for pattern in error_patterns:
            if pattern in stderr_content:
                # Extract the line containing the error
                for line in stderr_content.split('\n'):
                    if pattern in line:
                        errors.append(line.strip())
                        break

        return errors

    def _check_compilation_status(self, outputs: Dict[str, str]) -> bool:
        """
        Check if compilation succeeded.

        Args:
            outputs: Service outputs

        Returns:
            True if compilation succeeded
        """
        # Check compilation_status.txt first
        if "compile_status" in outputs and outputs["compile_status"]:
            status = outputs["compile_status"].strip().lower()
            if "compilation succeeded" in status:
                return True
            elif "compilation failed" in status:
                return False

        # Check stdout for compilation success patterns
        if "stdout" in outputs and outputs["stdout"]:
            success_patterns = [
                "compilation succeeded",
                "compilation complete",
                "successfully built",
                "test executable created"
            ]

            stdout_lower = outputs["stdout"].lower()
            for pattern in success_patterns:
                if pattern in stdout_lower:
                    return True

        return False

    def _verify_test_execution(self, outputs: Dict[str, str]) -> bool:
        """
        Verify if test was executed.

        Args:
            outputs: Service outputs

        Returns:
            True if test was executed
        """
        # Check test_results first
        if "test_results" in outputs:
            return True

        # Check stdout for test execution patterns
        if "stdout" in outputs and outputs["stdout"]:
            execution_patterns = [
                "test started",
                "running test",
                "test complete",
                "test finished",
                "test passed",
                "all tests passed"
            ]

            stdout_lower = outputs["stdout"].lower()
            for pattern in execution_patterns:
                if pattern in stdout_lower:
                    return True

        return False

    def _generate_analysis_summary(self, passed: bool, failures: List[str]) -> str:
        """
        Generate human-readable analysis summary.

        Args:
            passed: Whether tests passed
            failures: List of failure messages

        Returns:
            Summary string
        """
        if passed:
            return "All tests passed successfully"
        else:
            if not failures:
                return "Tests failed: No positive confirmation of test success"
            else:
                return f"Tests failed: {'; '.join(failures[:3])}"  # Limit to first 3 failures