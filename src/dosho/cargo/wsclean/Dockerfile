# dosho image: WSClean interferometric imager, built from source on the KERN
# suite base. PORTABLE=Yes so the binary runs on any x86-64 CPU (no host-CPU
# instructions baked in). Rendered by `dosho images build WSCLEAN`.
FROM kernsuite/base:{kern_version}

RUN docker-apt-install cmake g++ git \
    casacore-dev casacore-data \
    libgsl-dev libhdf5-dev libfftw3-dev libcfitsio-dev wcslib-dev \
    libblas-dev liblapack-dev libboost-all-dev libpython3-dev

RUN git clone --depth 1 -b v{package_version} https://gitlab.com/aroffringa/wsclean.git /wsclean \
    && cmake -S /wsclean -B /wsclean/build -DPORTABLE=Yes -DCMAKE_BUILD_TYPE=Release \
    && make -C /wsclean/build -j"$(nproc)" \
    && make -C /wsclean/build install \
    && rm -rf /wsclean

CMD {cmd}
