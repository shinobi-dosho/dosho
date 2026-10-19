#!/bin/sh
set -eu
# LLVM 14 aborts at datashader JIT relocation on ARM64 under QEMU.
# Keep JIT enabled on AMD64, where this workaround is unnecessary.
if [ "$(uname -m)" = aarch64 ]; then
    export NUMBA_DISABLE_JIT=1
fi
exec "$@"
