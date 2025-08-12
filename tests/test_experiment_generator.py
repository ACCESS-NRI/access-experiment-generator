import pytest
import sys
from experiment_generator.experiment_generator import ExperimentGenerator as eg, VALID_MODELS


def test_validate_valid_and_invalid_model_types():
    indata = {
        "model_type": VALID_MODELS[0],
        "repository_directory": "test_repo",
    }

    val_model = eg(indata)
    val_model._validate_model_type()

    indata2 = {
        "model_type": "invalid_model",
        "repository_directory": "test_repo2",
    }
    inval_model = eg(indata2)
    with pytest.raises(ValueError) as exc_info:
        inval_model._validate_model_type()
    assert "either" in str(exc_info.value)


def test_create_test_path_when_not_exists(tmp_path, capsys):
    test_path = tmp_path / "custom_path"
    indata = {
        "repository_directory": "test_repo",
        "test_path": test_path,
    }

    exp_gen = eg(indata)
    assert not test_path.exists()
    exp_gen._create_test_path()
    captured_output = capsys.readouterr()
    assert test_path.exists()
    assert "-- Test directory" in captured_output.out and "has been created!" in captured_output.out


def test_create_test_path_when_exists(tmp_path, capsys):
    test_path = tmp_path / "existing_path"
    test_path.mkdir(parents=True, exist_ok=True)
    indata = {
        "repository_directory": "test_repo",
        "test_path": test_path,
    }

    exp_gen = eg(indata)
    assert test_path.exists()
    exp_gen._create_test_path()
    captured_output = capsys.readouterr()
    assert "-- Test directory" in captured_output.out and "already exists!" in captured_output.out


def test_clone_repository_when_exists(tmp_path, capsys, monkeypatch):
    indata = {
        "test_path": tmp_path / "custom_test_path",
        "repository_directory": "test_repo",
        "model_type": VALID_MODELS[0],
        "repository_url": "https://github.com/ACCESS-NRI/access-om3-configs.git",
        "control_branch_name": "test_branch",
        "keep_uuid": True,
        "start_point": "abcd1234",
    }

    exp_gen = eg(indata)
    # ensure the directory exists
    exp_gen.directory.mkdir(parents=True, exist_ok=True)

    called_clone = {"called": False}

    def dummy_clone(*args, **kwargs):
        called_clone["called"] = True

    monkeypatch.setattr(sys.modules[exp_gen.__module__], "clone", dummy_clone)

    exp_gen._clone_repository()
    captured_output = capsys.readouterr()
    # Because the directory already exists, clone should not be called
    assert called_clone["called"] is False
    assert "not cloning" in captured_output.out and "already exists" in captured_output.out


def test_clone_repository_when_not_exists(tmp_path, capsys, monkeypatch):
    indata = {
        "test_path": tmp_path / "custom_test_path",
        "repository_directory": "test_repo",
        "model_type": VALID_MODELS[0],
        "repository_url": "https://github.com/ACCESS-NRI/access-om3-configs.git",
        "control_branch_name": "test_branch",
        "keep_uuid": True,
        "start_point": "abcd1234",
    }

    exp_gen = eg(indata)

    if exp_gen.directory.exists():
        exp_gen.directory.rmdir()

    called_clone = {}

    def dummy_clone(*args, **kwargs):
        called_clone.update(kwargs)

    monkeypatch.setattr(sys.modules[exp_gen.__module__], "clone", dummy_clone)

    exp_gen._clone_repository()
    # clone should be called with all expected input keys
    assert called_clone.get("repository") == indata["repository_url"]
    assert called_clone.get("directory") == exp_gen.directory
    assert called_clone.get("branch") == exp_gen.existing_branch
    assert called_clone.get("keep_uuid") == exp_gen.keep_uuid
    assert called_clone.get("model_type") == exp_gen.model_type
    assert called_clone.get("config_path") == exp_gen.config_path
    assert called_clone.get("lab_path") == exp_gen.lab_path
    assert called_clone.get("new_branch_name") == exp_gen.control_branch_name
    assert called_clone.get("restart_path") == exp_gen.restart_path
    assert called_clone.get("parent_experiment") == exp_gen.parent_experiment
    assert called_clone.get("start_point") == exp_gen.start_point


def test_run_sequence_but_without_perturbation(tmp_path, monkeypatch):
    indata = {
        "test_path": tmp_path / "custom_test_path",
        "repository_directory": "test_repo",
        "model_type": VALID_MODELS[0],
        "repository_url": "https://github.com/ACCESS-NRI/access-om3-configs.git",
        "control_branch_name": "test_branch",
        "keep_uuid": True,
        "start_point": "abcd1234",
        "Perturbation_Experiment": False,
    }

    exp_gen = eg(indata)

    called_order = []

    # "self" has to be there because of replacing a class method
    def dummy_create_test_path(self):
        called_order.append("create")

    def dummy_validate_model_type(self):
        called_order.append("validate")

    def dummy_clone_repository(self):
        called_order.append("clone")

    monkeypatch.setattr(eg, "_create_test_path", dummy_create_test_path, raising=True)
    monkeypatch.setattr(eg, "_validate_model_type", dummy_validate_model_type, raising=True)
    monkeypatch.setattr(eg, "_clone_repository", dummy_clone_repository, raising=True)

    class DummyPerturbationExperiment:
        def __init__(self, directory, indata):
            DummyPerturbationExperiment.called_indata = indata

        def manage_control_expt(self):
            DummyPerturbationExperiment.control_called = True

        def manage_perturb_expt(self):
            DummyPerturbationExperiment.perturb_called = True

    monkeypatch.setattr(sys.modules[exp_gen.__module__], "PerturbationExperiment", DummyPerturbationExperiment)

    # run it
    exp_gen.run()

    # test run sequence
    assert called_order == [
        "create",
        "validate",
        "clone",
    ]

    assert getattr(DummyPerturbationExperiment, "control_called", False) is True
    assert not hasattr(DummyPerturbationExperiment, "perturb_called")


def test_run_with_perturbation(monkeypatch):
    indata = {
        "model_type": VALID_MODELS[0],
        "repository_directory": "test_repo",
        "Perturbation_Experiment": True,
    }

    exp_gen = eg(indata)
    called_order = []

    # "self" has to be there because of replacing a class method
    def dummy_create_test_path(self):
        called_order.append("create")

    def dummy_validate_model_type(self):
        called_order.append("validate")

    def dummy_clone_repository(self):
        called_order.append("clone")

    monkeypatch.setattr(eg, "_create_test_path", dummy_create_test_path, raising=True)
    monkeypatch.setattr(eg, "_validate_model_type", dummy_validate_model_type, raising=True)
    monkeypatch.setattr(eg, "_clone_repository", dummy_clone_repository, raising=True)

    class DummyPerturbationExperiment:
        def __init__(self, directory, indata):
            DummyPerturbationExperiment.called_indata = indata

        def manage_control_expt(self):
            DummyPerturbationExperiment.control_called = True

        def manage_perturb_expt(self):
            DummyPerturbationExperiment.perturb_called = True

    monkeypatch.setattr(sys.modules[exp_gen.__module__], "PerturbationExperiment", DummyPerturbationExperiment)

    # run it
    exp_gen.run()

    # test run sequence
    assert called_order == [
        "create",
        "validate",
        "clone",
    ]

    assert getattr(DummyPerturbationExperiment, "control_called", False) is True
    assert getattr(DummyPerturbationExperiment, "perturb_called", False) is True
