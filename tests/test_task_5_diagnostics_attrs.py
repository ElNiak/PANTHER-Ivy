"""Tests for Phase 5: Diagnostic attribute completeness.

Validates that all diagnostics have correct ranges, severity levels,
source fields, and message content.
"""
import sys
from pathlib import Path

from lsprotocol.types import DiagnosticSeverity

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestDiagnosticRanges:
    """Every diagnostic must have valid, non-negative ranges."""

    def test_structural_diags_have_valid_ranges(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("type cid\n", "a.ivy")  # missing header
        for d in diags:
            assert d.range.start.line >= 0
            assert d.range.start.character >= 0
            assert d.range.end.line >= d.range.start.line
            assert d.range.end.character >= 0

    def test_parse_error_diags_have_valid_ranges(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser, "#lang ivy1.7\nobject x = { @@@ }\n", "bad.ivy"
        )
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        for d in errors:
            assert d.range.start.line >= 0
            assert d.range.end.line >= d.range.start.line

    def test_brace_error_range_points_to_correct_line(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        source = "#lang ivy1.7\nline1\n}\nline3\n"
        diags = check_structural_issues(source, "a.ivy")
        brace = [d for d in diags if "brace" in d.message.lower()]
        assert len(brace) > 0
        assert brace[0].range.start.line == 2  # 0-indexed, '}' is line 2


class TestDiagnosticSeverity:
    """Verify correct severity assignment."""

    def test_missing_header_is_warning(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("type cid\n", "a.ivy")
        header_diags = [
            d
            for d in diags
            if "header" in d.message.lower() or "lang" in d.message.lower()
        ]
        assert all(d.severity == DiagnosticSeverity.Warning for d in header_diags)

    def test_unmatched_brace_is_error(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("#lang ivy1.7\nobject x = {\n", "a.ivy")
        brace_diags = [d for d in diags if "brace" in d.message.lower()]
        assert all(d.severity == DiagnosticSeverity.Error for d in brace_diags)

    def test_unresolved_include_is_warning(self, tmp_path):
        from ivy_lsp.features.diagnostics import check_structural_issues
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ninclude nonexistent\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        diags = check_structural_issues(
            "#lang ivy1.7\ninclude nonexistent\n",
            str(tmp_path / "a.ivy"),
            indexer=indexer,
        )
        inc_diags = [d for d in diags if "include" in d.message.lower()]
        assert all(d.severity == DiagnosticSeverity.Warning for d in inc_diags)

    def test_parse_error_is_error_severity(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser, "#lang ivy1.7\nobject x = { @@@ }\n", "bad.ivy"
        )
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) > 0


class TestDiagnosticSourceField:
    """All diagnostics must have a source field."""

    def test_structural_diags_have_source(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("type cid\n", "a.ivy")
        for d in diags:
            assert d.source is not None
            assert d.source in ("ivy", "ivy-lsp")

    def test_parse_error_diags_have_source(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser, "#lang ivy1.7\nobject x = { @@@ }\n", "bad.ivy"
        )
        for d in diags:
            assert d.source is not None


class TestDiagnosticEdgeCases:
    """Edge cases that could cause crashes."""

    def test_empty_file(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(parser, "", "empty.ivy")
        assert isinstance(diags, list)

    def test_only_whitespace(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(parser, "   \n\n  \n", "whitespace.ivy")
        assert isinstance(diags, list)

    def test_very_long_line(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        source = "#lang ivy1.7\n" + "x" * 10000 + "\n"
        diags = check_structural_issues(source, "long.ivy")
        assert isinstance(diags, list)

    def test_unicode_content(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser,
            "#lang ivy1.7\n# comment with unicode chars\ntype cid\n",
            "unicode.ivy",
        )
        assert isinstance(diags, list)


class TestIncrementalReindexing:
    """Verify that saving a file triggers re-indexing."""

    def test_reindex_file_updates_symbols(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        # Verify initial state
        results = indexer.lookup_symbol("cid")
        assert len(results) > 0

        # Simulate file change: add new type
        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\ntype pkt_num\n")
        indexer.reindex_file(str(tmp_path / "a.ivy"))

        # New symbol should be found
        results = indexer.lookup_symbol("pkt_num")
        assert len(results) > 0
