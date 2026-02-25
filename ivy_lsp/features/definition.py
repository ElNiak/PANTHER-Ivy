"""Go-to-definition feature for Ivy LSP."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from lsprotocol import types as lsp

from ivy_lsp.utils.position_utils import make_range, word_at_position


def goto_definition(
    indexer,
    filepath: str,
    position: lsp.Position,
    source_lines: List[str],
) -> Optional[Union[lsp.Location, List[lsp.Location]]]:
    """Find definition(s) of the symbol at the given position.

    Extracts the word under the cursor from *source_lines* at *position*,
    then queries the *indexer* for matching symbol definitions across the
    workspace.

    If the word is a dotted name (e.g. ``frame.ack``) and no results are
    found for the full qualified name, falls back to looking up just the
    last component (``ack``).

    Args:
        indexer: A :class:`WorkspaceIndexer` instance to query.
        filepath: Absolute path to the file being edited.
        position: The cursor position (0-based line and character).
        source_lines: The source file split into lines.

    Returns:
        A single :class:`lsp.Location` when exactly one definition is found,
        a list of locations when multiple definitions match,
        or ``None`` when no definition can be located.
    """
    word = word_at_position(source_lines, position)
    if not word:
        return None

    results = indexer.lookup_symbol(word)
    if not results and "." in word:
        last = word.rsplit(".", 1)[1]
        results = indexer.lookup_symbol(last)

    if not results:
        return None

    locations = []
    for sl in results:
        uri = Path(sl.filepath).as_uri() if sl.filepath else ""
        r = make_range(*sl.range)
        locations.append(lsp.Location(uri=uri, range=r))

    if len(locations) == 1:
        return locations[0]
    return locations


def register(server) -> None:
    """Register the ``textDocument/definition`` feature handler.

    Args:
        server: The pygls ``LanguageServer`` instance to register on.
    """

    @server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
    def definition(
        params: lsp.DefinitionParams,
    ) -> Optional[Union[lsp.Location, List[lsp.Location]]]:
        """Handle textDocument/definition requests."""
        uri = params.text_document.uri
        doc = server.workspace.get_text_document(uri)
        if not hasattr(server, "_indexer") or server._indexer is None:
            return None
        lines = doc.source.split("\n") if doc.source else []
        filepath = uri.replace("file://", "")
        return goto_definition(server._indexer, filepath, params.position, lines)
