"""
Tests for `use_worktrees`, with a real git repository and the real file updaters.

Payu's checkout is replaced by its git part only (create or check out the branch), since the
Laboratory, metadata and symlinks need a Payu model setup that these tests do not have.
"""

import shutil
from pathlib import Path

import f90nml
import git
import pytest
from payu.git_utils import GitRepository

import experiment_generator.perturbation_experiment as pert_exp
from experiment_generator.config_updater import ConfigUpdater
from experiment_generator.f90nml_updater import F90NamelistUpdater
from experiment_generator.tmp_parser.yaml_config import read_yaml

REPO_DIR = "test_repo"
CONTROL_BRANCH = "ctrl"


@pytest.fixture
def test_path(tmp_path: Path) -> Path:
    """
    A test_path holding a control directory on the control branch.
    """
    control_directory = tmp_path / REPO_DIR
    repo = git.Repo.init(control_directory, initial_branch="main")
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")
        config.set_value("commit", "gpgsign", "false")

    (control_directory / "config.yaml").write_text(f"queue: normal\njobname: {REPO_DIR}\n")
    (control_directory / "ice_in").write_text("&setup_nml\n  diagfreq = 960\n/\n")
    repo.index.add(["config.yaml", "ice_in"])
    repo.index.commit("Initial commit")
    repo.create_head(CONTROL_BRANCH).checkout()

    return tmp_path


@pytest.fixture
def checkout_calls(patch_git, patch_updaters, monkeypatch) -> list[dict]:
    """
    Use payu's real GitRepository and the real file updaters that conftest stubs for every test,
    and a checkout that only does the git part of payu's.
    """
    calls = []

    def fake_checkout_branch(**kwargs):
        control_path = kwargs.get("control_path") or Path(kwargs["config_path"]).parent
        # payu reads part of the configuration from the working directory
        assert Path.cwd() == Path(control_path).resolve()
        GitRepository(control_path).checkout_branch(
            kwargs["branch_name"], kwargs["is_new_branch"], kwargs.get("start_point")
        )
        calls.append(kwargs)

    monkeypatch.setattr(pert_exp, "GitRepository", GitRepository)
    monkeypatch.setattr(pert_exp, "ConfigUpdater", ConfigUpdater)
    monkeypatch.setattr(pert_exp, "F90NamelistUpdater", F90NamelistUpdater)
    monkeypatch.setattr(pert_exp, "checkout_branch", fake_checkout_branch)
    return calls


def make_indata(test_path: Path, branches: list[str], use_worktrees: bool = True) -> dict:
    return {
        "test_path": str(test_path),
        "repository_directory": REPO_DIR,
        "control_branch_name": CONTROL_BRANCH,
        "keep_uuid": True,
        "use_worktrees": use_worktrees,
        "Perturbation_Experiment": {
            "Parameter_block1": {
                "branches": branches,
                "config.yaml": {"queue": ["express", "expresssr"][: len(branches)]},
                "ice_in": {"setup_nml": {"diagfreq": [360, 720][: len(branches)]}},
            }
        },
    }


def generate(test_path: Path, branches: list[str], use_worktrees: bool = True) -> None:
    """
    Run the perturbation step as a fresh generator run would.
    """
    expt = pert_exp.PerturbationExperiment(test_path / REPO_DIR, make_indata(test_path, branches, use_worktrees))
    expt.manage_perturb_expt()


def branch_heads(test_path: Path) -> dict[str, str]:
    return {head.name: head.commit.hexsha for head in git.Repo(test_path / REPO_DIR).heads}


def test_new_branches_get_their_own_worktree(test_path, checkout_calls, capsys):
    control_repo = git.Repo(test_path / REPO_DIR)
    control_commit = control_repo.head.commit.hexsha

    generate(test_path, ["perturb_1", "perturb_2"])

    for branch, queue, diagfreq in [("perturb_1", "express", 360), ("perturb_2", "expresssr", 720)]:
        directory = test_path / branch / REPO_DIR
        repo = git.Repo(directory)
        assert repo.active_branch.name == branch
        assert not repo.is_dirty()
        assert repo.head.commit.message.startswith("Updated perturbation files")
        assert repo.head.commit.parents[0].hexsha == control_commit

        config = read_yaml(directory / "config.yaml")
        assert config["queue"] == queue
        assert config["jobname"] == REPO_DIR
        assert f90nml.read(directory / "ice_in")["setup_nml"]["diagfreq"] == diagfreq

    # payu created each branch from the control branch, inside its worktree
    assert [(c["branch_name"], c["is_new_branch"], c["start_point"]) for c in checkout_calls] == [
        ("perturb_1", True, CONTROL_BRANCH),
        ("perturb_2", True, CONTROL_BRANCH),
    ]
    assert [c["control_path"] for c in checkout_calls] == [
        test_path / "perturb_1" / REPO_DIR,
        test_path / "perturb_2" / REPO_DIR,
    ]

    # the control directory is untouched, apart from the untracked REMOVE state store
    assert control_repo.active_branch.name == CONTROL_BRANCH
    assert control_repo.head.commit.hexsha == control_commit
    assert not control_repo.is_dirty(untracked_files=False)

    assert "Perturbation experiment directories" in capsys.readouterr().out


def test_rerun_reuses_worktrees_without_new_commits(test_path, checkout_calls):
    generate(test_path, ["perturb_1", "perturb_2"])
    heads = branch_heads(test_path)
    checkout_calls.clear()

    generate(test_path, ["perturb_1", "perturb_2"])

    assert branch_heads(test_path) == heads
    assert [(c["branch_name"], c["is_new_branch"], c["control_path"]) for c in checkout_calls] == [
        ("perturb_1", False, test_path / "perturb_1" / REPO_DIR),
        ("perturb_2", False, test_path / "perturb_2" / REPO_DIR),
    ]


def test_deleted_worktree_is_recreated(test_path, checkout_calls):
    generate(test_path, ["perturb_1", "perturb_2"])
    heads = branch_heads(test_path)
    shutil.rmtree(test_path / "perturb_1")

    generate(test_path, ["perturb_1", "perturb_2"])

    assert git.Repo(test_path / "perturb_1" / REPO_DIR).active_branch.name == "perturb_1"
    assert branch_heads(test_path) == heads


def test_branches_from_a_run_without_worktrees_are_moved_to_worktrees(test_path, checkout_calls):
    generate(test_path, ["perturb_1", "perturb_2"], use_worktrees=False)
    control_repo = git.Repo(test_path / REPO_DIR)
    # without worktrees, the control directory is left on the last perturbation branch
    assert control_repo.active_branch.name == "perturb_2"
    heads = branch_heads(test_path)

    generate(test_path, ["perturb_1", "perturb_2"])

    assert control_repo.active_branch.name == CONTROL_BRANCH
    for branch in ["perturb_1", "perturb_2"]:
        assert git.Repo(test_path / branch / REPO_DIR).active_branch.name == branch
    assert branch_heads(test_path) == heads


def test_worktree_left_detached_by_an_interrupted_run_is_used(test_path, checkout_calls):
    # an interrupted run can leave the worktree added but the branch not created yet
    control_repo = git.Repo(test_path / REPO_DIR)
    control_repo.git.worktree("add", "--detach", str(test_path / "perturb_1" / REPO_DIR), CONTROL_BRANCH)

    generate(test_path, ["perturb_1"])

    assert git.Repo(test_path / "perturb_1" / REPO_DIR).active_branch.name == "perturb_1"
    assert checkout_calls[0]["is_new_branch"] is True


def test_existing_directory_that_is_not_a_worktree_is_not_overwritten(test_path, checkout_calls):
    directory = test_path / "perturb_1" / REPO_DIR
    directory.mkdir(parents=True)
    (directory / "notes.txt").write_text("keep me")

    with pytest.raises(FileExistsError, match="is not a worktree"):
        generate(test_path, ["perturb_1"])

    assert (directory / "notes.txt").read_text() == "keep me"
    assert "perturb_1" not in branch_heads(test_path)


def test_branch_checked_out_in_another_worktree_is_rejected(test_path, checkout_calls):
    control_repo = git.Repo(test_path / REPO_DIR)
    control_repo.git.worktree("add", "-b", "perturb_1", str(test_path / "elsewhere"), CONTROL_BRANCH)

    with pytest.raises(RuntimeError, match="is checked out at"):
        generate(test_path, ["perturb_1"])


def test_branch_named_like_the_control_directory_is_rejected(test_path, checkout_calls):
    with pytest.raises(ValueError, match="inside the control directory"):
        generate(test_path, [REPO_DIR])

    # nothing was created
    assert len(git.Repo(test_path / REPO_DIR).git.worktree("list").splitlines()) == 1
    assert checkout_calls == []
