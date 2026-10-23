"""Inert cab documents and compiled parameter contracts, independent of execution."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from .schema import (
    ParamMeta,
    ParamPattern as Pattern,
    ParamSegment as Segment,
    Policies,
    match_patterns,
    parameter_name,
)


class CabSpec(BaseModel):
    name: str
    document: dict[str, JsonValue]
    images: dict[str, str] = Field(default_factory=dict)


class CompiledParamMeta(ParamMeta):
    framework_family: JsonValue = None


ParamSegment = Segment[CompiledParamMeta]
ParamPattern = Pattern[CompiledParamMeta]


class CompiledCab(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    command: str
    inputs_model: type[BaseModel]
    outputs_model: type[BaseModel]
    policies: Policies = Field(default_factory=Policies)
    field_meta: dict[str, CompiledParamMeta] = Field(default_factory=dict)
    input_patterns: list[ParamPattern] = Field(default_factory=list)
    output_patterns: list[ParamPattern] = Field(default_factory=list)
    framework_declarations: dict[str, JsonValue] = Field(default_factory=dict)
    input_mutability: dict[str, str] = Field(default_factory=dict)
    flavour: str = "binary"
    image: str | None = None
    info: str | None = None
    wranglers: dict[str, list[str]] = Field(default_factory=dict)
    sandbox: bool | None = None
    harvest: list[str] = Field(default_factory=list)
    scratch: list[str] = Field(default_factory=list)
    cache: bool | None = None

    def param_name(self, field: str) -> str:
        return parameter_name(self.field_meta, field)

    def match_pattern(self, name: str) -> CompiledParamMeta | None:
        return match_patterns(self.input_patterns, name)
