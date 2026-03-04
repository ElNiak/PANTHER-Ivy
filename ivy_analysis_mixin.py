import re
from typing import Any, Dict, List, Optional, Tuple

from ._shared import determine_verdict


class IvyAnalysisMixin:
    """
    Mixin for Ivy test output analysis with refactored methods.

    This mixin extracts and refactors the massive 241-line analyze_outputs()
    method into smaller, focused methods following PANTHER conventions.
    """

    def analyze_outputs_with_data(
        self, collected_outputs: Dict[str, Any]
    ) -> Dict[str, Any]:
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
        seen_failures = set()

        for service_name, outputs in service_outputs.items():
            service_result = self._analyze_service_outputs(service_name, outputs)
            detailed_results[service_name] = service_result

            verdict = service_result.get("verdict", "UNKNOWN")
            if verdict != "UNKNOWN":
                # Decisive IVY verdict — only NO_VIOLATION_FOUND is a pass
                if verdict != "NO_VIOLATION_FOUND":
                    for msg in service_result["error_messages"]:
                        if msg not in seen_failures:
                            seen_failures.add(msg)
                            all_failures.append(msg)
            elif not service_result["execution_successful"]:
                for msg in service_result["error_messages"]:
                    if msg not in seen_failures:
                        seen_failures.add(msg)
                        all_failures.append(msg)

        # Test passes only if at least one decisive verdict is NO_VIOLATION_FOUND,
        # no decisive verdict is negative, and all compilations succeeded
        decisive = {
            name: r.get("verdict", "UNKNOWN")
            for name, r in detailed_results.items()
            if r.get("verdict", "UNKNOWN") != "UNKNOWN"
        }
        all_compilations_succeeded = all(
            r.get("compilation_succeeded", False) for r in detailed_results.values()
        )
        if decisive:
            passed = (
                all(v == "NO_VIOLATION_FOUND" for v in decisive.values())
                and all_compilations_succeeded
            )
        else:
            # No IVY-specific verdict — cannot positively confirm success
            passed = False

        # Generate summary
        analysis_summary = self._generate_analysis_summary(passed, all_failures)

        return {
            "passed": passed,
            "analysis_summary": analysis_summary,
            "detailed_results": detailed_results,
            "failures": all_failures,
        }

    def analyze_ivy_outputs(self) -> Dict[str, Any]:
        """
        Analyze collected outputs for Ivy tests.

        Wrapper method that uses the collected_outputs from the service manager
        and delegates to the core analyze_outputs_with_data method.

        Returns:
            Dict[str, Any]: Analysis results with passed/failed status
        """
        if not hasattr(self, "collected_outputs") or not self.collected_outputs:
            self.logger.warning("No collected outputs available for analysis")
            return {
                "passed": False,
                "analysis_summary": "No outputs to analyze",
                "detailed_results": {},
                "failures": ["No collected outputs available"],
            }

        return self.analyze_outputs_with_data(self.collected_outputs)

    def _organize_outputs_by_service(
        self, collected_outputs: Dict[str, Any]
    ) -> Dict[str, Dict[str, str]]:
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
                if output_type in service_outputs[service_name]:
                    service_outputs[service_name][output_type] += "\n" + content
                else:
                    service_outputs[service_name][output_type] = content

        return service_outputs

    def _parse_output_key(self, output_key: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse output key to extract service name and output type.

        Keys from Docker Compose output collector follow the format
        ``{phase}_{type}_{service_name}`` – for example:
        - ``runtime_stdout_ivy_server``
        - ``compilation_status_ivy_server``
        - ``compile_stderr_ivy_server``

        Args:
            output_key: Key like "runtime_stderr_ivy_server" or "compilation_status_ivy_server"

        Returns:
            Tuple of (service_name, output_type) or (None, None)
        """
        # Infix patterns – matched as substrings inside the key.
        # Order matters: more specific patterns first to avoid partial matches.
        infix_patterns = [
            ("_compilation_status_", "compile_status"),
            ("_compile_status_", "compile_status"),
            ("_test_results_", "test_results"),
            ("_ivy_log_", "ivy_log"),
            ("_stderr_", "stderr"),
            ("_stdout_", "stdout"),
        ]

        for pattern, output_type in infix_patterns:
            if pattern in output_key:
                parts = output_key.split(pattern)
                if len(parts) > 1:
                    return parts[1], output_type

        # Prefix patterns – keys that start with the type directly.
        prefix_patterns = [
            ("compilation_status_", "compile_status"),
            ("compile_status_", "compile_status"),
            ("runtime_stdout_", "stdout"),
            ("runtime_stderr_", "stderr"),
            ("compile_stdout_", "stdout"),
            ("compile_stderr_", "stderr"),
            ("stderr_", "stderr"),
            ("stdout_", "stdout"),
            ("test_results_", "test_results"),
        ]

        for prefix, output_type in prefix_patterns:
            if output_key.startswith(prefix):
                return output_key[len(prefix) :], output_type

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
                with open(file_path, "r") as f:
                    return f.read()
            except Exception as e:
                self.logger.warning(f"Failed to read {file_path}: {e}")

        return None

    def _analyze_service_outputs(
        self, service_name: str, outputs: Dict[str, str]
    ) -> Dict[str, Any]:
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
                "terminated": False,
            },
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
            stderr_analysis = self._analyze_stderr_details(
                outputs["stderr"], service_name
            )
            result.update(stderr_analysis)

        # Analyze stdout for additional details
        if "stdout" in outputs and outputs["stdout"]:
            stdout_analysis = self._analyze_stdout_details(
                outputs["stdout"], service_name
            )
            result.update(stdout_analysis)

        # Check compilation and test execution markers
        result["compilation_succeeded"] = self._check_compilation_status(outputs)
        result["test_executed"] = self._verify_test_execution(outputs)

        # --- IVY verdict determination (primary decision logic) ---
        stdout_content = outputs.get("stdout", "")
        stderr_content = outputs.get("stderr", "")
        verdict_info = self._determine_ivy_verdict(stdout_content, stderr_content)
        result["verdict"] = verdict_info["verdict"]
        result["assumption_failures"] = verdict_info["assumption_failures"]

        verdict = verdict_info["verdict"]

        if verdict == "NO_VIOLATION_FOUND":
            result["execution_successful"] = True
            result["service_status"] = "no_violation_found"
        elif verdict == "NON_COMPLIANT":
            result["execution_successful"] = False
            result["service_status"] = "non_compliant"
            for af in verdict_info["assumption_failures"]:
                result["error_messages"].append(af)
        elif verdict == "TESTER_CRASH":
            result["execution_successful"] = False
            result["service_status"] = "tester_crash"
            result["error_messages"].extend(verdict_info["details"])
        elif verdict == "IUT_CRASH":
            result["execution_successful"] = False
            result["service_status"] = "iut_crash"
            result["error_messages"].extend(verdict_info["details"])
        else:
            # UNKNOWN – fall back to compilation + lifecycle heuristics
            if result["has_errors"]:
                result["service_status"] = "error_detected"
            elif result["compilation_succeeded"] and result["test_executed"]:
                result["execution_successful"] = True
                result["service_status"] = "completed_successfully"
            else:
                # Fallback: infer success from process lifecycle when explicit
                # markers are absent. The Ivy container doesn't always produce
                # "compilation succeeded" / "test started" text, but stderr
                # lifecycle events (started, running) plus a clean exit are
                # strong evidence that the test ran without issues.
                lifecycle = result.get("process_lifecycle", {})
                exit_code = result.get("return_code")
                process_completed_cleanly = (
                    lifecycle.get("started", False)
                    and not result["has_errors"]
                    and (exit_code is None or exit_code == 0)
                )
                if process_completed_cleanly:
                    result["execution_successful"] = True
                    result["service_status"] = "completed_inferred"
                else:
                    if not result["compilation_succeeded"]:
                        result["error_messages"].append(
                            "No confirmation of successful compilation"
                        )
                        result["service_status"] = "compilation_failed"
                    if not result["test_executed"]:
                        result["error_messages"].append(
                            "No confirmation of test execution"
                        )
                        if result["service_status"] == "unknown":
                            result["service_status"] = "execution_failed"

        return result

    def _analyze_stderr_details(
        self, stderr_content: str, service_name: str
    ) -> Dict[str, Any]:
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
                "terminated": False,
            },
        }

        lines = stderr_content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract connection events
            if "binding client id" in line.lower():
                details["connection_events"].append(
                    {
                        "type": "client_binding",
                        "details": line,
                        "timestamp": self._extract_timestamp(line),
                    }
                )
            elif "socket" in line.lower():
                details["connection_events"].append(
                    {
                        "type": "socket_event",
                        "details": line,
                        "timestamp": self._extract_timestamp(line),
                    }
                )

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
                except (ValueError, IndexError, AttributeError):
                    self.logger.debug(f"Could not extract cycle count from: {line!r}")

            # Extract detailed error information
            if any(
                error_word in line.lower()
                for error_word in ["error", "failed", "timeout"]
            ):
                details["detailed_errors"].append(
                    {
                        "message": line,
                        "timestamp": self._extract_timestamp(line),
                        "severity": self._determine_error_severity(line),
                    }
                )

        return details

    def _analyze_stdout_details(
        self, stdout_content: str, service_name: str
    ) -> Dict[str, Any]:
        """
        Extract detailed information from stdout content.

        Args:
            stdout_content: Content of stdout
            service_name: Name of the service

        Returns:
            Dictionary with detailed stdout analysis
        """
        details = {"return_code": None, "exit_status": None, "runtime_duration": None}

        lines = stdout_content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract return codes and exit status
            if "exit code" in line.lower() or "return code" in line.lower():
                try:
                    # Try to extract numeric exit code
                    code_match = re.search(
                        r"(?:exit|return)\s+code[:\s]+(\d+)", line, re.IGNORECASE
                    )
                    if code_match:
                        details["return_code"] = int(code_match.group(1))
                        details["exit_status"] = (
                            "success" if details["return_code"] == 0 else "failure"
                        )
                except (ValueError, IndexError, AttributeError):
                    self.logger.debug(f"Could not extract exit code from: {line!r}")

            # Extract timing information
            if "duration" in line.lower() or "elapsed" in line.lower():
                try:
                    time_match = re.search(
                        r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?|ms|milliseconds?)",
                        line,
                        re.IGNORECASE,
                    )
                    if time_match:
                        details["runtime_duration"] = time_match.group(1)
                except (ValueError, IndexError, AttributeError):
                    self.logger.debug(f"Could not extract duration from: {line!r}")

        return details

    # ------------------------------------------------------------------
    # IVY verdict determination
    # ------------------------------------------------------------------

    def _determine_ivy_verdict(
        self, stdout_content: str, stderr_content: str
    ) -> Dict[str, Any]:
        """Determine IVY test verdict from stdout/stderr markers.

        Delegates to the shared pure function ``determine_verdict()``
        in ``panther_ivy._shared``, which is the single source of truth
        for verdict logic, regex patterns, and crash indicators.

        Returns:
            Dict with keys: verdict, details, assumption_failures
        """
        return determine_verdict(stdout_content, stderr_content)

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """
        Extract timestamp from log line if present.

        Args:
            line: Log line

        Returns:
            Timestamp string or None
        """
        # Look for timestamp patterns like [2025-06-24 03:53:47]
        timestamp_match = re.search(
            r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]", line
        )
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

        if any(
            word in error_line_lower for word in ["critical", "fatal", "abort", "crash"]
        ):
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
            "FAILED:",
        ]

        errors = []
        for pattern in error_patterns:
            if pattern in stderr_content:
                # Extract the line containing the error
                for line in stderr_content.split("\n"):
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
        # Check compilation_status / compile_status key (both variants)
        # Accept multiple status formats for flexibility:
        # - Full status messages like "Compilation succeeded" / "Compilation failed with code X"
        # - Short status values like "succeeded", "success", "ok", "failed", "error"
        for key in ("compile_status", "compilation_status"):
            if key in outputs and outputs[key]:
                status = outputs[key].strip().lower()
                failure_patterns = [
                    "compilation failed",
                    "failed",
                    "error",
                ]
                success_patterns = [
                    "compilation succeeded",
                    "succeeded",
                    "success",
                    "ok",
                ]
                # Check failure first to avoid masking by partial matches
                if any(status == p or p in status for p in failure_patterns):
                    return False
                elif any(status == p or p in status for p in success_patterns):
                    return True

        # Check stdout for compilation success patterns
        if "stdout" in outputs and outputs["stdout"]:
            success_patterns = [
                "compilation succeeded",
                "compilation complete",
                "successfully built",
                "test executable created",
            ]

            stdout_lower = outputs["stdout"].lower()
            for pattern in success_patterns:
                if pattern in stdout_lower:
                    return True

        # Fallback: check stderr for lifecycle evidence of successful compilation
        if "stderr" in outputs and outputs["stderr"]:
            stderr_lower = outputs["stderr"].lower()
            if (
                "starting runtime phase" in stderr_lower
                or "call_generating" in stderr_lower
            ):
                return True

        return False

    def _verify_test_execution(self, outputs: Dict[str, str]) -> bool:
        """
        Verify if test was actually executed.

        IVY tests don't emit generic "test started" / "running test" messages.
        Instead we look for IVY-specific evidence:
        - Protocol event markers (``<`` or ``>``) in stdout
        - ``assumption_failed`` in stdout (proves the test ran)
        - ``test_completed`` in stdout
        - ``call_generating`` / ``cycles =`` in stderr

        Args:
            outputs: Service outputs

        Returns:
            True if test was executed
        """
        # Check test_results first
        if "test_results" in outputs:
            return True

        # Check stdout for IVY-specific execution evidence
        if "stdout" in outputs and outputs["stdout"]:
            stdout = outputs["stdout"]
            # Protocol event markers (e.g. "> quic_connected" or "< quic_packet")
            if re.search(r"^[<>]\s", stdout, re.MULTILINE):
                return True
            if "assumption_failed" in stdout:
                return True
            if "test_completed" in stdout:
                return True

        # Fallback: check stderr for evidence the test actually ran
        if "stderr" in outputs and outputs["stderr"]:
            stderr_lower = outputs["stderr"].lower()
            if "call_generating" in stderr_lower or "cycles =" in stderr_lower:
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
