from pathlib import Path
from src.experiment_generator.base_experiment import BaseExperiment


def test_base_experiment_defaults_and_paths(tmp_path):
    """
    BaseExperiment should set default paths and combine cwd, test_path and repo_dir correctly.
    """
    repo_dir = "test_repo"
    indata = {
        # no test_path is provided, should default to 'experiment_generator_test_path'
        "repository_directory": repo_dir,
    }

    base = BaseExperiment(indata)

    assert base.test_path == Path("experiment_generator_test_path")

    expected_directory = Path.cwd() / "experiment_generator_test_path" / repo_dir

    assert base.directory == expected_directory

    repo_dir2 = "another_test_repo"
    indata2 = {
        "test_path": tmp_path / "user_test_path",
        "repository_directory": repo_dir2,
    }

    base2 = BaseExperiment(indata2)

    expcted_directory2 = tmp_path / "user_test_path" / repo_dir2

    assert base2.directory == expcted_directory2
