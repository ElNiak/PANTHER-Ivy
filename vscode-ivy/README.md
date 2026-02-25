# Ivy Language for VSCode

Language support for [Ivy](https://github.com/ElNiak/Panther-IVy) formal specification files (`.ivy`).

## Features

### Syntax Highlighting

Full TextMate grammar covering all 80+ Ivy keywords:

- Declaration keywords (`action`, `object`, `module`, `type`, `struct`, `isolate`, ...)
- Specification keywords (`property`, `invariant`, `require`, `ensure`, `assert`, `assume`, ...)
- Quantifiers and temporal operators (`forall`, `exists`, `globally`, `eventually`)
- Control flow (`if`, `else`, `while`, `for`, `match`)
- Native code blocks (`<<<...>>>`)
- Labels (`[name]`), uppercase variables, type annotations
- `#lang ivy1.7` directive (highlighted as directive, not comment)

### Language Server (LSP)

When the Ivy LSP server is installed, you get:

- Document outline (Cmd/Ctrl+Shift+O)
- Workspace symbol search (Cmd/Ctrl+T)
- Go-to-definition (F12)
- Find references (Shift+F12)
- Hover information
- Diagnostics (parse errors)

### Snippets

Code templates for common Ivy patterns:
`module`, `object`, `action`, `type`, `struct`, `variant`, `isolate`, `property`, `invariant`, `include`, `instance`, `forall`, `exists`, `if`, and more.

### Language Configuration

- Line comments with `#`
- Auto-closing brackets and native quotes (`<<<`/`>>>`)
- Smart indentation after `= {`
- Word selection includes qualified names (`frame.ack.range`)
- Code folding on `{`/`}`

## Installation

### From VSIX (Recommended)

1. Build the extension:
   ```bash
   cd vscode-ivy
   npm install
   npm run compile
   npx vsce package
   ```
2. Install the `.vsix` file:
   - VSCode: Extensions sidebar > `...` menu > "Install from VSIX..."
   - Or: `code --install-extension ivy-language-0.1.0.vsix`

### For Development

1. Open `vscode-ivy/` in VSCode
2. Press F5 to launch the Extension Development Host
3. Open any `.ivy` file

## Prerequisites

### Syntax Highlighting Only

No prerequisites. The TextMate grammar works standalone.

### Full LSP Support

- Python 3.10+
- `ivy_lsp` package:
  ```bash
  cd panther_ivy
  pip install -e ".[lsp]"
  ```

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ivy.pythonPath` | string | `""` | Python interpreter path. Empty = auto-detect. |
| `ivy.lsp.enabled` | boolean | `true` | Enable/disable the LSP server. |
| `ivy.lsp.args` | string[] | `[]` | Extra arguments for the LSP server. |
| `ivy.lsp.trace.server` | string | `"off"` | Trace level: `off`, `messages`, `verbose`. |

### Python Auto-Detection

The extension searches for Python in this order:
1. `ivy.pythonPath` setting
2. Workspace `.venv/bin/python`
3. System `python3`
4. System `python`

## Troubleshooting

### "No Python interpreter found"

Set `ivy.pythonPath` in your VSCode settings to point to a Python 3.10+ interpreter.

### "ivy_lsp package is not installed"

Install the LSP server from the panther_ivy directory:
```bash
pip install -e ".[lsp]"
```

### LSP server crashes

Check the "Ivy Language Server" output channel (View > Output > select "Ivy Language Server").
The extension auto-restarts the server up to 3 times within 5 minutes.

### Syntax highlighting works but no LSP features

The extension degrades gracefully. You still get syntax highlighting, snippets, and language configuration without the LSP server.

## Development

```bash
cd vscode-ivy
npm install          # Install dependencies
npm run compile      # Build TypeScript
npm run watch        # Watch mode
npm run lint         # ESLint
npm test             # Run tests (requires VSCode)
npx vsce package     # Package as .vsix
```

## Architecture

This is a **thin TypeScript client** — all language intelligence lives in the Python LSP server (`ivy_lsp/`). The extension:

1. Registers the `.ivy` language, grammar, and snippets
2. Discovers a suitable Python interpreter
3. Spawns `python -m ivy_lsp` over stdio
4. Bridges VSCode UI to the LSP server via `vscode-languageclient`
