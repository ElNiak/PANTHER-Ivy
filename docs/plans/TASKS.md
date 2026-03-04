# Ivy LSP - Task Breakdown

**Branch**: `feature/ivy-lsp`
**Design Doc**: `docs/plans/2026-02-20-ivy-lsp-design.md`

> Each task has a checkbox, estimated effort, dependencies, and acceptance criteria.
> Tasks are ordered by implementation phase and dependency chain.

---

## Phase 1: Core Parser Integration + Document Symbols

### Task 1.1: Project Scaffolding
- [ ] **Create `ivy_lsp/` package structure**
- **Effort**: 1 hour
- **Dependencies**: None
- **Files to create**:
  - `ivy_lsp/__init__.py` - Package init, version string
  - `ivy_lsp/__main__.py` - Entry point: `python -m ivy_lsp` starts stdio LSP server
  - `ivy_lsp/server.py` - `IvyLanguageServer(LanguageServer)` pygls server class with lifecycle handlers
  - `ivy_lsp/parsing/__init__.py`
  - `ivy_lsp/indexer/__init__.py`
  - `ivy_lsp/features/__init__.py`
  - `ivy_lsp/utils/__init__.py`
- **Code style note**: All `ivy_lsp/*.py` files must follow pre-commit Tier 1 rules defined in `.pre-commit-config.yaml`: Black formatting (`--target-version py310`), isort imports (`--profile black`), line length 88. Run `pre-commit run --all-files` to verify.
- **Acceptance criteria**:
  - `python -m ivy_lsp` starts a server that accepts LSP initialization over stdio
  - Server responds to `initialize` with capabilities (document symbols, definition, references, completion, diagnostics)
  - Server logs startup to stderr

### Task 1.2: IvySymbol Dataclasses
- [ ] **Create symbol representation (`ivy_lsp/parsing/symbols.py`)**
- **Effort**: 2 hours
- **Dependencies**: None
- **Details**:
  - `IvySymbol` dataclass: `name`, `kind` (LSP SymbolKind), `range` (start_line, end_line, start_col, end_col), `children: List[IvySymbol]`, `detail` (signature string), `file_path`
  - `IvyScope` dataclass: `name`, `symbols: Dict[str, IvySymbol]`, `parent: Optional[IvyScope]`, `children: List[IvyScope]`
  - `SymbolTable` class: `add_symbol()`, `lookup(name)`, `lookup_qualified(path)`, `all_symbols()`, `symbols_in_file(path)`
  - `IncludeGraph` class: `add_edge(from_file, to_file)`, `get_includes(file)`, `get_included_by(file)`, `get_transitive_includes(file)`
- **Acceptance criteria**:
  - Symbol hierarchy can represent nested Ivy constructs (object inside object)
  - SymbolTable supports qualified name lookup (e.g., `frame.ack.range`)
  - IncludeGraph supports transitive dependency queries

### Task 1.3: Parser State Isolation
- [ ] **Create `ivy_lsp/parsing/parser_session.py`**
- **Effort**: 4 hours
- **Dependencies**: Task 1.2
- **Details**:
  - `ParserSession` context manager that saves/restores all `ivy_parser` globals:
    - `ivy_parser.error_list` (line 100)
    - `ivy_parser.stack` (line 102)
    - `ivy_parser.special_attribute` (line 236)
    - `ivy_parser.parent_object` (line 237)
    - `ivy_parser.global_attribute` (line 238)
    - `ivy_parser.common_attribute` (line 239)
    - `iu.filename`
    - `iu.ivy_language_version` (set to `[1,7]`)
    - `ivy_ast.label_counter`
    - `ivy_ast.lf_counter`
  - `IvyParserWrapper` class:
    - `parse(source: str, filename: str) -> ParseResult`
    - `ParseResult`: `ast: Optional[Ivy]`, `errors: List[ParseError]`, `success: bool`
    - Uses `ParserSession` context manager
    - Catches all exceptions (including `ErrorList`, `IvyError`, unexpected exceptions)
    - Returns partial results when possible
  - Import path handling: ensure `ivy` package is importable from `ivy_lsp/`
  - **Production note**: Z3 imports now route through `ivy/z3_shim.py`, a compatibility shim that wraps `z3` / `z3_api`. The shim is read-only (no mutable state to save/restore), but the import path must be accessible. Ensure `ivy.z3_shim` is importable when configuring the `ivy` package path.
  - **Production note**: `ivy_parser.py` now includes an `UNPROVABLE` reserved word and grammar rules (`p_optunprovable`, `p_top_unprovable_property_labeledfmla`, etc.). The `check_unprovable` context var from `ivy_actions` is imported at line 6. These add parser globals to be aware of but do **not** require state save/restore (they are grammar rules, not mutable globals). Line number references for globals above are verified accurate on production.
- **Acceptance criteria**:
  - Can parse a valid `.ivy` file and get back an `Ivy` AST object
  - Global state is fully restored after parsing (even on exception)
  - Two sequential parses don't interfere with each other
  - Parse errors are captured, not raised

### Task 1.4: AST-to-Symbol Converter
- [ ] **Create `ivy_lsp/parsing/ast_to_symbols.py`**
- **Effort**: 6 hours
- **Dependencies**: Task 1.2, Task 1.3
- **Details**:
  - `ast_to_symbols(ivy_ast: Ivy, filename: str) -> List[IvySymbol]`
  - Walk `Ivy.decls` list, map each `Decl` subclass to `IvySymbol`:
    - `TypeDecl` -> `SymbolKind.Class` (detect enum types from args)
    - `ObjectDecl` -> `SymbolKind.Module` (recurse into nested decls)
    - `ModuleDecl` -> `SymbolKind.Module` (extract parameters)
    - `ActionDecl` -> `SymbolKind.Function` (extract params, return type from AST)
    - `RelationDecl` -> `SymbolKind.Function`
    - `FunctionDecl` -> `SymbolKind.Function` (extract return type)
    - `PropertyDecl` -> `SymbolKind.Property` (note: may have `lf.unprovable=True` attribute; reflect in `detail` string, e.g., `"unprovable property name"`)
    - `AxiomDecl` -> `SymbolKind.Property`
    - `IsolateDecl` -> `SymbolKind.Namespace`
    - `InstanceDecl` (InstantiateDecl) -> `SymbolKind.Variable`
    - `AliasDecl` -> `SymbolKind.Variable`
    - `DestructorDecl` -> `SymbolKind.Field`
    - `VariantDecl` -> `SymbolKind.Class`
    - `ImportDecl` / `ExportDeccl` -> track but don't emit as symbols
    - `IncludeDecl` -> track for include graph
    - `BeforeDecl` / `AfterDecl` / `AroundDecl` -> `SymbolKind.Function` (mixin)
    - `DefinitionDecl` -> `SymbolKind.Function`
    - `StructDecl` (within TypeDecl) -> fields as children
  - Extract `detail` string for each symbol (e.g., action signature: `(pkt:quic_packet) returns (ok:bool)`)
  - Handle `lineno` from `iu.Location` objects -> LSP Range
- **Reference**: `ivy/ivy_ast.py` for all Decl subclasses and their `defines()` methods
- **Acceptance criteria**:
  - Parse `quic_types.ivy` and produce correct symbol hierarchy
  - Parse `quic_frame.ivy` and produce correct nested object structure
  - All 13+ Decl types are handled
  - Symbol positions (line/column) are accurate

### Task 1.5: Lexer Fallback Scanner
- [ ] **Create `ivy_lsp/parsing/fallback_scanner.py`**
- **Effort**: 4 hours
- **Dependencies**: Task 1.2
- **Details**:
  - `fallback_scan(source: str, filename: str) -> List[IvySymbol]`
  - Use `ivy_lexer.lexer` (with `LexerVersion([1,7])`) to tokenize the source
  - Walk token stream, detect declaration patterns:
    ```
    TYPE PRESYMBOL            -> TypeSymbol
    OBJECT PRESYMBOL [EQ] LCB -> ObjectSymbol (push scope)
    MODULE PRESYMBOL LPAREN   -> ModuleSymbol (push scope)
    ACTION PRESYMBOL          -> ActionSymbol
    RELATION PRESYMBOL        -> RelationSymbol
    FUNCTION PRESYMBOL        -> FunctionSymbol
    INCLUDE PRESYMBOL         -> IncludeDirective
    ISOLATE PRESYMBOL         -> IsolateSymbol
    EXPORT [ACTION] PRESYMBOL -> ExportDirective
    IMPORT [ACTION] PRESYMBOL -> ImportDirective
    PROPERTY/AXIOM/CONJECTURE -> PropertySymbol
    UNPROVABLE PROPERTY/INVARIANT -> PropertySymbol (with unprovable flag)
    BEFORE/AFTER/AROUND PRESYMBOL -> MixinSymbol
    VARIANT PRESYMBOL OF PRESYMBOL -> VariantSymbol
    INSTANTIATE PRESYMBOL COLON PRESYMBOL -> InstanceSymbol
    ALIAS PRESYMBOL           -> AliasSymbol
    INTERPRET PRESYMBOL       -> InterpretSymbol
    VAR/INDIV PRESYMBOL       -> VariableSymbol
    DESTRUCTOR PRESYMBOL      -> DestructorSymbol
    DEFINITION PRESYMBOL      -> DefinitionSymbol
    SPECIFICATION LCB         -> Block scope
    IMPLEMENTATION LCB        -> Block scope
    ```
  - Track brace depth (`LCB`/`RCB`) for scope nesting
  - Recognize `GLOBALLY` (U+25A1) and `EVENTUALLY` (U+25C7) as Unicode temporal operator tokens (defined in `ivy_lexer.py` via `t_GLOBALLY`/`t_EVENTUALLY` functions)
  - Note: lexer uses `re.UNICODE | re.VERBOSE` flags (line 251 of `ivy_lexer.py`)
  - Produce hierarchical symbols respecting object/module nesting
- **Acceptance criteria**:
  - Can produce partial symbols from files with syntax errors
  - Handles nested `object { object { ... } }` correctly via brace depth
  - Produces same top-level symbols as AST converter for valid files (degraded detail)

### Task 1.6: Document Symbols Feature
- [ ] **Create `ivy_lsp/features/document_symbols.py`**
- **Effort**: 2 hours
- **Dependencies**: Task 1.3, Task 1.4, Task 1.5
- **Details**:
  - Register `textDocument/documentSymbol` handler on the server
  - On request: parse the document (primary: parser, fallback: scanner)
  - Convert `List[IvySymbol]` to `List[DocumentSymbol]` (LSP protocol type)
  - Handle hierarchical symbols (children nested inside parent DocumentSymbol)
- **Acceptance criteria**:
  - VS Code / Serena can display symbol outline for `.ivy` files
  - Hierarchy reflects `object` / `module` nesting
  - Falls back gracefully on invalid files

### Task 1.7: Workspace Symbols Feature
- [ ] **Create `ivy_lsp/features/workspace_symbols.py`**
- **Effort**: 2 hours
- **Dependencies**: Task 1.6
- **Details**:
  - Register `workspace/symbol` handler
  - On request with query string: search all parsed symbols matching query
  - Support substring matching and qualified names
  - Return `List[WorkspaceSymbol]` with file locations
- **Acceptance criteria**:
  - Search for `pkt_num` returns all matching symbols across workspace
  - Supports partial matching (e.g., `pkt` matches `pkt_num`)

### Task 1.8: Position Utilities
- [ ] **Create `ivy_lsp/utils/position_utils.py`**
- **Effort**: 1 hour
- **Dependencies**: None
- **Details**:
  - `ivy_location_to_range(loc: iu.Location, source: str) -> Range` - Convert Ivy's `iu.Location` to LSP Range
  - `offset_to_position(offset: int, source: str) -> Position` - Convert byte offset to LSP Position
  - `word_at_position(lines: List[str], position: Position) -> str` - Extract word at cursor
  - Handle Ivy's 1-based line numbers vs LSP's 0-based
- **Acceptance criteria**:
  - Line number conversion is correct (Ivy 1-based -> LSP 0-based)
  - Word extraction handles `.` separated qualified names

### Task 1.9: Phase 1 Testing
- [ ] **Test parser integration against real Ivy files**
- **Effort**: 4 hours
- **Dependencies**: All Phase 1 tasks
- **Details**:
  - Unit test: Parse each Decl type against small `.ivy` snippets
  - Integration test: Parse `quic_types.ivy`, `quic_frame.ivy`, `quic_packet.ivy`
  - Fallback test: Introduce syntax errors in test files, verify fallback produces symbols
  - Corpus test: Run parser against sample of `.ivy` files from `protocol-testing/quic/`
  - Server test: Start LSP server, send `documentSymbol` request, verify response
- **Acceptance criteria**:
  - All tests pass
  - Parser handles at least 95% of `quic_stack/` files without crashes
  - Fallback produces reasonable symbols for files that fail parsing

---

## Phase 2: Cross-File Index + Navigation

### Task 2.1: Include Resolver
- [ ] **Create `ivy_lsp/indexer/include_resolver.py`**
- **Effort**: 3 hours
- **Dependencies**: Phase 1 complete
- **Details**:
  - `IncludeResolver` class:
    - `__init__(workspace_root: str, ivy_include_path: Optional[str] = None)`
    - `resolve(include_name: str, from_file: str) -> Optional[str]` - Resolve `include X` to absolute file path
    - Search order (from `ivy_compiler.py` `import_module` logic):
      1. Same directory as the including file
      2. Workspace root directory
      3. Standard library: `ivy/include/1.7/` (relative to ivy package)
    - Handle `.ivy` extension appending
  - `find_all_ivy_files(workspace_root: str) -> List[str]` - Glob for all `.ivy` files
- **Reference**: `ivy/ivy_compiler.py` lines ~2268-2311 (`read_module`, `import_module`)
- **Acceptance criteria**:
  - `include quic_types` in `quic_frame.ivy` resolves to `quic_stack/quic_types.ivy`
  - Standard library includes (e.g., `include collections`) resolve to `ivy/include/1.7/collections.ivy`
  - Returns `None` for unresolvable includes

### Task 2.2: File Cache
- [ ] **Create `ivy_lsp/indexer/file_cache.py`**
- **Effort**: 2 hours
- **Dependencies**: Task 1.3
- **Details**:
  - `FileCache` class:
    - `get(filepath: str) -> Optional[CachedFile]` - Returns cached parse result if mtime unchanged
    - `put(filepath: str, result: ParseResult, symbols: List[IvySymbol])` - Cache parse result
    - `invalidate(filepath: str)` - Remove from cache
    - `invalidate_dependents(filepath: str, include_graph: IncludeGraph)` - Invalidate all files that include this one
  - `CachedFile` dataclass: `filepath`, `mtime`, `parse_result`, `symbols`, `includes`
  - LRU eviction when cache exceeds configurable size (default: 500 files)
- **Acceptance criteria**:
  - Second parse of same (unmodified) file is served from cache
  - File modification triggers cache invalidation
  - Dependent files are invalidated when a dependency changes

### Task 2.3: Workspace Indexer
- [ ] **Create `ivy_lsp/indexer/workspace_indexer.py`**
- **Effort**: 6 hours
- **Dependencies**: Task 2.1, Task 2.2, Task 1.2
- **Details**:
  - `WorkspaceIndexer` class:
    - `__init__(workspace_root: str, parser: IvyParserWrapper, resolver: IncludeResolver)`
    - `index_workspace() -> None` - Scan all `.ivy` files, parse each, build symbol table + include graph
    - `reindex_file(filepath: str) -> None` - Re-parse a single file, update symbol table
    - `get_symbols(filepath: str) -> List[IvySymbol]` - Get symbols for a file
    - `lookup_symbol(name: str) -> List[SymbolLocation]` - Find all definitions of a symbol
    - `lookup_references(name: str, definition_file: str) -> List[SymbolLocation]` - Find all references
    - `get_symbols_in_scope(filepath: str) -> List[IvySymbol]` - All symbols visible in a file (own + transitive includes)
  - Background indexing with progress reporting (`window/workDoneProgress`)
  - Debounced re-indexing on file changes (200ms debounce)
- **Acceptance criteria**:
  - Full workspace index of `protocol-testing/quic/` completes in <30 seconds
  - Symbol lookup across include boundaries works correctly
  - File changes trigger targeted re-indexing (not full workspace)

### Task 2.4: Go-to-Definition Feature
- [ ] **Create `ivy_lsp/features/definition.py`**
- **Effort**: 3 hours
- **Dependencies**: Task 2.3
- **Details**:
  - Register `textDocument/definition` handler
  - On request:
    1. Get word at cursor position
    2. Handle qualified names (e.g., `frame.ack.largest_acked` -> look up `largest_acked` in `frame.ack` scope)
    3. Look up in workspace indexer
    4. Return `Location` (file URI + range)
  - Handle multiple definitions (return `List[Location]`)
- **Acceptance criteria**:
  - Go-to-definition on `pkt_num` in `quic_frame.ivy` jumps to `quic_types.ivy`
  - Go-to-definition on `quic_packet_type.initial` jumps to the enum definition
  - Works across `include` boundaries

### Task 2.5: Find References Feature
- [ ] **Create `ivy_lsp/features/references.py`**
- **Effort**: 3 hours
- **Dependencies**: Task 2.3
- **Details**:
  - Register `textDocument/references` handler
  - On request:
    1. Get word at cursor position
    2. Search all files in workspace for token matching the symbol name
    3. Filter to files that are in the include graph (can actually see the symbol)
    4. Return `List[Location]`
  - For cross-file references: use lexer tokenization to find exact token matches (not substring grep)
- **Acceptance criteria**:
  - Find references on `type pkt_num` shows all files using `pkt_num`
  - Does not show false positives from files that don't include the definition

### Task 2.6: Phase 2 Testing
- [ ] **Test cross-file navigation against QUIC protocol models**
- **Effort**: 4 hours
- **Dependencies**: All Phase 2 tasks
- **Details**:
  - Test include resolution for all files in `quic_stack/`
  - Test go-to-definition across include boundaries
  - Test find references across the workspace
  - Test workspace indexer performance on full `protocol-testing/` (667 files)
  - Test cache invalidation on file changes
- **Acceptance criteria**:
  - All `include` directives in `quic_stack/` resolve correctly
  - Go-to-definition works for at least 90% of symbol references
  - Workspace indexing completes in reasonable time (<30s)

---

## Phase 3: Completion + Diagnostics + Hover

### Task 3.1: Completion Feature
- [ ] **Create `ivy_lsp/features/completion.py`**
- **Effort**: 6 hours
- **Dependencies**: Phase 2 complete
- **Details**:
  - Register `textDocument/completion` handler
  - Completion contexts:
    1. **After `.`**: Scope-based completion (e.g., `frame.` -> fields/actions of `frame`)
       - Look up the object/module before the dot in symbol table
       - Return its children as completion items
    2. **After `include `**: List available `.ivy` filenames in workspace + standard library
    3. **After keywords** (`type`, `action`, `object`, etc.): Suggest common patterns
    4. **General**: All symbols in scope (from current file + transitive includes)
       - Keywords from `ivy_lexer.py` `all_reserved` dict (includes `unprovable`, `globally`, `eventually` on production)
       - Add `unprovable` to keyword completions for property-related contexts (e.g., after typing in a property/invariant block)
       - All defined symbols visible through include chain
  - `CompletionItem` with:
    - `label`: symbol name
    - `kind`: mapped from IvySymbol kind
    - `detail`: type signature or definition summary
    - `documentation`: extracted from nearby comments (if any)
    - `insertText`: smart insertion (e.g., action with parameters -> snippet)
- **Acceptance criteria**:
  - `frame.` produces field completions for the `frame` object
  - `include ` produces available filenames
  - General completion shows all visible symbols + keywords
  - No duplicate completions

### Task 3.2: Diagnostics Feature
- [ ] **Create `ivy_lsp/features/diagnostics.py`**
- **Effort**: 4 hours
- **Dependencies**: Task 1.3
- **Details**:
  - **Parser diagnostics** (always available):
    - Convert `ivy_parser` `ParseError` / `ErrorList` to LSP `Diagnostic`
    - Map `iu.Location` to LSP Range
    - Severity: `Error` for parse errors, `Warning` for redefinitions
  - **Structural diagnostics** (from fallback scanner):
    - Missing `#lang ivy1.7` directive -> Warning
    - Unmatched braces -> Error
    - Unresolved `include` (file not found) -> Error
  - **Deep diagnostics** (async, when `ivyc` available, on save):
    - Shell out to `ivy_check <file>.ivy` or `ivyc target=test <file>.ivy`
    - Parse stderr for error messages: `<filename>: line <N>: <message>`
    - Check if `ivyc` / `ivy_check` is on PATH, skip silently if not
    - Run in background asyncio task, publish results when complete
  - Publish diagnostics on `textDocument/didOpen`, `textDocument/didChange` (debounced), `textDocument/didSave`
- **Acceptance criteria**:
  - Parse errors show as diagnostics with correct line numbers
  - Missing `#lang` directive produces a warning
  - Unresolved includes show as errors
  - `ivyc` diagnostics appear after save (when available)
  - No diagnostics when `ivyc` is not available (graceful degradation)

### Task 3.3: Hover Feature
- [ ] **Create `ivy_lsp/features/hover.py`**
- **Effort**: 3 hours
- **Dependencies**: Phase 2 complete
- **Details**:
  - Register `textDocument/hover` handler
  - On hover:
    1. Get word at cursor
    2. Look up symbol in index
    3. Return formatted hover content:
       - For actions: `action name(param: type, ...) returns (ret: type)`
       - For types: `type name` or `type name = {enum1, enum2, ...}` or `type name = struct { field: type, ... }`
       - For relations: `relation name(param: type, ...)`
       - For functions: `function name(param: type, ...) : return_type`
       - For instances: `instance name : module_name(params)`
       - For aliases: `alias name = target_type`
    4. Format as markdown code block with `ivy` language tag
- **Acceptance criteria**:
  - Hover on action name shows full signature
  - Hover on type name shows type definition
  - Hover on instance shows module being instantiated

### Task 3.4: Phase 3 Testing
- [ ] **Test completion, diagnostics, and hover against real files**
- **Effort**: 3 hours
- **Dependencies**: All Phase 3 tasks
- **Details**:
  - Test completion in various contexts (after `.`, after `include `, general)
  - Test diagnostics with valid files (no diagnostics), invalid files (parser errors), unresolved includes
  - Test hover on different symbol types
  - Test `ivyc` async diagnostics (requires Docker or local ivyc installation)
- **Acceptance criteria**:
  - All completion contexts produce relevant suggestions
  - Diagnostics have correct positions and messages
  - Hover shows useful type information

---

## Phase 4: Serena Integration + Polish

### Task 4.1: Fork Serena and Add IVY Language
- [ ] **Add IVY language support to Serena**
- **Effort**: 4 hours
- **Dependencies**: Phase 3 complete
- **Details**:
  - Fork `https://github.com/oraios/serena`
  - Add `IVY = "ivy"` to `Language` enum in `src/solidlsp/ls_config.py`
  - Implement `get_source_fn_matcher()`: `FilenameMatcher("*.ivy")`
  - Implement `get_ls_class()`: return `IvyLanguageServer` class
  - Implement `is_experimental()`: return `True` initially
  - Create `src/solidlsp/language_servers/ivy_language_server.py`:
    - `IvyLanguageServer(SolidLanguageServer)` subclass
    - `_start_server()`: Start `python -m ivy_lsp` over stdio
    - `_create_dependency_provider()`: Check for `ivy_lsp` on PATH or in project
    - `is_ignored_dirname()`: Skip `build/`, `submodules/`, `__pycache__/`
  - Test with `uv run serena` pointing at panther_ivy workspace
- **Acceptance criteria**:
  - Serena recognizes `.ivy` files and starts the Ivy LSP
  - `get_symbols_overview` works on `.ivy` files
  - `find_symbol` works for Ivy symbols
  - `find_referencing_symbols` works across Ivy files

### Task 4.2: Update Serena Project Configuration
- [ ] **Update `.serena/project.yml` to include ivy**
- **Effort**: 30 minutes
- **Dependencies**: Task 4.1
- **Details**:
  - Add `ivy` to the `languages` list in `.serena/project.yml`
  - Test that Serena picks up `.ivy` files
- **Acceptance criteria**:
  - Serena processes `.ivy` files in the PANTHER workspace

### Task 4.3: Package ivy_lsp
- [ ] **Add ivy_lsp to setup.py**
- **Effort**: 1 hour
- **Dependencies**: Phase 3 complete
- **Details**:
  - Package is now `panther_ms_ivy` v1.8.26 (renamed from `ms_ivy` v1.8.25 during VMT-RF integration). Update `setup.py` (line 28: `name="panther_ms_ivy"`, line 30: `version="1.8.26"`).
  - Add `"lsp": ["pygls", "lsprotocol"]` to `extras_require` in `setup.py`
  - Add entry point: `ivy_lsp=ivy_lsp.__main__:main` in `console_scripts`
  - Ensure `ivy_lsp` can locate the `ivy` package (parent directory or installed)
  - Test installation: `pip install -e ".[lsp]"` and verify `python -m ivy_lsp` starts
- **Acceptance criteria**:
  - `pip install -e ".[lsp]"` installs ivy_lsp with all dependencies
  - `python -m ivy_lsp` starts the language server

### Task 4.4: Corpus Testing
- [ ] **Test against full protocol-testing corpus**
- **Effort**: 4 hours
- **Dependencies**: Phase 3 complete
- **Details**:
  - Parse all `.ivy` files in `protocol-testing/` (currently 667 files) and `doc/examples/cav2024/` (7 VMT-RF files added post-PR #9). Total corpus across the repo (excluding submodules): ~1430 `.ivy` files.
  - Measure: parse success rate, fallback rate, average parse time
  - Fix any parser crashes or edge cases discovered
  - Test include resolution across all files
  - Test workspace indexing performance
  - Generate test report
- **Acceptance criteria**:
  - 95%+ files parse successfully with full parser
  - Remaining files produce fallback symbols
  - No crashes on any file
  - Workspace indexing completes in <60 seconds for full corpus

### Task 4.5: End-to-End Serena Workflow Test
- [ ] **Test complete Serena MCP workflow**
- **Effort**: 2 hours
- **Dependencies**: Task 4.1, Task 4.2
- **Details**:
  - Start Serena MCP with Ivy LSP configured
  - Test each Serena tool with `.ivy` files:
    - `get_symbols_overview("quic_types.ivy")` -> symbol list
    - `find_symbol("pkt_num")` -> definition with body
    - `find_referencing_symbols("pkt_num", "quic_types.ivy")` -> references
    - `replace_symbol_body("some_action", ...)` -> edit works
    - `insert_after_symbol("some_type", ...)` -> insertion works
  - Verify symbol editing works (replace, insert before/after)
- **Acceptance criteria**:
  - All Serena tools work correctly with `.ivy` files
  - Symbol editing produces valid Ivy code
  - LLM can use Serena to navigate and modify Ivy specifications

### Task 4.6: Documentation
- [ ] **Write usage documentation**
- **Effort**: 2 hours
- **Dependencies**: All Phase 4 tasks
- **Details**:
  - Update `CLAUDE.md` with Ivy LSP information
  - Write `ivy_lsp/README.md`:
    - Installation instructions
    - Serena configuration
    - Supported LSP features
    - Known limitations
    - Troubleshooting
  - Add to panther_ivy's `README.md`
- **Acceptance criteria**:
  - A new developer can set up and use the Ivy LSP from the documentation

---

---

## Phase 5: VSCode Extension

> **Branch**: `feature/ivy-lsp-integration`
> **Design Doc**: `docs/plans/2026-02-25-vscode-extension-design.md`
>
> This phase adds a thin VSCode client extension that connects to the Python LSP server
> (`ivy_lsp/`) over stdio, plus TextMate grammar for syntax highlighting, language
> configuration, and snippets.
>
> **Location**: `panther_ivy/vscode-ivy/`

### Architecture

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

### Directory Structure

```
panther_ivy/vscode-ivy/
  package.json                    # Extension manifest
  tsconfig.json                   # TypeScript config
  language-configuration.json     # Brackets, comments, indentation
  .vscodeignore                   # Exclude source from VSIX
  .eslintrc.json                  # Linting
  README.md                       # Extension readme
  syntaxes/
    ivy.tmLanguage.json           # TextMate grammar (syntax highlighting)
  snippets/
    ivy.json                      # Code snippets
  src/
    extension.ts                  # Activation, LSP client lifecycle
    pythonFinder.ts               # Python + ivy_lsp discovery logic
    test/
      runTest.ts                  # Test runner setup
      suite/
        index.ts                  # Mocha test suite loader
        grammar.test.ts           # Grammar tokenization tests
        extension.test.ts         # Extension activation tests
```

### Task 5.1: Extension Scaffolding
- [ ] **Create directory structure, `package.json`, `tsconfig.json`, `.vscodeignore`**
- **Effort**: 2 hours
- **Dependencies**: None (can start immediately, parallel with Phases 1-4)
- **Files**:
  - `package.json` — Extension manifest with:
    - `name`: `ivy-language`, `displayName`: `Ivy Language`
    - `engines.vscode`: `^1.75.0`
    - `activationEvents`: `["onLanguage:ivy"]`
    - `main`: `./out/extension.js`
    - `contributes.languages`: `id: ivy`, extensions `.ivy`, config `./language-configuration.json`
    - `contributes.grammars`: `scopeName: source.ivy`, path `./syntaxes/ivy.tmLanguage.json`
    - `contributes.snippets`: path `./snippets/ivy.json`
    - `contributes.configuration`: settings for `ivy.pythonPath`, `ivy.lsp.enabled`, `ivy.lsp.args`, `ivy.lsp.trace.server`
    - `dependencies`: `vscode-languageclient ^9.0.1`
    - `devDependencies`: `@types/vscode`, `@types/mocha`, `@types/node`, `typescript`, `@vscode/test-electron`, `@vscode/vsce`, `eslint`, `@typescript-eslint/*`, `mocha`, `vscode-tmgrammar-test`
    - `scripts`: `compile`, `watch`, `lint`, `pretest`, `test`, `vscode:prepublish`
  - `tsconfig.json` — `module: Node16`, `target: ES2022`, `outDir: out`, `rootDir: src`, `strict: true`
  - `.vscodeignore` — Exclude `src/`, `node_modules/`, `*.ts`, `*.map`, `.vscode-test/`
  - `.eslintrc.json` — TypeScript ESLint with `@typescript-eslint/recommended`
- **Acceptance criteria**:
  - `npm install && npm run compile` succeeds
  - `vsce package` produces `.vsix` file
  - Directory structure matches the plan

### Task 5.2: TextMate Grammar
- [ ] **Create `syntaxes/ivy.tmLanguage.json` — complete Ivy syntax highlighting**
- **Effort**: 6 hours
- **Dependencies**: None (parallel with 5.1)
- **Key source**: `ivy/ivy_lexer.py` lines 51-173 for definitive keyword list (80+ keywords)
- **Details**:
  - Root scope: `source.ivy`
  - Pattern priority order (higher first):
    1. `#lang ivy1.7` version pragma -> `keyword.control.directive.ivy` (NOT a comment)
    2. `#` line comments -> `comment.line.number-sign.ivy`
    3. Double-quoted strings -> `string.quoted.double.ivy`
    4. `<<<...>>>` native quotes -> `string.unquoted.native.ivy` (multiline)
    5. Numeric literals: decimal `[0-9]+`, hex `0x[0-9a-fA-F]+` -> `constant.numeric.ivy`
    6. Declaration keywords (30+): `action`, `object`, `module`, `type`, `isolate`, `struct`, `relation`, `function`, `individual`, `axiom`, `conjecture`, `schema`, `instantiate`, `instance`, `derived`, `concept`, `init`, `method`, `field`, `state`, `macro`, `interpret`, `mixin`, `execute`, `destructor`, `constructor`, `definition`, `alias`, `var`, `attribute`, `variant`, `class`, `scenario`, `proof`, `tactic` -> `keyword.declaration.ivy`
    7. Control keywords: `if`, `else`, `while`, `for`, `match`, `call`, `local`, `let`, `entry`, `returns`, `in`, `of` -> `keyword.control.ivy`
    8. Specification keywords: `property`, `invariant`, `axiom`, `conjecture`, `assume`, `assert`, `ensures`, `requires`, `modifies`, `ensure`, `require`, `theorem` -> `keyword.other.specification.ivy`
    9. Quantifiers/temporal: `forall`, `exists`, `globally`, `eventually`, `temporal`, `decreases` -> `keyword.operator.quantifier.ivy`
    10. Scope/module keywords: `export`, `import`, `include`, `using`, `delegate`, `with`, `before`, `after`, `around`, `extract`, `process`, `specification`, `implementation`, `private`, `common`, `global`, `parameter`, `trusted`, `ghost`, `named`, `explicit`, `finite`, `unprovable` -> `keyword.other.ivy`
    11. Boolean/null constants: `true`, `false`, `null`, `this`, `old`, `fresh` -> `constant.language.ivy`
    12. Other reserved: `set`, `update`, `params`, `from`, `some`, `maximizing`, `minimizing`, `implement`, `progress`, `rely`, `mixord`, `apply`, `showgoals`, `defergoal`, `spoil`, `thunk`, `isa`, `autoinstance`, `unfold`, `forget`, `debug`, `subclass`, `whenfirst`, `whenlast`, `whenprev`, `whennext`, `trigger` -> `keyword.other.ivy`
    13. Operators: `:=` (assign), `->` (arrow), `<->` (iff), `&` (and), `|` (or), `~` (tilda), `~=` (tildaeq), `..` (range), `*>` (pto) -> `keyword.operator.ivy`
    14. Uppercase identifiers `[A-Z][_a-zA-Z0-9]*` -> `variable.other.ivy`
    15. Label syntax `[name]` -> `entity.name.tag.ivy`
    16. Type annotations in `name:type` patterns -> `entity.name.type.ivy` for the type part
    17. Unicode temporal operators: `\u25A1` (globally box), `\u25C7` (eventually diamond) -> `keyword.operator.temporal.ivy`
  - Nested scopes:
    - `object name = { ... }` — begin/end with `{ include: "$self" }`
    - `module name = { ... }` — begin/end with `{ include: "$self" }`
    - `struct { ... }` — begin/end with `{ include: "$self" }`
  - **Word boundary**: All keyword patterns use `\b` boundaries to avoid matching inside identifiers (e.g., `property_name` should NOT highlight `property`)
- **Acceptance criteria**:
  - Real files (`quic_types.ivy`, `quic_frame.ivy`) highlight correctly
  - `#lang ivy1.7` is a directive, not a comment
  - Keywords inside identifiers (e.g., `property_name`) are NOT highlighted
  - `<<<...>>>` native quotes highlight as strings
  - Uppercase variables (`X`, `Y`, `Z`) highlight differently from lowercase identifiers
  - Labels `[name]` highlight as tags
  - Comments after `#` are correctly scoped (except `#lang` which is a directive)

### Task 5.3: Language Configuration
- [ ] **Create `language-configuration.json`**
- **Effort**: 1 hour
- **Dependencies**: None (parallel)
- **Details**:
  - Line comment: `#` (prefix `# `)
  - No block comments (Ivy has none)
  - Bracket pairs: `()`, `{}`, `[]`
  - Auto-closing pairs: `()`, `{}`, `[]`, `""`, `<<<` / `>>>`
  - Surrounding pairs: `()`, `{}`, `[]`, `""`, `<<<` / `>>>`
  - `wordPattern`: `[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*` — includes `.` for qualified names like `frame.ack.range`
  - Folding markers: `{` / `}` and `#region` / `#endregion`
  - Indent rules:
    - Increase: lines ending with `= {`, `{`, or `(`
    - Decrease: lines starting with `}` or `)`
  - `onEnterRules`: after `= {$` insert indented newline
- **Acceptance criteria**:
  - `#` toggles line comments
  - `{` auto-closes with `}`
  - Enter after `= {` indents the next line
  - Double-click selects full qualified name (e.g., `frame.ack.range`)
  - Code folding works on `{` / `}` blocks

### Task 5.4: Snippets
- [ ] **Create `snippets/ivy.json` — common Ivy patterns**
- **Effort**: 1 hour
- **Dependencies**: None (parallel)
- **Details**: Snippets with tab stops for:
  - `#lang` pragma: `#lang ivy1.7`
  - `module`: `module $1 = { ... }`
  - `object`: `object $1 = { ... }`
  - `action`: `action $1($2) returns ($3) = { ... }`
  - `type`: `type $1` (simple) and `type $1 = {$2}` (enum)
  - `struct`: `type $1 = struct { $2:$3 }`
  - `isolate`: `isolate $1 = $2 with $3`
  - `property`: `property $1 = $2`
  - `invariant`: `invariant [spec] $1`
  - `after init`: `after init { ... }`
  - `require`/`ensure`: guards
  - `forall`/`exists`: quantifiers
  - `include`: `include $1`
  - `instance`: `instance $1 : $2`
  - `before`/`after` action mixins
- **Acceptance criteria**:
  - Typing prefix + Tab inserts correct template with tab stops
  - All snippets produce valid Ivy syntax
  - Tab stops navigate logically through the template

### Task 5.5: Extension Client (TypeScript)
- [ ] **Create `src/extension.ts` and `src/pythonFinder.ts`**
- **Effort**: 4 hours
- **Dependencies**: Task 5.1 (needs `package.json`), Phase 1 complete (LSP server must be startable)
- **Details**:
  - **`src/pythonFinder.ts`**:
    - `findPython()` function with 5-step discovery:
      1. Check `ivy.pythonPath` setting (if non-empty)
      2. Check workspace `.venv/bin/python` (or `.venv/Scripts/python.exe` on Windows)
      3. Try `python3` on PATH
      4. Try `python` on PATH
      5. Return `undefined` if none found
    - `checkIvyLsp(pythonPath: string): Promise<string | undefined>` — runs `python -c "import ivy_lsp; print(ivy_lsp.__version__)"` and returns version or `undefined`
    - Cache discovered Python path for session
  - **`src/extension.ts`**:
    - `activate(context: ExtensionContext)`:
      1. If `ivy.lsp.enabled` is false, return early (syntax-only mode)
      2. Call `findPython()` to discover Python
      3. If Python not found: show warning, degrade to syntax-only
      4. Call `checkIvyLsp()` to verify `ivy_lsp` is importable
      5. If `ivy_lsp` not found: show error with install instructions (`pip install -e ".[lsp]"`)
      6. Create `LanguageClient` with:
         - `serverOptions`: `{ command: pythonPath, args: ["-m", "ivy_lsp", ...extraArgs] }`
         - `clientOptions`: `{ documentSelector: [{ scheme: "file", language: "ivy" }] }`
         - Trace level from `ivy.lsp.trace.server` setting
      7. Start the client
      8. Create status bar item: `"Ivy LSP: Running"` / `"Ivy LSP: Error"` / `"Ivy LSP: Syntax Only"`
    - `deactivate()`: Stop client, dispose status bar item
    - Config change listener: restart server when `ivy.pythonPath` or `ivy.lsp.args` changes
    - Error handling: auto-restart built into `vscode-languageclient` (3 restarts / 5 min)
- **Acceptance criteria**:
  - Opening `.ivy` file starts LSP server
  - Status bar shows "Ivy LSP: Running"
  - Changing `ivy.pythonPath` restarts the server
  - Clear error messages when Python / `ivy_lsp` not found
  - Extension still provides syntax highlighting when LSP is unavailable

### Task 5.6: Extension Testing
- [ ] **Create test suite for grammar tokenization and extension activation**
- **Effort**: 3 hours
- **Dependencies**: Tasks 5.2, 5.5
- **Details**:
  - **`src/test/runTest.ts`**: Test runner using `@vscode/test-electron` to launch VSCode instance
  - **`src/test/suite/index.ts`**: Mocha test suite loader
  - **`src/test/suite/grammar.test.ts`**: Grammar tokenization tests:
    - Test `#lang ivy1.7` -> `keyword.control.directive.ivy`
    - Test `# comment` -> `comment.line.number-sign.ivy`
    - Test `action foo(x:t)` -> `keyword.declaration.ivy` + `source.ivy`
    - Test `object bar = { }` -> `keyword.declaration.ivy`
    - Test `<<<native code>>>` -> `string.unquoted.native.ivy`
    - Test `X` uppercase -> `variable.other.ivy`
    - Test `[label]` -> `entity.name.tag.ivy`
    - Test `true`, `false` -> `constant.language.ivy`
    - Test `forall`, `exists` -> `keyword.operator.quantifier.ivy`
    - Test `property`, `invariant` -> `keyword.other.specification.ivy`
    - Test keyword inside identifier NOT highlighted (e.g., `property_name` stays `source.ivy`)
  - **`src/test/suite/extension.test.ts`**: Extension activation tests:
    - Test extension activates on `.ivy` file
    - Test configuration reading
    - Test Python finder (mocked)
- **Acceptance criteria**:
  - `npm test` passes
  - Covers 10+ Ivy syntax patterns
  - Tests are reliable (no flaky tests)

### Task 5.7: Integration with setup.py
- [ ] **Update `setup.py` to include `vscode-ivy` as package data**
- **Effort**: 30 min
- **Dependencies**: Task 5.1
- **Details**:
  - Add `"lsp": ["pygls>=1.0", "lsprotocol"]` to `extras_require` in `setup.py`
  - Add entry point: `"ivy_lsp=ivy_lsp.__main__:main"` to `console_scripts`
  - Add `"ivy_lsp"` to the `packages` list (or adjust `find_packages()` to include it)
  - Ensure `vscode-ivy/` is excluded from the Python package (it's a separate Node package)
- **Acceptance criteria**:
  - `pip install -e ".[lsp]"` installs `pygls` and `lsprotocol`
  - `python -m ivy_lsp` starts the language server
  - `ivy_lsp` console script also starts the server

### Task 5.8: End-to-End Testing
- [ ] **Test complete workflow: extension -> LSP -> real Ivy files**
- **Effort**: 3 hours
- **Dependencies**: All Phase 5 tasks + LSP Phases 1-3
- **Details**:
  - Open `quic_types.ivy`, `quic_frame.ivy` in VSCode Development Host
  - Verify syntax highlighting for all element types:
    - `#lang ivy1.7` is a directive (not grayed as comment)
    - `type`, `object`, `action` are keyword-colored
    - `# comments` are comment-colored
    - `<<<...>>>` native quotes are string-colored
    - Uppercase variables are distinctly colored
  - Verify document outline (Cmd+Shift+O) shows symbol hierarchy
  - Verify workspace symbols (Cmd+T) finds symbols across files
  - Test with broken `.ivy` file (fallback symbols should still appear)
  - Test server crash recovery (kill Python process, verify auto-restart)
  - Test syntax-only mode (disable LSP, verify highlighting still works)
- **Acceptance criteria**:
  - All syntax elements highlight correctly
  - Document symbols match the file hierarchy
  - No crashes on the QUIC corpus
  - Server recovers from crashes within 5 seconds

### Task 5.9: Documentation
- [ ] **Write extension README and installation guide**
- **Effort**: 1.5 hours
- **Dependencies**: All Phase 5 tasks
- **Details**:
  - `vscode-ivy/README.md` with:
    - Feature overview (syntax highlighting, LSP features, snippets)
    - Installation methods: VSIX file, from source
    - Configuration reference (all `ivy.*` settings)
    - Prerequisites: Python 3.10+, `ivy_lsp` package
    - Troubleshooting: Python not found, `ivy_lsp` not installed, server crashes
    - Screenshots (placeholder paths for future)
    - Development guide: building, testing, packaging
  - Update `panther_ivy/CLAUDE.md` with VSCode extension information
- **Acceptance criteria**:
  - New developer can install and use the extension from README alone
  - All settings are documented
  - Troubleshooting covers common failure modes

---

### Phase 5 Parallelism

```
5.1 (scaffold) -------> 5.5 (client TS) -------> 5.8 (E2E)
5.2 (grammar)  -------> 5.6 (testing) ----------> 5.9 (docs)
5.3 (lang config) --+
5.4 (snippets) -----+
5.7 (setup.py) -----+
```

Tasks 5.1, 5.2, 5.3, 5.4 can ALL proceed in parallel (no dependencies).
Phase 5 has NO hard dependency on Phases 2-4 — extension works with Phase 1 alone (syntax + document symbols).

---

## Summary

| Phase | Tasks | Estimated Effort |
|-------|-------|-----------------|
| Phase 1: Core Parser + Symbols | 9 tasks | ~26 hours |
| Phase 2: Cross-File Navigation | 6 tasks | ~21 hours |
| Phase 3: Completion + Diagnostics | 4 tasks | ~16 hours |
| Phase 4: Serena Integration | 6 tasks | ~13.5 hours |
| **Phase 5: VSCode Extension** | **9 tasks** | **~22 hours** |
| **Total** | **34 tasks** | **~98.5 hours** |

### Critical Path

```
1.1 -> 1.3 -> 1.4 -> 1.6 -> 2.3 -> 2.4 -> 3.1 -> 4.1 -> 4.5
              |               |
              v               v
             1.5             2.5

5.1 -> 5.5 -> 5.8
5.2 -> 5.6 -> 5.9
```

### Parallelizable Tasks

- Task 1.2 (symbols) and Task 1.8 (position utils) can be done in parallel
- Task 1.4 (AST converter) and Task 1.5 (fallback scanner) can be done in parallel
- Task 2.4 (definition) and Task 2.5 (references) can be done in parallel
- Task 3.1 (completion), Task 3.2 (diagnostics), and Task 3.3 (hover) can be done in parallel
- Task 4.1 (Serena fork) and Task 4.3 (packaging) can be done in parallel
- Tasks 5.1, 5.2, 5.3, 5.4 can ALL proceed in parallel
- Task 5.5 and Task 5.7 can proceed in parallel (both depend on 5.1)

### Critical Files for Phase 5

| File | Purpose |
|------|---------|
| `ivy/ivy_lexer.py` (lines 51-173) | Definitive keyword list for TextMate grammar |
| `ivy_lsp/server.py` | LSP server class the extension spawns |
| `ivy_lsp/__main__.py` | Entry point `python -m ivy_lsp` (interface contract) |
| `ivy_lsp/__init__.py` | Version string (`0.1.0`) checked by Python finder |
| `setup.py` | Package integration (Task 5.7) |
