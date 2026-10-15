#!/bin/sh
set -eu
mkdir -p /opt/casa/src /opt/casa/build /opt/casa/install
cd /opt/casa/src
git clone --filter=blob:none --depth 1 --branch 6.7.0.31 https://open-bitbucket.nrao.edu/scm/casa/casa6.git casa6
cd casa6
test "$(git rev-parse HEAD)" = 01dc26b15daf69d07239bf0a4f059f7f374abbf6
git submodule update --init --depth 1 casatools/casacore
cd /opt/casa/src
curl -fL https://github.com/tnakazato/sakura/archive/refs/tags/libsakura-5.2.1.tar.gz | tar -xz
