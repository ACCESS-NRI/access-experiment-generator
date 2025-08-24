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
                        {"type": "REMOVE", "dimension": "temporal", "value": "test_data/temporal.RYF.rsds.1990_1991.nc"}
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
                    {"type": "REMOVE", "dimension": "temporal", "value": "test_data/temporal.RYF.rsds.1990_1991.nc"}
                ]
            }
        },
        "atmosphere/forcing.json",
    )


def test_manage_control_expt_applies_updates_and_commits(tmp_repo_dir, indata, patch_git):
    patch_git.repo.branches = [DummyBranch(indata["control_branch_name"])]
    patch_git.repo.index = DummyIndex(["config.yaml", "ice_in"])

    control_block = {
        "config.yaml": {"queue": "normal"},
        "ice_in": {"diagfreq": 720},
        "MOM_input": {"DT": 1800.0},
        "nuopc.runseq": {"cpl_dt": 3600},
        "nuopc.runconfig": {"ALLCOMP_attributes": {"ATM_model": "satm"}},
        "atmosphere/forcing.json": {"tas": {"perturbations": [{"type": "REMOVE"}]}},
    }

    indata = {**indata, "Control_Experiment": control_block}
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    expt.manage_control_expt()

    assert len(patch_git.commits) == 1
    msg, files = patch_git.commits[0]
    assert files == ["config.yaml", "ice_in"]
    assert "Updated control files" in msg


def test_manage_control_expt_without_control_warn_skip(tmp_repo_dir, indata, patch_git):
    """
    Test that manage_control_expt skips if control branch is not set.
    """
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)

    with pytest.warns(UserWarning):
        expt.manage_control_expt()

    assert patch_git.commits == []


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
        # nested dict
        ({"nested": {"param": ["value1", "value2"]}}, 0, 2, {"nested": {"param": "value1"}}),
        ({"nested": {"param": ["value1", "value2"]}}, 1, 2, {"nested": {"param": "value2"}}),
        # list of dicts: same value for all dicts
        ({"modules": [{"name": ["A", "B"]}, {"name": ["A", "B"]}]}, 0, 2, {"modules": {"name": "A"}}),
        ({"modules": [{"name": ["A", "B"]}, {"name": ["A", "B"]}]}, 1, 2, {"modules": {"name": "B"}}),
        # list of dicts: different values for each dict
        ({"modules": [{"name": ["A", "B"]}, {"name": ["C", "D"]}]}, 0, 2, {"modules": [{"name": "A"}, {"name": "C"}]}),
        ({"modules": [{"name": ["A", "B"]}, {"name": ["C", "D"]}]}, 1, 2, {"modules": [{"name": "B"}, {"name": "D"}]}),
        # pick by index when list length == total_exps
        ({"queue": ["normal", "express"]}, 0, 2, {"queue": "normal"}),
        ({"queue": ["normal", "express"]}, 1, 2, {"queue": "express"}),
        # list of lists - broadcast inner list when outer_len == 1
        ({"queue": [["normal"]]}, 0, 2, {"queue": ["normal"]}),
        ({"queue": [["normal"]]}, 1, 2, {"queue": ["normal"]}),
        # list of lists - pick by index when outer_len == total_exps
        ({"modules": [["A"], ["B"]]}, 0, 2, {"modules": ["A"]}),
        ({"modules": [["A"], ["B"]]}, 1, 2, {"modules": ["B"]}),
        # select None should return None (row in REMOVED)
        ({"modules": ["A", "REMOVE"]}, 0, 2, {"modules": "A"}),
        ({"modules": ["A", "REMOVE"]}, 1, 2, {"modules": None}),
        # scalar - broadcast across branches
        ({"cpl_dt": 3600}, 0, 2, {"cpl_dt": 3600}),
        ({"cpl_dt": 3600}, 1, 2, {"cpl_dt": 3600}),
    ],
)
def test_extract_run_specific_params_rules(tmp_repo_dir, indata, param_dict, indx, total, expected):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    result = expt._extract_run_specific_params(param_dict, indx, total)
    assert result == expected


def test_extract_run_specific_params_raises_on_invalid_list_length(tmp_repo_dir, indata):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    with pytest.raises(ValueError):
        expt._extract_run_specific_params({"queue": ["normal", "express"]}, 0, 3)


def test_extract_run_specific_params_raises_on_invalid_outerlen(tmp_repo_dir, indata):
    expt = pert_exp.PerturbationExperiment(directory=tmp_repo_dir, indata=indata)
    with pytest.raises(ValueError):
        expt._extract_run_specific_params({"modules": [["A"], ["B"]]}, 0, 3)


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


def test_setup_branch_is_new_branch_true(tmp_repo_dir, indata, patch_git, checkout_recorder):
    patch_git.repo.branches = []
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
    assert call["is_new_branch"] is True
    assert call["start_point"] == indata["control_branch_name"]
