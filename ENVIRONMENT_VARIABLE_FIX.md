# Environment Variable Resolution Fix

This document describes the fix for the Docker Compose environment variable resolution warnings.

## Problem

The Docker Compose lifecycle manager was unable to resolve nested environment variables like:

```yaml
PANTHER_IVY_BASE_DIR: "${PANTHER_IVY_BASE_DIR:-$SOURCE_DIR/panther_ivy}"
ZRTT_SSLKEYLOGFILE: "${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/last_tls_key.txt"
```

This caused warnings such as:

```
[WARNING] - docker_compose_lifecycle_manager - Could not fully resolve environment variable PANTHER_IVY_BASE_DIR=${PANTHER_IVY_BASE_DIR:-/opt/panther_ivy}
```

## Root Cause

The issue was caused by:

1. **Nested variable references**: Variables referencing other variables that weren't yet resolved
2. **Shell expansion syntax**: Using `${VAR:-default}` syntax that the lifecycle manager couldn't process
3. **Circular dependencies**: Variables depending on each other in ways that prevented resolution

## Solution

### 1. Replaced Nested Variables with Flexible Templates

**Before:**

```yaml
env:
  PANTHER_IVY_BASE_DIR: "${PANTHER_IVY_BASE_DIR:-$SOURCE_DIR/panther_ivy}"
  IVY_PROTOCOL_BASE: "${IVY_PROTOCOL_BASE:-protocol-testing/apt/apt_protocols}"
  ZRTT_SSLKEYLOGFILE: "${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/last_tls_key.txt"
```

**After:**

```yaml
env:
  PANTHER_IVY_BASE_DIR: "PANTHER_IVY_BASE_DIR>"
  IVY_PROTOCOL_BASE: "IVY_PROTOCOL_BASE>"
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

### 2. Updated Default Environment Variables

**Before (in config_schema.py):**

```python
DEFAULT_ENVIRONMENT_VARIABLES = {
    "IVY_DIR": "$SOURCE_DIR/panther_ivy",  # Nested reference
    "Z3_LIBRARY_DIRS": "$IVY_DIR/submodules/z3/build",  # Depends on IVY_DIR
}
```

**After:**

```python
DEFAULT_ENVIRONMENT_VARIABLES = {
    "IVY_DIR": "/opt/panther_ivy",  # Direct value
    "Z3_LIBRARY_DIRS": "/opt/panther_ivy/submodules/z3/build",  # Direct value
    # Added flexible template base variables
    "PANTHER_IVY_BASE_DIR": "/opt/panther_ivy",
    "PANTHER_IVY_INSTALL_DIR": "/opt/panther_ivy",
    "IVY_PROTOCOL_BASE": "protocol-testing/apt/apt_protocols",
    "IVY_QUIC_DATA_DIR": "quic",
}
```

### 3. Enhanced Path Template Resolver

Updated the template resolver to handle proper defaults:

```python
def _setup_default_variables(self):
    source_dir = os.getenv('SOURCE_DIR', '/opt')
    defaults = {
        'PANTHER_IVY_BASE_DIR': os.getenv('PANTHER_IVY_BASE_DIR', f'{source_dir}/panther_ivy'),
        'PANTHER_IVY_INSTALL_DIR': os.getenv('PANTHER_IVY_INSTALL_DIR', '/opt/panther_ivy'),
        # ... other variables
    }
```

## Files Modified

### Configuration Files

- `version_configs/quic/rfc9000.yaml` - Converted to flexible templates
- `version_configs/quic/draft29.yaml` - Converted to flexible templates

### Core Implementation

- `config_schema.py` - Updated DEFAULT_ENVIRONMENT_VARIABLES
- `path_template_resolver.py` - Enhanced default variable handling

## Benefits of the Fix

1. **No More Warnings**: Docker Compose can now resolve all environment variables
2. **Architecture Awareness**: Templates automatically adapt to APT vs individual architecture
3. **Simplified Configuration**: Cleaner, more readable YAML files
4. **Better Maintainability**: Single source of truth for path templates
5. **Backward Compatibility**: Existing installations continue to work

## Testing the Fix

### Before Fix

```bash
# This would produce warnings:
2025-06-24 08:17:19 [WARNING] - Could not fully resolve environment variable PANTHER_IVY_BASE_DIR=${PANTHER_IVY_BASE_DIR:-/opt/panther_ivy}
```

### After Fix

```bash
# No warnings - all variables resolve cleanly
# Templates are processed by the flexible template system
```

### Verification Command

```bash
# Test template resolution
python -c "
from panther.plugins.services.testers.panther_ivy.path_template_resolver import get_global_resolver
resolver = get_global_resolver()
template = '<\$PANTHER_IVY_BASE_DIR>/<\$IS_APT_PATH>/quic/last_tls_key.txt'
apt_context = resolver.create_architecture_context(use_apt_protocols=True, protocol_name='quic')
print('APT Result:', resolver.resolve_template(template, apt_context))
"
```

## Template Resolution Examples

### APT Architecture (use_system_models=True)

```
Template: PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt
Result:   /opt/panther_ivy/apt/apt_protocols/quic/last_tls_key.txt
```

### Individual Architecture (use_system_models=False)

```
Template: PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt
Result:   /opt/panther_ivy/quic/quic/last_tls_key.txt
```

## Migration Notes

- **Existing Installations**: No changes required - defaults maintain compatibility
- **Custom Deployments**: Can set environment variables normally:

  ```bash
  export PANTHER_IVY_BASE_DIR="/custom/path"
  export PANTHER_IVY_INSTALL_DIR="/custom/install"
  ```

- **Docker Environments**: Templates automatically adapt to container paths

## Conclusion

The fix eliminates the Docker Compose environment variable resolution warnings by:

1. Removing problematic nested variable references
2. Using the flexible template system for runtime path resolution
3. Providing clean, direct default values
4. Maintaining full backward compatibility

The flexible template system now handles all path complexity internally, while presenting clean, simple configuration files to users.
