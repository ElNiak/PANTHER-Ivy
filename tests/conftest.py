"""Shared fixtures for Ivy LSP tests."""

import sys
from pathlib import Path

import pytest

# Insert IVY_ROOT into sys.path so `import ivy` and `import ivy_lsp` work
IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))

QUIC_STACK_DIR = IVY_ROOT / "protocol-testing" / "quic" / "quic_stack"


# ---------------------------------------------------------------------------
# Minimal Ivy source fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ivy_source_minimal():
    """Minimal valid Ivy source with a single type declaration."""
    return "#lang ivy1.7\n\ntype cid\n"


@pytest.fixture
def ivy_source_object():
    """Ivy source with a nested object containing type and individuals."""
    return """\
#lang ivy1.7

object bit = {
    type this
    individual zero:bit
    individual one:bit
    definition zero = 0
    definition one = 1
}
"""


@pytest.fixture
def ivy_source_complex():
    """Complex Ivy source with multiple declaration types."""
    return """\
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


@pytest.fixture
def ivy_source_syntax_error():
    """Ivy source with a syntax error."""
    return """\
#lang ivy1.7

type cid
object broken = {
    type this
    this is not valid ivy syntax !!!
}
type pkt_num
"""


@pytest.fixture
def ivy_source_module():
    """Ivy source with a module declaration."""
    return """\
#lang ivy1.7

module counter(t) = {
    individual val : t

    action up = {
        val := val + 1;
    }

    action down = {
        val := val - 1;
    }
}
"""


@pytest.fixture
def ivy_source_include():
    """Ivy source with an include directive."""
    return """\
#lang ivy1.7

include quic_types

type my_type
"""


@pytest.fixture
def ivy_source_isolate():
    """Ivy source with an isolate declaration."""
    return """\
#lang ivy1.7

type node

object protocol = {
    action step(n:node)
    action init(n:node)
}

isolate iso_protocol = protocol
"""


@pytest.fixture
def ivy_source_property():
    """Ivy source with property and axiom declarations."""
    return """\
#lang ivy1.7

type t

relation r(X:t, Y:t)

axiom [symmetry] r(X,Y) -> r(Y,X)
property [reflexivity] r(X,X)
"""


@pytest.fixture
def ivy_source_mixin():
    """Ivy source with before/after mixin declarations."""
    return """\
#lang ivy1.7

type t

object foo = {
    action step(x:t)
}

before foo.step {
    require x ~= x;
}

after foo.step {
    ensure true;
}
"""


@pytest.fixture
def ivy_source_instance():
    """Ivy source with an instance declaration."""
    return """\
#lang ivy1.7

module unbounded_sequence = {
    type this
    action next(x:this) returns (y:this)
}

instance idx : unbounded_sequence
"""


@pytest.fixture
def ivy_source_enum():
    """Ivy source with enum type."""
    return """\
#lang ivy1.7

type stream_kind = {unidir, bidir}
"""


@pytest.fixture
def ivy_source_variant():
    """Ivy source with variant/destructor patterns."""
    return """\
#lang ivy1.7

type packet_type = {initial, handshake, one_rtt}
"""


# ---------------------------------------------------------------------------
# Real file path fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def quic_types_path():
    """Path to the real quic_types.ivy file."""
    path = QUIC_STACK_DIR / "quic_types.ivy"
    if not path.exists():
        pytest.skip(f"quic_types.ivy not found at {path}")
    return path


@pytest.fixture
def quic_types_source(quic_types_path):
    """Source content of quic_types.ivy."""
    return quic_types_path.read_text()


@pytest.fixture
def quic_frame_path():
    """Path to the real quic_frame.ivy file."""
    path = QUIC_STACK_DIR / "quic_frame.ivy"
    if not path.exists():
        pytest.skip(f"quic_frame.ivy not found at {path}")
    return path


@pytest.fixture
def quic_frame_source(quic_frame_path):
    """Source content of quic_frame.ivy."""
    return quic_frame_path.read_text()


@pytest.fixture
def quic_stack_ivy_files():
    """List of all .ivy files in the QUIC stack directory."""
    if not QUIC_STACK_DIR.exists():
        pytest.skip(f"QUIC stack directory not found at {QUIC_STACK_DIR}")
    return sorted(QUIC_STACK_DIR.glob("*.ivy"))
