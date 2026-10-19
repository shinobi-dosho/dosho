#!/bin/sh
set -eu
jobs=$(nproc)
[ "$jobs" -le 48 ] || jobs=48
PKG_CONFIG_PATH=/opt/casa/install/lib/pkgconfig cmake \
  -S /opt/casa/src/casa6/casatools/src/code -B /opt/casa/build/casacpp \
  -DCMAKE_INSTALL_PREFIX=/opt/casa/install \
  -DPKG_CONFIG_USE_CMAKE_PREFIX_PATH=/opt/casa/install \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /opt/casa/build/casacpp --parallel "$jobs"
cmake --install /opt/casa/build/casacpp
