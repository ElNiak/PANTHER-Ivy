"""Lexer-based fallback symbol scanner for Ivy source files.

When the full Ivy parser fails (e.g., on incomplete or broken files), this
module extracts symbol declarations using only PLY lexer tokens.  The result
is a degraded but useful ``List[IvySymbol]`` with correct nesting for
``object`` and ``module`` scopes.
"""

from __future__ import annotations

import copy
import logging
from typing import List, Optional, Tuple

from lsprotocol.types import SymbolKind

from ivy_lsp.parsing.symbols import IvySymbol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword-to-SymbolKind mapping
# ---------------------------------------------------------------------------
# Keys are the PLY token *type* strings emitted by ivy.ivy_lexer.
# Note: ``instance`` maps to ``INSTANTIATE`` in the Ivy lexer grammar.

_KEYWORD_TO_KIND = {
    "TYPE": SymbolKind.Class,
    "OBJECT": SymbolKind.Module,
    "ACTION": SymbolKind.Function,
    "RELATION": SymbolKind.Function,
    "MODULE": SymbolKind.Module,
    "ISOLATE": SymbolKind.Namespace,
    "PROPERTY": SymbolKind.Property,
    "AXIOM": SymbolKind.Property,
    "CONJECTURE": SymbolKind.Property,
    "ALIAS": SymbolKind.Variable,
    "BEFORE": SymbolKind.Function,
    "AFTER": SymbolKind.Function,
    "INSTANTIATE": SymbolKind.Variable,
}

# Keywords that open a brace-delimited scope for child symbols.
_SCOPE_OPENERS = {"OBJECT", "MODULE"}

# Keywords that can use ``[label]`` syntax (e.g. ``property [p1] ...``).
_LABEL_KEYWORDS = {"PROPERTY", "AXIOM", "CONJECTURE"}

# Keywords whose name is a dotted path (e.g. ``before foo.step``).
_DOTTED_NAME_KEYWORDS = {"BEFORE", "AFTER"}


# ---------------------------------------------------------------------------
# Tokenizer helper
# ---------------------------------------------------------------------------


def _tokenize(source: str) -> list:
    """Tokenize *source* using the Ivy PLY lexer.

    Returns a (possibly partial) list of tokens.  If the lexer raises on
    an illegal character the tokens collected so far are returned -- this
    provides best-effort results for broken files.
    """
    from ivy.ivy_lexer import LexerVersion
    from ivy.ivy_lexer import lexer as ivy_lexer

    lex_copy = copy.copy(ivy_lexer)
    tokens: list = []
    with LexerVersion([1, 7]):
        lex_copy.input(source)
        while True:
            try:
                tok = lex_copy.token()
            except Exception:
                # The Ivy lexer raises IvyError on illegal characters.
                # Return whatever we collected so far.
                break
            if tok is None:
                break
            tokens.append(tok)
    return tokens


# ---------------------------------------------------------------------------
# Name extraction helpers
# ---------------------------------------------------------------------------

# Token types that represent valid "name" tokens (identifiers / reserved
# words that may appear as part of a dotted name after BEFORE/AFTER).
_NAME_TOKEN_TYPES = frozenset({"PRESYMBOL"})


def _is_name_token(tok) -> bool:
    """Return True if *tok* can serve as a symbol name component.

    PRESYMBOL is the standard identifier token.  But inside ``before``/
    ``after`` dotted paths, reserved words like ``init``, ``step`` etc.
    can appear as name parts -- we accept any token whose ``.value`` is
    alphanumeric-ish for that purpose.
    """
    if tok.type == "PRESYMBOL":
        return True
    # Reserved words that got their own token type but are really
    # identifiers in a dotted-name context.
    if tok.value and tok.value.isidentifier():
        return True
    return False


def _read_dotted_name(tokens: list, start: int) -> Tuple[Optional[str], int]:
    """Read a potentially dot-separated name starting at *start*.

    Returns ``(name_string, next_index)`` or ``(None, start)`` if no name
    token is found at the start position.
    """
    if start >= len(tokens) or not _is_name_token(tokens[start]):
        return None, start

    parts = [tokens[start].value]
    i = start + 1
    while i + 1 < len(tokens) and tokens[i].type == "DOT":
        next_tok = tokens[i + 1]
        if _is_name_token(next_tok):
            parts.append(next_tok.value)
            i += 2
        else:
            break

    return ".".join(parts), i


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fallback_scan(
    source: str, filename: str = "<string>"
) -> List[IvySymbol]:
    """Extract symbol declarations from Ivy source using lexer tokens only.

    Parameters
    ----------
    source:
        Raw Ivy source text.
    filename:
        File path to attach to every returned symbol.

    Returns
    -------
    List of ``IvySymbol`` instances with correct parent/child nesting for
    ``object`` and ``module`` scopes.  If the source is empty or the lexer
    fails completely, an empty list is returned.
    """
    if not source or not source.strip():
        return []

    try:
        tokens = _tokenize(source)
    except Exception:
        logger.debug("Lexer failed entirely for %s, returning empty", filename)
        return []

    if not tokens:
        return []

    lines = source.split("\n")
    symbols: List[IvySymbol] = []
    # Stack of (IvySymbol, brace_depth_when_pushed) for nested scopes.
    scope_stack: List[Tuple[IvySymbol, int]] = []
    brace_depth = 0
    i = 0

    while i < len(tokens):
        tok = tokens[i]

        # -- Track brace depth ------------------------------------------
        if tok.type == "LCB":
            brace_depth += 1
            i += 1
            continue

        if tok.type == "RCB":
            brace_depth -= 1
            # Pop any scopes that have closed.
            while scope_stack and scope_stack[-1][1] >= brace_depth:
                scope_stack.pop()
            i += 1
            continue

        # -- INCLUDE (special: not in _KEYWORD_TO_KIND) -----------------
        if tok.type == "INCLUDE":
            if i + 1 < len(tokens) and _is_name_token(tokens[i + 1]):
                name = tokens[i + 1].value
                line_idx = max(0, tok.lineno - 1)
                line_len = len(lines[line_idx]) if line_idx < len(lines) else 0
                sym = IvySymbol(
                    name=name,
                    kind=SymbolKind.File,
                    range=(line_idx, 0, line_idx, line_len),
                    file_path=filename,
                    detail="include",
                )
                symbols.append(sym)
                i += 2
            else:
                i += 1
            continue

        # -- Declaration keywords ---------------------------------------
        if tok.type in _KEYWORD_TO_KIND:
            kind = _KEYWORD_TO_KIND[tok.type]
            keyword_str = tok.type.lower()
            line_no = tok.lineno  # 1-based from PLY
            name: Optional[str] = None

            if tok.type in _DOTTED_NAME_KEYWORDS:
                # BEFORE / AFTER: read dotted name like ``foo.step``
                name, i = _read_dotted_name(tokens, i + 1)

            elif tok.type in _LABEL_KEYWORDS:
                # PROPERTY / AXIOM / CONJECTURE: may have ``[label]`` or
                # plain ``PRESYMBOL`` name.
                if (
                    i + 3 < len(tokens)
                    and tokens[i + 1].type == "LB"
                    and _is_name_token(tokens[i + 2])
                    and tokens[i + 3].type == "RB"
                ):
                    name = tokens[i + 2].value
                    i += 4
                elif i + 1 < len(tokens) and _is_name_token(tokens[i + 1]):
                    name = tokens[i + 1].value
                    i += 2
                else:
                    i += 1
                    continue

            elif tok.type == "TYPE":
                # TYPE can be followed by PRESYMBOL *or* THIS (inside objects,
                # ``type this`` is a common pattern where ``this`` is a
                # reserved keyword tokenised as THIS).
                if i + 1 < len(tokens) and (
                    tokens[i + 1].type == "PRESYMBOL"
                    or tokens[i + 1].type == "THIS"
                ):
                    name = tokens[i + 1].value
                    i += 2
                else:
                    i += 1
                    continue

            else:
                # Generic: keyword + PRESYMBOL
                if i + 1 < len(tokens) and _is_name_token(tokens[i + 1]):
                    name = tokens[i + 1].value
                    i += 2
                else:
                    i += 1
                    continue

            if name is None:
                continue

            # Build 0-based range spanning the keyword's line.
            line_idx = max(0, line_no - 1)
            line_len = len(lines[line_idx]) if line_idx < len(lines) else 0
            sym_range = (line_idx, 0, line_idx, line_len)

            sym = IvySymbol(
                name=name,
                kind=kind,
                range=sym_range,
                file_path=filename,
                detail=keyword_str,
            )

            # Attach to current scope parent or root list.
            if scope_stack:
                scope_stack[-1][0].children.append(sym)
            else:
                symbols.append(sym)

            # Scope-opening keywords push onto the stack.
            if tok.type in _SCOPE_OPENERS:
                scope_stack.append((sym, brace_depth))

            continue

        # -- Unhandled token: skip --------------------------------------
        i += 1

    return symbols
