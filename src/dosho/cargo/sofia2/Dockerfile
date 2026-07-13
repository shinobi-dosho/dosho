# dosho image: SoFiA-2 spectral-line source finder, built from source on the
# KERN suite base via its Makefile (OpenMP-enabled). `make install` drops the
# `sofia` binary into /usr/bin. Rendered by `dosho images build SOFIA2`.
FROM kernsuite/base:{kern_version}

RUN docker-apt-install build-essential git wcslib-dev

RUN git clone --depth 1 -b v{package_version} https://gitlab.com/SoFiA-Admin/SoFiA-2.git /SoFiA-2 \
    && make -C /SoFiA-2 OMP=true \
    && make -C /SoFiA-2 install

CMD {cmd}
