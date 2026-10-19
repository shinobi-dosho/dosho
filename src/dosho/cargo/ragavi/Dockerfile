# ragavi 0.5.2 predates Python 3.12, Bokeh 3 and NumPy 2. Debian bookworm
# supplies Python 3.11 and a casacore binding on both AMD64 and ARM64.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-pip python3-casacore \
    && rm -rf /var/lib/apt/lists/*
# Keep the older Bokeh API ragavi uses and a Dask/Distributed pair.
RUN pip3 install --break-system-packages 'numpy<2' 'bokeh<3' \
    'dask[complete]==2024.6.0' 'distributed==2024.6.0' 'ragavi=={package_version}'
# ragavi's averaging module still imports chan_metadata and Numba's
# generated_jit. Their last compatible ARM64/Python 3.11 releases require
# NumPy 1.24, hence a matching 2023-era plotting stack. Resolve the general
# dependencies above first, then replace only these packages; this set passed
# a real ragavi-vis import and MeasurementSet read on ARM64.
RUN pip3 install --break-system-packages --no-deps --no-compile \
    'codex-africanus==0.2.10' 'numba==0.57.1' 'llvmlite==0.40.1' \
    'numpy==1.24.4' 'pandas==2.0.3' 'xarray==2023.12.0' \
    'scipy==1.11.4' 'matplotlib==3.7.5' 'datashader==0.16.3' \
    pytz tzdata
# Import alone does not reveal a NumPy C API mismatch in python-casacore.
RUN python3 -c 'from casacore.tables import table, maketabdesc, makescacoldesc; from tempfile import TemporaryDirectory; d=TemporaryDirectory(); p=d.name+"/smoke"; t=table(p, tabledesc=maketabdesc(makescacoldesc("x", 0.0)), nrow=1, readonly=False, ack=False); t.putcell("x", 0, 1.0); t.close(); t=table(p, ack=False); assert t.getcell("x", 0) == 1.0; t.close(); d.cleanup()'
RUN python3 -c 'import ragavi.visibilities'
RUN ragavi-gains --help >/dev/null && ragavi-vis --help >/dev/null
COPY entrypoint.sh /usr/local/bin/dosho-ragavi-entrypoint
RUN chmod +x /usr/local/bin/dosho-ragavi-entrypoint
ENTRYPOINT ["/usr/local/bin/dosho-ragavi-entrypoint"]
CMD ["ragavi-gains", "--help"]
