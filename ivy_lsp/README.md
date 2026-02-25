# Ivy Language Server (ivy_lsp)

Language Server Protocol implementation for the Ivy formal specification language.

## Installation

From the panther_ivy directory:

```bash
pip install -e ".[lsp]"
```

This installs `pygls` and `lsprotocol` as LSP dependencies.

## Usage

### Standalone (stdio)

```bash
python -m ivy_lsp
# or
ivy_lsp
```

The server communicates over stdio using JSON-RPC (LSP protocol).

### With Serena MCP

1. Add `ivy` to `.serena/project.yml` languages list
2. Ensure `ivy_lsp` is installed in the Serena Python environment
3. Serena will automatically start the Ivy LSP for `.ivy` files

### With VSCode

Install the `vscode-ivy` extension (see `vscode-ivy/README.md`).

## Supported LSP Features

| Feature | Method | Description |
|---------|--------|-------------|
| Document Symbols | `textDocument/documentSymbol` | File outline with nested hierarchy |
| Workspace Symbols | `workspace/symbol` | Cross-file symbol search |
| Go to Definition | `textDocument/definition` | Jump to symbol definition |
| Find References | `textDocument/references` | Find all uses of a symbol |
| Hover | `textDocument/hover` | Type signatures and documentation |
| Completion | `textDocument/completion` | Context-aware suggestions |
| Diagnostics | `textDocument/publishDiagnostics` | Parse errors, structural warnings |

## Architecture

```
Source text
    |
    v
IvyParserWrapper (ivy_parser + state isolation)
    |
    +--[success]--> ast_to_symbols() --> IvySymbol tree
    |
    +--[failure]--> fallback_scan() --> IvySymbol tree (degraded)
    |
    v
WorkspaceIndexer (SymbolTable + IncludeGraph + FileCache)
    |
    v
LSP Feature Handlers (document symbols, definition, references, etc.)
```

### Key Components

- **`parsing/parser_session.py`**: State isolation for the Ivy PLY parser
- **`parsing/ast_to_symbols.py`**: AST to IvySymbol conversion (13+ declaration types)
- **`parsing/fallback_scanner.py`**: Lexer-based fallback for broken files
- **`indexer/workspace_indexer.py`**: Cross-file symbol table with include graph
- **`features/`**: LSP request handlers

## Known Limitations

- Requires the `ivy` package on Python path (usually via `pip install -e .`)
- First workspace indexing may take several seconds for large projects (667+ files)
- Fallback scanner produces degraded symbol detail (no type signatures)
- Deep diagnostics (`ivy_check`) require `ivyc` on PATH (graceful degradation if absent)

## Troubleshooting

**"Import ivy failed"**: Ensure the panther_ivy package is installed (`pip install -e .`)

**Slow startup**: First workspace indexing parses all `.ivy` files. Subsequent file changes use incremental re-indexing.

**No diagnostics**: Parser diagnostics are always available. `ivy_check` diagnostics require the `ivyc` binary on PATH.
