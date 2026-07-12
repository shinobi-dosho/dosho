# dosho image: simms -- MS/visibility simulator (skysim/telsim sub-commands),
# built on the curated KERN suite base image.
#
# str.format template rendered by `dosho images build SIMMS` from the manifest
# build vars (version, kern_version, package, cmd). Keep any literal shell
# braces out of it -- every brace here is a template field.
FROM kernsuite/base:{kern_version}

RUN docker-apt-install python3-pip python3-venv git

RUN pip install --break-system-packages {package}

CMD {cmd}
