"""Tests for Task 2.4: Go-to-Definition."""

import sys
from pathlib import Path

import pytest
from lsprotocol.types import Position

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestDefinitionImport:
    def test_import(self):
        from ivy_lsp.features.definition import goto_definition

        assert goto_definition is not None


class TestGotoDefinition:
    def test_simple_name(self, tmp_path):
        from ivy_lsp.features.definition import goto_definition
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype cid\n")
        (tmp_path / "user.ivy").write_text(
            "#lang ivy1.7\ninclude types\nrelation uses(X:cid, Y:cid)\n"
        )
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        lines = (tmp_path / "user.ivy").read_text().split("\n")
        # Line 2: "relation uses(X:cid, Y:cid)"
        #          0123456789...      16=c 17=i 18=d
        pos = Position(line=2, character=16)  # cursor on first "cid"
        result = goto_definition(indexer, str(tmp_path / "user.ivy"), pos, lines)
        assert result is not None
        loc = result[0] if isinstance(result, list) else result
        assert loc.uri.endswith("types.ivy")

    def test_unknown_returns_none(self, tmp_path):
        from ivy_lsp.features.definition import goto_definition
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
        result = goto_definition(indexer, str(tmp_path / "a.ivy"), pos, lines)
        assert result is None
