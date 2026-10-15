# CASA's published casatools wheel is x86-only on Linux. Build the pinned
# modular source on the target architecture; plotms is deliberately separate.
FROM ubuntu:24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git curl cmake ninja-build build-essential gfortran \
    python3 python3-dev python3-pip python3-venv python3-numpy \
    flex bison swig pkg-config default-jdk \
    libreadline-dev libncurses-dev libblas-dev liblapack-dev \
    libfftw3-dev libcfitsio-dev wcslib-dev libeigen3-dev \
    libxerces-c-dev libxml2-dev libxslt1-dev libgsl-dev libsqlite3-dev \
    libprotobuf-dev protobuf-compiler-grpc libgrpc-dev libgrpc++-dev \
    libopenmpi-dev openmpi-bin && rm -rf /var/lib/apt/lists/*
COPY fetch.sh /opt/casa-build/fetch.sh
RUN sh /opt/casa-build/fetch.sh
COPY libsakura.sh /opt/casa-build/libsakura.sh
RUN sh /opt/casa-build/libsakura.sh
COPY casacore.sh /opt/casa-build/casacore.sh
RUN sh /opt/casa-build/casacore.sh
COPY casacpp.sh /opt/casa-build/casacpp.sh
RUN sh /opt/casa-build/casacpp.sh
COPY wheel.sh /opt/casa-build/wheel.sh
RUN sh /opt/casa-build/wheel.sh

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-venv libgfortran5 libstdc++6 \
    libreadline8t64 libncurses6 libblas3 liblapack3 libfftw3-double3 libfftw3-single3 \
    libcfitsio10t64 wcslib-tools libxerces-c3.2t64 libxml2 libxslt1.1 \
    libgsl27 libsqlite3-0 libgrpc++1.51t64 libprotobuf32t64 \
    libopenmpi3t64 && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/casa/install/lib /opt/casa/install/lib
COPY --from=build /opt/casa/venv /opt/casa/venv
COPY casasiteconfig.py /opt/casa/casasiteconfig.py
ENV PATH=/opt/casa/venv/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/casa/install/lib
ENV CASASITECONFIG=/opt/casa/casasiteconfig.py
RUN mkdir -p /opt/casa/data /usr/local/share/data && ln -s /opt/casa/data /usr/local/share/data/casacore \
    && python3 -m casaconfig --measurespath /opt/casa/data --update-all \
    && python3 -m casaconfig --measurespath /opt/casa/data --current-data
# Gate both platforms at build time, including before a Buildx --push.
RUN {cmd}
CMD {cmd}
