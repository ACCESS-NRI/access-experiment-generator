import sys
import experiment_generator.experiment_generator as exp_gen
from experiment_generator.experiment_generator import VALID_MODELS
from experiment_generator.tmp_parser import yaml_config
import pytest
import runpy


def test_main_runs_with_i_flag(tmp_path, monkeypatch):
    import experiment_generator.main as main_module

    yaml = tmp_path / "example.yaml"
    yaml.write_text(
        f"""
repository_directory: test_repo
control_branch_name: ctrl
model_type: {VALID_MODELS[0]}
""",
    )

    called = {}

    class DummyEG:
        def __init__(self, indata):
            called["indata"] = indata

        def run(self):
            called["run"] = True

    monkeypatch.setattr(main_module, "ExperimentGenerator", DummyEG, raising=True)

    monkeypatch.setattr(sys, "argv", ["prog", "--input-yaml-file", yaml.as_posix()])

    main_module.main()

    assert called.get("run") is True
    assert called["indata"]["model_type"] == VALID_MODELS[0]


def test_main_uses_default_yaml_when_present(tmp_path, monkeypatch):
    import experiment_generator.main as main_module

    default_yaml = tmp_path / "Experiment_generator.yaml"
    default_yaml.write_text(f"""
repository_directory: test_repo
control_branch_name: ctrl
model_type: {VALID_MODELS[1]}
""")

    monkeypatch.chdir(tmp_path)

    called = {}

    class DummyEG:
        def __init__(self, indata):
            called["indata"] = indata

        def run(self):
            called["run"] = True

    monkeypatch.setattr(main_module, "ExperimentGenerator", DummyEG, raising=True)

    monkeypatch.setattr(sys, "argv", ["prog"])

    main_module.main()

    assert called.get("run") is True
    assert called["indata"]["model_type"] == VALID_MODELS[1]


def test_main_errors_when_no_yaml_provided_and_default_missing(tmp_path, monkeypatch, capsys):
    import experiment_generator.main as main_module

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code != 0

    captured = capsys.readouterr()

    err = captured.err
    assert "Experiment_generator.yaml" in err
    assert "-i / --input-yaml-file" in err


def test_exec_main(tmp_path, monkeypatch):
    called = {}

    def dummy_read_yaml(file_path):
        return {
            "repository_directory": "test_repo",
            "control_branch_name": "ctrl",
            "model_type": VALID_MODELS[0],
            "test_path": str(tmp_path),
        }

    class DummyEG:
        def __init__(self, indata):
            called["indata"] = indata

        def run(self):
            called["run"] = True

    monkeypatch.setattr(yaml_config, "read_yaml", dummy_read_yaml, raising=True)
    monkeypatch.setattr(exp_gen, "ExperimentGenerator", DummyEG, raising=True)

    monkeypatch.setattr(sys, "argv", ["prog", "-i", "dummy.yaml"])

    sys.modules.pop("experiment_generator.main", None)

    runpy.run_module("experiment_generator.main", run_name="__main__", alter_sys=True)

    assert called.get("run") is True
    assert called["indata"]["model_type"] == VALID_MODELS[0]


def test_get_version_fails(monkeypatch):
    import experiment_generator.main as main_module

    def raise_not_found(_name):
        raise main_module.PackageNotFoundError

    monkeypatch.setattr(main_module, "version", raise_not_found, raising=True)

    assert main_module.get_version() == "unknown"
