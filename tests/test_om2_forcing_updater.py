from pathlib import Path
import pytest
from experiment_generator.om2_forcing_updater import Om2ForcingUpdater
from experiment_generator.tmp_parser.json_parser import read_json, write_json


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """
    A temp repo dir with a minimal atmosphere/forcing.json.
    """
    repo = tmp_path / "repo"
    (repo / "atmosphere").mkdir(parents=True)
    forcing = {
        "description": "JRA55-do v1.4.0 IAF forcing",
        "inputs": [
            {"filename": "INPUT/rsds.nc", "fieldname": "rsds", "cname": "swfld_ai"},
            {"filename": "INPUT/uas.nc", "fieldname": "uas", "cname": "uwnd_ai"},
            {"filename": "INPUT/tas.nc", "fieldname": "tas", "cname": "tair_ai"},
        ],
    }
    write_json(forcing, repo / "atmosphere" / "forcing.json")
    return repo


def test_list_of_perturbs(tmp_repo: Path):
    """
    Ensures perturbations are persisted as a list
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "uas": {
            "filename": "INPUT/uas_new.nc",
            "cname": "uwnd_ai",
            "perturbations": [
                {
                    "type": "scaling",
                    "dimension": "spatial",
                    "value": "INPUT/uas_TP.nc",
                    "calendar": "forcing",
                    "comment": "increase TP winds",
                },
                {
                    "type": "offset",
                    "dimension": "constant",
                    "value": 5,
                    "calendar": "forcing",
                    "comment": "",
                },
                {
                    "type": "separable",
                    "dimension": ["temporal", "spatial"],
                    "value": ["T.nc", "S.nc"],
                    "calendar": "experiment",
                    "comment": "",
                },
            ],
        }
    }

    updater.update_forcing_params(params, Path("atmosphere/forcing.json"))

    data = read_json(tmp_repo / "atmosphere" / "forcing.json")
    uas = next(x for x in data["inputs"] if x["fieldname"] == "uas")
    assert uas["filename"] == "INPUT/uas_new.nc"
    assert isinstance(uas.get("perturbations"), list)
    assert len(uas["perturbations"]) == 3
    assert uas["perturbations"][0]["type"] == "scaling"
    assert uas["perturbations"][1]["dimension"] == "constant"
    assert uas["perturbations"][2]["dimension"] == ["temporal", "spatial"]


def test_dict_of_single_perturb(tmp_repo: Path):
    """
    Input a single dict perturbation, it should be wrapped to a list
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "tas": {
            "filename": "INPUT/tas_new.nc",
            "cname": "tair_ai",
            "perturbations": {
                "type": "offset",
                "dimension": "constant",
                "value": 10,
                "calendar": "forcing",
                "comment": "",
            },
        }
    }

    updater.update_forcing_params(params, Path("atmosphere/forcing.json"))

    data = read_json(tmp_repo / "atmosphere" / "forcing.json")
    tas = next(x for x in data["inputs"] if x["fieldname"] == "tas")
    assert tas["filename"] == "INPUT/tas_new.nc"
    assert isinstance(tas.get("perturbations"), list)
    assert len(tas["perturbations"]) == 1
    assert tas["perturbations"][0]["type"] == "offset"
    assert tas["perturbations"][0]["dimension"] == "constant"


def test_no_perturbations_key(tmp_repo: Path):
    """
    No 'perturbations' key in updates, should still update others but not perturbations.
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "rsds": {
            "filename": "INPUT/rsds_new.nc",
            "cname": "swfld_ai",
            # No perturbations provided
        }
    }

    updater.update_forcing_params(params, Path("atmosphere/forcing.json"))

    data = read_json(tmp_repo / "atmosphere" / "forcing.json")
    rsds = next(x for x in data["inputs"] if x["fieldname"] == "rsds")
    assert rsds["filename"] == "INPUT/rsds_new.nc"
    assert "perturbations" not in rsds  # No perturbations key should be present


@pytest.mark.parametrize("not_existed", [None, {}, []])
def test_single_field_with_perturbation_no_content(tmp_repo: Path, not_existed):
    """
    For None, {} or [], it should warn and remove the perturbations key.
    """
    updater = Om2ForcingUpdater(tmp_repo)
    fieldname = "tas"
    updates = {
        "filename": "INPUT/tas_new.nc",
        "cname": "tair_ai",
        "perturbations": not_existed,  # No perturbations provided
    }

    with pytest.warns(UserWarning):
        updater.update_forcing_params({fieldname: updates}, Path("atmosphere/forcing.json"))

    data = read_json(tmp_repo / "atmosphere" / "forcing.json")
    tas = next(x for x in data["inputs"] if x["fieldname"] == "tas")
    assert "perturbations" not in tas  # No perturbations key should be present


def test_missing_required_key_raises(tmp_repo: Path):
    """
    Missing 'filename' must raise a ValueError
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "uas": {
            # missing 'filename'
            "cname": "uwnd_ai",
        }
    }
    with pytest.raises(ValueError) as e:
        updater.update_forcing_params(params, Path("atmosphere/forcing.json"))
    assert "non-empty 'filename'" in str(e.value)


def test_missing_perturbation_fields(tmp_repo: Path):
    """
    Missing required fields in perturbation should raise ValueError
    """
    updater = Om2ForcingUpdater(tmp_repo)
    fieldname = "tas"
    updates = {
        "filename": "INPUT/tas_new.nc",
        "cname": "tair_ai",
        "perturbations": {
            "type": "offset",  # Missing 'dimension', 'value', 'calendar', 'comment'
        },
    }

    with pytest.raises(
        ValueError, match="Perturbation is missing required fields: dimension, value, calendar, comment"
    ):
        updater._preprocess_perturbations(fieldname, updates)


def test_invalid_perturbation_type(tmp_repo: Path):
    """
    Ensure invalid perturbation type raises a ValueError
    """
    updater = Om2ForcingUpdater(tmp_repo)
    fieldname = "tas"
    updates = {
        "filename": "INPUT/tas_new.nc",
        "cname": "tair_ai",
        "perturbations": {
            "type": "invalid_type",  # Invalid type
            "dimension": "constant",
            "value": 10,
            "calendar": "forcing",
            "comment": "",
        },
    }

    with pytest.raises(ValueError, match="Invalid perturbation type: invalid_type"):
        updater._preprocess_perturbations(fieldname, updates)


def test_field_not_found_raises(tmp_repo: Path):
    """
    Ensure that if the fieldname does not exist in forcing.json, it raises ValueError
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "not_an_existed_field": {
            "filename": "INPUT/not_an_existed_field.nc",
            "cname": "xx",
        }
    }
    with pytest.raises(ValueError) as e:
        updater.update_forcing_params(params, Path("atmosphere/forcing.json"))
    assert "Not found a valid perturbed fieldname" in str(e.value)


def test_invalid_perturbation_dimension(tmp_repo: Path):
    """
    Ensure that an invalid perturbation dimension raises a ValueError
    """
    updater = Om2ForcingUpdater(tmp_repo)
    fieldname = "tas"
    updates = {
        "filename": "INPUT/tas_new.nc",
        "cname": "tair_ai",
        "perturbations": {
            "type": "scaling",
            "dimension": "invalid_dimension",  # Invalid dimension
            "value": 10,
            "calendar": "forcing",
            "comment": "",
        },
    }

    with pytest.raises(ValueError, match="Invalid perturbation dimension: invalid_dimension"):
        updater._preprocess_perturbations(fieldname, updates)


@pytest.mark.parametrize("dim", (["temporal", "spatial"], ["spatial", "temporal"]))
def test_valid_separable_dimension_orders(tmp_repo: Path, dim):
    """
    Separable accepts either ['temporal', 'spatial'] or ['spatial', 'temporal']
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "uas": {
            "filename": "INPUT/uas_new.nc",
            "cname": "uwnd_ai",
            "perturbations": [
                {
                    "type": "separable",
                    "dimension": dim,
                    "value": ["T.nc", "S.nc"],
                    "calendar": "forcing",
                    "comment": "",
                }
            ],
        }
    }
    # Should not raise
    updater.update_forcing_params(params, Path("atmosphere/forcing.json"))

    data = read_json(tmp_repo / "atmosphere" / "forcing.json")

    uas = next(x for x in data["inputs"] if x["fieldname"] == "uas")
    assert isinstance(uas.get("perturbations"), list)
    assert uas["perturbations"][0]["dimension"] == dim


def test_invalid_calendar_raises(tmp_repo: Path):
    """
    Calendar must be 'forcing' or 'experiment'
    """
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "uas": {
            "filename": "INPUT/uas_new.nc",
            "cname": "uwnd_ai",
            "perturbations": [
                {
                    "type": "offset",
                    "dimension": "constant",
                    "value": 2,
                    "calendar": "invalid",  # invalid calendar
                    "comment": "",
                }
            ],
        }
    }
    with pytest.raises(ValueError) as e:
        updater.update_forcing_params(params, Path("atmosphere/forcing.json"))
    assert "Invalid perturbation calendar" in str(e.value)


@pytest.mark.parametrize("invalid", ["not a dict or list", 1.0, [1, 2, 3]])
def test_invalid_perturbations_container_type_raises(tmp_repo: Path, invalid):
    updater = Om2ForcingUpdater(tmp_repo)
    params = {
        "tas": {
            "filename": "INPUT/tas.nc",
            "cname": "tair_ai",
            "perturbations": invalid,
        }
    }
    with pytest.raises(TypeError) as e:
        updater.update_forcing_params(params, Path("atmosphere/forcing.json"))
    assert str(e.value) == "-- forcing.json 'tas': 'perturbations' must be a dict or list of dicts"
