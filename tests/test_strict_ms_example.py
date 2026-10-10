"""The example must stay fully contracted before any native evidence is taken."""

import runpy
from pathlib import Path

import pytest
from shinobi.dataset_access import plan_recipe_accesses
from shinobi.datasets import DatasetKind, dataset_declarations


def example():
    return runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "examples" / "strict_ms_pipeline.py")
    )["pipeline"]


def test_example_plans_only_strict_ms_ports(no_dataset_closure, tmp_path):
    recipe = example()
    plan = plan_recipe_accesses(
        recipe,
        {"ms": tmp_path / "sim.ms", "sky": tmp_path / "sky.txt", "flag_config": "flags.yaml"},
        workspace=tmp_path,
    )
    assert plan.graph.names == [
        "simulate",
        "populate",
        "backup",
        "flag",
        "restore",
        "summary",
        "image",
    ]
    for accesses in plan.accesses.values():
        assert accesses
    for ref in recipe.steps:
        scope = ref.step
        inputs = dataset_declarations(scope.inputs_model)
        for access in scope.dataset_accesses:
            declaration = inputs.get(access.field) or inputs.get(access.field + "[]")
            assert declaration is not None, f"{ref.name}.{access.field} is path-only"
            assert declaration.kind is DatasetKind.MEASUREMENT_SET_V2
        for model in [scope.inputs_model, scope.outputs_model]:
            for field, declaration in dataset_declarations(model).items():
                assert declaration.kind is DatasetKind.MEASUREMENT_SET_V2, field
    assert plan.accesses["summary"][0].declaration.columns.read == ("UVW", "DATA", "FLAG")
    assert ("restore", "backup") in plan.reasons
    assert ("flag", "backup") in plan.reasons
    assert ("image", "summary") in plan.reasons


@pytest.fixture
def no_dataset_closure(monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("planning inspected a dataset that does not exist yet")

    monkeypatch.setattr("shinobi.dataset_access.resolve_dataset_closure", refuse)
