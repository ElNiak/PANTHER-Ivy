# Flexible Template System Usage Examples

This document provides practical examples of how to use the new flexible path template system in PANTHER-Ivy.

## Quick Start

The flexible template system allows you to use variables like `homepath>/protocol-testing/IS_APT_PATH>/...` in configuration files, which automatically adapt to different deployment scenarios.

### Basic Example

Instead of hardcoded paths:

```yaml
# OLD: Hardcoded path
ZRTT_SSLKEYLOGFILE: "/opt/panther_ivy/protocol-testing/apt/apt_protocols/quic/last_tls_key.txt"
```

Use flexible templates:

```yaml
# NEW: Flexible template
ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

## Architecture-Aware Templates

The system automatically adapts paths based on your architecture choice:

### APT Architecture (`use_system_models=True`)

```yaml
# Template resolves to:
# /opt/panther_ivy/apt/apt_protocols/quic/last_tls_key.txt
ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

### Individual Architecture (`use_system_models=False`)

```yaml
# Template resolves to:
# /opt/panther_ivy/quic/quic/last_tls_key.txt
ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

## Deployment Scenarios

### Development Setup

Set environment variables:

```bash
export PANTHER_IVY_BASE_DIR="./dev_protocols"
export PANTHER_IVY_INSTALL_DIR="./dev_tools"
```

Templates automatically resolve to development paths:

```yaml
# Resolves to: ./dev_protocols/apt/apt_protocols/quic/last_tls_key.txt
ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"

# Resolves to: ./dev_tools/protocol-testing/
binary_dir: "PANTHER_IVY_INSTALL_DIR>/protocol-testing/"
```

### Docker Environment

Set container-specific paths:

```bash
export PANTHER_IVY_BASE_DIR="/app/protocols"
export PANTHER_IVY_INSTALL_DIR="/usr/local/bin"
```

Same templates work in containers:

```yaml
# Resolves to: /app/protocols/apt/apt_protocols/quic/last_tls_key.txt
ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

### Home Directory Setup

Use user's home directory:

```yaml
# Resolves to: /home/username/panther_protocols/apt/apt_protocols/quic/last_tls_key.txt
ZRTT_SSLKEYLOGFILE: "homepath>/panther_protocols/IS_APT_PATH>/quic/last_tls_key.txt"
```

## Complete Configuration Examples

### QUIC Configuration with Flexible Templates

```yaml
# version_configs/quic/rfc9000_flexible.yaml
version: "rfc9000"
commit: "production"

env:
  # Base paths using templates
  PANTHER_IVY_BASE_DIR: "homepath>/protocol-testing"
  PROTOCOL_MODEL_PATH: "PANTHER_IVY_BASE_DIR>/PROTOCOL_PATH>"
  
  # QUIC-specific files
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
  ZRTT_TOKEN_FILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_token.txt"
  ZRTT_SESSION_TICKET_FILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_session_ticket.txt"

server:
  binary:
    dir: "PANTHER_IVY_INSTALL_DIR>/protocol-testing/"
  logging:
    log_path: "/app/logs/service_name>_server.log"

client:
  binary:
    dir: "PANTHER_IVY_INSTALL_DIR>/protocol-testing/"
  logging:
    log_path: "/app/logs/service_name>_client.log"

parameters:
  tests_dir:
    value: "protocol_name>_tests/"
```

## Custom Variables

You can define custom variables for your specific needs:

```python
# In your code
from panther.plugins.services.testers.panther_ivy.path_template_resolver import get_global_resolver

resolver = get_global_resolver()
resolver.add_variables({
    'custom_base': '/my/custom/installation',
    'project_name': 'my_quic_project',
    'log_level': 'debug'
})
```

Then use them in templates:

```yaml
# Uses custom variables
project_path: "custom_base>/project_name>"
debug_log: "project_path>/logs/log_level>/service_name>.log"
```

## Migration Guide

### From Environment Variables to Templates

**Before (Environment Variables):**

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "${PANTHER_IVY_BASE_DIR:-$SOURCE_DIR/panther_ivy}/${IVY_PROTOCOL_BASE:-protocol-testing/apt/apt_protocols}/${IVY_QUIC_DATA_DIR:-quic}/last_tls_key.txt"
  BINARY_DIR: "${PANTHER_IVY_INSTALL_DIR:-/opt/panther_ivy}/protocol-testing/"
```

**After (Flexible Templates):**

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
  BINARY_DIR: "PANTHER_IVY_INSTALL_DIR>/protocol-testing/"
```

### Benefits of Migration

1. **Simpler syntax**: No complex shell variable expansions
2. **Architecture awareness**: Automatic path adaptation
3. **Better readability**: Clear variable names
4. **Easier maintenance**: Centralized variable management

## Testing Templates

You can test your templates before using them:

```bash
# Run the test script
python panther/plugins/services/testers/panther_ivy/test_flexible_templates.py
```

Or test programmatically:

```python
from panther.plugins.services.testers.panther_ivy.path_template_resolver import get_global_resolver

resolver = get_global_resolver()

# Test a template
template = "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/data.txt"
apt_context = resolver.create_architecture_context(use_apt_protocols=True, protocol_name="quic")
result = resolver.resolve_template(template, apt_context)
print(f"Template resolves to: {result}")

# Validate template
is_valid, undefined = resolver.validate_template(template)
if not is_valid:
    print(f"Undefined variables: {undefined}")
```

## Best Practices

1. **Use descriptive variable names**:

   ```yaml
   # Good
   log_path: "LOG_BASE_DIR>/service_name>_role>.log"
   
   # Avoid
   log_path: "LBD>/SN>_R>.log"
   ```

2. **Keep templates readable**:

   ```yaml
   # Good - broken into logical segments
   base_path: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>"
   data_file: "base_path>/quic/data.txt"
   
   # Avoid - too complex in single line
   data_file: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/data.txt"
   ```

3. **Test in different environments**:
   - Development (local paths)
   - Docker (container paths)
   - Production (system paths)

4. **Use architecture variables**:

   ```yaml
   # Good - adapts to architecture
   protocol_path: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>"
   
   # Avoid - hardcoded for specific architecture
   protocol_path: "PANTHER_IVY_BASE_DIR>/apt/apt_protocols"
   ```

## Troubleshooting

### Common Issues

1. **Template not resolving**:
   - Check variable name spelling
   - Verify variable is defined
   - Use `resolver.get_available_variables()` to see all variables

2. **Wrong architecture paths**:
   - Verify `use_system_models` setting
   - Check that `IS_APT_PATH>` is being used correctly

3. **Path doesn't exist**:
   - Ensure base directories are created
   - Check file permissions
   - Verify environment variables are set correctly

### Debug Mode

Enable debug logging to see template resolution:

```python
import logging
logging.getLogger('panther.plugins.services.testers.panther_ivy').setLevel(logging.DEBUG)
```

This will show how templates are being resolved in the logs.

## Advanced Usage

### Conditional Templates

Based on environment:

```yaml
# Development vs Production
log_path: "homepath>/dev_logs/service_name>.log"  # Development
log_path: "/var/log/panther/service_name>.log"      # Production
```

### Multi-Protocol Support

```yaml
# Protocol-agnostic template
test_dir: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/protocol_name>_tests/"

# Resolves to different paths per protocol:
# QUIC: /opt/panther_ivy/apt/apt_protocols/quic_tests/
# HTTP: /opt/panther_ivy/apt/apt_protocols/http_tests/
```

### Service-Specific Paths

```yaml
# Service and role aware
output_file: "OUTPUT_DIR>/service_name>_role>_results.json"

# Examples:
# ivy_client_client_results.json
# ivy_server_server_results.json
```
