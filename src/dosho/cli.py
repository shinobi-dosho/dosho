"""``dosho images`` -- build and publish dosho's container images from the
`images.yaml` manifest.

A small build driver modelled on cult-cargo's ``build-cargo``: for each
`build:` entry it renders the entry's Dockerfile (a ``str.format`` template
over the manifest's build vars) and shells out to ``docker build`` /
``docker run`` (a sanity check) / ``docker push``. `ref:` entries are external
images (used verbatim) and are not built here.

The resolved tag is ``{registry}/{name}:{version}-{bundle_version}`` (the same
reference `dosho.images.<KEY>` exposes to cabs), so a built+pushed image is
exactly what the cabs consume.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import click

from dosho import images as _images

_CARGO_DIR = Path(__file__).with_name("cargo")


def _run(argv: list[str], **kwargs: Any) -> None:
    click.echo(click.style("+ " + " ".join(argv), fg="cyan"))
    subprocess.run(argv, check=True, **kwargs)


def _get_build_entry(key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _images.manifest
    imgs = manifest["images"]
    if key not in imgs:
        raise click.ClickException(f"no image {key!r} in the manifest (have: {', '.join(imgs)})")
    entry = imgs[key]
    if "build" not in entry:
        raise click.ClickException(f"image {key!r} is a `ref:` (external) -- dosho does not build it")
    return entry, manifest["metadata"]


def _tag(key: str, entry: dict[str, Any], metadata: dict[str, Any], registry: str | None) -> str:
    registry = registry or metadata["registry"]
    name = entry.get("name", key.lower())
    return f"{registry}/{name}:{entry['build']['version']}-{metadata['bundle_version']}"


def _render_dockerfile(entry: dict[str, Any], metadata: dict[str, Any], package: str | None) -> tuple[str, Path]:
    build = dict(entry["build"])
    if package:
        build["package"] = package
    dockerfile = _CARGO_DIR / build["dockerfile"]
    text = dockerfile.read_text()
    fmt = {**metadata, **build}
    return text.format(**fmt), dockerfile.parent


@click.group()
def main() -> None:
    """dosho tooling."""


@main.group()
def images() -> None:
    """Build and publish dosho's container images."""


@images.command("list")
def images_list() -> None:
    """List every manifest image, its kind (ref/build), and resolved reference."""
    for key, entry in _images.manifest["images"].items():
        kind = "build" if "build" in entry else "ref"
        click.echo(f"{key:16} [{kind:5}] {getattr(_images, key)}")


@images.command("build")
@click.argument("key")
@click.option("--push", "do_push", is_flag=True, help="push the image after building.")
@click.option("--no-cache", is_flag=True, help="build without the docker layer cache.")
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
@click.option("--package", default=None, help="override the pip package/spec installed (e.g. a prerelease).")
@click.option("--dry-run", is_flag=True, help="render and print the Dockerfile + tag; do not build.")
def images_build(
    key: str, do_push: bool, no_cache: bool, registry: str | None, package: str | None, dry_run: bool
) -> None:
    """Build (and optionally --push) the image for KEY."""
    entry, metadata = _get_build_entry(key)
    tag = _tag(key, entry, metadata, registry)
    dockerfile, context = _render_dockerfile(entry, metadata, package)

    if dry_run:
        click.echo(f"# tag: {tag}\n# context: {context}\n{dockerfile}")
        return

    build_argv = ["docker", "build", "-t", tag, "-f", "-"]
    if no_cache:
        build_argv.append("--no-cache")
    build_argv.append(str(context))
    _run(build_argv, input=dockerfile.encode())

    # sanity check: run the image's own CMD (e.g. `<tool> --help`).
    _run(["docker", "run", "--rm", tag])

    if do_push:
        _run(["docker", "push", tag])

    click.echo(click.style(f"built {tag}" + (" and pushed" if do_push else ""), fg="green"))


@images.command("push")
@click.argument("key")
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
def images_push(key: str, registry: str | None) -> None:
    """Push the already-built image for KEY."""
    entry, metadata = _get_build_entry(key)
    _run(["docker", "push", _tag(key, entry, metadata, registry)])


if __name__ == "__main__":
    main()
