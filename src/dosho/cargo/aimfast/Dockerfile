# AIMFAST 1.3.4 pins astLib 0.10.0, which imports the removed Python 3.12
# imp module. Install the pinned package first, then override astLib with 0.13.2.
# Both astLib releases are source-built on ARM64 and AMD64.
FROM {base_image}
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --break-system-packages "{package}"
RUN pip install --break-system-packages -U 'astLib>=0.13.2'
# AIMFAST still uses Bokeh 2's plot_width/plot_height argument names, while
# astLib 0.13.2 requires NumPy 2 and the resolved Bokeh release is 3.x.
COPY patch_bokeh3.py /tmp/patch_bokeh3.py
RUN python3 /tmp/patch_bokeh3.py && rm /tmp/patch_bokeh3.py
RUN {cmd}
COPY smoke_residuals.py /tmp/smoke_residuals.py
RUN python3 /tmp/smoke_residuals.py && rm /tmp/smoke_residuals.py
CMD {cmd}
