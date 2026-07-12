# dosho shared base image: the curated KERN suite base + Python + casacore +
# the common astro stack every pip-tool cab needs (python-casacore, astropy,
# dask-ms, ...). The pip tools build FROM this via `base: BASE_ASTRO` in the
# manifest, so that heavy layer is built once and cached.
#
# str.format template rendered by `dosho images build BASE_ASTRO`.
FROM kernsuite/base:{kern_version}

RUN docker-apt-install python3-pip python3-venv git casacore-tools

RUN pip install --break-system-packages \
    python-casacore astropy "dask-ms[xarray]" numpy scipy omegaconf

CMD {cmd}
