"""Strict MeasurementSet contracts: which cabs declare them, and what they say.

A cab is *strict* when an MS field is typed `MSv2` (YAML `dtype: MSv2`) and
the cab declares `dataset_accesses` -- shinobi then plans, claims, snapshots
and verifies that MS around the step instead of treating it as an opaque
path. That is opt-in per cab, so `CONTRACTS` is the whole strict set: a cab
that gains (or loses) a contract fails `test_strict_set_is_exactly_contracted`
until someone records what it declares here.

Nothing below needs casacore or a real MS. Declarations are checked as loaded,
and planning runs with shinobi's closure resolution patched to fail, so a test
that would have to inspect a table on disk fails loudly instead.
"""

from __future__ import annotations

import warnings

import pytest
import shinobi.dataset_access as access_module
from pydantic import BaseModel
from shinobi import DatasetAccess, DatasetColumns, MSv2, Recipe
from shinobi.dataset_access import (
    DatasetAccessError,
    plan_recipe_accesses,
    scope_has_dataset_contract,
    validate_scope_dataset_accesses,
)
from shinobi.datasets import DatasetKind, dataset_declarations
from shinobi.loaders import yaml_cab
from shinobi.loaders.yaml_cab import CabLoadError
from shinobi.steps.schema import Cab, InputRef, Mutability, StepRef, mutated_path_fields

from dosho import registry

FLAGS = DatasetColumns(write=("FLAG", "FLAG_ROW"))

# The exact declaration each strict cab carries. Column lists appear only
# where they are complete; a cab whose columns are parameters declares none
# (stimela-ninja#176), which shinobi reads as the whole dataset.
CONTRACTS: dict[str, list[DatasetAccess]] = {
    "simms-telsim": [DatasetAccess(field="ms", mode="create")],
    "simms-skysim": [DatasetAccess(field="ms", mode="write", allow_schema_change=True)],
    "msutils-flags-backup": [
        DatasetAccess(field="ms", mode="read", columns=DatasetColumns(read=("FLAG", "FLAG_ROW")))
    ],
    "msutils-flags-restore": [DatasetAccess(field="ms", mode="write", columns=FLAGS)],
    "tricolour": [DatasetAccess(field="ms", mode="write")],
}


def _scope(cab):
    """The `Scope` carrying a registry entry's schema: a `Cab`, or a pystep's
    underlying step."""
    return getattr(cab, "step", cab)


def _all_scopes() -> dict[str, object]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # experimental-cab warnings
        return {name: _scope(registry.get(name)) for name in registry.list_cabs()}


def _load(name: str, text: str) -> Cab:
    """A document built the way the registry builds it, from edited text."""
    return yaml_cab.loads(text, **registry.loader_options())[name]


def _document(name: str) -> str:
    return registry.get_document(name)[1]


def _replace(text: str, old: str, new: str) -> str:
    """`str.replace` that fails when the edit misses: a negative test whose
    mutation silently did nothing would pass for the wrong reason."""
    assert old in text, f"{old!r} not in document"
    return text.replace(old, new)


def assert_strict(scope, expected: list[DatasetAccess]) -> None:
    """Everything a strict contract has to agree with, beyond its own list."""
    assert list(scope.dataset_accesses) == expected
    validate_scope_dataset_accesses(scope)
    inputs = dataset_declarations(scope.inputs_model)
    outputs = dataset_declarations(scope.outputs_model)
    mutated = mutated_path_fields(scope)
    for access in expected:
        field = access.field
        assert field in inputs, f"{scope.name}.{field} is not a strict input"
        assert inputs[field].kind is DatasetKind.MEASUREMENT_SET_V2
        if field in scope.outputs_model.model_fields:
            assert field in outputs, f"{scope.name}.{field} output is not strict"
            assert outputs[field].kind is DatasetKind.MEASUREMENT_SET_V2
        # A filesystem write -- dual declaration, MUTABLE or a write access --
        # exactly when the contract is not a read.
        assert (field in mutated) is (access.mode.value != "read")
        if isinstance(scope, Cab):
            # Documents spell a writer `mutable: true`; a reader or a creator
            # is not mutable (a mutable field may not declare only a read).
            mutable = scope.mutability_of(field) is Mutability.MUTABLE
            assert mutable is (access.mode.value == "write")


def test_strict_set_is_exactly_contracted():
    strict = {name for name, scope in _all_scopes().items() if scope_has_dataset_contract(scope)}
    assert strict == set(CONTRACTS)


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_contract(name):
    assert_strict(_all_scopes()[name], CONTRACTS[name])


# --- the contract fails closed when a document is edited wrongly ------------


def test_a_mutable_field_cannot_declare_only_read():
    text = _replace(_document("msutils-flags-restore"), "mode: write", "mode: read")
    text = _replace(text, "write: [FLAG, FLAG_ROW]", "read: [FLAG, FLAG_ROW]")
    with pytest.raises(CabLoadError, match="cannot declare only read"):
        _load("msutils-flags-restore", text)


def test_backup_cannot_become_mutable_while_it_declares_a_read():
    text = _replace(
        _document("msutils-flags-backup"),
        "          positional: true\n",
        "          positional: true\n        mutable: true\n",
    )
    with pytest.raises(CabLoadError, match="cannot declare only read"):
        _load("msutils-flags-backup", text)


def test_creating_a_column_needs_allow_schema_change():
    text = _replace(_document("msutils-flags-restore"), "write: [FLAG, FLAG_ROW]", "create: [X]")
    with pytest.raises(CabLoadError, match="allow_schema_change"):
        _load("msutils-flags-restore", text)


def test_an_access_on_an_unknown_field_is_refused():
    text = _replace(_document("tricolour"), "      - field: ms\n", "      - field: msname\n")
    with pytest.raises(CabLoadError, match="unknown field"):
        _load("tricolour", text)


def test_a_path_only_ms_is_not_strict_even_with_accesses():
    """`dtype: MS` stays a plain `Path`: the accesses still load, but nothing
    declares the field an MSv2, so the cab is not the contract it reads as."""
    text = _replace(_document("msutils-flags-restore"), "dtype: MSv2", "dtype: MS")
    weak = _load("msutils-flags-restore", text)
    assert dataset_declarations(weak.inputs_model) == {}
    assert dataset_declarations(weak.outputs_model) == {}
    with pytest.raises(AssertionError):
        assert_strict(weak, CONTRACTS["msutils-flags-restore"])


# --- planning a strict pipeline (no casacore, no MS on disk) ----------------


class _MS(BaseModel):
    ms: MSv2


class _Empty(BaseModel):
    pass


@pytest.fixture
def no_closure(monkeypatch):
    """Planning a pipeline whose MS does not exist yet must not inspect it --
    telsim's `create` stands in for the table until it is made."""

    def refuse(*args, **kwargs):
        pytest.fail("planning inspected a dataset closure")

    monkeypatch.setattr(access_module, "resolve_dataset_closure", refuse)


def _pipeline(backup: Cab) -> Recipe:
    """telsim -> flags backup -> tricolour -> flags restore, every step wired
    from the one recipe input, as strict steps have to be."""
    ms = InputRef(field="ms")
    recipe = Recipe(name="strict-flagging", inputs_model=_MS, outputs_model=_Empty)
    recipe.add_step("sim", registry.get("simms-telsim"), ms=ms, telescope="meerkat")
    # The msutils flags cabs take their version as a `name` input, which
    # collides with `add_step`'s own first argument -- so it rides in on a
    # StepRef's params rather than as a keyword.
    recipe.add_step("backup", StepRef(name="backup", step=backup, params={"name": "pre"}), ms=ms)
    recipe.add_step("flag", registry.get("tricolour"), ms=ms)
    restore = registry.get("msutils-flags-restore")
    recipe.add_step("restore", StepRef(name="restore", step=restore, params={"name": "pre"}), ms=ms)
    return recipe


def test_a_strict_flagging_pipeline_plans_in_order(no_closure, tmp_path):
    plan = plan_recipe_accesses(
        _pipeline(registry.get("msutils-flags-backup")),
        {"ms": tmp_path / "sim.ms"},
        workspace=tmp_path,
    )
    modes = {step: [a.mode.value for a in accesses] for step, accesses in plan.accesses.items()}
    assert modes == {
        "sim": ["create"],
        "backup": ["read"],
        "flag": ["write"],
        "restore": ["write"],
    }
    # Nothing is wired step-to-step, so every edge below is an access hazard
    # shinobi inferred, each with the reason it gives.
    assert plan.reasons == {
        ("backup", "sim"): ("read-after-write: sim.ms, MAIN.FLAG",),
        ("flag", "backup"): ("write-after-read: sim.ms",),
        ("restore", "flag"): ("write-after-write: sim.ms, MAIN.FLAG",),
    }
    names = plan.graph.names
    for child, parent in plan.reasons:
        assert names.index(parent) in plan.graph.deps[names.index(child)]


def test_backup_with_its_old_output_is_a_contradictory_reader(no_closure, tmp_path):
    """The reason backup lost its `ms` output: a same-named output is a
    filesystem write, which a read contract contradicts."""
    text = _replace(
        _document("msutils-flags-backup"),
        "    dataset_accesses:\n",
        "    outputs:\n      ms:\n        dtype: MSv2\n    dataset_accesses:\n",
    )
    backup = _load("msutils-flags-backup", text)
    with pytest.raises(DatasetAccessError, match="declares READ access"):
        plan_recipe_accesses(_pipeline(backup), {"ms": tmp_path / "sim.ms"}, workspace=tmp_path)


def test_telsim_declared_as_a_reader_is_refused(no_closure, tmp_path):
    """telsim writes its MS (`write_paths=["ms"]`), so a `read` contract on it
    contradicts the schema and planning refuses it, rather than recording a
    creation as a read."""
    telsim = registry.get("simms-telsim")
    as_reader = telsim.step.model_copy(
        update={"dataset_accesses": [DatasetAccess(field="ms", mode="read")]}
    )
    reader = telsim.model_copy(update={"step": as_reader})
    # After the real telsim, so the misdeclared one resolves against the
    # planned (not yet existing) MS instead of inspecting one on disk.
    ms = InputRef(field="ms")
    recipe = Recipe(name="resimulate", inputs_model=_MS, outputs_model=_Empty)
    recipe.add_step("sim", telsim, ms=ms, telescope="meerkat")
    recipe.add_step("resim", reader, ms=ms, telescope="meerkat")
    with pytest.raises(DatasetAccessError, match="declares READ access"):
        plan_recipe_accesses(recipe, {"ms": tmp_path / "sim.ms"}, workspace=tmp_path)
