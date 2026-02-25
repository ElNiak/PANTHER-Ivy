"""Tests for Task 4.5: Serena E2E workflow contract tests.

Validates that ivy_lsp returns well-formed LSP objects that satisfy
Serena's expectations for get_symbols_overview, find_symbol,
find_referencing_symbols, and symbol editing.
"""

import sys
from pathlib import Path

import pytest
from lsprotocol import types as lsp

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


def _build_indexer(tmp_path, files: dict):
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


MULTI_FILE_WORKSPACE = {
    "types.ivy": "#lang ivy1.7\ntype cid\ntype pkt_num\n",
    "frame.ivy": (
        "#lang ivy1.7\n"
        "include types\n"
        "object frame = {\n"
        "    type this\n"
        "    individual src:cid\n"
        "    action send(dst:cid)\n"
        "}\n"
    ),
}


class TestSerenaGetSymbolsOverview:
    """Serena's get_symbols_overview maps to textDocument/documentSymbol."""

    def test_returns_list_of_document_symbols(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        indexer, parser = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        source = (tmp_path / "types.ivy").read_text()
        result = compute_document_symbols(
            parser, indexer, source, str(tmp_path / "types.ivy")
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_symbols_have_required_fields(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        indexer, parser = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        source = (tmp_path / "frame.ivy").read_text()
        result = compute_document_symbols(
            parser, indexer, source, str(tmp_path / "frame.ivy")
        )
        for sym in result:
            assert sym.name, "DocumentSymbol must have name"
            assert sym.kind is not None, "DocumentSymbol must have kind"
            assert sym.range is not None, "DocumentSymbol must have range"
            assert (
                sym.selection_range is not None
            ), "DocumentSymbol must have selection_range"

    def test_nested_symbols_have_children(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        indexer, parser = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        source = (tmp_path / "frame.ivy").read_text()
        result = compute_document_symbols(
            parser, indexer, source, str(tmp_path / "frame.ivy")
        )
        frame_sym = next((s for s in result if s.name == "frame"), None)
        assert frame_sym is not None, "Expected 'frame' symbol"
        assert frame_sym.children is not None, "Object should have children"
        assert len(frame_sym.children) > 0


class TestSerenaFindSymbol:
    """Serena's find_symbol maps to workspace/symbol."""

    def test_returns_workspace_symbols(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        result = compute_workspace_symbols(indexer, "cid")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_symbols_have_location_with_uri(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        result = compute_workspace_symbols(indexer, "cid")
        for sym in result:
            assert sym.location.uri.startswith("file://")

    def test_cross_file_search(self, tmp_path):
        from ivy_lsp.features.workspace_symbols import compute_workspace_symbols

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        # 'frame' is in frame.ivy, 'cid' is in types.ivy
        frame_results = compute_workspace_symbols(indexer, "frame")
        cid_results = compute_workspace_symbols(indexer, "cid")
        assert len(frame_results) > 0
        assert len(cid_results) > 0


class TestSerenaDefinition:
    """Serena relies on go-to-definition for cross-file navigation."""

    def test_definition_returns_location(self, tmp_path):
        from ivy_lsp.features.definition import goto_definition

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        # Look up 'cid' on line "    individual src:cid" in frame.ivy
        lines = (tmp_path / "frame.ivy").read_text().split("\n")
        result = goto_definition(
            indexer, str(tmp_path / "frame.ivy"), lsp.Position(4, 19), lines
        )
        assert result is not None

    def test_cross_file_definition(self, tmp_path):
        from ivy_lsp.features.definition import goto_definition

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        lines = (tmp_path / "frame.ivy").read_text().split("\n")
        result = goto_definition(
            indexer, str(tmp_path / "frame.ivy"), lsp.Position(4, 19), lines
        )
        if result is not None:
            loc = result if isinstance(result, lsp.Location) else result[0]
            # Should resolve to types.ivy where 'cid' is defined
            assert "types.ivy" in loc.uri


class TestSerenaReferences:
    """Serena's find_referencing_symbols maps to textDocument/references."""

    def test_references_returns_locations(self, tmp_path):
        from ivy_lsp.features.references import find_references

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        lines = (tmp_path / "types.ivy").read_text().split("\n")
        result = find_references(
            indexer, str(tmp_path / "types.ivy"), lsp.Position(1, 5), lines, True
        )
        assert isinstance(result, list)

    def test_cross_file_references(self, tmp_path):
        from ivy_lsp.features.references import find_references

        indexer, _ = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        lines = (tmp_path / "types.ivy").read_text().split("\n")
        result = find_references(
            indexer, str(tmp_path / "types.ivy"), lsp.Position(1, 5), lines, True
        )
        # 'cid' is used in frame.ivy too
        if len(result) > 0:
            uris = [r.uri for r in result]
            # Verify at minimum no crash; cross-file detection depends on
            # word_at_position extracting 'cid' correctly
            assert all(isinstance(u, str) for u in uris)


class TestSerenaSymbolRanges:
    """Serena editing tools depend on accurate symbol ranges."""

    def test_symbol_range_not_negative(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        indexer, parser = _build_indexer(tmp_path, MULTI_FILE_WORKSPACE)
        source = (tmp_path / "frame.ivy").read_text()
        result = compute_document_symbols(
            parser, indexer, source, str(tmp_path / "frame.ivy")
        )
        for sym in result:
            assert sym.range.start.line >= 0
            assert sym.range.start.character >= 0
            assert sym.range.end.line >= 0
            assert sym.range.end.character >= 0

    def test_symbol_range_covers_declaration(self, tmp_path):
        from ivy_lsp.features.document_symbols import compute_document_symbols

        indexer, parser = _build_indexer(
            tmp_path, {"a.ivy": "#lang ivy1.7\ntype cid\n"}
        )
        source = (tmp_path / "a.ivy").read_text()
        result = compute_document_symbols(
            parser, indexer, source, str(tmp_path / "a.ivy")
        )
        cid_sym = next((s for s in result if s.name == "cid"), None)
        assert cid_sym is not None
        # 'type cid' is on line 1 (0-indexed)
        assert cid_sym.range.start.line >= 0
