from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from plugins.services.iut.config_schema import ImplementationConfig
from plugins.services.iut.config_schema import ImplementationType
@dataclass
class EnvironmentConfig:
    PROTOCOL_TESTED: str = ""
    RUST_LOG: str = "debug"
    RUST_BACKTRACE: str = "1"
    SOURCE_DIR: str = "/opt/"
    IVY_DIR: str = "$SOURCE_DIR/panther_ivy"
    PYTHON_IVY_DIR: str = "/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/"
    IVY_INCLUDE_PATH: str = "$IVY_INCLUDE_PATH:/usr/local/lib/python3.10/dist-packages/ms_ivy-1.8.25-py3.10-linux-x86_64.egg/ivy/include/1.7"
    Z3_LIBRARY_DIRS: str = "$IVY_DIR/submodules/z3/build"
    Z3_LIBRARY_PATH: str = "$IVY_DIR/submodules/z3/build"
    LD_LIBRARY_PATH: str = "$LD_LIBRARY_PATH:$IVY_DIR/submodules/z3/build"
    PROOTPATH: str = "$SOURCE_DIR"
    ADDITIONAL_PYTHONPATH: str = "/app/implementations/quic-implementations/aioquic/src/:$IVY_DIR/submodules/z3/build/python:$PYTHON_IVY_DIR"
    ADDITIONAL_PATH: str = "/go/bin:$IVY_DIR/submodules/z3/build"
    
    
@dataclass
class PantherIvyConfig(ImplementationConfig):
    name: str  = "panther_ivy" # Implementation name
    type: ImplementationType = ImplementationType.testers  # Default type for panther_ivy
    test: str = None  # Test name for testers
