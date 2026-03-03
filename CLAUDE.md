# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Panther-Ivy is a **PANTHER framework plugin** (`PluginType.TESTER`) that integrates Microsoft's IVy formal verification tool for specification-based protocol testing. It generates test traffic from formal Ivy protocol models and verifies implementation compliance against those models. The primary supported protocol is QUIC (RFC 9000).

This repository is a **git submodule** of the main PANTHER project, located at `panther/plugins/services/testers/panther_ivy/`. It is also a standalone Python package (`panther_ms_ivy`, version 1.10.1).

## Essential Commands

### Building (Docker-only, not built locally)

Ivy compilation requires Z3, picotls, and C++ toolchains. All builds happen inside Docker containers managed by the parent PANTHER framework.

```bash
# Docker build (from PANTHER root, not this directory)
panther run --config <experiment_config.yaml>

# Build submodules (Z3, picotls) - runs inside Docker
python build_submodules.py
# With specific build mode
BUILD_MODE=rel-lto python build_submodules.py
```

### Ivy CLI Tools (inside Docker container)

```bash
ivyc target=test <test_file>.ivy           # Compile Ivy model to C++ test binary
ivy_check <model>.ivy                       # Check Ivy model for errors
ivy_to_cpp <model>.ivy                      # Generate C++ from Ivy model
ivy_show <model>.ivy                        # Display Ivy model structure
```

### Running Tests (via PANTHER)

Tests are not run directly; they are orchestrated by the PANTHER experiment framework:

```bash
# From PANTHER root
panther run --config experiment-config/base/experiment_config_example_minimal.yaml
```

### Package Build

```bash
python setup.py bdist_wheel --plat-name manylinux1_x86_64
```

## Architecture

### Mixin-Based Service Manager

The core class `PantherIvyServiceManager` (`panther_ivy.py`) uses a mixin composition pattern. Each mixin handles one concern:

```
PantherIvyServiceManager
├── TesterServiceManagerMixin      # Base tester interface (from PANTHER core)
├── ServiceManagerDockerMixin      # Docker image building (from PANTHER core)
├── TesterManagerEventMixin        # Event handling (from PANTHER core)
├── IvyCommandMixin                # ivy_command_mixin.py - Command generation (compile, run)
├── IvyAnalysisMixin               # ivy_analysis_mixin.py - Test output analysis
├── IvyOutputPatternMixin          # ivy_output_pattern_mixin.py - Phase-based output file patterns
├── IvyProtocolAwareMixin          # ivy_protocol_aware_mixin.py - Protocol name/path resolution
├── IvyNetworkResolutionMixin      # ivy_network_resolution_mixin.py - Dynamic IP/service resolution
└── ErrorHandlerMixin              # Error handling (from PANTHER core)
```

### Command Generation Pipeline

Commands flow through a 4-phase lifecycle matching PANTHER's execution model:

1. **Pre-compile** (`generate_ivy_pre_compile_commands`): Network resolution, environment setup
2. **Compile** (`generate_ivy_compile_commands`): `ivyc target=test <model>.ivy` to produce C++ binary
3. **Runtime** (`generate_ivy_runtime_commands`): Setup before test execution
4. **Test** (`generate_run_command`): Execute compiled test binary with parameters (seed, addresses, iterations)

Commands use Jinja2 templates from `templates/{protocol}/` (e.g., `client_command_structured.jinja`).

### Protocol Model Organization

Two architecture variants exist for protocol models:

- **Standard**: `protocol-testing/{protocol}/` (default)
- **APT (system models)**: `protocol-testing/apt/apt_protocols/{protocol}/` (when `use_system_models=true`)

QUIC model structure under `protocol-testing/quic/`:
```
quic_stack/          # Core protocol model (.ivy files: packet, frame, connection, etc.)
quic_tests/          # Test specifications
├── server_tests/    # Tests targeting server implementations (Ivy acts as client)
├── client_tests/    # Tests targeting client implementations (Ivy acts as server)
└── mim_tests/       # Man-in-the-middle attack tests
tls_stack/           # TLS formal model
quic_shims/          # Interface between Ivy model and real implementations
quic_attacks_stack/  # Security/attack formal models
```

### Role Inversion Logic

A key concept: the Ivy tester's role is the **opposite** of what it tests. Testing a QUIC server means Ivy acts as a formal client (`quic_server_test_*` files). The `oppose_role()` function handles this mapping.

### Path Resolution

`ivy_path_template_resolver.py` provides a template-based path system using environment variables:
- `PANTHER_IVY_BASE_PATH`: Base for protocol models (default: `/opt/panther_ivy/protocol-testing`)
- `PANTHER_IVY_APT_SUBPATH`: APT architecture subpath
- `PROTOCOL_PATH`: Resolved full protocol path

### Configuration

`config_schema.py` defines `PantherIvyConfig` (extends `ServicePluginConfig`) with key fields:
- `build_mode`: Z3 compilation mode (`""`, `debug-asan`, `rel-lto`, `release-static-pgo`)
- `test`: Name of the Ivy test to run
- `iterations_per_test` / `internal_iterations_per_test`: Test repetition controls
- `timeout`: Per-test timeout in seconds
- `use_system_models`: Toggle between standard and APT model architectures
- `log_level_events` / `log_level_binary`: Debug verbosity controls

Version-specific configs are loaded from `version_configs/{protocol}/` YAML files.

### Build Modes (Z3 Compilation)

Defined in `build_submodules.py`, these control Z3 and Ivy compilation:

| Mode | Purpose |
|------|---------|
| `""` (empty) | Shadow Network Simulator compatible, legacy mk_make.py |
| `debug-asan` | AddressSanitizer, debug symbols |
| `rel-lto` | Release with Link-Time Optimization |
| `release-static-pgo` | Maximum performance, static linking, PGO |

### Submodules

- `submodules/z3/` - Z3 SMT solver (theorem prover backend)
- `submodules/picotls/` - TLS 1.3 implementation for QUIC crypto
- `submodules/abc/` - ABC sequential synthesis

### Docker

Two Dockerfiles exist:
- `Dockerfile` - Standard single-stage build
- `Dockerfile.buildkit` - Multi-stage BuildKit build with cross-platform support

Both inherit from `panther_base_service` and install Z3, picotls, pyenv, and the Ivy package.

## Key Conventions

- **Phase-based outputs**: All test outputs follow PANTHER's phase structure (`pre-compile/`, `compile/`, `runtime/`, `test/`, `artifacts/`)
- **Network placeholders**: Use `@{service_name:ip:decimal}` patterns resolved at runtime, not hardcoded IPs
- **Command templates**: Do not edit `.jinja` templates directly; customize by changing data passed to them
- **Environment variables**: Protocol paths use `$PROTOCOL_PATH` and related env vars, not hardcoded paths
- **Plugin registration**: Uses `@register_plugin` decorator with `PluginType.TESTER`

## Known Issues

- First Docker build takes ~30 minutes (Z3 + Ivy compilation)
- ARM/Apple Silicon: Z3 math errors on ARM; use `development-scp-refactor` branch
- The `test/` directory contains Ivy language tests (`.ivy` files), not Python unit tests
- Excluded from parent project's linting (`panther_ivy/` is a submodule)
