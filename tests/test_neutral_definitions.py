"""The public catalogue/schema boundary never needs the execution framework."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import BaseModel, Field, ValidationError

import dosho
from dosho.validation import CabSpec, build_document, compile_cab, describe_cab
from dosho.validation.exceptions import CabLoadError
from dosho.validation.pyfunc import inputs_model_from_signature, outputs_model_from_return
from dosho.validation.schema import ParamMeta


class Output(BaseModel):
    value: int


def test_every_definition_and_catalogue_load_with_shinobi_imports_blocked(tmp_path):
    source = Path(__file__).resolve().parents[1]
    script = """
import importlib.abc, runpy, sys, types
class NoShinobi(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'shinobi':
            raise AssertionError('unexpected execution import: ' + fullname)
sys.meta_path.insert(0, NoShinobi())
import dosho
from dosho.validation import CabSpec, describe_cab
from dosho.validation.pyfunc import inputs_model_from_signature, outputs_model_from_return
for name in dosho.list_cabs():
    value = dosho.get(name)
    if isinstance(value, CabSpec):
        describe_cab(value)
    else:
        inputs_model_from_signature(value)
        outputs_model_from_return(value)
module = runpy.run_path(sys.argv[1])
module['_generate'](types.SimpleNamespace(srcdir=sys.argv[2]))
assert not any(name == 'shinobi' or name.startswith('shinobi.') for name in sys.modules)
"""
    subprocess.run(
        [sys.executable, "-c", script, str(source / "docs/_ext/cab_catalog.py"), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    text = (tmp_path / "reference/cabs.rst").read_text()
    assert "ProductFamily[FITSImage]" in text
    assert "List[MSv2]" in text


def test_marker_preserves_function_identity_signature_and_body():
    def original(ctx, value: int = 2) -> Output:
        raise AssertionError("schema inspection executed the body")

    signature = inspect.signature(original)
    marked = dosho.pystep(name="marked", cache=False, write_paths=[])(original)
    assert marked is original
    assert inspect.signature(marked) == signature
    inputs, wants_ctx, _ = inputs_model_from_signature(marked)
    assert wants_ctx and inputs().value == 2
    assert outputs_model_from_return(marked) == (Output, False)


def test_shared_function_schema_preserves_choices_and_fieldinfo():
    default = Field("fast", description="explicit", json_schema_extra={"abbreviation": "m"})

    def function(
        mode: Annotated[str, ParamMeta(choices=["fast", "slow"], info="metadata")] = default,
    ) -> None:
        raise AssertionError

    before = dict(default.json_schema_extra)
    model, _, metadata = inputs_model_from_signature(function)
    assert model().mode == "fast"
    assert model.model_fields["mode"].description == "explicit"
    assert model.model_fields["mode"].json_schema_extra["abbreviation"] == "m"
    assert metadata["mode"].choices == ["fast", "slow"]
    assert default.json_schema_extra == before
    with pytest.raises(ValidationError):
        model(mode="unknown")


def test_document_selection_composition_and_exact_descriptive_schema(tmp_path):
    (tmp_path / "base.yaml").write_text("base:\n  command: tool\n  image: TOOL\n")
    text = """
_include: (pkg)base.yaml
cabs:
  chosen:
    _use: base
    inputs:
      data:
        ms-list: {dtype: 'List[MSv2]', required: true, info: Scientific input}
      mode: {dtype: str, default: fast, choices: [fast, slow], nullable: false}
    outputs:
      image: {dtype: 'ProductFamily[FITSImage]'}
    dataset_accesses: [{input: data_ms_list, mode: read}]
"""
    spec = build_document(
        "dosho-cab-v1", text, "chosen", package_roots={"pkg": tmp_path}, images={"TOOL": "test:1"}
    )
    assert isinstance(spec, CabSpec)
    description = describe_cab(spec)
    field = description.inputs["data_ms_list"]
    assert (field.original_name, field.dtype, field.required) == (
        "data.ms-list",
        "List[MSv2]",
        True,
    )
    assert field.description == "Scientific input"
    assert description.image == "test:1"
    assert description.outputs["image"].dtype == "ProductFamily[FITSImage]"
    assert description.inputs["mode"].nullable is False
    with pytest.raises(ValueError, match="binding"):
        compile_cab(spec)
    with pytest.raises(CabLoadError, match="not 'other'"):
        build_document("yaml_cab", "one: {command: true}", "other")
    with pytest.raises(CabLoadError, match="no name"):
        build_document("yaml_cab", "one: {command: x}\ntwo: {command: y}")
    with pytest.raises(CabLoadError, match="unknown cab dialect"):
        build_document("other", "")


def test_python_authoring_and_classic_are_neutral():
    spec = dosho.define_cab("tool", "tool", "image:1", {"my-value": ("int", True, None)})
    assert isinstance(spec, CabSpec)
    assert describe_cab(spec).inputs["my_value"].required
    classic = build_document(
        "stimela-classic",
        '{"task":"classic","parameters":[{"name":"my-value","dtype":"int","mapping":"n","required":true}]}',
    )
    assert isinstance(classic, CabSpec)
    assert describe_cab(classic).inputs["my_value"].meta.nom_de_guerre == "n"
    assert compile_cab(classic).inputs_model(my_value=2).my_value == 2
    with pytest.raises(CabLoadError, match="not 'wrong'"):
        build_document("stimela-classic", '{"task":"classic"}', "wrong")


def test_decorator_options_are_snapshots():
    from dosho.validation.pyfunc import get_pystep_definition

    paths = ["result"]
    constants = [1, 2]

    @dosho.pystep(write_paths=paths, values=constants)
    def function(result: Path, values: list[int]) -> None:
        pass

    paths.append("other")
    constants.append(3)
    definition = get_pystep_definition(function)
    assert definition.options["write_paths"] == ["result"]
    assert definition.options["values"] == [1, 2]
    copy = definition.options
    copy["values"].append(4)
    assert definition.options["values"] == [1, 2]


@pytest.mark.parametrize(
    "required,default,nullable",
    [(True, None, None), (True, 1, None), (False, 1, False), (True, None, True)],
)
def test_description_and_compilation_share_required_default(required, default, nullable):
    from dosho.validation import parse_document

    spec = parse_document(
        "tool",
        {
            "command": "tool",
            "inputs": {
                "value": {
                    "dtype": "int",
                    "required": required,
                    "default": default,
                    **({"nullable": nullable} if nullable is not None else {}),
                }
            },
        },
    )
    description = describe_cab(spec).inputs["value"]
    field = compile_cab(spec).inputs_model.model_fields["value"]
    assert description.required == field.is_required()
    if not description.required:
        assert description.default == field.default


def test_description_rejects_invalid_presence_rule_without_runtime_types():
    from dosho.validation import parse_document

    spec = parse_document(
        "tool", {"command": "tool", "inputs": {"value": {"dtype": "MSv2", "nullable": False}}}
    )
    with pytest.raises(CabLoadError, match="requires required"):
        describe_cab(spec)


def test_missing_validation_dependency_is_not_reported_as_missing_shinobi():
    script = """
import importlib.abc, sys
class NoPydantic(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'pydantic':
            raise ModuleNotFoundError('validation dependency pydantic unavailable', name='pydantic')
sys.meta_path.insert(0, NoPydantic())
import dosho.cabs
try:
    dosho.cabs.wsclean
except ModuleNotFoundError as exc:
    assert exc.name == 'pydantic'
    assert 'stimela-ninja' not in str(exc)
    assert 'shinobi' not in str(exc)
else:
    raise AssertionError('definition lookup should require validation dependencies')
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)


def test_classic_ignores_shared_provider_options(tmp_path):
    spec = build_document(
        "stimela-classic",
        '{"task":"test", "base":"IMG"}',
        images={"IMG": "test:1"},
        package_roots={"pkg": tmp_path},
    )
    assert spec.name == "test"
    assert describe_cab(spec).image == "IMG"
