"""textDocument/documentSymbol feature handler.

Converts ``IvySymbol`` trees to LSP ``DocumentSymbol`` trees and registers
the ``textDocument/documentSymbol`` request handler on the server.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from lsprotocol import types as lsp

from ivy_lsp.parsing.symbols import IvySymbol
from ivy_lsp.utils.position_utils import make_range

logger = logging.getLogger(__name__)


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


def compute_document_symbols(
    parser,
    indexer,
    source: str,
    filepath: str,
) -> List[lsp.DocumentSymbol]:
    """Parse source and return LSP DocumentSymbol list.

    Strategy:
    1. If parser available: parse source, convert AST to symbols
    2. If parse fails: fallback scanner
    3. If no parser but indexer available: use cached indexed symbols
    4. If neither: return empty list
    """
    symbols: List[IvySymbol] = []

    if parser is not None and source:
        from ivy_lsp.parsing.ast_to_symbols import ast_to_symbols
        from ivy_lsp.parsing.fallback_scanner import fallback_scan

        result = parser.parse(source, filepath)
        if result.success and result.ast is not None:
            symbols = ast_to_symbols(result.ast, filepath, source)
        else:
            symbols = fallback_scan(source, filepath)
    elif indexer is not None:
        symbols = indexer.get_symbols(filepath) or []

    return get_document_symbols(symbols)


def register(server) -> None:
    """Register the ``textDocument/documentSymbol`` feature handler.

    Args:
        server: The pygls ``LanguageServer`` instance to register on.
    """

    @server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbol(
        params: lsp.DocumentSymbolParams,
    ) -> List[lsp.DocumentSymbol]:
        """Handle textDocument/documentSymbol requests."""
        uri = params.text_document.uri
        doc = server.workspace.get_text_document(uri)
        filepath = uri.replace("file://", "")
        source = doc.source or ""
        parser = getattr(server, "_parser", None)
        indexer = getattr(server, "_indexer", None)
        return compute_document_symbols(parser, indexer, source, filepath)
