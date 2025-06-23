from panther.core.exceptions.error_handler_mixin import ErrorHandlerMixin


from typing import Any, Dict, List, Optional, Tuple


class IvyAnalysisMixin(ErrorHandlerMixin):
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
            ("_compilation_status_", "compilation_status"),
            ("_test_results_", "test_results"),
            ("_ivy_log_", "ivy_log"),
        ]

        for pattern, output_type in patterns:
            if pattern in output_key:
                parts = output_key.split(pattern)
                if len(parts) > 1:
                    return parts[1], output_type

        # Fallback patterns
        for prefix in ["stderr_", "stdout_", "compilation_status_", "test_results_"]:
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
        Analyze outputs for a single service.

        Args:
            service_name: Name of the service
            outputs: Service outputs by type

        Returns:
            Analysis result for the service
        """
        result = {
            "has_stderr": False,
            "has_errors": False,
            "execution_successful": False,
            "compilation_succeeded": False,
            "test_executed": False,
            "error_messages": []
        }

        # Check for errors
        if "stderr" in outputs and outputs["stderr"]:
            result["has_stderr"] = True
            errors = self._check_error_patterns(outputs["stderr"])
            if errors:
                result["has_errors"] = True
                result["error_messages"].extend(errors)

        # Check compilation status
        if not result["has_errors"]:
            result["compilation_succeeded"] = self._check_compilation_status(outputs)
            result["test_executed"] = self._verify_test_execution(outputs)

            # Determine overall success
            if result["compilation_succeeded"] and result["test_executed"]:
                result["execution_successful"] = True
            else:
                if not result["compilation_succeeded"]:
                    result["error_messages"].append("No confirmation of successful compilation")
                if not result["test_executed"]:
                    result["error_messages"].append("No confirmation of test execution")

        return result

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
        if "compilation_status" in outputs and outputs["compilation_status"]:
            status = outputs["compilation_status"].strip().lower()
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