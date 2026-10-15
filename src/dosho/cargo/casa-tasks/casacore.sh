#!/bin/sh
set -eu
jobs=$(nproc)
[ "$jobs" -le 48 ] || jobs=48
cmake -S /opt/casa/src/casa6/casatools/casacore -B /opt/casa/build/casacore \
  -DCMAKE_INSTALL_PREFIX=/opt/casa/install -DCMAKE_BUILD_TYPE=Release \
  -DDATA_DIR=/opt/casa/data -DUSE_OPENMP=ON -DUSE_THREADS=ON \
  -DBUILD_FFTPACK_DEPRECATED=ON -DBUILD_TESTING=OFF -DBUILD_PYTHON3=OFF \
  -DBUILD_DYSCO=ON -DPORTABLE=ON -DUSE_PCH=OFF
cmake --build /opt/casa/build/casacore --parallel "$jobs"
cmake --install /opt/casa/build/casacore
