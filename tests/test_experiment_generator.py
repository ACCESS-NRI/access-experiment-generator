import shutil
import pytest

from src.experiment_generator.experiment_generator import (
    ExperimentGenerator,
    VALID_MODELS,
)


def test_valid_model_type():
    """
    Test that the model type is valid and recognised by the ExperimentGenerator.
    """

    valid_data = {
        "model_type": VALID_MODELS[0],
        "repository_url": "repo",
        "repository_directory": "dir",
        "control_branch_name": "main",
    }

    valid = ExperimentGenerator(valid_data)
    valid._validate_model_type()

    invalid_data = {
        "model_type": "invalid_model",
        "repository_url": "repo",
        "repository_directory": "dir",
        "control_branch_name": "main",
    }

    invalid = ExperimentGenerator(invalid_data)
    with pytest.raises(ValueError) as exc:
        invalid._validate_model_type()

    error_message = str(exc.value)

    assert "either" in error_message
    assert str(VALID_MODELS) in error_message


def test_create_test_path(tmp_path, capsys):
    """
    _create_test_path should create the test directory if missing or warning if it exists.
    """

    test_path = tmp_path / "test_dir"

    indata = {
        "test_path": str(test_path),
        "repository_url": "repo",
        "repository_directory": "dir",
        "control_branch_name": "main",
    }

    new_path = ExperimentGenerator(indata)
    assert not new_path.test_path.exists()

    new_path._create_test_path()

    assert new_path.test_path.exists()
    assert new_path.test_path.is_dir()

    assert f"has been created" in capsys.readouterr().out

    new_path2 = ExperimentGenerator(indata)
    new_path2.test_path.mkdir(parents=True, exist_ok=True)

    assert new_path2.test_path.exists()
    new_path2._create_test_path()

    assert f"already exists" in capsys.readouterr().out


def test_clone_repository(tmp_path, monkeypatch):
    """
    _clone_repository should clone the repository if it doesn't exist.
    """

    indata = {
        "repository_url": "https://example.com/repo.git",
        "repository_directory": "test_repo",
        "control_branch_name": "test_branch",
        "existing_branch": "main",
        "model_type": VALID_MODELS[0],
    }

    generator = ExperimentGenerator(indata)

    clone = {
        "clone_called": False,
        "clone_kwargs": None,
    }

    def mock_clone(**kwargs):
        clone["clone_called"] = True
        clone["clone_kwargs"] = kwargs

    monkeypatch.setattr(
        "src.experiment_generator.experiment_generator.clone", mock_clone
    )

    # directory not exist now
    if generator.directory.exists():
        # remove it to ensure we can test cloning
        shutil.rmtree(generator.directory, ignore_errors=True)

    generator._clone_repository()
    assert clone["clone_called"] is True

    kwargs = clone["clone_kwargs"]
    assert kwargs["repository"] == generator.repository
    assert kwargs["directory"] == generator.directory
    assert kwargs["branch"] == generator.existing_branch
    assert kwargs["keep_uuid"] == generator.keep_uuid
    assert kwargs["model_type"] == generator.model_type
    assert kwargs["lab_path"] == generator.lab_path
    assert kwargs["new_branch_name"] == generator.control_branch_name
    assert kwargs["restart_path"] == generator.restart_path
    assert kwargs["parent_experiment"] == generator.parent_experiment
    assert kwargs["start_point"] == generator.start_point

    # directory exists now then skip cloning
    clone["clone_called"] = False

    generator.directory.mkdir(parents=True, exist_ok=True)
    generator._clone_repository()

    assert clone["clone_called"] is False


def test_run_control_optional_perturb(monkeypatch):
    """
    ExperimentGenerator should run control experiment and optionally perturb experiment.
    """

    # dummy class for PerturbationExperiment
    class DummyPerturbationExperiment:
        def __init__(self, directory, indata):
            self.directory = directory
            self.indata = indata

        def manage_control_expt(self):
            call["control"] = True

        def manage_perturb_expt(self):
            call["perturb"] = True

    monkeypatch.setattr(
        "src.experiment_generator.experiment_generator.PerturbationExperiment",
        DummyPerturbationExperiment,
    )

    indata1 = {
        "repository_url": "repo",
        "repository_directory": "test_repo",
        "control_branch_name": "main",
        "model_type": VALID_MODELS[0],
    }

    generator = ExperimentGenerator(indata1)

    call = {
        "control": False,
        "perturb": False,
    }

    # call control experiment only
    generator.run()

    assert call["control"] is True
    assert call["perturb"] is False

    call = {
        "control": False,
        "perturb": False,
    }

    indata2 = {
        "repository_url": "repo",
        "repository_directory": "test_repo",
        "control_branch_name": "main",
        "model_type": VALID_MODELS[0],
        "Perturbation_Experiment": {"k": "v"},
    }

    generator2 = ExperimentGenerator(indata2)

    # call perturbation experiment as well
    generator2.run()

    assert call["control"] is True
    assert call["perturb"] is True
