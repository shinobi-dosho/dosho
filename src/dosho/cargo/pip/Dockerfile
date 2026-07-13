# dosho shared pip-tool template: install a pip package on top of the shared
# base-astro image. Rendered by `dosho images build <KEY>` from the manifest's
# build vars ({base_image} = the resolved base ref, {package}, {cmd}, and the
# optional {pre_install}/{extra_deps} which default to empty).
FROM {base_image}

{pre_install}
RUN pip install --break-system-packages {pip_install_flags} {package} {extra_deps}

CMD {cmd}
