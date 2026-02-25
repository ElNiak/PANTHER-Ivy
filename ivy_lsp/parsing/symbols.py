"""Symbol representations and lookup structures for Ivy source analysis.

Provides the core data types used throughout the LSP server to represent
parsed Ivy symbols, their hierarchical scopes, and inter-file include
relationships.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from lsprotocol.types import SymbolKind


@dataclass
class IvySymbol:
    """A single symbol extracted from an Ivy source file.

    Attributes:
        name: The symbol's identifier (e.g., ``"cid"``, ``"send"``).
        kind: LSP symbol kind (Class, Function, Variable, etc.).
        range: 0-based ``(start_line, start_col, end_line, end_col)`` span.
        children: Nested symbols (e.g., fields inside an object).
        detail: Optional human-readable signature or type string.
        file_path: Optional originating file path.
    """

    name: str
    kind: SymbolKind
    range: Tuple[int, int, int, int]
    children: List[IvySymbol] = field(default_factory=list)
    detail: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class IvyScope:
    """A named scope that holds symbols and links to parent/child scopes.

    Attributes:
        name: Scope identifier (e.g., ``"global"``, ``"bit"``).
        symbols: Mapping of symbol name to ``IvySymbol`` within this scope.
        parent: Enclosing scope, or ``None`` for the root.
        children: Nested child scopes.
    """

    name: str
    symbols: Dict[str, IvySymbol] = field(default_factory=dict)
    parent: Optional[IvyScope] = None
    children: List[IvyScope] = field(default_factory=list)


class SymbolTable:
    """Indexed collection of ``IvySymbol`` instances with fast lookup.

    Supports lookup by plain name, qualified dotted path (walking the
    ``children`` hierarchy), file path, and enumeration of all symbols.
    """

    def __init__(self) -> None:
        self._by_name: Dict[str, List[IvySymbol]] = defaultdict(list)
        self._by_file: Dict[str, List[IvySymbol]] = defaultdict(list)
        self._all: List[IvySymbol] = []

    def add_symbol(self, sym: IvySymbol) -> None:
        """Register *sym* in all internal indices."""
        self._by_name[sym.name].append(sym)
        if sym.file_path is not None:
            self._by_file[sym.file_path].append(sym)
        self._all.append(sym)

    def lookup(self, name: str) -> List[IvySymbol]:
        """Return all top-level symbols whose name matches *name*."""
        return list(self._by_name.get(name, []))

    def lookup_qualified(self, qualified_name: str) -> List[IvySymbol]:
        """Walk the ``children`` hierarchy along a dotted path.

        For ``"frame.ack.range"``, first find all top-level symbols named
        ``"frame"``, then look for ``"ack"`` among each one's children,
        then ``"range"`` among *those* children.  Returns the matching
        leaf symbols.
        """
        if not qualified_name:
            return []

        parts = qualified_name.split(".")
        candidates: List[IvySymbol] = self.lookup(parts[0])

        for part in parts[1:]:
            next_candidates: List[IvySymbol] = []
            for sym in candidates:
                for child in sym.children:
                    if child.name == part:
                        next_candidates.append(child)
            candidates = next_candidates
            if not candidates:
                return []

        return candidates

    def all_symbols(self) -> List[IvySymbol]:
        """Return every registered symbol."""
        return list(self._all)

    def symbols_in_file(self, path: str) -> List[IvySymbol]:
        """Return symbols whose ``file_path`` equals *path*."""
        return list(self._by_file.get(path, []))


class IncludeGraph:
    """Directed graph of Ivy ``include`` relationships between files.

    Tracks both forward (``includes``) and reverse (``included_by``)
    edges and supports cycle-safe transitive traversal.
    """

    def __init__(self) -> None:
        self._includes: Dict[str, Set[str]] = defaultdict(set)
        self._included_by: Dict[str, Set[str]] = defaultdict(set)

    def add_edge(self, from_file: str, to_file: str) -> None:
        """Record that *from_file* includes *to_file*."""
        self._includes[from_file].add(to_file)
        self._included_by[to_file].add(from_file)

    def get_includes(self, f: str) -> Set[str]:
        """Direct includes of *f*."""
        return set(self._includes.get(f, set()))

    def get_included_by(self, f: str) -> Set[str]:
        """Files that directly include *f*."""
        return set(self._included_by.get(f, set()))

    def get_transitive_includes(self, f: str) -> Set[str]:
        """All files transitively included by *f*, with cycle safety.

        Uses BFS with a visited set.  The starting file *f* is never
        included in the result.
        """
        visited: Set[str] = {f}
        queue: deque[str] = deque(self._includes.get(f, set()))
        result: Set[str] = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            result.add(current)
            for included in self._includes.get(current, set()):
                if included not in visited:
                    queue.append(included)

        return result
