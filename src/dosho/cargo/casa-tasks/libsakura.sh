#!/bin/sh
set -eu
jobs=$(nproc)
[ "$jobs" -le 48 ] || jobs=48
# libsakura 5.2.1 hard-codes the x86-only -m64 flag in its library target.
if [ "$(uname -m)" = aarch64 ]; then
  sed -i 's/ -m64 / /' /opt/casa/src/sakura-libsakura-5.2.1/libsakura/src/CMakeLists.txt
fi
cmake -S /opt/casa/src/sakura-libsakura-5.2.1/libsakura -B /opt/casa/build/libsakura \
  -DCMAKE_INSTALL_PREFIX=/opt/casa/install -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_DOC=OFF -DPYTHON_BINDING=OFF -DSIMD_ARCH=GENERIC -DENABLE_TEST=OFF
cmake --build /opt/casa/build/libsakura --parallel "$jobs"
cmake --install /opt/casa/build/libsakura
