"""Diagnostics feature for Ivy LSP."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from lsprotocol import types as lsp

logger = logging.getLogger(__name__)

DEBOUNCE_DELAY = 0.5  # seconds


def _convert_error_to_diagnostic(error: Any, source: str) -> lsp.Diagnostic:
    """Convert a single Ivy parse error to an LSP Diagnostic."""
    line = 0
    message = str(error)

    if hasattr(error, "lineno"):
        lineno = error.lineno
        if hasattr(lineno, "line") and isinstance(lineno.line, int) and lineno.line > 0:
            line = lineno.line - 1

    if hasattr(error, "msg"):
        message = error.msg

    lines = source.split("\n")
    line_len = len(lines[line]) if line < len(lines) else 0

    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=line, character=0),
            end=lsp.Position(line=line, character=line_len),
        ),
        message=message,
        severity=lsp.DiagnosticSeverity.Error,
        source="ivy",
    )


def check_structural_issues(
    source: str,
    filepath: str,
    indexer: Any = None,
) -> List[lsp.Diagnostic]:
    """Check for structural problems without full parsing."""
    diags: List[lsp.Diagnostic] = []
    lines = source.split("\n")

    # 1. Missing #lang header
    stripped = source.lstrip()
    if not stripped.startswith("#lang"):
        first_len = len(lines[0]) if lines else 0
        diags.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(0, 0),
                    end=lsp.Position(0, first_len),
                ),
                message="Missing '#lang ivy1.7' header",
                severity=lsp.DiagnosticSeverity.Warning,
                source="ivy-lsp",
            )
        )

    # 2. Unmatched braces
    depth = 0
    for i, line_text in enumerate(lines):
        # Skip comments but preserve #lang lines
        if line_text.strip().startswith("#lang"):
            code = line_text
        else:
            code = line_text.split("#")[0]
        for ch in code:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth < 0:
                diags.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(i, 0),
                            end=lsp.Position(i, len(line_text)),
                        ),
                        message="Unmatched closing brace",
                        severity=lsp.DiagnosticSeverity.Error,
                        source="ivy-lsp",
                    )
                )
                depth = 0
    if depth > 0:
        last = len(lines) - 1
        last_len = len(lines[last]) if lines else 0
        diags.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(last, 0),
                    end=lsp.Position(last, last_len),
                ),
                message=f"Unmatched opening brace ({depth} unclosed)",
                severity=lsp.DiagnosticSeverity.Error,
                source="ivy-lsp",
            )
        )

    # 3. Unresolved includes
    if indexer:
        for match in re.finditer(r"^include\s+(\w+)", source, re.MULTILINE):
            inc_name = match.group(1)
            resolved = indexer._resolver.resolve(inc_name, filepath)
            if resolved is None:
                line_no = source[: match.start()].count("\n")
                line_text = lines[line_no] if line_no < len(lines) else ""
                diags.append(
                    lsp.Diagnostic(
                        range=lsp.Range(
                            start=lsp.Position(line_no, 0),
                            end=lsp.Position(line_no, len(line_text)),
                        ),
                        message=f"Unresolved include: {inc_name}",
                        severity=lsp.DiagnosticSeverity.Warning,
                        source="ivy-lsp",
                    )
                )

    return diags


def compute_diagnostics(
    parser: Any,
    source: str,
    filepath: str,
    indexer: Any = None,
) -> List[lsp.Diagnostic]:
    """Compute all diagnostics for a source file."""
    diags = check_structural_issues(source, filepath, indexer)

    if parser is None:
        return diags

    result = parser.parse(source, filepath)
    if not result.success:
        for error in result.errors:
            diags.append(_convert_error_to_diagnostic(error, source))

    return diags


async def run_deep_diagnostics(
    filepath: str,
    ivy_check_cmd: str = "ivy_check",
) -> List[lsp.Diagnostic]:
    """Run ivy_check as subprocess and convert output to diagnostics."""
    try:
        proc = await asyncio.create_subprocess_exec(
            ivy_check_cmd,
            filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
    except FileNotFoundError:
        logger.debug("%s not found on PATH", ivy_check_cmd)
        return []
    except asyncio.TimeoutError:
        logger.warning("Deep diagnostics timed out for %s", filepath)
        return []
    except Exception:
        logger.warning("Deep diagnostics failed for %s", filepath, exc_info=True)
        return []

    diags: List[lsp.Diagnostic] = []
    output = stderr.decode("utf-8", errors="replace") + stdout.decode(
        "utf-8", errors="replace"
    )
    for line in output.splitlines():
        m = re.match(r".*?:(\d+):\s*(error|warning):\s*(.*)", line)
        if m:
            lineno = max(0, int(m.group(1)) - 1)
            severity = (
                lsp.DiagnosticSeverity.Error
                if m.group(2) == "error"
                else lsp.DiagnosticSeverity.Warning
            )
            diags.append(
                lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(lineno, 0),
                        end=lsp.Position(lineno, 999),
                    ),
                    message=m.group(3),
                    severity=severity,
                    source="ivy_check",
                )
            )
    return diags


def register(server) -> None:
    """Register diagnostic handlers for didOpen, didChange, didSave."""
    _debounce_tasks: Dict[str, asyncio.Task] = {}

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
        uri = params.text_document.uri
        doc = server.workspace.get_text_document(uri)
        filepath = uri.replace("file://", "")
        diags = compute_diagnostics(
            server._parser, doc.source or "", filepath, server._indexer
        )
        server.publish_diagnostics(uri, diags)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
        uri = params.text_document.uri
        old_task = _debounce_tasks.pop(uri, None)
        if old_task and not old_task.done():
            old_task.cancel()

        async def _debounced():
            await asyncio.sleep(DEBOUNCE_DELAY)
            doc = server.workspace.get_text_document(uri)
            filepath = uri.replace("file://", "")
            diags = compute_diagnostics(
                server._parser, doc.source or "", filepath, server._indexer
            )
            server.publish_diagnostics(uri, diags)

        loop = asyncio.get_event_loop()
        _debounce_tasks[uri] = loop.create_task(_debounced())

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
        uri = params.text_document.uri
        filepath = uri.replace("file://", "")
        doc = server.workspace.get_text_document(uri)
        diags = compute_diagnostics(
            server._parser, doc.source or "", filepath, server._indexer
        )
        server.publish_diagnostics(uri, diags)

        async def _deep():
            deep = await run_deep_diagnostics(filepath)
            server.publish_diagnostics(uri, diags + deep)

        loop = asyncio.get_event_loop()
        loop.create_task(_deep())
