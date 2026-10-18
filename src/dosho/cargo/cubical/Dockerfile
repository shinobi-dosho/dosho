# CubiCal 1.6.4 imports collections.Iterator, removed in Python 3.10.
# Debian bullseye supplies Python 3.9 and a matching python3-casacore binary
# on both architectures. This older base is an era pin for a legacy tool;
# revisit it when CubiCal supports a maintained Python interpreter.
FROM debian:bullseye-slim
# Bullseye security packages have moved off the rolling mirror; use the
# archived final package set so apt indexes and .deb files stay in sync.
RUN sed -i 's@deb.debian.org/debian-security@archive.debian.org/debian-security@; s@deb.debian.org/debian@archive.debian.org/debian@; /bullseye-updates/d' /etc/apt/sources.list \
    && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99archive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-pip python3-casacore \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*
ENV CC=gcc CXX=g++
RUN python3 -m pip install --no-cache-dir --upgrade 'pip<26'
# CubiCal predates NumPy 2; its source-built dependencies need a C compiler.
RUN python3 -m pip install --no-cache-dir --no-compile "numpy<2" cubical=={package_version}
# A real table operation catches a NumPy C API mismatch that import alone misses.
RUN python3 -c 'from casacore.tables import table, maketabdesc, makescacoldesc; from tempfile import TemporaryDirectory; d=TemporaryDirectory(); p=d.name+"/smoke"; t=table(p, tabledesc=maketabdesc(makescacoldesc("x", 0.0)), nrow=1, readonly=False, ack=False); t.putcell("x", 0, 1.0); t.close(); t=table(p, ack=False); assert t.getcell("x", 0) == 1.0; t.close(); d.cleanup()'
RUN {cmd}
CMD {cmd}
