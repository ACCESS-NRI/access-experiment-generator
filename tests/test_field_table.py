from experiment_generator.field_table_updater import FieldTableUpdater
from experiment_generator.tmp_parser.field_table import read_field_table
from experiment_generator.common_var import REMOVED, PRESERVED


def test_update_field_table_params_add_change_remove(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    field_table_file = repo_dir / "field_table"
    field_table_file.write_text(
        """
"prog_tracers","ocean_mod","temp"
horizontal-advection-scheme = mdppm
vertical-advection-scheme = mdppm
restart_file  = ocean_temp_salt.res.nc
ppm_hlimiter = 3
ppm_vlimiter = 3
/
# added by FRE: sphum must be present in atmos
# specific humidity for moist runs
 "TRACER", "atmos_mod", "sphum"
           "longname",     "specific humidity"
           "units",        "kg/kg"
       "profile_type", "fixed", "surface_value=3.e-6" /

"rayleigh_damp_table","ocean_mod","rayleigh_damp_table"
"rayleigh","Lombok","itable=36,jtable=112,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Ombai","itable=44,jtable=111,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=106,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=107,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=108,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=109,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"/
    """
    )

    updater = FieldTableUpdater(repo_dir)

    param_dict = {
        "temp": {
            "ocean_mod": {
                "prog_tracers": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        {
                            "key": "restart_file",
                            "value": "ocean_temp_salt2.res.nc",
                        },
                        {
                            "key": "ppm_hlimiter",
                            "value": "4",
                        },
                    ]
                }
            }
        },
        "sphum": {
            "atmos_mod": {
                "TRACER": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        {
                            "key": "profile_type",
                            "value": "fixed",
                            "params": {"surface_value": "1.e-6"},
                        },
                    ]
                }
            }
        },
        "rayleigh_damp_table": {
            "ocean_mod": {
                "rayleigh_damp_table": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        PRESERVED,
                        REMOVED,
                        {
                            "key": "rayleigh",
                            "value": "Ombai",
                            "params": {
                                "itable": "0",
                                "jtable": "0",
                                "ktable_1": "0",
                                "ktable_2": "0",
                                "rayleigh_damp_table": "0",
                            },
                        },
                    ]
                }
            }
        },
    }

    state = {}

    # run 1
    updater.update_field_table_params(
        param_dict,
        field_table_file.name,
        state,
    )

    after1 = read_field_table(field_table_file)

    # run 2 with same state
    updater.update_field_table_params(
        param_dict,
        field_table_file.name,
        state,
    )
    after2 = read_field_table(field_table_file)
    assert after1 == after2, "Field table changed on 2nd identical update!"

    # and state should not be empty (BASE snapshots + REMOVE markers)
    assert any(k.endswith("::BASE") for k in state)
    assert any("::REMOVE[" in k for k in state)
