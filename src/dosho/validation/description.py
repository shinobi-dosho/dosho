"""Descriptive schema records retain exact declared dtype labels."""

from dataclasses import dataclass
from typing import Any

from .compiled import CompiledParamMeta, ParamPattern


@dataclass(frozen=True)
class ParameterDescription:
    name: str
    original_name: str
    dtype: str
    required: bool
    default: Any
    meta: CompiledParamMeta
    mutability: str | None = None

    @property
    def description(self):
        return self.meta.info

    @property
    def choices(self):
        return self.meta.choices

    @property
    def nullable(self):
        return self.meta.nullable


@dataclass(frozen=True)
class CabDescription:
    name: str
    command: str | None
    info: str | None
    image: str | None
    inputs: dict[str, ParameterDescription]
    outputs: dict[str, ParameterDescription]
    input_patterns: list[ParamPattern]
    output_patterns: list[ParamPattern]
    framework_declarations: dict[str, Any]
