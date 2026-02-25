import codecs
import os
import platform
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.dist import Distribution


# Workaround for bdist_wheel so that we get a platform-specific package
class BinaryDistribution(Distribution):
    """Distribution which always forces a binary package with platform name"""

    def has_ext_modules(foo):
        return True


# Get the long description from the README file
here = os.path.abspath(os.path.dirname(__file__))
try:
    with codecs.open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = f.read()
except:
    # This happens when running tests
    long_description = None

setup(
    name="panther_ms_ivy",
    python_requires=">=3.10",
    version="1.8.26",
    description="IVy verification tool",
    long_description=long_description,
    url="https://github.com/ElNiak/Panther-IVy",
    author="IVy team",
    author_email="nomail@example.com",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"])
    + [
        "ivy_lsp",
        "ivy_lsp.features",
        "ivy_lsp.indexer",
        "ivy_lsp.parsing",
        "ivy_lsp.utils",
    ],
    package_dir={"ivy_lsp": "ivy_lsp/ivy_lsp"},
    package_data=(
        {
            "ivy": [
                "include/*/*.ivy",
                "include/*/*.h",
                "include/*.h",
                "lib/*.dll",
                "lib/*.lib",
                "z3/*.dll",
                "z3/*.py",
            ]
        }
        if platform.system() == "Windows"
        else (
            {
                "ivy": [
                    "include/*/*.ivy",
                    "include/*/*.h",
                    "include/*.h",
                    "lib/*.dylib",
                    "lib/*.a",
                    "z3/*.dylib",
                    "z3/*.py",
                    "bin/*",
                ]
            }
            if platform.system() == "Darwin"
            else {
                "ivy": [
                    "include/*/*.ivy",
                    "include/*/*.h",
                    "include/*.h",
                    "lib/*.so",
                    "lib/*.a",
                    "z3/*.so",
                    "z3/*.py",
                    "ivy2/s3/ivyc_s3",
                    "bin/*",
                ]
            }
        )
    ),
    install_requires=[
        "pyparsing",
        "ply",
        "tarjan",
        "pydot",
        "ordered-set",
    ]
    + (["applescript"] if platform.system() == "Darwin" else []),
    extras_require={
        "z3": ["z3-solver==4.13.4.0"],
        "lsp": ["pygls>=1.0", "lsprotocol"],
    },
    entry_points={
        "console_scripts": [
            "ivy=ivy.ivy:main",
            "ivy_check=ivy.ivy_check:main",
            "ivy_to_cpp=ivy.ivy_to_cpp:main",
            "ivy_show=ivy.ivy_show:main",
            "ivy_ev_viewer=ivy.ivy_ev_viewer:main",
            "ivyc=ivy.ivy_to_cpp:ivyc",
            "ivy_to_md=ivy.ivy_to_md:main",
            "ivy_libs=ivy.ivy_libs:main",
            "ivy_shell=ivy.ivy_shell:main",
            "ivy_launch=ivy.ivy_launch:main",
            "ivy_lsp=ivy_lsp.__main__:main",
        ],
    },
    zip_safe=False,
    distclass=BinaryDistribution,
)
