FROM panther_base_service_panther:latest

ENV DEBIAN_FRONTEND=noninteractive
# Define build arguments for version-specific configurations
ARG VERSION=production
ARG DEPENDENCIES="[]"  # JSON-formatted list of dependencies
ENV VERSION=${VERSION}
ENV DEPENDENCIES=${DEPENDENCIES}

RUN apt update; \
    add-apt-repository --yes ppa:deadsnakes/ppa; \
    apt update; \
    apt --fix-missing -y install python3.10 \
    python3.10-dev \
    python3.10-tk \
    build-essential \
    python3-ply \
    alien \
    iptables\
    iproute2 \
    iputils-ping \
    tzdata \
    curl \
    tar \
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
    libgflags-dev \
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
    libreadline-dev \
    dsniff \
    sudo

    
# picotls
RUN apt-get install -y jq
# Function to parse and build dependencies
# TODO make more modular
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
            make check && \
            echo "Successfully built dependency '$DEP_NAME'"; \
        else \
            echo "Invalid dependency configuration: $dep"; \
            exit 1; \
        fi; \
    done



# Tester-specific dependencies + installation
# ARG USE_LOCAL=1  # 1: Use local files, 0: Clone from repo
# RUN if [ "$USE_LOCAL" = "0" ]; then \
#         cd /opt && \
#         git clone https://github.com/ElNiak/PANTHER-Ivy.git panther_ivy && \
#         cd /opt/panther_ivy && \
#         git checkout ${VERSION} && \
#         git submodule update --init --recursive \
#     fi


RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10
# For Panther-Ivy
RUN python3.10 -m pip install pexpect \
    chardet \
    pandas \
    scandir \
    ply  \
    pygraphviz \ 
    pydot \
    progressbar2

# For Ivy
# .gitmodules 
ADD setup.py build_submodules.py /opt/panther_ivy/
ADD templates /opt/panther_ivy/templates/
ADD submodules /opt/panther_ivy/submodules/
# TODO only python file for building
ADD ivy /opt/panther_ivy/ivy/
ADD lib /opt/panther_ivy/lib/
ADD scripts /opt/panther_ivy/scripts/

ENV PYTHONPATH="$$PYTHONPATH:/opt/panther_ivy/"

WORKDIR /opt/panther_ivy/

RUN python3.10 -m pip install . ;\
    python3.10 build_submodules.py; \
    sudo python3.10 setup.py install; \
    cp lib/libz3.so submodules/z3/build/python/z3;


ADD protocol-testing /opt/panther_ivy/protocol-testing/

# Set entrypoint (can be overridden)
ENTRYPOINT [ "/bin/sh", "-l", "-c" ]