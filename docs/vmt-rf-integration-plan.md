# Plan: Integrate `vmt-rf` Branch from `kenmcmil/ivy` into PANTHER-Ivy

## Context

**Problem**: The upstream IVy repository (`kenmcmil/ivy`) has a `vmt-rf` branch containing valuable formal verification features: VMT (Verification Modulo Theories) enhancements, MyPyVy integration, liveness ranking tactics, CEGAR refinement, and Z3 solver improvements. These capabilities would strengthen PANTHER-Ivy's protocol testing power but the fork has diverged significantly.

**Goal**: Merge ALL `vmt-rf` features into the PANTHER-Ivy fork without breaking existing QUIC protocol testing functionality. Use a dedicated branch + PR workflow for safety.

**Key Finding**: After thorough analysis, the conflict surface is **near-zero**. The vmt-rf branch modifies `ivy/` core files, while PANTHER customizations are in entirely separate files (mixins, config, Docker, protocol models). Only 3-4 files need manual conflict resolution, and they have clear resolution strategies.

## Approach: Direct Git Merge

A standard `git merge` is recommended because:
- Shared git ancestry exists (both repos fork from the same origin)
- Preserves complete commit history for `git blame`
- Creates a proper merge base for future upstream syncs
- Near-zero conflict overlap makes this straightforward

### Z3 Strategy: Keep Vendored Z3 (for now)

The `vmt-rf` branch includes a `z3refactor` sub-merge that changes Z3 from vendored (`import ivy.z3`) to system-installed (`import z3`). We will **keep PANTHER's vendored Z3** because:
- PANTHER's `build_submodules.py` has 4 custom build modes (debug-asan, rel-lto, release-static-pgo)
- Dockerfiles build Z3 from source using the vendored submodule
- kenmcmil/z3 at `425291ee2` is actually newer than what z3refactor points to
- Z3 migration can be a separate follow-up PR

This means we must fix `import z3` to `import ivy.z3 as z3` in ~6-7 new files after merge.

---

## Merge Execution Steps

### Step 1: Safety Setup
```bash
git branch backup-production-pre-vmtrf production
git stash  # If any uncommitted changes
```

### Step 2: Add Upstream Remote & Fetch
```bash
git remote add upstream https://github.com/kenmcmil/ivy.git
git fetch upstream vmt-rf
git fetch upstream master

# Verify common ancestor exists
git merge-base production upstream/vmt-rf
```

### Step 3: Merge
```bash
git merge upstream/vmt-rf --no-ff -m "Merge upstream vmt-rf: VMT, MyPyVy, liveness tactics, z3refactor"
```

### Step 4: Resolve Conflicts

Expected conflicts and resolution:

| File | Resolution |
|------|-----------|
| `.gitmodules` | `git checkout --ours .gitmodules` (keep kenmcmil/z3 URL) |
| `build_submodules.py` | `git checkout --ours build_submodules.py` (keep PANTHER's 4 build modes) |
| `submodules/z3` | `git checkout --ours submodules/z3` (keep PANTHER's Z3 pointer) |
| `doc/install.md` | `git checkout --theirs doc/install.md` (accept upstream) |
| `setup.py` | Keep PANTHER's version, add only genuinely new dependencies |
| `ivy/ivy_solver.py` | Keep vendored `import ivy.z3`, accept functional changes |
| `ivy/ivy_alpha.py`, `ivy/ivy_core.py`, `ivy/ivy_interp.py`, `ivy/z3_utils.py` | Keep PANTHER's `import ivy.z3` pattern |

### Step 5: Fix Z3 Imports in New Files

Change in all new files from vmt-rf:
- `import z3` to `import ivy.z3 as z3`
- `from z3 import X` to `from ivy.z3 import X`

### Step 6: Static Verification

1. Verify PANTHER files are unchanged
2. Verify new vmt-rf files exist
3. Python syntax check on all modified/new ivy/ files
4. Verify z3 imports are consistent (no system z3 imports remain)
5. Verify protocol-testing/ is intact (~667 .ivy files)

### Step 7: Push & Create PR

Push `integrate/vmt-rf` to origin and create PR targeting `production`.

---

## Rollback Plan

| Stage | Rollback Command |
|-------|-----------------|
| During merge | `git merge --abort` |
| After commit, before push | `git checkout production && git branch -D integrate/vmt-rf` |
| After push, before PR merge | Close the PR |
| After PR merge to production | `git revert -m 1 <merge-commit-sha>` |
| Nuclear option | `git reset --hard backup-production-pre-vmtrf` |

## Critical Files

**Will be modified by merge (ivy/ core)**:
- `ivy/ivy_tactics.py` - +237 lines of liveness ranking tactics
- `ivy/ivy_check.py` - +53 lines verification improvements
- `ivy/ivy_actions.py` - +103 lines action system enhancements
- `ivy/ivy_vmt.py` - +82/-19 VMT export enhancements
- `ivy/ivy_temporal.py` - +12 lines temporal logic support
- `ivy/ivy_compiler.py` - Non-overlapping changes (auto-merge expected)
- `ivy/ivy_solver.py` - Functional improvements + z3 import conflict

**New files from vmt-rf**:
- `ivy/ivy_duoai.py` - AI/automation module
- `ivy/ivy_mypyvy.py` - MyPyVy integration
- `ivy/mypyvy_syntax.py` - MyPyVy syntax definitions
- `ivy/mypyvy_utils.py` - MyPyVy utilities
- `ivy/ivy_z3_utils.py` - Z3 utilities
- `ivy/ivy_distpy.py` - Distributed checking
- `ivy/ivy_ranking_infer.py` - Ranking inference

**Must remain unchanged (PANTHER-specific)**:
- `panther_ivy.py`, all `*mixin.py` files, `config_schema.py`
- `Dockerfile`, `Dockerfile.buildkit`, `build_submodules.py`
- `protocol-testing/` (667 .ivy files)
- `templates/`, `version_configs/`

## Follow-up Work (Separate PRs)

1. **Z3 Migration**: Migrate from vendored `ivy.z3` to system `z3-solver` pip package (aligning with upstream direction)
2. **MyPyVy Integration**: Create PANTHER command templates for MyPyVy-based specifications if useful for protocol testing
3. **Liveness Testing**: Explore using new liveness tactics for QUIC protocol liveness properties
