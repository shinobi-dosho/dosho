# cubical 1.6.4 (2023) does not support Python >=3.10: its own source does
# `from collections import Iterator` (pickled_db.py), an alias removed in
# 3.10 -- so the shared BASE_ASTRO (KERN-10 -> Python 3.12) is a non-starter,
# and sed-patching upstream source in-image is the kind of snowflake dosho
# avoids. Build on the era-correct interpreter instead: Python 3.9 on Debian
# bookworm, the same combination the proven stimela2/cubical:1.6.4 image
# runs. On 3.9 pip's resolver also lands a self-consistent 2023-era
# dependency set (numba <=0.59 pins numpy <1.27), sidestepping the numpy-2
# removals cubical predates. Users wanting a modern-Python calibrator should
# be on QUARTICAL (CubiCal's successor, built on BASE_ASTRO) anyway.
#
# str.format template rendered by `dosho images build CUBICAL`.
FROM python:{python_version}-bookworm

# sharedarray (a cubical dep) builds from source -- the python:* base images
# already carry gcc/make, no extra system packages needed.
RUN pip install cubical=={version}

CMD {cmd}
