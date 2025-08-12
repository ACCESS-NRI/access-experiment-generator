from experiment_generator.nuopc_runconfig_updater import NuopcRunConfigUpdater
from experiment_generator.tmp_parser.nuopc_config import read_nuopc_config


def test_update_runconfig_params_updates_and_removes(tmp_path):

    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    runconfig_path = repo_dir / "nuopc.runconfig"
    runconfig_path.write_text(
        """
PELAYOUT_attributes::
     atm_ntasks = 364
     atm_nthreads = 2
     atm_pestride = 2
     atm_rootpe = 0
    """
    )

    updater = NuopcRunConfigUpdater(repo_dir)
    updater.update_runconfig_params(
        {
            "PELAYOUT_attributes": {
                "atm_ntasks": 150,
                "atm_nthreads": 1,
                "atm_pestride": 1,
                "atm_rootpe": 0,
            }
        },
        runconfig_path.name,
    )

    new_nuopc_config = read_nuopc_config(runconfig_path)

    assert new_nuopc_config["PELAYOUT_attributes"]["atm_ntasks"] == 150
    assert new_nuopc_config["PELAYOUT_attributes"]["atm_nthreads"] == 1
    assert new_nuopc_config["PELAYOUT_attributes"]["atm_pestride"] == 1
    assert new_nuopc_config["PELAYOUT_attributes"]["atm_rootpe"] == 0
