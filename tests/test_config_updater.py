import pytest
from pathlib import Path
from experiment_generator.config_updater import ConfigUpdater
from experiment_generator.utils import read_yaml


def test_update_config_params_update_params_and_jobname_warning(tmp_path, capsys):
    repo_dir = tmp_path / "test_repo"
    rel_path = Path("config.yaml")
    config_path = repo_dir / rel_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
    jobname: existing_job_name
    queue: normalsr
    """
    )

    updater = ConfigUpdater(repo_dir)

    # test_jobname will trigger the warning
    params = {
        "jobname": "test_jobname",
        "queue": "normal",
    }
    with pytest.warns(UserWarning) as record:
        updater.update_config_params(params, config_path)
    assert any(
        "-- jobname must be the same as" in str(f.message) for f in record
    ), "Expected jobaname inconsistency warning not showing!"

    updated = read_yaml(config_path)

    assert updated["jobname"] == "test_repo"
    assert updated["queue"] == "normal"
