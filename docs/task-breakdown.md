# panther-ivy-serena Plugin -- Task Breakdown

**Branch**: `feature/ivy-lsp-integration`
**Design Doc**: `panther_ivy/docs/panther-ivy-serena-plugin-design.md`
**Related**: `panther_ivy/docs/plans/TASKS.md` (Ivy LSP tasks -- prerequisite work)

> Each task is a self-contained card that a future Claude session can pick up
> independently. Cards include status, dependencies, files to create, content
> outline, acceptance criteria, and key source files for context.
>
> The implementation order below reflects dependency chains: foundation first,
> then skills (which inform agent prompts), then agents (which reference skills),
> then commands (workflow shortcuts), then hooks (enforcement), and finally
> documentation.

---

## Implementation Order

1. **Task 1**: Repo setup + manifest (foundation)
2. **Tasks 7--13**: Skills first (they inform agent prompts)
3. **Tasks 2--6**: Agents (reference skills in prompts)
4. **Tasks 14--18**: Commands (workflow shortcuts)
5. **Task 19**: Hooks (enforcement layer)
6. **Task 20**: Documentation (this document)

### Dependency Graph

```
Task 1 (manifest)
  |
  +---> Task 7  (NCT skill)        --+
  +---> Task 8  (NACT skill)       --+---> Task 2 (NCT agent)
  +---> Task 9  (NSCT skill)       --+---> Task 3 (NACT agent)
  +---> Task 10 (14-layer skill)   --+---> Task 4 (NSCT agent)
  +---> Task 11 (test-specs skill) --+---> Task 5 (verifier agent)
  +---> Task 12 (RFC mapping skill)--+---> Task 6 (explorer agent)
  +---> Task 13 (serena-for-ivy)   --+
  |
  +---> Task 14 (/nct-check)
  +---> Task 15 (/nct-compile)
  +---> Task 16 (/nct-model-info)
  +---> Task 17 (/nct-new-protocol)  <--- Task 10
  +---> Task 18 (/nct-new-test)      <--- Task 11
  |
  +---> Task 19 (hooks)
  |
  +---> Task 20 (documentation)
```

### Parallelization Notes

- Tasks 7--13 (all skills) have no inter-dependencies and can proceed in parallel.
- Tasks 2--6 (agents) can proceed in parallel once their skill dependencies are met.
- Tasks 14--16 (check/compile/model-info commands) have no inter-dependencies.
- Tasks 17 and 18 depend on specific skills but are independent of each other.

---

## Task 1: Repository Setup & Manifest

- **Status**: todo
- **Dependencies**: None (foundation task)
- **Estimated effort**: 1 hour
- **Files to create**:
  - `panther-ivy-serena/.claude-plugin/plugin.json`
  - `panther-ivy-serena/.mcp.json`
- **Content**:
  - `plugin.json`:
    ```json
    {
      "name": "panther-ivy-serena",
      "version": "0.1.0",
      "description": "Claude Code plugin for NCT/NACT/NSCT methodology guidance for Ivy protocol testing via panther-serena MCP tools",
      "author": "ElNiak",
      "repository": "https://github.com/ElNiak/panther-ivy-serena",
      "license": "MIT",
      "keywords": ["ivy", "protocol-testing", "nct", "nact", "nsct", "formal-verification"]
    }
    ```
  - `.mcp.json`: Declare `panther-serena` as a required MCP server with serena configuration. The server must be reachable so that all Ivy-specific tools (`ivy_check`, `ivy_compile`, `ivy_model_info`) and generic Serena tools (`find_symbol`, `get_symbols_overview`, etc.) are available to agents and commands.
- **Acceptance criteria**:
  - Plugin loads in Claude Code without errors
  - `/plugins` shows `panther-ivy-serena` in the list
  - The MCP server declaration is syntactically valid and points to a working serena configuration
- **Key source files**: None needed, pure scaffold
- **Notes**: This is the only hard prerequisite for all other tasks. Validate the plugin loading mechanism before proceeding.

---

## Task 2: NCT Guide Agent

- **Status**: todo
- **Dependencies**: Task 7 (nct-methodology skill), Task 10 (14-layer-template skill), Task 13 (panther-serena-for-ivy skill)
- **Estimated effort**: 4 hours
- **Files to create**: `panther-ivy-serena/agents/nct-guide.md`
- **Content outline**:
  - Agent frontmatter: name (`nct-guide`), description ("Guides compositional protocol testing using NCT methodology via panther-serena MCP tools"), trigger conditions
  - System prompt must include:
    - MUST use panther-serena MCP tools exclusively (never direct `ivy_check`, `ivyc`, or `ivy_show` CLI calls)
    - Understands the 14-layer formal model template (references skill `14-layer-template`)
    - Workflow: identify protocol -> decompose into 14 layers -> write role-based specs -> generate tests -> verify against IUT
    - Uses serena tools for navigation and editing, ivy tools for verification
    - Protocol-agnostic: works with any protocol using the 14-layer template
  - Key knowledge that must be embedded in the agent prompt:
    - NCT = Network-Centric Compositional Testing: testing by playing one role (client, server, or MIM) against a real implementation under test (IUT)
    - Specifications generate test traffic via Z3/SMT solving against declared constraints
    - Tests monitor actual network packets against specification assertions
    - `before` clauses define preconditions/guards that constrain when actions can fire
    - `after` clauses define state updates and postcondition checks after actions execute
    - `_finalize()` checks verify end-state properties after test completion
    - Role inversion: testing a server means Ivy plays the client role, and vice versa
  - Tools the agent should use:
    - `mcp__plugin_serena_serena__ivy_check` -- formal verification (check isolate assumptions, invariants, safety properties)
    - `mcp__plugin_serena_serena__ivy_compile` -- test compilation (`ivyc target=test`)
    - `mcp__plugin_serena_serena__ivy_model_info` -- model introspection (`ivy_show`)
    - `mcp__plugin_serena_serena__find_symbol` -- navigate to symbol definitions in .ivy files
    - `mcp__plugin_serena_serena__get_symbols_overview` -- list all symbols in a file
    - `mcp__plugin_serena_serena__find_referencing_symbols` -- trace which files/symbols reference a given symbol
    - `mcp__plugin_serena_serena__search_for_pattern` -- regex search across the project
    - `mcp__plugin_serena_serena__read_file` -- read specific sections of .ivy files
    - `mcp__plugin_serena_serena__create_text_file` -- create new .ivy specification files
    - `mcp__plugin_serena_serena__replace_symbol_body` -- edit existing specifications by replacing symbol bodies
  - Trigger conditions: user is doing compositional protocol testing, writing formal specifications, verifying protocol implementations, mentions "NCT", asks about testing from a role perspective
- **Acceptance criteria**:
  - Agent triggers on relevant queries about compositional testing or NCT
  - Agent never suggests direct ivy CLI calls (always uses panther-serena MCP tools)
  - Agent references the 14-layer template when decomposing a new protocol
  - Agent correctly explains role inversion (testing server = Ivy plays client)
  - Agent produces actionable step-by-step guidance for a user starting a new protocol model
- **Key source files to read for context**:
  - `protocol-testing/quic/README.md` -- QUIC specification guide showing real-world NCT structure
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` -- canonical test structure (includes, export actions, `_finalize`)
  - `protocol-testing/formal_model_analysis.md` -- 14-layer architecture documentation
  - `protocol-testing/quic/quic_stack/` -- example core protocol stack files

---

## Task 3: NACT Guide Agent

- **Status**: todo
- **Dependencies**: Task 8 (nact-methodology skill), Task 13 (panther-serena-for-ivy skill)
- **Estimated effort**: 4 hours
- **Files to create**: `panther-ivy-serena/agents/nact-guide.md`
- **Content outline**:
  - Agent frontmatter: name (`nact-guide`), description ("Guides attack-oriented compositional testing using NACT methodology and APT lifecycle via panther-serena MCP tools"), trigger conditions
  - System prompt must include:
    - MUST use panther-serena MCP tools exclusively (never direct ivy CLI calls)
    - Understands the APT (Advanced Persistent Threat) 6-stage lifecycle
    - Workflow: define threat model -> design attack entities -> write attacker specifications -> create attack test scenarios -> verify security properties against IUT
    - Protocol-agnostic attack modeling using the APT template, with protocol-specific bindings
  - Key knowledge that must be embedded in the agent prompt:
    - NACT = Network-Attack Compositional Testing: compositional testing from an attacker's perspective
    - APT 6-stage lifecycle:
      1. **Reconnaissance** (`attack_reconnaissance.ivy`) -- information gathering, probing
      2. **Infiltration** (`attack_infiltration.ivy`) -- initial access, exploitation
      3. **C2 Communication** (`attack_c2_communication.ivy`) -- command and control channels
      4. **Privilege Escalation** (`attack_privilege_escalation.ivy`) -- gaining higher access
      5. **Persistence** (`attack_maintain_persistence.ivy`) -- maintaining access
      6. **Exfiltration** (`attack_exflitration.ivy`) -- data extraction
      - Plus **White Noise** (`attack_white_noise.ivy`) -- distraction/cover traffic
    - Attack entities are defined in `apt/apt_entities/`
    - Test specifications are in `apt/apt_tests/`
    - Protocol-specific bindings exist for: QUIC (`quic_apt_lifecycle/`), MiniP (`minip_apt_lifecycle/`), UDP (`udp_apt_lifecycle/`), Stream Data (`stream_data_apt_lifecycle/`)
    - The attack lifecycle model (`attack_life_cycle.ivy`) orchestrates all stages
    - Network-level primitives: `apt_datagram.ivy`, `apt_packet.ivy`, `apt_attack_connection.ivy`
  - Same serena tools as NCT agent, with particular focus on navigating the `apt/` directory structure
  - Trigger conditions: user is doing attack testing, security testing, threat modeling, APT lifecycle work, mentions "NACT", asks about adversarial testing
- **Acceptance criteria**:
  - Agent triggers on attack/security testing queries or NACT mentions
  - Agent correctly explains all 6 APT lifecycle stages and their purpose
  - Agent understands the relationship between generic lifecycle and protocol-specific bindings
  - Agent never suggests direct ivy CLI calls
  - Agent can guide creation of a new attack scenario from scratch
- **Key source files to read for context**:
  - `protocol-testing/apt/apt_lifecycle/attack_life_cycle.ivy` -- lifecycle orchestration structure
  - `protocol-testing/apt/apt_lifecycle/attack_reconnaissance.ivy` -- example single stage implementation
  - `protocol-testing/apt/apt_lifecycle/quic_apt_lifecycle/` -- QUIC-specific APT bindings
  - `protocol-testing/apt/apt_lifecycle/attack_white_noise.ivy` -- distraction attack pattern

---

## Task 4: NSCT Guide Agent

- **Status**: todo
- **Dependencies**: Task 9 (nsct-methodology skill), Task 13 (panther-serena-for-ivy skill)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/agents/nsct-guide.md`
- **Content outline**:
  - Agent frontmatter: name (`nsct-guide`), description ("Guides simulation-centric compositional testing using NSCT methodology with Shadow Network Simulator via panther-serena MCP tools"), trigger conditions
  - System prompt must include:
    - MUST use panther-serena MCP tools for all Ivy-related operations
    - Understands Shadow Network Simulator integration with PANTHER
    - Workflow: define network topology -> configure simulation parameters -> set up protocol implementations as Ivy models -> run simulation-based verification -> analyze results
    - Explains when NSCT complements or replaces NCT
  - Key knowledge that must be embedded in the agent prompt:
    - NSCT = Network-Simulator Centric Compositional Testing: compositional testing in deterministic simulated network environments
    - Shadow NS provides deterministic replay of network conditions (latency, loss, bandwidth)
    - Enables testing at scale with multiple concurrent protocol participants
    - Configuration via PANTHER experiment configs with `network_environment.type: shadow_ns`
    - Complements NCT by adding controlled network conditions (NCT uses Docker Compose with real networking; NSCT uses Shadow for deterministic simulation)
    - Build mode for Shadow compatibility: empty string `""` (legacy `mk_make.py` for Z3, see `build_submodules.py`)
    - The `system/` directory in `protocol-testing/` contains system-level models for NSCT scenarios (currently placeholder `.gitkeep` files)
  - Trigger conditions: user mentions simulation, Shadow NS, network topology, large-scale testing, deterministic testing, mentions "NSCT"
- **Acceptance criteria**:
  - Agent triggers on simulation-related queries or NSCT mentions
  - Agent correctly explains NSCT methodology and its relationship to NCT
  - Agent can guide Shadow NS configuration within PANTHER
  - Agent explains when to choose NSCT over NCT (determinism, scale, network conditions)
- **Key source files to read for context**:
  - PANTHER experiment config examples with `shadow_ns` network environment type
  - `panther/plugins/environments/` -- environment plugin implementations in parent PANTHER project
  - `protocol-testing/system/` -- system-level model directory (template/placeholder)
  - `build_submodules.py` -- build mode documentation including Shadow-compatible mode

---

## Task 5: Spec Verifier Agent

- **Status**: todo
- **Dependencies**: Task 13 (panther-serena-for-ivy skill)
- **Estimated effort**: 4 hours
- **Files to create**: `panther-ivy-serena/agents/spec-verifier.md`
- **Content outline**:
  - Agent frontmatter: name (`spec-verifier`), description ("Runs formal verification checks on Ivy specifications, interprets results, and suggests fixes for failures"), trigger conditions
  - This is a workflow agent (not methodology): it runs checks, parses and interprets results, and suggests concrete fixes
  - Core workflow:
    1. Use `mcp__plugin_serena_serena__ivy_check` -> parse stdout/stderr -> identify isolate violations, invariant failures, type errors, and safety property violations
    2. Use `mcp__plugin_serena_serena__ivy_compile` -> check compilation success -> report build errors with context
    3. Use `mcp__plugin_serena_serena__ivy_model_info` -> show model structure for debugging and understanding isolate boundaries
    4. Cross-reference failures with spec structure using `find_symbol` and `get_symbols_overview` to locate the offending code
  - Key knowledge that must be embedded in the agent prompt:
    - `ivy_check` output format: isolate assumption violations, invariant violations, safety property violations; each with file:line references
    - `ivyc` error format: type errors, unresolved symbols, missing includes, compilation failures with C++ backend errors
    - Common failure patterns and their fixes:
      - "isolate X has no implementation for action Y" -- missing `implement` block or `with` clause
      - "invariant [name] failed" -- invariant does not hold; need to strengthen preconditions or weaken the invariant
      - "type mismatch" -- parameter type does not match expected signature
      - "unresolved symbol" -- missing `include` or the symbol is not exported
      - "assumption not satisfied" -- isolate's assumptions are not proved by its context
    - How to isolate which layer/module causes a failure: check isolate boundaries, trace include dependencies
    - Relationship between compilation targets and test types: `target=test` produces test executables; different isolates test different aspects
  - Trigger conditions: user wants to verify a spec, has compilation errors, needs to diagnose test failures, asks "why does ivy_check fail", mentions verification
- **Acceptance criteria**:
  - Agent triggers on verification/compilation queries
  - Agent presents results in a structured PASS/FAIL format with clear error categorization
  - Agent suggests concrete fixes for the top 5 most common failure patterns
  - Agent uses `find_symbol` to navigate to the failing code location
  - Agent never suggests running `ivy_check` or `ivyc` directly in bash
- **Key source files to read for context**:
  - `/private/tmp/claude-501/panther-serena-clone/src/serena/tools/ivy_tools.py` -- tool API reference (parameter signatures, return format)
  - `protocol-testing/quic/quic_tests/` -- real test files that can fail verification

---

## Task 6: Spec Explorer Agent

- **Status**: todo
- **Dependencies**: Task 10 (14-layer-template skill), Task 13 (panther-serena-for-ivy skill)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/agents/spec-explorer.md`
- **Content outline**:
  - Agent frontmatter: name (`spec-explorer`), description ("Navigates and explains existing Ivy protocol specifications using semantic tools"), trigger conditions
  - Uses Serena symbolic navigation tools exclusively:
    - `find_symbol` -- jump to any symbol definition
    - `get_symbols_overview` -- list all symbols in a file
    - `find_referencing_symbols` -- trace all references to a symbol
    - `search_for_pattern` -- regex search across the project
    - `read_file` -- read specific file sections
  - Understands the `protocol-testing/` directory layout per protocol:
    ```
    protocol-testing/{protocol}/
      {prot}_stack/          -- Core protocol model
      {prot}_tests/          -- Test specifications
        server_tests/        -- Tests where Ivy plays client
        client_tests/        -- Tests where Ivy plays server
        mim_tests/           -- Man-in-the-middle tests
      {prot}_shims/          -- Implementation bridge
      {prot}_attacks_stack/  -- Attack models (optional)
      tls_stack/ or dtls_stack/ -- Security sub-protocol (optional)
    ```
  - Can explain what each of the 14 layers does, how layers relate to each other, what tests exist for each protocol feature
  - Key knowledge that must be embedded:
    - Naming conventions: `{prot}_*.ivy` for stack files, `ivy_{prot}_{role}.ivy` for entity definitions, `{prot}_{role}_test*.ivy` for test files
    - How `include` directives create dependency chains between .ivy files
    - How to find which tests exercise which protocol features by tracing symbol references
    - The distinction between `specification` blocks (abstract interface) and `implementation` blocks (concrete behavior)
    - How `isolate` declarations partition the model into verifiable components
  - Trigger conditions: user wants to understand existing specs, onboard to a protocol, explore dependencies, asks "what does X do", "where is Y defined", "what tests exist for Z"
- **Acceptance criteria**:
  - Agent navigates the codebase exclusively using serena symbolic tools (never `cat`, `grep`, `find`)
  - Agent can explain protocol structure at any level of detail (high-level architecture to single-action semantics)
  - Agent correctly traces include dependency chains
  - Agent identifies which tests cover a given protocol feature
- **Key source files to read for context**:
  - `protocol-testing/formal_model_analysis.md` -- 14-layer architecture documentation
  - `protocol-testing/quic/` -- most complete protocol implementation for reference
  - `protocol-testing/quic/quic_stack/` -- core stack example
  - `protocol-testing/quic/quic_tests/server_tests/` -- test file examples

---

## Task 7: NCT Methodology Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational, no dependency on Task 1)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/skills/nct-methodology/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`nct-methodology`), description, triggers: `["compositional testing", "protocol specification", "formal verification", "NCT", "network-centric testing", "role-based testing"]`
  - Section: What is NCT
    - Compositional role-based testing from formal specifications
    - Ivy plays one protocol role (client, server, or MIM) against a real IUT
    - Z3/SMT solver generates test traffic satisfying formal constraints
    - Network monitors verify IUT responses against specification assertions
    - Deterministic by seed: same random seed produces the same test sequence
  - Section: NCT workflow step by step
    1. Select target protocol and RFC(s)
    2. Decompose into the 14 formal layers (reference 14-layer-template skill)
    3. Write type definitions first (`{prot}_types.ivy`) -- this is the foundation all other layers import
    4. Build up through layers: frames -> packets -> protection -> connection
    5. Define entity roles: client (`ivy_{prot}_client.ivy`), server (`ivy_{prot}_server.ivy`), optionally MIM
    6. Write behavioral constraints using `before`/`after` monitors and FSM modules
    7. Create test specifications (`{prot}_tests/server_tests/`, `{prot}_tests/client_tests/`)
    8. Compile and run via panther-serena tools
  - Section: Serena tools for each step
    - Step 1-2: `search_for_pattern`, `get_symbols_overview` to explore existing models
    - Step 3-6: `create_text_file` for new files, `replace_symbol_body` for edits
    - Step 7: `create_text_file` with test template structure
    - Step 8: `ivy_check` for verification, `ivy_compile` for test binary generation
  - Section: Example walkthrough using QUIC as reference
    - Brief annotated walkthrough of `quic_server_test.ivy` showing the test structure
- **Acceptance criteria**:
  - Skill auto-activates when user mentions "compositional testing", "NCT", or "formal verification" in context
  - Content is accurate against the actual protocol-testing directory structure
  - Workflow steps are actionable (a user can follow them to create a new protocol model)
  - Serena tool mapping is correct for each workflow step
- **Key source files to read for context**:
  - `protocol-testing/quic/README.md` -- QUIC specification guide
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` -- canonical test file structure
  - `protocol-testing/formal_model_analysis.md` -- 14-layer reference

---

## Task 8: NACT Methodology Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/skills/nact-methodology/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`nact-methodology`), description, triggers: `["attack testing", "APT", "threat modeling", "security verification", "NACT", "adversarial testing", "attack lifecycle"]`
  - Section: What is NACT
    - Attack-oriented compositional testing extending NCT with adversarial entities
    - Ivy models an attacker following the APT lifecycle against a real IUT
    - Combines formal attack specification with network-level verification
  - Section: APT lifecycle (6 stages explained in detail)
    1. **Reconnaissance** -- Information gathering about the target; probing services, version detection, capability enumeration. File: `attack_reconnaissance.ivy`
    2. **Infiltration** -- Initial access and exploitation; crafting malicious packets, exploiting vulnerabilities. File: `attack_infiltration.ivy`
    3. **C2 Communication** -- Establishing command and control channels; covert communication, protocol tunneling. File: `attack_c2_communication.ivy`
    4. **Privilege Escalation** -- Gaining higher access; exploiting state machine flaws, authentication bypasses. File: `attack_privilege_escalation.ivy`
    5. **Persistence** -- Maintaining access across sessions; connection migration abuse, state manipulation. File: `attack_maintain_persistence.ivy`
    6. **Exfiltration** -- Data extraction; covert channels, protocol abuse for data leakage. File: `attack_exflitration.ivy`
    - Plus **White Noise** -- Distraction and cover traffic to mask attack activity. File: `attack_white_noise.ivy`
  - Section: Designing attacker entities in Ivy
    - Entity definition pattern in `apt_entities/`
    - How attacker actions relate to lifecycle stages
    - Relationship between attacker entities and target protocol entities
  - Section: Writing attack test specifications
    - Test file organization in `apt_tests/`
    - How to specify expected attack outcomes
    - Asserting security property violations
  - Section: Protocol-specific attack bindings
    - How to create protocol-specific lifecycle bindings (e.g., `quic_apt_lifecycle/`)
    - Mapping generic APT stages to protocol-specific attack vectors
  - Section: Example
    - Brief walkthrough of QUIC APT lifecycle tests
- **Acceptance criteria**:
  - Skill auto-activates on attack/APT/security testing queries
  - All 6 lifecycle stages plus white noise are accurately described
  - Content matches the actual file structure in `protocol-testing/apt/apt_lifecycle/`
  - Protocol-specific binding mechanism is correctly explained
- **Key source files to read for context**:
  - `protocol-testing/apt/apt_lifecycle/attack_life_cycle.ivy` -- lifecycle orchestration
  - `protocol-testing/apt/apt_lifecycle/attack_reconnaissance.ivy` -- single stage example
  - `protocol-testing/apt/apt_lifecycle/quic_apt_lifecycle/` -- QUIC-specific bindings
  - `protocol-testing/apt/apt_lifecycle/apt_datagram.ivy` -- network-level primitives

---

## Task 9: NSCT Methodology Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 2 hours
- **Files to create**: `panther-ivy-serena/skills/nsct-methodology/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`nsct-methodology`), description, triggers: `["simulation", "Shadow NS", "network simulator", "NSCT", "deterministic testing", "large-scale testing"]`
  - Section: What is NSCT
    - Simulation-centric compositional testing using Shadow Network Simulator
    - Deterministic replay of network conditions for reproducible protocol testing
    - Enables testing at scale: multiple concurrent participants, varied topologies
  - Section: Shadow NS integration with PANTHER
    - PANTHER's `shadow_ns` environment plugin (vs `docker_compose` for NCT)
    - Configuration via experiment YAML with `network_environment.type: shadow_ns`
    - Shadow provides virtual time, deterministic packet scheduling, configurable link properties
  - Section: Configuring network topologies
    - Topology definition in PANTHER experiment configs
    - Link parameters: latency, bandwidth, packet loss
    - Node placement and routing
  - Section: Running simulation-based protocol tests
    - Build mode compatibility: empty string `""` for Shadow-compatible Z3 build
    - How Ivy models interact with Shadow-simulated network
    - Collecting and analyzing simulation traces
  - Section: Analyzing simulation results
    - Trace file formats
    - Comparing deterministic runs
    - Debugging with deterministic replay
  - Section: When to use NSCT vs NCT
    - NCT: real network stack, Docker isolation, testing individual IUTs, fast iteration
    - NSCT: simulated network, deterministic replay, testing at scale, controlled conditions
    - NSCT complements NCT; both can be used for the same protocol
- **Acceptance criteria**:
  - Skill auto-activates on simulation/Shadow NS queries
  - Correctly distinguishes NSCT from NCT with clear decision criteria
  - Build mode compatibility note is accurate
  - Configuration guidance matches PANTHER's actual experiment config format
- **Key source files to read for context**:
  - PANTHER Shadow NS environment plugin in `panther/plugins/environments/`
  - PANTHER experiment config examples
  - `build_submodules.py` -- build mode table (Shadow compatibility)

---

## Task 10: 14-Layer Template Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 4 hours
- **Files to create**: `panther-ivy-serena/skills/14-layer-template/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`14-layer-template`), description, triggers: `["creating new protocol model", "protocol specification", "layer architecture", "14 layers", "protocol template", "scaffolding"]`
  - Section: 14 layers listed with purpose
    - **Core Protocol Stack (Layers 1--9, always required)**:
      1. Type Definitions (`{prot}_types.ivy`) -- Identifiers, bit vectors, enumerations; foundation all other layers import
      2. Application Layer (`{prot}_application.ivy`) -- Data transfer semantics, payload handling
      3. Security/Handshake Layer (`{prot}_security.ivy`) -- Key establishment, handshake state machine
      4. Frame/Message Layer (`{prot}_frame.ivy`) -- Protocol data unit definitions; where protocol semantics live
      5. Packet Layer (`{prot}_packet.ivy`) -- Wire-level packet structure, headers
      6. Protection Layer (`{prot}_protection.ivy`) -- Encryption/decryption of packets
      7. Connection/State Management (`{prot}_connection.ivy`) -- Session lifecycle, state machine
      8. Transport Parameters (`{prot}_transport_parameters.ivy`) -- Negotiable session parameters
      9. Error Handling (`{prot}_error_code.ivy`) -- Error taxonomy and error generation
    - **Entity Model (Layers 10--12, always required)**:
      10. Entity Definitions (`ivy_{prot}_{role}.ivy`) -- Network participant instances (client, server, MIM)
      11. Entity Behavior (`ivy_{prot}_{role}_behavior.ivy`) -- FSM and behavioral constraints (before/after monitors)
      12. Shims (`{prot}_shim.ivy`) -- Implementation bridge between Ivy model and real network
    - **Infrastructure (Layers 13--14, mostly reusable)**:
      13. Serialization/Deserialization (`{prot}_ser.ivy`, `{prot}_deser.ivy`) -- Wire format encoding/decoding
      14. Utilities (`byte_stream.ivy`, `file.ivy`, `time.ivy`, `random_value.ivy`, `locale.ivy`) -- Shared helpers
  - Section: File naming convention per layer
    - Stack files: `{prot}_{layer_name}.ivy` (e.g., `quic_types.ivy`, `quic_frame.ivy`)
    - Entity files: `ivy_{prot}_{role}.ivy` (e.g., `ivy_quic_client.ivy`)
    - Behavior files: `ivy_{prot}_{role}_behavior.ivy`
    - Test files: `{prot}_{role}_test*.ivy` (e.g., `quic_server_test.ivy`)
    - Shim files: `{prot}_shim.ivy`
  - Section: Dependencies between layers (include chain)
    - Types (L1) imported by all layers
    - Frame (L4) imports Types (L1)
    - Packet (L5) imports Frame (L4) + Types (L1)
    - Protection (L6) imports Packet (L5) + Security (L3)
    - Connection (L7) imports most lower layers
    - Entity (L10) imports Connection (L7) + Shim (L12)
    - Test files import Entity (L10) + Behavior (L11)
    - Provide a directed dependency diagram
  - Section: How to scaffold a new protocol
    - Minimal viable set: Types (L1) + Frame (L4) + Entity (L10) + Shim (L12) + one test file
    - Incremental expansion from minimal set
    - Reference `protocol-testing/new_prot/` template directory structure:
      ```
      new_prot/
        new_prot.md           -- Protocol-specific notes
        new_prot_entities/    -- Entity definitions (L10-11)
        new_prot_shims/       -- Shim layer (L12)
        new_prot_stack/       -- Core protocol stack (L1-9)
        new_prot_utils/       -- Utilities (L14)
      ```
  - Section: Optional layers
    - Security Sub-Protocol (`tls_stack/` or `dtls_stack/`) -- when protocol uses TLS/DTLS
    - FSM Modules (`{prot}_fsm/`) -- explicit finite state machine modeling
    - Recovery/Congestion (`{prot}_recovery/`, `{prot}_congestion/`) -- transport reliability
    - Extensions (`{prot}_extensions/`) -- protocol extensions and options
    - Attacks Stack (`{prot}_attacks_stack/`) -- security/attack formal models
    - Stream/Flow Management (`{prot}_stream.ivy`) -- stream multiplexing
  - Section: Decision matrix for template selection by protocol category
    - Connection-Oriented Transport (SSH, SMTP, FTP): replace UDP with TCP stream handling, simplify packet layer
    - Publish/Subscribe (MQTT, AMQP): add topic/subscription management, broker entity
    - Routing Protocols (OSPF, IS-IS): add RIB, symmetric peer entities
    - Real-Time Media (RTP, WebRTC): add timing models, companion control protocol
    - IoT/Constrained (CoAP, LwM2M): add block-wise transfer, observe pattern
- **Acceptance criteria**:
  - All 14 layers accurately described with naming conventions matching actual codebase
  - Dependency chain is correct (verified against actual `include` directives in QUIC model)
  - Template directory `new_prot/` structure matches the actual filesystem
  - Decision matrix covers at least 5 protocol categories with actionable adaptations
- **Key source files to read for context**:
  - `protocol-testing/formal_model_analysis.md` -- primary reference document
  - `protocol-testing/new_prot/` -- template directory structure
  - `protocol-testing/quic/quic_stack/` -- most complete real implementation
  - `protocol-testing/bgp/` -- partial implementation for comparison

---

## Task 11: Writing Test Specs Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/skills/writing-test-specs/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`writing-test-specs`), description, triggers: `["writing test files", "monitors", "assertions", "before/after", "_finalize", "test specification", "ivy test"]`
  - Section: Test specification structure in Ivy
    - Header: `#lang ivy1.7`
    - Include directives: import protocol stack, entities, shims
    - `object` declaration wrapping the test
    - `export` declarations for actions the environment can call
    - `import` declarations for actions the test uses
    - Main test body with `before`/`after` monitors
    - `_finalize()` action for end-state checks
  - Section: `before` clauses (preconditions/guards)
    - Syntax: `before {action_name} { ... }`
    - Purpose: constrain when an action can fire; define preconditions
    - Example: `before packet.send(pkt) { require pkt.valid; }`
    - Can modify parameters before the action executes
    - Used for input validation, state precondition checks
  - Section: `after` clauses (state updates/checks)
    - Syntax: `after {action_name} { ... }`
    - Purpose: verify postconditions, update specification state
    - Example: `after packet.recv(pkt) { assert pkt.pkt_num > last_seen_pkt_num; }`
    - Used for protocol compliance verification, state machine transitions
  - Section: `_finalize()` end-state verification
    - Called after all test iterations complete
    - Checks protocol-level invariants that must hold at test termination
    - Example: all streams closed, no pending data, connection properly terminated
    - Structure: `action _finalize = { assert ...; assert ...; }`
  - Section: Role isolation
    - `client_test`: Ivy acts as client, tests a real server
    - `server_test`: Ivy acts as server, tests a real client
    - `mim_test`: Ivy acts as man-in-the-middle, tests both endpoints
    - Directory organization: `{prot}_tests/server_tests/`, `{prot}_tests/client_tests/`, `{prot}_tests/mim_tests/`
  - Section: Test variants and parameterization
    - Weight attributes on test actions (e.g., `attribute [weight] = "3"`)
    - How weights influence Z3 test generation
    - Seed-based determinism: `--seed` parameter for reproducible tests
    - Iteration control: `--iters` for number of test iterations
  - Section: Common patterns from protocol-testing/ examples
    - Testing handshake completion
    - Testing data transfer correctness
    - Testing error handling
    - Testing state machine transitions
  - Section: Mapping RFC MUST/SHOULD/MAY to test assertions
    - MUST -> `assert` in `after` clause (hard failure)
    - SHOULD -> `assert` with warning annotation or conditional check
    - MAY -> optional behavior test with branching
- **Acceptance criteria**:
  - Provides actionable guidance sufficient to write a new test spec from scratch
  - All Ivy test syntax is correctly described (verified against actual test files)
  - Weight attribute syntax matches actual usage in the codebase
  - RFC mapping methodology is practical and referenced to real examples
- **Key source files to read for context**:
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` -- canonical structure
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test_stream.ivy` -- weight attributes
  - `protocol-testing/quic/quic_tests/client_tests/` -- client-side test examples
  - `protocol-testing/quic/quic_tests/mim_tests/` -- MIM test examples

---

## Task 12: RFC-to-Ivy Mapping Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/skills/rfc-to-ivy-mapping/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`rfc-to-ivy-mapping`), description, triggers: `["translating RFC", "requirements extraction", "specification mapping", "RFC to Ivy", "MUST SHOULD MAY", "formal requirements"]`
  - Section: Reading RFC requirements
    - MUST/MUST NOT: mandatory behavior; violation is non-compliance
    - SHOULD/SHOULD NOT: recommended behavior; deviation requires justification
    - MAY: optional behavior; implementation choice
    - How to extract testable requirements from RFC prose
  - Section: Identifying testable properties
    - Not all RFC statements are directly testable
    - Properties that can be observed on the wire (packet contents, timing, state)
    - Properties that require internal state access (via shims)
    - Properties that are inherently untestable from the network (internal implementation choices)
  - Section: Mapping to Ivy constructs
    - Invariants (`invariant [name] ...`) -- properties that must hold at all times
    - Monitors (`before`/`after` clauses) -- properties checked at specific protocol events
    - Actions (`action name(...) = { ... }`) -- protocol operations with pre/postconditions
    - Types and enumerations -- protocol data structure definitions
    - Relations (`relation name(x:T, y:U)`) -- state tracking (e.g., "connection X is in state Y")
  - Section: `before`/`after` pattern for protocol events
    - Identify the protocol event (e.g., "when a server receives a ClientHello")
    - Write `after` clause on the corresponding action
    - Add `assert` for MUST requirements, conditional checks for SHOULD
    - Update specification state (relations, variables) to track protocol progress
  - Section: Example -- RFC 9000 requirement to Ivy specification
    - Pick a specific RFC 9000 requirement (e.g., "A server MUST discard an Initial packet that is received in a UDP datagram smaller than 1200 bytes")
    - Show the original RFC text
    - Show the Ivy specification that tests this requirement
    - Explain each part of the mapping
  - Section: Using `new_requirements_rfc9000.txt` as reference
    - How the requirements file is structured
    - How to cross-reference with Ivy specifications
    - Gap analysis: finding untested requirements
- **Acceptance criteria**:
  - Clear methodology for RFC-to-Ivy translation that a user can follow
  - Example mapping is accurate against actual QUIC specification files
  - RFC requirement levels (MUST/SHOULD/MAY) correctly map to Ivy assertion types
  - References to `new_requirements_rfc9000.txt` are accurate
- **Key source files to read for context**:
  - `protocol-testing/quic/new_requirements_rfc9000.txt` -- requirements extraction reference
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` -- requirement implementation
  - `protocol-testing/quic/quic_stack/quic_frame.ivy` -- frame-level requirement mapping

---

## Task 13: Panther-Serena for Ivy Skill

- **Status**: todo
- **Dependencies**: None (skills are foundational)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/skills/panther-serena-for-ivy/SKILL.md`
- **Content outline**:
  - Skill frontmatter: name (`panther-serena-for-ivy`), description, triggers: `["ivy", "serena", "tool guidance", "how to use serena", "MCP tools", "panther-serena"]`
  - Section: Why use panther-serena (not direct CLI)
    - Consistency: all operations go through the same tool interface
    - Tool tracking: operations are logged and auditable
    - Semantic navigation: symbol-aware operations vs text-based grep/cat
    - Safety: panther-serena validates paths and parameters
    - Integration: works within the Claude Code agent loop with structured output
  - Section: Tool mapping table (CLI -> MCP tool)

    | CLI Command | MCP Tool | Description |
    |---|---|---|
    | `ivy_check file.ivy` | `mcp__plugin_serena_serena__ivy_check` | Formal verification |
    | `ivyc target=test file.ivy` | `mcp__plugin_serena_serena__ivy_compile` | Compile to test binary |
    | `ivy_show file.ivy` | `mcp__plugin_serena_serena__ivy_model_info` | Model structure display |
    | `cat file.ivy` | `mcp__plugin_serena_serena__read_file` | Read file contents |
    | `grep pattern *.ivy` | `mcp__plugin_serena_serena__search_for_pattern` | Pattern search |
    | Manual symbol lookup | `mcp__plugin_serena_serena__find_symbol` | Semantic symbol navigation |
    | Manual file structure | `mcp__plugin_serena_serena__get_symbols_overview` | File symbol listing |
    | Manual reference trace | `mcp__plugin_serena_serena__find_referencing_symbols` | Reference tracking |
    | `echo "..." > file.ivy` | `mcp__plugin_serena_serena__create_text_file` | Create new spec file |
    | Manual edit | `mcp__plugin_serena_serena__replace_symbol_body` | Edit symbol body |
    | Manual insert | `mcp__plugin_serena_serena__insert_after_symbol` / `insert_before_symbol` | Insert adjacent to symbol |

  - Section: Recommended workflow pattern
    1. **Navigate** with `find_symbol` / `get_symbols_overview` -- understand the model
    2. **Understand** with `read_file` / `find_referencing_symbols` -- trace dependencies
    3. **Edit** with `replace_symbol_body` / `create_text_file` -- modify or create specs
    4. **Verify** with `ivy_check` / `ivy_compile` -- check correctness
  - Section: Prerequisites
    - `ivy_lsp` installed (`pip install -e ".[lsp]"` from panther_ivy)
    - `ivy` listed in `.serena/project.yml` `languages` list
    - panther-serena MCP server running and accessible
  - Section: Tool parameter reference (from `ivy_tools.py`)
    - `ivy_check`:
      - `relative_path: str` -- relative path to .ivy file (required)
      - `isolate: str | None` -- optional isolate name to check in isolation
      - `max_answer_chars: int` -- output length limit (-1 for default)
      - Returns: JSON with stdout, stderr, return code
    - `ivy_compile`:
      - `relative_path: str` -- relative path to .ivy file (required)
      - `target: str` -- compilation target, default `"test"` (required)
      - `isolate: str | None` -- optional isolate name
      - `max_answer_chars: int` -- output length limit
      - Returns: JSON with stdout, stderr, return code
    - `ivy_model_info`:
      - `relative_path: str` -- relative path to .ivy file (required)
      - `isolate: str | None` -- optional isolate name
      - `max_answer_chars: int` -- output length limit
      - Returns: JSON with stdout, stderr, return code
  - Section: Common usage patterns
    - Check a specific isolate: `ivy_check` with `isolate="protocol_model"`
    - Compile for testing: `ivy_compile` with `target="test"`
    - Explore model before editing: `ivy_model_info` -> `get_symbols_overview` -> `find_symbol`
    - Trace a failure: `ivy_check` -> parse error -> `find_symbol` to navigate to error location
- **Acceptance criteria**:
  - Complete tool mapping table covering all Ivy-related operations
  - API signatures match actual `ivy_tools.py` implementation exactly
  - Prerequisites are accurate (verified against actual Serena configuration)
  - Workflow pattern is practical and follows the navigate-understand-edit-verify cycle
- **Key source files to read for context**:
  - `/private/tmp/claude-501/panther-serena-clone/src/serena/tools/ivy_tools.py` -- definitive tool API
  - `.serena/project.yml` -- Serena project configuration
  - `panther_ivy/CLAUDE.md` -- Ivy CLI tool reference

---

## Task 14: /nct-check Command

- **Status**: todo
- **Dependencies**: Task 1 (manifest)
- **Estimated effort**: 1 hour
- **Files to create**: `panther-ivy-serena/commands/nct-check.md`
- **Content outline**:
  - Command frontmatter: name (`nct-check`), description ("Run ivy_check on an Ivy specification file via panther-serena")
  - Command accepts arguments:
    - `<file>` -- relative path to the .ivy file (required)
    - `--isolate <name>` -- optional isolate name to check in isolation
  - Prompt template:
    1. Parse the user's arguments to extract `file` and optional `isolate`
    2. Call `mcp__plugin_serena_serena__ivy_check` with `relative_path=<file>` and optionally `isolate=<name>`
    3. Parse the JSON result (stdout, stderr, return code)
    4. Present results in structured format:
       - If return code 0: "PASS: All checks succeeded for `<file>`" followed by any stdout notes
       - If return code non-zero: "FAIL: Verification errors in `<file>`" followed by parsed error details from stderr
    5. For failures, suggest next steps: use `find_symbol` to navigate to the error location, common fix patterns
- **Acceptance criteria**:
  - `/nct-check protocol-testing/quic/quic_stack/quic_types.ivy` executes successfully
  - Results are presented in PASS/FAIL format
  - Optional `--isolate` parameter is correctly passed through
  - Errors include file:line references when available
- **Key source files**: `ivy_tools.py` `IvyCheckTool.apply()` for parameter reference

---

## Task 15: /nct-compile Command

- **Status**: todo
- **Dependencies**: Task 1 (manifest)
- **Estimated effort**: 1 hour
- **Files to create**: `panther-ivy-serena/commands/nct-compile.md`
- **Content outline**:
  - Command frontmatter: name (`nct-compile`), description ("Compile an Ivy specification file to a test executable via panther-serena")
  - Command accepts arguments:
    - `<file>` -- relative path to the .ivy file (required)
    - `--target <type>` -- compilation target, default `"test"` (optional)
    - `--isolate <name>` -- optional isolate name
  - Prompt template:
    1. Parse arguments to extract `file`, `target` (default `"test"`), and optional `isolate`
    2. Call `mcp__plugin_serena_serena__ivy_compile` with `relative_path=<file>`, `target=<target>`, and optionally `isolate=<name>`
    3. Parse the JSON result
    4. Present results:
       - Success: "Compilation succeeded for `<file>` (target: `<target>`)" with output path if available
       - Failure: "Compilation failed for `<file>`" with parsed error details
    5. For failures, suggest fixes based on common compilation error patterns
- **Acceptance criteria**:
  - `/nct-compile protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` executes
  - Default target is `"test"`
  - Success/failure is clearly reported
  - Compilation errors are parsed and presented readably
- **Key source files**: `ivy_tools.py` `IvyCompileTool.apply()` for parameter reference

---

## Task 16: /nct-model-info Command

- **Status**: todo
- **Dependencies**: Task 1 (manifest)
- **Estimated effort**: 1 hour
- **Files to create**: `panther-ivy-serena/commands/nct-model-info.md`
- **Content outline**:
  - Command frontmatter: name (`nct-model-info`), description ("Display the structure of an Ivy model via panther-serena")
  - Command accepts arguments:
    - `<file>` -- relative path to the .ivy file (required)
    - `--isolate <name>` -- optional isolate name to display information about
  - Prompt template:
    1. Parse arguments to extract `file` and optional `isolate`
    2. Call `mcp__plugin_serena_serena__ivy_model_info` with `relative_path=<file>` and optionally `isolate=<name>`
    3. Parse the JSON result
    4. Present a readable summary:
       - Types defined in the model
       - Actions and their signatures
       - Relations and their parameters
       - Invariants and properties
       - Isolate boundaries
    5. If the output is large, organize by category (types, actions, relations, invariants, isolates)
- **Acceptance criteria**:
  - `/nct-model-info protocol-testing/quic/quic_stack/quic_types.ivy` displays model structure
  - Output is organized and readable (not raw JSON dump)
  - Optional `--isolate` parameter works correctly
  - Large models are presented in categorized sections
- **Key source files**: `ivy_tools.py` `IvyModelInfoTool.apply()` for parameter reference

---

## Task 17: /nct-new-protocol Command

- **Status**: todo
- **Dependencies**: Task 1 (manifest), Task 10 (14-layer-template skill for template content)
- **Estimated effort**: 3 hours
- **Files to create**: `panther-ivy-serena/commands/nct-new-protocol.md`
- **Content outline**:
  - Command frontmatter: name (`nct-new-protocol`), description ("Scaffold a new protocol specification using the 14-layer template")
  - Interactive scaffolding workflow:
    1. Ask for protocol full name (e.g., "Quick UDP Internet Connections")
    2. Ask for protocol abbreviation (e.g., "quic") -- used in all file names
    3. Ask which protocol category (connection-oriented transport, pub/sub, routing, real-time, IoT, custom)
    4. Ask which layers to scaffold (present the 14 layers with defaults based on category):
       - Core Stack (L1-9): all selected by default for the chosen category
       - Entity Model (L10-12): always selected
       - Infrastructure (L13-14): selected by default
       - Optional layers: presented based on category relevance
    5. Ask for initial entity roles to create (client/server/mim -- default: client + server)
  - For each selected layer, use `mcp__plugin_serena_serena__create_text_file` to create:
    - Directory structure:
      ```
      protocol-testing/{prot}/
        {prot}_stack/          -- Layers 1-9
        {prot}_tests/
          server_tests/        -- If server entity selected
          client_tests/        -- If client entity selected
          mim_tests/           -- If MIM entity selected
        {prot}_entities/       -- Layers 10-11
        {prot}_shims/          -- Layer 12
        {prot}_utils/          -- Layer 14
      ```
    - Each .ivy file with:
      - `#lang ivy1.7` header
      - Appropriate `include` directives for the layer's dependencies
      - Placeholder `object` or `type` declarations with comments explaining what to fill in
      - Layer-specific boilerplate (e.g., types file gets common type patterns, frame file gets PDU object structure)
  - Present summary of created files at completion
- **Acceptance criteria**:
  - Running `/nct-new-protocol` creates a complete directory structure matching the 14-layer template
  - Each created .ivy file has valid Ivy syntax (at minimum: `#lang ivy1.7` header)
  - Include directives in generated files reference the correct relative paths
  - Category-specific adaptations are applied (e.g., TCP-based protocols get different packet layer)
  - Summary lists all created files
- **Key source files to read for context**:
  - `protocol-testing/new_prot/` -- template directory structure
  - `protocol-testing/formal_model_analysis.md` -- layer descriptions and category adaptations
  - `protocol-testing/quic/quic_stack/quic_types.ivy` -- example types file for boilerplate reference

---

## Task 18: /nct-new-test Command

- **Status**: todo
- **Dependencies**: Task 1 (manifest), Task 11 (writing-test-specs skill for template content)
- **Estimated effort**: 2 hours
- **Files to create**: `panther-ivy-serena/commands/nct-new-test.md`
- **Content outline**:
  - Command frontmatter: name (`nct-new-test`), description ("Scaffold a new Ivy test specification file")
  - Interactive workflow:
    1. Ask for protocol abbreviation (e.g., "quic")
    2. Ask for role: client, server, mim, or attacker
    3. Ask for test name/description (e.g., "handshake_version_negotiation")
    4. Ask for test focus: which protocol feature or RFC requirement is being tested
  - Create test file using `mcp__plugin_serena_serena__create_text_file`:
    - File placement: `protocol-testing/{prot}/{prot}_tests/{role}_tests/{prot}_{role}_test_{name}.ivy`
    - Template content:
      ```
      #lang ivy1.7

      include {prot}_stack/{prot}_types
      include {prot}_stack/{prot}_frame
      include {prot}_stack/{prot}_packet
      include {prot}_stack/{prot}_connection
      include {prot}_entities/ivy_{prot}_{opposite_role}
      include {prot}_shims/{prot}_shim

      # Test: {test_name}
      # Focus: {test_focus}
      # Role: Ivy acts as {opposite_role}, testing real {role}

      object {prot}_{role}_test_{name} = {

          # Export actions that the environment can call
          # export action ...

          # Import actions from the protocol model
          # import action ...

          # Before/after monitors for protocol events
          # before {action} {
          #     require ...
          # }

          # after {action} {
          #     assert ...
          # }

          # End-state verification
          action _finalize = {
              # assert ...
          }
      }
      ```
    - Note: `opposite_role` is computed from role (server -> client, client -> server, mim -> mim, attacker -> target)
  - Present the created file path and suggest next steps (fill in exports, imports, monitors)
- **Acceptance criteria**:
  - Running `/nct-new-test` creates a valid .ivy test file in the correct directory
  - Generated file has correct `#lang ivy1.7` header
  - Include directives reference the correct paths for the specified protocol
  - Role inversion is correctly applied (testing server = Ivy acts as client)
  - File contains clearly commented template sections for the user to fill in
- **Key source files to read for context**:
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` -- canonical test structure
  - `protocol-testing/quic/quic_tests/server_tests/quic_server_test_stream.ivy` -- variant with weight attributes

---

## Task 19: Hooks -- Enforce Serena Usage

- **Status**: todo
- **Dependencies**: Task 1 (manifest)
- **Estimated effort**: 2 hours
- **Files to create**:
  - `panther-ivy-serena/hooks/hooks.json`
  - `panther-ivy-serena/hooks/scripts/block-direct-ivy.sh`
- **Content for `hooks.json`**:
  ```json
  {
    "hooks": [
      {
        "type": "PreToolUse",
        "tool": "Bash",
        "script": "scripts/block-direct-ivy.sh",
        "timeout": 5
      }
    ]
  }
  ```
- **Content for `block-direct-ivy.sh`**:
  ```bash
  #!/usr/bin/env bash
  # Hook: Block direct Ivy CLI invocations in Bash tool.
  # Purpose: Enforce usage of panther-serena MCP tools instead of raw CLI.
  #
  # Receives tool input via stdin as JSON with a "command" field.
  # Exits non-zero to block the command, zero to allow it.

  set -euo pipefail

  # Read the tool input JSON from stdin
  INPUT=$(cat)

  # Extract the command string from the JSON
  COMMAND=$(echo "$INPUT" | python3 -c "
  import sys, json
  data = json.load(sys.stdin)
  print(data.get('command', ''))
  " 2>/dev/null || echo "$INPUT")

  # List of blocked Ivy CLI commands
  BLOCKED_COMMANDS=(
      "ivy_check"
      "ivyc "
      "ivy_show"
      "ivy_to_cpp"
  )

  for blocked in "${BLOCKED_COMMANDS[@]}"; do
      if echo "$COMMAND" | grep -q "$blocked"; then
          cat <<'ERRMSG'
  BLOCKED: Direct Ivy CLI invocation detected.

  Use panther-serena MCP tools instead:
    - ivy_check  -> /nct-check or mcp__plugin_serena_serena__ivy_check
    - ivyc       -> /nct-compile or mcp__plugin_serena_serena__ivy_compile
    - ivy_show   -> /nct-model-info or mcp__plugin_serena_serena__ivy_model_info
    - ivy_to_cpp -> mcp__plugin_serena_serena__ivy_compile (with appropriate target)

  Reason: panther-serena provides consistent tool tracking, semantic
  navigation, path validation, and structured output. Direct CLI calls
  bypass these safeguards.
  ERRMSG
          exit 1
      fi
  done

  # Command is not an Ivy CLI call; allow it
  exit 0
  ```
- **Acceptance criteria**:
  - Hook blocks `ivy_check some_file.ivy` in a Bash tool call with a clear error message
  - Hook blocks `ivyc target=test some_file.ivy` with the same redirection message
  - Hook blocks `ivy_show some_file.ivy` and `ivy_to_cpp some_file.ivy`
  - Hook allows unrelated Bash commands (e.g., `ls`, `git status`, `python script.py`)
  - Hook allows panther-serena tool calls (they go through MCP, not Bash)
  - Error message clearly directs the user to the correct alternative tool/command
  - Hook script exits within the 5-second timeout
- **Edge cases to handle**:
  - Command containing "ivy_check" as part of a longer string (e.g., in a path) -- acceptable to block conservatively
  - Piped commands where ivy CLI appears mid-pipeline
  - Commands with quotes around the ivy CLI invocation
- **Key source files**: None (pure bash hook, no Ivy source dependency)

---

## Task 20: Documentation

- **Status**: in-progress (this document is part of Task 20)
- **Dependencies**: None (can be done first or last; updates as implementation progresses)
- **Estimated effort**: 4 hours total across all documents
- **Files to create/update**:
  - `panther_ivy/docs/panther-ivy-serena-plugin-design.md` -- full design document (already exists, update as implementation evolves)
  - `panther_ivy/docs/task-breakdown.md` -- this document (created)
  - `panther_ivy/docs/methodology-reference.md` -- NCT/NACT/NSCT summary reference
- **Content for `methodology-reference.md`**:
  - Concise summary of all three methodologies (NCT, NACT, NSCT) in a single reference page
  - Comparison table: when to use which methodology
  - Quick-reference tool mapping
  - Links to detailed skill documents and agents
  - Glossary of key terms (IUT, isolate, shim, role inversion, before/after monitors, etc.)
- **Acceptance criteria**:
  - Each document is self-contained and sufficient for independent implementation
  - Task breakdown accurately reflects all 20 tasks with correct dependencies
  - Design document and task breakdown are consistent with each other
  - Methodology reference provides a quick-start summary for new users
  - All file paths referenced in documentation are accurate
- **Key source files for verification**:
  - All files listed in individual task cards above
  - `panther_ivy/docs/panther-ivy-serena-plugin-design.md` -- design document to cross-reference
  - `panther_ivy/docs/plans/TASKS.md` -- related Ivy LSP tasks for context

---

## Summary

| Group | Tasks | Estimated Effort |
|---|---|---|
| Foundation (manifest) | Task 1 | 1 hour |
| Skills (methodology + tools) | Tasks 7--13 | 21 hours |
| Agents (interactive guides) | Tasks 2--6 | 18 hours |
| Commands (workflow shortcuts) | Tasks 14--18 | 8 hours |
| Hooks (enforcement) | Task 19 | 2 hours |
| Documentation | Task 20 | 4 hours |
| **Total** | **20 tasks** | **~54 hours** |

### Critical Path

```
Task 1 (manifest, 1h)
  -> Tasks 7+10+13 (NCT skill + 14-layer + serena-for-ivy, parallel, 4h)
    -> Task 2 (NCT agent, 4h)
      -> Task 17 (/nct-new-protocol, 3h)

Total critical path: ~12 hours
```

### Parallelizable Groups

- **All skills (Tasks 7--13)**: fully independent, run in parallel for maximum throughput
- **All agents (Tasks 2--6)**: independent of each other (only depend on specific skills)
- **Simple commands (Tasks 14--16)**: fully independent, only require Task 1
- **Hooks (Task 19)**: independent, only requires Task 1
- **Documentation (Task 20)**: independent, can start immediately
