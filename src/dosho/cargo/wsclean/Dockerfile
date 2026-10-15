# WSClean 3.6 and chgcentre, with IDG and EveryBeam available on both arches.
# KERN-10 supplies casacore and idg-dev; EveryBeam still builds from source.
FROM {base_image} AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends \
       cmake g++ make git wget idg-dev casacore-dev casacore-data \
       libgsl-dev libhdf5-dev libfftw3-dev libcfitsio-dev wcslib-dev \
       libblas-dev liblapack-dev libpython3-dev \
       libboost-date-time-dev libboost-filesystem-dev \
       libboost-program-options-dev libboost-system-dev \
    && rm -rf /var/lib/apt/lists/*

# WSClean 3.6 supports EveryBeam 0.6/0.7, not 0.8+.
RUN git clone --depth 1 -b v{everybeam_version} \
       https://git.astron.nl/RD/EveryBeam.git /everybeam \
    && cmake -S /everybeam -B /everybeam/build \
       -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_WITH_PYTHON=OFF -DBUILD_TESTING=OFF \
    && cmake --build /everybeam/build --parallel 4 \
    && cmake --install /everybeam/build \
    && ldconfig \
    && rm -rf /everybeam

RUN git clone --depth 1 -b v{package_version} \
       https://gitlab.com/aroffringa/wsclean.git /wsclean \
    && cmake -S /wsclean -B /wsclean/build \
       -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
       > /tmp/wsclean-configure.log 2>&1 \
    && cat /tmp/wsclean-configure.log \
    && grep -Fq 'EveryBeam library found.' /tmp/wsclean-configure.log \
    && grep -Fq 'Image domain gridder libraries found.' /tmp/wsclean-configure.log \
    && cmake --build /wsclean/build --parallel 4 \
    && cmake --install /wsclean/build \
    && ldconfig

FROM {base_image}
ENV DEBIAN_FRONTEND=noninteractive
# The compiler, headers and source trees stay in the build stage. The runtime
# libraries cover the native WSClean/EveryBeam binaries and IDG from the PPA.
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends \
       idg-dev libgsl27 libhdf5-103-1t64 libhdf5-cpp-103-1t64 \
       libfftw3-double3 libfftw3-single3 libcfitsio10t64 libwcs8 \
       libboost-date-time1.83.0 libboost-filesystem1.83.0 \
       libboost-program-options1.83.0 libboost-system1.83.0 \
       wget \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/ /usr/local/
RUN ldconfig \
    && chgcentre >/dev/null \
    && wsclean --version > /tmp/wsclean-version.txt \
    && cat /tmp/wsclean-version.txt \
    && grep -Fq 'EveryBeam is available.' /tmp/wsclean-version.txt \
    && grep -Fq 'IDG is available.' /tmp/wsclean-version.txt
CMD {cmd}
