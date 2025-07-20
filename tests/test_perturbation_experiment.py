import sys
import pytest
from pathlib import Path
from conftest import DummyBranch
from experiment_generator.perturbation_experiment import PerturbationExperiment as pert_exp
from experiment_generator.perturbation_experiment import ExperimentDefinition as ed


def test_apply_updates_call_correct_updater(tmp_path, monkeypatch):
    indata = {
        "repository_directory": "test_repo",
        "Perturbation_Experiment": True,
    }
    expt = pert_exp(tmp_path, indata)

    called = {}

    def dummy_nml(params, filename):
        called["f90"] = (params, filename)

    def dummy_config(params, filename):
        called["yaml"] = (params, filename)

    def dummy_runconfig(params, filename):
        called["runconfig"] = (params, filename)

    def dummy_mom6(params, filename):
        called["mom_input"] = (params, filename)

    def dummy_nuopc_runseq(params, filename):
        called["runseq"] = (params, filename)

    monkeypatch.setattr(expt.f90namelistupdater, "update_nml_params", dummy_nml, raising=True)
    monkeypatch.setattr(expt.configupdater, "update_config_params", dummy_config, raising=True)
    monkeypatch.setattr(expt.nuopcrunconfigupdater, "update_runconfig_params", dummy_runconfig, raising=True)
    monkeypatch.setattr(expt.mom6inputupdater, "update_mom6_params", dummy_mom6, raising=True)
    monkeypatch.setattr(expt.nuopcrunsequpdater, "update_nuopc_runseq", dummy_nuopc_runseq, raising=True)

    expt._apply_updates({"ice_in": {"shortwave_nml": {"ahmax": 0.1}}})
    assert "f90" in called and called["f90"][1] == "ice_in"
    called.clear()

    expt._apply_updates({"input.nml": {"diag_manager_nml": {"max_axes": 100}}})
    assert "f90" in called and called["f90"][1] == "input.nml"
    called.clear()

    expt._apply_updates({"config.yaml": {"queue": "normal"}})
    assert "yaml" in called and called["yaml"][1] == "config.yaml"
    called.clear()

    expt._apply_updates({"nuopc.runconfig": {"DRIVER_attributes": {"pio_debug_level": 0}}})
    assert "runconfig" in called and called["runconfig"][1] == "nuopc.runconfig"

    expt._apply_updates({"MOM_input": {"DT": 900.0}})
    assert "mom_input" in called and called["mom_input"][1] == "MOM_input"
    called.clear()

    expt._apply_updates({"nuopc.runseq": {"cpl_dt": 900.0}})
    assert "runseq" in called and called["runseq"][1] == "nuopc.runseq"
    called.clear()


def test_manage_control_expt_calls_apply_updates(tmp_path, monkeypatch):
    repo_dir = tmp_path / "test_repo"

    rel_path = Path("ice/cice_in.nml")
    (repo_dir / rel_path).parent.mkdir(parents=True, exist_ok=True)
    (repo_dir / rel_path).write_text("&nml\n/")

    control_yaml = {str(rel_path): {"shortwave_nml": {"ahmax": 0.1}}}

    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
        "Control_Experiment": control_yaml,
    }

    expt = pert_exp(repo_dir, indata)

    called = {}

    def dummy_apply(params, filename):
        called["params"] = params
        called["filename"] = filename

    monkeypatch.setattr(expt.f90namelistupdater, "update_nml_params", dummy_apply)

    expt.manage_control_expt()

    assert called, "_apply_updates is not applied"
    assert called["params"] == control_yaml[str(rel_path)]
    assert called["filename"] == "ice/cice_in.nml"


def test_manage_control_expt_no_control_data(tmp_path):
    indata = {
        "repository_directory": "test_repo",
    }
    expt = pert_exp(tmp_path, indata)
    with pytest.raises(ValueError):
        expt.manage_control_expt()


def test_manage_control_expt_updates_and_commits(tmp_path, monkeypatch):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # files in skip directories and dummy files
    (repo_dir / ".git").mkdir()
    (repo_dir / ".git" / "dummy_file").write_text("dummy")
    (repo_dir / ".github").mkdir()
    (repo_dir / ".github" / "dummy_file").write_text("dummy")
    (repo_dir / "testing").mkdir()
    (repo_dir / "testing" / "dummy_file").write_text("dummy")
    (repo_dir / "docs").mkdir()
    (repo_dir / "docs" / "dummy_file").write_text("dummy")

    # normal files
    dummyfile1 = repo_dir / "dummyfile1"
    dummyfile2 = repo_dir / "sub_dir" / "dummyfile2"
    dummyfile2.parent.mkdir()
    dummyfile1.write_text("dummy")
    dummyfile2.write_text("dummy")

    # prepare control experiment matching dummyfile1 and sub_dir/dummyfile2
    control_data = {
        "dummyfile1": {
            "param1": 1,
            "param2": 2,
        },
        "sub_dir/dummyfile2": {
            "param3": 3,
        },
    }

    indata = {"repository_directory": repo_dir.name, "control_branch_name": "ctrl", "Control_Experiment": control_data}

    expt = pert_exp(repo_dir, indata)

    # monkeypatch ._apply_updates() to track calls and simulate git changes
    applied = []

    def dummy_apply(self, file_params):
        applied.append(list(file_params.keys())[0])
        self.gitrepository.repo.index._changed_files = [list(file_params.keys())]

    monkeypatch.setattr(pert_exp, "_apply_updates", dummy_apply, raising=True)

    expt.manage_control_expt()


def test_manage_control_expt_existing_branch_checkout(tmp_path, monkeypatch):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    control_data = {
        "dummyfile1": {
            "param1": 1,
            "param2": 2,
        },
        "sub_dir/dummyfile2": {
            "param3": 3,
        },
    }

    indata = {"repository_directory": repo_dir.name, "control_branch_name": "ctrl", "Control_Experiment": control_data}

    expt = pert_exp(repo_dir, indata)

    expt.gitrepository.repo.branches = []

    expt.gitrepository.repo.branches.append(DummyBranch("ctrl"))

    # patch another checkout_branch for this specific test
    called = {"**kwargs": None}

    def dummy_checkout_branch(**kwargs):
        called["kwargs"] = kwargs

    monkeypatch.setattr(sys.modules[pert_exp.__module__], "checkout_branch", dummy_checkout_branch)
    monkeypatch.setattr(pert_exp, "_apply_updates", lambda self, file_params: None, raising=True)

    expt.manage_control_expt()


def test_manage_perturb_expt_no_data(tmp_path):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }

    expt = pert_exp(repo_dir, indata)
    with pytest.warns(UserWarning):
        expt.manage_perturb_expt()


def test_manage_perturb_expt_applies_all_steps(tmp_path, monkeypatch):
    perturb_data = {"dummy": 1}

    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
        "Perturbation_Experiment": perturb_data,
    }

    expt = pert_exp(repo_dir, indata)

    definitions = [
        ed(block_name="Parameter_block1", branch_name="perturb_1", file_params={"file1": {"p": 1}}),
        ed(block_name="Parameter_block1", branch_name="perturb_2", file_params={"file2": {"q": 2}}),
    ]

    monkeypatch.setattr(pert_exp, "_collect_experiment_definitions", lambda self, namelists: definitions, raising=True)

    # track _setup_branch and _apply_updates
    setup_called = []

    def dummy_setup_branch(self, expt_def, local_branches):
        setup_called.append(expt_def.branch_name)

    monkeypatch.setattr(pert_exp, "_setup_branch", dummy_setup_branch, raising=True)

    applied = []

    def dummy_apply(self, file_params):
        applied.append(list(file_params.keys()))
        self.gitrepository.repo.index._changed_files = [list(file_params.keys())]

    monkeypatch.setattr(pert_exp, "_apply_updates", dummy_apply, raising=True)

    expt.manage_perturb_expt()

    assert setup_called == ["perturb_1", "perturb_2"]
    assert any("file1" in files for files in applied) and any("file2" in files for files in applied)

    commits = expt.gitrepository.commits
    assert len(commits) == 2
    for message, files in commits:
        assert "Updated perturbation files:" in message


def test_setup_branch_existing_and_new(tmp_path, monkeypatch):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }
    expt = pert_exp(repo_dir, indata)

    expt_def = ed(block_name="Parameter_block1", branch_name="perturb_1", file_params={})

    # if branch already exists
    expt.gitrepository.repo.branches = [type("Parameter_block1", (), {"name": "perturb_1"})()]
    called = {}

    def dummy_checkout_branch(**kwargs):
        called["kwargs"] = kwargs

    monkeypatch.setattr(sys.modules[pert_exp.__module__], "checkout_branch", dummy_checkout_branch)
    expt._setup_branch(expt_def, expt.gitrepository.local_branches_dict())

    assert called["kwargs"].get("branch_name") == "perturb_1"
    assert called["kwargs"].get("is_new_branch") is False
    called.clear()

    # if no branch exists
    expt.gitrepository.repo.branches = []
    expt._setup_branch(expt_def, expt.gitrepository.local_branches_dict())
    assert called["kwargs"].get("branch_name") == "perturb_1"
    assert called["kwargs"].get("start_point") == expt.control_branch_name
    assert called["kwargs"].get("is_new_branch") is True


def test_collect_experiment_definitions_multiple_eds(tmp_path):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }
    expt = pert_exp(repo_dir, indata)

    # Perturbation input with 2 branches and param lists
    namelists = {
        "Parameter_block1": {
            "Parameter_block1_branches": ["perturb_1", "perturb_2"],
            "config.yaml": {"queue": ["normal", "normalsr"], "jobfs": [10, 20]},
        }
    }
    result = expt._collect_experiment_definitions(namelists)

    assert len(result) == 2, "Expected 2 branches!"
    branch_names = [res.branch_name for res in result]
    assert ["perturb_1", "perturb_2"] == branch_names

    defn1 = next(d for d in result if d.branch_name == "perturb_1")
    defn2 = next(d for d in result if d.branch_name == "perturb_2")
    expected_file_params1 = {"config.yaml": {"queue": "normal", "jobfs": 10}}
    expected_file_params2 = {"config.yaml": {"queue": "normalsr", "jobfs": 20}}
    assert defn1.file_params == expected_file_params1
    assert defn2.file_params == expected_file_params2


def test_collect_experiment_definitions_missing_branches_suffix(tmp_path):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }
    expt = pert_exp(repo_dir, indata)

    namelists = {"Parameter_block1": {"Parameter_block1_aaa": "perturb_1"}}
    with pytest.warns(UserWarning):
        result = expt._collect_experiment_definitions(namelists)
    assert result == []


def test_extract_run_specific_params_scalar_and_list_and_nested_dict(tmp_path):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }
    expt = pert_exp(repo_dir, indata)
    # if scalar, string, bools, etc so return as is
    nested = {"val": 5}
    res = expt._extract_run_specific_params(nested, indx=0, total_exps=1)
    assert res == {"val": 5}

    nested = {"val": True}
    res = expt._extract_run_specific_params(nested, indx=0, total_exps=1)
    assert res == {"val": True}

    nested = {"val": "dummy"}
    res = expt._extract_run_specific_params(nested, indx=0, total_exps=1)
    assert res == {"val": "dummy"}

    # if it has one element or all elements are identical, broadcast that element to total_exps
    # even if the length of total_exps is greater than nested_list.
    nested_list = {"val": [5, 5]}
    res0 = expt._extract_run_specific_params(nested_list, indx=0, total_exps=3)
    res1 = expt._extract_run_specific_params(nested_list, indx=1, total_exps=3)
    res2 = expt._extract_run_specific_params(nested_list, indx=2, total_exps=3)
    assert res0 == {"val": 5} and res1 == {"val": 5} and res2 == {"val": 5}

    # if distinct values and lengths are not the same as total_exps
    nested_list = {"val": [5, 6]}
    with pytest.raises(ValueError):
        expt._extract_run_specific_params(nested_list, indx=0, total_exps=3)

    # distinct values should pick index-specific value
    nested_list2 = {"val": [5, 6]}
    res0 = expt._extract_run_specific_params(nested_list2, indx=0, total_exps=2)
    res1 = expt._extract_run_specific_params(nested_list2, indx=1, total_exps=2)
    assert res0 == {"val": 5} and res1 == {"val": 6}

    # nested dict
    nested = {"dct": {"val": 5}}
    res = expt._extract_run_specific_params(nested, indx=0, total_exps=1)
    assert res == {"dct": {"val": 5}}


def test_extract_run_specific_params_list_of_lists_and_dicts(tmp_path):
    repo_dir = tmp_path / "test_repo"
    indata = {
        "repository_directory": repo_dir.name,
        "control_branch_name": "ctrl",
    }
    expt = pert_exp(repo_dir, indata)
    # list of lists where each inner list has one element (broadcast each inner element)
    nested = {"arr": [[1], [2], [3]]}
    res0 = expt._extract_run_specific_params(nested, indx=0, total_exps=3)
    res1 = expt._extract_run_specific_params(nested, indx=1, total_exps=3)
    res2 = expt._extract_run_specific_params(nested, indx=2, total_exps=3)
    expected_list = [1, 2, 3]
    assert res0["arr"] == expected_list and res1["arr"] == expected_list and res2["arr"] == expected_list

    # list of lists where each inner list has length equal to total_exps
    # select per index, total_exps= 2
    nested2 = {"arr": [[1, 2], [3, 4]]}
    res0 = expt._extract_run_specific_params(nested2, indx=0, total_exps=2)
    res1 = expt._extract_run_specific_params(nested2, indx=1, total_exps=2)
    assert res0["arr"] == [1, 3] and res1["arr"] == [2, 4]

    # List of lists with mismatched length should raise ValueError
    nested3 = {"arr": [[1, 2, 3], [4, 5]]}
    with pytest.raises(ValueError):
        expt._extract_run_specific_params(nested3, indx=0, total_exps=3)

    # list of dicts where each dict yields identical result -> collapsed to single dict
    list_of_dicts = {"lst": [{"p": [1, 2]}, {"p": [1, 2]}]}
    res0 = expt._extract_run_specific_params(list_of_dicts, indx=0, total_exps=2)
    res1 = expt._extract_run_specific_params(list_of_dicts, indx=1, total_exps=2)
    assert res0["lst"] == {"p": 1} and res1["lst"] == {"p": 2}

    # list of dicts with differing keys hence result remains a list of dicts per element
    list_of_dicts2 = {"lst": [{"p": [1, 2]}, {"q": [3, 4]}]}
    res0 = expt._extract_run_specific_params(list_of_dicts2, indx=0, total_exps=2)
    res1 = expt._extract_run_specific_params(list_of_dicts2, indx=1, total_exps=2)
    assert isinstance(res0["lst"], list) and isinstance(res1["lst"], list)
    assert res0["lst"][0] == {"p": 1} and res0["lst"][1] == {"q": 3}
    assert res1["lst"][0] == {"p": 2} and res1["lst"][1] == {"q": 4}
