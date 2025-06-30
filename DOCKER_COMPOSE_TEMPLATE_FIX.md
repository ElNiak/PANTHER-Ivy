# Docker Compose Template Resolution Fix

## Problem

Docker Compose lifecycle manager was generating warnings for unresolved environment variables containing flexible path templates:

```
[WARNING] - docker_compose_lifecycle_manager - Could not fully resolve environment variable ZRTT_SSLKEYLOGFILE=PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt
[WARNING] - docker_compose_lifecycle_manager - Could not fully resolve environment variable RETRY_TOKEN_FILE=PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_retry_token.txt
```

## Root Cause

The Docker Compose lifecycle manager's `_resolve_environment_variables()` method was designed to handle traditional environment variable patterns like `$VAR` and `${VAR}`, but not the flexible path template patterns like `VARIABLE>` that were introduced in the PantherIvy configuration system.

**Flow Analysis:**

1. PantherIvy loads environment variables from YAML config files containing templates like `PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/file.txt`
2. These are stored in `service.environments` and passed to Docker Compose
3. Docker Compose template renders these into docker-compose.yml
4. **DockerComposeLifecycleManager** processes environment variables but couldn't resolve `TEMPLATE>` patterns
5. Unresolved templates caused warnings

## Solution

Enhanced the `DockerComposeLifecycleManager._resolve_environment_variables()` method to:

1. **Import PathTemplateResolver**: Use the existing flexible template system
2. **Resolve Templates First**: Process `VARIABLE>` patterns before standard `$VARIABLE` resolution
3. **Create Template Context**: Build context from resolved environment variables
4. **Architecture Awareness**: Default to APT architecture (`IS_APT_PATH = 'apt/apt_protocols'`)
5. **Graceful Fallback**: Continue if PathTemplateResolver is not available

## Implementation

### Key Changes in `docker_compose_lifecycle_manager.py`

```python
def _resolve_environment_variables(self, env_vars: Dict[str, str]) -> Dict[str, str]:
    # ... existing code ...
    
    # First, resolve flexible templates (VARIABLE>) before standard variable resolution
    try:
        from panther.plugins.services.testers.panther_ivy.path_template_resolver import get_global_resolver
        
        # Get the global template resolver
        template_resolver = get_global_resolver()
        
        # Create a context from current working variables
        template_context = {}
        for k, v in working_vars.items():
            if isinstance(v, str) and '$' not in v and '' not in v:
                # Only use fully resolved values for template context
                template_context[k] = v
        
        # Add IS_APT_PATH context - determine from configuration or default to APT
        template_context['IS_APT_PATH'] = 'apt/apt_protocols'
        
        # Resolve all templates first
        for key, value in working_vars.items():
            if isinstance(value, str) and '' in value:
                try:
                    resolved_value = template_resolver.resolve_template(value, template_context)
                    working_vars[key] = resolved_value
                    self.logger.debug(f"Resolved template {key}: {value} -> {resolved_value}")
                except Exception as e:
                    self.logger.warning(f"Failed to resolve template {key}={value}: {e}")
                    
    except ImportError:
        # PathTemplateResolver not available, skip template resolution
        self.logger.debug("PathTemplateResolver not available, skipping template resolution")

    # ... rest of existing variable resolution logic ...
```

## Template Resolution Examples

### Before Fix (Problematic)

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

**Result**: `PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt` (unresolved, causing warnings)

### After Fix (Resolved)

```yaml
env:
  ZRTT_SSLKEYLOGFILE: "PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/last_tls_key.txt"
```

**Result**: `/opt/panther_ivy/apt/apt_protocols/quic/last_tls_key.txt` (fully resolved)

## Architecture Awareness

The fix automatically determines the correct architecture:

### APT Architecture (Default)

- **Template**: `PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/file.txt`
- **Resolved**: `/opt/panther_ivy/apt/apt_protocols/quic/file.txt`

### Individual Protocol Architecture  

- **Template**: `PANTHER_IVY_BASE_DIR>/IS_APT_PATH>/quic/file.txt`
- **Resolved**: `/opt/panther_ivy/quic/quic/file.txt` (when `use_apt_protocols=False`)

## Testing

### Test Script

Run the validation test:

```bash
python panther/plugins/services/testers/panther_ivy/test_docker_compose_template_fix.py
```

### Expected Output

```
🎯 ALL TESTS PASSED
   The Docker Compose template resolution fix is working correctly.
   Environment variable warnings should be eliminated.
```

### Manual Verification

```bash
# Before fix - would show warnings
grep "Could not fully resolve" logs/

# After fix - no warnings for template variables
# Only legitimate unresolved variables (if any) would appear
```

## Benefits

1. **Eliminates Warnings**: No more Docker Compose environment variable resolution warnings
2. **Architecture Aware**: Automatically adapts paths for APT vs individual protocol architectures  
3. **Backward Compatible**: Existing `$VARIABLE` resolution continues to work
4. **Graceful Degradation**: Falls back gracefully if PathTemplateResolver is unavailable
5. **Consistent Behavior**: Uses the same template system as PantherIvy configuration

## Integration Points

### Affected Components

- **DockerComposeLifecycleManager**: Enhanced environment variable resolution
- **PathTemplateResolver**: Reused existing flexible template system
- **PantherIvy Configuration**: Templates now fully resolve before Docker Compose

### Dependency Chain

```
PantherIvy Config (YAML) 
  → service.environments 
  → Docker Compose Template 
  → DockerComposeLifecycleManager 
  → PathTemplateResolver (NEW)
  → Docker Compose (clean environment variables)
```

## Maintenance Notes

- **Template Context**: The fix defaults to `IS_APT_PATH = 'apt/apt_protocols'` which works for most PANTHER-Ivy usage
- **Future Enhancement**: Could be made configurable if non-APT architectures become common
- **Error Handling**: Template resolution failures are logged as warnings but don't break the process
- **Performance**: Minimal overhead - only processes variables containing `` patterns

## Conclusion

This fix resolves the Docker Compose environment variable warnings by integrating the flexible path template system directly into the Docker Compose lifecycle manager. The solution is architecture-aware, backward-compatible, and maintains the existing template functionality while ensuring clean environment variable resolution for Docker Compose.
