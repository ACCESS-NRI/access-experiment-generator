from pathlib import Path
import pytest
from experiment_generator.om2_forcing_updater import Om2ForcingUpdater
import experiment_generator.om2_forcing_updater as om2_forcing_module
import json


@pytest.fixture
def sample_input():
    return {
        "inputs": [
            {
                "fieldname": "tas",
                "filename": "INPUT/tas.nc",
                "cname": "tair_ai",
            },
            {
                "fieldname": "uas",
                "filename": "INPUT/uas.nc",
                "cname": "uwnd_ai",
            },
        ]
    }


@pytest.fixture
def patch_json_and_utils(monkeypatch, sample_input):
    """
    Patch the read_json, write_json and update_config_entries functions
    to use sample input.
    """
    calls = {
        "read_json": [],
        "write_json": [],
        "update_config_entries": [],
    }

    def dummy_read_json(path):
        calls["read_json"].append(path)
        return {"inputs": sample_input["inputs"]}

    def dummy_write_json(data, path):
        tmp_data = json.dumps(data)
        calls["write_json"].append((tmp_data, path))

    def dummy_update_config_entries(base: dict, updates: dict, **kwargs):
        calls["update_config_entries"].append((base, updates, kwargs))
        for k, v in updates.items():
            base[k] = v

    monkeypatch.setattr(om2_forcing_module, "read_json", dummy_read_json, raising=True)
    monkeypatch.setattr(om2_forcing_module, "write_json", dummy_write_json, raising=True)
    monkeypatch.setattr(om2_forcing_module, "update_config_entries", dummy_update_config_entries, raising=True)
    return calls


def test_update_forcing_params_correct_path(tmp_repo_dir, patch_json_and_utils):
    """
    - dict `perturbations` is a list
    - perturbations is list[dict]
    - update_config_entries is invoked per fieldname
    - write_json is called once with merged content
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)

    params = {
        "tas": {
            "filename": "NEW/tas_{{year}}.nc",
            "cname": "tair_ai",
            "perturbations": {
                "type": "scaling",
                "dimension": "temporal",
                "value": "../test_data/scaling.tas.1990_1991.nc",
                "calendar": "forcing",
                "comment": "scale up",
            },
        },
        "uas": {
            "filename": "NEW/uas_{{year}}.nc",
            "cname": "uwnd_ai",
            "perturbations": [
                {
                    "type": "offset",
                    "dimension": ["temporal", "spatial"],
                    "value": ["../test_data/temporal.uas.1990_1991.nc", "../test_data/spatial.uas.1990_1991.nc"],
                    "calendar": "experiment",
                    "comment": "bias adjust",
                }
            ],
        },
    }

    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)

    # read and write
    assert patch_json_and_utils["read_json"] == [tmp_repo_dir / "atmosphere" / "forcing.json"]
    assert len(patch_json_and_utils["write_json"]) == 1
    written_data, written_path = patch_json_and_utils["write_json"][0]
    assert written_path == tmp_repo_dir / "atmosphere" / "forcing.json"

    assert len(patch_json_and_utils["update_config_entries"]) == 2


def test_all_removed_perturbations_warn_and_skip(tmp_repo_dir, patch_json_and_utils, monkeypatch):
    """
    Cleaning branch where every perturbation is marked for removal,
    warn and do NOT set updates['perturbations'] (early return).
    """
    # Make "REMOVE"
    monkeypatch.setattr(om2_forcing_module, "REMOVED", "REMOVE", raising=True)

    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "NEW/tas.nc",
            "cname": "tair_ai",
            "perturbations": [
                # all perturbations are marked for removal
                {"type": "REMOVE", "dimension": "REMOVE", "value": "REMOVE", "calendar": "REMOVE", "comment": "REMOVE"},
                # also ensure 'type' alone being REMOVED is enough
                {"type": "REMOVE", "dimension": "spatial", "value": 1, "calendar": "forcing", "comment": "x"},
            ],
        }
    }

    state = {}

    with pytest.warns(UserWarning):
        updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)

    assert len(patch_json_and_utils["update_config_entries"]) == 1
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "perturbations" not in updates


def test_fieldname_not_found_raises(tmp_repo_dir, patch_json_and_utils):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    tmp = {"not_in_file": {"filename": "x.nc", "cname": "X"}}
    state = {}
    with pytest.raises(ValueError):
        updater.update_forcing_params(tmp, target_file=Path("atmosphere/forcing.json"), state=state)
    assert patch_json_and_utils["write_json"] == []


@pytest.mark.parametrize("empty", [None, {}, []])
def test_empty_or_none_perturbations_warn_and_removed(tmp_repo_dir, patch_json_and_utils, empty):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    tmp = {"tas": {"filename": "x.nc", "cname": "X", "perturbations": empty}}
    state = {}
    with pytest.warns(UserWarning):
        updater.update_forcing_params(tmp, target_file=Path("atmosphere/forcing.json"), state=state)
    # ensure preprocess removed the key before merging
    assert len(patch_json_and_utils["update_config_entries"]) == 1
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "perturbations" not in updates


@pytest.mark.parametrize("invalid", [42, "oops", [1, 2], [{"type": "scaling"}, "invalid"]])
def test_invalid_perturbations_type_raises(tmp_repo_dir, patch_json_and_utils, invalid):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    state = {}
    tmp = {"tas": {"filename": "x.nc", "cname": "X", "perturbations": invalid}}
    with pytest.raises(TypeError):
        updater.update_forcing_params(tmp, target_file=Path("atmosphere/forcing.json"), state=state)
    assert patch_json_and_utils["write_json"] == []


@pytest.mark.parametrize("ptype", ["", None, "wrongtype"])
def test_validate_single_perturbation_wrong_type(tmp_repo_dir, ptype):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    pert = {
        "type": ptype,
        "dimension": "temporal",
        "value": "../test_data/temporal.tas.1990_1991.nc",
        "calendar": "forcing",
        "comment": "x",
    }
    with pytest.raises(ValueError):
        updater._validate_single_perturbation(pert)


@pytest.mark.parametrize(
    "dim",
    [
        123,
        "space",  # not allowed
        ["temporal"],  # list but not the two-item allowed perms
        ["temporal", "spatial", "x"],  # extra item
    ],
)
def test_validate_single_perturbation_invalid_dimension(tmp_repo_dir, dim):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    pert = {
        "type": "offset",
        "dimension": dim,
        "value": "../test_data/offset.tas.1990_1991.nc",
        "calendar": "forcing",
        "comment": "wrong dim",
    }
    with pytest.raises(ValueError):
        updater._validate_single_perturbation(pert)


@pytest.mark.parametrize("calendar", ["", None, "weird"])
def test_validate_single_perturbation_wrong_calendar(tmp_repo_dir, calendar):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    pert = {
        "type": "scaling",
        "dimension": "spatiotemporal",
        "value": "../test_data/scaling.tas.1990_1991.nc",
        "calendar": calendar,
        "comment": "wrong calendar",
    }
    with pytest.raises(ValueError):
        updater._validate_single_perturbation(pert)


@pytest.mark.parametrize(
    "wrong_type",
    [
        None,
        42,
        "nonsense",
    ],
)
def test_invalid_type_branch_removes_perturbations(tmp_repo_dir, patch_json_and_utils, wrong_type):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "NEW/tas.nc",
            "cname": "tair_ai",
            "perturbations": [
                {
                    "type": wrong_type,
                    "dimension": "temporal",
                    "value": "../bad.nc",
                    "calendar": "forcing",
                    "comment": "invalid type",
                }
            ],
        }
    }
    state = {}
    with pytest.raises(ValueError):
        updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)

    assert patch_json_and_utils["update_config_entries"] == []
    assert patch_json_and_utils["write_json"] == []


def test_top_level_perturbations_preserved_scalar_is_dropped(tmp_repo_dir, patch_json_and_utils):
    """
    if _is_preserved_str(perts): pop 'perturbations'
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "tas.nc",
            "perturbations": "PRESERVE",
        }
    }
    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)

    # ensure we merged without 'perturbations'
    assert len(patch_json_and_utils["update_config_entries"]) == 1
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "perturbations" not in updates
    assert updates["filename"] == "tas.nc"


def test_top_level_perturbations_preserved_singleton_list_is_dropped(tmp_repo_dir, patch_json_and_utils):
    """
    list with one PRESERVED element
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "tas.nc",
            "perturbations": ["PRESERVE"],
        }
    }
    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)
    assert len(patch_json_and_utils["update_config_entries"]) == 1
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "perturbations" not in updates
    assert updates["filename"] == "tas.nc"


def test_top_level_keys_marked_preserved_are_dropped_before_merge(tmp_repo_dir, patch_json_and_utils):
    """
    keys_to_drop = [k for k, v in updates.items() if _is_preserved_str(v)]
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "PRESERVE",
            "cname": "tair_ai",
            "perturbations": {
                "type": "scaling",
                "dimension": "temporal",
                "value": "../tas.nc",
                "calendar": "forcing",
                "comment": "x",
            },
        }
    }
    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)
    # ensure 'filename' key didn't get passed to the merger
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "filename" not in updates
    assert "perturbations" in updates


def test_preprocess_perturbations_type_preserved_skips_that_entry(tmp_repo_dir, patch_json_and_utils):
    """
    if _is_preserved_str(t_): continue
    Also ensures remaining valid perturbation is kept.
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "perturbations": [
                {
                    "type": "PRESERVE",
                    "dimension": "temporal",
                    "value": "../tas.nc",
                    "calendar": "forcing",
                    "comment": "x",
                },
                {
                    "type": "offset",  # kept
                    "dimension": "spatial",
                    "value": "../keep.nc",
                    "calendar": "experiment",
                    "comment": "keep",
                },
            ]
        }
    }
    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)
    # exactly one perturbation survives and is passed to merger
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    perts = updates["perturbations"]
    assert isinstance(perts, list) and len(perts) == 1
    assert perts[0]["type"] == "offset"
    assert perts[0]["dimension"] == "spatial"
    assert perts[0]["calendar"] == "experiment"


def test_preprocess_perturbations_inner_fields_preserved_are_dropped(tmp_repo_dir, patch_json_and_utils):
    """
    for k in list(q.keys()): dropping inner 'PRESERVE' fields inside each perturbation dict.
    """
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "perturbations": [
                {
                    "type": "scaling",
                    "dimension": "temporal",
                    "value": "../tas.nc",
                    "calendar": "forcing",
                    "comment": "PRESERVE",  # should be removed from dict
                }
            ]
        }
    }
    state = {}
    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    (pert,) = updates["perturbations"]
    assert "comment" not in pert  # dropped
    # sanity: others remain
    assert pert["type"] == "scaling"
    assert pert["dimension"] == "temporal"
    assert pert["calendar"] == "forcing"


def test_update_forcing_params_no_perturbations_key_skips_branch(tmp_repo_dir, patch_json_and_utils, monkeypatch):
    updater = Om2ForcingUpdater(tmp_repo_dir)
    params = {
        "tas": {
            "filename": "NEW/tas.nc",
            "cname": "tair_ai",
            # NOTE: no "perturbations" key at all
        }
    }
    state = {}

    updater.update_forcing_params(params, target_file=Path("atmosphere/forcing.json"), state=state)

    # update_config_entries should be called once (for tas)
    assert len(patch_json_and_utils["update_config_entries"]) == 1
    _, updates, _ = patch_json_and_utils["update_config_entries"][0]
    assert "perturbations" not in updates
    assert updates["filename"] == "NEW/tas.nc"

    # write_json called once
    assert len(patch_json_and_utils["write_json"]) == 1
