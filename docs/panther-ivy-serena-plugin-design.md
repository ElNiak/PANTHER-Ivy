# panther-ivy-serena Plugin -- Design Document

## 1. Executive Summary

- **Plugin name**: `panther-ivy-serena`
- **Purpose**: Claude Code plugin providing NCT/NACT/NSCT methodology guidance for Ivy protocol testing via panther-serena MCP tools
- **Target users**: Protocol engineers writing formal Ivy specifications for the PANTHER framework
- **Repository**: https://github.com/ElNiak/panther-ivy-serena

The `panther-ivy-serena` plugin bridges the gap between the Ivy formal verification toolchain and the developer experience inside Claude Code. It provides structured methodology guidance for three distinct testing approaches -- NCT (Network-Centric Compositional Testing), NACT (Network-Attack Compositional Testing), and NSCT (Network-Simulator Centric Compositional Testing) -- while enforcing the use of panther-serena's semantic MCP tools over raw CLI invocations. The plugin embodies a layered approach: agents guide workflows interactively, skills inject domain knowledge contextually, commands provide workflow shortcuts, and hooks enforce tooling discipline.

---

## 2. Problem Statement

### 2.1 No structured guidance for three distinct methodologies

Ivy protocol testing within PANTHER spans three fundamentally different approaches:

- **NCT** tests protocol implementations by having Ivy play the opposing role (e.g., a formal client testing a real server) and checking for specification compliance on the wire.
- **NACT** extends this to adversarial testing by modeling attacker behavior through a 6-stage APT lifecycle (Reconnaissance, Infiltration, C2 Communication, Privilege Escalation, Persistence, Exfiltration) plus white noise distractions.
- **NSCT** uses the Shadow Network Simulator for deterministic, large-scale simulation-based protocol testing.

Each methodology has its own directory structure, entity model, test specification patterns, and execution workflow. No existing tooling provides unified guidance across these approaches or helps users select the appropriate methodology for a given testing goal.

### 2.2 Raw CLI usage instead of semantic MCP tools

Users currently interact with the Ivy toolchain through raw CLI commands (`ivy_check`, `ivyc`, `ivy_show`) executed in a terminal or via Bash tool calls in Claude Code. This bypasses the semantic MCP layer that panther-serena provides, which means:

- No symbol-level understanding of Ivy models (just text-based interaction)
- No tracking of verification operations through the MCP tool call pipeline
- No integration with serena's project-aware navigation (find_symbol, get_symbols_overview, etc.)
- Risk of running Ivy commands outside the correct project context

### 2.3 No scaffolding for new protocol specifications

Creating a new protocol specification requires instantiating up to 14 structural layers (types, application, security, frame, packet, protection, connection, transport parameters, error handling, entities, behaviors, shims, serialization, utilities) with proper cross-references and naming conventions. The existing `new_prot/` template directory provides skeleton files but no interactive scaffolding or guidance for which layers to include based on protocol characteristics.

### 2.4 Steep learning curve for formal protocol specification

The Ivy language combines first-order logic, state machines, compositional reasoning, and C++ code generation. Writing protocol specifications requires understanding:

- The `before`/`after` monitor pattern for specification assertions
- Isolate-based compositional verification
- Role inversion (testing a QUIC server means Ivy acts as a formal client)
- The `_finalize()` pattern for end-state property checking
- Z3/SMT solver interactions and constraint generation
- The relationship between RFC requirements and formal Ivy assertions

---

## 3. Solution: Claude Code Plugin

A Claude Code plugin with agents, skills, commands, and hooks addresses each problem systematically.

### 3.1 Agents (5)

Agents are interactive, prompt-driven assistants that guide users through specific workflows.

| Agent | Role | Primary Use Case |
|---|---|---|
| `nct-guide` | NCT methodology guidance | Walks users through writing specification-based tests that play one protocol role against an IUT |
| `nact-guide` | NACT methodology guidance | Guides adversarial test specification using the APT 6-stage lifecycle model |
| `nsct-guide` | NSCT methodology guidance | Helps configure and write tests for Shadow Network Simulator environments |
| `spec-verifier` | Verification workflow agent | Action-oriented agent that orchestrates ivy_check/ivy_compile/ivy_model_info operations via serena tools |
| `spec-explorer` | Navigation and exploration agent | Helps users understand existing Ivy model structure using serena's symbol-level navigation |

Each agent has a focused system prompt referencing the relevant skill(s) and knows which serena MCP tools to invoke. By separating agents per methodology, system prompts remain concise and contextually accurate. The spec-verifier is orthogonal to methodology (it works for NCT, NACT, and NSCT alike), and the spec-explorer is navigation-focused rather than methodology-focused.

### 3.2 Skills (7)

Skills are structured knowledge documents that auto-activate based on context keywords. Unlike agents, they do not require explicit invocation -- they are injected into context when relevant keywords appear.

| Skill | Auto-activates on | Content |
|---|---|---|
| `nct-methodology` | "NCT", "compositional test", "network-centric" | NCT workflow: role inversion, before/after monitors, _finalize() checks, test spec structure |
| `nact-methodology` | "NACT", "attack test", "APT", "adversarial" | NACT workflow: APT 6-stage lifecycle, attack entities, attacker roles, CVE-based test specs |
| `nsct-methodology` | "NSCT", "shadow", "simulator", "simulation" | NSCT workflow: Shadow NS configuration, deterministic simulation, scale testing |
| `14-layer-template` | "new protocol", "template", "scaffold", "14-layer" | The 14-layer structural template, decision matrix for layer selection, naming conventions |
| `writing-test-specs` | "test spec", "server test", "client test", "mim test" | How to write .ivy test files: includes, exports, init blocks, _finalize(), role-specific patterns |
| `rfc-to-ivy-mapping` | "RFC", "requirement", "specification", "compliance" | Mapping RFC MUST/SHOULD/MAY language to Ivy assertions, requirement traceability |
| `panther-serena-for-ivy` | "serena", "ivy_check", "ivy_compile", "MCP" | Correct usage of serena Ivy MCP tools, parameter reference, common error patterns |

Skills serve a different purpose than agents: they provide reference knowledge that agents (or the user) can draw upon without requiring an interactive workflow session. Cross-cutting skills (14-layer-template, writing-test-specs, rfc-to-ivy-mapping, panther-serena-for-ivy) are useful regardless of which methodology is being followed.

### 3.3 Commands (5)

Commands are slash-command shortcuts that reduce common multi-step workflows to a single invocation.

| Command | Action | Underlying MCP Tool(s) |
|---|---|---|
| `/nct-check` | Run ivy_check on specified file via serena | `mcp__plugin_serena_serena__ivy_check` |
| `/nct-compile` | Compile .ivy file to test binary via serena | `mcp__plugin_serena_serena__ivy_compile` |
| `/nct-model-info` | Display model structure via serena | `mcp__plugin_serena_serena__ivy_model_info` |
| `/nct-new-protocol` | Scaffold a new protocol from the 14-layer template | `mcp__plugin_serena_serena__create_text_file` (multiple calls) |
| `/nct-new-test` | Create a new test specification from a template | `mcp__plugin_serena_serena__create_text_file` |

Commands wrap serena MCP tool calls with appropriate defaults and validation. For example, `/nct-check quic_server_test_stream.ivy` resolves the relative path within the active project, invokes `ivy_check` via serena, and formats the output with highlighted errors and pass/fail summary.

### 3.4 Hooks (1)

A single PreToolUse hook enforces the disciplined use of serena MCP tools over raw CLI access.

**Hook**: `block-direct-ivy` -- Intercepts Bash tool calls containing `ivy_check`, `ivyc`, `ivy_show`, or `ivy_to_cpp` commands and blocks them with a message directing the user to the corresponding serena MCP tool.

This hook ensures that all Ivy operations flow through the MCP layer, providing consistent tracking, project-context awareness, and semantic integration.

---

## 4. Architecture

### 4.1 Plugin Structure

```
panther-ivy-serena/
|-- .claude-plugin/
|   +-- plugin.json                        # Plugin manifest: name, version, dependencies
|-- agents/
|   |-- nct-guide.md                       # NCT methodology interactive agent
|   |-- nact-guide.md                      # NACT methodology interactive agent
|   |-- nsct-guide.md                      # NSCT methodology interactive agent
|   |-- spec-verifier.md                   # Verification workflow agent
|   +-- spec-explorer.md                   # Navigation and exploration agent
|-- skills/
|   |-- nct-methodology/
|   |   +-- skill.md                       # NCT knowledge document
|   |-- nact-methodology/
|   |   +-- skill.md                       # NACT knowledge document
|   |-- nsct-methodology/
|   |   +-- skill.md                       # NSCT knowledge document
|   |-- 14-layer-template/
|   |   +-- skill.md                       # Template architecture knowledge
|   |-- writing-test-specs/
|   |   +-- skill.md                       # Test specification patterns
|   |-- rfc-to-ivy-mapping/
|   |   +-- skill.md                       # RFC-to-Ivy requirement mapping
|   +-- panther-serena-for-ivy/
|       +-- skill.md                       # Serena Ivy tool usage guide
|-- commands/
|   |-- nct-check.md                       # /nct-check command definition
|   |-- nct-compile.md                     # /nct-compile command definition
|   |-- nct-model-info.md                  # /nct-model-info command definition
|   |-- nct-new-protocol.md                # /nct-new-protocol command definition
|   +-- nct-new-test.md                    # /nct-new-test command definition
|-- hooks/
|   |-- hooks.json                         # Hook registration manifest
|   +-- scripts/
|       +-- block-direct-ivy.sh            # PreToolUse hook script
+-- .mcp.json                              # panther-serena MCP server dependency
```

### 4.2 Dependency on panther-serena

The plugin requires the panther-serena MCP server to be running and configured with Ivy support. The `.mcp.json` file declares this dependency. The serena server must be configured with:

1. **Ivy in the languages list** in `.serena/project.yml` so that the Ivy language server is activated.
2. **Ivy tools enabled** in `included_optional_tools` so that `ivy_check`, `ivy_compile`, and `ivy_model_info` are exposed as MCP tools.

The following table maps raw Ivy CLI commands to their serena MCP tool equivalents:

| Raw CLI Command | Serena MCP Tool | Claude Code Tool Name |
|---|---|---|
| `ivy_check <file.ivy>` | `IvyCheckTool.apply()` | `mcp__plugin_serena_serena__ivy_check` |
| `ivyc target=test <file.ivy>` | `IvyCompileTool.apply()` | `mcp__plugin_serena_serena__ivy_compile` |
| `ivy_show <file.ivy>` | `IvyModelInfoTool.apply()` | `mcp__plugin_serena_serena__ivy_model_info` |

In addition to Ivy-specific tools, the plugin uses standard serena tools for code navigation and file operations:

| Serena Tool | Purpose in Plugin |
|---|---|
| `find_symbol` | Locate Ivy symbols (actions, types, relations) by name |
| `get_symbols_overview` | Display high-level structure of an Ivy file (all types, actions, invariants) |
| `find_referencing_symbols` | Find where a symbol is referenced across .ivy files |
| `search_for_pattern` | Regex search across the Ivy codebase |
| `read_file` | Read .ivy file contents with line numbers |
| `create_text_file` | Create new .ivy files (used by scaffolding commands) |
| `replace_symbol_body` | Edit the body of an Ivy action/type/relation in-place |
| `replace_content` | General content replacement in .ivy files |

### 4.3 MCP Tool Parameters Reference

The following documents the actual API signatures from the serena source code at `src/serena/tools/ivy_tools.py`.

#### ivy_check

```
IvyCheckTool.apply(
    relative_path: str,
    isolate: str | None = None,
    max_answer_chars: int = -1,
) -> str
```

**Description**: Runs `ivy_check` on an Ivy source file to verify its formal properties. This checks isolate assumptions, invariants, and safety properties. The file must be an `.ivy` file within the active serena project.

**Parameters**:
- `relative_path` (required, `str`): Relative path to the `.ivy` file to check, resolved from the serena project root. Example: `protocol-testing/quic/quic_tests/server_tests/quic_server_test_stream.ivy`.
- `isolate` (optional, `str | None`): Name of a specific isolate to check in isolation. When provided, the command becomes `ivy_check isolate=<name> <file>`. Useful for checking a single component of a large model without verifying the entire specification. Example: `"protocol_model"`.
- `max_answer_chars` (optional, `int`, default `-1`): Maximum number of characters in the returned output. `-1` uses the serena server's default limit. Useful for large models that produce verbose output.

**Returns**: A JSON string containing the `ivy_check` output with fields for stdout, stderr, and return code.

**Underlying command**: `ivy_check <relative_path>` or `ivy_check isolate=<isolate> <relative_path>`, executed with `cwd` set to the serena project root.

**Common outputs**:
- Return code 0 with empty stderr: All properties verified successfully.
- Return code 1 with `assumption failed` in output: A specification assumption was violated, indicating a potential protocol violation.
- Return code 1 with `error: ...` in stderr: Syntax or type errors in the Ivy model.

#### ivy_compile

```
IvyCompileTool.apply(
    relative_path: str,
    target: str = "test",
    isolate: str | None = None,
    max_answer_chars: int = -1,
) -> str
```

**Description**: Compiles an Ivy source file using `ivyc` (the Ivy compiler). By default, compiles to a `test` target that generates a C++ test executable. Compilation may take significant time for large models (QUIC compilation can take 10-30 minutes on the first build).

**Parameters**:
- `relative_path` (required, `str`): Relative path to the `.ivy` file to compile, resolved from the serena project root.
- `target` (optional, `str`, default `"test"`): Compilation target. The `"test"` target generates a test executable that uses Z3/SMT solving to generate protocol traffic. Other targets may be available depending on the Ivy installation.
- `isolate` (optional, `str | None`): Name of a specific isolate to compile in isolation. When provided, the command becomes `ivyc target=<target> isolate=<name> <file>`.
- `max_answer_chars` (optional, `int`, default `-1`): Maximum number of characters in the returned output.

**Returns**: A JSON string containing the `ivyc` output with fields for stdout, stderr, and return code.

**Underlying command**: `ivyc target=<target> <relative_path>` or `ivyc target=<target> isolate=<isolate> <relative_path>`.

**Common outputs**:
- Return code 0: Compilation successful; a binary is produced in the `build/` directory.
- Return code 1 with `error: ...`: Compilation errors (type mismatches, undefined symbols, etc.).

#### ivy_model_info

```
IvyModelInfoTool.apply(
    relative_path: str,
    isolate: str | None = None,
    max_answer_chars: int = -1,
) -> str
```

**Description**: Runs `ivy_show` on an Ivy source file to display its model structure, including types, relations, actions, invariants, and isolates. This is a read-only introspection tool useful for understanding the high-level architecture of an Ivy formal model before attempting verification or compilation.

**Parameters**:
- `relative_path` (required, `str`): Relative path to the `.ivy` file to inspect, resolved from the serena project root.
- `isolate` (optional, `str | None`): Name of a specific isolate to display information about. When provided, the command becomes `ivy_show isolate=<name> <file>`.
- `max_answer_chars` (optional, `int`, default `-1`): Maximum number of characters in the returned output.

**Returns**: A JSON string containing the `ivy_show` output with fields for stdout, stderr, and return code. The output includes a listing of all types, relations (state variables), actions (events/procedures), invariants, and isolate boundaries defined in the model.

**Underlying command**: `ivy_show <relative_path>` or `ivy_show isolate=<isolate> <relative_path>`.

---

## 5. Methodology Overview

### 5.1 NCT (Network-Centric Compositional Testing)

NCT is the primary testing methodology in PANTHER's Ivy integration. It tests protocol implementations by having the Ivy tester play one role in the protocol (client, server, or man-in-the-middle) against an Implementation Under Test (IUT).

#### Core Concept: Specification-Based Traffic Generation

The Ivy specification defines protocol events as *actions* with `before` (precondition/guard) and `after` (state update) clauses. These clauses serve as monitors: the `before` clause asserts requirements that must hold before an event can occur, and the `after` clause updates shared state variables to record history information. When the Ivy tester generates traffic, it uses Z3/SMT solving to randomly produce protocol messages that satisfy all `before` clauses -- meaning the generated traffic is specification-compliant by construction. The responses from the IUT are then checked against the same specification for compliance.

#### Role Inversion

A key concept in NCT is role inversion: testing a QUIC **server** means the Ivy tester acts as a formal **client**. The test files reflect this:

- `quic_server_test_*.ivy` files include `ivy_quic_shim_client` and `ivy_quic_client_behavior` -- the tester IS the client.
- `quic_client_test_*.ivy` files include the server-side shims and behaviors.
- `quic_*_mim_*.ivy` files use man-in-the-middle entity definitions.

This is handled programmatically by the `oppose_role()` function in the PANTHER Ivy plugin.

#### Test Specification Structure

A typical NCT test specification (e.g., `quic_server_test.ivy`) follows this pattern:

```ivy
#lang ivy1.7

include order
include quic_infer
include file
include ivy_quic_shim_client        # Shim for the role we're playing
include quic_locale
include ivy_quic_client_behavior    # Behavior constraints for our role

# Transport parameters
include ivy_quic_client_standard_tp

include quic_time

# Initialization: open sockets, configure TLS, set transport parameters
after init {
    sock := net.open(endpoint_id.client, client.ep);
    client.set_tls_id(0);
    server.set_tls_id(1);
    var extns := tls_extensions.empty;
    extns := extns.append(make_transport_parameters);
    call tls_api.upper.create(0, false, extns);
}

# Export actions that the tester will generate via SMT solving
export frame.ack.handle
export frame.stream.handle
export frame.crypto.handle
export packet_event
export client_send_event
export tls_recv_event

# _finalize(): end-state checks after the test completes
export action _finalize = {
    require is_no_error;
    require conn_total_data(the_cid) > 0;
}
```

The `export` declarations specify which actions the tester can execute. The `_finalize()` action is called when the test completes (typically after a timeout) and checks end-state properties -- for example, that data was successfully exchanged and no errors occurred.

#### QUIC NCT Test Coverage

The existing QUIC NCT test suite includes 50+ test specifications covering:

| Category | Example Tests | What They Verify |
|---|---|---|
| Basic data transfer | `quic_server_test_stream`, `quic_server_test_max` | Stream data exchange, MAX_DATA compliance |
| Connection lifecycle | `quic_server_test_connection_close`, `quic_server_test_timeout` | Clean/dirty shutdown, idle timeout |
| 0-RTT | `quic_server_test_0rtt`, `quic_server_test_0rtt_stream` | Early data acceptance/rejection |
| Error handling | `quic_server_test_tp_error`, `quic_server_test_max_error` | Transport parameter errors, flow control errors |
| Migration | `quic_server_test_migration`, `quic_server_test_stream_migration` | Connection migration, path validation |
| Connection ID | `quic_server_test_ncid_quant_vulne`, `quic_server_test_newconnectionid_error` | NEW_CONNECTION_ID handling, CID lifecycle |
| Version negotiation | `quic_server_test_version_negociation` | Version negotiation protocol |
| Retry | `quic_server_test_retry`, `quic_server_test_retry_reuse_key` | Retry token handling, address validation |
| Recovery | `quic_server_test_loss_recovery`, `quic_server_test_congestion_control` | Loss detection, congestion response |
| Extensions | `quic_server_test_ext_min_ack_delay` | Protocol extensions |

### 5.2 NACT (Network-Attack Compositional Testing)

NACT extends NCT's compositional testing approach to adversarial scenarios. Instead of testing whether an implementation correctly follows the protocol specification, NACT tests whether an implementation correctly resists attacks.

#### APT 6-Stage Lifecycle

The attack model is based on the Advanced Persistent Threat (APT) lifecycle, organized into six stages plus a white noise stage. Each stage is defined in its own Ivy file under `protocol-testing/apt/apt_lifecycle/`:

| Stage | File | Description |
|---|---|---|
| 1. Reconnaissance | `attack_reconnaissance.ivy` | Information gathering: passive (WHOIS, DNS queries) and active (port scanning, service enumeration, OS fingerprinting) |
| 2. Infiltration | `attack_infiltration.ivy` | Initial access: exploiting vulnerabilities, delivering payloads |
| 3. C2 Communication | `attack_c2_communication.ivy` | Command and control: establishing covert communication channels |
| 4. Privilege Escalation | `attack_privilege_escalation.ivy` | Elevating access: exploiting local vulnerabilities for higher privileges |
| 5. Persistence | `attack_maintain_persistence.ivy` | Maintaining access: installing backdoors, creating persistence mechanisms |
| 6. Exfiltration | `attack_exflitration.ivy` | Data extraction: stealing data through covert channels |
| (White Noise) | `attack_white_noise.ivy` | Distraction: generating benign-looking traffic to mask attack activity |

The master lifecycle file (`attack_life_cycle.ivy`) composes all stages:

```ivy
#ivy lang1.7

include attack_white_noise

# Infiltration
include attack_reconnaissance
include attack_infiltration
include attack_c2_communication

# Expansion
include attack_privilege_escalation
include attack_maintain_persistence

# Extraction
include attack_exfiltration
```

#### Attack Entities

NACT defines additional entity types beyond NCT's client/server model, located in `protocol-testing/apt/apt_entities/`:

| Entity | File | Role |
|---|---|---|
| Attacker | `ivy_attacker.ivy` | Base attacker entity with scanning parameters, malicious endpoints |
| Bot | `ivy_bot.ivy` | Compromised machine under attacker control |
| C2 Server | `ivy_c2_server.ivy` | Command and control server |
| Target | `ivy_target.ivy` | The target of the attack |
| MIM | `ivy_mim.ivy` | Man-in-the-middle entity |

Protocol-specific attack entity bindings exist for QUIC, MiniP, Stream Data, and System models under `apt_entities/{protocol}/`.

#### Protocol-Specific Attack Bindings

The generic attack lifecycle stages are bound to protocol-specific operations through binding modules:

- `quic_apt_lifecycle/`: Malicious QUIC frames, packets, encrypted packets, attack connections, random padding
- `minip_apt_lifecycle/`: Malicious MiniP frames, packets, attack connections
- `udp_apt_lifecycle/`: Malicious UDP datagrams
- `stream_data_apt_lifecycle/`: Malicious stream data

#### NACT Test Specifications

Attack test specifications are organized in `protocol-testing/apt/apt_tests/`:

- **`attacker_server_tests/`**: Tests where the attacker targets a server IUT. Includes CVE-specific tests (CVE-2024-22588, CVE-2024-22590, CVE-2024-24989, CVE-2024-25678, CVE-2024-25679, CVE-2024-26190, CVE-2022-30591, CVE-2024-22189, CVE-2023-42805) and generic attack tests (reflection, malicious frames, slowloris, stream vulnerabilities, token exploits).
- **`attacker_client_tests/`**: Tests where the attacker targets a client IUT. Includes 0-RTT replay attacks, PSK reflection/selfie attacks, version negotiation forgery/modification.
- **`mim_tests/`**: Man-in-the-middle tests for QUIC, MiniP, Stream Data, and System models. Tests include forwarding, delaying, reflecting, and replaying traffic.

#### Attacker Entity Configuration

The attacker entity (`ivy_attacker.ivy`) exposes configurable parameters:

```ivy
parameter malicious_client_addr : ip.addr = 0x0a000001
parameter malicious_client_port : ip.port = 4441
parameter malicious_server_addr : ip.addr = 0x0a000001
parameter malicious_server_port : ip.port = 4442
parameter is_scanning         : bool = true
parameter start_scanning_port : ip.port = 4442
parameter end_scanning_port   : ip.port = 4443
parameter verify_incoming_packet : bool = true
parameter slow_loris : bool = false
```

These parameters control the attacker's behavior: network addresses, scanning ranges, packet verification, and specific attack techniques like slowloris.

### 5.3 NSCT (Network-Simulator Centric Compositional Testing)

NSCT provides compositional testing in simulated network environments using the Shadow Network Simulator. While NCT tests against real network stacks and NACT adds adversarial scenarios on real networks, NSCT enables deterministic, reproducible testing at scale.

#### Shadow Network Simulator Integration

Shadow provides:

- **Deterministic simulation**: Network behavior is fully reproducible across runs.
- **Scale testing**: Many nodes and complex topologies can be simulated without physical resources.
- **Controlled conditions**: Latency, bandwidth, packet loss, and jitter can be precisely configured.
- **Time simulation**: Virtual time allows testing timeout behaviors without real-time waits.

#### PANTHER Configuration for NSCT

NSCT experiments are configured through PANTHER experiment YAML files with `type: shadow_ns` in the network environment:

```yaml
tests:
  - name: "NSCT QUIC Test"
    network_environment:
      type: shadow_ns
    services:
      server:
        implementation:
          name: picoquic
          type: iut
        protocol:
          name: quic
          version: rfc9000
          role: server
```

#### Complementary Relationship with NCT

NSCT is not a replacement for NCT but a complement:

- **NCT** uses real network stacks -- it catches real-world bugs that simulation might miss, but cannot scale to complex topologies or guarantee reproducibility.
- **NSCT** uses simulated networks -- it provides deterministic reproduction of failures and can test at scale, but may miss implementation-specific bugs in real network stacks.

The Ivy specifications themselves are the same across NCT and NSCT; only the execution environment differs. The same test specification (e.g., `quic_server_test_stream.ivy`) can be compiled and run in either a real Docker network (NCT) or a Shadow simulation (NSCT).

---

## 6. The 14-Layer Template

The formal model architecture analysis (documented in `protocol-testing/formal_model_analysis.md`) identifies 14 structural layers that form the template for any protocol specification. These layers are organized into four groups.

### Core Protocol Stack (Always Required)

These nine layers define the protocol's fundamental data types, message formats, and state management. Every protocol specification requires all of them, though the complexity of each layer varies significantly by protocol.

| Layer | File Pattern | Description |
|---|---|---|
| 1. Type Definitions | `{prot}_types.ivy` | Identifiers, bit vectors, enumerations, and other fundamental data types used throughout the specification. |
| 2. Application Layer | `{prot}_application.ivy` | Data transfer semantics: how application data is sent, received, buffered, and delivered. |
| 3. Security/Handshake Layer | `{prot}_security.ivy` | Key establishment, handshake state machine, authentication, and session security properties. |
| 4. Frame/Message Layer | `{prot}_frame.ivy` | Protocol data unit (PDU) definitions: the messages or frames that the protocol exchanges. This is where protocol semantics concentrate most heavily. QUIC defines 20+ frame types; BGP has 4 message types. |
| 5. Packet Layer | `{prot}_packet.ivy` | Wire-level packet structure: how frames are assembled into packets, headers, and trailers. |
| 6. Protection Layer | `{prot}_protection.ivy` | Encryption and decryption: how packets are protected on the wire. May be trivial for unencrypted protocols. |
| 7. Connection/State Management | `{prot}_connection.ivy` | Session lifecycle: connection establishment, maintenance, migration, and teardown. State machines differ fundamentally by protocol (QUIC uses CID-based tracking with migration; BGP uses a 6-state FSM). |
| 8. Transport Parameters | `{prot}_transport_parameters.ivy` | Negotiable parameters exchanged during connection establishment (e.g., max_data, max_streams, idle_timeout). |
| 9. Error Handling | `{prot}_error_code.ivy` | Error taxonomy: error codes, error signaling mechanisms, and error recovery behaviors. |

### Entity Model (Always Required)

These three layers define the network participants and their behavioral constraints.

| Layer | File Pattern | Description |
|---|---|---|
| 10. Entity Definitions | `ivy_{prot}_{role}.ivy` | Network participant instance declarations: client, server, MIM, attacker. Defines the endpoints that exist in the model. |
| 11. Entity Behavior | `ivy_{prot}_{role}_behavior.ivy` | Finite state machine and behavioral constraints for each entity. This is the largest and most complex protocol-specific code: QUIC behavior files are ~15k lines each. Contains the `before`/`after` monitors that encode RFC requirements. |
| 12. Shims | `{prot}_shim.ivy` | Implementation bridge between the Ivy model and real network implementations. The shim pattern is architecturally consistent across protocols, but the implementation is entirely protocol-specific. |

### Infrastructure (Mostly Reusable)

These two layers provide utilities that are largely protocol-independent.

| Layer | File Pattern | Description |
|---|---|---|
| 13. Serialization/Deserialization | `{prot}_ser.ivy`, `{prot}_deser.ivy` | Wire format encoding and decoding. Entirely protocol-specific in content. QUIC has ~47k lines across 12+ file pairs. May be implemented in C++ for performance. |
| 14. Utilities | `byte_stream.ivy`, `file.ivy`, `time.ivy`, `random_value.ivy`, `locale.ivy` | Generic utilities. `byte_stream.ivy`, `file.ivy`, and `random_value.ivy` are identical across protocols and can be copied verbatim. |

### Optional Layers (Protocol-Dependent)

Depending on the protocol's characteristics, additional layers may be needed:

- **Security Sub-Protocol** (`tls_stack/` or `dtls_stack/`): For protocols with integrated TLS/DTLS.
- **FSM Modules** (`{prot}_fsm/`): For protocols with complex state machines requiring separate modeling.
- **Recovery & Congestion** (`{prot}_recovery/` or `{prot}_congestion/`): For protocols with built-in reliability.
- **Extensions** (`{prot}_extensions/`): For protocols with extension mechanisms.
- **Attacks Stack** (`{prot}_attacks_stack/`): For NACT integration.
- **Stream/Flow Management** (`{prot}_stream.ivy`): For multiplexed protocols.

### Directory Structure per Protocol

```
protocol-testing/{prot}/
|-- {prot}_stack/              # Layers 1-9: Core protocol stack
|   |-- {prot}_types.ivy
|   |-- {prot}_application.ivy
|   |-- {prot}_security.ivy
|   |-- {prot}_frame.ivy
|   |-- {prot}_packet.ivy
|   |-- {prot}_protection.ivy
|   |-- {prot}_connection.ivy
|   |-- {prot}_transport_parameters.ivy
|   +-- {prot}_error_code.ivy
|-- {prot}_entities/           # Layers 10-11: Entity model
|   |-- ivy_{prot}_client.ivy
|   |-- ivy_{prot}_server.ivy
|   |-- ivy_{prot}_client_behavior.ivy
|   +-- ivy_{prot}_server_behavior.ivy
|-- {prot}_shims/              # Layer 12: Implementation bridge
|   |-- {prot}_shim.ivy
|   |-- {prot}_shim_client.ivy
|   +-- {prot}_shim_server.ivy
|-- {prot}_utils/              # Layers 13-14: Infrastructure
|   |-- {prot}_ser.ivy
|   |-- {prot}_deser.ivy
|   |-- byte_stream.ivy
|   |-- file.ivy
|   |-- time.ivy
|   +-- random_value.ivy
|-- {prot}_tests/
|   |-- server_tests/          # NCT tests targeting server IUTs
|   |-- client_tests/          # NCT tests targeting client IUTs
|   +-- mim_tests/             # Man-in-the-middle tests
+-- {prot}_attacks_stack/      # Optional: NACT integration
```

### Decision Matrix for Template Selection

When creating a new protocol specification, the following decision matrix determines which optional layers and architectural adaptations are needed:

| Protocol Property | Template Impact |
|---|---|
| Connection-oriented? | TCP layer replaces UDP datagram layer; simplified packet structure |
| Built-in reliability? | Add recovery and congestion control modules |
| Multiplexed streams? | Add stream management layer with per-stream FSMs |
| Integrated security? | Add TLS/DTLS sub-protocol stack and protection layer |
| Peer-to-peer? | Symmetric entities (Speaker/Peer) instead of client/server |
| Publish/Subscribe pattern? | Add broker entity, topic/subscription management |
| Extension mechanism? | Add extensions module |
| Stateless? | Simplify or omit connection/state management |
| Tunneling? | Add encapsulation layer, Security Association management |
| Real-time? | Add timing constraints, FEC recovery instead of retransmission |
| IoT/Constrained? | Resource discovery, proxy/gateway entities, block-wise transfer |

### Genuinely Reusable Components

The analysis reveals that almost nothing in the core protocol stack is truly generic -- the template provides a structural pattern, but the content of each layer is entirely protocol-dependent. The only genuinely reusable components are:

- `byte_stream.ivy` -- identical across all protocols
- `file.ivy` -- identical across all protocols
- `random_value.ivy` -- identical across all protocols
- The shim architectural pattern (not the implementation)
- The `_finalize()` check pattern in test specifications
- The `before`/`after` monitor pattern for specification assertions

---

## 7. Design Rationale

### 7.1 Why enforce serena over direct CLI?

**Consistency**: When all Ivy operations flow through MCP tool calls, they are tracked in a uniform way. Other agents or tools in the Claude Code session can observe and react to verification results without parsing raw CLI output.

**Semantic navigation**: Serena provides symbol-level understanding of Ivy models through `find_symbol`, `get_symbols_overview`, and `find_referencing_symbols`. Raw CLI access gives only text output. For example, serena can resolve "find all actions that reference the `conn_total_data` relation" -- something that `grep` can approximate but cannot do with semantic accuracy.

**Project context awareness**: Serena resolves relative paths from the project root and validates that files are `.ivy` files within the active project. Direct CLI usage risks running Ivy commands in the wrong directory, against the wrong files, or without the correct environment variables.

**Integration with other agents**: Verification results from serena MCP tools can be consumed by the spec-verifier agent, which can then correlate failures with specific model structure information from `ivy_model_info`. This agent-level integration is not possible with raw CLI output.

**Safety**: The PreToolUse hook prevents accidental execution of Ivy CLI commands outside the controlled serena context. This is particularly important for `ivyc`, which can produce build artifacts and modify the filesystem.

### 7.2 Why separate agents vs one monolithic agent?

**Distinct workflows per methodology**: NCT, NACT, and NSCT have fundamentally different workflows:

- NCT workflows center on: select a role, write before/after monitors, define exports, write _finalize checks.
- NACT workflows center on: select an attack stage, define attacker parameters, bind to protocol-specific attack structures, write CVE-specific tests.
- NSCT workflows center on: configure Shadow NS topology, define node capabilities, set network conditions, run deterministic simulations.

A monolithic agent would need to carry all three workflow descriptions in its system prompt, making it large, slow, and prone to context confusion.

**Spec-verifier is action-oriented**: The spec-verifier agent orchestrates a sequence of tool calls (check model info, then verify, then compile) rather than providing methodology guidance. Its system prompt focuses on error interpretation and iterative fix-verify cycles.

**Spec-explorer is navigation-focused**: The spec-explorer agent helps users understand existing Ivy model structure through serena's navigation tools. It is orthogonal to methodology choice and can be used independently.

**Focused system prompts improve performance**: Smaller, focused system prompts produce more accurate responses than large, general-purpose prompts. Each agent's system prompt can include specific examples, error patterns, and workflow steps relevant to its domain.

### 7.3 Why skills in addition to agents?

**Auto-activation vs explicit invocation**: Skills auto-activate when relevant keywords appear in the conversation context. A user writing "I need to create a new QUIC test spec" would automatically receive knowledge from the `writing-test-specs` skill without needing to invoke an agent. Agents require explicit invocation (or delegation from another agent).

**Structured reference knowledge**: Skills provide structured, authoritative knowledge that agents reference but do not replicate in their system prompts. The `14-layer-template` skill contains the full decision matrix and layer descriptions; agents reference this skill rather than embedding the information.

**Cross-cutting concerns**: Several skills (14-layer-template, writing-test-specs, rfc-to-ivy-mapping, panther-serena-for-ivy) are useful regardless of which methodology is being followed. They represent domain knowledge that cuts across the NCT/NACT/NSCT boundaries.

**Separation of knowledge from workflow**: Agents are for interactive guidance through a workflow. Skills are for knowledge injection. A user can benefit from the `nct-methodology` skill's knowledge while interacting with the `spec-verifier` agent. This compositional approach allows knowledge to be reused across multiple interaction patterns.

---

## 8. Prerequisites

### 8.1 panther-serena MCP server with Ivy tools enabled

The serena MCP server must be configured with:

1. **Ivy in the languages list** in the project's `.serena/project.yml`:
   ```yaml
   languages:
     - python
     - ivy
   ```

2. **Ivy optional tools included** in `.serena/project.yml`:
   ```yaml
   included_optional_tools:
     - ivy_check
     - ivy_compile
     - ivy_model_info
   ```

3. **Serena project indexed** so that the Ivy language server can resolve symbols:
   ```bash
   uvx --from git+https://github.com/oraios/serena serena project index
   ```

### 8.2 ivy_lsp installed

The Ivy Language Server Protocol implementation must be installed for serena to provide Ivy language support:

```bash
# From the panther_ivy directory
pip install -e ".[lsp]"
# Or directly
pip install ivy-lsp
```

### 8.3 Ivy added to .serena/project.yml languages list

The Ivy language must be registered in the serena project configuration so that the language server is activated and `.ivy` files are recognized for semantic analysis.

### 8.4 GitHub repository

The plugin source is hosted at https://github.com/ElNiak/panther-ivy-serena. To install the plugin:

```bash
# Clone into the Claude Code plugins directory
git clone https://github.com/ElNiak/panther-ivy-serena.git
```

Or reference it in the project's `.claude/plugins.json` configuration.

---

## 9. Key Source Files Reference

The following files in the panther_ivy submodule and the panther-serena codebase are the primary sources of truth for the knowledge encoded in this plugin's skills and agents.

### Protocol Model Architecture

| File | Content |
|---|---|
| `protocol-testing/formal_model_analysis.md` | Complete 14-layer architecture analysis, cross-protocol structural comparison, decision matrix for template selection, and protocol category adaptation guides (connection-oriented, pub/sub, routing, real-time, IoT, name resolution, multiplexed transport, VPN/tunneling). |

### QUIC Specification (Reference Implementation)

| File | Content |
|---|---|
| `protocol-testing/quic/README.md` | QUIC specification guide: installation, compilation, testing workflow, implementation notes for picoquic/quant/MinQUIC/Google QUIC. |
| `protocol-testing/quic/new_requirements_rfc9000.txt` | RFC 9000 requirements extraction with annotations about which requirements are already covered, partially covered, or missing in the formal model. |

### Template and Scaffolding

| File | Content |
|---|---|
| `protocol-testing/new_prot/` | Template directory for new protocols. Contains skeleton files: `new_prot_entities/` (endpoint, behavior), `new_prot_shims/` (shim), `new_prot_stack/` (application), `new_prot_utils/` (byte_stream, deser, file, ser, time, type). |
| `protocol-testing/new_prot/new_prot.md` | Template documentation (minimal, placeholder for protocol-specific documentation). |

### APT/NACT Lifecycle

| File | Content |
|---|---|
| `protocol-testing/apt/apt_lifecycle/attack_life_cycle.ivy` | Master lifecycle composition: includes all 6 stages plus white noise. |
| `protocol-testing/apt/apt_lifecycle/attack_reconnaissance.ivy` | Stage 1: Passive and active reconnaissance actions (WHOIS, DNS, port scanning). |
| `protocol-testing/apt/apt_lifecycle/attack_infiltration.ivy` | Stage 2: Initial access exploitation. |
| `protocol-testing/apt/apt_lifecycle/attack_c2_communication.ivy` | Stage 3: Command and control channel establishment. |
| `protocol-testing/apt/apt_lifecycle/attack_privilege_escalation.ivy` | Stage 4: Privilege escalation techniques. |
| `protocol-testing/apt/apt_lifecycle/attack_maintain_persistence.ivy` | Stage 5: Persistence mechanisms. |
| `protocol-testing/apt/apt_lifecycle/attack_exflitration.ivy` | Stage 6: Data exfiltration. |
| `protocol-testing/apt/apt_lifecycle/attack_white_noise.ivy` | Distraction traffic generation. |

### APT Protocol Bindings

| Directory | Content |
|---|---|
| `protocol-testing/apt/apt_lifecycle/quic_apt_lifecycle/` | QUIC-specific attack structures: malicious frames, packets, encrypted packets, attack connections, random padding. |
| `protocol-testing/apt/apt_lifecycle/minip_apt_lifecycle/` | MiniP-specific attack structures. |
| `protocol-testing/apt/apt_lifecycle/udp_apt_lifecycle/` | UDP-specific malicious datagrams. |
| `protocol-testing/apt/apt_lifecycle/stream_data_apt_lifecycle/` | Stream data-specific malicious payloads. |

### APT Entities and Behaviors

| Directory | Content |
|---|---|
| `protocol-testing/apt/apt_entities/` | Base attacker entities (attacker, bot, C2 server, target, MIM) and protocol-specific bindings (quic/, minip/, stream_data/, system/). |
| `protocol-testing/apt/apt_entities_behavior/` | Behavioral constraints for attack entities, organized by protocol. |

### APT Test Specifications

| Directory | Content |
|---|---|
| `protocol-testing/apt/apt_tests/attacker_server_tests/` | Server-targeted attack tests including CVE reproductions (CVE-2024-22588, CVE-2024-22590, CVE-2024-24989, CVE-2024-25678, CVE-2024-25679, CVE-2024-26190, CVE-2022-30591, CVE-2024-22189, CVE-2023-42805). |
| `protocol-testing/apt/apt_tests/attacker_client_tests/` | Client-targeted attack tests: 0-RTT replay, PSK reflection, version negotiation attacks. |
| `protocol-testing/apt/apt_tests/mim_tests/` | MIM tests: forwarding, delaying, reflecting, replaying traffic for QUIC, MiniP, Stream Data, System. |

### NCT Test Specification Example

| File | Content |
|---|---|
| `protocol-testing/quic/quic_tests/server_tests/quic_server_test.ivy` | Canonical NCT test example: includes, init blocks, exports, _finalize() pattern. |

### Serena Tool API

| File | Content |
|---|---|
| `/private/tmp/claude-501/panther-serena-clone/src/serena/tools/ivy_tools.py` | Source code for `IvyCheckTool`, `IvyCompileTool`, and `IvyModelInfoTool` with full API signatures, parameter documentation, and implementation details. |
