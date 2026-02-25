"""Tests for Task 3.4: Phase 3 Integration."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import DiagnosticSeverity, Position

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


def _build_indexer(tmp_path, files: dict):
    """Helper: create .ivy files and build an indexer."""
    from ivy_lsp.indexer.include_resolver import IncludeResolver
    from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
    from ivy_lsp.parsing.parser_session import IvyParserWrapper

    for name, content in files.items():
        (tmp_path / name).write_text(content)
    parser = IvyParserWrapper()
    resolver = IncludeResolver(str(tmp_path))
    indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
    indexer.index_workspace()
    return indexer, parser


class TestPhase3Pipeline:
    def test_completion_general(self, tmp_path):
        from ivy_lsp.features.completion import get_completions

        indexer, _ = _build_indexer(
            tmp_path,
            {"a.ivy": "#lang ivy1.7\ntype cid\ntype pkt_num\n"},
        )
        lines = ["#lang ivy1.7", "type cid", "type pkt_num", ""]
        items = get_completions(indexer, str(tmp_path / "a.ivy"), Position(3, 0), lines)
        labels = [i.label for i in items]
        assert "cid" in labels
        assert "pkt_num" in labels
        assert "action" in labels  # keyword

    def test_completion_dot_access(self, tmp_path):
        from ivy_lsp.features.completion import get_completions

        indexer, _ = _build_indexer(
            tmp_path,
            {
                "a.ivy": (
                    "#lang ivy1.7\n"
                    "object bit = {\n"
                    "    type this\n"
                    "    individual zero:bit\n"
                    "}\n"
                )
            },
        )
        lines = [
            "#lang ivy1.7",
            "object bit = {",
            "    type this",
            "    individual zero:bit",
            "}",
            "bit.",
        ]
        items = get_completions(indexer, str(tmp_path / "a.ivy"), Position(5, 4), lines)
        labels = [i.label for i in items]
        assert len(labels) > 0

    def test_completion_include(self, tmp_path):
        from ivy_lsp.features.completion import get_completions

        indexer, _ = _build_indexer(
            tmp_path,
            {
                "types.ivy": "#lang ivy1.7\ntype t\n",
                "main.ivy": "#lang ivy1.7\ninclude \n",
            },
        )
        lines = ["#lang ivy1.7", "include "]
        items = get_completions(
            indexer, str(tmp_path / "main.ivy"), Position(1, 8), lines
        )
        labels = [i.label for i in items]
        assert "types" in labels

    def test_hover_on_type(self, tmp_path):
        from ivy_lsp.features.hover import get_hover_info

        indexer, _ = _build_indexer(tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\n"})
        lines = ["#lang ivy1.7", "type cid"]
        result = get_hover_info(indexer, str(tmp_path / "a.ivy"), Position(1, 5), lines)
        assert result is not None
        assert "cid" in result.contents.value

    def test_hover_on_action(self, tmp_path):
        from ivy_lsp.features.hover import get_hover_info

        indexer, _ = _build_indexer(
            tmp_path,
            {"a.ivy": "#lang ivy1.7\ntype t\naction foo(x:t) = {\n}\n"},
        )
        lines = ["#lang ivy1.7", "type t", "action foo(x:t) = {", "}"]
        result = get_hover_info(indexer, str(tmp_path / "a.ivy"), Position(2, 8), lines)
        assert result is not None
        assert "foo" in result.contents.value

    def test_diagnostics_valid_file(self, tmp_path):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser, "#lang ivy1.7\ntype cid\n", str(tmp_path / "a.ivy")
        )
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) == 0

    def test_diagnostics_broken_file(self):
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        diags = compute_diagnostics(
            parser, "#lang ivy1.7\nobject x = { @@@ }\n", "bad.ivy"
        )
        errors = [d for d in diags if d.severity == DiagnosticSeverity.Error]
        assert len(errors) > 0


class TestServerRegistration:
    def test_server_instantiation_with_phase3(self):
        from ivy_lsp.server import IvyLanguageServer

        server = IvyLanguageServer()
        assert server is not None


class TestFeatureInteraction:
    def test_diagnostics_then_completion(self, tmp_path):
        """File with errors still provides completions."""
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.features.diagnostics import compute_diagnostics
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        source = "#lang ivy1.7\ntype cid\nobject broken = { @@@ }\n"
        (tmp_path / "a.ivy").write_text(source)

        indexer, parser = _build_indexer(tmp_path, {"a.ivy": source})

        # Diagnostics should find errors
        diags = compute_diagnostics(parser, source, str(tmp_path / "a.ivy"))
        assert len(diags) > 0

        # Completion should still work
        lines = source.split("\n") + [""]
        items = get_completions(
            indexer, str(tmp_path / "a.ivy"), Position(len(lines) - 1, 0), lines
        )
        # Should have at least keywords
        assert len(items) > 0
