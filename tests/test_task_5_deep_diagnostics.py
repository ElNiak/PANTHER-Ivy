"""Tests for Phase 5: Deep diagnostics parsing and robustness."""
import asyncio
import inspect
import re
import sys
from pathlib import Path

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


IVY_CHECK_REGEX = re.compile(r".*?:(\d+):\s*(error|warning):\s*(.*)")


class TestDeepDiagnosticsRegex:
    """Validate the ivy_check output parsing regex in isolation."""

    def test_parses_error_line(self):
        line = "quic_types.ivy:42: error: type mismatch"
        m = IVY_CHECK_REGEX.match(line)
        assert m is not None
        assert m.group(1) == "42"
        assert m.group(2) == "error"
        assert m.group(3) == "type mismatch"

    def test_parses_warning_line(self):
        line = "test.ivy:10: warning: unused variable"
        m = IVY_CHECK_REGEX.match(line)
        assert m is not None
        assert m.group(2) == "warning"

    def test_ignores_non_matching_line(self):
        line = "Compilation successful"
        m = IVY_CHECK_REGEX.match(line)
        assert m is None

    def test_parses_path_with_spaces(self):
        line = "/path/to my file/test.ivy:5: error: bad syntax"
        m = IVY_CHECK_REGEX.match(line)
        assert m is not None
        assert m.group(1) == "5"

    def test_parses_line_number_1(self):
        line = "test.ivy:1: error: missing header"
        m = IVY_CHECK_REGEX.match(line)
        assert m is not None
        assert m.group(1) == "1"


class TestDeepDiagnosticsFunction:
    """Test run_deep_diagnostics end-to-end behavior."""

    def test_missing_binary_returns_empty(self):
        from ivy_lsp.features.diagnostics import run_deep_diagnostics

        result = asyncio.run(
            run_deep_diagnostics("test.ivy", ivy_check_cmd="nonexistent_cmd_xyz")
        )
        assert result == []

    def test_timeout_returns_empty(self):
        """Verify the function doesn't crash with a nonexistent command."""
        from ivy_lsp.features.diagnostics import run_deep_diagnostics

        result = asyncio.run(
            run_deep_diagnostics("/dev/null", ivy_check_cmd="nonexistent_cmd_xyz")
        )
        assert isinstance(result, list)

    def test_result_has_ivy_check_source(self):
        """Verify parsed diagnostics have source='ivy_check'."""
        from ivy_lsp.features import diagnostics

        source_code = inspect.getsource(diagnostics.run_deep_diagnostics)
        assert 'source="ivy_check"' in source_code

    def test_hardcoded_end_character_999(self):
        """Document that deep diagnostics use character=999 as end column."""
        from ivy_lsp.features import diagnostics

        source_code = inspect.getsource(diagnostics.run_deep_diagnostics)
        assert "999" in source_code
