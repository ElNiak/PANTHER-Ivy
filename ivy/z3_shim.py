"""Z3 import shim -- prefers local ivy/z3/ bindings when available.

In Docker (z3_source=local), the Dockerfile installs local Z3 as the system
'z3' package, so 'import z3' already resolves correctly. This shim serves as
a defensive fallback for non-Docker environments where ivy/z3/ was populated
by build_submodules.py but not installed as a system package.
"""
import os as _os

_local_z3_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'z3')
_has_local_z3 = _os.path.isfile(_os.path.join(_local_z3_dir, 'z3core.py'))

if _has_local_z3:
    from .z3 import *
    # Export underscore-prefixed utilities that wildcard import skips
    try:
        from .z3 import _to_ast_array, _to_expr_ref
    except ImportError:
        pass
else:
    from z3 import *
    # Export underscore-prefixed utilities that wildcard import skips.
    # Try z3 top-level first, then z3.z3 submodule (where they're defined).
    try:
        from z3 import _to_ast_array, _to_expr_ref
    except ImportError:
        try:
            from z3.z3 import _to_ast_array, _to_expr_ref
        except ImportError:
            pass
    try:
        from z3 import _z3_assert
    except ImportError:
        # _z3_assert is defined in z3/z3.py but is underscore-prefixed, so
        # z3/__init__.py's `from .z3 import *` does NOT re-export it (Python
        # convention: wildcard imports skip names starting with '_').
        #
        # This means `from z3 import _z3_assert` fails with pip z3-solver
        # even though the function still exists in z3.z3._z3_assert.
        #
        # Definition in Z3 source (unchanged since at least 4.7.1 through 4.13.4):
        #   src/api/python/z3/z3.py  (line 87 in 4.7.1, line 105 in 4.13.4)
        #   https://github.com/Z3Prover/z3/blob/z3-4.13.4/src/api/python/z3/z3.py#L105
        #
        # Package __init__.py that causes the import to fail:
        #   https://github.com/Z3Prover/z3/blob/z3-4.13.4/src/api/python/z3/__init__.py
        from z3 import Z3Exception
        def _z3_assert(cond, msg):
            if not cond:
                raise Z3Exception(msg)
