"""Tests for Task 2.1: Include Resolver."""

import os
import sys
from pathlib import Path

import pytest

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestIncludeResolverImport:
    def test_import(self):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        assert IncludeResolver is not None


class TestIncludeResolverSameDir:
    def test_resolve_same_dir(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        (tmp_path / "a.ivy").write_text("#lang ivy1.7\ntype a\n")
        (tmp_path / "b.ivy").write_text("#lang ivy1.7\ninclude a\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("a", str(tmp_path / "b.ivy"))
        assert result is not None
        assert result == str(tmp_path / "a.ivy")

    def test_resolve_nonexistent_returns_none(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        (tmp_path / "b.ivy").write_text("#lang ivy1.7\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("nonexistent", str(tmp_path / "b.ivy"))
        assert result is None


class TestIncludeResolverWorkspaceRoot:
    def test_resolve_workspace_root(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "shared.ivy").write_text("#lang ivy1.7\ntype s\n")
        (subdir / "user.ivy").write_text("#lang ivy1.7\ninclude shared\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("shared", str(subdir / "user.ivy"))
        assert result == str(tmp_path / "shared.ivy")


class TestIncludeResolverStdLib:
    def test_resolve_collections(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        (tmp_path / "test.ivy").write_text("#lang ivy1.7\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("collections", str(tmp_path / "test.ivy"))
        assert result is not None
        assert result.endswith("collections.ivy")
        assert "include" in result

    def test_resolve_order(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        (tmp_path / "test.ivy").write_text("#lang ivy1.7\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("order", str(tmp_path / "test.ivy"))
        assert result is not None
        assert result.endswith("order.ivy")


class TestIncludeResolverOverride:
    def test_override_std_lib_path(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        fake_std = tmp_path / "fake_std"
        fake_std.mkdir()
        (fake_std / "custom.ivy").write_text("#lang ivy1.7\n")
        resolver = IncludeResolver(str(tmp_path), ivy_include_path=str(fake_std))
        result = resolver.resolve("custom", str(tmp_path / "test.ivy"))
        assert result == str(fake_std / "custom.ivy")


class TestIncludeResolverPriority:
    def test_same_dir_wins_over_workspace_root(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "shared.ivy").write_text("# workspace root version\n")
        (sub / "shared.ivy").write_text("# same dir version\n")
        (sub / "user.ivy").write_text("#lang ivy1.7\n")
        resolver = IncludeResolver(str(tmp_path))
        result = resolver.resolve("shared", str(sub / "user.ivy"))
        assert result == str(sub / "shared.ivy")


class TestFindAllIvyFiles:
    def test_finds_all_files(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        (tmp_path / "a.ivy").write_text("")
        (tmp_path / "b.ivy").write_text("")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.ivy").write_text("")
        (tmp_path / "d.txt").write_text("")
        resolver = IncludeResolver(str(tmp_path))
        files = resolver.find_all_ivy_files()
        assert len(files) == 3
        names = {os.path.basename(f) for f in files}
        assert names == {"a.ivy", "b.ivy", "c.ivy"}

    def test_empty_dir(self, tmp_path):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        resolver = IncludeResolver(str(tmp_path))
        assert resolver.find_all_ivy_files() == []


class TestIncludeResolverQuicStack:
    def test_quic_frame_includes_resolve(self):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        quic_stack = (
            Path(__file__).resolve().parent.parent
            / "protocol-testing"
            / "quic"
            / "quic_stack"
        )
        if not quic_stack.exists():
            pytest.skip("quic_stack not found")
        resolver = IncludeResolver(str(quic_stack))
        frame_file = str(quic_stack / "quic_frame.ivy")
        result = resolver.resolve("quic_stream", frame_file)
        assert result is not None
        assert result.endswith("quic_stream.ivy")
        result = resolver.resolve("collections", frame_file)
        assert result is not None
        assert "include" in result

    def test_find_all_ivy_files_quic_stack(self):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        quic_stack = (
            Path(__file__).resolve().parent.parent
            / "protocol-testing"
            / "quic"
            / "quic_stack"
        )
        if not quic_stack.exists():
            pytest.skip("quic_stack not found")
        resolver = IncludeResolver(str(quic_stack))
        files = resolver.find_all_ivy_files()
        assert len(files) >= 15
