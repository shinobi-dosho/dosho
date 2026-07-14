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
    assert len(dosho.get("killms").inputs_model.model_fields) == 94


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
