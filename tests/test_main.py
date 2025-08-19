import sys
import experiment_generator.main as main_module
from experiment_generator.experiment_generator import VALID_MODELS
import pytest


def test_main_runs_with_i_flag(tmp_path, monkeypatch):
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
    default_yaml = tmp_path / "Experiment_manager.yaml"
    default_yaml.write_text(
        f"""
repository_directory: test_repo
control_branch_name: ctrl
model_type: {VALID_MODELS[1]}
"""
    )

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
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv", ["prog"])

    with pytest.raises(SystemExit) as exc_info:
        main_module.main()

    assert exc_info.value.code != 0

    captured = capsys.readouterr()

    err = captured.err
    assert "Experiment_generator.yaml" in err
    assert "-i / --input-yaml-file" in err
