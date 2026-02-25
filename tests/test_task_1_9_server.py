"""Tests for Task 1.9: Server Handler Integration Tests.

Tests that exercise the feature-handler layer (document_symbols,
workspace_symbols) as they would be invoked by the LSP server,
ensuring the full pipeline from parse to LSP response objects works.
"""

from pathlib import Path

import pytest
from lsprotocol import types as lsp

from ivy_lsp.features.document_symbols import (
    get_document_symbols,
    ivy_symbol_to_document_symbol,
)
from ivy_lsp.features.workspace_symbols import (
    FlatSymbol,
    flatten_symbols,
    search_symbols,
    to_workspace_symbol,
)
from ivy_lsp.parsing.ast_to_symbols import ast_to_symbols
from ivy_lsp.parsing.parser_session import IvyParserWrapper
from ivy_lsp.parsing.symbols import IvySymbol


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_to_symbols(source: str, filename: str = "test.ivy"):
    """Parse source and return IvySymbol list (asserts parse success)."""
    wrapper = IvyParserWrapper()
    result = wrapper.parse(source, filename)
    assert result.success, f"Parse failed: {result.errors}"
    return ast_to_symbols(result.ast, filename, source)


# ---------------------------------------------------------------------------
# DocumentSymbol handler integration
# ---------------------------------------------------------------------------


class TestDocumentSymbolHandler:
    """Test parse -> symbols -> get_document_symbols pipeline."""

    def test_document_symbols_returns_correct_types(self):
        """Parse a multi-decl source, verify DocumentSymbol list structure."""
        source = """\
#lang ivy1.7

type cid
type pkt_num
alias aid = cid

object bit = {
    type this
    individual zero:bit
}
"""
        symbols = _parse_to_symbols(source)
        doc_syms = get_document_symbols(symbols)
        assert isinstance(doc_syms, list)
        assert len(doc_syms) > 0, "Expected non-empty DocumentSymbol list"
        for ds in doc_syms:
            assert isinstance(ds, lsp.DocumentSymbol)
            assert ds.name, "DocumentSymbol must have a non-empty name"
            assert isinstance(ds.kind, lsp.SymbolKind)
            assert isinstance(ds.range, lsp.Range)
            assert isinstance(ds.selection_range, lsp.Range)

    def test_document_symbol_children_are_recursive(self):
        """Object with children should produce DocumentSymbol with children."""
        source = """\
#lang ivy1.7

object bit = {
    type this
    individual zero:bit
    individual one:bit
}
"""
        symbols = _parse_to_symbols(source)
        doc_syms = get_document_symbols(symbols)
        # Find the 'bit' symbol
        bit_ds = None
        for ds in doc_syms:
            if ds.name == "bit":
                bit_ds = ds
                break
        assert bit_ds is not None, "Expected DocumentSymbol 'bit'"
        assert bit_ds.children is not None, (
            "DocumentSymbol 'bit' should have children"
        )
        child_names = [c.name for c in bit_ds.children]
        assert "zero" in child_names, (
            f"Expected 'zero' in children, got {child_names}"
        )

    def test_document_symbol_kinds_match_ivy_symbols(self):
        """DocumentSymbol kinds should match the underlying IvySymbol kinds."""
        source = """\
#lang ivy1.7

type cid
alias aid = cid

action send(x:cid) returns (y:cid) = {
    y := x
}
"""
        symbols = _parse_to_symbols(source)
        doc_syms = get_document_symbols(symbols)
        # Build a name-to-kind map from IvySymbols
        ivy_kinds = {s.name: s.kind for s in symbols}
        # Verify DocumentSymbols preserve the kinds
        for ds in doc_syms:
            if ds.name in ivy_kinds:
                assert ds.kind == ivy_kinds[ds.name], (
                    f"Kind mismatch for '{ds.name}': "
                    f"IvySymbol={ivy_kinds[ds.name]}, "
                    f"DocumentSymbol={ds.kind}"
                )

    def test_empty_symbols_returns_empty_list(self):
        """get_document_symbols(None) and get_document_symbols([]) -> []."""
        assert get_document_symbols(None) == []
        assert get_document_symbols([]) == []


# ---------------------------------------------------------------------------
# WorkspaceSymbol handler integration
# ---------------------------------------------------------------------------


class TestWorkspaceSymbolHandler:
    """Test parse -> symbols -> flatten -> search pipeline."""

    def test_search_finds_matching_symbols(self):
        """search_symbols('cid') should find 'cid' and 'aid' (contains 'cid')."""
        source = """\
#lang ivy1.7

type cid
alias aid = cid
type pkt_num
"""
        symbols = _parse_to_symbols(source)
        flat = flatten_symbols(symbols)
        results = search_symbols(flat, "cid")
        found_names = [r.qualified_name for r in results]
        assert "cid" in found_names, (
            f"Expected 'cid' in search results, got: {found_names}"
        )

    def test_empty_query_returns_all(self):
        """Workspace search with empty query returns all symbols."""
        source = """\
#lang ivy1.7

type cid
type pkt_num
alias aid = cid
"""
        symbols = _parse_to_symbols(source)
        flat = flatten_symbols(symbols)
        results = search_symbols(flat, "")
        assert len(results) == len(flat), (
            f"Empty query should return all {len(flat)} symbols, "
            f"got {len(results)}"
        )

    def test_workspace_symbol_conversion(self):
        """FlatSymbol -> WorkspaceSymbol has correct structure."""
        source = "#lang ivy1.7\n\ntype cid\n"
        # Use absolute path because to_workspace_symbol calls Path.as_uri()
        # which requires an absolute path.
        symbols = _parse_to_symbols(source, filename="/tmp/test.ivy")
        flat = flatten_symbols(symbols)
        assert len(flat) > 0
        ws_sym = to_workspace_symbol(flat[0])
        assert isinstance(ws_sym, lsp.WorkspaceSymbol)
        assert ws_sym.name == flat[0].qualified_name
        assert isinstance(ws_sym.kind, lsp.SymbolKind)
        assert isinstance(ws_sym.location, lsp.Location)

    def test_nested_symbols_produce_qualified_names(self):
        """Flattened nested symbols should have dot-separated qualified names."""
        source = """\
#lang ivy1.7

object frame = {
    object ack = {
        type this
    }
    type this
}
"""
        symbols = _parse_to_symbols(source)
        flat = flatten_symbols(symbols)
        qnames = [f.qualified_name for f in flat]
        # Should have 'frame' and 'frame.ack' at minimum
        assert "frame" in qnames, f"Expected 'frame' in {qnames}"
        assert any("frame.ack" in qn for qn in qnames), (
            f"Expected 'frame.ack' in qualified names, got: {qnames}"
        )


# ---------------------------------------------------------------------------
# Full pipeline with real quic_types.ivy
# ---------------------------------------------------------------------------


class TestQuicTypesServerPipeline:
    """Full pipeline: parse quic_types.ivy -> symbols -> LSP responses."""

    def test_document_symbols_from_real_file(
        self, quic_types_source, quic_types_path
    ):
        """Parse quic_types.ivy -> DocumentSymbol list, verify non-empty."""
        symbols = _parse_to_symbols(
            quic_types_source, str(quic_types_path)
        )
        doc_syms = get_document_symbols(symbols)
        assert len(doc_syms) > 0, (
            "Expected non-empty DocumentSymbol list from quic_types.ivy"
        )
        # Verify all have names
        for ds in doc_syms:
            assert ds.name, f"DocumentSymbol has empty name: {ds}"

    def test_workspace_search_from_real_file(
        self, quic_types_source, quic_types_path
    ):
        """Parse quic_types.ivy -> flatten -> search produces results."""
        symbols = _parse_to_symbols(
            quic_types_source, str(quic_types_path)
        )
        flat = flatten_symbols(symbols)
        assert len(flat) > 0, "Expected non-empty flat symbol list"

        # Search for 'bit' should find at least the 'bit' object
        results = search_symbols(flat, "bit")
        found_names = [r.qualified_name for r in results]
        assert any("bit" in n for n in found_names), (
            f"search('bit') should find 'bit', got: {found_names}"
        )
