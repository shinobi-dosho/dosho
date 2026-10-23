"""Keep integration runtime records inside each test's disposable workspace."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_records(monkeypatch, tmp_path):
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    monkeypatch.setenv("SHINOBI_PROVENANCE__DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("SHINOBI_SANDBOX__DIR", str(tmp_path / "sandboxes"))
