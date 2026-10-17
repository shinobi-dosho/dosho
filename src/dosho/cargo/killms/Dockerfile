# dosho image: killMS, direction-dependent calibration, built on top of
# dosho's own DDFACET image (killMS's real upstream Dockerfile,
# github.com/saopicc/killMS, does `FROM bhugo/ddfacet:0.9.0.0` then installs
# killMS into that image's venv -- {base_image} here is dosho's own DDFACET
# build instead of that external published image). killMS 3.3.0 publishes to
# PyPI, so this installs from there rather than upstream's local `ADD killMS
# ...` (which assumes being built from inside a killMS checkout).
# Rendered by `dosho images build KILLMS` ({package_version} = killMS's pip version,
# {cmd} = sanity check).
FROM {base_image}

# killMS 3.3.0's dot0.c includes the x86-only emmintrin.h but uses no SIMD
# intrinsics. Remove that unused include when compiling its sdist on ARM64.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "arm64" ]; then \
      . /opt/venv/bin/activate && \
      mkdir -p /opt/killms-source && \
      python -m pip download --no-deps --no-binary=killms \
        --dest /opt/killms-source killms=={package_version} && \
      tar -xzf /opt/killms-source/killms-{package_version}.tar.gz \
        -C /opt/killms-source && \
      sed -i '/^#include <emmintrin.h>$/d' \
        /opt/killms-source/killms-{package_version}/killMS/Array/Dot/dot0.c && \
      python -m pip install --use-pep517 /opt/killms-source/killms-{package_version} && \
      rm -rf /opt/killms-source; \
    else \
      . /opt/venv/bin/activate && \
      python -m pip install --use-pep517 killms=={package_version}; \
    fi

RUN kMS.py --help > /dev/null
CMD {cmd}
