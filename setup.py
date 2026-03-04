import os
import shutil

from setuptools import setup, find_packages
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
from setuptools.dist import Distribution

here = os.path.dirname(os.path.abspath(__file__))


def _ensure_picotls():
    """Build picotls if ivy/lib/ or ivy/include/picotls/ are missing."""
    ivy_dir = os.path.join(here, "ivy")
    lib_dir = os.path.join(ivy_dir, "lib")
    include_picotls = os.path.join(ivy_dir, "include", "picotls")

    # Skip if already built
    if (
        os.path.isdir(lib_dir)
        and os.path.isdir(include_picotls)
        and any(f.endswith((".a", ".dylib", ".lib")) for f in os.listdir(lib_dir))
    ):
        return

    # Check submodule exists
    submod = os.path.join(here, "submodules", "picotls")
    if not os.path.isdir(submod):
        print(
            "WARNING: submodules/picotls not found, skipping picotls build\n"
            "  Run: git submodule update --init --recursive"
        )
        return

    # Check cmake available
    if not shutil.which("cmake"):
        print(
            "WARNING: cmake not found, skipping picotls build\n"
            "  Install: brew install cmake (macOS) / apt install cmake (Linux)"
        )
        return

    # Build by importing build_submodules with correct cwd
    saved_cwd = os.getcwd()
    try:
        os.chdir(here)
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_submodules", os.path.join(here, "build_submodules.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build_picotls()
        mod.install_picotls()
        print("picotls built and installed successfully")
    except Exception as e:
        print(
            f"WARNING: picotls build failed: {e}\n"
            "  Manual fallback: python build_submodules.py --picotls-only"
        )
    finally:
        os.chdir(saved_cwd)


class BuildPyWithPicotls(build_py):
    def run(self):
        _ensure_picotls()
        super().run()


class DevelopWithPicotls(develop):
    def run(self):
        _ensure_picotls()
        super().run()


class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name."""

    def has_ext_modules(self):
        return True


kwargs = {}
if not os.environ.get("PURE_PYTHON_BUILD"):
    kwargs["distclass"] = BinaryDistribution

setup(
    packages=find_packages(include=["ivy", "ivy.*"]),
    cmdclass={
        "build_py": BuildPyWithPicotls,
        "develop": DevelopWithPicotls,
    },
    **kwargs,
)
