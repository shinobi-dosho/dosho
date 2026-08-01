from __future__ import annotations

import tomllib
from pathlib import Path

import dosho

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _declared_version() -> str:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_version_matches_pyproject():
    """The exported version is the one being released.

    `dosho.__version__` is what `docs/conf.py` publishes the documentation
    site under, so a stale value labels the whole site with a release that
    did not produce it. It used to be a literal in `dosho/__init__.py` and
    sat two releases behind (`0.1.0a1` against a `0.1.0b3` distribution);
    deriving it from the installed distribution fixes that, and this pins
    the derivation to the version actually declared for the build.
    """
    assert dosho.__version__ == _declared_version()


def test_version_is_not_the_uninstalled_fallback():
    """Guard the `PackageNotFoundError` branch from passing for the wrong reason.

    If the test run ever imports `dosho` off a bare source tree rather than
    the installed project, `__version__` degrades to the sentinel and the
    comparison above would be testing nothing.
    """
    assert dosho.__version__ != "0+unknown"
