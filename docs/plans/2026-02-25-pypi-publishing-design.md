# Plan: Publish panther-net, panther_ms_ivy, and ivy-lsp to PyPI

## Context

Three Python packages need PyPI publishing infrastructure:
- **panther-net** (v1.1.5) -- already on PyPI but workflow has bugs (no submodule checkout, OIDC auth needs switching to API token)
- **panther_ms_ivy** (v1.8.26) -- only on test.pypi.org, uses legacy `setup.py`, needs migration to `pyproject.toml`
- **ivy-lsp** (v0.1.0) -- never published, needs a publish workflow

Each lives in its own GitHub repo. They have optional cross-dependencies:
- `ivy-lsp [ivy]` -> `panther_ms_ivy`
- `panther_ms_ivy [lsp]` -> `ivy-lsp` (currently a git URL, must become PyPI reference)

## Publish Order

**ivy-lsp first** -> **panther_ms_ivy second** -> **panther-net third**

This order ensures each package exists on PyPI before the next references it.

---

## Step 1: ivy-lsp (github.com/ElNiak/ivy-lsp)

### 1a. Fix `pyproject.toml` build backend

Change line 3:
```diff
- build-backend = "setuptools.backends._legacy:_Backend"
+ build-backend = "setuptools.build_meta"
```

The `_legacy:_Backend` is an undocumented private API that may break across setuptools versions.

### 1b. Create publish workflow

**File:** `.github/workflows/publish.yml`

Triggers on `push: tags: ['v*']`. Builds with `python -m build`, checks with `twine check`, publishes via `pypa/gh-action-pypi-publish` with API token auth.

### 1c. Create version bump script

**File:** `scripts/bump_version.py`

Updates version in both `pyproject.toml` and `ivy_lsp/__init__.py`, creates git commit + tag.

### 1d. Manual setup required

- Add `PYPI_API_TOKEN` secret to `ElNiak/ivy-lsp` repo on GitHub

---

## Step 2: panther_ms_ivy (github.com/ElNiak/PANTHER-Ivy)

### 2a. Migrate setup.py to pyproject.toml

Full `pyproject.toml` with all metadata from `setup.py`:
- Package name: `panther_ms_ivy`, version `1.8.26`
- Build system: `setuptools>=68.0`
- All dependencies from `setup.py` including `applescript; sys_platform == 'darwin'` (env marker replaces platform.system() conditional)
- Package data: combine ALL platform globs (`.so`, `.dylib`, `.dll`, `.a`, `.lib`) -- extra patterns that match nothing are harmless
- Exclude `ivy_lsp`, `ivy_lsp.*`, `vscode-ivy` from packages
- Optional deps: `z3 = ["z3-solver==4.13.4.0"]`, `lsp = ["ivy-lsp"]` (PyPI name, not git URL)
- All console_scripts entry points
- Preserve existing `[tool.black]` and `[tool.isort]` sections

### 2b. Minimize setup.py (keep for BinaryDistribution only)

All metadata now lives in `pyproject.toml`. `setup.py` only injects the platform-specific wheel tag.

### 2c. Replace publish workflows with unified matrix workflow

Unified workflow with:
- Trigger: `on: push: tags: ['v*']`
- Matrix: `ubuntu-22.04` (Linux) + `macos-latest` (macOS)
- Submodule checkout: `submodules: recursive`
- ccache for build speed
- Linux system deps install
- `python build_submodules.py` (Z3, picotls compilation)
- Linux wheel: `python setup.py bdist_wheel --plat-name manylinux2014_x86_64`
- macOS wheel: `python -m build --wheel`
- Publish job collects all platform artifacts, publishes to real PyPI

**Delete:** `.github/workflows/macos-build-publish.yml` (merged into unified workflow)

### 2d. Create version bump script

Updates version in `pyproject.toml` only (single location post-migration).

### 2e. Outdated action versions

Updated in workflow: checkout v4, setup-python v5, upload/download-artifact v4, ubuntu-22.04.

### 2f. Manual setup required

- Verify `PYPI_API_TOKEN` secret exists in `ElNiak/PANTHER-Ivy` repo

---

## Step 3: panther-net (github.com/ElNiak/PANTHER)

### 3a. Fix existing publish workflow

Changes:
1. Add `submodules: recursive` to `actions/checkout@v4`
2. Switch from OIDC to API token auth
3. Change trigger from `on: release` to `on: push: tags: ['v*']`

### 3b. Create version bump script

Updates version in both `pyproject.toml` and `panther/__init__.py`.

### 3c. Manual setup required

- Add `PYPI_API_TOKEN` secret to `ElNiak/PANTHER` repo on GitHub

---

## Risks and Notes

- **manylinux version**: panther_ivy's Linux wheel uses `manylinux1_x86_64` which is rejected by real PyPI. Updated to `manylinux2014_x86_64`.
- **PyPI name availability**: Verify `ivy-lsp` is not already taken on pypi.org before first publish.
- **Submodule edits**: Changes to ivy_lsp and panther_ivy files must be committed in those submodule repos first, then the submodule reference updated in PANTHER.
- **PYPI_API_TOKEN**: Each repo needs its own token. Generate per-project scoped tokens from pypi.org account settings.
