# Ivy VSCode Extension - Design Document

**Date**: 2026-02-25
**Branch**: `feature/ivy-lsp-integration`
**Status**: Implementation in progress

## Context

Working with Ivy formal specification files (`.ivy`) in PANTHER has zero IDE tooling. An LSP server (`ivy_lsp/`) is partially implemented (Phase 1 of `TASKS.md` — parser session, symbol types, AST conversion, fallback scanner, stub feature handlers). But there is **no VSCode extension** — no syntax highlighting, no language configuration, no client to connect the LSP server to an editor.

This design adds **Phase 5: VSCode Extension** to the existing `TASKS.md`, creating a thin TypeScript client that spawns the Python LSP server over stdio, plus a TextMate grammar for syntax highlighting, language configuration, and snippets.

**Primary user**: Developer + AI/LLM agents (via Serena MCP).
**Location**: `panther_ivy/vscode-ivy/` (inside the submodule).

## Architecture

```
VSCode  <-->  extension.ts (TypeScript thin client)
                    |
                    | stdio (JSON-RPC)
                    v
              python -m ivy_lsp  (Python, pygls)
                    |
                    v
              ivy_parser / ivy_lexer (PLY-based)
```

The extension is a **thin TypeScript client** using `vscode-languageclient` that:
1. Registers `.ivy` language ID, TextMate grammar, language config
2. Discovers Python + `ivy_lsp` installation
3. Spawns `python -m ivy_lsp` as child process over stdio
4. Bridges VSCode UI to the Python LSP server

All intelligence stays in Python. TypeScript only handles: find Python, spawn server, forward LSP messages.

## Key Design Decisions

### TextMate Grammar (`syntaxes/ivy.tmLanguage.json`)

Root scope: `source.ivy`. Pattern priority order:
1. `#lang ivy1.7` version pragma (higher priority than comments)
2. `#` line comments (`comment.line.number-sign.ivy`)
3. Double-quoted strings + `<<<...>>>` native quotes
4. Numeric literals (integer, hex `0x`)
5. Declaration keywords: `action`, `object`, `module`, `type`, `isolate`, etc.
6. Control keywords: `if`, `else`, `while`, `for`, `match`
7. Specification keywords: `property`, `axiom`, `conjecture`, `invariant`, `require`, `ensure`, `assert`, `assume`
8. Quantifiers: `forall`, `exists`, `globally`, `eventually`
9. Operators: `:=`, `->`, `<->`, `&`, `|`, `~`, `~=`, `..`
10. Uppercase variables (`X`, `Y`, `Z`) as `variable.other.ivy`
11. Label syntax `[name]` as `entity.name.tag.ivy`
12. Type annotations in `name:type` patterns

Keyword source: `ivy/ivy_lexer.py` lines 51-173 (`all_reserved` dict, 80+ keywords).

Nested scopes: `begin`/`end` patterns for `object`, `module`, `struct` bodies with `{ include: "$self" }`.

### Language Configuration

- Line comment: `#` (no block comments in Ivy)
- Bracket pairs: `()`, `{}`, `[]`
- `wordPattern`: `[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*` — includes `.` for qualified names like `frame.ack.range`
- Indent: increase on `= {`, decrease on `}`
- Auto-close `<<<`/`>>>`

### Extension Client (`src/extension.ts`)

Python discovery order:
1. `ivy.pythonPath` setting (if set)
2. Workspace `.venv/bin/python`
3. System `python3`, then `python`
4. Verify with: `python -c "import ivy_lsp; print(ivy_lsp.__version__)"`

Error handling:
- Python not found: warning, degrade to syntax-only
- `ivy_lsp` not importable: error with install instructions
- Server crash: auto-restart (3 times / 5 min, built into `vscode-languageclient`)

Extension settings:
- `ivy.pythonPath`: Path to Python interpreter
- `ivy.lsp.enabled`: Enable/disable LSP (default: true)
- `ivy.lsp.args`: Extra args for LSP server
- `ivy.lsp.trace.server`: Trace level (off/messages/verbose)

## Verification

1. **Syntax highlighting**: Open `protocol-testing/quic/quic_stack/quic_types.ivy` in VSCode Development Host. All keywords, types, comments, strings should be colored. `#lang ivy1.7` should be a directive, not a comment.

2. **Language features**: Toggle line comment with shortcut. Auto-close `{`. Auto-indent after `= {`. Double-click selects `frame.ack.range` as one word.

3. **LSP connection**: Status bar shows "Ivy LSP: Running". Document outline (Cmd+Shift+O) shows symbol hierarchy. Workspace symbol search (Cmd+T) finds symbols across files.

4. **Error handling**: Uninstall `ivy_lsp`, reopen `.ivy` file — should see clear warning. Extension should still provide syntax highlighting.

5. **Tests**: `cd vscode-ivy && npm test` — all grammar and extension tests pass.

6. **Packaging**: `cd vscode-ivy && vsce package` — produces installable `.vsix`.
