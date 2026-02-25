"""Find references feature for Ivy LSP."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from lsprotocol import types as lsp

from ivy_lsp.utils.position_utils import make_range, word_at_position


def find_references(
    indexer,
    filepath: str,
    position: lsp.Position,
    source_lines: List[str],
    include_declaration: bool = True,
) -> List[lsp.Location]:
    """Find all references to the symbol at the given position.

    Extracts the word under the cursor, then scans every ``.ivy`` file in the
    workspace for whole-word matches, returning an LSP ``Location`` for each.

    Args:
        indexer: The :class:`WorkspaceIndexer` instance providing access to
            the workspace file list via ``indexer._resolver.find_all_ivy_files()``.
        filepath: Absolute path of the document containing the cursor.
        position: The cursor position (0-based line and character).
        source_lines: The source of the current document split into lines.
        include_declaration: Whether to include the declaration site itself
            among the returned locations.  Currently unused (all matches
            are returned regardless), reserved for future filtering.

    Returns:
        A list of :class:`lsp.Location` objects, one per match found.
        Returns an empty list when the word under the cursor is empty
        or no matches are found.
    """
    word = word_at_position(source_lines, position)
    if not word:
        return []

    # For dotted names like ``frame.ack``, match only the last component.
    name = word.rsplit(".", 1)[-1] if "." in word else word
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")

    all_files = indexer._resolver.find_all_ivy_files()

    locations: List[lsp.Location] = []
    for fpath in all_files:
        try:
            with open(fpath) as f:
                file_source = f.read()
        except OSError:
            continue
        file_lines = file_source.split("\n")
        for line_no, line in enumerate(file_lines):
            for match in pattern.finditer(line):
                uri = Path(fpath).as_uri()
                r = make_range(line_no, match.start(), line_no, match.end())
                locations.append(lsp.Location(uri=uri, range=r))

    return locations


def register(server) -> None:
    """Register the ``textDocument/references`` feature handler.

    Args:
        server: The pygls ``LanguageServer`` instance to register on.
    """

    @server.feature(lsp.TEXT_DOCUMENT_REFERENCES)
    def references(
        params: lsp.ReferenceParams,
    ) -> Optional[List[lsp.Location]]:
        """Handle textDocument/references requests."""
        uri = params.text_document.uri
        doc = server.workspace.get_text_document(uri)
        if not hasattr(server, "_indexer") or server._indexer is None:
            return None
        lines = doc.source.split("\n") if doc.source else []
        filepath = uri.replace("file://", "")
        include_decl = (
            params.context.include_declaration if params.context else True
        )
        return find_references(
            server._indexer,
            filepath,
            params.position,
            lines,
            include_declaration=include_decl,
        )
