import pytest
from conftest import DummyBranch, DummyIndex
import experiment_generator.perturbation_experiment as pert_exp
from experiment_generator.perturbation_experiment import ExperimentDefinition as ed
from experiment_generator.experiment_generator import VALID_MODELS


@pytest.fixture
def indata():
    return {
        "repository_directory": "test_repo",
        "control_branch_name": "control_branch",
        "keep_uuid": True,
        "model_type": VALID_MODELS[0],
    }


@pytest.fixture
def checkout_recorder(patch_git, monkeypatch):
    calls = []

    def _recorder(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(pert_exp, "checkout_branch", _recorder, raising=True)
    return calls


def test_manage_control_expt_without_control_warn_skip(tmp_repo_dir, indata, patch_git):
    """
    Test that manage_control_expt skips if control branch is not set.
    """
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    with pytest.warns(UserWarning):
        expt.manage_control_expt()

    assert patch_git.commits == []


def test_manage_perturb_expt_warns_no_perturbation_block(tmp_repo_dir, indata, patch_git):
    """
    Test that manage_perturb_expt raises a warning if no perturbation block is provided.
    """
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    with pytest.warns(UserWarning):
        expt.manage_perturb_expt()

    assert patch_git.commits == []


def test_collect_defs_warns_and_skips_block_without_branches(tmp_repo_dir, indata, patch_git):
    """
    Test that collect_defs warns and skips blocks without branches.
    """
    perturb_block = {
        "Parameter_block1": {
            "config.yaml": {"queue": "normal"},
            "ice_in": {"diagfreq": 720},
        }
    }

    expt = pert_exp.PerturbationExperiment(
        directory=tmp_repo_dir, indata={**indata, "Perturbation_Experiment": perturb_block}
    )

    with pytest.warns(UserWarning):
        expt._collect_experiment_definitions(perturb_block)

    assert patch_git.commits == []


def test_apply_updates_with_correct_updaters(tmp_repo_dir, patch_updaters, indata):
    (
        f90_recorder,
        payuconfig_recorder,
        nuopc_runconfig_recorder,
        mom6_input_recorder,
        nuopc_runseq_recorder,
        om2_forcing_recorder,
    ) = patch_updaters

    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    expt._apply_updates(
        {
            "ice_in": {"diagfreq": 720},
            "input.nml": {"MOM_input_nml": {"parameter_filename": "MOM_input"}},
            "config.yaml": {"queue": "express"},
            "nuopc.runseq": {"cpl_dt": 20},
            "nuopc.runconfig": {"ALLCOMP_attributes": {"ATM_model": "satm"}},
            "MOM_input": {"DT": 3600.0},
            "atmosphere/forcing.json": {
                "tas": {
                    "perturbations": [
                        {
                            "type": "scaling",
                            "dimension": "temporal",
                            "value": "test_data/temporal.RYF.rsds.1990_1991.nc",
                        }
                    ]
                }
            },
        }
    )

    assert f90_recorder.calls[0] == ("update_nml_params", {"diagfreq": 720}, "ice_in")
    assert f90_recorder.calls[1] == (
        "update_nml_params",
        {"MOM_input_nml": {"parameter_filename": "MOM_input"}},
        "input.nml",
    )
    assert payuconfig_recorder.calls[0] == ("update_config_params", {"queue": "express"}, "config.yaml")
    assert nuopc_runseq_recorder.calls[0] == ("update_nuopc_runseq", {"cpl_dt": 20}, "nuopc.runseq")
    assert nuopc_runconfig_recorder.calls[0] == (
        "update_runconfig_params",
        {"ALLCOMP_attributes": {"ATM_model": "satm"}},
        "nuopc.runconfig",
    )
    assert mom6_input_recorder.calls[0] == ("update_mom6_params", {"DT": 3600.0}, "MOM_input")
    assert om2_forcing_recorder.calls[0] == (
        "update_forcing_params",
        {
            "tas": {
                "perturbations": [
                    {"type": "scaling", "dimension": "temporal", "value": "test_data/temporal.RYF.rsds.1990_1991.nc"}
                ]
            }
        },
        "atmosphere/forcing.json",
    )


def test_manage_control_expt_applies_updates_and_commits(tmp_repo_dir, indata, patch_git):
    patch_git.repo.branches = [DummyBranch(indata["control_branch_name"])]
    patch_git.repo.index = DummyIndex(
        ["config.yaml", "ice_in", "MOM_input", "nuopc.runseq", "nuopc.runconfig", "atmosphere/forcing.json"]
    )

    control_block = {
        "config.yaml": {"queue": "express"},
        "ice_in": {"diagfreq": 720},
        "MOM_input": {"DT": 3600.0},
        "nuopc.runseq": {"cpl_dt": 20},
        "nuopc.runconfig": {"ALLCOMP_attributes": {"ATM_model": "satm"}},
        "atmosphere/forcing.json": {"tas": {"perturbations": [{"type": "REMOVE"}]}},
    }

    indata = {**indata, "Control_Experiment": control_block}
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    expt.manage_control_expt()

    assert len(patch_git.commits) == 1
    msg, files = patch_git.commits[0]
    assert files == ["config.yaml", "ice_in", "MOM_input", "nuopc.runseq", "nuopc.runconfig", "atmosphere/forcing.json"]
    assert "Updated control files" in msg


def test_manage_perturb_expt_creat_branches_applies_updates_and_commits(
    tmp_repo_dir, indata, patch_git, patch_updaters, checkout_recorder
):
    patch_git.repo.branches = []
    patch_git.repo.index = DummyIndex(["config.yaml", "ice_in"])

    perturb_block = {
        "Parameter_block1": {
            "branches": ["perturb_1", "perturb_2"],
            "config.yaml": {"queue": ["express", "expresssr"]},
            "ice_in": {"diagfreq": [360, 720]},
        }
    }

    expt = pert_exp.PerturbationExperiment(
        directory=tmp_repo_dir, indata={**indata, "Perturbation_Experiment": perturb_block}
    )

    f90_recorder, payuconfig_recorder, _, _, _, _ = patch_updaters

    expt.manage_perturb_expt()

    assert len(checkout_recorder) == 2
    assert checkout_recorder[0]["branch_name"] == "perturb_1"
    assert checkout_recorder[0]["is_new_branch"] is True
    assert checkout_recorder[1]["branch_name"] == "perturb_2"
    assert checkout_recorder[1]["is_new_branch"] is True

    # two commits (one per branch)
    assert len(patch_git.commits) == 2

    for msg, files in patch_git.commits:
        assert files == ["config.yaml", "ice_in"]
        assert "Updated perturbation files" in msg

    # Updaters receive run-specific params
    assert payuconfig_recorder.calls[0] == ("update_config_params", {"queue": "express"}, "config.yaml")
    assert payuconfig_recorder.calls[1] == ("update_config_params", {"queue": "expresssr"}, "config.yaml")
    assert f90_recorder.calls[0] == ("update_nml_params", {"diagfreq": 360}, "ice_in")
    assert f90_recorder.calls[1] == ("update_nml_params", {"diagfreq": 720}, "ice_in")


@pytest.mark.parametrize(
    "param_dict, indx, total, expected",
    [
        # broadcast single list value across branches
        ({"queue": ["normal"]}, 0, 2, {"queue": "normal"}),
        ({"queue": ["normal"]}, 1, 2, {"queue": "normal"}),
        # broadcast single plain value across branches
        ({"cpl_dt": 3600}, 0, 2, {"cpl_dt": 3600}),
        ({"cpl_dt": 3600}, 1, 2, {"cpl_dt": 3600}),
        # Two 1-layer nested dict for two branches
        ({"metadata": {"enable": [True, False]}}, 0, 2, {"metadata": {"enable": True}}),
        ({"metadata": {"enable": [True, False]}}, 1, 2, {"metadata": {"enable": False}}),
        # Two 2-layers nested dict for two branches
        ({"manifest": {"reproduce": {"exe": ["exe1", "exe2"]}}}, 0, 2, {"manifest": {"reproduce": {"exe": "exe1"}}}),
        ({"manifest": {"reproduce": {"exe": ["exe1", "exe2"]}}}, 1, 2, {"manifest": {"reproduce": {"exe": "exe2"}}}),
        # broadcast single nested dict for two branches
        ({"metadata": {"enable": [True]}}, 0, 2, {"metadata": {"enable": True}}),
        ({"metadata": {"enable": [True]}}, 1, 2, {"metadata": {"enable": True}}),
        # broadcast single 2-layers nested dict for two branches
        ({"manifest": {"reproduce": {"exe": ["exe1"]}}}, 0, 2, {"manifest": {"reproduce": {"exe": "exe1"}}}),
        ({"manifest": {"reproduce": {"exe": ["exe1"]}}}, 1, 2, {"manifest": {"reproduce": {"exe": "exe1"}}}),
        # list of lists - single one inner list: broadcast inner list
        ({"modules": {"use": [[["/g/data/vk83/modules"]]]}}, 0, 2, {"modules": {"use": [["/g/data/vk83/modules"]]}}),
        ({"modules": {"use": [[["/g/data/vk83/modules"]]]}}, 1, 2, {"modules": {"use": [["/g/data/vk83/modules"]]}}),
        # list of lists - single inner lists with 2 items: broadcast as above
        ({"modules": {"load": [[["moduleA"], ["moduleB"]]]}}, 0, 2, {"modules": {"load": [["moduleA"], ["moduleB"]]}}),
        ({"modules": {"load": [[["moduleA"], ["moduleB"]]]}}, 1, 2, {"modules": {"load": [["moduleA"], ["moduleB"]]}}),
        # list of lists - two inner lists: pick by index
        (
            {"modules": {"load": [[["moduleA"], ["moduleB"]], [["moduleC"], ["moduleD"]]]}},
            0,
            2,
            {"modules": {"load": [["moduleA"], ["moduleB"]]}},
        ),
        (
            {"modules": {"load": [[["moduleA"], ["moduleB"]], [["moduleC"], ["moduleD"]]]}},
            1,
            2,
            {"modules": {"load": [["moduleC"], ["moduleD"]]}},
        ),
        # _filter_value: _is_remove_str(x)
        ({"queue": "REMOVE"}, 0, 2, {"queue": "REMOVE"}),
        ({"queue": "REMOVE"}, 1, 2, {"queue": "REMOVE"}),
        ({"queue": ["REMOVE"]}, 0, 1, {"queue": "REMOVE"}),
        ({"queue": ["REMOVE"]}, 0, 2, {"queue": "REMOVE"}),
        # list of empty lists: collapse to empty dict
        ({"queue": [[]]}, 0, 2, {}),
        ({"queue": [[], {"keep": 1}]}, 1, 2, {"queue": {"keep": 1}}),
        ({"modules": {"child": {"a": [[], []]}}}, 0, 2, {}),
        ({"outer": [{"a": [[], []]}, {"b": [[], []]}]}, 0, 2, {}),
        # ({"platform": [{"nodesize": [104, 104]}, {"nodesize": [104, 104]}]}, 0, 2, {"platform": {"nodesize": 104}}),
        (
            {
                "diag_table": [
                    {"A": {"fields": [{"temp_branch1": {None}, "salt_branch1": {None}}, {"temp_branch2": {None}}]}}
                ]
            },
            1,
            2,
            {"diag_table": {"A": {"fields": {"temp_branch2": {None}}}}},
        ),
        (
            {"submodels": [[{"input": ["1.nc", "2.nc"]}, {"input": ["1.nc", "2.nc"]}]]},
            1,
            2,
            {"submodels": [{"input": "2.nc"}, {"input": "2.nc"}]},
        ),
        (
            {"submodels": [[{"input": ["1.nc", "2.nc"]}, {"input": ["3.nc", "4.nc"]}]]},
            1,
            2,
            {"submodels": [{"input": "2.nc"}, {"input": "4.nc"}]},
        ),
    ],
)
def test_extract_run_specific_params_rules(tmp_repo_dir, indata, param_dict, indx, total, expected):
    # param_dict is the value of a single file
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    result = expt._extract_run_specific_params(param_dict, indx, total)
    assert result == expected


def test_setup_branch_is_new_branch_false(tmp_repo_dir, indata, patch_git, checkout_recorder):
    patch_git.repo.branches = [DummyBranch("perturb_1")]
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    expt_def = ed(
        block_name="Parameter_block1",
        branch_name="perturb_1",
        file_params={},
    )

    expt._setup_branch(expt_def, patch_git.local_branches_dict())

    assert len(checkout_recorder) == 1
    call = checkout_recorder[0]
    assert call["branch_name"] == "perturb_1"
    assert call["is_new_branch"] is False
    assert call["start_point"] == "perturb_1"


def test_extract_run_specific_params_raises_on_invalid_list_length(tmp_repo_dir, indata):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    with pytest.raises(ValueError):
        # 2 items in list, but total_exps=3
        expt._extract_run_specific_params({"queue": ["normal", "express"]}, 0, 3)


def test_extract_run_specific_params_raises_on_invalid_outerlen(tmp_repo_dir, indata):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    with pytest.raises(ValueError):
        # outer list len 2, but total_exps=3
        expt._extract_run_specific_params({"modules": [["A"], ["B"]]}, 0, 3)


def test_extract_run_specific_params_raises_on_list_of_dicts_inconsistent_outer_len_total_exps(tmp_repo_dir, indata):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    with pytest.raises(ValueError):
        # outer list len 3, but total_exps=2
        expt._extract_run_specific_params(
            {
                "diag_table": [
                    {"A": {"fields": [{"temp_branch1": {None}}, {"temp_branch2": {None}}, {"temp_branch3": {None}}]}}
                ]
            },
            0,
            2,
        )
