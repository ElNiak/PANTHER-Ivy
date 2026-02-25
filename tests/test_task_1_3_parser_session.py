"""Tests for Task 1.3: Parser State Isolation."""

import pytest


class TestParseResult:
    """Verify ParseResult dataclass."""

    def test_creation_success(self):
        from ivy_lsp.parsing.parser_session import ParseResult

        result = ParseResult(ast=object(), errors=[], success=True)
        assert result.success is True
        assert result.errors == []
        assert result.ast is not None

    def test_creation_failure(self):
        from ivy_lsp.parsing.parser_session import ParseResult

        result = ParseResult(ast=None, errors=["some error"], success=False)
        assert result.success is False
        assert len(result.errors) == 1
        assert result.ast is None

    def test_default_values(self):
        from ivy_lsp.parsing.parser_session import ParseResult

        result = ParseResult()
        assert result.ast is None
        assert result.errors == []
        assert result.success is False


class TestParserSession:
    """Verify ParserSession context manager isolates globals."""

    def test_restores_error_list(self):
        import ivy.ivy_parser as ip
        from ivy_lsp.parsing.parser_session import ParserSession

        ip.error_list = ["pre-existing"]
        with ParserSession():
            assert ip.error_list == []
        assert ip.error_list == ["pre-existing"]
        ip.error_list = []  # cleanup

    def test_restores_stack(self):
        import ivy.ivy_parser as ip
        from ivy_lsp.parsing.parser_session import ParserSession

        ip.stack = ["something"]
        with ParserSession():
            assert ip.stack == []
        assert ip.stack == ["something"]
        ip.stack = []  # cleanup

    def test_restores_special_attribute(self):
        import ivy.ivy_parser as ip
        from ivy_lsp.parsing.parser_session import ParserSession

        ip.special_attribute = "test_val"
        with ParserSession():
            assert ip.special_attribute is None
        assert ip.special_attribute == "test_val"
        ip.special_attribute = None  # cleanup

    def test_restores_parent_object(self):
        import ivy.ivy_parser as ip
        from ivy_lsp.parsing.parser_session import ParserSession

        ip.parent_object = "parent"
        with ParserSession():
            assert ip.parent_object is None
        assert ip.parent_object == "parent"
        ip.parent_object = None  # cleanup

    def test_restores_filename(self):
        import ivy.ivy_utils as iu
        from ivy_lsp.parsing.parser_session import ParserSession

        iu.filename = "/some/file.ivy"
        with ParserSession():
            assert iu.filename is None
        assert iu.filename == "/some/file.ivy"
        iu.filename = None  # cleanup

    def test_sets_version_to_1_7(self):
        import ivy.ivy_utils as iu
        from ivy_lsp.parsing.parser_session import ParserSession

        original = iu.ivy_language_version
        with ParserSession():
            assert iu.ivy_language_version == "1.7"
        assert iu.ivy_language_version == original

    def test_restores_on_exception(self):
        import ivy.ivy_parser as ip
        from ivy_lsp.parsing.parser_session import ParserSession

        ip.error_list = ["keep"]
        with pytest.raises(ValueError):
            with ParserSession():
                ip.error_list.append("inside")
                raise ValueError("test exception")
        assert ip.error_list == ["keep"]
        ip.error_list = []  # cleanup

    def test_restores_ast_globals(self):
        import ivy.ivy_ast as ia
        from ivy_lsp.parsing.parser_session import ParserSession

        ia.lf_counter = 42
        ia.reference_lineno = "ref"
        with ParserSession():
            assert ia.lf_counter == 0
            assert ia.reference_lineno is None
        assert ia.lf_counter == 42
        assert ia.reference_lineno == "ref"
        ia.lf_counter = 0  # cleanup
        ia.reference_lineno = None  # cleanup


class TestIvyParserWrapper:
    """Verify IvyParserWrapper.parse() method."""

    def test_parse_valid_source(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        result = wrapper.parse("#lang ivy1.7\n\ntype cid\n", "test.ivy")
        assert result.success is True
        assert result.ast is not None
        assert result.errors == []

    def test_parse_syntax_error_no_raise(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        result = wrapper.parse("#lang ivy1.7\n\nthis is not valid !!!\n", "bad.ivy")
        assert result.success is False
        assert result.ast is None or len(result.errors) > 0

    def test_sequential_parses_dont_interfere(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        r1 = wrapper.parse("#lang ivy1.7\n\ntype cid\n", "file1.ivy")
        r2 = wrapper.parse("#lang ivy1.7\n\ntype pkt_num\n", "file2.ivy")
        assert r1.success is True
        assert r2.success is True

    def test_error_then_valid_sequence(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        r1 = wrapper.parse("#lang ivy1.7\n\nbad bad bad !!!\n", "err.ivy")
        r2 = wrapper.parse("#lang ivy1.7\n\ntype cid\n", "good.ivy")
        assert r1.success is False
        assert r2.success is True

    def test_parse_object_declaration(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        source = """\
#lang ivy1.7

object bit = {
    type this
    individual zero:bit
    individual one:bit
}
"""
        wrapper = IvyParserWrapper()
        result = wrapper.parse(source, "objects.ivy")
        assert result.success is True
        assert result.ast is not None
        assert hasattr(result.ast, "decls")
        assert len(result.ast.decls) > 0

    def test_parse_complex_source(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        source = """\
#lang ivy1.7

type cid
type pkt_num
alias aid = cid

object bit = {
    type this
    individual zero:bit
    individual one:bit
}

object role = {
    type this = {client, server}
}

action send(src:cid, dst:cid, pkt:pkt_num) = {
    require src ~= dst;
}

relation connected(X:cid, Y:cid)
"""
        wrapper = IvyParserWrapper()
        result = wrapper.parse(source, "complex.ivy")
        assert result.success is True
        assert len(result.ast.decls) > 5

    def test_parse_quic_types(self, quic_types_source, quic_types_path):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        result = wrapper.parse(quic_types_source, str(quic_types_path))
        assert result.success is True
        assert result.ast is not None
        assert len(result.ast.decls) > 0

    def test_parse_empty_source(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        result = wrapper.parse("#lang ivy1.7\n", "empty.ivy")
        assert result.success is True

    def test_parse_preserves_filename(self):
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        wrapper = IvyParserWrapper()
        result = wrapper.parse("#lang ivy1.7\n\ntype cid\n", "myfile.ivy")
        assert result.success is True
        assert result.filename == "myfile.ivy"
