"""Data types for the panther_ivy public API."""
from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass
class CommandResult:
    """Shell commands with their environment and working directory."""

    commands: List[str]
    environment: Dict[str, str]
    working_dir: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompileResult:
    """Result of generating compilation commands."""

    setup_commands: CommandResult
    compile_commands: CommandResult

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestRunResult:
    """Result of generating full test execution commands."""

    compile: CompileResult
    run_commands: CommandResult

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DiagnosticItem:
    """A single diagnostic (error/warning) from compilation."""

    file: str
    line: int
    column: int
    severity: str  # "error" | "warning" | "info"
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestInfo:
    """Metadata about an available Ivy test specification."""

    name: str
    protocol: str
    version: str
    role: str  # "server" | "client"
    ivy_file: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionResult:
    """Result of executing commands in Docker or on host."""

    exit_code: int
    stdout: str
    stderr: str
    target: str  # "docker" | "host"

    def to_dict(self) -> dict:
        return asdict(self)
