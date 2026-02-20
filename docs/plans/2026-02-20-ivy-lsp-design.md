# Ivy Language Server Protocol (LSP) - Design Document

**Date**: 2026-02-20
**Status**: Approved
**Branch**: `feature/ivy-lsp`

## Problem Statement

Working with Ivy formal specification files (`.ivy`) in the PANTHER project has zero IDE tooling - no symbol navigation, no go-to-definition, no validation feedback. This makes it difficult for Serena MCP and LLMs to navigate and produce valid Ivy formal specifications.

## Goals

1. Integrate with Serena MCP for symbol navigation (`find_symbol`, `get_symbols_overview`, `find_referencing_symbols`)
2. Provide validation feedback via real parse errors and async `ivyc` diagnostics
3. Work locally (host machine) for navigation even without Docker/ivyc
4. Work inside Docker for full validation with ivyc
5. Guide LLMs in producing valid Ivy formal specifications

## Architecture: Full Parser (1.7 pinned) + Lexer Fallback

### Design Rationale

Pinning to Ivy 1.7 eliminates the version-dependent grammar problem (conditional grammar rules at import time in `ivy_parser.py` lines 16-75). This makes the full `ivy_parser.py` viable for LSP use, giving us:
- Full AST with nested definitions, parameter types, return types
- Built-in `include` resolution with scope merging
- Module instantiation expansion
- Real parse error diagnostics (redefinitions, wrong param count, etc.)

When the parser fails (user mid-typing, incomplete code), we fall back to the lexer (`ivy_lexer.py`) + a lightweight declaration scanner for degraded but usable results.

### Two-Tier Parsing Strategy

```
File change event
       |
       v
+------------------+
| ivy_parser.parse |  <-- Primary: Full AST, include resolution, rich symbols
|  (1.7 pinned)    |
+--------+---------+
         |
    Parse succeeds?
    +----+----+
   Yes       No (ErrorList)
    |         |
    v         v
Full AST   +------------------+
symbols    | ivy_lexer tokens |  <-- Fallback: Token stream + declaration scanner
           | + decl scanner   |
           +--------+---------+
                    |
              Degraded symbols
              (declarations only)
```

### Parser State Isolation

Before each `parse()` call, save and restore these globals in try/finally:

```python
# ivy_parser.py globals (lines 100-102, 236-239)
error_list, stack, special_attribute, parent_object, global_attribute, common_attribute

# ivy_utils globals
iu.filename, iu.ivy_language_version

# ivy_ast globals
ivy_ast.label_counter, ivy_ast.lf_counter
```

All parsing is serialized through an async queue (no concurrent parsing = no state corruption).

### Project Structure

```
ivy_lsp/
  __init__.py
  __main__.py                    # Entry: python -m ivy_lsp (stdio mode)
  server.py                      # IvyLanguageServer(pygls.LanguageServer)

  parsing/
    __init__.py
    parser_session.py            # State isolation wrapper for ivy_parser.parse()
    fallback_scanner.py          # Lexer-based declaration scanner (fallback)
    symbols.py                   # IvySymbol, IvyScope, SymbolTable dataclasses
    ast_to_symbols.py            # Walk ivy_ast Decl tree -> LSP DocumentSymbol

  indexer/
    __init__.py
    workspace_indexer.py         # Scans workspace, builds cross-file symbol index
    include_resolver.py          # Resolves `include X` -> file paths (cwd + std lib)
    file_cache.py                # Parsed AST cache with mtime invalidation

  features/
    __init__.py
    document_symbols.py          # textDocument/documentSymbol
    workspace_symbols.py         # workspace/symbol
    definition.py                # textDocument/definition
    references.py                # textDocument/references
    completion.py                # textDocument/completion
    diagnostics.py               # textDocument/publishDiagnostics
    hover.py                     # textDocument/hover (type info from AST)

  utils/
    __init__.py
    position_utils.py            # LSP position/range helpers
```

### AST-to-Symbol Mapping

| Ivy AST class | LSP SymbolKind | Info extracted |
|--------------|----------------|----------------|
| `TypeDecl` | Class | Name, enum values if enumerated |
| `ObjectDecl` | Module | Name, nested declarations |
| `ModuleDecl` | Module | Name, parameters |
| `ActionDecl` | Function | Name, params with types, return type |
| `RelationDecl` | Function | Name, parameter types |
| `FunctionDecl` | Function | Name, params, return type |
| `PropertyDecl` | Property | Name, formula |
| `AxiomDecl` | Property | Name, formula |
| `IsolateDecl` | Namespace | Name, with-clause |
| `InstanceDecl` | Variable | Name, module instantiated |
| `AliasDecl` | Variable | Name, aliased type |
| `DestructorDecl` | Field | Name, parent struct |
| `VariantDecl` | Class | Name, parent type |

### Serena MCP Integration

Serena expects a standard LSP server over stdio. Integration requires:

1. **Fork Serena** to add `IVY` to the `Language` enum in `src/solidlsp/ls_config.py`
2. Implement `get_source_fn_matcher()` -> `FilenameMatcher("*.ivy")`
3. Implement `get_ls_class()` -> `IvyLanguageServer` (SolidLanguageServer subclass)
4. Update `.serena/project.yml`: add `ivy` to languages list

### Dependencies

- `pygls` >= 1.0 - Python LSP framework
- `lsprotocol` - LSP type definitions (installed with pygls)
- `ivy` package (existing, in-repo) - lexer, parser, AST classes
- No new native dependencies

### Key Reference Files

| File | Why |
|------|-----|
| `ivy/ivy_lexer.py` | 170+ tokens, version-dependent reserved words, fallback tokenization |
| `ivy/ivy_parser.py` | Full grammar (200 rules), `parse()` at line 3120, globals at lines 100-102, 236-239 |
| `ivy/ivy_ast.py` | ~40 Decl subclasses with `defines()` methods |
| `ivy/ivy_compiler.py` | Include resolution (`import_module` ~line 2299), version detection |
| `ivy/ivy_utils.py` | `Location`, `filename`, `ivy_language_version` globals |
| `protocol-testing/quic/quic_stack/quic_types.ivy` | Primary test file |
| `protocol-testing/quic/quic_stack/quic_frame.ivy` | Complex nested objects/variants |
| `.serena/project.yml` | Serena config |

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Parser global state corruption | Save/restore in try/finally, serialize all parses |
| Poor error recovery on invalid files | Fall back to lexer-based scanner |
| Large workspace indexing performance | Cache parsed ASTs with mtime invalidation, debounce re-parses |
| Serena doesn't support custom language | Fork Serena and add IVY enum member |
| `include` chains cause slow re-parsing | Cache included file ASTs, only re-parse changed file |
| Parser crashes on edge cases | Catch all exceptions, return fallback results |
