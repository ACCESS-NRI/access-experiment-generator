import pytest
from pathlib import Path

from experiment_generator.experiment_generator import ExperimentGenerator as eg, VALID_MODELS
import experiment_generator.experiment_generator as exp_gen


@pytest.fixture
def base_indata(tmp_path):
    return {
        "test_path": str(tmp_path),
        "repository_url": "https://github.com/ACCESS-NRI/access-om3-configs.git",
        "repository_directory": "test_repo",
        "model_type": "access-om3",
        "existing_branch": "main",
        "control_branch_name": "test_branch",
        "keep_uuid": True,
        "restart_path": None,
        "parent_experiment": None,
        "config_path": None,
        "lab_path": None,
        "start_point": "abcd1234",
        "Perturbation_Experiment": False,
    }


@pytest.fixture
def clone_recorder(monkeypatch):
    calls = []

    def dummy_clone(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(exp_gen, "clone", dummy_clone, raising=True)
    return calls


@pytest.fixture
def pert_exp_recorder(monkeypatch):
    created = []

    class DummyPerturbationExperiment:
        def __init__(self, directory, indata):
            self.directory = directory
            self.indata = indata
            self.calls = []
            created.append(self)

        def manage_control_expt(self):
            self.calls.append("manage_control_expt")

        def manage_perturb_expt(self):
            self.calls.append("manage_perturb_expt")

    monkeypatch.setattr(exp_gen, "PerturbationExperiment", DummyPerturbationExperiment, raising=True)

    return created


def test_validate_model_type_valid(base_indata):
    for x in VALID_MODELS:
        obj_eg = eg(dict(base_indata, model_type=x))
        obj_eg._validate_model_type()


def test_validate_model_type_invalid(base_indata):
    obj_eg = eg(dict(base_indata, model_type="invalid-model"))
    with pytest.raises(ValueError) as e:
        obj_eg._validate_model_type()
    res = str(e.value)
    assert "invalid-model must be either" in res


def test_create_test_path(tmp_path, base_indata, capsys):
    new_path = tmp_path / "test_create_path"
    obj_eg = eg(dict(base_indata, test_path=str(new_path)))
    assert not new_path.exists()

    obj_eg._create_test_path()
    assert new_path.exists()

    out = capsys.readouterr().out
    assert f"-- Test directory {new_path} has been created!" in out


def test_create_test_path_skip_if_exists(tmp_path, base_indata, capsys):
    existing_path = tmp_path / "existing_test_path"
    existing_path.mkdir()

    obj_eg = eg(dict(base_indata, test_path=str(existing_path)))
    obj_eg._create_test_path()

    out = capsys.readouterr().out
    assert f"-- Test directory {existing_path} already exists!" in out


def test_clone_repository_skip_if_exists(tmp_path, base_indata, clone_recorder):
    target_path = (Path(base_indata["test_path"]) / base_indata["repository_directory"]).resolve()
    target_path.mkdir(parents=True, exist_ok=True)
    obj_eg = eg(base_indata)

    obj_eg._clone_repository()
    assert clone_recorder == []


def test_clone_repository_run_if_not_exists(tmp_path, base_indata, clone_recorder):
    target_path = (Path(base_indata["test_path"]) / base_indata["repository_directory"]).resolve()
    obj_eg = eg(base_indata)
    assert not target_path.exists()

    obj_eg._clone_repository()
    assert len(clone_recorder) == 1
    call = clone_recorder[0]

    assert call["repository"] == base_indata["repository_url"]
    assert call["directory"] == target_path
    assert call["branch"] == base_indata["existing_branch"]
    assert call["keep_uuid"] == base_indata["keep_uuid"]
    assert call["model_type"] == base_indata["model_type"]
    assert call["config_path"] == base_indata["config_path"]
    assert call["lab_path"] == base_indata["lab_path"]
    assert call["new_branch_name"] == base_indata["control_branch_name"]
    assert call["restart_path"] == base_indata["restart_path"]
    assert call["parent_experiment"] == base_indata["parent_experiment"]
    assert call["start_point"] == base_indata["start_point"]


def test_run_without_perturbation(tmp_path, base_indata, clone_recorder, pert_exp_recorder):
    obj_eg = eg(base_indata)
    obj_eg.run()

    assert len(clone_recorder) == 1
    assert len(pert_exp_recorder) == 1
    pert_exp = pert_exp_recorder[0]
    expected_dir = (Path(base_indata["test_path"]) / base_indata["repository_directory"]).resolve()
    assert pert_exp.directory == expected_dir
    assert pert_exp.indata is base_indata

    assert "manage_control_expt" in pert_exp.calls
    assert "manage_perturb_expt" not in pert_exp.calls


def test_run_with_perturbation(tmp_path, base_indata, clone_recorder, pert_exp_recorder):
    obj_eg = eg(dict(base_indata, Perturbation_Experiment=True))
    obj_eg.run()

    assert len(clone_recorder) == 1
    assert len(pert_exp_recorder) == 1
    pert_exp = pert_exp_recorder[0]
    expected_dir = (Path(base_indata["test_path"]) / base_indata["repository_directory"]).resolve()
    assert pert_exp.directory == expected_dir
    assert pert_exp.indata is obj_eg.indata

    assert "manage_control_expt" in pert_exp.calls
    assert "manage_perturb_expt" in pert_exp.calls
