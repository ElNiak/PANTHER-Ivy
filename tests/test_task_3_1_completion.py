"""Tests for Task 3.1: Completion Feature."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import CompletionItemKind, Position, SymbolKind

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestCompletionImport:
    def test_import(self):
        from ivy_lsp.features.completion import (
            CompletionContext,
            detect_context,
            get_completions,
        )

        assert detect_context is not None
        assert get_completions is not None
        assert CompletionContext is not None


class TestDetectCompletionContext:
    def test_after_dot(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("frame.", 6)
        assert ctx == CompletionContext.DOT_ACCESS
        assert scope == "frame"
        assert prefix == ""

    def test_after_dot_with_prefix(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("frame.ac", 8)
        assert ctx == CompletionContext.DOT_ACCESS
        assert scope == "frame"
        assert prefix == "ac"

    def test_nested_dot(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("frame.ack.", 10)
        assert ctx == CompletionContext.DOT_ACCESS
        assert scope == "frame.ack"

    def test_after_include(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("include ", 8)
        assert ctx == CompletionContext.INCLUDE
        assert prefix == ""

    def test_include_partial(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("include qu", 10)
        assert ctx == CompletionContext.INCLUDE
        assert prefix == "qu"

    def test_general_empty(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("", 0)
        assert ctx == CompletionContext.GENERAL

    def test_general_mid_identifier(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("ci", 2)
        assert ctx == CompletionContext.GENERAL
        assert prefix == "ci"

    def test_indented_include(self):
        from ivy_lsp.features.completion import CompletionContext, detect_context

        ctx, prefix, scope = detect_context("    include ", 12)
        assert ctx == CompletionContext.INCLUDE


class TestDotAccessCompletion:
    def test_object_children(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        src = "#lang ivy1.7\nobject bit = {\n    type this\n    individual zero:bit\n    individual one:bit\n}\n"
        (tmp_path / "a.ivy").write_text(src)
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        # Line: "bit."  cursor at col 4
        lines = src.split("\n") + ["bit."]
        pos = Position(line=len(lines) - 1, character=4)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "this" in labels or "zero" in labels or "one" in labels

    def test_unknown_scope_returns_empty(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["unknown_obj."]
        pos = Position(line=0, character=12)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert items == []


class TestIncludeCompletion:
    def test_lists_ivy_files(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype t\n")
        (tmp_path / "utils.ivy").write_text("#lang ivy1.7\ntype u\n")
        (tmp_path / "main.ivy").write_text("#lang ivy1.7\ninclude \n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "include "]
        pos = Position(line=1, character=8)
        items = get_completions(indexer, str(tmp_path / "main.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "types" in labels
        assert "utils" in labels

    def test_excludes_self(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "main.ivy").write_text("#lang ivy1.7\ninclude \n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "include "]
        pos = Position(line=1, character=8)
        items = get_completions(indexer, str(tmp_path / "main.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "main" not in labels

    def test_partial_filter(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype t\n")
        (tmp_path / "utils.ivy").write_text("#lang ivy1.7\ntype u\n")
        (tmp_path / "main.ivy").write_text("#lang ivy1.7\ninclude ty\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "include ty"]
        pos = Position(line=1, character=10)
        items = get_completions(indexer, str(tmp_path / "main.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "types" in labels
        assert "utils" not in labels


class TestGeneralCompletion:
    def test_symbols_in_scope(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\ntype pkt_num\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "type cid", "type pkt_num", ""]
        pos = Position(line=3, character=0)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "cid" in labels
        assert "pkt_num" in labels

    def test_keywords_included(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "type t", ""]
        pos = Position(line=2, character=0)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "action" in labels
        assert "type" in labels
        assert "object" in labels

    def test_prefix_filters(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\ntype pkt_num\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "type cid", "type pkt_num", "ci"]
        pos = Position(line=3, character=2)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert "cid" in labels
        # pkt_num should be filtered out by "ci" prefix
        assert "pkt_num" not in labels

    def test_no_duplicates(self, tmp_path):
        from ivy_lsp.features.completion import get_completions
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype cid\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "type cid", ""]
        pos = Position(line=2, character=0)
        items = get_completions(indexer, str(tmp_path / "a.ivy"), pos, lines)
        labels = [i.label for i in items]
        assert len(labels) == len(set(labels))


class TestCompletionItemKindMapping:
    def test_symbol_to_completion_kind(self):
        from ivy_lsp.features.completion import _symbol_kind_to_completion_kind

        assert (
            _symbol_kind_to_completion_kind(SymbolKind.Class)
            == CompletionItemKind.Class
        )
        assert (
            _symbol_kind_to_completion_kind(SymbolKind.Function)
            == CompletionItemKind.Function
        )
        assert (
            _symbol_kind_to_completion_kind(SymbolKind.Module)
            == CompletionItemKind.Module
        )
