#!/bin/sh
set -eu
# The pinned commit carries both 6.7.0.31 and 6.7.1.0 tags. CASA's
# detached-checkout version script otherwise emits a dirty dev version.
printf '6.7.0.31 6.7.0.31\n' > /opt/casa/src/casa6/casatools/version.txt
python3 -m venv /opt/casa/venv
/opt/casa/venv/bin/pip install --no-cache-dir build setuptools wheel
PKG_CONFIG_PATH=/opt/casa/install/lib/pkgconfig \
  /opt/casa/venv/bin/python -m build -o /opt/casa/install/dist /opt/casa/src/casa6/casatools
/opt/casa/venv/bin/pip install --no-cache-dir /opt/casa/install/dist/casatools*.whl \
  casatasks==6.7.0.31 casaconfig casadata protobuf==3.20.*
