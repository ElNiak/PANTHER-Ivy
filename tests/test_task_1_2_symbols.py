"""Tests for Task 1.2: IvySymbol Dataclasses and Supporting Types (TDD)."""

from lsprotocol.types import SymbolKind


class TestIvySymbol:
    """Verify IvySymbol dataclass creation and defaults."""

    def test_creation_minimal(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="cid",
            kind=SymbolKind.Class,
            range=(2, 0, 2, 8),
        )
        assert sym.name == "cid"
        assert sym.kind == SymbolKind.Class
        assert sym.range == (2, 0, 2, 8)

    def test_default_children_empty(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="x",
            kind=SymbolKind.Variable,
            range=(0, 0, 0, 5),
        )
        assert sym.children == []

    def test_default_detail_none(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="x",
            kind=SymbolKind.Variable,
            range=(0, 0, 0, 5),
        )
        assert sym.detail is None

    def test_default_file_path_none(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="x",
            kind=SymbolKind.Variable,
            range=(0, 0, 0, 5),
        )
        assert sym.file_path is None

    def test_explicit_children(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        child = IvySymbol(
            name="zero",
            kind=SymbolKind.Variable,
            range=(3, 4, 3, 20),
        )
        parent = IvySymbol(
            name="bit",
            kind=SymbolKind.Class,
            range=(2, 0, 6, 1),
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].name == "zero"

    def test_explicit_detail(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="send",
            kind=SymbolKind.Function,
            range=(5, 0, 7, 1),
            detail="action send(src:cid, dst:cid)",
        )
        assert sym.detail == "action send(src:cid, dst:cid)"

    def test_explicit_file_path(self):
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="cid",
            kind=SymbolKind.Class,
            range=(2, 0, 2, 8),
            file_path="/opt/ivy/quic_types.ivy",
        )
        assert sym.file_path == "/opt/ivy/quic_types.ivy"

    def test_range_is_zero_based(self):
        """Range tuple represents 0-based line/col positions."""
        from ivy_lsp.parsing.symbols import IvySymbol

        sym = IvySymbol(
            name="t",
            kind=SymbolKind.Class,
            range=(0, 0, 0, 6),
        )
        start_line, start_col, end_line, end_col = sym.range
        assert start_line == 0
        assert start_col == 0
        assert end_line == 0
        assert end_col == 6

    def test_children_default_not_shared(self):
        """Each instance should get its own children list."""
        from ivy_lsp.parsing.symbols import IvySymbol

        sym1 = IvySymbol(name="a", kind=SymbolKind.Variable, range=(0, 0, 0, 1))
        sym2 = IvySymbol(name="b", kind=SymbolKind.Variable, range=(1, 0, 1, 1))
        sym1.children.append(
            IvySymbol(name="c", kind=SymbolKind.Variable, range=(2, 0, 2, 1))
        )
        assert len(sym1.children) == 1
        assert len(sym2.children) == 0


class TestIvyScope:
    """Verify IvyScope dataclass creation and navigation."""

    def test_creation_minimal(self):
        from ivy_lsp.parsing.symbols import IvyScope

        scope = IvyScope(name="global")
        assert scope.name == "global"

    def test_default_symbols_empty(self):
        from ivy_lsp.parsing.symbols import IvyScope

        scope = IvyScope(name="global")
        assert scope.symbols == {}

    def test_default_parent_none(self):
        from ivy_lsp.parsing.symbols import IvyScope

        scope = IvyScope(name="global")
        assert scope.parent is None

    def test_default_children_empty(self):
        from ivy_lsp.parsing.symbols import IvyScope

        scope = IvyScope(name="global")
        assert scope.children == []

    def test_parent_link(self):
        from ivy_lsp.parsing.symbols import IvyScope

        parent = IvyScope(name="global")
        child = IvyScope(name="bit", parent=parent)
        parent.children.append(child)

        assert child.parent is parent
        assert child.parent.name == "global"
        assert len(parent.children) == 1
        assert parent.children[0].name == "bit"

    def test_symbols_dict_holds_ivy_symbols(self):
        from ivy_lsp.parsing.symbols import IvyScope, IvySymbol

        sym = IvySymbol(
            name="cid",
            kind=SymbolKind.Class,
            range=(2, 0, 2, 8),
        )
        scope = IvyScope(name="global", symbols={"cid": sym})
        assert "cid" in scope.symbols
        assert scope.symbols["cid"].name == "cid"

    def test_nested_scopes(self):
        from ivy_lsp.parsing.symbols import IvyScope

        root = IvyScope(name="global")
        obj_scope = IvyScope(name="bit", parent=root)
        root.children.append(obj_scope)
        inner = IvyScope(name="inner", parent=obj_scope)
        obj_scope.children.append(inner)

        assert inner.parent.parent is root
        assert root.children[0].children[0] is inner

    def test_symbols_default_not_shared(self):
        """Each instance should get its own symbols dict."""
        from ivy_lsp.parsing.symbols import IvyScope, IvySymbol

        s1 = IvyScope(name="a")
        s2 = IvyScope(name="b")
        s1.symbols["x"] = IvySymbol(
            name="x", kind=SymbolKind.Variable, range=(0, 0, 0, 1)
        )
        assert "x" in s1.symbols
        assert "x" not in s2.symbols


class TestSymbolTable:
    """Verify SymbolTable add/lookup/query operations."""

    def test_empty_lookup_returns_empty(self):
        from ivy_lsp.parsing.symbols import SymbolTable

        table = SymbolTable()
        assert table.lookup("nonexistent") == []

    def test_empty_all_symbols(self):
        from ivy_lsp.parsing.symbols import SymbolTable

        table = SymbolTable()
        assert table.all_symbols() == []

    def test_add_and_lookup(self):
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym = IvySymbol(name="cid", kind=SymbolKind.Class, range=(2, 0, 2, 8))
        table.add_symbol(sym)
        result = table.lookup("cid")
        assert len(result) == 1
        assert result[0] is sym

    def test_multiple_same_name(self):
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym1 = IvySymbol(
            name="val",
            kind=SymbolKind.Variable,
            range=(3, 4, 3, 20),
            file_path="a.ivy",
        )
        sym2 = IvySymbol(
            name="val",
            kind=SymbolKind.Variable,
            range=(10, 4, 10, 20),
            file_path="b.ivy",
        )
        table.add_symbol(sym1)
        table.add_symbol(sym2)
        result = table.lookup("val")
        assert len(result) == 2

    def test_all_symbols(self):
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym1 = IvySymbol(name="cid", kind=SymbolKind.Class, range=(2, 0, 2, 8))
        sym2 = IvySymbol(name="pkt_num", kind=SymbolKind.Class, range=(3, 0, 3, 12))
        table.add_symbol(sym1)
        table.add_symbol(sym2)
        all_syms = table.all_symbols()
        assert len(all_syms) == 2
        names = {s.name for s in all_syms}
        assert names == {"cid", "pkt_num"}

    def test_symbols_in_file(self):
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym1 = IvySymbol(
            name="cid",
            kind=SymbolKind.Class,
            range=(2, 0, 2, 8),
            file_path="quic_types.ivy",
        )
        sym2 = IvySymbol(
            name="frame",
            kind=SymbolKind.Class,
            range=(5, 0, 20, 1),
            file_path="quic_frame.ivy",
        )
        sym3 = IvySymbol(
            name="pkt_num",
            kind=SymbolKind.Class,
            range=(4, 0, 4, 12),
            file_path="quic_types.ivy",
        )
        table.add_symbol(sym1)
        table.add_symbol(sym2)
        table.add_symbol(sym3)

        types_syms = table.symbols_in_file("quic_types.ivy")
        assert len(types_syms) == 2
        names = {s.name for s in types_syms}
        assert names == {"cid", "pkt_num"}

        frame_syms = table.symbols_in_file("quic_frame.ivy")
        assert len(frame_syms) == 1
        assert frame_syms[0].name == "frame"

    def test_symbols_in_file_no_match(self):
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym = IvySymbol(
            name="cid",
            kind=SymbolKind.Class,
            range=(2, 0, 2, 8),
            file_path="quic_types.ivy",
        )
        table.add_symbol(sym)
        assert table.symbols_in_file("nonexistent.ivy") == []

    def test_symbols_in_file_none_file_path(self):
        """Symbols without file_path should not match any file."""
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym = IvySymbol(name="x", kind=SymbolKind.Variable, range=(0, 0, 0, 1))
        table.add_symbol(sym)
        assert table.symbols_in_file("any.ivy") == []

    def test_lookup_qualified_single_level(self):
        """Single-name qualified lookup should behave like regular lookup."""
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        table = SymbolTable()
        sym = IvySymbol(name="cid", kind=SymbolKind.Class, range=(2, 0, 2, 8))
        table.add_symbol(sym)
        result = table.lookup_qualified("cid")
        assert len(result) == 1
        assert result[0].name == "cid"

    def test_lookup_qualified_walks_children(self):
        """Qualified lookup 'frame.ack.range' walks children hierarchy."""
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        range_sym = IvySymbol(
            name="range",
            kind=SymbolKind.Field,
            range=(15, 8, 15, 30),
        )
        ack_sym = IvySymbol(
            name="ack",
            kind=SymbolKind.Class,
            range=(10, 4, 18, 5),
            children=[range_sym],
        )
        frame_sym = IvySymbol(
            name="frame",
            kind=SymbolKind.Class,
            range=(5, 0, 25, 1),
            children=[ack_sym],
        )
        table = SymbolTable()
        table.add_symbol(frame_sym)

        result = table.lookup_qualified("frame.ack.range")
        assert len(result) == 1
        assert result[0].name == "range"
        assert result[0] is range_sym

    def test_lookup_qualified_not_found(self):
        """Qualified lookup returns [] when path does not exist."""
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        sym = IvySymbol(
            name="frame",
            kind=SymbolKind.Class,
            range=(5, 0, 25, 1),
        )
        table = SymbolTable()
        table.add_symbol(sym)

        assert table.lookup_qualified("frame.nonexistent") == []

    def test_lookup_qualified_partial_path(self):
        """Qualified lookup returns [] when only partial path matches."""
        from ivy_lsp.parsing.symbols import IvySymbol, SymbolTable

        ack_sym = IvySymbol(
            name="ack",
            kind=SymbolKind.Class,
            range=(10, 4, 18, 5),
        )
        frame_sym = IvySymbol(
            name="frame",
            kind=SymbolKind.Class,
            range=(5, 0, 25, 1),
            children=[ack_sym],
        )
        table = SymbolTable()
        table.add_symbol(frame_sym)

        assert table.lookup_qualified("frame.ack.deep.nested") == []

    def test_lookup_qualified_empty_string(self):
        """Empty qualified name returns []."""
        from ivy_lsp.parsing.symbols import SymbolTable

        table = SymbolTable()
        assert table.lookup_qualified("") == []


class TestIncludeGraph:
    """Verify IncludeGraph edge tracking and traversal."""

    def test_empty_graph_get_includes(self):
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        assert graph.get_includes("any.ivy") == set()

    def test_empty_graph_get_included_by(self):
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        assert graph.get_included_by("any.ivy") == set()

    def test_single_edge(self):
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("quic_frame.ivy", "quic_types.ivy")

        assert graph.get_includes("quic_frame.ivy") == {"quic_types.ivy"}
        assert graph.get_included_by("quic_types.ivy") == {"quic_frame.ivy"}

    def test_multiple_includes(self):
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("quic_frame.ivy", "quic_types.ivy")
        graph.add_edge("quic_frame.ivy", "quic_packet.ivy")

        includes = graph.get_includes("quic_frame.ivy")
        assert includes == {"quic_types.ivy", "quic_packet.ivy"}

    def test_included_by_reverse(self):
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "common.ivy")
        graph.add_edge("b.ivy", "common.ivy")
        graph.add_edge("c.ivy", "common.ivy")

        assert graph.get_included_by("common.ivy") == {"a.ivy", "b.ivy", "c.ivy"}

    def test_transitive_chain(self):
        """A includes B, B includes C => transitive_includes(A) = {B, C}."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")
        graph.add_edge("b.ivy", "c.ivy")

        result = graph.get_transitive_includes("a.ivy")
        assert result == {"b.ivy", "c.ivy"}

    def test_transitive_deep_chain(self):
        """A->B->C->D => transitive_includes(A) = {B, C, D}."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")
        graph.add_edge("b.ivy", "c.ivy")
        graph.add_edge("c.ivy", "d.ivy")

        result = graph.get_transitive_includes("a.ivy")
        assert result == {"b.ivy", "c.ivy", "d.ivy"}

    def test_transitive_does_not_include_self(self):
        """Transitive includes should not contain the queried file itself."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")

        result = graph.get_transitive_includes("a.ivy")
        assert "a.ivy" not in result

    def test_cycle_detection(self):
        """A->B->C->A cycle: transitive_includes terminates and returns all."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")
        graph.add_edge("b.ivy", "c.ivy")
        graph.add_edge("c.ivy", "a.ivy")

        result = graph.get_transitive_includes("a.ivy")
        assert result == {"b.ivy", "c.ivy"}

    def test_cycle_detection_self_loop(self):
        """Self-loop: A->A should not cause infinite loop."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "a.ivy")

        result = graph.get_transitive_includes("a.ivy")
        # Self is excluded from transitive includes
        assert result == set()

    def test_transitive_diamond(self):
        """Diamond: A->B, A->C, B->D, C->D => transitive(A) = {B,C,D}."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")
        graph.add_edge("a.ivy", "c.ivy")
        graph.add_edge("b.ivy", "d.ivy")
        graph.add_edge("c.ivy", "d.ivy")

        result = graph.get_transitive_includes("a.ivy")
        assert result == {"b.ivy", "c.ivy", "d.ivy"}

    def test_transitive_no_includes(self):
        """File with no includes has empty transitive set."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")

        result = graph.get_transitive_includes("b.ivy")
        assert result == set()

    def test_duplicate_edges_idempotent(self):
        """Adding the same edge twice does not create duplicates."""
        from ivy_lsp.parsing.symbols import IncludeGraph

        graph = IncludeGraph()
        graph.add_edge("a.ivy", "b.ivy")
        graph.add_edge("a.ivy", "b.ivy")

        assert graph.get_includes("a.ivy") == {"b.ivy"}
        assert graph.get_included_by("b.ivy") == {"a.ivy"}
