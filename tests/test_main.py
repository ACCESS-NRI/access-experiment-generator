import sys
import experiment_generator.main as main_module

VALID_MODELS = ["access-om2", "access-om3"]


def test_main_runs_generator(tmp_path, monkeypatch):
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
