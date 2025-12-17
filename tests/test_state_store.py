import json
from pathlib import Path

from experiment_generator.state_store import RemoveStateStore


def test_state_path_creates_dir_and_has_expected_filename(tmp_path: Path):
    store = RemoveStateStore(root_dir=tmp_path)

    p = store.state_path("perturb_1")

    # directory is created as a side-effect
    assert (tmp_path / store.remove_state_dirname).is_dir()
    # filename is correct
    assert p.name == "perturb_1.json"
    assert p.parent == (tmp_path / store.remove_state_dirname)


def test_load_state_missing_file_returns_empty_dict(tmp_path: Path):
    store = RemoveStateStore(root_dir=tmp_path)

    state = store.load_state("does_not_exist")

    assert state == {}


def test_save_then_load_roundtrip(tmp_path: Path):
    store = RemoveStateStore(root_dir=tmp_path)

    state_in = {
        "a": 1,
        "nested": {"x": [1, 2, 3]},
        "path::REMOVE[0]": "/g/data/foo/bar.nc",
    }

    store.save_state("perturb_1", state_in)

    fpath = store.state_path("perturb_1")
    assert fpath.exists()

    # sanity: file is valid JSON
    parsed = json.loads(fpath.read_text())
    assert parsed == state_in

    state_out = store.load_state("perturb_1")
    assert state_out == state_in


def test_save_overwrites_existing_file(tmp_path: Path):
    store = RemoveStateStore(root_dir=tmp_path)

    store.save_state("perturb_1", {"a": 1})
    store.save_state("perturb_1", {"a": 2, "b": 3})

    assert store.load_state("perturb_1") == {"a": 2, "b": 3}


def test_custom_state_dirname(tmp_path: Path):
    store = RemoveStateStore(root_dir=tmp_path, remove_state_dirname=".my_states")

    store.save_state("perturb_2", {"k": "v"})

    assert (tmp_path / ".my_states").is_dir()
    assert (tmp_path / ".my_states" / "perturb_2.json").exists()
    assert store.load_state("perturb_2") == {"k": "v"}
