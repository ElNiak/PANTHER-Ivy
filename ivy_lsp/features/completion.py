"""Completion feature for Ivy LSP."""

from __future__ import annotations

import enum
import logging
import os
import re
from typing import List, Optional, Set, Tuple

from lsprotocol import types as lsp
from lsprotocol.types import SymbolKind

from ivy_lsp.parsing.symbols import IvySymbol

logger = logging.getLogger(__name__)

MAX_COMPLETIONS = 300

# Load keywords from ivy lexer with frozen fallback.
try:
    from ivy.ivy_lexer import all_reserved

    IVY_KEYWORDS: List[str] = sorted(all_reserved.keys())
except ImportError:
    IVY_KEYWORDS = [
        "action",
        "after",
        "alias",
        "around",
        "assert",
        "assume",
        "attribute",
        "axiom",
        "before",
        "call",
        "class",
        "common",
        "concept",
        "conjecture",
        "constructor",
        "debug",
        "decreases",
        "definition",
        "delegate",
        "derived",
        "destructor",
        "else",
        "ensure",
        "ensures",
        "entry",
        "eventually",
        "execute",
        "exists",
        "explicit",
        "export",
        "extract",
        "false",
        "field",
        "finite",
        "for",
        "forall",
        "forget",
        "fresh",
        "from",
        "function",
        "ghost",
        "global",
        "globally",
        "if",
        "implement",
        "implementation",
        "import",
        "in",
        "include",
        "individual",
        "init",
        "instance",
        "instantiate",
        "interpret",
        "invariant",
        "isa",
        "isolate",
        "let",
        "local",
        "macro",
        "match",
        "maximizing",
        "method",
        "minimizing",
        "mixin",
        "mixord",
        "module",
        "named",
        "null",
        "object",
        "of",
        "old",
        "parameter",
        "params",
        "private",
        "process",
        "progress",
        "proof",
        "property",
        "relation",
        "rely",
        "require",
        "requires",
        "returns",
        "scenario",
        "schema",
        "set",
        "some",
        "specification",
        "state",
        "struct",
        "subclass",
        "tactic",
        "temporal",
        "template",
        "theorem",
        "this",
        "thunk",
        "trigger",
        "true",
        "trusted",
        "type",
        "unfold",
        "unprovable",
        "update",
        "using",
        "var",
        "variant",
        "while",
        "with",
    ]

IVY_KEYWORDS_SET: Set[str] = set(IVY_KEYWORDS)


class CompletionContext(enum.Enum):
    DOT_ACCESS = "dot_access"
    INCLUDE = "include"
    AFTER_KEYWORD = "after_keyword"
    GENERAL = "general"


_KIND_TO_COMPLETION = {
    SymbolKind.Class: lsp.CompletionItemKind.Class,
    SymbolKind.Function: lsp.CompletionItemKind.Function,
    SymbolKind.Module: lsp.CompletionItemKind.Module,
    SymbolKind.Variable: lsp.CompletionItemKind.Variable,
    SymbolKind.Property: lsp.CompletionItemKind.Property,
    SymbolKind.Namespace: lsp.CompletionItemKind.Module,
    SymbolKind.Field: lsp.CompletionItemKind.Field,
    SymbolKind.EnumMember: lsp.CompletionItemKind.EnumMember,
}


def _symbol_kind_to_completion_kind(kind: SymbolKind) -> lsp.CompletionItemKind:
    return _KIND_TO_COMPLETION.get(kind, lsp.CompletionItemKind.Text)


def detect_context(
    line_text: str,
    character: int,
) -> Tuple[CompletionContext, str, str]:
    """Detect completion context from text before cursor.

    Returns (context_type, prefix, scope_name).
    """
    text_before = line_text[:character]

    # 1. Dot access: "identifier." or "identifier.partial"
    dot_match = re.search(r"(\w+(?:\.\w+)*)\.(\w*)$", text_before)
    if dot_match:
        return CompletionContext.DOT_ACCESS, dot_match.group(2), dot_match.group(1)

    # 2. Include
    include_match = re.match(r"^\s*include\s+(\w*)$", text_before)
    if include_match:
        return CompletionContext.INCLUDE, include_match.group(1), ""

    # 3. General (extract prefix)
    prefix_match = re.search(r"(\w*)$", text_before)
    prefix = prefix_match.group(1) if prefix_match else ""
    return CompletionContext.GENERAL, prefix, ""


def get_completions(
    indexer,
    filepath: str,
    position: lsp.Position,
    source_lines: List[str],
) -> List[lsp.CompletionItem]:
    """Compute completion items for the given position."""
    if position.line < 0 or position.line >= len(source_lines):
        return []

    line_text = source_lines[position.line]
    ctx, prefix, scope_name = detect_context(line_text, position.character)

    if ctx == CompletionContext.DOT_ACCESS:
        return _dot_access_completions(indexer, filepath, scope_name, prefix)
    elif ctx == CompletionContext.INCLUDE:
        return _include_completions(indexer, filepath, prefix)
    else:
        return _general_completions(indexer, filepath, prefix)


def _dot_access_completions(
    indexer, filepath: str, scope_name: str, prefix: str
) -> List[lsp.CompletionItem]:
    """Complete children of a named scope (after '.')."""
    symbols = indexer._symbol_table.lookup_qualified(scope_name)
    if not symbols:
        symbols = indexer._symbol_table.lookup(scope_name)
    if not symbols:
        return []

    items: List[lsp.CompletionItem] = []
    seen: Set[str] = set()
    for parent in symbols:
        for child in parent.children:
            if prefix and not child.name.lower().startswith(prefix.lower()):
                continue
            if child.name in seen:
                continue
            seen.add(child.name)
            items.append(
                lsp.CompletionItem(
                    label=child.name,
                    kind=_symbol_kind_to_completion_kind(child.kind),
                    detail=child.detail,
                )
            )
    return items[:MAX_COMPLETIONS]


def _include_completions(
    indexer, filepath: str, prefix: str
) -> List[lsp.CompletionItem]:
    """Complete include filenames."""
    abs_filepath = os.path.abspath(filepath)
    all_files = indexer._resolver.find_all_ivy_files()
    items: List[lsp.CompletionItem] = []
    seen: Set[str] = set()
    for fpath in all_files:
        if os.path.abspath(fpath) == abs_filepath:
            continue
        name = os.path.splitext(os.path.basename(fpath))[0]
        if name in seen:
            continue
        if prefix and not name.lower().startswith(prefix.lower()):
            continue
        seen.add(name)
        items.append(
            lsp.CompletionItem(
                label=name,
                kind=lsp.CompletionItemKind.File,
            )
        )
    return items[:MAX_COMPLETIONS]


def _general_completions(
    indexer, filepath: str, prefix: str
) -> List[lsp.CompletionItem]:
    """Return all symbols in scope + keywords, filtered by prefix."""
    items: List[lsp.CompletionItem] = []
    seen: Set[str] = set()
    lower_prefix = prefix.lower()

    # Symbols in scope
    scope_symbols = indexer.get_symbols_in_scope(filepath)
    for sym in scope_symbols:
        _add_symbol_completions(sym, lower_prefix, seen, items)

    # Keywords
    for kw in IVY_KEYWORDS:
        if kw in seen:
            continue
        if lower_prefix and not kw.startswith(lower_prefix):
            continue
        seen.add(kw)
        items.append(
            lsp.CompletionItem(
                label=kw,
                kind=lsp.CompletionItemKind.Keyword,
            )
        )

    return items[:MAX_COMPLETIONS]


def _add_symbol_completions(
    sym: IvySymbol,
    lower_prefix: str,
    seen: Set[str],
    items: List[lsp.CompletionItem],
) -> None:
    """Add a symbol and its children to the completion list."""
    if sym.name not in seen:
        if not lower_prefix or sym.name.lower().startswith(lower_prefix):
            seen.add(sym.name)
            items.append(
                lsp.CompletionItem(
                    label=sym.name,
                    kind=_symbol_kind_to_completion_kind(sym.kind),
                    detail=sym.detail,
                )
            )
    for child in sym.children:
        _add_symbol_completions(child, lower_prefix, seen, items)


def register(server) -> None:
    """Register the textDocument/completion feature handler."""

    @server.feature(
        lsp.TEXT_DOCUMENT_COMPLETION,
        lsp.CompletionOptions(trigger_characters=[".", " "]),
    )
    def completion(
        params: lsp.CompletionParams,
    ) -> Optional[List[lsp.CompletionItem]]:
        uri = params.text_document.uri
        doc = server.workspace.get_text_document(uri)
        if not hasattr(server, "_indexer") or server._indexer is None:
            return None
        lines = doc.source.split("\n") if doc.source else []
        filepath = uri.replace("file://", "")
        return get_completions(server._indexer, filepath, params.position, lines)
