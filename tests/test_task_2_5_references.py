"""Tests for Task 2.5: Find References."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import Position

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestReferencesImport:
    def test_import(self):
        from ivy_lsp.features.references import find_references

        assert find_references is not None


class TestFindReferences:
    def test_finds_references_in_same_file(self, tmp_path):
        from ivy_lsp.features.references import find_references
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        source = "#lang ivy1.7\n\ntype cid\nrelation uses(X:cid, Y:cid)\n"
        (tmp_path / "a.ivy").write_text(source)
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        lines = source.split("\n")
        pos = Position(line=2, character=5)
        results = find_references(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert len(results) >= 1

    def test_finds_references_across_files(self, tmp_path):
        from ivy_lsp.features.references import find_references
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype cid\n")
        (tmp_path / "user.ivy").write_text(
            "#lang ivy1.7\ninclude types\nrelation r(X:cid)\n"
        )
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        lines = (tmp_path / "types.ivy").read_text().split("\n")
        pos = Position(line=1, character=5)
        results = find_references(indexer, str(tmp_path / "types.ivy"), pos, lines)
        uris = [r.uri for r in results]
        assert any("types.ivy" in u for u in uris)
        assert any("user.ivy" in u for u in uris)

    def test_unknown_symbol_returns_empty(self, tmp_path):
        from ivy_lsp.features.references import find_references
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        lines = ["# xyznonexistent"]
        pos = Position(line=0, character=3)
        results = find_references(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert results == []
