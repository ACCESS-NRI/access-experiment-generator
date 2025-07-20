import pytest
from pathlib import Path
import experiment_generator.experiment_generator as exp_gen
import experiment_generator.perturbation_experiment as pert_exp


class DummyBranch:
    def __init__(self, name):
        self.name = name


class DummyDiff:
    def __init__(self, a_path):
        self.a_path = a_path


class DummyIndex:
    def __init__(self, changed_files):
        self._changed_files = changed_files

    def diff(self, _):
        return (DummyDiff(file) for file in self._changed_files)


class DummyRepo:
    def __init__(self, branches=None, changed_files=None):
        if branches is None:
            branches = []
        if changed_files is None:
            changed_files = []

        self.branches = [DummyBranch(name) for name in branches]
        self.index = DummyIndex(changed_files)


class DummyGitRepository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.repo = DummyRepo()
        self.commits = []

    def commit(self, message, files):
        self.commits.append((message, files))

    def local_branches_dict(self):
        return {branch.name: branch for branch in self.repo.branches}


def dummy_clone(*args, **kwargs):
    return None


def dummy_checkout_branch(*args, **kwargs):
    return None


@pytest.fixture(autouse=True)
def patch_git(monkeypatch):
    """
    Auto-patch the clone, GitRepository and check_branch for testing.
    """
    monkeypatch.setattr(exp_gen, "clone", dummy_clone)
    monkeypatch.setattr(pert_exp, "GitRepository", DummyGitRepository)
    monkeypatch.setattr(pert_exp, "checkout_branch", dummy_checkout_branch)
