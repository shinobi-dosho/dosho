"""Standalone validation needs no execution framework."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import ValidationError

from dosho.validation import (
    ParamMeta,
    Policies,
    build_argv,
    build_model,
    compile_cab,
    parse_document,
)
from dosho.validation.exceptions import UnsupportedFlavourError


def test_validation_imports_and_formats_without_shinobi():
    script = """
import sys
class Refuse:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "shinobi" or fullname.startswith("shinobi."):
            raise RuntimeError("validation imported the execution framework")
sys.meta_path.insert(0, Refuse())
from dosho.validation import compile_cab, parse_document, build_argv
cab = compile_cab(parse_document("tool", {"command": "tool", "inputs": {"n": {"dtype": "int", "required": True}}}))
assert build_argv(cab, cab.inputs_model(n="4").model_dump()) == ["tool", "--n", "4"]
assert not any(name == "shinobi" or name.startswith("shinobi.") for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_base_catalogue_needs_neither_validation_nor_shinobi():
    script = """
import sys
class Refuse:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"shinobi", "pydantic"}:
            raise RuntimeError("base catalogue imported optional validation or execution")
sys.meta_path.insert(0, Refuse())
import dosho
assert "wsclean" in dosho.list_cabs()
from dosho.registry import get_document
assert "wsclean" in get_document("wsclean")[1]
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_public_model_helpers_support_reusable_inputs():
    model = build_model(
        "RecipeInputs",
        {"iterations": ("int", False, 2)},
        nullable={"iterations": False},
        choices={"iterations": [1, 2, 3]},
    )
    assert model().iterations == 2
    with pytest.raises(ValidationError):
        model(iterations=None)
    with pytest.raises(ValidationError):
        model(iterations=4)
    assert ParamMeta(positional=True).positional
    assert Policies(prefix="-").arg_name("size") == "-size"


def test_standalone_formatter_rejects_code_flavours():
    cab = compile_cab(
        parse_document("tool", {"command": "raise SystemExit()", "flavour": "python-code"})
    )
    with pytest.raises(UnsupportedFlavourError):
        build_argv(cab, {})


def test_generic_length_constraints_and_defaults():
    import pytest
    from pydantic import ValidationError

    from dosho.validation import build_model, compile_cab, parse_document

    cab = compile_cab(
        parse_document(
            "bounded",
            {
                "command": "tool",
                "inputs": {
                    "items": {
                        "dtype": "List[str]",
                        "default": [],
                        "nullable": False,
                        "max_length": 0,
                    }
                },
            },
        )
    )
    assert cab.inputs_model().items == []
    with pytest.raises(ValidationError):
        cab.inputs_model(items=["unsafe"])
    bad = build_model(
        "BadDefault", {"items": ("List[str]", False, ["bad"])}, lengths={"items": {"max_length": 0}}
    )
    with pytest.raises(ValidationError):
        bad()
    for bounds in [{"min_length": -1}, {"max_length": True}, {"min_length": 2, "max_length": 1}]:
        with pytest.raises(ValueError):
            build_model("BadBounds", {"items": ("List[str]", False, [])}, lengths={"items": bounds})


@pytest.mark.parametrize("pol,token", [(["I", "Q"], "I,Q"), ("IQUV", "IQUV")])
def test_wsclean_pol_formats_without_redundant_repeat_hint(pol, token):
    from dosho import registry

    document = registry.get("wsclean").document
    field = document["inputs"]["pol"]
    # The former comma hint was ignored; the cab's normal list separator owns this.
    for parameter in (field, {**field, "policies": {"repeat": ","}}):
        cab = compile_cab(
            parse_document(
                "wsclean_pol",
                {
                    "command": document["command"],
                    "policies": document["policies"],
                    "inputs": {"pol": parameter},
                },
            )
        )
        values = cab.inputs_model(pol=pol).model_dump()
        assert build_argv(cab, values) == ["wsclean", "-pol", token]


def test_simms_list_defaults_validate_and_preserve_complete_argv():
    from dosho import registry

    cab = compile_cab(registry.get("simms"))
    expected_defaults = {
        "direction": ["J2000,0deg,-30deg"],
        "freq0": ["1.4GHz"],
        "dfreq": ["2MHz"],
        "nchan": [1],
    }
    values = cab.inputs_model(msname="example.ms", telescope="meerkat").model_dump()
    checked = cab.inputs_model.model_validate(values)
    for name, expected in expected_defaults.items():
        assert cab.inputs_model.model_fields[name].default == expected
        assert values[name] == expected
        assert getattr(checked, name) == expected
    assert build_argv(cab, values) == [
        "simms",
        "--name",
        "example.ms",
        "--tel",
        "meerkat",
        "--type",
        "casa",
        "--coord-sys",
        "itrf",
        "--direction",
        "J2000,0deg,-30deg",
        "--synthesis",
        "4",
        "--dtime",
        "2",
        "--freq0",
        "1.4GHz",
        "--dfreq",
        "2MHz",
        "--nband",
        "1",
        "--nchan",
        "1",
        "--pol",
        "XX XY YX YY",
        "--feed",
        "perfect X Y",
        "--scan-lag",
        "0",
    ]
