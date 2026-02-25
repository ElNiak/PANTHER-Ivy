"""Convert Ivy AST declarations to IvySymbol trees.

Walks the flat declaration list produced by ``ivy_parser.parse()`` and
emits a list of :class:`IvySymbol` instances.  Dot-prefixed names
(produced by the parser for nested ``object`` bodies) are reassembled
into a parent/child hierarchy via :func:`_reconstruct_hierarchy`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from lsprotocol.types import SymbolKind

from ivy_lsp.parsing.symbols import IvySymbol
from ivy_lsp.utils.position_utils import ivy_location_to_range

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def ast_to_symbols(
    ivy_obj: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert a parsed Ivy AST into a hierarchical list of symbols.

    Args:
        ivy_obj: The result of ``ivy_parser.parse()`` (has ``.decls``).
        filename: The originating file path.
        source: The full source text (needed for line-length lookups).

    Returns:
        A list of top-level ``IvySymbol`` instances with nested children.
    """
    if ivy_obj is None or not hasattr(ivy_obj, "decls"):
        return []

    flat_symbols: List[IvySymbol] = []
    for decl in ivy_obj.decls:
        try:
            syms = _convert_decl(decl, filename, source)
            flat_symbols.extend(syms)
        except Exception:
            logger.debug(
                "Skipping decl %s: conversion failed",
                type(decl).__name__,
                exc_info=True,
            )

    return _reconstruct_hierarchy(flat_symbols)


# ---------------------------------------------------------------------------
# Hierarchy reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_hierarchy(flat_symbols: List[IvySymbol]) -> List[IvySymbol]:
    """Nest dot-prefixed symbols under their parent.

    Given flat symbols ``["frame", "frame.ack", "frame.ack.largest_acked"]``,
    produces ``"frame"`` with child ``"ack"`` with child ``"largest_acked"``.

    When multiple symbols share the same name (e.g. an ObjectDecl and a
    TypeDecl both named ``"bit"``), the Module/Namespace symbol is
    preferred as the parent target.  The TypeDecl for inner ``type this``
    is itself nested as a child.
    """
    root_symbols: List[IvySymbol] = []
    # Maps full dotted name to the *preferred parent* symbol.
    # Module/Namespace kinds win over others because children should
    # nest under the object/module, not the inner ``type this``.
    by_name: Dict[str, IvySymbol] = {}

    _CONTAINER_KINDS = {SymbolKind.Module, SymbolKind.Namespace}

    # First pass: index symbols, preferring container kinds.
    for sym in flat_symbols:
        existing = by_name.get(sym.name)
        if existing is None:
            by_name[sym.name] = sym
        elif sym.kind in _CONTAINER_KINDS and existing.kind not in _CONTAINER_KINDS:
            # New sym is a container, existing is not — replace.
            by_name[sym.name] = sym
        # Otherwise keep the existing entry (first container wins, or
        # first non-container if no container is seen).

    # Second pass: nest children and collect roots.
    for sym in flat_symbols:
        if "." in sym.name:
            # Check whether a container symbol with the *same* full
            # dotted name already exists.  If so, this is the inner
            # ``type this`` that should be nested *inside* the existing
            # container child, not added as a sibling under the parent.
            existing_child = by_name.get(sym.name)
            if (
                existing_child is not None
                and existing_child is not sym
                and existing_child.kind in _CONTAINER_KINDS
            ):
                child_name = sym.name.rsplit(".", 1)[1]
                child = IvySymbol(
                    name=child_name,
                    kind=sym.kind,
                    range=sym.range,
                    children=sym.children,
                    detail=sym.detail,
                    file_path=sym.file_path,
                )
                existing_child.children.append(child)
                continue

            parent_name = sym.name.rsplit(".", 1)[0]
            if parent_name in by_name:
                child_name = sym.name.rsplit(".", 1)[1]
                child = IvySymbol(
                    name=child_name,
                    kind=sym.kind,
                    range=sym.range,
                    children=sym.children,
                    detail=sym.detail,
                    file_path=sym.file_path,
                )
                by_name[parent_name].children.append(child)
                # Register the child under its full name so deeper
                # nesting can find it (e.g. "frame.ack" is parent of
                # "frame.ack.largest_acked").  Only register if no
                # container already owns this name slot.
                if by_name.get(sym.name) is sym:
                    by_name[sym.name] = child
                continue

        # Non-dotted name: check if this is the canonical entry or a
        # duplicate that should be nested as a child of the container.
        if sym.name in by_name and by_name[sym.name] is not sym:
            # This is the *non-preferred* duplicate (e.g., TypeDecl
            # ``"bit"`` when an ObjectDecl ``"bit"`` is the container).
            parent = by_name[sym.name]
            if parent.kind in _CONTAINER_KINDS:
                child = IvySymbol(
                    name=sym.name,
                    kind=sym.kind,
                    range=sym.range,
                    children=sym.children,
                    detail=sym.detail,
                    file_path=sym.file_path,
                )
                parent.children.append(child)
                continue

        root_symbols.append(sym)

    return root_symbols


# ---------------------------------------------------------------------------
# Per-declaration converters
# ---------------------------------------------------------------------------


def _convert_decl(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Dispatch a single declaration to the appropriate handler.

    Returns a (possibly empty) list of flat ``IvySymbol`` instances.
    """
    import ivy.ivy_ast as ia

    if isinstance(decl, ia.ObjectDecl):
        return _convert_object(decl, filename, source)
    if isinstance(decl, ia.ActionDecl):
        return _convert_action(decl, filename, source)
    if isinstance(decl, ia.TypeDecl):
        return _convert_type(decl, filename, source)
    if isinstance(decl, ia.DefinitionDecl):
        return _convert_definition(decl, filename, source)
    if isinstance(decl, ia.PropertyDecl):
        return _convert_labeled(decl, filename, source, SymbolKind.Property)
    if isinstance(decl, ia.AxiomDecl):
        return _convert_labeled(decl, filename, source, SymbolKind.Property)
    if isinstance(decl, ia.ConjectureDecl):
        return _convert_labeled(decl, filename, source, SymbolKind.Property)
    if isinstance(decl, ia.IsolateDecl):
        return _convert_isolate(decl, filename, source)
    if isinstance(decl, ia.ModuleDecl):
        return _convert_module(decl, filename, source)
    if isinstance(decl, ia.AliasDecl):
        return _convert_alias(decl, filename, source)
    # ConstantDecl check must come after subclass checks (DestructorDecl,
    # ConstructorDecl inherit from ConstantDecl).
    if isinstance(decl, ia.DestructorDecl):
        return _convert_constant(decl, filename, source, SymbolKind.Field)
    if isinstance(decl, ia.ConstructorDecl):
        return _convert_constant(
            decl, filename, source, SymbolKind.EnumMember
        )
    if isinstance(decl, ia.ConstantDecl):
        return _convert_constant_or_relation(decl, filename, source)
    if isinstance(decl, ia.InstantiateDecl):
        return _convert_instantiate(decl, filename, source)
    # Skip: MixinDecl, VariantDecl, ExportDecl, ImportDecl
    if isinstance(
        decl,
        (ia.MixinDecl, ia.VariantDecl, ia.ExportDecl, ia.ImportDecl),
    ):
        return []

    return []


# ---------------------------------------------------------------------------
# Type declarations
# ---------------------------------------------------------------------------


def _convert_type(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert a TypeDecl to one IvySymbol (SymbolKind.Class).

    For enum types (``type sk = {a, b}``), includes a detail string
    listing the variant names.
    """
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)
    detail = _extract_enum_detail(decl)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Class,
            range=rng,
            detail=detail,
            file_path=filename,
        )
    ]


def _extract_enum_detail(decl: Any) -> Optional[str]:
    """If the TypeDecl defines an enumerated sort, return 'enum: a, b, ...'."""
    import ivy.ivy_ast as ia

    try:
        type_def = decl.args[0]  # TypeDef
        if len(type_def.args) >= 2:
            sort_part = type_def.args[1]
            if isinstance(sort_part, ia.EnumeratedSort):
                variant_names = [
                    getattr(a, "relname", str(a)) for a in sort_part.args
                ]
                return "enum: " + ", ".join(variant_names)
    except (IndexError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Object declarations
# ---------------------------------------------------------------------------


def _convert_object(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert an ObjectDecl to SymbolKind.Module."""
    defs = decl.defines()
    if not defs:
        # Fallback: try args[0].relname
        name = _name_from_args(decl)
        if name is None:
            return []
        return [
            IvySymbol(
                name=name,
                kind=SymbolKind.Module,
                range=(0, 0, 0, 0),
                file_path=filename,
            )
        ]

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Module,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Action declarations
# ---------------------------------------------------------------------------


def _convert_action(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert an ActionDecl to SymbolKind.Function with param/return detail."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)
    detail = _extract_action_detail(decl)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Function,
            range=rng,
            detail=detail,
            file_path=filename,
        )
    ]


def _extract_action_detail(decl: Any) -> Optional[str]:
    """Build a signature detail string from an ActionDecl's formal params/returns."""
    try:
        action_def = decl.args[0]  # ActionDef
        parts = []

        params = getattr(action_def, "formal_params", None)
        if params:
            param_strs = []
            for p in params:
                pname = getattr(p, "rep", str(p))
                # Strip the 'fml:' prefix
                pname = pname.replace("fml:", "")
                sort = getattr(p, "sort", None)
                if sort:
                    param_strs.append(f"{pname}:{sort}")
                else:
                    param_strs.append(pname)
            parts.append("(" + ", ".join(param_strs) + ")")

        returns = getattr(action_def, "formal_returns", None)
        if returns:
            ret_strs = []
            for r in returns:
                rname = getattr(r, "rep", str(r))
                rname = rname.replace("fml:", "")
                sort = getattr(r, "sort", None)
                if sort:
                    ret_strs.append(f"{rname}:{sort}")
                else:
                    ret_strs.append(rname)
            parts.append("returns (" + ", ".join(ret_strs) + ")")

        if parts:
            return " ".join(parts)
    except (IndexError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Constant declarations (including relations)
# ---------------------------------------------------------------------------


def _convert_constant_or_relation(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert a ConstantDecl, detecting relations (bool sort with args)."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    # Detect relation: ConstantDecl whose atom has args and bool sort
    kind = SymbolKind.Variable
    try:
        arg0 = decl.args[0]
        has_args = hasattr(arg0, "args") and len(arg0.args) > 0
        sort = getattr(arg0, "sort", None)
        if has_args and str(sort) == "bool":
            kind = SymbolKind.Function
    except (IndexError, AttributeError):
        pass

    return [
        IvySymbol(
            name=name,
            kind=kind,
            range=rng,
            file_path=filename,
        )
    ]


def _convert_constant(
    decl: Any,
    filename: str,
    source: str,
    kind: SymbolKind,
) -> List[IvySymbol]:
    """Convert a ConstantDecl subclass (Destructor, Constructor)."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=kind,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Alias declarations
# ---------------------------------------------------------------------------


def _convert_alias(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert an AliasDecl to SymbolKind.Variable."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Variable,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Isolate declarations
# ---------------------------------------------------------------------------


def _convert_isolate(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert an IsolateDecl to SymbolKind.Namespace."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Namespace,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Module declarations
# ---------------------------------------------------------------------------


def _convert_module(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert a ModuleDecl to SymbolKind.Module."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Module,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Labeled declarations (Axiom, Property, Conjecture)
# ---------------------------------------------------------------------------


def _convert_labeled(
    decl: Any,
    filename: str,
    source: str,
    kind: SymbolKind,
) -> List[IvySymbol]:
    """Convert a LabeledDecl (Axiom/Property/Conjecture) to the given kind."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=kind,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Definition declarations
# ---------------------------------------------------------------------------


def _convert_definition(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert a DefinitionDecl to SymbolKind.Function."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Function,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Instantiate declarations
# ---------------------------------------------------------------------------


def _convert_instantiate(
    decl: Any, filename: str, source: str
) -> List[IvySymbol]:
    """Convert an InstantiateDecl to SymbolKind.Variable."""
    defs = decl.defines()
    if not defs:
        return []

    name = defs[0][0]
    loc = defs[0][1] if len(defs[0]) >= 2 else None
    rng = _loc_to_tuple(loc, source)

    return [
        IvySymbol(
            name=name,
            kind=SymbolKind.Variable,
            range=rng,
            file_path=filename,
        )
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _loc_to_tuple(
    loc: Any, source: str
) -> Tuple[int, int, int, int]:
    """Convert an Ivy location to a 0-based 4-int tuple.

    Uses :func:`ivy_location_to_range` to handle the 1-based to 0-based
    conversion and line-length computation.
    """
    rng = ivy_location_to_range(loc, source)
    return (
        rng.start.line,
        rng.start.character,
        rng.end.line,
        rng.end.character,
    )


def _name_from_args(decl: Any) -> Optional[str]:
    """Try to extract a name from ``decl.args[0].relname``."""
    try:
        return decl.args[0].relname
    except (IndexError, AttributeError):
        return None
