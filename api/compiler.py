"""Compiler API: generate ivyc compilation commands and parse output."""
import re
from pathlib import Path
from typing import List, Optional

from .discovery import detect_from_path
from .types import CommandResult, CompileResult, DiagnosticItem

# ivyc error patterns (from ivy_analysis_mixin.py:504-526)
# Patterns: "error: file.ivy: line N: message" or "file.ivy: line N: error: message"
_ERROR_PATTERN = re.compile(
    r"(?:error:\s*)?(?P<file>[^\s:]+\.ivy):\s*line\s+(?P<line>\d+):\s*"
    r"(?:error:\s*)?(?P<message>.+)"
)
_WARNING_PATTERN = re.compile(
    r"(?:warning:\s*)?(?P<file>[^\s:]+\.ivy):\s*line\s+(?P<line>\d+):\s*"
    r"(?:warning:\s*)?(?P<message>.+)"
)
_SEVERITY_PREFIX = re.compile(r"^(error|warning):\s*")


def generate_compile_commands(
    ivy_file: Path,
    protocol: Optional[str] = None,
    version: Optional[str] = None,
    build_mode: str = "",
    test_iters: int = 300,
    *,
    base_path: str,
) -> CompileResult:
    """Generate ivyc compilation commands for an .ivy file.

    Args:
        ivy_file: Path to the .ivy source file.
        protocol: Protocol name. Auto-detected from path if None.
        version: Protocol version. Auto-detected if None.
        build_mode: Z3 build mode ("", "debug-asan", "rel-lto", "release-static-pgo").
        test_iters: Internal Ivy test iterations (default 300).
        base_path: Base protocol-testing path. Required (no default).

    Returns:
        CompileResult with setup and compilation commands.

    Raises:
        ValueError: If protocol cannot be determined or base_path is None.
    """
    if base_path is None:
        raise ValueError("base_path is required and cannot be None")

    # Auto-detect if needed
    if protocol is None:
        detected = detect_from_path(ivy_file)
        protocol = detected["protocol"]
        if version is None and "version" in detected:
            version = detected["version"]

    test_name = Path(ivy_file).stem

    protocol_dir = f"{base_path}/{protocol}"

    build_dir = f"{protocol_dir}/build"
    tests_subdir = f"{protocol_dir}/{protocol}_tests"

    # Setup commands: ensure build directory exists
    setup = CommandResult(
        commands=[f"mkdir -p {build_dir}"],
        environment={},
        working_dir=protocol_dir,
    )

    # Build environment
    env = {}
    if build_mode:
        env["BUILD_MODE"] = build_mode
        env["Z3_BUILD_MODE"] = build_mode

    # Compile command: mirrors _build_test_compilation_commands()
    # from ivy_command_mixin.py:542-601
    ivyc_cmd = (
        f"ivyc show_compiled=false trace=false target=test "
        f"test_iters={test_iters} {test_name}.ivy"
    )

    compile_cmds = CommandResult(
        commands=[ivyc_cmd],
        environment=env,
        working_dir=tests_subdir,
    )

    return CompileResult(setup_commands=setup, compile_commands=compile_cmds)


def parse_compile_output(stdout: str, stderr: str) -> List[DiagnosticItem]:
    """Parse ivyc compilation output into structured diagnostics.

    Args:
        stdout: Standard output from ivyc.
        stderr: Standard error from ivyc.

    Returns:
        List of DiagnosticItem objects.
    """
    diagnostics: List[DiagnosticItem] = []
    combined = stderr + "\n" + stdout

    for line in combined.splitlines():
        line = line.strip()
        if not line:
            continue

        # Determine severity from prefix
        severity = "error"
        if line.startswith("warning:") or ": warning:" in line:
            severity = "warning"

        # Try error/warning pattern
        if severity == "error":
            match = _ERROR_PATTERN.search(line)
        else:
            match = _WARNING_PATTERN.search(line)
        if not match:
            # Try generic pattern
            match = _ERROR_PATTERN.search(line) or _WARNING_PATTERN.search(line)

        if match:
            message = match.group("message").strip()
            # Clean up severity prefix from message if duplicated
            message = _SEVERITY_PREFIX.sub("", message)

            diagnostics.append(
                DiagnosticItem(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=0,
                    severity=severity,
                    message=message,
                )
            )

    return diagnostics
