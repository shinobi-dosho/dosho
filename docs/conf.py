"""Sphinx configuration for the dosho documentation.

Autodoc imports ``dosho`` and ``cab_catalog`` inspects cab documents and
ordinary Python functions. The docs group supplies schema inspection and
Sphinx without Shinobi (``uv sync --group docs`` locally). Read the Docs
installs the validation extra and ``docs/requirements.txt``. The package lives
under ``src/``, added to sys.path below so a source checkout also builds.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath("_ext"))  # local Sphinx extensions (cab_catalog)

from dosho import __version__

# -- Project information -----------------------------------------------------

project = "dosho"
author = "Sphesihle Makhathini"
copyright = f"{datetime.now(tz=UTC).year}, {author}"

version = __version__
release = __version__

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "myst_parser",
    "cab_catalog",  # generates reference/cabs.rst from the live registry + manifest
]

templates_path = ["_templates"]
# `design_*.md` are repo-internal design records, not published pages -- they
# carry file:line citations and implementation sequencing that go stale by
# design. myst_parser would otherwise pick them up as documents, and CI builds
# with `-W`, so a design doc in no toctree fails the build. Matches
# stimela-ninja's own conf.py, which excludes its design docs the same way.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "design_*.md",
]

# Keep local documentation and CI strict about missing references.
nitpicky = True
# These are type variables, aliases or constraint metadata rather than classes
# with linkable API entries. Preserve their annotation text without class links.
nitpick_ignore = [
    ("py:class", "JsonValue"),
    ("py:class", "pydantic.types.JsonValue"),
    ("py:class", "MetaT"),
    ("py:class", "dosho.validation.schema.MetaT"),
    ("py:obj", "dosho.validation.schema.MetaT"),
    ("py:class", "annotated_types.Ge"),
    ("py:class", "ge=0"),
    ("py:class", "strict=True"),
    ("py:class", "BaseModel"),
    ("py:class", "TypeAliasForwardRef"),
    ("py:class", "'dosho.validation.compiled.CompiledParamMeta'"),
]
autodoc_type_aliases = {
    "BaseModel": "pydantic.BaseModel",
    "CompiledParamMeta": "dosho.validation.compiled.CompiledParamMeta",
}

# -- Autodoc / autosummary ---------------------------------------------------

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": False,
}
# pydantic BaseModels (Cab, StepRef, ...) carry a lot of inherited
# machinery; don't document it.
autodoc_inherit_docstrings = False

napoleon_google_docstring = True
napoleon_numpy_docstring = True

# -- Intersphinx -------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "shinobi": ("https://stimela-ninja.readthedocs.io/en/latest/", None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = f"dosho {release}"
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/shinobi-dosho/dosho/",
    "source_branch": "main",
    "source_directory": "docs/",
}

# -- MyST (markdown) ---------------------------------------------------------

myst_enable_extensions = ["colon_fence", "deflist"]
