# Flexible Path Templates for PANTHER-Ivy

This document describes the new flexible path template system that allows dynamic path construction using configurable template variables.

## Overview

The flexible template system replaces static environment variables with dynamic templates that can adapt to different deployment scenarios and architectural configurations.

## Template Syntax

Templates use the format `variable_name>` where variables can be:

- **Built-in variables**: Predefined system variables
- **Architecture variables**: Automatically set based on configuration
- **Context variables**: Set based on current service state
- **Custom variables**: User-defined variables

## Built-in Variables

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `homepath>` | User's home directory | `/home/username` |
| `SOURCE_DIR>` | Project source directory | `/app/src` |
| `PANTHER_IVY_BASE_DIR>` | Base directory for Ivy data | `/opt/panther_ivy` |
| `PANTHER_IVY_INSTALL_DIR>` | Installation directory | `/usr/local/panther_ivy` |
| `IVY_PROTOCOL_BASE>` | Protocol base path | `protocol-testing/apt/apt_protocols` |
| `IVY_QUIC_DATA_DIR>` | QUIC data directory | `quic` |

## Architecture Variables

These variables are automatically set based on the `use_system_models` configuration:

### APT Architecture (`use_system_models=True`)

| Variable | Value | Description |
|----------|-------|-------------|
| `IS_APT_PATH>` | `apt/apt_protocols` | Path segment for APT architecture |
| `PROTOCOL_PATH>` | `apt/apt_protocols/quic` | Full protocol path |
| `USE_APT_PROTOCOLS>` | `1` | Flag indicating APT architecture |

### Individual Architecture (`use_system_models=False`)

| Variable | Value | Description |
|----------|-------|-------------|
| `IS_APT_PATH>` | `quic` | Path segment for individual architecture |
| `PROTOCOL_PATH>` | `quic` | Full protocol path |
| `USE_APT_PROTOCOLS>` | `0` | Flag indicating individual architecture |

## Context Variables

Automatically set based on current service state:

| Variable | Description | Example |
|----------|-------------|---------|
| `protocol_name>` | Current protocol | `quic` |
| `service_name>` | Service name | `ivy_client` |
| `role>` | Service role | `client` |
| `test_name>` | Test being executed | `quic_client_test` |

## Usage Examples

### Basic Template Usage

```yaml
# Simple template with built-in variables
log_path: "homepath>/logs/service_name>.log"

# Architecture-aware template
data_path: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/protocol_name>/data"
```

### Configuration File Example

```yaml
env:
  # Flexible base path
  PANTHER_IVY_BASE_DIR: "homepath>/protocol-testing"
  
  # Architecture-aware paths
  PROTOCOL_MODEL_PATH: "PANTHER_IVY_BASE_DIR>/PROTOCOL_PATH>"
  
  # QUIC-specific files with flexible templates
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
  ZRTT_TOKEN_FILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_token.txt"

server:
  binary:
    dir: "PANTHER_IVY_INSTALL_DIR>/protocol-testing/"
    
parameters:
  tests_dir:
    value: "protocol_name>_tests/"
```

## Resolution Examples

### APT Architecture Resolution

For `use_system_models=True` with `protocol_name=quic`:

```
Template: PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt
Context: 
  PANTHER_IVY_BASE_DIR=/opt/panther_ivy
  IS_APT_PATH=apt/apt_protocols
  
Result: /opt/panther_ivy/apt/apt_protocols/quic/last_tls_key.txt
```

### Individual Architecture Resolution

For `use_system_models=False` with `protocol_name=quic`:

```
Template: PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt
Context:
  PANTHER_IVY_BASE_DIR=/home/user/protocols
  IS_APT_PATH=quic
  
Result: /home/user/protocols/quic/quic/last_tls_key.txt
```

### Custom Installation Resolution

With custom environment variables:

```bash
export PANTHER_IVY_BASE_DIR="/custom/install/path"
export PANTHER_IVY_INSTALL_DIR="/custom/binaries"
```

```
Template: PANTHER_IVY_INSTALL_DIR>/protocol-testing/
Result: /custom/binaries/protocol-testing/
```

## Advanced Features

### Nested Template Resolution

Templates can reference other templates:

```yaml
BASE_PATH: "homepath>/panther"
PROTOCOL_PATH: "BASE_PATH>/IS_APT_PATH>"
DATA_FILE: "PROTOCOL_PATH>/protocol_name>/data.txt"
```

### Conditional Templates

Different templates based on architecture:

```yaml
# For APT architecture: /opt/panther_ivy/apt/apt_protocols/quic/
# For individual: /opt/panther_ivy/quic/
PROTOCOL_DIR: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/"
```

## Programming Interface

### Using the PathTemplateResolver

```python
from panther.plugins.services.testers.panther_ivy.path_template_resolver import get_global_resolver

# Get global resolver
resolver = get_global_resolver()

# Add custom variables
resolver.add_variable('custom_base', '/my/custom/path')

# Resolve template with context
context = {'protocol_name': 'quic', 'role': 'client'}
result = resolver.resolve_template('custom_base>/protocol_name>/role>', context)
```

### In Service Manager

```python
# Resolve templates in service manager
template = "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/data"
resolved_path = self.resolve_path_template(template)
```

## Migration from Environment Variables

### Old Approach (Environment Variables)

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "${PANTHER_IVY_BASE_DIR:-$SOURCE_DIR/panther_ivy}/${IVY_PROTOCOL_BASE:-protocol-testing/apt/apt_protocols}/${IVY_QUIC_DATA_DIR:-quic}/last_tls_key.txt"
```

### New Approach (Flexible Templates)

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

**Benefits of new approach:**

- More readable and maintainable
- Architecture-aware variable resolution
- Automatic context switching between APT and individual architectures
- Simpler configuration management

## Deployment Scenarios

### Development Environment

```bash
# Set development paths
export PANTHER_IVY_BASE_DIR="./dev_protocols"
export PANTHER_IVY_INSTALL_DIR="./dev_binaries"

# All templates automatically resolve to development paths
```

### Production Environment

```bash
# Production paths (or use defaults)
export PANTHER_IVY_BASE_DIR="/opt/panther_ivy"
export PANTHER_IVY_INSTALL_DIR="/usr/local/panther_ivy"

# Templates resolve to production paths
```

### Docker Environment

```bash
# Container-specific paths
export PANTHER_IVY_BASE_DIR="/app/protocols"
export PANTHER_IVY_INSTALL_DIR="/usr/local/bin"

# Templates adapt to container filesystem
```

### CI/CD Environment

```bash
# CI workspace paths
export PANTHER_IVY_BASE_DIR="${CI_WORKSPACE}/protocols"
export PANTHER_IVY_INSTALL_DIR="${CI_WORKSPACE}/tools"

# Templates work seamlessly in CI environment
```

## Troubleshooting

### Template Validation

Check if templates are valid:

```python
resolver = get_global_resolver()
is_valid, undefined_vars = resolver.validate_template('PANTHER_IVY_BASE_DIR>/unknown_var>')
if not is_valid:
    print(f"Undefined variables: {undefined_vars}")
```

### Debug Template Resolution

```python
# Enable debug logging to see template resolution
import logging
logging.getLogger('panther.plugins.services.testers.panther_ivy').setLevel(logging.DEBUG)

# Templates will log their resolution process
```

### Common Issues

1. **Undefined Variable**: Template contains `variable>` that doesn't exist
   - **Solution**: Check available variables with `resolver.get_available_variables()`

2. **Wrong Architecture**: Template resolves to unexpected path
   - **Solution**: Verify `use_system_models` setting matches intended architecture

3. **Path Not Found**: Resolved path doesn't exist
   - **Solution**: Check that base directories are created and accessible

## Best Practices

1. **Use descriptive variable names**: `QUIC_DATA_DIR>` instead of `QDD>`
2. **Keep templates readable**: Break complex paths into multiple variables
3. **Test templates in different environments**: Verify resolution works across deployments
4. **Document custom variables**: Explain what each custom variable represents
5. **Use architecture variables**: Let the system handle APT vs individual architecture differences

## Future Enhancements

- **Template inheritance**: Base templates that can be extended
- **Conditional resolution**: If-then logic in templates
- **Template validation**: Pre-deployment template checking
- **Template documentation**: Auto-generated docs from template definitions
