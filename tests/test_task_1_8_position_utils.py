"""Tests for Task 1.8: Position Utilities."""

import pytest
from lsprotocol.types import Position, Range

# ---------------------------------------------------------------------------
# Mock for Ivy location objects (avoids importing Ivy itself)
# ---------------------------------------------------------------------------


class MockLocation(list):
    """Mimics Ivy's location tuple: [filename, line_number]."""

    @property
    def filename(self):
        return self[0]

    @property
    def line(self):
        return self[1]


# ===========================================================================
# make_range
# ===========================================================================


class TestMakeRange:
    """Tests for make_range convenience constructor."""

    def test_basic_range(self):
        from ivy_lsp.utils.position_utils import make_range

        r = make_range(0, 0, 0, 10)
        assert r.start.line == 0
        assert r.start.character == 0
        assert r.end.line == 0
        assert r.end.character == 10

    def test_multiline_range(self):
        from ivy_lsp.utils.position_utils import make_range

        r = make_range(1, 5, 3, 12)
        assert r.start.line == 1
        assert r.start.character == 5
        assert r.end.line == 3
        assert r.end.character == 12

    def test_zero_length_range(self):
        from ivy_lsp.utils.position_utils import make_range

        r = make_range(2, 7, 2, 7)
        assert r.start.line == r.end.line == 2
        assert r.start.character == r.end.character == 7

    def test_returns_range_type(self):
        from ivy_lsp.utils.position_utils import make_range

        r = make_range(0, 0, 0, 0)
        assert isinstance(r, Range)


# ===========================================================================
# ivy_location_to_range
# ===========================================================================


class TestIvyLocationToRange:
    """Tests for ivy_location_to_range: Ivy 1-based line -> LSP 0-based Range."""

    def test_normal_line1(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        loc = MockLocation(["test.ivy", 1])
        source = "type cid\n"
        r = ivy_location_to_range(loc, source)
        assert r.start.line == 0
        assert r.start.character == 0
        assert r.end.line == 0
        assert r.end.character == len("type cid")

    def test_line3_multiline(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        loc = MockLocation(["test.ivy", 3])
        source = "#lang ivy1.7\n\ntype cid\n"
        r = ivy_location_to_range(loc, source)
        # Line 3 (1-based) -> line 2 (0-based), content is "type cid"
        assert r.start.line == 2
        assert r.start.character == 0
        assert r.end.line == 2
        assert r.end.character == len("type cid")

    def test_none_location(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        r = ivy_location_to_range(None, "some source")
        assert r.start.line == 0
        assert r.start.character == 0
        assert r.end.line == 0
        assert r.end.character == 0

    def test_line_zero_defensive(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        loc = MockLocation(["test.ivy", 0])
        r = ivy_location_to_range(loc, "type cid\n")
        assert r.start.line == 0
        assert r.start.character == 0
        assert r.end.line == 0
        assert r.end.character == 0

    def test_line_beyond_source(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        loc = MockLocation(["test.ivy", 100])
        source = "line one\nline two\n"
        r = ivy_location_to_range(loc, source)
        # Should clamp to last line
        lines = source.split("\n")
        # Last non-empty line index
        last_idx = len(lines) - 1
        # The source ends with \n, so last element is ""
        # Clamped to max(0, len(lines)-1)
        assert r.start.line == last_idx
        assert r.start.character == 0

    def test_empty_source(self):
        from ivy_lsp.utils.position_utils import ivy_location_to_range

        loc = MockLocation(["test.ivy", 1])
        r = ivy_location_to_range(loc, "")
        assert r.start.line == 0
        assert r.start.character == 0
        assert r.end.line == 0
        assert r.end.character == 0


# ===========================================================================
# offset_to_position
# ===========================================================================


class TestOffsetToPosition:
    """Tests for offset_to_position: byte offset -> Position(line, character)."""

    def test_offset_zero(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        p = offset_to_position(0, "hello\nworld")
        assert p.line == 0
        assert p.character == 0

    def test_offset_middle_line2(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        source = "hello\nworld"
        # offset 8 -> 'r' in "world" (line 1, char 2)
        p = offset_to_position(8, source)
        assert p.line == 1
        assert p.character == 2

    def test_negative_offset(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        p = offset_to_position(-5, "hello\nworld")
        assert p.line == 0
        assert p.character == 0

    def test_offset_beyond_end(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        source = "ab\ncd"
        p = offset_to_position(1000, source)
        # Should clamp to end of source
        assert p.line == 1
        assert p.character == 2

    def test_empty_source(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        p = offset_to_position(5, "")
        assert p.line == 0
        assert p.character == 0

    def test_returns_position_type(self):
        from ivy_lsp.utils.position_utils import offset_to_position

        p = offset_to_position(0, "hello")
        assert isinstance(p, Position)


# ===========================================================================
# word_at_position
# ===========================================================================


class TestWordAtPosition:
    """Tests for word_at_position: extract word under cursor."""

    def test_simple_word(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["type cid"]
        pos = Position(line=0, character=5)  # cursor on 'c' of "cid"
        assert word_at_position(lines, pos) == "cid"

    def test_dot_qualified_name(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["    frame.ack.largest_acked"]
        pos = Position(line=0, character=10)  # cursor on 'a' of "ack"
        result = word_at_position(lines, pos)
        assert result == "frame.ack.largest_acked"

    def test_cursor_on_dot(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["frame.ack"]
        pos = Position(line=0, character=5)  # cursor on '.'
        result = word_at_position(lines, pos)
        assert result == "frame.ack"

    def test_underscores_and_digits(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["pkt_num_123"]
        pos = Position(line=0, character=4)  # cursor on 'n' of "num"
        assert word_at_position(lines, pos) == "pkt_num_123"

    def test_out_of_range_line(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["hello"]
        pos = Position(line=5, character=0)
        assert word_at_position(lines, pos) == ""

    def test_out_of_range_column(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["hi"]
        pos = Position(line=0, character=100)
        assert word_at_position(lines, pos) == ""

    def test_empty_lines(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = []
        pos = Position(line=0, character=0)
        assert word_at_position(lines, pos) == ""

    def test_cursor_at_word_start(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["type cid"]
        pos = Position(line=0, character=0)  # cursor on 't' of "type"
        assert word_at_position(lines, pos) == "type"

    def test_cursor_at_word_end(self):
        from ivy_lsp.utils.position_utils import word_at_position

        lines = ["type cid"]
        pos = Position(line=0, character=3)  # cursor on 'e' of "type"
        assert word_at_position(lines, pos) == "type"
