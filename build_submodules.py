import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()  # Current working directory
SUBMOD, IVY = ROOT / "submodules", ROOT / "ivy"

# ─────────── Build-mode table ───────────
MODES: dict[str, dict[str, object]] = {
    "": {"cmake": [], "static": False},  # shadow/original
    "debug-asan": {
        "cmake": [
            "-DCMAKE_BUILD_TYPE=Debug",
            "-DSANITIZE_ADDRESS=TRUE",
            "-DINCLUDE_GIT_HASH=FALSE",
            "-DINCLUDE_GIT_DESCRIBE=FALSE",
            "-DBUILD_LIBZ3_SHARED=FALSE",
        ],
        "static": False,
    },
    "rel-lto": {
        "cmake": [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DINCLUDE_GIT_HASH=FALSE",
            "-DINCLUDE_GIT_DESCRIBE=FALSE",
            "-DLINK_TIME_OPTIMIZATION=TRUE",
            "-DBUILD_LIBZ3_SHARED=FALSE",
            "-DUSE_LIB_GMP=TRUE",
            "-DDUSE_OPENMP=TRUE",
        ],
        "static": False,
    },
    "release-static-pgo": {
        "cmake": [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DLINK_TIME_OPTIMIZATION=TRUE",
            "-DINCLUDE_GIT_HASH=FALSE",
            "-DINCLUDE_GIT_DESCRIBE=FALSE",
            "-DBUILD_LIBZ3_SHARED=FALSE",
            "-DCMAKE_C_FLAGS=-fprofile-use",
            "-DCMAKE_CXX_FLAGS=-fprofile-use",
            "-DCMAKE_POSITION_INDEPENDENT_CODE=FALSE",
        ],
        "static": True,
    },
}

BUILD_MODE = os.getenv("BUILD_MODE", "")
Z3_BUILD_MODE = os.getenv("Z3_BUILD_MODE", BUILD_MODE)
if Z3_BUILD_MODE not in MODES:
    sys.exit(f"Unknown Z3_BUILD_MODE='{Z3_BUILD_MODE}'; choose one of {list(MODES)}")


def do_cmd(cmd):
    print(cmd)
    if status := os.system(cmd):
        exit(status)


def run_cmd(cmd, cwd=None):
    print(cmd if isinstance(cmd, str) else " ".join(cmd))
    print(f"Running in directory: {cwd if cwd else 'current directory'}")
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout (TODO: make configurable)
        )

        # Always print stdout for visibility
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")

        # Print stderr and exit on failure
        if result.returncode != 0:
            print(f"ERROR: Command failed with return code {result.returncode}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            sys.exit(result.returncode)

    except subprocess.TimeoutExpired:
        print(f"ERROR: Command timed out after 30 minutes")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Command execution failed: {e}")
        sys.exit(1)


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def make_dir_exist(dir):
    if not os.path.exists(dir):
        os.mkdir(dir)
    elif not os.path.isdir(dir):
        print(f"cannot create directory {dir}")
        exit(1)


def find_vs():
    import os

    try:
        windir = os.getenv("WINDIR")
        drive = windir[0]
    except Exception:
        drive = "C"
    for v in ["2019", "2017"]:
        for w in ["", " (x86)"]:
            dir = f"{drive}:\\Program Files{w}\\Microsoft Visual Studio\{v}"
            if os.path.exists(dir):
                for vers in ["Enterprise", "Professional", "Community"]:
                    vers_dir = dir + "\\" + vers
                    if os.path.exists(vers_dir):
                        vcvars = vers_dir + "\\VC\\Auxiliary\\Build\\vcvars64.bat"
                        if os.path.exists(vcvars):
                            return vcvars
    for v in range(15, 9, -1):
        for w in ["", " (x86)"]:
            dir = f"{drive}:\\Program Files{w}\\Microsoft Visual Studio {v}.0"
            vcvars = dir + "\\VC\\vcvars64.bat"
            if os.path.exists(vcvars):
                return vcvars
    print(
        "Cannot find a suitable version of Visual Studio (require 10.0-15.0 or 2017 or 2019)"
    )


def build_z3():
    print("--- Building Z3 ---")

    z3 = SUBMOD / "z3"
    if not z3.exists():
        sys.exit("submodules/z3 missing (git submodule update --init)")

    if BUILD_MODE in MODES and BUILD_MODE != "":
        print(f"Using CMake for Z3 build with BUILD_MODE={BUILD_MODE}")
        optimized_build_for_ivy_test_target(z3)
    else:
        print(f"Using legacy build for BUILD_MODE='{BUILD_MODE}'")
        legacy_build(z3)


def legacy_build(z3):
    # Use legacy mk_make.py method for original/Shadow compatibility
    print("Using legacy mk_make.py method for Z3 build")
    cmd = (
        f"python3 scripts/mk_make.py --python --prefix {str(ROOT)} --pypkgdir {str(IVY)}"
        # f'python3 scripts/mk_make.py --prefix {str(ROOT)}'
        if platform.system() != "Windows"
        else f"python3 scripts/mk_make.py -x --python --pypkgdir {str(IVY)}"
    )
    run_cmd(cmd, cwd=str(z3))

    build_dir = str(z3 / "build")

    if platform.system() == "Windows":
        run_cmd(f'"{find_vs()}" & nmake', cwd=build_dir)
    else:
        run_cmd("make -j 4", cwd=build_dir)
        run_cmd("make install", cwd=build_dir)


def optimized_build_for_ivy_test_target(z3):
    import shutil

    cfg = MODES[BUILD_MODE]
    build_dir = z3 / "build"
    print(
        f"Using CMake for Z3 build with BUILD_MODE={BUILD_MODE} and configuration: {cfg}"
    )
    print(f"Build directory: {build_dir}")
    # Allow incremental builds by default (critical for Docker cache mounts).
    # Set Z3_CLEAN_BUILD=1 to force a clean build when needed locally.
    if os.getenv("Z3_CLEAN_BUILD", "0") == "1" and build_dir.exists():
        print("Z3_CLEAN_BUILD=1: removing old build directory")
        shutil.rmtree(build_dir)

    ensure_dir(build_dir)

    cmake_cmd = "CC=gcc CXX=g++ "
    cmake_cmd += "cmake "
    cmake_cmd += '-G "Unix Makefiles" '
    cmake_cmd += f"-DCMAKE_INSTALL_PREFIX={ROOT}"

    # For LTO builds, use gcc-ar/gcc-ranlib/gcc-nm which understand LTO bitcode
    if BUILD_MODE in ("rel-lto", "release-static-pgo"):
        cmake_cmd += " -DCMAKE_AR=/usr/bin/gcc-ar"
        cmake_cmd += " -DCMAKE_RANLIB=/usr/bin/gcc-ranlib"
        cmake_cmd += " -DCMAKE_NM=/usr/bin/gcc-nm"

    for opt in cfg["cmake"]:
        cmake_cmd += f" {opt}"

    cmake_cmd += " ../"

    build_dir = str(build_dir)

    print(f"Running CMake command: {cmake_cmd} in {build_dir}")

    run_cmd(cmake_cmd, cwd=build_dir)
    # run_cmd("cmake --build . -j 4", cwd=build_dir)
    # run_cmd("cmake --install .", cwd=build_dir)
    run_cmd(
        "CC=gcc CXX=g++ make -j 1", cwd=build_dir
    )  # job-server FD problem. (emulation ?)

    # Install Z3 (installs libs, headers, and Python bindings)
    run_cmd("make install", cwd=build_dir)

    # stage artefacts into ivy/
    ensure_dir(IVY / "lib")
    ensure_dir(IVY / "include")
    for hdr in (ROOT / "include").glob("z3*.h"):
        shutil.copy2(hdr, IVY / "include" / hdr.name)

    if cfg["static"]:
        shutil.copy2(ROOT / "lib/libz3.a", IVY / "lib/libz3.a")
    else:
        for so in (ROOT / "lib").glob("libz3.*"):
            shutil.copy2(so, IVY / "lib" / so.name)


def install_z3():
    """Install Z3 Python bindings and libraries into ivy/ directory.

    For legacy builds (BUILD_MODE=""), make install with --pypkgdir already
    placed Python files in ivy/z3/. We still copy .so/.h files.

    For CMake builds (non-empty BUILD_MODE), we must also copy the
    generated Python binding files (z3core.py, z3consts.py) from the
    build directory, plus the source .py files.
    """
    import shutil

    print("--- Installing Z3 ---")
    make_dir_exist("ivy/lib")
    make_dir_exist("ivy/z3")

    if platform.system() == "Windows":
        do_cmd("copy submodules\\z3\\src\\api\\*.h ivy\\include")
        do_cmd('copy "submodules\\z3\\src\\api\\c++\\*.h" ivy\\include')
        do_cmd("copy submodules\\z3\\build\\*.dll ivy\\lib")
        do_cmd("copy submodules\\z3\\build\\*.lib ivy\\lib")
        do_cmd("copy submodules\\z3\\build\\*.dll ivy\\z3")
        do_cmd("copy submodules\\z3\\build\\python\\z3\\*.py ivy\\z3")
    elif platform.system() == "Darwin":
        do_cmd("cp include/*.h ivy/include")
        do_cmd("cp lib/*.dylib ivy/lib")
        do_cmd("cp lib/*.dylib ivy/z3")
    else:
        do_cmd("cp include/*.h ivy/include")
        if list((ROOT / "lib").glob("*.so")):
            do_cmd("cp lib/*.so ivy/lib")
            do_cmd("cp lib/*.so ivy/z3")
        elif list((ROOT / "lib").glob("*.a")):
            do_cmd("cp lib/*.a ivy/lib")

    # For CMake-based builds (non-empty BUILD_MODE), make install doesn't
    # use --pypkgdir, so Python bindings aren't placed in ivy/z3/ automatically.
    # Copy them explicitly from the build output and source tree.
    if BUILD_MODE in MODES and BUILD_MODE != "":
        z3_py_src = SUBMOD / "z3" / "src" / "api" / "python" / "z3"
        z3_build_py = SUBMOD / "z3" / "build" / "python" / "z3"

        # Copy source Python files (z3.py, __init__.py, z3num.py, etc.)
        if z3_py_src.exists():
            print(f"Copying Z3 Python source files from {z3_py_src}")
            for py_file in z3_py_src.glob("*.py"):
                shutil.copy2(py_file, IVY / "z3" / py_file.name)

        # Copy generated files (z3core.py, z3consts.py) from build output
        if z3_build_py.exists():
            print(f"Copying Z3 generated Python files from {z3_build_py}")
            for py_file in z3_build_py.glob("*.py"):
                shutil.copy2(py_file, IVY / "z3" / py_file.name)
        else:
            print(f"WARNING: Z3 build Python directory not found: {z3_build_py}")
            print("z3core.py and z3consts.py may be missing")

    # Verify Z3 Python bindings are complete
    required_files = ["__init__.py", "z3.py"]
    missing = [f for f in required_files if not (IVY / "z3" / f).exists()]
    if missing:
        print(f"WARNING: Z3 Python binding files missing from ivy/z3/: {missing}")
        # Fallback: copy from source tree
        z3_py_src = SUBMOD / "z3" / "src" / "api" / "python" / "z3"
        if z3_py_src.exists():
            print(f"Fallback: copying from {z3_py_src}")
            for py_file in z3_py_src.glob("*.py"):
                shutil.copy2(py_file, IVY / "z3" / py_file.name)
        # Re-check after fallback — fail hard if bindings are still missing
        still_missing = [f for f in required_files if not (IVY / "z3" / f).exists()]
        if still_missing:
            print(
                f"FATAL: Z3 Python bindings still missing after fallback: {still_missing}"
            )
            sys.exit(1)


def build_picotls():
    if not os.path.exists("submodules/picotls"):
        print(
            "submodules/picotls not found. try 'git submodule update; git submodule update'"
        )
        exit(1)

    cwd = os.getcwd()

    os.chdir("submodules/picotls")

    # TODO: extract commit from version_config
    # TODO: Building Docker image 'panther_ivy_rfc9000_rel-lto:latest':[91mfatal: not a git repository: /opt/panther_ivy/submodules/picotls/../../../../../../../.git/modules/panther/plugins/services/testers/panther_ivy/modules/submodules/picotls
    # do_cmd('git checkout 047c5fe20bb9ea91c1caded8977134f19681ec76')

    if platform.system() == "Windows":
        do_cmd(
            '"{}" & msbuild /p:OPENSSL64DIR=c:\\OpenSSL-Win64 picotlsvs\\picotls\\picotls.vcxproj'.format(
                find_vs()
            )
        )
    else:
        if platform.system() == "Darwin":
            do_cmd(
                'PKG_CONFIG_PATH="/usr/local/opt/openssl/lib/pkgconfig" cmake . -DOPENSSL_CRYPTO_LIBRARY=/usr/local/opt/openssl/lib/libcrypto.dylib -DOPENSSL_SSL_LIBRARY=/usr/local/opt/openssl/lib/libssl.dylib'
            )
        else:
            do_cmd("cmake .")
        do_cmd("make")

    os.chdir(cwd)


def install_picotls():
    make_dir_exist("ivy/lib")

    cwd = os.getcwd()

    os.chdir("submodules/picotls")

    if platform.system() == "Windows":
        do_cmd("copy include\\*.h ..\\..\\ivy\\include\\")
        if not os.path.exists("../../ivy/include/picotls"):
            do_cmd("mkdir ..\\..\\ivy\\include\\picotls")
        do_cmd("copy include\\picotls\\*.h ..\\..\\ivy\\include\\picotls\\")
        do_cmd("copy picotlsvs\\picotls\\*.h ..\\..\\ivy\\include\\picotls\\")
        do_cmd("copy picotlsvs\\picotls\\x64\\Debug\\picotls.lib ..\\..\\ivy\\lib\\")
    else:
        do_cmd("cp -a include/*.h include/picotls ../../ivy/include/")
        do_cmd("cp -a *.a ../../ivy/lib/")

    os.chdir(cwd)


def build_v2_compiler():
    cwd = os.getcwd()

    os.chdir("ivy/ivy2/s1")
    do_cmd("python3.10 ../../ivy_to_cpp.py target=repl ivyc_s1.ivy")
    do_cmd("g++ -O2 -o ivyc_s1 ivyc_s1.cpp -pthread")

    os.chdir("../s2")
    do_cmd("IVY_INCLUDE_PATH=../s1/include ../s1/ivyc_s1 ivyc_s2.ivy")
    do_cmd("g++ -I../s1/include -O2 -o ivyc_s2 -std=c++17 ivyc_s2.cpp")

    os.chdir("../s3")
    do_cmd("IVY_INCLUDE_PATH=../s2/include ../s2/ivyc_s2 ivyc_s3.ivy")

    os.chdir(cwd)


def build_aiger():
    cwd = os.getcwd()

    os.chdir("submodules/aiger")

    do_cmd("./configure.sh && make -j 4")

    os.chdir(cwd)


def install_aiger():
    make_dir_exist("ivy/bin")
    cwd = os.getcwd()

    os.chdir("submodules/aiger")

    do_cmd("cp -a aigtoaig ../../ivy/bin/")

    os.chdir(cwd)


def build_abc():
    cwd = os.getcwd()

    os.chdir("submodules/abc")

    do_cmd("make -j 4")

    os.chdir(cwd)


def install_abc():
    make_dir_exist("ivy/bin")
    cwd = os.getcwd()

    os.chdir("submodules/abc")

    do_cmd("cp -a abc ../../ivy/bin/")

    os.chdir(cwd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build panther_ivy submodules")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--z3-only",
        action="store_true",
        help="Build only Z3 (for Docker multi-stage z3-builder stage)",
    )
    group.add_argument(
        "--skip-z3",
        action="store_true",
        help="Skip Z3, build everything else (for Docker multi-stage main stage)",
    )
    parser.add_argument(
        "--z3-source",
        choices=["local", "pip"],
        default="local",
        help="Z3 source: 'local' builds from submodule, 'pip' uses pip z3-solver only",
    )
    args = parser.parse_args()

    print("--- Running build_submodules.py ---")

    if args.z3_only:
        if args.z3_source == "pip":
            print("[z3-only + pip mode] Skipping Z3 build, pip z3-solver will be used")
        else:
            print("[z3-only mode] Building Z3 from submodule")
            build_z3()
            install_z3()
    elif args.skip_z3:
        print("[skip-z3 mode] Skipping Z3, building picotls/aiger/abc")
        build_picotls()
        install_picotls()
        if platform.system() == "Windows":
            print("Model checking not supported on Windows")
        else:
            build_aiger()
            install_aiger()
            build_abc()
            install_abc()
    else:
        build_z3()
        install_z3()
        build_picotls()
        install_picotls()
        if platform.system() == "Windows":
            print("Model checking not supported on Windows")
        else:
            build_aiger()
            install_aiger()
            build_abc()
            install_abc()
