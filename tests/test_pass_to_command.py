"""Explicit non-argv tool-adapter inputs still validate as ordinary ports."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dosho.validation import build_document, compile_cab, describe_cab
from dosho.validation.policies import build_argv

_DOCUMENT = """cabs:
  tool:
    command: tool
    inputs:
      value: {dtype: int, required: true}
      native-file: {dtype: File, required: true}
      dependency: {dtype: File, required: true, writable: false, pass_to_command: false}
"""


def test_metadata_port_validates_but_is_not_a_native_flag():
    spec = build_document("dosho-cab-v1", _DOCUMENT, "tool")
    assert describe_cab(spec).inputs["dependency"].meta.pass_to_command is False
    cab = compile_cab(spec)
    validated = cab.inputs_model(value=2, native_file="visible", dependency="screen.fits")
    assert validated.dependency == Path("screen.fits")
    assert cab.field_meta["dependency"].writable is False
    assert build_argv(cab, validated.model_dump()) == [
        "tool",
        "--value",
        "2",
        "--native-file",
        "visible",
    ]
    with pytest.raises(ValidationError):
        cab.inputs_model(value=2, native_file="visible")
    with pytest.raises(ValidationError):
        cab.inputs_model(value=2, native_file="visible", dependency=123)


def test_pass_to_command_defaults_to_unchanged_native_behavior():
    cab = compile_cab(
        build_document(
            "dosho-cab-v1",
            _DOCUMENT.replace("pass_to_command: false", "pass_to_command: true"),
            "tool",
        )
    )
    assert build_argv(cab, {"value": 2, "native_file": "visible", "dependency": "screen.fits"})[
        -2:
    ] == [
        "--dependency",
        "screen.fits",
    ]


def test_non_boolean_pass_to_command_is_rejected():
    with pytest.raises((ValidationError, ValueError)):
        compile_cab(
            build_document(
                "dosho-cab-v1",
                _DOCUMENT.replace("pass_to_command: false", 'pass_to_command: "false"'),
                "tool",
            )
        )
