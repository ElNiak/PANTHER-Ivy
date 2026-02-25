"""Tests for Task 4.4: Full corpus testing across all protocol-testing/ .ivy files.

Validates parse success rate, fallback rate, performance, and include resolution
across the entire 667+ file corpus.
"""

import logging
import re
import sys
import time
from pathlib import Path

import pytest

IVY_ROOT = Path(__file__).resolve().parent.parent
if str(IVY_ROOT) not in sys.path:
    sys.path.insert(0, str(IVY_ROOT))

from ivy_lsp.features.document_symbols import compute_document_symbols
from ivy_lsp.indexer.include_resolver import IncludeResolver
from ivy_lsp.indexer.workspace_indexer import WorkspaceIndexer
from ivy_lsp.parsing.ast_to_symbols import ast_to_symbols
from ivy_lsp.parsing.fallback_scanner import fallback_scan
from ivy_lsp.parsing.parser_session import IvyParserWrapper

logger = logging.getLogger(__name__)

PROTOCOL_TESTING_DIR = IVY_ROOT / "protocol-testing"
DOC_EXAMPLES_DIR = IVY_ROOT / "doc" / "examples"


def _collect_corpus_files():
    """Collect all .ivy files from corpus directories."""
    files = []
    for d in [PROTOCOL_TESTING_DIR, DOC_EXAMPLES_DIR]:
        if d.exists():
            files.extend(sorted(d.rglob("*.ivy")))
    return files


@pytest.fixture(scope="module")
def corpus_files():
    files = _collect_corpus_files()
    if not files:
        pytest.skip("No corpus .ivy files found")
    return files


@pytest.fixture(scope="module")
def parser():
    return IvyParserWrapper()


@pytest.mark.slow
class TestFullCorpusParsing:
    """Parse all .ivy files in protocol-testing/ and doc/examples/."""

    def test_no_crashes(self, corpus_files, parser):
        """No .ivy file should cause an unhandled exception."""
        crashes = []
        for f in corpus_files:
            try:
                source = f.read_text(errors="replace")
                result = parser.parse(source, str(f))
                if result.success and result.ast is not None:
                    ast_to_symbols(result.ast, str(f), source)
                else:
                    fallback_scan(source, str(f))
            except Exception as exc:
                crashes.append((f.name, str(exc)))
        assert len(crashes) == 0, f"Crashes during corpus parsing: {crashes[:10]}"

    def test_parse_success_rate_above_threshold(self, corpus_files, parser):
        """Parse success rate should not regress below baseline.

        The full corpus includes advanced Ivy constructs (interprets, after
        init, complex parameterised types) that the PLY grammar doesn't yet
        cover.  Baseline is ~26% full-parse; fallback scanner covers the rest.
        Threshold set at 20% to catch regressions without false failures.
        """
        successes = 0
        total = len(corpus_files)
        for f in corpus_files:
            source = f.read_text(errors="replace")
            result = parser.parse(source, str(f))
            if result.success:
                successes += 1
        rate = successes / total if total > 0 else 0
        logger.info("Parse success rate: %d/%d = %.1f%%", successes, total, rate * 100)
        assert rate >= 0.20, f"Parse success rate {rate:.1%} < 20% (regression)"

    def test_fallback_produces_symbols_for_failures(self, corpus_files, parser):
        """Every file that fails full parse should produce symbols via fallback."""
        no_symbols = []
        for f in corpus_files:
            source = f.read_text(errors="replace")
            result = parser.parse(source, str(f))
            if not result.success:
                symbols = fallback_scan(source, str(f))
                # Only flag if the file has actual content (not empty/header-only)
                lines = [
                    line
                    for line in source.strip().splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                if len(lines) > 0 and len(symbols) == 0:
                    no_symbols.append(f.name)
        if no_symbols:
            logger.warning("Files with no fallback symbols: %s", no_symbols[:10])
        # Allow some files to have no symbols (e.g., empty or include-only files)
        assert len(no_symbols) < len(corpus_files) * 0.1

    def test_average_parse_time_under_200ms(self, corpus_files, parser):
        """Average per-file parse time should be under 200ms."""
        total_time = 0.0
        for f in corpus_files:
            source = f.read_text(errors="replace")
            start = time.monotonic()
            result = parser.parse(source, str(f))
            if result.success and result.ast is not None:
                ast_to_symbols(result.ast, str(f), source)
            else:
                fallback_scan(source, str(f))
            total_time += time.monotonic() - start
        avg_ms = (total_time / len(corpus_files)) * 1000
        logger.info(
            "Average parse time: %.1fms over %d files", avg_ms, len(corpus_files)
        )
        assert avg_ms < 200, f"Average parse time {avg_ms:.1f}ms > 200ms"


@pytest.mark.slow
class TestCorpusIncludeResolution:
    """Test include resolution across the corpus."""

    def test_quic_stack_includes_resolve(self):
        """Include directives within quic_stack/ should resolve to existing files."""
        quic_dir = PROTOCOL_TESTING_DIR / "quic" / "quic_stack"
        if not quic_dir.exists():
            pytest.skip("quic_stack/ not found")
        resolver = IncludeResolver(str(quic_dir))
        unresolved = []
        for f in sorted(quic_dir.glob("*.ivy")):
            source = f.read_text(errors="replace")
            for match in re.finditer(r"^include\s+(\S+)", source, re.MULTILINE):
                include_name = match.group(1)
                resolved = resolver.resolve(include_name, str(f))
                if resolved is None:
                    unresolved.append((f.name, include_name))
        if unresolved:
            logger.warning("Unresolved includes: %s", unresolved[:10])
        # quic_stack references sibling directories (tls_stack/, byte_stream,
        # quic_fsm_*, etc.) that the single-directory resolver cannot find.
        # Baseline is ~17 unresolved; threshold set at 25 to catch regressions.
        assert len(unresolved) < 25, f"Too many unresolved includes: {unresolved}"


@pytest.mark.slow
class TestCorpusWorkspaceIndexing:
    """Test workspace indexing performance on corpus."""

    def test_quic_workspace_indexes_under_60s(self):
        """Full indexing of quic/ protocol-testing should complete in <60s."""
        quic_dir = PROTOCOL_TESTING_DIR / "quic"
        if not quic_dir.exists():
            pytest.skip("quic/ not found")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(quic_dir))
        indexer = WorkspaceIndexer(str(quic_dir), parser, resolver)
        start = time.monotonic()
        indexer.index_workspace()
        elapsed = time.monotonic() - start
        logger.info("Workspace indexing took %.1fs", elapsed)
        assert elapsed < 60, f"Indexing took {elapsed:.1f}s > 60s"

    def test_indexed_symbols_are_searchable(self):
        """After indexing, symbol lookup should find known QUIC types."""
        quic_stack = PROTOCOL_TESTING_DIR / "quic" / "quic_stack"
        if not quic_stack.exists():
            pytest.skip("quic_stack/ not found")
        parser = IvyParserWrapper()
        resolver = IncludeResolver(str(quic_stack))
        indexer = WorkspaceIndexer(str(quic_stack), parser, resolver)
        indexer.index_workspace()
        results = indexer.lookup_symbol("cid")
        assert len(results) > 0, "Expected to find 'cid' after indexing quic_stack"


@pytest.mark.slow
class TestDocumentSymbolsCorpus:
    """Verify compute_document_symbols works on corpus files."""

    def test_quic_types_produces_symbols(self):
        quic_types = PROTOCOL_TESTING_DIR / "quic" / "quic_stack" / "quic_types.ivy"
        if not quic_types.exists():
            pytest.skip("quic_types.ivy not found")
        parser = IvyParserWrapper()
        source = quic_types.read_text()
        result = compute_document_symbols(parser, None, source, str(quic_types))
        assert (
            len(result) > 5
        ), f"Expected >5 symbols from quic_types.ivy, got {len(result)}"
        names = [s.name for s in result]
        assert "cid" in names
