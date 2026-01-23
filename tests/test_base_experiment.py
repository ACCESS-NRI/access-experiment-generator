from pathlib import Path
from experiment_generator.base_experiment import BaseExperiment
from experiment_generator.experiment_generator import VALID_MODELS


def test_base_experiment_defaults_and_paths(tmp_path, monkeypatch):
    """
    this should set default values for missing optional input keys.
    """
    # minimal input
    indata = {
        "repository_directory": "test_repo",
    }

    base = BaseExperiment(indata)

    assert base.test_path == Path(".").expanduser()
    assert base.model_type is False

    # Repository setup
    assert base.repository_url is None
    assert base.repo_dir == "test_repo"
    assert base.directory == (base.test_path / "test_repo").resolve()
    assert base.existing_branch is None
    assert base.control_branch_name == "ctrl"
    assert base.keep_uuid is False

    # Restart and configuration paths
    assert base.restart_path is None
    assert base.parent_experiment is None
    assert base.config_path is None
    assert base.lab_path is None
    assert base.start_point is None

    # Experiment mode
    assert base.perturbation_enabled is False


def test_base_experiment_custom_values_and_paths(tmp_path):

    # Test with custom values for all keys
    indata = {
        "test_path": "~/custom_test_path",
        "repository_directory": "test_repo2",
        "model_type": VALID_MODELS[0],
        "repository_url": "https://github.com/ACCESS-NRI/access-om3-configs.git",
        "existing_branch": "main",
        "control_branch_name": "test_branch",
        "keep_uuid": True,
        "restart_path": tmp_path / "restart_path",
        "parent_experiment": tmp_path / "parent_path",
        "config_path": tmp_path / "config_path",
        "lab_path": tmp_path / "lab_path",
        "start_point": "abcd1234",
        "Perturbation_Experiment": True,
    }

    base = BaseExperiment(indata)

    assert base.indata is indata

    assert base.test_path == Path("~/custom_test_path").expanduser()
    assert base.repo_dir == "test_repo2"
    assert base.directory == (base.test_path / "test_repo2").resolve()
    assert base.model_type == VALID_MODELS[0]
    assert base.repository_url == "https://github.com/ACCESS-NRI/access-om3-configs.git"
    assert base.existing_branch == "main"
    assert base.control_branch_name == "test_branch"
    assert base.keep_uuid is True
    assert base.restart_path == tmp_path / "restart_path"
    assert base.parent_experiment == tmp_path / "parent_path"
    assert base.config_path == tmp_path / "config_path"
    assert base.lab_path == tmp_path / "lab_path"
    assert base.start_point == "abcd1234"
    assert base.perturbation_enabled is True
