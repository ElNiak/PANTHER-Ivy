"""Runner API: generate test execution commands and parse results."""
from pathlib import Path
from typing import Dict, Optional

from panther_ivy._shared import (
    VERDICT_IUT_CRASH,
    VERDICT_NON_COMPLIANT,
    VERDICT_NO_VIOLATION_FOUND,
    VERDICT_TESTER_CRASH,
    determine_verdict,
)

from .compiler import generate_compile_commands
from .discovery import detect_from_path
from .types import CommandResult, TestRunResult


def generate_test_commands(
    ivy_file: Path,
    protocol: Optional[str] = None,
    version: Optional[str] = None,
    seed: Optional[int] = None,
    iterations: int = 1,
    target_addr: Optional[str] = None,
    build_mode: str = "",
    test_iters: int = 300,
    *,
    base_path: str,
) -> TestRunResult:
    """Generate full test execution commands (compile + run).

    Args:
        ivy_file: Path to the .ivy source file.
        protocol: Protocol name. Auto-detected if None.
        version: Protocol version. Auto-detected if None.
        seed: Random seed for test execution.
        iterations: Number of test repetitions.
        target_addr: Target service address (IP).
        build_mode: Z3 build mode.
        test_iters: Internal Ivy iterations per compilation.
        base_path: Base protocol-testing path. Required (no default).

    Returns:
        TestRunResult with compile and run phases.

    Raises:
        ValueError: If base_path is None.
    """
    if base_path is None:
        raise ValueError("base_path is required and cannot be None")

    # Generate compile commands
    compile_result = generate_compile_commands(
        ivy_file=ivy_file,
        protocol=protocol,
        version=version,
        build_mode=build_mode,
        test_iters=test_iters,
        base_path=base_path,
    )

    # Auto-detect protocol if needed
    if protocol is None:
        detected = detect_from_path(ivy_file)
        protocol = detected["protocol"]

    test_name = Path(ivy_file).stem

    protocol_dir = f"{base_path}/{protocol}"

    build_dir = f"{protocol_dir}/build"

    # Construct test binary invocation
    run_args = [f"./{test_name}"]
    if seed is not None:
        run_args.append(f"seed={seed}")
    if target_addr:
        run_args.append(f"server_addr={target_addr}")
    if iterations > 1:
        run_args.append(f"iters={iterations}")

    run_cmd = " ".join(run_args)

    run_commands = CommandResult(
        commands=[run_cmd],
        environment=compile_result.compile_commands.environment.copy(),
        working_dir=build_dir,
    )

    return TestRunResult(compile=compile_result, run_commands=run_commands)


def parse_test_output(stdout: str, stderr: str = "") -> Dict:
    """Parse Ivy test binary output into structured results.

    Delegates to _shared.determine_verdict() for the core logic, then maps
    internal verdict names to API-level names:
    - TESTER_CRASH / IUT_CRASH -> "CRASH"
    - UNKNOWN -> "INCONCLUSIVE"

    Args:
        stdout: Standard output from the test binary.
        stderr: Standard error from the test binary.

    Returns:
        Dict with keys: passed (bool), verdict (str), details (str).
    """
    result = determine_verdict(stdout, stderr)
    internal_verdict = result["verdict"]

    # Map internal verdicts to API-level names
    if internal_verdict in (VERDICT_TESTER_CRASH, VERDICT_IUT_CRASH):
        verdict = "CRASH"
        passed = False
        details = "Test binary crashed"
    elif internal_verdict == VERDICT_NON_COMPLIANT:
        verdict = "NON_COMPLIANT"
        passed = False
        details = "Assumption violation detected"
    elif internal_verdict == VERDICT_NO_VIOLATION_FOUND:
        verdict = "NO_VIOLATION_FOUND"
        passed = True
        details = "Test completed successfully"
    else:
        verdict = "INCONCLUSIVE"
        passed = False
        details = "No test execution evidence found"

    return {
        "passed": passed,
        "verdict": verdict,
        "details": details,
    }
