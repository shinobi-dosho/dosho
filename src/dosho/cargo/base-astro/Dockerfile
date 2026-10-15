# Shared astronomy runtime. KERN-10 is an apt source, never the parent image.
# Keep build tools and alternate Python interpreters in children that need them.
FROM ubuntu:24.04 AS kern-key
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL \
    'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x5711690ECBEB59BAC7D3CBF9813B0DC8B7D042E7' \
    -o /tmp/kern-key.asc \
    && test "$(gpg --show-keys --with-colons /tmp/kern-key.asc 2>/dev/null \
      | grep '^fpr:' | head -1 | cut -d: -f10)" = 5711690ECBEB59BAC7D3CBF9813B0DC8B7D042E7 \
    && gpg --dearmor -o /kernsuite-kern-10.gpg /tmp/kern-key.asc

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
COPY --from=kern-key /kernsuite-kern-10.gpg /usr/share/keyrings/kernsuite-kern-10.gpg
RUN printf '%s\n' \
    'deb [signed-by=/usr/share/keyrings/kernsuite-kern-10.gpg] http://ppa.launchpadcontent.net/kernsuite/kern-10/ubuntu noble main' \
    > /etc/apt/sources.list.d/kernsuite-kern-10.list \
    && apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git wget python3 python3-pip python3-venv \
       casacore-tools casacore-data python3-casacore \
    && rm -rf /var/lib/apt/lists/*
# KERN's Python casacore binding is built against Noble's NumPy 1.x. Let the
# shared venv see apt packages, but put pip additions in the venv itself so
# children can install or override dependencies without modifying apt files.
RUN python3 -m venv --system-site-packages /opt/dosho/venv
ENV PATH=/opt/dosho/venv/bin:$PATH
RUN pip install --no-compile --no-cache-dir 'numpy<2' \
    'dask[array]==2024.6.0' 'xarray==2024.6.0' 'pandas==2.2.2' \
    astropy==7.2.2 'dask-ms[xarray]==0.2.21' scipy==1.17.1 omegaconf==2.4.0
# The build checks each architecture before Buildx can publish a manifest.
RUN command -v taql && {cmd}
CMD {cmd}
