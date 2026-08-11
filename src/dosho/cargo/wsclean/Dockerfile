# dosho image: WSClean interferometric imager, built from source on the KERN
# suite base, together with IDG and EveryBeam. PORTABLE=Yes throughout so the
# binaries run on any x86-64 CPU (no host-CPU instructions baked in).
# Rendered by `dosho images build WSCLEAN`.
#
# IDG and EveryBeam are source builds because KERN packages neither usably:
# it ships IDG's runtime libraries but no headers (there is no libidg-dev), and
# carries no EveryBeam at all. wsclean's CMake finds both only if present and
# otherwise configures *silently* without them -- which is how the published
# 3.6 image came to declare eleven beam/a-term options that could not work.
# Version bounds are wsclean 3.6's own (CMakeLists.txt): IDG >= 0.8.1, and
# EveryBeam 0.6.x or 0.7.x -- a 0.8.x EveryBeam is a hard configure error, so
# `everybeam_version` cannot simply track upstream's latest.
FROM kernsuite/base:{kern_version}

# wget is EveryBeam's, not ours: it is a hard `FATAL_ERROR` at configure time
# (CMakeLists.txt:249) because EveryBeam fetches some telescopes' coefficient
# files on demand at *run* time -- so it has to stay in the final image, not
# just the build.
RUN docker-apt-install cmake g++ git wget \
    casacore-dev casacore-data \
    libgsl-dev libhdf5-dev libfftw3-dev libcfitsio-dev wcslib-dev \
    libblas-dev liblapack-dev libboost-all-dev libpython3-dev

# Both projects run `git submodule update --init --recursive` themselves at
# configure time, so a shallow non-recursive clone is enough (as for wsclean).
RUN git clone --depth 1 -b {idg_version} https://gitlab.com/astron-idg/idg.git /idg \
    && cmake -S /idg -B /idg/build -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_WITH_PYTHON=OFF -DBUILD_TESTING=OFF \
    && make -C /idg/build -j"$(nproc)" \
    && make -C /idg/build install \
    && ldconfig \
    && rm -rf /idg

# EveryBeam's MeerKAT response is compiled in (cpp/circularsymmetric/
# meerkatcoefficients.cc), so it needs no run-time coefficient files. The
# telescopes that do need them -- LOBES and OVRO-LWA -- are opt-in downloads
# (DOWNLOAD_LOBES / DOWNLOAD_LWA), left off; turn one on here if a cab ever
# needs it rather than expecting the beam to be found at run time.
RUN git clone --depth 1 -b v{everybeam_version} https://git.astron.nl/RD/EveryBeam.git /everybeam \
    && cmake -S /everybeam -B /everybeam/build -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
       -DBUILD_WITH_PYTHON=OFF -DBUILD_TESTING=OFF \
    && make -C /everybeam/build -j"$(nproc)" \
    && make -C /everybeam/build install \
    && ldconfig \
    && rm -rf /everybeam

RUN git clone --depth 1 -b v{package_version} https://gitlab.com/aroffringa/wsclean.git /wsclean \
    && cmake -S /wsclean -B /wsclean/build -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
    && make -C /wsclean/build -j"$(nproc)" \
    && make -C /wsclean/build install \
    && ldconfig \
    && rm -rf /wsclean

CMD {cmd}
