"""Position and range utilities for Ivy-to-LSP coordinate conversion.

Ivy uses 1-based line numbers; LSP uses 0-based line/character.
This module provides helpers to bridge the two coordinate systems.
"""

from __future__ import annotations

import re
from typing import Any

from lsprotocol.types import Position, Range


def make_range(sl: int, sc: int, el: int, ec: int) -> Range:
    """Create an LSP Range from four integers (all 0-based).

    Args:
        sl: Start line.
        sc: Start character.
        el: End line.
        ec: End character.

    Returns:
        An LSP Range spanning from (sl, sc) to (el, ec).
    """
    return Range(
        start=Position(line=sl, character=sc),
        end=Position(line=el, character=ec),
    )


def ivy_location_to_range(loc: Any, source: str) -> Range:
    """Convert an Ivy location object to an LSP Range spanning the full line.

    Ivy locations are objects with a ``.line`` property where ``.line``
    is **1-based**. The returned Range uses 0-based line numbers and
    spans the entire line content.

    Args:
        loc: An Ivy location (has ``.line`` attribute, 1-based) or None.
        source: The full source text of the file.

    Returns:
        An LSP Range for the corresponding line, or Range(0,0,0,0) on error.
    """
    if loc is None or not hasattr(loc, "line") or loc.line is None or loc.line <= 0:
        return make_range(0, 0, 0, 0)

    if not source:
        return make_range(0, 0, 0, 0)

    lines = source.split("\n")
    line_idx = loc.line - 1  # convert 1-based to 0-based

    if line_idx >= len(lines):
        line_idx = max(0, len(lines) - 1)

    line_len = len(lines[line_idx]) if line_idx < len(lines) else 0
    return make_range(line_idx, 0, line_idx, line_len)


def offset_to_position(offset: int, source: str) -> Position:
    """Convert a character offset within *source* to an LSP Position.

    Args:
        offset: 0-based character offset into *source*.
        source: The full source text.

    Returns:
        An LSP Position (0-based line and character).
    """
    if not source or offset <= 0:
        return Position(line=0, character=0)

    offset = min(offset, len(source))
    before = source[:offset]
    line = before.count("\n")
    last_nl = before.rfind("\n")
    char = offset - (last_nl + 1) if last_nl >= 0 else offset
    return Position(line=line, character=char)


def word_at_position(lines: list[str], position: Any) -> str:
    """Extract the word under the cursor at *position*.

    Words consist of ``[_a-zA-Z0-9.]`` characters. Leading and trailing
    dots are stripped so that dot-qualified names like ``frame.ack.field``
    are returned intact when the cursor is anywhere inside the token.

    Args:
        lines: The source split into lines.
        position: An object with ``.line`` and ``.character`` attributes
            (typically ``lsprotocol.types.Position``).

    Returns:
        The word under the cursor, or ``""`` if none.
    """
    if position.line < 0 or position.line >= len(lines):
        return ""

    line = lines[position.line]

    if position.character < 0 or position.character > len(line):
        return ""

    for m in re.finditer(r"[_a-zA-Z0-9.]+", line):
        if m.start() <= position.character <= m.end():
            return m.group().strip(".")

    return ""
