from experiment_generator.mom6_input_updater import Mom6InputUpdater
from experiment_generator.tmp_parser.mom6_input import read_mom_input


def test_update_mom6_params_add_change_remove(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    mom_file = repo_dir / "MOM_input"
    mom_file.write_text(
        """
DT = 900.0                      !   [s]
                                ! The (baroclinic) dynamics time step.  The time-step that is actually used will
                                ! be an integer fraction of the forcing time-step (DT_FORCING in ocean-only mode
                                ! or the coupling timestep in coupled mode.)
DT_THERM = 7200.0               !   [s] default = 900.0
                                ! The thermodynamic and tracer advection time step. Ideally DT_THERM should be
                                ! an integer multiple of DT and less than the forcing or coupling time-step,
                                ! unless THERMO_SPANS_COUPLING is true, in which case DT_THERM can be an integer
                                ! multiple of the coupling timestep.  By default DT_THERM is set to DT.
    """
    )

    updater = Mom6InputUpdater(repo_dir)
    updater.update_mom6_params(
        {
            "DT": 10,
            "THERMO_SPANS_COUPLING": True,
            "DT_THERM": "REMOVE",
        },
        mom_file.name,
    )

    raw_lines, params = read_mom_input(mom_file)

    assert params["DT"] == "10"
    assert "DT_THERM" not in params
    assert params["THERMO_SPANS_COUPLING"] == "True"

    assert any("The (baroclinic) dynamics time step." in line for line in raw_lines)
