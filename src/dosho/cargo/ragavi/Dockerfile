FROM stimela/base:1.2.5

# ragavi 0.5.2 (2020) targets Python 3.6 with an era-compatible bokeh (<3, which
# still has Plot.plot_width) and numpy (<1.24, which still has np.bool8). The
# modern shared BASE_ASTRO (KERN-10 -> Python 3.12 / numpy 2.x / bokeh 3.x)
# removed both, so ragavi-gains/-vis crash there ("unexpected attribute
# 'plot_width'", "module 'numpy' has no attribute 'bool8'"). Build on the
# stimela-classic base ragavi actually shipped on instead -- a deliberate
# one-off external base (no shared dosho base). Mirrors ratt-ru/Stimela-classic
# stimela/cargo/base/ragavi/Dockerfile.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.6 10
RUN pip3 install pyyaml python-casacore numba==0.48
RUN pip3 install -I ragavi==0.5.2
CMD ["ragavi-gains", "--help"]
