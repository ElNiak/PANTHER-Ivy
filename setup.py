import os

from setuptools import setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name."""

    def has_ext_modules(self):
        return True


kwargs = {}
if not os.environ.get("PURE_PYTHON_BUILD"):
    kwargs["distclass"] = BinaryDistribution

setup(**kwargs)
