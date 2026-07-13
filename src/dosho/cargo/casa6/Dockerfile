# dosho image: CASA 6 (casatools/casatasks + casaplotms) built fresh on the KERN
# suite base. Isolated from BASE_ASTRO on purpose -- CASA pins its own numpy and
# protobuf==3.20, so it gets a lean base rather than the shared astro stack.
# Ported from cult-cargo's casa6 recipe, adapted for Ubuntu 24.04 / Python 3.12
# (dist-packages paths, t64 apt package names). Rendered by
# `dosho images build CASA6`.
FROM kernsuite/base:{kern_version}

# Runtime libs for casacore + the headless casaplotms Qt/AppImage stack.
RUN docker-apt-install python3-pip python3-casacore xvfb \
    libblas-dev liblapack-dev libfuse-dev fuse libgoogle-perftools-dev \
    libglib2.0-0t64 libqt5gui5t64 \
    && rm -rf /var/lib/apt/lists/*

# NB: protobuf==3.20 is required by CASA. --ignore-installed because
# python3-casacore pulls Debian's python3-numpy, which pip cannot uninstall (no
# RECORD file); pip's numpy lands in /usr/local and shadows the apt one.
RUN pip install --break-system-packages --no-cache-dir --ignore-installed --upgrade numpy \
    casatools=={wheel_version} casatasks=={wheel_version} \
    casaplotms casaconfig casadata protobuf==3.20

# Bake the measures/ephemeris data into the image and disable runtime updates
# (see casasiteconfig.py). measurespath there == /opt/casa/data downloaded here.
RUN mkdir -p /opt/casa/data
COPY casasiteconfig.py /opt/casa/
ENV CASASITECONFIG=/opt/casa/casasiteconfig.py
RUN python3 -m casaconfig --measurespath /opt/casa/data --update-all \
    && python3 -m casaconfig --measurespath /opt/casa/data --current-data

# Extract the casaplotms AppImage and repoint plotmstool at the extracted binary
# (FUSE-mounting the AppImage does not work inside an unprivileged container).
RUN cd /opt \
    && /usr/local/lib/python3.12/dist-packages/casaplotms/__bin__/casaplotms-x86_64.AppImage --appimage-extract \
    && mv /opt/squashfs-root /opt/casaplotms \
    && chmod -R go+rx /opt/casaplotms
RUN sed -i -e "s|app_path = __os.path.join( __os.path.abspath( __os.path.join(__os.path.dirname(__file__),\"..\") ), '__bin__/casaplotms-x86_64.AppImage')|app_path = '/opt/casaplotms/usr/bin/casaplotms'|g" \
    /usr/local/lib/python3.12/dist-packages/casaplotms/private/plotmstool.py
ENV LD_LIBRARY_PATH=/opt/casaplotms/usr/lib/
ENV QT_QPA_PLATFORM_PLUGIN_PATH=/opt/casaplotms/usr/lib/plugins/platforms

# Let casacore find the bundled data too.
RUN mkdir -p /usr/local/share/data/ \
    && ln -s /opt/casa/data /usr/local/share/data/casacore

CMD {cmd}
