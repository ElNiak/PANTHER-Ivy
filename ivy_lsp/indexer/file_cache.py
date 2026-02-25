"""Mtime-based file parse cache with LRU eviction."""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class CachedFile:
    """Cached parse result for a single file."""

    filepath: str
    mtime: float
    parse_result: Any
    symbols: List[Any]
    includes: List[str] = field(default_factory=list)


class FileCache:
    """LRU cache of parsed Ivy file results, keyed by filepath."""

    def __init__(self, max_size: int = 500) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, CachedFile] = OrderedDict()

    def get(self, filepath: str) -> Optional[CachedFile]:
        """Return cached entry if it exists and mtime still matches.

        Moves the entry to the end of the LRU order on hit.
        Returns None and removes the entry if the file was modified
        or deleted since caching.
        """
        entry = self._cache.get(filepath)
        if entry is None:
            return None
        try:
            current_mtime = os.path.getmtime(filepath)
        except OSError:
            self._cache.pop(filepath, None)
            return None
        if current_mtime != entry.mtime:
            self._cache.pop(filepath, None)
            return None
        self._cache.move_to_end(filepath)
        return entry

    def put(
        self,
        filepath: str,
        result: Any,
        symbols: List[Any],
        includes: Optional[List[str]] = None,
    ) -> None:
        """Store a parse result with the file's current mtime.

        Evicts the oldest entry if the cache exceeds *max_size*.
        Silently returns if the file cannot be stat'd.
        """
        try:
            mtime = os.path.getmtime(filepath)
        except OSError:
            return
        entry = CachedFile(
            filepath=filepath,
            mtime=mtime,
            parse_result=result,
            symbols=symbols,
            includes=includes or [],
        )
        self._cache[filepath] = entry
        self._cache.move_to_end(filepath)
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, filepath: str) -> None:
        """Remove *filepath* from the cache. No error if absent."""
        self._cache.pop(filepath, None)

    def invalidate_dependents(
        self, filepath: str, include_graph: Any
    ) -> None:
        """Invalidate all files that directly include *filepath*.

        Uses ``include_graph.get_included_by(filepath)`` to discover
        dependents.  The file itself is **not** invalidated.
        """
        dependents = include_graph.get_included_by(filepath)
        for dep in dependents:
            self._cache.pop(dep, None)
