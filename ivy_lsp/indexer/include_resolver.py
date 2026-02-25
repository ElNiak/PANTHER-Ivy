"""Resolve Ivy ``include`` directives to absolute file paths."""

from __future__ import annotations

import os
from typing import List, Optional


class IncludeResolver:
    """Resolve ``include X`` to absolute file paths.

    Search order:
    1. Same directory as the including file
    2. Workspace root directory
    3. Standard library (``ivy/include/1.7/``)
    """

    def __init__(
        self,
        workspace_root: str,
        ivy_include_path: Optional[str] = None,
    ) -> None:
        self._workspace_root = os.path.abspath(workspace_root)
        self._ivy_include_path = ivy_include_path

    def resolve(
        self, include_name: str, from_file: str
    ) -> Optional[str]:
        """Resolve an include name to an absolute file path.

        Args:
            include_name: The bare name from ``include X`` (without .ivy).
            from_file: Absolute path of the file containing the include.

        Returns:
            Absolute path to the resolved .ivy file, or None if not found.
        """
        fname = include_name + ".ivy"

        # 1. Same directory as the including file
        from_dir = os.path.dirname(os.path.abspath(from_file))
        candidate = os.path.join(from_dir, fname)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

        # 2. Workspace root
        candidate = os.path.join(self._workspace_root, fname)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

        # 3. Standard library
        std_dir = self._get_std_include_dir()
        if std_dir is not None:
            candidate = os.path.join(std_dir, fname)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        return None

    def find_all_ivy_files(self, root: Optional[str] = None) -> List[str]:
        """Walk the directory tree and return all .ivy file paths, sorted.

        Args:
            root: Directory to search. Defaults to workspace_root.

        Returns:
            Sorted list of absolute paths to .ivy files.
        """
        search_root = root or self._workspace_root
        result: List[str] = []
        for dirpath, _dirnames, filenames in os.walk(search_root):
            for fn in filenames:
                if fn.endswith(".ivy"):
                    result.append(os.path.join(dirpath, fn))
        return sorted(result)

    def _get_std_include_dir(self) -> Optional[str]:
        """Locate the Ivy standard library include directory.

        Tries the custom ``ivy_include_path`` first, then attempts to
        import ``ivy`` and locate ``ivy/include/<version>/``, selecting
        the highest version directory available.

        Returns:
            Absolute path to the standard library include directory,
            or None if not found.
        """
        if self._ivy_include_path is not None:
            return self._ivy_include_path
        try:
            import ivy as ivy_mod

            ivy_dir = os.path.dirname(os.path.abspath(ivy_mod.__file__))
            inc_base = os.path.join(ivy_dir, "include")
            if not os.path.isdir(inc_base):
                return None
            best: Optional[str] = None
            for d in os.listdir(inc_base):
                full = os.path.join(inc_base, d)
                if os.path.isdir(full) and d.replace(".", "").isdigit():
                    if best is None or d > best:
                        best = d
            if best is not None:
                return os.path.join(inc_base, best)
        except ImportError:
            pass
        return None
