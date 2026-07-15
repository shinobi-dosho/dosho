"""dosho.cabs.killms -- ported from killMS's own DefaultParset.cfg, the
same ReadCFG.py-based format DDFacet uses (see ddfacet.py's docstring).
Checks registration, field-count sanity, real argv shape, and that killms
builds on top of dosho's own DDFACET image.
"""

from shinobi.policies import build_argv

import dosho


def test_killms_registered_and_uses_pinned_image():
    cab = dosho.get("killms")
    assert cab.name == "killms"
    assert cab.command == "kMS.py"
    from dosho import images

    assert cab.image == images.KILLMS
    # KILLMS's own manifest entry builds FROM the DDFACET image (see images.yaml)
    assert images.manifest["images"]["KILLMS"]["build"]["base"] == "DDFACET"


def test_killms_full_field_count():
    # 94 real DefaultParset.cfg options, plus 1 for the head-positional `parset` field
    assert len(dosho.get("killms").inputs_model.model_fields) == 95


def test_killms_case_preserved_flags():
    cab = dosho.get("killms")
    argv = build_argv(
        cab,
        {
            "vis_data_ms_name": "obs.MS",
            "sky_model_sky_model": "model.lsm.html",
            "solvers_solver_type": "CohJones",
        },
    )
    assert argv[0] == "kMS.py"
    assert "--VisData-MSName" in argv and "obs.MS" in argv
    assert "--SkyModel-SkyModel" in argv and "model.lsm.html" in argv
    assert "--Solvers-SolverType" in argv and "CohJones" in argv


def test_killms_parset_is_a_bare_head_positional_at_argv_1():
    # kMS.py's own driver() reads sys.argv[1] as the parset unconditionally
    # (no leftover-arg validation) -- it must land immediately after
    # "kMS.py", or it's silently never read as a parset at all.
    cab = dosho.get("killms")
    argv = build_argv(cab, {"parset": "base.parset", "vis_data_ms_name": "obs.MS"})
    assert argv[0] == "kMS.py"
    assert argv[1] == "base.parset"
    assert "--parset" not in argv


def test_killms_parset_omitted_when_not_given():
    cab = dosho.get("killms")
    argv = build_argv(cab, {"vis_data_ms_name": "obs.MS"})
    assert "base.parset" not in argv
    assert argv[1] == "--VisData-MSName"
