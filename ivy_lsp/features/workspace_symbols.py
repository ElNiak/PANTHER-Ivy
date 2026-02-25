"""Workspace symbol search for the Ivy Language Server.

Implements the ``workspace/symbol`` LSP request by flattening hierarchical
:class:`IvySymbol` trees into qualified-name :class:`FlatSymbol` lists,
supporting case-insensitive substring matching, and converting results to
LSP :class:`WorkspaceSymbol` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from lsprotocol import types as lsp

from ivy_lsp.parsing.symbols import IvySymbol
from ivy_lsp.utils.position_utils import make_range

MAX_RESULTS = 100


@dataclass
class FlatSymbol:
    """Flattened symbol with qualified name for workspace search.

    Attributes:
        qualified_name: Dot-separated path (e.g. ``"frame.ack.range"``).
        kind: LSP symbol kind.
        file_path: Originating file path, or ``None``.
        range: 0-based ``(start_line, start_col, end_line, end_col)`` span.
    """

    qualified_name: str
    kind: lsp.SymbolKind
    file_path: Optional[str]
    range: tuple  # (sl, sc, el, ec)


def flatten_symbols(symbols: List[IvySymbol], prefix: str = "") -> List[FlatSymbol]:
    """Recursively flatten IvySymbol trees into qualified-name list.

    Each symbol becomes a :class:`FlatSymbol` whose ``qualified_name`` is
    formed by joining the ancestor chain with dots.  Children are visited
    depth-first, so the parent always precedes its descendants in the
    returned list.

    Args:
        symbols: Top-level symbols to flatten.
        prefix: Dotted prefix to prepend (used in recursive calls).

    Returns:
        A flat list of :class:`FlatSymbol` instances.
    """
    result: List[FlatSymbol] = []
    for sym in symbols:
        qname = f"{prefix}.{sym.name}" if prefix else sym.name
        result.append(
            FlatSymbol(
                qualified_name=qname,
                kind=sym.kind,
                file_path=sym.file_path,
                range=sym.range,
            )
        )
        if sym.children:
            result.extend(flatten_symbols(sym.children, prefix=qname))
    return result


def search_symbols(flat: List[FlatSymbol], query: str) -> List[FlatSymbol]:
    """Case-insensitive substring search over flattened symbols.

    Args:
        flat: Pre-flattened symbol list to search.
        query: Substring to match against ``qualified_name``.
            An empty string matches everything.

    Returns:
        Matching symbols, capped at :data:`MAX_RESULTS`.
    """
    if not query:
        return flat[:MAX_RESULTS]
    q = query.lower()
    matches = [s for s in flat if q in s.qualified_name.lower()]
    return matches[:MAX_RESULTS]


def to_workspace_symbol(flat: FlatSymbol) -> lsp.WorkspaceSymbol:
    """Convert a FlatSymbol to an LSP WorkspaceSymbol.

    Args:
        flat: The flattened symbol to convert.

    Returns:
        An LSP WorkspaceSymbol with a ``file://`` URI and range.
    """
    uri = Path(flat.file_path).as_uri() if flat.file_path else ""
    r = make_range(*flat.range)
    return lsp.WorkspaceSymbol(
        name=flat.qualified_name,
        kind=flat.kind,
        location=lsp.Location(uri=uri, range=r),
    )


def register(server) -> None:
    """Register the ``workspace/symbol`` feature handler on *server*.

    Args:
        server: An :class:`IvyLanguageServer` instance.
    """

    @server.feature(lsp.WORKSPACE_SYMBOL)
    def workspace_symbol(
        params: lsp.WorkspaceSymbolParams,
    ) -> List[lsp.WorkspaceSymbol]:
        # Will be wired up during integration (Task 1.9)
        return []
