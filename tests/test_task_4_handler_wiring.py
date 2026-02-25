"""Tests for Phase 4: Handler wiring for document_symbols and workspace_symbols."""

import sys
from pathlib import Path

import pytest
from lsprotocol import types as lsp

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestDocumentSymbolsWiring:
    """Verify compute_document_symbols returns real symbols, not empty list."""

    def test_valid_source_returns_symbols(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\n\ntype cid\ntype pkt_num\n"
        result = compute_document_symbols(parser, None, source, "test.ivy")
        assert len(result) > 0
        names = [s.name for s in result]
        assert "cid" in names

    def test_broken_source_returns_fallback_symbols(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\ntype cid\nobject broken = { @@@ }\ntype pkt_num\n"
        result = compute_document_symbols(parser, None, source, "broken.ivy")
        assert len(result) > 0  # Fallback scanner should find 'cid' and/or 'pkt_num'

    def test_empty_source_returns_empty_list(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        result = compute_document_symbols(parser, None, "", "empty.ivy")
        assert result == []

    def test_no_parser_uses_indexer_fallback(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        result = compute_document_symbols(None, indexer, "", str(tmp_path / "a.ivy"))
        assert len(result) > 0

    def test_no_parser_no_indexer_returns_empty(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        result = compute_document_symbols(
            None, None, "#lang ivy1.7\ntype cid\n", "test.ivy"
        )
        assert result == []

    def test_hierarchy_preserved(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = (
            "#lang ivy1.7\n"
            "object bit = {\n"
            "    type this\n"
            "    individual zero:bit\n"
            "}\n"
        )
        result = compute_document_symbols(parser, None, source, "test.ivy")
        bit_sym = next((s for s in result if s.name == "bit"), None)
        assert bit_sym is not None
        assert bit_sym.children is not None
        assert len(bit_sym.children) > 0

    def test_returns_document_symbol_type(self):
        from ivy_lsp.features.document_symbols import compute_document_symbols
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        source = "#lang ivy1.7\ntype cid\n"
        result = compute_document_symbols(parser, None, source, "test.ivy")
        for sym in result:
            assert isinstance(sym, lsp.DocumentSymbol)


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


class TestWorkspaceSymbolsWiring:
    """Verify compute_workspace_symbols returns symbols from the indexer."""

    def test_empty_query_returns_all_symbols(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(
            tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\ntype pkt_num\n"}
        )
        result = compute_workspace_symbols(indexer, "")
        assert len(result) > 0

    def test_filtered_query_returns_matches(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(
            tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\ntype pkt_num\n"}
        )
        result = compute_workspace_symbols(indexer, "cid")
        names = [s.name for s in result]
        assert any("cid" in n for n in names)

    def test_no_indexer_returns_empty(self):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        result = compute_workspace_symbols(None, "cid")
        assert result == []

    def test_returns_workspace_symbol_type(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\n"})
        result = compute_workspace_symbols(indexer, "")
        for sym in result:
            assert isinstance(sym, lsp.WorkspaceSymbol)

    def test_symbols_have_file_uri(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\n"})
        result = compute_workspace_symbols(indexer, "cid")
        assert len(result) > 0
        assert result[0].location.uri.startswith("file://")

    def test_respects_max_results(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import (
            MAX_RESULTS,
            compute_workspace_symbols,
        )

        # Create many types to exceed MAX_RESULTS
        types = "\n".join(f"type t{i}" for i in range(150))
        indexer, _ = _build_indexer(tmp_path, {"a.ivy": f"#lang ivy1.7\n{types}\n"})
        result = compute_workspace_symbols(indexer, "")
        assert len(result) <= MAX_RESULTS
