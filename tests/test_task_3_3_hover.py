"""Tests for Task 3.3: Hover Feature."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import Position, SymbolKind

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestHoverImport:
    def test_import(self):
        from ivy_lsp.features.hover import format_hover_content, get_hover_info

        assert format_hover_content is not None
        assert get_hover_info is not None


class TestFormatHoverContent:
    def _sym(self, name, kind, detail=None, children=None, file_path=None):
        from ivy_lsp.parsing.symbols import IvySymbol

        return IvySymbol(
            name=name,
            kind=kind,
            range=(0, 0, 0, len(name)),
            children=children or [],
            detail=detail,
            file_path=file_path,
        )

    def test_type_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("cid", SymbolKind.Class)
        result = format_hover_content(sym)
        assert "```ivy" in result
        assert "type cid" in result

    def test_enum_type_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("stream_kind", SymbolKind.Class, detail="enum: unidir, bidir")
        result = format_hover_content(sym)
        assert "type stream_kind" in result
        assert "unidir" in result
        assert "bidir" in result

    def test_action_symbol_with_signature(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym(
            "send", SymbolKind.Function, detail="(src:cid, dst:cid, pkt:pkt_num)"
        )
        result = format_hover_content(sym)
        assert "action send" in result
        assert "src:cid" in result

    def test_relation_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("connected", SymbolKind.Function, detail="relation")
        result = format_hover_content(sym)
        assert "relation connected" in result

    def test_object_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        child = self._sym("zero", SymbolKind.Variable)
        sym = self._sym("bit", SymbolKind.Module, children=[child])
        result = format_hover_content(sym)
        assert "object bit" in result or "module bit" in result

    def test_property_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("reflexivity", SymbolKind.Property)
        result = format_hover_content(sym)
        assert "property reflexivity" in result or "axiom reflexivity" in result

    def test_namespace_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("iso_protocol", SymbolKind.Namespace)
        result = format_hover_content(sym)
        assert "isolate iso_protocol" in result

    def test_variable_symbol(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("aid", SymbolKind.Variable, detail="alias")
        result = format_hover_content(sym)
        assert "alias aid" in result

    def test_file_path_in_hover(self):
        from ivy_lsp.features.hover import format_hover_content

        sym = self._sym("cid", SymbolKind.Class, file_path="/ws/quic_types.ivy")
        result = format_hover_content(sym)
        assert "quic_types.ivy" in result

    def test_none_symbol_returns_none(self):
        from ivy_lsp.features.hover import format_hover_content

        result = format_hover_content(None)
        assert result is None


class TestGetHoverInfo:
    def test_hover_on_known_symbol(self, tmp_path):
        from ivy_lsp.features.hover import get_hover_info
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype cid\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["#lang ivy1.7", "type cid"]
        pos = Position(line=1, character=5)  # cursor on "cid"
        result = get_hover_info(indexer, str(tmp_path / "types.ivy"), pos, lines)
        assert result is not None
        assert "cid" in result.contents.value

    def test_hover_on_unknown_symbol(self, tmp_path):
        from ivy_lsp.features.hover import get_hover_info
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["# nothing_here"]
        pos = Position(line=0, character=5)
        result = get_hover_info(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert result is None

    def test_hover_on_empty_position(self, tmp_path):
        from ivy_lsp.features.hover import get_hover_info
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = ["", "type t"]
        pos = Position(line=0, character=0)  # empty line
        result = get_hover_info(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert result is None
