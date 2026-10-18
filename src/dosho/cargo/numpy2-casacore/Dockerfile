# Shared NumPy 2/casacore runtime for tools whose dependencies require NumPy 2.
# BASE_ASTRO provides casacore 3.7.1 built against NumPy 1; rebuild its
# converter library with the final NumPy 2 headers for both architectures.
FROM {base_image} AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential python3-dev casacore-dev libboost-python-dev \
    && rm -rf /var/lib/apt/lists/*

# ducc0 source builds default to -march=native, which sees QEMU ARMv9 features.
# A generic optimized build remains usable on baseline ARM64 hosts.
ENV DUCC0_OPTIMIZATION=generic-strip
{pre_install}
RUN pip install --break-system-packages "{package}" {extra_deps}

RUN dpkg-query -W casacore-dev | grep -q '3.7.1-' \
    && wget -q -O /tmp/casacore-v3.7.1.tar.gz \
       https://github.com/casacore/casacore/archive/refs/tags/v3.7.1.tar.gz \
    && tar -xzf /tmp/casacore-v3.7.1.tar.gz -C /tmp \
    && ln -s /tmp/casacore-3.7.1 /tmp/casacore \
    && cd /tmp/casacore-3.7.1/python/Converters \
    && g++ -std=c++17 -O2 -fPIC -shared \
       -I"$(python3 -c 'import numpy; print(numpy.get_include())')" \
       $(python3-config --includes) -I/tmp \
       PycArray.cc PycArrayNP.cc PycBasicData.cc PycExcp.cc PycImport.cc \
       PycRecord.cc PycValueHolder.cc \
       -lcasa_casa -lboost_python312 $(python3-config --ldflags --embed) \
       -Wl,-soname,libcasa_python3.so.8 \
       -o /opt/dosho/venv/lib/libcasa_python3.so.8 \
    && rm -rf /tmp/casacore /tmp/casacore-3.7.1 /tmp/casacore-v3.7.1.tar.gz

FROM {base_image}
# Replace the venv exactly: pip may have removed older base packages.
RUN rm -rf /opt/dosho/venv
COPY --from=build /opt/dosho/venv /opt/dosho/venv
ENV LD_LIBRARY_PATH=/opt/dosho/venv/lib
{post_install}
# Opening a table exercises the NumPy C API in libcasa_python3.
COPY casacore_smoke.py /tmp/casacore_smoke.py
RUN python3 /tmp/casacore_smoke.py && rm /tmp/casacore_smoke.py

RUN {cmd}
CMD {cmd}
