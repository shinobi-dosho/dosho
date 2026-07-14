# dosho image: DDFacet, a facet-based radio-interferometric imager, adapted
# from DDFacet's own upstream Dockerfile (github.com/saopicc/DDFacet,
# `docker.2404`): a from-source build of SOFA, blitz, CASAREST, MAKEMS and
# MeqTrees-timba (DDFacet's real, non-KERN-suite runtime dependencies -- none
# of these are BASE_ASTRO/kernsuite packages, hence a dedicated base image
# rather than `base: BASE_ASTRO`), followed by DDFacet itself installed from
# PyPI (rather than upstream's local `ADD DDFacet/ ...` + git-submodule step,
# which assumes being built from inside a DDFacet checkout -- DDFacet 1.0.0.0
# publishes the same source as a real sdist, so a straight `pip install`
# reaches the same result without needing that local build context).
# Rendered by `dosho images build DDFACET` ({version} = DDFacet's own pip
# version, {cmd} = sanity check).
FROM ubuntu:24.04

RUN echo "*         -   memlock     unlimited" > /etc/security/limits.conf
ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=critical
ENV GNUCOMPILER=11
ENV PYTHONVER=3.12
ENV NUMPYVER=2.3.2

ENV DEB_SETUP_DEPENDENCIES="dpkg-dev g++-${{GNUCOMPILER}} gcc-${{GNUCOMPILER}} libc-dev cmake gfortran-${{GNUCOMPILER}} git wget subversion rsync"
ENV DEB_DEPENDENCIES="python3-virtualenv python3-pip libfftw3-dev python3-numpy libfreetype6 libfreetype6-dev libfreetype-dev libpng-dev pkg-config python3-dev libboost-all-dev libcfitsio-dev libhdf5-dev wcslib-dev libatlas-base-dev liblapack-dev python3-tk libreadline6-dev liblog4cplus-dev libncurses5-dev libtinfo6 libncurses-dev flex bison libbison-dev libqdbm-dev libgsl-dev make casacore-data python3-casacore casacore-dev casacore-tools"

RUN apt-get update && \
    apt-get install -y ${{DEB_DEPENDENCIES}} && \
    apt-get install -y ${{DEB_SETUP_DEPENDENCIES}}

RUN update-alternatives --install /usr/bin/cc cc /usr/bin/gcc-${{GNUCOMPILER}} 100 \
        --slave /usr/bin/gcc gcc /usr/bin/gcc-${{GNUCOMPILER}} \
        --slave /usr/bin/x86_64-linux-gnu-gcc x86_64-linux-gnu-gcc /usr/bin/gcc-${{GNUCOMPILER}} && \
    update-alternatives --install /usr/bin/x86_64-linux-gnu-g++ x86_64-linux-gnu-g++ /usr/bin/g++-${{GNUCOMPILER}} 100 \
        --slave /usr/bin/g++ g++ /usr/bin/g++-${{GNUCOMPILER}} \
        --slave /usr/bin/x86_64-linux-gnu-cpp x86_64-linux-gnu-cpp /usr/bin/g++-${{GNUCOMPILER}} && \
    update-alternatives --install /usr/bin/gfortran gfortran /usr/bin/gfortran-${{GNUCOMPILER}} 100 \
        --slave /usr/bin/x86_64-linux-gnu-gfortran x86_64-linux-gnu-gfortran /usr/bin/gfortran-${{GNUCOMPILER}}

# All python dependencies go into venv
WORKDIR /opt
RUN virtualenv venv -p python${{PYTHONVER}}
RUN . /opt/venv/bin/activate && python -m pip install -U pip setuptools wheel

################################
# build SOFA
################################
WORKDIR /opt
RUN wget https://www.iausofa.org/s/sofa_c-20231011tar.gz && \
    tar xvfz sofa_c-20231011tar.gz && \
    rm sofa_c-20231011tar.gz && \
    cd /opt/sofa/20231011/c/src && \
    sed -i '52s/.*/INSTALL_DIR = \/usr/' makefile && \
    make -j4 && \
    make install && \
    make test && \
    rm -r /opt/sofa

################################
## build blitz from source
################################
WORKDIR /opt
RUN wget https://github.com/blitzpp/blitz/archive/1.0.2.tar.gz && \
    tar -xvf 1.0.2.tar.gz && \
    rm 1.0.2.tar.gz && \
    cd /opt/blitz-1.0.2 && \
    grep -rl python . | xargs sed -i "s/python/python${{PYTHONVER}}/g" && \
    autoreconf --force --install && \
    ./configure --enable-shared && \
    make -j16 && \
    make install && \
    ldconfig && \
    rm -r /opt/blitz-1.0.2

################################################################
## BUILD CASAREST FROM SOURCE
################################################################
WORKDIR /opt
RUN cd /opt && \
    wget https://github.com/casacore/casarest/archive/v1.8.1.tar.gz && \
    tar xvf v1.8.1.tar.gz && \
    rm v1.8.1.tar.gz && \
    cd /opt/casarest-1.8.1 && \
    mkdir -p build && \
    cd /opt/casarest-1.8.1/build && \
    cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release ../ && \
    make -j 16 && \
    make install && \
    rm -r /opt/casarest-1.8.1 && \
    ldconfig
RUN cd /opt && \
    . /opt/venv/bin/activate && python -m pip install --use-pep517 python-casacore==3.7.1 "numpy==${{NUMPYVER}}" && \
    cd / && \
    python -c "from pyrap.tables import table as tbl"

################################################################
## BUILD MAKEMS FROM SOURCE AND TEST
################################################################
WORKDIR /opt
RUN wget https://github.com/ska-sa/makems/archive/v1.5.6.tar.gz && \
    tar xvf v1.5.6.tar.gz && \
    rm v1.5.6.tar.gz && \
    mkdir -p /opt/makems-1.5.6/LOFAR/build/gnu_opt && \
    cd /opt/makems-1.5.6/LOFAR/build/gnu_opt && \
    cmake -DCMAKE_MODULE_PATH:PATH=/opt/makems-1.5.6/LOFAR/CMake \
          -DUSE_LOG4CPLUS=OFF -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX=/usr ../.. && \
    make -j 16 && \
    make install && \
    cd /opt/makems-1.5.6/test && \
    makems WSRT_makems.cfg && \
    rm -r /opt/makems-1.5.6

################################################################
## BUILD MEQTREES FROM SOURCE AND TEST
################################################################
WORKDIR /opt
# Get MeqTrees universe python packages
WORKDIR /opt

RUN . /opt/venv/bin/activate && python -m pip install \
    purr \
    'owlcat>=1.8.1rc1' \
    kittens \
    'meqtrees-cattery>=1.8.0rc3' \
    astro-tigger-lsm \
    "numpy==${{NUMPYVER}}"

RUN . /opt/venv/bin/activate && wget https://github.com/ska-sa/meqtrees-timba/archive/refs/tags/v1.11.tar.gz && \
    tar zxvf v1.11.tar.gz && \
    rm v1.11.tar.gz && \
    cd meqtrees-timba-1.11 && \
    mkdir build && \
    cd build && \
    cmake -DCMAKE_INSTALL_PREFIX=/usr \
          -DCMAKE_BUILD_TYPE=Release \
          -DENABLE_PYTHON_3=ON \
          -DPYTHON_PACKAGES_DIR=/opt/venv/lib/python${{PYTHONVER}}/site-packages \
          .. && \
    make -j4 && \
    make install && \
    ldconfig && \
    rm -r /opt/meqtrees-timba-1.11 && \
    cd /opt

################################################################
## BUILD LOFAR FROM SOURCE
################################################################
WORKDIR /opt
RUN wget https://github.com/bennahugo/LOFARBeam/archive/refs/tags/DDF_KMS_22.04.tar.gz && \
    tar zxvf DDF_KMS_22.04.tar.gz && \
    rm DDF_KMS_22.04.tar.gz && \
    cd LOFARBeam-DDF_KMS_22.04 && \
    mkdir -p build/gnucxx11_opt && \
    cd build/gnucxx11_opt && \
    cmake -DCMAKE_INSTALL_PREFIX=/usr \
          -DPYTHON_PACKAGES_DIR=/opt/venv/lib/python${{PYTHONVER}}/site-packages \
          ../../ && \
    make -j4 && \
    make install && \
    . /opt/venv/bin/activate && python -c "import lofar.stationresponse as lsr" && \
    rm -r /opt/LOFARBeam-DDF_KMS_22.04

################################################################
## INSTALL DDFACET (from PyPI -- see this file's header)
################################################################
# workaround for a pip build-isolation bug pulling a higher tensorflow that
# isn't ABI compatible (same pin the real upstream Dockerfile carries)
RUN echo "tensorflow==2.19.0" > /opt/constraints.txt
ENV PIP_CONSTRAINT=/opt/constraints.txt
RUN . /opt/venv/bin/activate && python -m pip install --use-pep517 \
    "DDFacet[testing-requirements,fits-beam-support,kms-support,alternate-data-backends,dft-support]=={version}"

# ensure bdsf backend still works
RUN . /opt/venv/bin/activate && python -c "import bdsf"

# Make venv globally available in this container
ENV LD_LIBRARY_PATH=/opt/venv/lib:$LD_LIBRARY_PATH
ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONPATH=/opt/venv/lib/python${{PYTHONVER}}/site-packages

CMD {cmd}
