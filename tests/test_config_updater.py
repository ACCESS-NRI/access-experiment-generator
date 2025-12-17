import pytest
from pathlib import Path
from experiment_generator.config_updater import ConfigUpdater
from experiment_generator.tmp_parser.yaml_config import read_yaml
import warnings


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

    state = {}

    with pytest.warns(UserWarning) as record:
        updater.update_config_params(params, config_path, state)
    assert any(
        "-- jobname must be the same as" in str(f.message) for f in record
    ), "Expected jobaname inconsistency warning not showing!"

    updated = read_yaml(config_path)

    assert updated["jobname"] == "test_repo"
    assert updated["queue"] == "normal"


def test_update_config_params_no_jobname_no_warning(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    config_path = repo_dir / "config.yaml"
    config_path.write_text("queue: normal\n")

    updater = ConfigUpdater(repo_dir)

    params = {"queue": "express"}
    state = {}

    # No warning expected
    updater.update_config_params(params, Path("config.yaml"), state)

    updated = read_yaml(config_path)
    assert updated["jobname"] == "test_repo"
    assert updated["queue"] == "express"


def test_update_config_params_jobname_matches_no_warning(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    rel_path = Path("config.yaml")
    config_path = repo_dir / rel_path
    config_path.write_text("jobname: test_repo\nqueue: normal\n")

    updater = ConfigUpdater(repo_dir)

    params = {"jobname": "test_repo", "queue": "express"}
    state = {}

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        updater.update_config_params(params, rel_path, state)

    assert not any(issubclass(x.category, UserWarning) for x in w)

    updated = read_yaml(config_path.as_posix())
    assert updated["jobname"] == "test_repo"
    assert updated["queue"] == "express"
