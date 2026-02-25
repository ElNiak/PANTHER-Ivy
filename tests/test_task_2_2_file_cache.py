"""Tests for Task 2.2: File Cache."""

import sys
import time
from pathlib import Path

import pytest

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))


class TestFileCacheImport:
    def test_import(self):
        from ivy_lsp.indexer.file_cache import CachedFile, FileCache

        assert FileCache is not None
        assert CachedFile is not None


class TestFileCachePutGet:
    def test_put_and_get_returns_cached(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        f = tmp_path / "a.ivy"
        f.write_text("#lang ivy1.7\ntype t\n")
        cache = FileCache()
        cache.put(str(f), result="ast_a", symbols=["sym_a"])
        entry = cache.get(str(f))
        assert entry is not None
        assert entry.parse_result == "ast_a"
        assert entry.symbols == ["sym_a"]

    def test_get_nonexistent_returns_none(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        cache = FileCache()
        assert cache.get(str(tmp_path / "nope.ivy")) is None


class TestFileCacheMtimeInvalidation:
    def test_stale_mtime_returns_none(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        f = tmp_path / "a.ivy"
        f.write_text("v1")
        cache = FileCache()
        cache.put(str(f), result="v1", symbols=[])
        assert cache.get(str(f)) is not None
        time.sleep(0.05)
        f.write_text("v2")
        assert cache.get(str(f)) is None


class TestFileCacheInvalidate:
    def test_invalidate_removes_entry(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        f = tmp_path / "a.ivy"
        f.write_text("v1")
        cache = FileCache()
        cache.put(str(f), result="v1", symbols=[])
        cache.invalidate(str(f))
        assert cache.get(str(f)) is None

    def test_invalidate_nonexistent_no_error(self):
        from ivy_lsp.indexer.file_cache import FileCache

        cache = FileCache()
        cache.invalidate("/no/such/file.ivy")


class TestFileCacheInvalidateDependents:
    def test_invalidate_cascades_to_dependents(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache
        from ivy_lsp.parsing.symbols import IncludeGraph

        a, b, c = (tmp_path / f for f in ("a.ivy", "b.ivy", "c.ivy"))
        for f in (a, b, c):
            f.write_text("#lang ivy1.7\n")
        cache = FileCache()
        for f, name in ((a, "a"), (b, "b"), (c, "c")):
            cache.put(str(f), result=name, symbols=[])
        graph = IncludeGraph()
        graph.add_edge(str(b), str(a))  # b includes a
        graph.add_edge(str(c), str(a))  # c includes a
        cache.invalidate_dependents(str(a), graph)
        assert cache.get(str(a)) is not None  # a itself NOT invalidated
        assert cache.get(str(b)) is None  # b invalidated
        assert cache.get(str(c)) is None  # c invalidated


class TestFileCacheLRU:
    def test_lru_eviction_at_max_size(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        cache = FileCache(max_size=3)
        files = []
        for i in range(4):
            f = tmp_path / f"{i}.ivy"
            f.write_text(f"v{i}")
            files.append(f)
            cache.put(str(f), result=f"r{i}", symbols=[])
        assert cache.get(str(files[0])) is None  # evicted (LRU)
        assert cache.get(str(files[1])) is not None
        assert cache.get(str(files[3])) is not None

    def test_get_refreshes_lru_order(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        cache = FileCache(max_size=3)
        files = []
        for i in range(3):
            f = tmp_path / f"{i}.ivy"
            f.write_text(f"v{i}")
            files.append(f)
            cache.put(str(f), result=f"r{i}", symbols=[])
        cache.get(str(files[0]))  # refresh file 0
        f3 = tmp_path / "3.ivy"
        f3.write_text("v3")
        cache.put(str(f3), result="r3", symbols=[])
        assert cache.get(str(files[0])) is not None  # refreshed, not evicted
        assert cache.get(str(files[1])) is None  # evicted


class TestFileCacheIncludes:
    def test_cached_file_stores_includes(self, tmp_path):
        from ivy_lsp.indexer.file_cache import FileCache

        f = tmp_path / "a.ivy"
        f.write_text("#lang ivy1.7\n")
        cache = FileCache()
        cache.put(
            str(f),
            result="ast",
            symbols=[],
            includes=["quic_types", "collections"],
        )
        entry = cache.get(str(f))
        assert entry is not None
        assert entry.includes == ["quic_types", "collections"]
