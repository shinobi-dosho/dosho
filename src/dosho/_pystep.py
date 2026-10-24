"""Inert Python step declarations, with no schema or framework dependency."""

from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PystepDefinition:
    """Inert decorator options; the function itself remains ordinary Python."""

    _options: dict[str, Any]

    def __post_init__(self):
        object.__setattr__(self, "_options", deepcopy(self._options))

    @property
    def options(self) -> dict[str, Any]:
        """An independent copy of the options captured at decoration time."""
        return deepcopy(self._options)


def pystep(
    *,
    name=None,
    info=None,
    image=None,
    venv=None,
    backend=None,
    cache=None,
    cache_dir=None,
    sandbox=None,
    harvest=None,
    write_paths=None,
    dataset_accesses=None,
    fits_accesses=None,
    **params,
):
    """Mark a trusted function for execution without wrapping or running it.

    Signature validation happens when a schema is requested or an execution
    framework adapts the definition. Options and per-call constants are data.
    """
    options = dict(
        name=name,
        info=info,
        image=image,
        venv=venv,
        backend=backend,
        cache=cache,
        cache_dir=cache_dir,
        sandbox=sandbox,
        harvest=harvest,
        write_paths=write_paths,
        dataset_accesses=dataset_accesses,
        fits_accesses=fits_accesses,
        **params,
    )

    def decorate(func):
        if not inspect.isfunction(func):
            raise TypeError("@dosho.pystep requires a Python function")
        func.__dosho_pystep__ = PystepDefinition(options)
        return func

    return decorate


def get_pystep_definition(func) -> PystepDefinition | None:
    """Return declaration metadata only for explicitly marked functions."""
    value = getattr(func, "__dosho_pystep__", None)
    return value if inspect.isfunction(func) and isinstance(value, PystepDefinition) else None
