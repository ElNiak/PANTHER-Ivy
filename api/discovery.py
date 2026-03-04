"""Discovery API: auto-detect protocol/version from .ivy paths, list available tests."""
import re
from pathlib import Path
from typing import Dict, List, Optional

from ._shared import detect_role

from .types import TestInfo

# Default protocol-testing directory relative to submodule root
_SUBMODULE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_PROTOCOL_TESTING_DIR = _SUBMODULE_ROOT / "protocol-testing"
_DEFAULT_VERSION_CONFIGS_DIR = _SUBMODULE_ROOT / "version_configs"

# Pattern: protocol-testing/{protocol}/{protocol}_tests/[subdirs/]{test_name}.ivy
# Handles both flat and nested structures:
#   protocol-testing/quic/quic_tests/quic_server_test_stream.ivy
#   protocol-testing/quic/quic_tests/server_tests/quic_server_test_stream.ivy
_STANDARD_PATTERN = re.compile(
    r"(?:^|/)protocol-testing/"
    r"(?P<protocol>[a-z_]+)/"
    r"[a-z_]+_tests/"
    r"(?:[a-z_]+/)?"
    r"(?P<test_name>[a-z_0-9]+)\.ivy$"
)
# APT: protocol-testing/apt/apt_protocols/{protocol}/{protocol}_tests/[subdirs/]{test_name}.ivy
_APT_PATTERN = re.compile(
    r"(?:^|/)protocol-testing/apt/apt_protocols/"
    r"(?P<protocol>[a-z_]+)/"
    r"[a-z_]+_tests/"
    r"(?:[a-z_]+/)?"
    r"(?P<test_name>[a-z_0-9]+)\.ivy$"
)


def _find_default_version(
    protocol: str,
    version_configs_dir: Optional[Path] = None,
) -> Optional[str]:
    """Find the default version for a protocol from version_configs/."""
    vdir = version_configs_dir or _DEFAULT_VERSION_CONFIGS_DIR
    protocol_dir = vdir / protocol
    if not protocol_dir.is_dir():
        return None
    yaml_files = sorted(protocol_dir.glob("*.yaml"))
    if not yaml_files:
        return None
    # Prefer rfc* files, otherwise pick first alphabetically
    for f in yaml_files:
        if f.stem.startswith("rfc"):
            return f.stem
    return yaml_files[0].stem


def detect_from_path(
    ivy_file: Path,
    version_configs_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """Auto-detect protocol, test name, role, and version from an .ivy file path.

    Args:
        ivy_file: Path to an .ivy file (absolute or relative).
        version_configs_dir: Override for version_configs directory.

    Returns:
        Dict with keys: protocol, test_name, role, version (optional),
        use_system_models (bool).

    Raises:
        ValueError: If the path doesn't match known patterns.
    """
    path_str = str(ivy_file)

    # Try APT pattern first (more specific)
    match = _APT_PATTERN.search(path_str)
    use_system_models = False
    if match:
        use_system_models = True
    else:
        match = _STANDARD_PATTERN.search(path_str)

    if not match:
        raise ValueError(
            f"Cannot detect protocol from path: {ivy_file}. "
            "Expected: protocol-testing/<protocol>/<protocol>_tests/<test>.ivy"
        )

    protocol = match.group("protocol")
    test_name = match.group("test_name")
    role = detect_role(test_name)
    version = _find_default_version(protocol, version_configs_dir)

    result: Dict[str, object] = {
        "protocol": protocol,
        "test_name": test_name,
        "role": role,
        "use_system_models": use_system_models,
    }
    if version:
        result["version"] = version
    return result


def list_tests(
    protocol: Optional[str] = None,
    version: Optional[str] = None,
    protocol_testing_dir: Optional[Path] = None,
    version_configs_dir: Optional[Path] = None,
) -> List[TestInfo]:
    """List available Ivy test specifications.

    Args:
        protocol: Filter by protocol name (e.g., "quic"). None for all.
        version: Filter by version (e.g., "rfc9000"). None for all.
        protocol_testing_dir: Root of protocol-testing tree.
        version_configs_dir: Root of version_configs tree.

    Returns:
        List of TestInfo objects for matching tests.
    """
    pt_dir = protocol_testing_dir or _DEFAULT_PROTOCOL_TESTING_DIR
    if not pt_dir.is_dir():
        return []

    results: List[TestInfo] = []

    # Determine which protocols to scan
    if protocol:
        protocol_dirs = [pt_dir / protocol]
    else:
        protocol_dirs = [
            d
            for d in pt_dir.iterdir()
            if d.is_dir() and d.name not in ("apt", "__pycache__", ".git")
        ]

    for proto_dir in protocol_dirs:
        if not proto_dir.is_dir():
            continue
        proto_name = proto_dir.name
        proto_version = version or _find_default_version(
            proto_name, version_configs_dir
        )

        # Scan {protocol}_tests/ directory recursively for .ivy files
        tests_dir = proto_dir / f"{proto_name}_tests"
        if not tests_dir.is_dir():
            continue

        for ivy_file in sorted(tests_dir.rglob("*.ivy")):
            test_name = ivy_file.stem
            role = detect_role(test_name)

            results.append(
                TestInfo(
                    name=test_name,
                    protocol=proto_name,
                    version=proto_version or "",
                    role=role,
                    ivy_file=str(ivy_file),
                )
            )

    # Apply version filter if both protocol and version specified
    if version:
        results = [t for t in results if t.version == version]

    return results
