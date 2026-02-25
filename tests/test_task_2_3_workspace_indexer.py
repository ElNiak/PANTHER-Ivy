"""Tests for Task 2.3: Workspace Indexer."""

import sys
import time
from pathlib import Path

import pytest

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))

QUIC_STACK_DIR = IVY_ROOT / "protocol-testing" / "quic" / "quic_stack"


class TestWorkspaceIndexerImport:
    def test_import(self):
        from ivy_lsp.indexer.workspace_indexer import SymbolLocation, WorkspaceIndexer
        assert WorkspaceIndexer is not None
        assert SymbolLocation is not None


class TestIndexWorkspace:
    def test_index_workspace_parses_all_files(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype a_type\n")
        (tmp_path / "b.ivy").write_text("#lang ivy1.7\ntype b_type\n")

        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        syms_a = indexer.get_symbols(str(tmp_path / "a.ivy"))
        syms_b = indexer.get_symbols(str(tmp_path / "b.ivy"))
        assert any(s.name == "a_type" for s in syms_a)
        assert any(s.name == "b_type" for s in syms_b)


class TestReindexFile:
    def test_reindex_updates_symbols(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        f = tmp_path / "a.ivy"
        f.write_text("#lang ivy1.7\ntype old_type\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        assert any(s.name == "old_type" for s in indexer.get_symbols(str(f)))

        time.sleep(0.05)
        f.write_text("#lang ivy1.7\ntype new_type\n")
        indexer.reindex_file(str(f))
        names = [s.name for s in indexer.get_symbols(str(f))]
        assert "new_type" in names


class TestLookupSymbol:
    def test_lookup_finds_symbol_across_files(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "types.ivy").write_text("#lang ivy1.7\ntype cid\n")
        (tmp_path / "frame.ivy").write_text("#lang ivy1.7\ninclude types\ntype frame_type\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        results = indexer.lookup_symbol("cid")
        assert len(results) >= 1
        assert results[0].filepath == str(tmp_path / "types.ivy")

    def test_lookup_qualified_name(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        source = "#lang ivy1.7\n\nobject frame = {\n    type this\n}\n"
        (tmp_path / "a.ivy").write_text(source)
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        results = indexer.lookup_symbol("frame")
        assert len(results) >= 1


class TestGetSymbolsInScope:
    def test_includes_own_and_transitive_symbols(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "base.ivy").write_text("#lang ivy1.7\ntype base_t\n")
        (tmp_path / "mid.ivy").write_text("#lang ivy1.7\ninclude base\ntype mid_t\n")
        (tmp_path / "top.ivy").write_text("#lang ivy1.7\ninclude mid\ntype top_t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()

        scope_syms = indexer.get_symbols_in_scope(str(tmp_path / "top.ivy"))
        names = [s.name for s in scope_syms]
        assert "top_t" in names
        assert "mid_t" in names
        assert "base_t" in names

    def test_file_without_includes_only_own_symbols(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype a_t\n")
        (tmp_path / "b.ivy").write_text("#lang ivy1.7\ntype b_t\n")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(tmp_path))
        indexer = WorkspaceIndexer(str(tmp_path), parser, resolver)
        indexer.index_workspace()
        scope_a = indexer.get_symbols_in_scope(str(tmp_path / "a.ivy"))
        names = [s.name for s in scope_a]
        assert "a_t" in names
        assert "b_t" not in names


class TestWorkspaceIndexerQuicStack:
    def test_index_quic_stack(self):
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        if not QUIC_STACK_DIR.exists():
            pytest.skip("quic_stack not found")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(QUIC_STACK_DIR))
        indexer = WorkspaceIndexer(str(QUIC_STACK_DIR), parser, resolver)
        indexer.index_workspace()

        results = indexer.lookup_symbol("cid")
        assert len(results) >= 1

        frame_scope = indexer.get_symbols_in_scope(str(QUIC_STACK_DIR / "quic_frame.ivy"))
        assert len(frame_scope) > 5
