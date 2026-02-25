"""Tests for Task 1.5: Lexer Fallback Scanner (TDD).

Verifies that ``fallback_scan`` extracts symbol declarations from Ivy source
using only lexer tokens when the full parser is unavailable or fails.
"""

import pytest
from lsprotocol.types import SymbolKind


class TestFallbackScanSingleDeclarations:
    """Verify extraction of individual declaration types."""

    def test_single_type(self):
        """``type cid`` produces a Class symbol named 'cid'."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("type cid", "test.ivy")
        assert len(symbols) == 1
        sym = symbols[0]
        assert sym.name == "cid"
        assert sym.kind == SymbolKind.Class

    def test_single_object(self):
        """``object foo = { type this }`` produces a Module with a child."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "object foo = {\n    type this\n}\n"
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        sym = symbols[0]
        assert sym.name == "foo"
        assert sym.kind == SymbolKind.Module
        # 'type this' inside the object should become a child
        assert len(sym.children) == 1
        assert sym.children[0].kind == SymbolKind.Class

    def test_single_action(self):
        """``action send(src:cid)`` produces a Function symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("action send(src:cid)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "send"
        assert symbols[0].kind == SymbolKind.Function

    def test_relation(self):
        """``relation r(X,Y)`` produces a Function symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("relation r(X,Y)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "r"
        assert symbols[0].kind == SymbolKind.Function

    def test_module(self):
        """``module counter(t) = { ... }`` produces a Module symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "module counter(t) = {\n    action up = { }\n}\n"
        symbols = fallback_scan(source, "test.ivy")
        # Should have at least the module symbol
        module_syms = [s for s in symbols if s.name == "counter"]
        assert len(module_syms) == 1
        assert module_syms[0].kind == SymbolKind.Module

    def test_include(self):
        """``include quic_types`` is tracked with SymbolKind.File."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("include quic_types", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "quic_types"
        assert symbols[0].kind == SymbolKind.File

    def test_isolate(self):
        """``isolate iso_foo = foo`` produces a Namespace symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("isolate iso_foo = foo", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "iso_foo"
        assert symbols[0].kind == SymbolKind.Namespace

    def test_property_with_label(self):
        """``property [p1] r(X,X)`` uses the label as name."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("property [p1] r(X,X)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "p1"
        assert symbols[0].kind == SymbolKind.Property

    def test_alias(self):
        """``alias aid = cid`` produces a Variable symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("alias aid = cid", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "aid"
        assert symbols[0].kind == SymbolKind.Variable

    def test_before_mixin(self):
        """``before foo.step { ... }`` produces a Function with dotted name."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "before foo.step {\n    require true;\n}\n"
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "foo.step"
        assert symbols[0].kind == SymbolKind.Function

    def test_after_mixin(self):
        """``after foo.step { ... }`` produces a Function with dotted name."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "after foo.step {\n    ensure true;\n}\n"
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "foo.step"
        assert symbols[0].kind == SymbolKind.Function

    def test_instance(self):
        """``instance idx : unbounded_sequence`` produces a Variable."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan(
            "instance idx : unbounded_sequence", "test.ivy"
        )
        assert len(symbols) == 1
        assert symbols[0].name == "idx"
        assert symbols[0].kind == SymbolKind.Variable

    def test_axiom_with_label(self):
        """``axiom [sym] r(X,Y) -> r(Y,X)`` uses label as name."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("axiom [sym] r(X,Y) -> r(Y,X)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "sym"
        assert symbols[0].kind == SymbolKind.Property

    def test_conjecture_with_label(self):
        """``conjecture [c1] true`` uses label as name."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("conjecture [c1] true", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "c1"
        assert symbols[0].kind == SymbolKind.Property


class TestFallbackScanNesting:
    """Verify brace-depth tracking and parent/child hierarchy."""

    def test_nested_objects_child_becomes_child_of_parent(self):
        """Symbols inside ``object { }`` become children of the object."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = (
            "object outer = {\n"
            "    type inner_type\n"
            "    action inner_action(x:t)\n"
            "}\n"
        )
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        outer = symbols[0]
        assert outer.name == "outer"
        assert outer.kind == SymbolKind.Module
        assert len(outer.children) == 2
        child_names = {c.name for c in outer.children}
        assert child_names == {"inner_type", "inner_action"}

    def test_nested_objects_hierarchy(self):
        """Nested objects form a proper parent-child tree."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = (
            "object parent_obj = {\n"
            "    object child_obj = {\n"
            "        type deep\n"
            "    }\n"
            "}\n"
        )
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        parent = symbols[0]
        assert parent.name == "parent_obj"
        assert len(parent.children) == 1
        child = parent.children[0]
        assert child.name == "child_obj"
        assert child.kind == SymbolKind.Module
        assert len(child.children) == 1
        assert child.children[0].name == "deep"

    def test_module_children(self):
        """Declarations inside a module become children."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = (
            "module counter(t) = {\n"
            "    action up\n"
            "    action down\n"
            "}\n"
        )
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        mod = symbols[0]
        assert mod.name == "counter"
        assert len(mod.children) == 2
        child_names = {c.name for c in mod.children}
        assert child_names == {"up", "down"}


class TestFallbackScanEdgeCases:
    """Verify resilience and edge-case handling."""

    def test_syntax_error_resilience(self):
        """Partial results from source with broken tokens.

        The lexer may stop at the illegal character, but symbols
        extracted before the error should be returned.
        """
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "type cid\n!!! broken\ntype pkt_num"
        symbols = fallback_scan(source, "test.ivy")
        # Should get at least the first symbol before the error
        assert len(symbols) >= 1
        assert symbols[0].name == "cid"

    def test_empty_source(self):
        """Empty source returns empty list."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        assert fallback_scan("", "test.ivy") == []

    def test_whitespace_only_source(self):
        """Whitespace-only source returns empty list."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        assert fallback_scan("   \n\n  \t  ", "test.ivy") == []


class TestFallbackScanMetadata:
    """Verify file path propagation and range correctness."""

    def test_file_path_propagation(self):
        """All symbols receive the filename argument."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "type cid\naction send(x:t)"
        symbols = fallback_scan(source, "quic_types.ivy")
        assert len(symbols) == 2
        for sym in symbols:
            assert sym.file_path == "quic_types.ivy"

    def test_range_is_zero_based(self):
        """Symbol ranges use 0-based line numbers."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        # Line 0: type cid
        symbols = fallback_scan("type cid", "test.ivy")
        assert len(symbols) == 1
        start_line = symbols[0].range[0]
        assert start_line == 0  # 0-based

    def test_range_multiline_offset(self):
        """Symbols on different lines have correct 0-based line offsets."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "\n\ntype cid\n"  # cid is on line index 2
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].range[0] == 2

    def test_detail_contains_keyword(self):
        """The detail field contains the lowercase keyword that produced the symbol."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("type cid", "test.ivy")
        assert symbols[0].detail is not None
        assert "type" in symbols[0].detail


class TestFallbackScanComplex:
    """Verify handling of complete multi-declaration source files."""

    def test_complete_source_multiple_types(self):
        """Multiple declaration types in one file are all extracted."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = (
            "type cid\n"
            "type pkt_num\n"
            "alias aid = cid\n"
            "object bit = {\n"
            "    type this\n"
            "}\n"
            "action send(src:cid)\n"
            "relation connected(X:cid, Y:cid)\n"
            "include quic_types\n"
            "isolate iso_foo = protocol\n"
        )
        symbols = fallback_scan(source, "complex.ivy")
        top_names = {s.name for s in symbols}
        assert "cid" in top_names
        assert "pkt_num" in top_names
        assert "aid" in top_names
        assert "bit" in top_names
        assert "send" in top_names
        assert "connected" in top_names
        assert "quic_types" in top_names
        assert "iso_foo" in top_names
        assert len(symbols) == 8

    def test_source_with_lang_header(self):
        """``#lang ivy1.7`` header is ignored (comment)."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        source = "#lang ivy1.7\n\ntype cid\n"
        symbols = fallback_scan(source, "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "cid"

    def test_property_without_label(self):
        """``property r(X,X)`` (no label) uses the first name token."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("property r(X,X)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "r"
        assert symbols[0].kind == SymbolKind.Property

    def test_axiom_without_label(self):
        """``axiom r(X,Y) -> r(Y,X)`` (no label) uses the first name token."""
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        symbols = fallback_scan("axiom r(X,Y) -> r(Y,X)", "test.ivy")
        assert len(symbols) == 1
        assert symbols[0].name == "r"
        assert symbols[0].kind == SymbolKind.Property
