"""textDocument/documentSymbol feature handler.

Converts ``IvySymbol`` trees to LSP ``DocumentSymbol`` trees and registers
the ``textDocument/documentSymbol`` request handler on the server.
"""

from __future__ import annotations

from typing import List, Optional

from lsprotocol import types as lsp

from ivy_lsp.parsing.symbols import IvySymbol
from ivy_lsp.utils.position_utils import make_range


def ivy_symbol_to_document_symbol(sym: IvySymbol) -> lsp.DocumentSymbol:
    """Convert an IvySymbol to an LSP DocumentSymbol.

    Children are converted recursively.  An empty ``children`` list on the
    input symbol produces ``children=None`` on the output (the LSP spec
    treats ``None`` and ``[]`` differently in some clients).

    Args:
        sym: The Ivy symbol to convert.

    Returns:
        An LSP DocumentSymbol with matching name, kind, range, detail,
        and recursively-converted children.
    """
    r = make_range(*sym.range)
    children: Optional[List[lsp.DocumentSymbol]] = None
    if sym.children:
        children = [ivy_symbol_to_document_symbol(c) for c in sym.children]
    return lsp.DocumentSymbol(
        name=sym.name,
        kind=sym.kind,
        range=r,
        selection_range=r,
        detail=sym.detail,
        children=children,
    )


def ivy_symbols_to_document_symbols(
    symbols: List[IvySymbol],
) -> List[lsp.DocumentSymbol]:
    """Convert a list of IvySymbols to LSP DocumentSymbols.

    Args:
        symbols: The Ivy symbols to convert.

    Returns:
        A list of LSP DocumentSymbols in the same order.
    """
    return [ivy_symbol_to_document_symbol(s) for s in symbols]


def get_document_symbols(
    symbols: Optional[List[IvySymbol]],
) -> List[lsp.DocumentSymbol]:
    """Null-safe wrapper for document symbol conversion.

    Args:
        symbols: An optional list of Ivy symbols.  ``None`` and ``[]``
            both produce an empty result.

    Returns:
        A (possibly empty) list of LSP DocumentSymbols.
    """
    if not symbols:
        return []
    return ivy_symbols_to_document_symbols(symbols)


def register(server: lsp.LanguageServer) -> None:  # type: ignore[name-defined]
    """Register the ``textDocument/documentSymbol`` feature handler.

    Args:
        server: The pygls ``LanguageServer`` instance to register on.
    """

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(
        params: lsp.DocumentSymbolParams,
    ) -> List[lsp.DocumentSymbol]:
        """Handle textDocument/documentSymbol requests.

        In a full implementation this will call ``server.parse_document()``
        and convert the resulting symbols.  During initial development it
        returns an empty list.
        """
        return []
