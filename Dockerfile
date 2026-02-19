ARG BASE_IMAGE

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

WORKDIR /opt/panther_ivy/

# Copy ONLY what Z3 needs (ordered by change frequency)
ADD build_submodules.py setup.py /opt/panther_ivy/
ADD patches /opt/panther_ivy/patches/
ADD submodules/z3 /opt/panther_ivy/submodules/z3/

# Apply patch to make Z3 git dependency optional for Docker builds
RUN patch -p1 < patches/z3-cmake-git-optional.patch

# Ensure output directories exist for COPY --from in later stages
RUN mkdir -p lib include ivy/lib ivy/z3 ivy/include

# Build Z3 only (BUILD_MODE passed inline to avoid extra ENV layer)
RUN BUILD_MODE=${BUILD_MODE} python3.10 build_submodules.py --z3-only

# =============================================================================
# STAGE 3: BASE - Main build (picotls, aiger, abc) + install
# =============================================================================

FROM deps AS base

ARG BUILD_MODE=""

ENV PYTHONPATH="/opt/panther_ivy/:${PYTHONPATH}"
WORKDIR /opt/panther_ivy/

# Copy application files (order: stable first, volatile last)
ADD setup.py build_submodules.py /opt/panther_ivy/
ADD patches /opt/panther_ivy/patches/
ADD submodules /opt/panther_ivy/submodules/
ADD ivy /opt/panther_ivy/ivy/
ADD lib /opt/panther_ivy/lib/

# Overlay Z3 build artifacts from z3-builder stage
COPY --from=z3-builder /opt/panther_ivy/lib/ /opt/panther_ivy/lib/
COPY --from=z3-builder /opt/panther_ivy/include/ /opt/panther_ivy/include/

# Install build toolchain
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential git ninja-build binutils gcc g++ gdb && \
    rm -rf /var/lib/apt/lists/*

# Build remaining submodules (skip Z3) + install
# BUILD_MODE passed inline to avoid invalidating COPY layers on mode change
RUN BUILD_MODE=${BUILD_MODE} python3.10 build_submodules.py --skip-z3 && \
    sudo python3.10 setup.py install && \
    mkdir -p submodules/z3/build/python/z3 && \
    mkdir -p ivy/z3 && \
    if [ ! -f lib/libz3.so ]; then \
        echo "ERROR: lib/libz3.so not found - Z3 build may have failed"; \
        exit 1; \
    fi && \
    cp lib/libz3.so submodules/z3/build/python/z3/ && \
    cp lib/libz3.so submodules/z3/build/ && \
    cp lib/libz3.so ivy/z3/ && \
    echo "Successfully copied libz3.so to all required locations"

ADD protocol-testing /opt/panther_ivy/protocol-testing/

# =============================================================================
# FINAL STAGE: Runtime configuration
# =============================================================================

FROM base AS final

ARG VERSION
ARG BUILD_MODE

LABEL service.type="tester"
LABEL service.name="panther_ivy"
LABEL version="${VERSION}"
LABEL build.mode="${BUILD_MODE}"
LABEL runtime.description="PANTHER IVY formal verification tester environment"

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3.10 --version && echo "IVY tester runtime healthy" || exit 1

WORKDIR /opt/panther_ivy

CMD ["/bin/bash"]
