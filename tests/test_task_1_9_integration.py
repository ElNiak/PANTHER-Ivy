"""Tests for Task 1.9: Phase 1 Integration Testing.

End-to-end tests that exercise the full pipeline: parse -> ast_to_symbols
-> verify for various Ivy declaration types, plus corpus-level validation
against the real QUIC protocol stack .ivy files.
"""

import logging
from pathlib import Path

import pytest
from lsprotocol.types import SymbolKind

from ivy_lsp.features.document_symbols import get_document_symbols
from ivy_lsp.features.workspace_symbols import flatten_symbols, search_symbols
from ivy_lsp.parsing.ast_to_symbols import ast_to_symbols
from ivy_lsp.parsing.fallback_scanner import fallback_scan
from ivy_lsp.parsing.parser_session import IvyParserWrapper
from ivy_lsp.parsing.symbols import IvySymbol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IVY_ROOT = Path(__file__).resolve().parent.parent
QUIC_STACK_DIR = IVY_ROOT / "protocol-testing" / "quic" / "quic_stack"


def _full_pipeline(source: str, filename: str = "test.ivy"):
    """Parse source, convert AST to symbols, return symbol list.

    Asserts that parsing succeeds.
    """
    wrapper = IvyParserWrapper()
    result = wrapper.parse(source, filename)
    assert result.success, f"Parse failed: {result.errors}"
    return ast_to_symbols(result.ast, filename, source)


def _find_symbol(symbols, name, kind=None):
    """Recursively find a symbol by name (and optionally kind)."""
    for sym in symbols:
        if sym.name == name and (kind is None or sym.kind == kind):
            return sym
        found = _find_symbol(sym.children, name, kind)
        if found is not None:
            return found
    return None


def _collect_all_names(symbols):
    """Recursively collect all symbol names from a hierarchy."""
    names = []
    for sym in symbols:
        names.append(sym.name)
        names.extend(_collect_all_names(sym.children))
    return names


# ---------------------------------------------------------------------------
# Snippet tests: one per declaration type (full pipeline)
# ---------------------------------------------------------------------------


class TestSnippetType:
    """type cid -> Class named 'cid'."""

    def test_type_declaration(self):
        source = "#lang ivy1.7\n\ntype cid\n"
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "cid")
        assert sym is not None, "Expected symbol 'cid'"
        assert sym.kind == SymbolKind.Class


class TestSnippetEnumType:
    """type sk = {a, b} -> Class with enum detail."""

    def test_enum_type_has_detail(self):
        source = "#lang ivy1.7\n\ntype sk = {a, b}\n"
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "sk")
        assert sym is not None, "Expected symbol 'sk'"
        assert sym.kind == SymbolKind.Class
        assert sym.detail is not None, "Enum type should have detail"
        assert "a" in sym.detail
        assert "b" in sym.detail


class TestSnippetAlias:
    """alias aid = cid -> Variable named 'aid'."""

    def test_alias_declaration(self):
        source = "#lang ivy1.7\n\ntype cid\nalias aid = cid\n"
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "aid")
        assert sym is not None, "Expected symbol 'aid'"
        assert sym.kind == SymbolKind.Variable


class TestSnippetObject:
    """object bit = { type this; individual zero:bit } -> Module with children."""

    def test_object_is_module_with_children(self):
        source = """\
#lang ivy1.7

object bit = {
    type this
    individual zero:bit
}
"""
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "bit", SymbolKind.Module)
        assert sym is not None, "Expected Module symbol 'bit'"
        child_names = [c.name for c in sym.children]
        assert "zero" in child_names, (
            f"Expected 'zero' in children, got {child_names}"
        )


class TestSnippetAction:
    """action next(e:this) returns (e:this) -> Function with param detail."""

    def test_action_has_params_in_detail(self):
        source = """\
#lang ivy1.7

type cid

action next(e:cid) returns (r:cid) = {
    r := e
}
"""
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "next")
        assert sym is not None, "Expected symbol 'next'"
        assert sym.kind == SymbolKind.Function
        assert sym.detail is not None, "Action should have param detail"
        assert "e" in sym.detail


class TestSnippetRelation:
    """relation r(X, Y) -> Function named 'r'."""

    def test_relation_is_function(self):
        source = """\
#lang ivy1.7

type t

relation r(X:t, Y:t)
"""
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "r")
        assert sym is not None, "Expected symbol 'r'"
        assert sym.kind == SymbolKind.Function


class TestSnippetInstance:
    """instance idx : unbounded_sequence -> parser expands to ObjectDecl."""

    def test_instance_expansion(self):
        source = """\
#lang ivy1.7

type node

module unbounded_sequence(t) = {
    type this
    action next(x:this) returns (y:this)
}

instance idx : unbounded_sequence(node)
"""
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "idx")
        assert sym is not None, "Expected symbol 'idx'"
        # Parser expands instance to ObjectDecl -> Module
        assert sym.kind == SymbolKind.Module


class TestSnippetProperty:
    """property [p1] ... -> Property named 'p1'."""

    def test_property_is_property_kind(self):
        source = """\
#lang ivy1.7

type t
relation r(X:t, Y:t)

property [p1] r(X, X)
"""
        symbols = _full_pipeline(source)
        sym = _find_symbol(symbols, "p1")
        assert sym is not None, "Expected symbol 'p1'"
        assert sym.kind == SymbolKind.Property


class TestSnippetNestedObjects:
    """Nested objects: frame -> ack -> Module 'frame' with child Module 'ack'."""

    def test_nested_object_hierarchy(self):
        source = """\
#lang ivy1.7

object frame = {
    object ack = {
        type this
    }
    type this
}
"""
        symbols = _full_pipeline(source)
        frame_sym = _find_symbol(symbols, "frame", SymbolKind.Module)
        assert frame_sym is not None, "Expected Module symbol 'frame'"
        ack_child = None
        for child in frame_sym.children:
            if child.name == "ack" and child.kind == SymbolKind.Module:
                ack_child = child
                break
        assert ack_child is not None, (
            f"Expected 'ack' as Module child of 'frame', "
            f"got children: {[(c.name, c.kind) for c in frame_sym.children]}"
        )


# ---------------------------------------------------------------------------
# Real file tests: quic_types.ivy
# ---------------------------------------------------------------------------


class TestQuicTypesFullPipeline:
    """Parse quic_types.ivy through the full pipeline."""

    def test_find_key_symbols(self, quic_types_source, quic_types_path):
        """Parse quic_types.ivy and find expected type/object symbols."""
        symbols = _full_pipeline(quic_types_source, str(quic_types_path))
        expected_names = ["cid", "pkt_num", "version", "bit", "quic_packet_type"]
        all_names = _collect_all_names(symbols)
        for name in expected_names:
            assert name in all_names, (
                f"Expected symbol '{name}' in quic_types.ivy, "
                f"got: {sorted(set(all_names))}"
            )

    def test_full_pipeline_to_document_symbols(
        self, quic_types_source, quic_types_path
    ):
        """Parse -> symbols -> DocumentSymbol list is non-empty."""
        symbols = _full_pipeline(quic_types_source, str(quic_types_path))
        doc_syms = get_document_symbols(symbols)
        assert len(doc_syms) > 0, "Expected non-empty DocumentSymbol list"
        # Verify all doc symbols have names
        for ds in doc_syms:
            assert ds.name, "DocumentSymbol must have a name"

    def test_full_pipeline_to_workspace_search(
        self, quic_types_source, quic_types_path
    ):
        """Parse -> symbols -> flatten -> search('cid') finds 'cid'."""
        symbols = _full_pipeline(quic_types_source, str(quic_types_path))
        flat = flatten_symbols(symbols)
        results = search_symbols(flat, "cid")
        found_names = [r.qualified_name for r in results]
        assert any("cid" in n for n in found_names), (
            f"search('cid') should find 'cid', got: {found_names}"
        )


# ---------------------------------------------------------------------------
# Fallback scanner tests
# ---------------------------------------------------------------------------


class TestFallbackScanner:
    """Fallback scanner handles broken and empty files."""

    def test_syntax_error_file_produces_some_symbols(self):
        """File with syntax error should still produce symbols via fallback."""
        source = """\
#lang ivy1.7

type cid
object broken = {
    type this
    this is not valid ivy syntax !!!
}
type pkt_num
"""
        symbols = fallback_scan(source, "broken.ivy")
        assert isinstance(symbols, list)
        all_names = _collect_all_names(symbols)
        # Should find at least 'cid' and/or 'pkt_num' from valid declarations
        assert len(all_names) > 0, (
            "Fallback scanner should extract at least some symbols "
            "from a file with mixed valid/invalid content"
        )

    def test_empty_file_no_crash(self):
        """Empty file (just lang header + newline) returns empty list."""
        source = "#lang ivy1.7\n"
        symbols = fallback_scan(source, "empty.ivy")
        assert isinstance(symbols, list)
        assert len(symbols) == 0

    def test_lang_header_only_no_crash(self):
        """File with only '#lang ivy1.7' (no trailing newline) returns empty."""
        source = "#lang ivy1.7"
        symbols = fallback_scan(source, "header_only.ivy")
        assert isinstance(symbols, list)
        assert len(symbols) == 0


# ---------------------------------------------------------------------------
# Corpus test class: parse ALL quic_stack/*.ivy files
# ---------------------------------------------------------------------------


class TestCorpusParsing:
    """Parse every .ivy file in the QUIC stack directory without crashes."""

    @pytest.fixture(autouse=True)
    def _setup_corpus(self, quic_stack_ivy_files):
        """Store the list of .ivy files for all tests in this class."""
        self.ivy_files = quic_stack_ivy_files

    def test_all_files_parse_without_crash(self):
        """No .ivy file should cause a crash during parse or symbol extraction."""
        wrapper = IvyParserWrapper()
        full_parse_success = 0
        fallback_used = 0
        total = len(self.ivy_files)
        failures = []

        for ivy_file in self.ivy_files:
            source = ivy_file.read_text()
            filename = str(ivy_file)
            try:
                result = wrapper.parse(source, filename)
                if result.success:
                    symbols = ast_to_symbols(result.ast, filename, source)
                    assert isinstance(symbols, list)
                    full_parse_success += 1
                else:
                    symbols = fallback_scan(source, filename)
                    assert isinstance(symbols, list)
                    fallback_used += 1
            except Exception as exc:
                failures.append((ivy_file.name, str(exc)))

        logger.info(
            "Corpus results: %d/%d full parse, %d/%d fallback, %d/%d failed",
            full_parse_success,
            total,
            fallback_used,
            total,
            len(failures),
            total,
        )

        assert len(failures) == 0, (
            f"Crashes during corpus parsing: {failures}"
        )

    def test_at_least_one_file_parses_fully(self):
        """Sanity check: at least one .ivy file should parse without errors."""
        wrapper = IvyParserWrapper()
        any_success = False

        for ivy_file in self.ivy_files:
            source = ivy_file.read_text()
            result = wrapper.parse(source, str(ivy_file))
            if result.success:
                symbols = ast_to_symbols(result.ast, str(ivy_file), source)
                if len(symbols) > 0:
                    any_success = True
                    break

        assert any_success, (
            "At least one .ivy file should parse fully and produce symbols"
        )

    def test_zero_crashes_across_corpus(self):
        """Redundant crash-safety check: iterate all files, no exceptions."""
        wrapper = IvyParserWrapper()
        crash_count = 0

        for ivy_file in self.ivy_files:
            source = ivy_file.read_text()
            filename = str(ivy_file)
            try:
                result = wrapper.parse(source, filename)
                if result.success:
                    ast_to_symbols(result.ast, filename, source)
                else:
                    fallback_scan(source, filename)
            except Exception:
                crash_count += 1

        assert crash_count == 0, (
            f"Expected zero crashes, got {crash_count}"
        )

    def test_corpus_symbol_counts(self):
        """Log symbol counts per file for diagnostic purposes."""
        wrapper = IvyParserWrapper()
        file_symbol_counts = {}

        for ivy_file in self.ivy_files:
            source = ivy_file.read_text()
            filename = str(ivy_file)
            try:
                result = wrapper.parse(source, filename)
                if result.success:
                    symbols = ast_to_symbols(result.ast, filename, source)
                else:
                    symbols = fallback_scan(source, filename)
                all_names = _collect_all_names(symbols)
                file_symbol_counts[ivy_file.name] = len(all_names)
            except Exception:
                file_symbol_counts[ivy_file.name] = -1

        logger.info("Corpus symbol counts: %s", file_symbol_counts)
        # At minimum, quic_types.ivy should have substantial symbols
        assert file_symbol_counts.get("quic_types.ivy", 0) >= 5, (
            f"quic_types.ivy should have at least 5 symbols, "
            f"got {file_symbol_counts.get('quic_types.ivy', 0)}"
        )
