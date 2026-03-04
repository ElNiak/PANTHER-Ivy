ARG BASE_IMAGE
ARG Z3_SOURCE="local"

# =============================================================================
# STAGE 1: DEPS - Shared toolchain
# =============================================================================

FROM ${BASE_IMAGE} AS deps

ENV DEBIAN_FRONTEND=noninteractive
ARG VERSION=master
ARG DEPENDENCIES="[]"

ENV DEPENDENCIES=${DEPENDENCIES}
ENV VERSION=${VERSION}

RUN printf "Building Panther-Ivy version: %s - Dependencies: %s\n" "${VERSION}" "${DEPENDENCIES}"

RUN apt update && \
    add-apt-repository --yes ppa:deadsnakes/ppa && \
    apt update && \
    apt --fix-missing -y install \
    build-essential \
    python3-ply \
    alien \
    iptables \
    iproute2 \
    iputils-ping \
    tzdata \
    curl \
    tar \
    gcc \
    g++ \
    cmake \
    tix \
    pkg-config \
    libssl-dev \
    lsof \
    graphviz \
    graphviz-dev \
    doxygen \
    faketime \
    libscope-guard-perl \
    libtest-tcp-perl \
    libbrotli-dev \
    libev-dev \
    libhttp-parser-dev \
    libbsd-dev \
    snapd \
    rand \
    binutils \
    binutils-dev \
    autoconf \
    automake \
    autotools-dev \
    libtool \
    libjemalloc-dev \
    libboost-all-dev \
    libboost-dev \
    ca-certificates \
    mime-support \
    libevent-dev \
    libdouble-conversion-dev \
    libgflags-dev \
    libgoogle-glog-dev \
    libiberty-dev \
    liblz4-dev \
    liblzma-dev \
    libsnappy-dev \
    zlib1g-dev \
    libsodium-dev \
    libffi-dev \
    cargo \
    libunwind-dev \
    radare2 \
    strace \
    bridge-utils \
    libreadline-dev \
    tk \
    libgv-tcl \
    libgraphviz-dev \
    libdevil1c2 \
    libgts-0.7-5 \
    liblasi0 \
    tcl-dev \
    tcl \
    libgmp-dev \
    dsniff \
    sudo \
    jq \
    ninja-build \
    libomp-dev \
    git \
    clang \
    clang-tidy \
    clang-format

# CPython feature headers (bz2, sqlite, zlib, ssl, tk, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    zlib1g-dev libbz2-dev liblzma-dev \
    libsqlite3-dev libssl-dev libffi-dev libreadline-dev \
    tk-dev tcl-dev libncursesw5-dev libgdbm-dev libnss3-dev libedit-dev \
    uuid-dev

# Install pyenv (skip if already exists from base image)
RUN if [ -d "$HOME/.pyenv" ]; then \
        echo "pyenv already installed, configuring environment..."; \
    else \
        echo "Installing pyenv..." && \
        curl https://pyenv.run | bash; \
    fi && \
    echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc && \
    echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc && \
    export PATH="$HOME/.pyenv/bin:$PATH" && \
    eval "$(pyenv init -)" && \
    eval "$(pyenv virtualenv-init -)" && \
    # Install Python 3.10.12 if not already installed
    if ! pyenv versions | grep -q "3.10.12"; then \
        echo "Installing Python 3.10.12..." && \
        pyenv install 3.10.12; \
    else \
        echo "Python 3.10.12 already installed"; \
    fi && \
    pyenv global 3.10.12 && \
    pyenv rehash && \
    ln -sf "$(pyenv which python3.10)" /usr/local/bin/python3.10 && \
    ln -sf "$(pyenv which python)"     /usr/local/bin/python && \
    python3.10 -V && which python3.10 && python -V && which python

# Build external dependencies
RUN cd /opt && \
    echo "Starting dependency installation..." && \
    echo $DEPENDENCIES | jq -c '.[]' | while read -r dep; do \
    DEP_NAME=$(echo $dep | jq -r '.name'); \
    DEP_URL=$(echo $dep | jq -r '.url'); \
    DEP_COMMIT=$(echo $dep | jq -r '.commit'); \
    if [ -n "$DEP_NAME" ] && [ -n "$DEP_URL" ] && [ -n "$DEP_COMMIT" ]; then \
    echo "Cloning dependency '$DEP_NAME' from '$DEP_URL' at commit '$DEP_COMMIT'" && \
    git clone "$DEP_URL" "$DEP_NAME" && \
    cd "$DEP_NAME" && \
    git checkout "$DEP_COMMIT" && \
    git submodule update --init --recursive && \
    OPENSSL_INCLUDE_DIR="/usr/include/openssl" cmake . && \
    make && \
    (make check || echo "[warn] make check failed (non-fatal)") && \
    echo "Successfully built dependency '$DEP_NAME'"; \
    else \
    echo "Invalid dependency configuration: $dep"; \
    exit 1; \
    fi; \
    done

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10

RUN python3.10 -m pip install pexpect \
    chardet \
    pandas \
    scandir \
    ply  \
    pygraphviz \
    pydot \
    progressbar2

# =============================================================================
# STAGE 2: Z3-BUILDER - Isolated Z3 compilation
# Only rebuilds when submodules/z3/, patches/, or build_submodules.py change.
# Changes to ivy/ or lib/ do NOT trigger Z3 rebuild (~30 min savings).
# =============================================================================

FROM deps AS z3-builder

ARG BUILD_MODE=""
ARG Z3_SOURCE="local"

WORKDIR /opt/panther_ivy/

# Copy ONLY what Z3 needs (ordered by change frequency)
ADD build_submodules.py setup.py pyproject.toml /opt/panther_ivy/
ADD patches /opt/panther_ivy/patches/
ADD submodules/z3 /opt/panther_ivy/submodules/z3/

# Apply patch only when building Z3 from submodule
RUN if [ "$Z3_SOURCE" = "local" ]; then \
        patch -p1 < patches/z3-cmake-git-optional.patch; \
    fi

# Ensure output directories exist for COPY --from in later stages
RUN mkdir -p lib include ivy/lib ivy/z3 ivy/include

# Build Z3 only when Z3_SOURCE=local (BUILD_MODE passed inline to avoid extra ENV layer)
RUN if [ "$Z3_SOURCE" = "local" ]; then \
        BUILD_MODE=${BUILD_MODE} python3.10 build_submodules.py --z3-only; \
    else \
        echo "Z3_SOURCE=pip: skipping local Z3 build (will use pip z3-solver)"; \
    fi

# =============================================================================
# STAGE 3: BASE - Main build (picotls, aiger, abc) + install
# =============================================================================

FROM deps AS base

ARG BUILD_MODE=""
ARG Z3_SOURCE="local"

ENV PYTHONPATH="/opt/panther_ivy/:${PYTHONPATH}"
WORKDIR /opt/panther_ivy/

# Copy application files (order: stable first, volatile last)
ADD setup.py build_submodules.py pyproject.toml /opt/panther_ivy/
ADD patches /opt/panther_ivy/patches/
ADD submodules /opt/panther_ivy/submodules/
ADD ivy /opt/panther_ivy/ivy/
ADD lib /opt/panther_ivy/lib/

# Verify z3_shim fix is deployed (catches stale build context)
RUN grep -q "z3_shim" ivy/ivy_z3_utils.py || \
    (echo "ERROR: ivy_z3_utils.py does not import z3_shim — build context has stale files" && exit 1)

# Overlay Z3 build artifacts from z3-builder stage
COPY --from=z3-builder /opt/panther_ivy/lib/ /opt/panther_ivy/lib/
COPY --from=z3-builder /opt/panther_ivy/include/ /opt/panther_ivy/include/
COPY --from=z3-builder /opt/panther_ivy/ivy/z3/ /opt/panther_ivy/ivy/z3/
COPY --from=z3-builder /opt/panther_ivy/ivy/lib/ /opt/panther_ivy/ivy/lib/
COPY --from=z3-builder /opt/panther_ivy/ivy/include/ /opt/panther_ivy/ivy/include/

# If using pip Z3, remove stale local Z3 artifacts that could cause ctypes
# Ast type mismatches (two different Ast classes from different module paths).
# The z3-builder stage creates empty dirs for pip mode, but the ADD ivy/ above
# may have copied local z3 bindings from the source tree.
RUN if [ "$Z3_SOURCE" != "local" ]; then \
        rm -rf ivy/z3/*.py ivy/z3/*.so lib/libz3.* && \
        echo "Z3_SOURCE=pip: cleaned stale local Z3 artifacts from ivy/z3/ and lib/"; \
    fi

# Install build toolchain
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential git ninja-build binutils gcc g++ gdb && \
    rm -rf /var/lib/apt/lists/*

# Build remaining submodules (skip Z3) + install
# BUILD_MODE passed inline to avoid invalidating COPY layers on mode change
# NOTE: When Z3_SOURCE=local, both Python bindings and C++ test binaries
#   use Z3 4.7.1 from the submodule. When Z3_SOURCE=pip, Python uses 4.13.4.0.
RUN BUILD_MODE=${BUILD_MODE} python3.10 build_submodules.py --skip-z3 && \
    if [ "$Z3_SOURCE" = "local" ]; then \
        # Install locally-built Z3 Python bindings as the system 'z3' package. \
        # This ensures 'import z3' uses v4.7.1, matching the C++ libz3.so. \
        mkdir -p /tmp/z3-pkg/z3 && \
        cp ivy/z3/*.py /tmp/z3-pkg/z3/ && \
        cp lib/libz3.so /tmp/z3-pkg/z3/ && \
        printf 'from setuptools import setup, find_packages\nsetup(name="z3-local", version="4.7.1", packages=find_packages(), package_data={"z3": ["*.so", "*.dylib"]})\n' > /tmp/z3-pkg/setup.py && \
        sudo python3.10 -m pip install /tmp/z3-pkg/ && \
        rm -rf /tmp/z3-pkg ; \
    else \
        sudo python3.10 -m pip install z3-solver==4.13.4.0 && \
        # Copy pip z3-solver's C++ headers and shared library to where
        # ivy_to_cpp.py's get_lib_dirs() expects them (ivy/include/, ivy/lib/).
        Z3_PKG_DIR=$(python3.10 -c "import z3; import os; print(os.path.dirname(os.path.abspath(z3.__file__)))") && \
        echo "Z3 pip package at: $Z3_PKG_DIR" && \
        mkdir -p ivy/include ivy/lib && \
        if [ -d "$Z3_PKG_DIR/include" ]; then \
            cp -r "$Z3_PKG_DIR/include/"* ivy/include/ && \
            echo "Copied Z3 C++ headers from pip package to ivy/include/"; \
        else \
            echo "WARN: pip z3-solver has no include/ dir — C++ compilation may fail"; \
        fi && \
        if [ -d "$Z3_PKG_DIR/lib" ]; then \
            cp "$Z3_PKG_DIR/lib/"libz3* ivy/lib/ && \
            echo "Copied libz3 from pip package to ivy/lib/"; \
        else \
            Z3_LIB=$(python3.10 -c "import z3; import os; d=os.path.dirname(os.path.abspath(z3.__file__)); [print(os.path.join(d,f)) for f in os.listdir(d) if f.startswith('libz3') and (f.endswith('.so') or f.endswith('.dylib'))]" 2>/dev/null | head -1) && \
            if [ -n "$Z3_LIB" ]; then \
                cp "$Z3_LIB" ivy/lib/ && \
                echo "Copied libz3 from pip package root to ivy/lib/"; \
            else \
                echo "WARN: pip z3-solver has no lib/ dir or libz3 — C++ linking may fail"; \
            fi; \
        fi ; \
    fi && \
    sudo env PURE_PYTHON_BUILD=1 python3.10 -m pip install . && \
    python3.10 -c "import z3; print('Python Z3 version:', z3.get_version_string())" && \
    if [ "$Z3_SOURCE" = "local" ]; then \
        # C++ linking: make libz3.so discoverable by the dynamic linker \
        if [ ! -f lib/libz3.so ]; then \
            echo "ERROR: lib/libz3.so not found - Z3 build may have failed"; \
            exit 1; \
        fi && \
        echo "/opt/panther_ivy/lib" | sudo tee /etc/ld.so.conf.d/panther-z3.conf && \
        sudo ldconfig && \
        echo "Z3_SOURCE=local: Python=4.7.1 (local pkg), C++=4.7.1 (ldconfig)"; \
    else \
        # For pip mode, make ivy/lib/libz3.so discoverable for C++ test binaries
        if [ -f ivy/lib/libz3.so ] || ls ivy/lib/libz3* >/dev/null 2>&1; then \
            echo "/opt/panther_ivy/ivy/lib" | sudo tee /etc/ld.so.conf.d/panther-z3.conf && \
            sudo ldconfig && \
            echo "Z3_SOURCE=pip: Python=4.13.4.0, C++ headers+lib copied to ivy/{include,lib}"; \
        else \
            echo "Z3_SOURCE=pip: Python=4.13.4.0 (pip z3-solver, no C++ artifacts copied)"; \
        fi; \
    fi

# Verify egg has the z3_shim fix (catches pyenv egg caching stale code)
RUN python3.10 -c "\
import importlib.util, pathlib; \
spec = importlib.util.find_spec('ivy.ivy_z3_utils'); \
assert spec and spec.origin, 'Could not locate ivy.ivy_z3_utils module'; \
first_line = pathlib.Path(spec.origin).read_text().split('\n')[0]; \
assert 'z3_shim' in first_line, f'Egg has stale ivy_z3_utils.py: {first_line}'; \
print(f'OK: egg ivy_z3_utils.py imports z3_shim (from {spec.origin})')"

# Verify Ast types are consistent (catches the specific ctypes mismatch)
RUN python3.10 -c "\
from ivy import z3_shim, ivy_z3_utils; \
shim_ast = getattr(z3_shim, 'Ast', None); \
utils_ast = getattr(ivy_z3_utils, 'Ast', None); \
assert not (shim_ast and utils_ast) or shim_ast is utils_ast, \
    f'Ast mismatch: z3_shim.Ast={shim_ast} vs ivy_z3_utils.Ast={utils_ast}'; \
print(f'OK: Ast type consistent ({shim_ast})' if (shim_ast and utils_ast) else f'WARN: could not verify Ast types (shim={shim_ast}, utils={utils_ast})')"

# Verify ivy_to_cpp.py uses Python-based Z3 version detection (not __has_include).
RUN python3.10 -c "\
import pathlib; \
src = pathlib.Path('/opt/panther_ivy/ivy/ivy_to_cpp.py').read_text(); \
assert 'import z3 as _z3_ver_mod' in src, \
    'STALE: ivy_to_cpp.py still uses __has_include for Z3 version detection'; \
assert '#if defined(Z3_MAJOR_VERSION) && (Z3_MAJOR_VERSION > 4' in src, \
    'STALE: ivy_to_cpp.py has wrong #if guard for parse_smtlib2_compat'; \
assert 'Z3_MINOR_VERSION >= 12' in src, \
    'STALE: ivy_to_cpp.py missing Z3 4.12 version guard for mk_enum/mk_decl'; \
print('OK: ivy_to_cpp.py uses Python-based Z3 version macros with 4.12 guards')"

ADD protocol-testing /opt/panther_ivy/protocol-testing/

# =============================================================================
# FINAL STAGE: Runtime configuration
# =============================================================================

FROM base AS final

ARG VERSION
ARG BUILD_MODE
ARG Z3_SOURCE

LABEL service.type="tester"
LABEL service.name="panther_ivy"
LABEL version="${VERSION}"
LABEL build.mode="${BUILD_MODE}"
LABEL z3.source="${Z3_SOURCE}"
LABEL runtime.description="PANTHER IVY formal verification tester environment"

WORKDIR /opt/panther_ivy/

CMD ["/bin/bash"]
