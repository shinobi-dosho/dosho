# dosho shared pip-tool template: install a pip package on top of the shared
# base-astro image. Rendered by dosho images build with these manifest
# variables: base_image, package, cmd, and optional pre_install,
# extra_deps, and post_install.
#
# The package spec is quoted: it is always one requirement, and a `dev:` entry
# states it in PEP 508 direct-URL form (`name[extras] @ git+...`) to keep the
# release's extras -- three shell words, which unquoted pip reads as three
# separate requirements and installs the tool without any of them.
# extra_deps is not, being a list of specs that quote their own operators
# where they need to (see SHADEMS, RFINDER).
FROM {base_image}

{pre_install}
RUN pip install --break-system-packages {pip_install_flags} "{package}" {extra_deps}
{post_install}

RUN {cmd}

CMD {cmd}
