"""Tests for Task 3.2: Diagnostics Feature."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import DiagnosticSeverity

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestDiagnosticsImport:
    def test_import(self):
        from ivy_lsp.features.diagnostics import (
            check_structural_issues,
            compute_diagnostics,
        )

        assert compute_diagnostics is not None
        assert check_structural_issues is not None


class TestParseDiagnostics:
    def test_valid_file_no_diagnostics(self, tmp_path):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\n\ntype cid\n"
        diags = compute_diagnostics(parser, source, str(tmp_path / "a.ivy"))
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) == 0

    def test_syntax_error_produces_diagnostic(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\n\ntype cid\nobject broken = {\n    this is not valid !!!\n}\n"
        diags = compute_diagnostics(parser, source, "broken.ivy")
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) > 0

    def test_diagnostic_has_message(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\nobject x = { @@@ }\n"
        diags = compute_diagnostics(parser, source, "bad.ivy")
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        if errors:
            assert errors[0].message  # non-empty message


class TestStructuralDiagnostics:
    def test_missing_lang_header(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("type cid\n", "a.ivy")
        assert any(
            "lang" in d.message.lower() or "header" in d.message.lower() for d in diags
        )

    def test_valid_header_no_warning(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("#lang ivy1.7\ntype cid\n", "a.ivy")
        lang_warnings = [
            d
            for d in diags
            if "lang" in d.message.lower() or "header" in d.message.lower()
        ]
        assert len(lang_warnings) == 0

    def test_unmatched_open_brace(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("#lang ivy1.7\nobject x = {\ntype t\n", "a.ivy")
        brace_diags = [d for d in diags if "brace" in d.message.lower()]
        assert len(brace_diags) > 0

    def test_unmatched_close_brace(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues("#lang ivy1.7\n}\n", "a.ivy")
        brace_diags = [d for d in diags if "brace" in d.message.lower()]
        assert len(brace_diags) > 0

    def test_balanced_braces_no_diagnostic(self):
        from ivy_lsp.features.diagnostics import check_structural_issues

        diags = check_structural_issues(
            "#lang ivy1.7\nobject x = {\ntype t\n}\n", "a.ivy"
        )
        brace_diags = [d for d in diags if "brace" in d.message.lower()]
        assert len(brace_diags) == 0

    def test_unresolved_include(self, tmp_path):
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
        include_diags = [d for d in diags if "include" in d.message.lower()]
        assert len(include_diags) > 0

    def test_resolved_include_no_diagnostic(self, tmp_path):
        from ivy_lsp.features.diagnostics import check_structural_issues
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype t\n")
        (tmp_path / "main.ivy").write_text("#lang ivy1.7\ninclude types\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        diags = check_structural_issues(
            "#lang ivy1.7\ninclude types\n",
            str(tmp_path / "main.ivy"),
            indexer=indexer,
        )
        include_diags = [d for d in diags if "unresolved" in d.message.lower()]
        assert len(include_diags) == 0


class TestComputeDiagnostics:
    def test_full_pipeline_valid(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(parser, "#lang ivy1.7\ntype cid\n", "a.ivy")
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) == 0

    def test_no_parser_graceful(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics

        diags = compute_diagnostics(None, "#lang ivy1.7\ntype cid\n", "a.ivy")
        # Should not crash; structural-only diagnostics
        assert isinstance(diags, list)


class TestDeepDiagnostics:
    @pytest.mark.asyncio
    async def test_missing_ivyc_handled(self):
        from ivy_lsp.features.diagnostics import run_deep_diagnostics

        result = await run_deep_diagnostics(
            "nonexistent.ivy", ivy_check_cmd="nonexistent_binary_12345"
        )
        assert result == []
