"""Tests for Task 2.6: Phase 2 Integration Testing."""

import re
import sys
from pathlib import Path

import pytest
from lsprotocol.types import Position

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))

QUIC_STACK_DIR = IVY_ROOT / "protocol-testing" / "quic" / "quic_stack"


class TestPhase2FullPipeline:

    @pytest.fixture
    def quic_indexer(self):
        if not QUIC_STACK_DIR.exists():
            pytest.skip("quic_stack not found")
        from ivy_lsp.indexer.include_resolver import IncludeResolver
        from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
        from ivy_lsp.parsing.parser_session import IvyParserWrapper

        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(QUIC_STACK_DIR))
        indexer = WorkspaceIndexer(str(QUIC_STACK_DIR), parser, resolver)
        indexer.index_workspace()
        return indexer

    def test_include_resolution_all_files(self, quic_indexer):
        from ivy_lsp.indexer.include_resolver import IncludeResolver

        resolver = IncludeResolver(str(QUIC_STACK_DIR))
        unresolved = []
        for f in sorted(QUIC_STACK_DIR.glob("*.ivy")):
            source = f.read_text()
            includes = re.findall(r"^include\s+(\w+)", source, re.MULTILINE)
            for inc in includes:
                result = resolver.resolve(inc, str(f))
                if result is None:
                    unresolved.append((f.name, inc))
        for fname, inc_name in unresolved:
            assert inc_name in {
                "byte_stream",
                "tls_record",
                "tls_msg",
                "tls_protocol",
                "quic_fsm_sending",
                "quic_fsm_receiving",
                "quic_ack_frequency_extension",
                "ip",
                "ipv6",
            }, f"Unexpected unresolved: {fname} -> {inc_name}"

    def test_lookup_pkt_num(self, quic_indexer):
        results = quic_indexer.lookup_symbol("pkt_num")
        assert len(results) >= 1

    def test_symbols_in_scope_includes_transitives(self, quic_indexer):
        frame_file = str(QUIC_STACK_DIR / "quic_frame.ivy")
        scope = quic_indexer.get_symbols_in_scope(frame_file)
        assert len(scope) >= 10

    def test_goto_definition_from_frame(self, quic_indexer):
        from ivy_lsp.features.definition import goto_definition

        frame_file = QUIC_STACK_DIR / "quic_frame.ivy"
        if not frame_file.exists():
            pytest.skip("quic_frame.ivy not found")
        source = frame_file.read_text()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "cid" in line and not line.strip().startswith("#"):
                col = line.index("cid")
                pos = Position(line=i, character=col + 1)
                result = goto_definition(
                    quic_indexer, str(frame_file), pos, lines
                )
                if result is not None:
                    break

    def test_server_can_instantiate_with_features(self):
        from ivy_lsp.server import IvyLanguageServer

        server = IvyLanguageServer()
        assert server._indexer is None  # not initialized yet


class TestIndexerPackageImports:
    def test_import_from_package(self):
        from ivy_lsp.indexer import (
            CachedFile,
            FileCache,
            IncludeResolver,
            SymbolLocation,
            WorkspaceIndexer,
        )

        assert CachedFile is not None
        assert FileCache is not None
        assert IncludeResolver is not None
        assert SymbolLocation is not None
        assert WorkspaceIndexer is not None
