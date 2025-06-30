# PANTHER-Ivy Environment Variables

This document describes the configurable environment variables that allow flexible deployment of PANTHER-Ivy across different environments.

## Overview

PANTHER-Ivy supports both **system-wide installations** (e.g., `/opt/panther_ivy/`) and **local development** setups. Environment variables provide seamless switching between these configurations without code changes.

## Environment Variables

### Core Path Configuration

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `PANTHER_IVY_BASE_DIR` | `$SOURCE_DIR/panther_ivy` | Base directory for Ivy protocol data and utilities |
| `PANTHER_IVY_INSTALL_DIR` | `/opt/panther_ivy` | Installation directory for Ivy binaries and protocol testing tools |
| `IVY_PROTOCOL_BASE` | `protocol-testing/apt/apt_protocols` | Relative path from base directory to protocol files |
| `IVY_QUIC_DATA_DIR` | `quic` | Directory name for QUIC-specific data files |

### Usage Examples

#### Local Development Setup
```bash
export PANTHER_IVY_BASE_DIR="./panther_ivy"
export PANTHER_IVY_INSTALL_DIR="./local_ivy_install"
export IVY_PROTOCOL_BASE="protocol-testing"
export IVY_QUIC_DATA_DIR="quic_data"
```

#### System-wide Installation (Default)
```bash
# Uses defaults - no environment variables needed
# PANTHER_IVY_INSTALL_DIR="/opt/panther_ivy"
# PANTHER_IVY_BASE_DIR="$SOURCE_DIR/panther_ivy"
```

#### Docker Container Setup
```bash
export PANTHER_IVY_BASE_DIR="/app/panther_ivy"
export PANTHER_IVY_INSTALL_DIR="/usr/local/panther_ivy"
export IVY_PROTOCOL_BASE="protocols"
```

#### CI/CD Pipeline
```bash
export PANTHER_IVY_BASE_DIR="${CI_WORKSPACE}/ivy"
export PANTHER_IVY_INSTALL_DIR="${CI_WORKSPACE}/ivy_tools"
export IVY_PROTOCOL_BASE="test_protocols"
```

## Affected Configuration Files

The following YAML configuration files now use these environment variables:

- `version_configs/quic/rfc9000.yaml`
- `version_configs/quic/draft29.yaml`
- `version_configs/minip/*.yaml`

## File Path Resolution

When environment variables are set, file paths are resolved as follows:

### QUIC Protocol Files
- **TLS Key File**: `${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/last_tls_key.txt`
- **Token Files**: `${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/last_*.txt`
- **Data Files**: `${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/*.txt`

### Binary Directories
- **Server/Client Binaries**: `${PANTHER_IVY_INSTALL_DIR}/protocol-testing/`

## Migration Guide

### From Hardcoded Paths
**Before:**
```yaml
ZRTT_SSLKEYLOGFILE: "$SOURCE_DIR/panther_ivy/protocol-testing/apt/apt_protocols/quic/last_tls_key.txt"
binary:
  dir: "/opt/panther_ivy/protocol-testing/"
```

**After:**
```yaml
ZRTT_SSLKEYLOGFILE: "${PANTHER_IVY_BASE_DIR}/${IVY_PROTOCOL_BASE}/${IVY_QUIC_DATA_DIR}/last_tls_key.txt"
binary:
  dir: "${PANTHER_IVY_INSTALL_DIR}/protocol-testing/"
```

### For Custom Installations
1. Set environment variables before running PANTHER
2. Ensure directories exist and are writable
3. Copy/link protocol files to the configured locations

## Backward Compatibility

All environment variables have sensible defaults that maintain compatibility with existing installations. If no environment variables are set, PANTHER-Ivy behaves exactly as before.

## Troubleshooting

### Common Issues

1. **Path Not Found Errors**: Verify environment variables point to existing directories
2. **Permission Denied**: Ensure PANTHER has read/write access to configured paths
3. **File Missing**: Check that protocol data files exist in the configured locations

### Debug Commands
```bash
# Check current environment variable values
env | grep PANTHER_IVY
env | grep IVY_

# Verify resolved paths
echo "Base: ${PANTHER_IVY_BASE_DIR:-$SOURCE_DIR/panther_ivy}"
echo "Install: ${PANTHER_IVY_INSTALL_DIR:-/opt/panther_ivy}"
echo "Protocol: ${IVY_PROTOCOL_BASE:-protocol-testing/apt/apt_protocols}"
echo "QUIC Data: ${IVY_QUIC_DATA_DIR:-quic}"
```

## Implementation Notes

- Environment variable expansion is handled by the YAML configuration loader
- Variables use `${VAR:-default}` syntax for fallback values
- Path resolution occurs at runtime during configuration loading
- No code changes required for existing installations