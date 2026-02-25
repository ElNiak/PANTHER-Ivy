"""Tests for Task 1.7: Workspace Symbols Feature (TDD).

Verifies that workspace symbol search flattens hierarchical ``IvySymbol``
trees into qualified-name ``FlatSymbol`` lists, supports case-insensitive
substring matching, respects result limits, and converts to LSP
``WorkspaceSymbol`` with correct URIs and ranges.
"""

import pytest
from lsprotocol import types as lsp

from ivy_lsp.parsing.symbols import IvySymbol
from ivy_lsp.features.workspace_symbols import (
    FlatSymbol,
    flatten_symbols,
    search_symbols,
    to_workspace_symbol,
    MAX_RESULTS,
)


class TestFlatSymbolDataclass:
    """Verify the FlatSymbol dataclass fields."""

    def test_fields(self):
        """FlatSymbol stores qualified_name, kind, file_path, range."""
        fs = FlatSymbol(
            qualified_name="frame.ack",
            kind=lsp.SymbolKind.Module,
            file_path="/tmp/test.ivy",
            range=(0, 0, 0, 10),
        )
        assert fs.qualified_name == "frame.ack"
        assert fs.kind == lsp.SymbolKind.Module
        assert fs.file_path == "/tmp/test.ivy"
        assert fs.range == (0, 0, 0, 10)


class TestFlattenSymbols:
    """Verify recursive flattening of IvySymbol trees."""

    def test_single_symbol(self):
        """A single symbol without children produces one FlatSymbol."""
        sym = IvySymbol(
            name="cid",
            kind=lsp.SymbolKind.Class,
            range=(0, 0, 0, 8),
            file_path="/tmp/test.ivy",
        )
        result = flatten_symbols([sym])
        assert len(result) == 1
        assert result[0].qualified_name == "cid"
        assert result[0].kind == lsp.SymbolKind.Class
        assert result[0].file_path == "/tmp/test.ivy"
        assert result[0].range == (0, 0, 0, 8)

    def test_nested_symbols(self):
        """Nested symbols produce qualified dotted names."""
        inner_child = IvySymbol(
            name="this",
            kind=lsp.SymbolKind.Class,
            range=(3, 4, 3, 20),
            file_path="/tmp/test.ivy",
        )
        child = IvySymbol(
            name="ack",
            kind=lsp.SymbolKind.Module,
            range=(2, 4, 4, 1),
            children=[inner_child],
            file_path="/tmp/test.ivy",
        )
        parent = IvySymbol(
            name="frame",
            kind=lsp.SymbolKind.Module,
            range=(1, 0, 5, 1),
            children=[child],
            file_path="/tmp/test.ivy",
        )
        result = flatten_symbols([parent])
        assert len(result) == 3
        assert result[0].qualified_name == "frame"
        assert result[1].qualified_name == "frame.ack"
        assert result[2].qualified_name == "frame.ack.this"

    def test_empty_list(self):
        """Empty input produces empty output."""
        result = flatten_symbols([])
        assert result == []

    def test_with_prefix(self):
        """A prefix is prepended to all qualified names."""
        sym = IvySymbol(
            name="cid",
            kind=lsp.SymbolKind.Class,
            range=(0, 0, 0, 8),
            file_path="/tmp/test.ivy",
        )
        result = flatten_symbols([sym], prefix="parent")
        assert len(result) == 1
        assert result[0].qualified_name == "parent.cid"


class TestSearchSymbols:
    """Verify case-insensitive substring matching and result limits."""

    def _make_flat(self, name: str) -> FlatSymbol:
        """Helper to create a FlatSymbol with a given name."""
        return FlatSymbol(
            qualified_name=name,
            kind=lsp.SymbolKind.Variable,
            file_path="/tmp/test.ivy",
            range=(0, 0, 0, 0),
        )

    def test_case_insensitive_match(self):
        """Query 'CID' matches qualified_name 'cid' (case-insensitive)."""
        flat = [self._make_flat("cid"), self._make_flat("pkt_num")]
        result = search_symbols(flat, "CID")
        assert len(result) == 1
        assert result[0].qualified_name == "cid"

    def test_empty_query_returns_all(self):
        """An empty query string returns all symbols (up to MAX_RESULTS)."""
        flat = [self._make_flat("a"), self._make_flat("b"), self._make_flat("c")]
        result = search_symbols(flat, "")
        assert len(result) == 3

    def test_no_match_returns_empty(self):
        """A query that matches nothing returns an empty list."""
        flat = [self._make_flat("cid"), self._make_flat("pkt_num")]
        result = search_symbols(flat, "zzz_no_match")
        assert result == []

    def test_result_limit(self):
        """Results are capped at MAX_RESULTS when more symbols match."""
        flat = [self._make_flat(f"sym_{i}") for i in range(150)]
        result = search_symbols(flat, "sym")
        assert len(result) == MAX_RESULTS

    def test_substring_match(self):
        """Substring matching works: 'ack' matches 'frame.ack.range'."""
        flat = [
            self._make_flat("frame.ack.range"),
            self._make_flat("frame.seq"),
        ]
        result = search_symbols(flat, "ack")
        assert len(result) == 1
        assert result[0].qualified_name == "frame.ack.range"


class TestToWorkspaceSymbol:
    """Verify conversion from FlatSymbol to LSP WorkspaceSymbol."""

    def test_basic_conversion(self):
        """FlatSymbol converts to WorkspaceSymbol with file:// URI."""
        fs = FlatSymbol(
            qualified_name="frame.ack",
            kind=lsp.SymbolKind.Module,
            file_path="/tmp/test.ivy",
            range=(1, 0, 5, 1),
        )
        ws = to_workspace_symbol(fs)
        assert isinstance(ws, lsp.WorkspaceSymbol)
        assert ws.name == "frame.ack"
        assert ws.kind == lsp.SymbolKind.Module
        assert ws.location.uri == "file:///tmp/test.ivy"

    def test_range_preserved(self):
        """The LSP Range in the WorkspaceSymbol matches the input range."""
        fs = FlatSymbol(
            qualified_name="cid",
            kind=lsp.SymbolKind.Class,
            file_path="/tmp/test.ivy",
            range=(2, 5, 2, 15),
        )
        ws = to_workspace_symbol(fs)
        r = ws.location.range
        assert r.start.line == 2
        assert r.start.character == 5
        assert r.end.line == 2
        assert r.end.character == 15

    def test_no_file_path(self):
        """A FlatSymbol with no file_path produces an empty URI."""
        fs = FlatSymbol(
            qualified_name="orphan",
            kind=lsp.SymbolKind.Variable,
            file_path=None,
            range=(0, 0, 0, 0),
        )
        ws = to_workspace_symbol(fs)
        assert ws.location.uri == ""


class TestRegister:
    """Verify that the register function is importable."""

    def test_register_importable(self):
        """The register function can be imported from the module."""
        from ivy_lsp.features.workspace_symbols import register

        assert callable(register)
