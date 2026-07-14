# dosho image: killMS, direction-dependent calibration, built on top of
# dosho's own DDFACET image (killMS's real upstream Dockerfile,
# github.com/saopicc/killMS, does `FROM bhugo/ddfacet:0.9.0.0` then installs
# killMS into that image's venv -- {base_image} here is dosho's own DDFACET
# build instead of that external published image). killMS 3.3.0 publishes to
# PyPI, so this installs from there rather than upstream's local `ADD killMS
# ...` (which assumes being built from inside a killMS checkout).
# Rendered by `dosho images build KILLMS` ({version} = killMS's pip version,
# {cmd} = sanity check).
FROM {base_image}

RUN . /opt/venv/bin/activate && python -m pip install --use-pep517 killms=={version}

CMD {cmd}
