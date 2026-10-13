import json
import math
from pathlib import Path
from textwrap import dedent

import pytest
from access.config import (
    FieldTableParser,
    FortranNMLParser,
    JSONParser,
    MOM6InputParser,
    NUOPCParser,
    NUOPCRunSeqParser,
    YAMLParser,
)

from experiment_generator.common_var import PRESERVED, REMOVED
from experiment_generator.config_file_updater import (
    ConfigFileUpdater,
    _from_fortran_text,
    _validate_single_perturbation,
    prune_empty_field_table_config,
)


@pytest.fixture
def repo_dir(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    return repo_dir


def _write(repo_dir: Path, filename: str, text: str) -> Path:
    path = repo_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _read(repo_dir: Path, filename: str):
    return ConfigFileUpdater.parser_for(filename).parse((repo_dir / filename).read_text())


# --- dispatch ---


@pytest.mark.parametrize(
    "filename, parser",
    [
        ("config.yaml", YAMLParser),
        ("diagnostic_profiles/diag_table_source.yaml", YAMLParser),
        ("MOM_input", MOM6InputParser),
        ("nuopc.runconfig", NUOPCParser),
        ("ice_in", FortranNMLParser),
        ("ocean/input.nml", FortranNMLParser),
        ("atmosphere/namelists", FortranNMLParser),
        ("atmosphere/forcing.json", JSONParser),
        ("nuopc.runseq", NUOPCRunSeqParser),
        ("ocean/field_table", FieldTableParser),
    ],
)
def test_parser_for(filename, parser):
    assert isinstance(ConfigFileUpdater.parser_for(filename), parser)


@pytest.mark.parametrize("filename", ["other.json", "MOM_override", "nuopc.runseq.bak"])
def test_parser_for_unsupported_file(filename):
    assert ConfigFileUpdater.parser_for(filename) is None


def test_update_params_unsupported_file_raises(repo_dir):
    with pytest.raises(ValueError, match="No parser available"):
        ConfigFileUpdater(repo_dir).update_params({}, "other.json")


# --- one generic merge for every format: update, add, REMOVE, PRESERVE ---


@pytest.mark.parametrize(
    "filename, original, params, expected",
    [
        pytest.param(
            "config.yaml",
            """# PBS configuration
jobname: test_repo
queue: normal
walltime: "01:00:00"
input:
    - /some/path/to/inputs/mom  # MOM6 inputs
    - /some/path/to/inputs/cice # CICE inputs
""",
            {
                "queue": "express",
                "walltime": "PRESERVE",
                "input": ["/new/path/to/inputs/mom", "PRESERVE"],
                "mem": "8GB",
            },
            """# PBS configuration
jobname: test_repo
queue: express
walltime: "01:00:00"
input:
    - /new/path/to/inputs/mom   # MOM6 inputs
    - /some/path/to/inputs/cice # CICE inputs
mem: 8GB
""",
            id="yaml",
        ),
        pytest.param(
            "MOM_input",
            """DT = 900.0                      !   [s]
                                ! The (baroclinic) dynamics time step.
DT_THERM = 7200.0               !   [s] default = 900.0
                                ! The thermodynamic time step.
INPUTDIR = "INPUT"
KPP%
N_SMOOTH = 1
%KPP
""",
            {"DT": 10, "DT_THERM": "REMOVE", "INPUTDIR": "PRESERVE", "KPP": {"N_SMOOTH": 2}, "USE_KPP": True},
            """DT = 10.0                      !   [s]
                                ! The (baroclinic) dynamics time step.
                                ! The thermodynamic time step.
INPUTDIR = "INPUT"
KPP%
N_SMOOTH = 2
%KPP
USE_KPP = True
""",
            id="mom6",
        ),
        pytest.param(
            "nuopc.runconfig",
            """PELAYOUT_attributes::
     atm_ntasks = 364
     atm_nthreads = 2
::

start_type: startup
stop_n: 1
""",
            {
                "PELAYOUT_attributes": {"atm_ntasks": 150, "atm_nthreads": "REMOVE", "atm_rootpe": 0},
                "start_type": "PRESERVE",
                "stop_n": 5,
            },
            """PELAYOUT_attributes::
     atm_ntasks = 150
     atm_rootpe = 0
::

start_type: startup
stop_n: 5
""",
            id="nuopc",
        ),
        pytest.param(
            "ice_in",
            """&setup_nml
  dt = 1800.0
  diagfreq = 24 ! comment
  runid = 'old'
/
""",
            {"setup_nml": {"dt": 1200, "diagfreq": "REMOVE", "runid": "PRESERVE", "use_leap_years": True}},
            """&setup_nml
  dt = 1200.0
  runid = 'old'
  use_leap_years = .true.
/
""",
            id="namelist",
        ),
        pytest.param(
            "atmosphere/forcing.json",
            json.dumps({"inputs": [{"fieldname": "tas", "filename": "INPUT/tas.nc", "cname": "tair_ai"}]}, indent=2)
            + "\n",
            {"tas": {"filename": "NEW/tas.nc", "cname": "PRESERVE", "comment": "new"}},
            json.dumps(
                {"inputs": [{"fieldname": "tas", "filename": "NEW/tas.nc", "cname": "tair_ai", "comment": "new"}]},
                indent=2,
            )
            + "\n",
            id="json",
        ),
    ],
)
def test_update_params_minimal_diff(repo_dir, filename, original, params, expected):
    path = _write(repo_dir, filename, original)

    # an untouched file is written back exactly as it was
    ConfigFileUpdater(repo_dir).update_params({}, filename, state={})
    if filename != "config.yaml":  # where jobname is always enforced
        assert path.read_text() == original

    ConfigFileUpdater(repo_dir).update_params(params, filename, state={})
    assert path.read_text() == expected
    assert not path.with_name(path.name + ".tmp").exists()


@pytest.mark.parametrize("change, written", [([1, 10, "REMOVE"], "1:10"), ([1, 10, 19, 26], "1:10:19:26")])
def test_update_params_list_length_change(repo_dir, change, written):
    """
    A list of a different length is laid out again, where it is.
    """
    _write(repo_dir, "nuopc.runconfig", "ALLCOMP_attributes::\n  ocn2glc_levels = 1:10:19\n  OCN_model = mom\n::\n")
    ConfigFileUpdater(repo_dir).update_params({"ALLCOMP_attributes": {"ocn2glc_levels": change}}, "nuopc.runconfig")
    assert (repo_dir / "nuopc.runconfig").read_text() == (
        f"ALLCOMP_attributes::\n  ocn2glc_levels = {written}\n  OCN_model = mom\n::\n"
    )


def test_update_params_none_unsupported(repo_dir):
    """
    MOM6 stops on a parameter with no value, so MOM_input cannot hold None.
    """
    path = _write(repo_dir, "MOM_input", "DT = 900.0\n")
    with pytest.raises(ValueError, match="cannot write None"):
        ConfigFileUpdater(repo_dir).update_params({"DT": None}, "MOM_input")
    assert path.read_text() == "DT = 900.0\n"


def test_nuopc_none_and_remove(repo_dir):
    _write(repo_dir, "nuopc.runconfig", "DT: 900.0\nDRIVER_attributes::\n  pio_blocksize = -1\n  Verbosity = off\n::\n")
    updater = ConfigFileUpdater(repo_dir)

    # None is an entry with no value, which NUOPC leaves unset
    updater.update_params({"DT": None, "DRIVER_attributes": {"pio_blocksize": None}}, "nuopc.runconfig")
    assert (repo_dir / "nuopc.runconfig").read_text() == (
        "DRIVER_attributes::\n  Verbosity = off\n  pio_blocksize =\n::\nDT:\n"
    )
    assert _read(repo_dir, "nuopc.runconfig") == {
        "DRIVER_attributes": {"Verbosity": "off", "pio_blocksize": None},
        "DT": None,
    }

    updater.update_params({"DRIVER_attributes": {"pio_blocksize": 2}}, "nuopc.runconfig")
    assert _read(repo_dir, "nuopc.runconfig")["DRIVER_attributes"]["pio_blocksize"] == 2

    updater.update_params({"DRIVER_attributes": {"pio_blocksize": "REMOVE"}}, "nuopc.runconfig")
    assert "pio_blocksize" not in _read(repo_dir, "nuopc.runconfig")["DRIVER_attributes"]


# --- config.yaml ---


def test_yaml_jobname_warning(repo_dir):
    _write(repo_dir, "config.yaml", "jobname: existing_job_name\nqueue: normalsr\n")

    with pytest.warns(UserWarning, match="-- jobname must be the same as"):
        ConfigFileUpdater(repo_dir).update_params({"jobname": "test_jobname", "queue": "normal"}, "config.yaml")

    updated = _read(repo_dir, "config.yaml")
    assert updated["jobname"] == "test_repo"
    assert updated["queue"] == "normal"


def test_yaml_jobname_added_without_warning(repo_dir, recwarn):
    _write(repo_dir, "config.yaml", "queue: normal\n")
    ConfigFileUpdater(repo_dir).update_params({"queue": "express"}, Path("config.yaml"), state={})

    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
    assert (repo_dir / "config.yaml").read_text() == "queue: express\njobname: test_repo\n"


def test_yaml_jobname_matches_no_warning(repo_dir, recwarn):
    _write(repo_dir, "config.yaml", "jobname: test_repo\nqueue: normal\n")
    ConfigFileUpdater(repo_dir).update_params({"jobname": "test_repo", "queue": "express"}, "config.yaml")

    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
    assert (repo_dir / "config.yaml").read_text() == "jobname: test_repo\nqueue: express\n"


def test_yaml_jobname_only_in_payu_config(repo_dir):
    filename = "diagnostic_profiles/source_yaml_files/diag_table_source.yaml"
    _write(repo_dir, filename, "title: ACCESS-OM3\n")
    ConfigFileUpdater(repo_dir).update_params({"title": "test"}, filename)
    assert (repo_dir / filename).read_text() == "title: test\n"


def test_yaml_remove_top_level_key(repo_dir):
    _write(repo_dir, "config.yaml", "jobname: test_repo\nqueue: normal\ninput: /some/path\n")
    ConfigFileUpdater(repo_dir).update_params({"input": "REMOVE"}, "config.yaml")
    assert (repo_dir / "config.yaml").read_text() == "jobname: test_repo\nqueue: normal\n"


# --- Fortran namelists ---


def test_namelist_group_value_must_be_dict(repo_dir):
    _write(repo_dir, "dummy.nml", "&grp\n/\n")
    updater = ConfigFileUpdater(repo_dir)

    with pytest.raises(ValueError, match="Expected dict for grp"):
        updater.update_params({"grp": 1}, "dummy.nml")

    updater.update_params({"grp": {"inner": 1}}, "dummy.nml")
    assert _read(repo_dir, "dummy.nml")["grp"]["inner"] == 1


def test_namelist_group_created_and_vars_set(repo_dir):
    _write(repo_dir, "grp.nml", "&dummy\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"ice_nml": {"A": 1, "B": 2}}, "grp.nml")

    parsed = _read(repo_dir, "grp.nml")
    assert parsed["ice_nml"]["A"] == 1
    assert parsed["ice_nml"]["B"] == 2


def test_namelist_none_and_remove(repo_dir):
    _write(repo_dir, "ice_in", "&grp\n  inner = 1\n  other = 2\n/\n")
    updater = ConfigFileUpdater(repo_dir)

    # None is a Fortran null value: the variable keeps its default
    updater.update_params({"grp": {"inner": None}}, "ice_in")
    assert (repo_dir / "ice_in").read_text() == "&grp\n  other = 2\n  inner =\n/\n"
    assert _read(repo_dir, "ice_in")["grp"]["inner"] is None

    updater.update_params({"grp": {"inner": 2}}, "ice_in")
    assert _read(repo_dir, "ice_in")["grp"]["inner"] == 2

    updater.update_params({"grp": {"inner": "REMOVE"}}, "ice_in")
    assert "inner" not in _read(repo_dir, "ice_in")["grp"]


def test_namelist_group_kept_when_emptied(repo_dir):
    _write(repo_dir, "ice_in", "&grp\n  a = 1\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"grp": {"a": "REMOVE"}}, "ice_in")
    assert _read(repo_dir, "ice_in") == {"GRP": {}}


def test_namelist_keys_are_case_insensitive(repo_dir):
    _write(repo_dir, "ice_in", "&SETUP_NML\n  Diagfreq = 24\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"setup_nml": {"diagfreq": 48}}, "ice_in")
    assert (repo_dir / "ice_in").read_text() == "&SETUP_NML\n  Diagfreq = 48\n/\n"


def test_namelist_repeated_group_raises(repo_dir):
    path = _write(repo_dir, "input.nml", "&grp\n  a = 1\n/\n&grp\n  a = 2\n/\n")
    with pytest.raises(ValueError, match="appears more than once"):
        ConfigFileUpdater(repo_dir).update_params({"grp": {"a": 3}}, "input.nml")
    assert path.read_text() == "&grp\n  a = 1\n/\n&grp\n  a = 2\n/\n"


def test_namelist_fortran_text(repo_dir):
    _write(repo_dir, "input.nml", "&grp\n  fields_in = 'x', 'y'\n  shape = 'square'\n  flag = .false.\n/\n")
    ConfigFileUpdater(repo_dir).update_params(
        {"grp": {"fields_in": "'u_flux', 'v_flux', 'lprec'", "shape": "'slenderX1'", "flag": ".true."}},
        "input.nml",
    )
    parsed = _read(repo_dir, "input.nml")
    assert parsed["grp"]["shape"] == "slenderX1"
    assert parsed["grp"]["flag"] is True
    assert (repo_dir / "input.nml").read_text() == (
        "&grp\n  fields_in = 'u_flux', 'v_flux', 'lprec'\n  shape = 'slenderX1'\n  flag = .true.\n/\n"
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("'slenderX1'", "slenderX1"),
        ('"it""s"', 'it"s'),
        ("'it''s, mine'", "it's, mine"),
        ("'a', 'b'", ["a", "b"]),
        ("1, 2.5, 3d-2, .TRUE., .f.", [1, 2.5, 0.03, True, False]),
        (" 42 ", 42),
        (".false.", False),
        ("cdf5", "cdf5"),
        ("INPUT/file.nc", "INPUT/file.nc"),
        ("a, b", "a, b"),
        ("REMOVE", "REMOVE"),
        (5, 5),
        (["'a'"], ["'a'"]),
    ],
)
def test_from_fortran_text(value, expected):
    assert _from_fortran_text(value) == expected


def test_turning_angle_compute_and_deletes_key(repo_dir):
    _write(repo_dir, "ice_in", "&dynamics_nml\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": 30}}, "ice_in")
    parsed = _read(repo_dir, "ice_in")

    assert "turning_angle" not in parsed["dynamics_nml"]
    assert math.isclose(parsed["dynamics_nml"]["cosw"], math.cos(math.radians(30)))
    assert math.isclose(parsed["dynamics_nml"]["sinw"], math.sin(math.radians(30)))


def test_turning_angle_explicit_cos_sin_take_precedence(repo_dir):
    _write(repo_dir, "ice_in", "&dynamics_nml\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": 30, "cosw": 0.5}}, "ice_in")
    parsed = _read(repo_dir, "ice_in")

    assert parsed["dynamics_nml"]["cosw"] == 0.5
    assert math.isclose(parsed["dynamics_nml"]["sinw"], math.sin(math.radians(30)))


def test_turning_angle_under_other_group_does_not_compute_cos_sin(repo_dir):
    _write(repo_dir, "ice_in", "&grp\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"grp": {"turning_angle": 20}}, "ice_in")
    parsed = _read(repo_dir, "ice_in")

    assert parsed["grp"]["turning_angle"] == 20
    assert "dynamics_nml" not in parsed


def test_turning_angle_remove_only_affects_dynamics_cos_sin(repo_dir):
    _write(repo_dir, "ice_in", "&grp\n  turning_angle = 1\n/\n&dynamics_nml\n  cosw = 0.5\n  sinw = 0.5\n/\n")
    updater = ConfigFileUpdater(repo_dir)

    # REMOVE under grp removes turning_angle there, and leaves cos/sin alone
    updater.update_params({"grp": {"turning_angle": "REMOVE"}}, "ice_in")
    parsed = _read(repo_dir, "ice_in")
    assert "turning_angle" not in parsed["grp"]
    assert parsed["dynamics_nml"] == {"COSW": 0.5, "SINW": 0.5}

    # REMOVE under dynamics_nml drops cos/sin, and keeps the group
    updater.update_params({"dynamics_nml": {"turning_angle": "REMOVE"}}, "ice_in")
    assert _read(repo_dir, "ice_in")["dynamics_nml"] == {}


def test_turning_angle_preserve_requires_existing_cos_sin(repo_dir):
    _write(repo_dir, "ice_in", "&dynamics_nml\n/\n")
    with pytest.raises(ValueError, match="Cannot preserve turning_angle"):
        ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": "PRESERVE"}}, "ice_in")


def test_turning_angle_preserve_keeps_existing_cos_sin(repo_dir):
    path = _write(repo_dir, "ice_in", "&dynamics_nml\n cosw = 0.1\n  sinw = 0.2\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": "PRESERVE"}}, "ice_in")
    assert path.read_text() == "&dynamics_nml\n cosw = 0.1\n  sinw = 0.2\n/\n"


def test_turning_angle_in_dynamics_non_cice_file_does_not_touch_cos_sin(repo_dir):
    path = _write(repo_dir, "input.nml", "&dynamics_nml\n  turning_angle = 10\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": 30}}, "input.nml")
    # turning_angle is never written, and cos/sin are only for CICE namelists
    assert path.read_text() == "&dynamics_nml\n  turning_angle = 10\n/\n"


def test_turning_angle_remove_when_dynamics_group_missing_is_noop(repo_dir):
    _write(repo_dir, "ice_in", "&grp\n  a = 1\n/\n")
    ConfigFileUpdater(repo_dir).update_params({"dynamics_nml": {"turning_angle": "REMOVE"}}, "ice_in")
    parsed = _read(repo_dir, "ice_in")
    # group is ensured to exist, but cosw/sinw should not appear
    assert parsed["dynamics_nml"] == {}


# --- atmosphere/forcing.json ---

FORCING_FILE = "atmosphere/forcing.json"


@pytest.fixture
def forcing_path(repo_dir):
    inputs = {
        "inputs": [
            {"fieldname": "tas", "filename": "INPUT/tas.nc", "cname": "tair_ai"},
            {"fieldname": "uas", "filename": "INPUT/uas.nc", "cname": "uwnd_ai"},
        ]
    }
    return _write(repo_dir, FORCING_FILE, json.dumps(inputs, indent=2) + "\n")


def _forcing_field(forcing_path: Path, fieldname: str) -> dict:
    (field,) = [f for f in json.loads(forcing_path.read_text())["inputs"] if f["fieldname"] == fieldname]
    return field


def _pert(**kwargs) -> dict:
    return {
        "type": "scaling",
        "dimension": "temporal",
        "value": "../tas.nc",
        "calendar": "forcing",
        "comment": "x",
    } | kwargs


def test_forcing_single_perturbation_is_written_as_list(repo_dir, forcing_path):
    ConfigFileUpdater(repo_dir).update_params({"tas": {"perturbations": _pert()}}, FORCING_FILE)
    assert _forcing_field(forcing_path, "tas")["perturbations"] == [_pert()]


def test_forcing_update_fields(repo_dir, forcing_path):
    params = {
        "tas": {
            "filename": "NEW/tas_{{year}}.nc",
            "perturbations": _pert(comment="scale up"),
        },
        "uas": {
            "filename": "NEW/uas_{{year}}.nc",
            "perturbations": [
                _pert(
                    type="offset",
                    dimension=["temporal", "spatial"],
                    value=["../temporal.uas.nc", "../spatial.uas.nc"],
                    calendar="experiment",
                )
            ],
        },
    }
    ConfigFileUpdater(repo_dir).update_params(params, FORCING_FILE, state={})

    tas = _forcing_field(forcing_path, "tas")
    assert tas["filename"] == "NEW/tas_{{year}}.nc"
    assert tas["cname"] == "tair_ai"
    assert tas["perturbations"] == [_pert(comment="scale up")]
    uas = _forcing_field(forcing_path, "uas")
    assert uas["filename"] == "NEW/uas_{{year}}.nc"
    assert uas["perturbations"][0]["dimension"] == ["temporal", "spatial"]
    assert forcing_path.read_text().startswith('{\n  "inputs": [\n')


def test_forcing_fieldname_not_found_raises(repo_dir, forcing_path):
    original = forcing_path.read_text()
    with pytest.raises(ValueError, match="Did not find a valid perturbed fieldname"):
        ConfigFileUpdater(repo_dir).update_params({"not_in_file": {"filename": "x.nc"}}, FORCING_FILE)
    assert forcing_path.read_text() == original


def test_forcing_all_removed_perturbations_warn_and_skip(repo_dir, forcing_path):
    params = {
        "tas": {
            "filename": "NEW/tas.nc",
            "perturbations": [
                {"type": "REMOVE", "dimension": "REMOVE", "value": "REMOVE", "calendar": "REMOVE", "comment": "REMOVE"},
                # 'type' alone being REMOVE is enough
                _pert(type="REMOVE"),
            ],
        }
    }
    with pytest.warns(UserWarning, match="are marked for removal"):
        ConfigFileUpdater(repo_dir).update_params(params, FORCING_FILE)

    tas = _forcing_field(forcing_path, "tas")
    assert tas["filename"] == "NEW/tas.nc"
    assert "perturbations" not in tas


@pytest.mark.parametrize("empty", [None, {}, []])
def test_forcing_empty_or_none_perturbations_warn_and_skip(repo_dir, forcing_path, empty):
    with pytest.warns(UserWarning, match="empty/None 'perturbations'"):
        ConfigFileUpdater(repo_dir).update_params({"tas": {"filename": "x.nc", "perturbations": empty}}, FORCING_FILE)

    tas = _forcing_field(forcing_path, "tas")
    assert tas["filename"] == "x.nc"
    assert "perturbations" not in tas


@pytest.mark.parametrize("invalid", [42, "oops", [1, 2], [{"type": "scaling"}, "invalid"]])
def test_forcing_invalid_perturbations_type_raises(repo_dir, forcing_path, invalid):
    original = forcing_path.read_text()
    with pytest.raises(TypeError, match="must be a dict or list of dicts"):
        ConfigFileUpdater(repo_dir).update_params({"tas": {"perturbations": invalid}}, FORCING_FILE)
    assert forcing_path.read_text() == original


@pytest.mark.parametrize(
    "pert",
    [
        pytest.param(_pert(type=None), id="no-type"),
        pytest.param(_pert(type=42), id="int-type"),
        pytest.param(_pert(type="nonsense"), id="wrong-type"),
        pytest.param(_pert(dimension=123), id="int-dimension"),
        pytest.param(_pert(dimension="space"), id="wrong-dimension"),
        pytest.param(_pert(dimension=["temporal"]), id="short-dimension"),
        pytest.param(_pert(dimension=["temporal", "spatial", "x"]), id="long-dimension"),
        pytest.param(_pert(calendar=""), id="empty-calendar"),
        pytest.param(_pert(calendar=None), id="no-calendar"),
        pytest.param(_pert(calendar="weird"), id="wrong-calendar"),
    ],
)
def test_forcing_invalid_perturbation_raises(repo_dir, forcing_path, pert):
    original = forcing_path.read_text()
    with pytest.raises(ValueError, match="(?i)invalid perturbation|invalid type"):
        ConfigFileUpdater(repo_dir).update_params({"tas": {"perturbations": [pert]}}, FORCING_FILE)
    assert forcing_path.read_text() == original


def test_validate_single_perturbation_wrong_type():
    with pytest.raises(ValueError, match="Invalid perturbation type"):
        _validate_single_perturbation(_pert(type="nonsense"))


@pytest.mark.parametrize("preserved", ["PRESERVE", ["PRESERVE"]])
def test_forcing_preserved_perturbations_are_untouched(repo_dir, forcing_path, preserved):
    ConfigFileUpdater(repo_dir).update_params({"tas": {"perturbations": [_pert()]}}, FORCING_FILE)
    ConfigFileUpdater(repo_dir).update_params({"tas": {"filename": "tas.nc", "perturbations": preserved}}, FORCING_FILE)

    tas = _forcing_field(forcing_path, "tas")
    assert tas["filename"] == "tas.nc"
    assert tas["perturbations"] == [_pert()]


def test_forcing_preserved_top_level_keys_are_untouched(repo_dir, forcing_path):
    params = {"tas": {"filename": "PRESERVE", "cname": "new_cname", "perturbations": _pert()}}
    ConfigFileUpdater(repo_dir).update_params(params, FORCING_FILE)

    tas = _forcing_field(forcing_path, "tas")
    assert tas["filename"] == "INPUT/tas.nc"
    assert tas["cname"] == "new_cname"
    assert tas["perturbations"] == [_pert()]


def test_forcing_perturbation_with_preserved_type_is_skipped(repo_dir, forcing_path):
    params = {
        "tas": {
            "perturbations": [
                _pert(type="PRESERVE"),
                _pert(type="offset", dimension="spatial", value="../keep.nc", calendar="experiment", comment="keep"),
            ]
        }
    }
    ConfigFileUpdater(repo_dir).update_params(params, FORCING_FILE)

    (pert,) = _forcing_field(forcing_path, "tas")["perturbations"]
    assert pert["type"] == "offset"
    assert pert["dimension"] == "spatial"
    assert pert["calendar"] == "experiment"


def test_forcing_preserved_fields_within_perturbation_are_dropped(repo_dir, forcing_path):
    ConfigFileUpdater(repo_dir).update_params({"tas": {"perturbations": [_pert(comment="PRESERVE")]}}, FORCING_FILE)

    (pert,) = _forcing_field(forcing_path, "tas")["perturbations"]
    assert "comment" not in pert
    assert pert["type"] == "scaling"
    assert pert["dimension"] == "temporal"
    assert pert["calendar"] == "forcing"


def test_forcing_no_perturbations_key(repo_dir, forcing_path):
    ConfigFileUpdater(repo_dir).update_params({"tas": {"filename": "NEW/tas.nc"}}, FORCING_FILE)

    tas = _forcing_field(forcing_path, "tas")
    assert tas == {"fieldname": "tas", "filename": "NEW/tas.nc", "cname": "tair_ai"}


def test_forcing_keeps_the_layout_of_its_lists(repo_dir):
    """
    A hand-formatted forcing.json keeps the lists it wrote on one line.
    """
    text = (
        '{\n  "inputs": [\n    {\n      "fieldname": "tas",\n      "filename": "INPUT/tas.nc",\n'
        '      "cname": "tair_ai",\n      "bounds": [1, 2]\n    }\n  ]\n}\n'
    )
    path = _write(repo_dir, FORCING_FILE, text)

    ConfigFileUpdater(repo_dir).update_params({"tas": {"cname": "tair_ai2"}}, FORCING_FILE)

    assert path.read_text() == text.replace("tair_ai", "tair_ai2")


# --- nuopc.runseq ---

RUNSEQ = "# the sequence\nrunSeq::\n@1100   \n  MED do_something   \n\n  @550\n    OCN\n  @\n@\n::\n"


def test_runseq_cpl_dt_rewrites_only_the_first_time_loop(repo_dir):
    """
    Comments, blank lines, the other lines and the trailing spaces are written as they were.
    """
    path = _write(repo_dir, "nuopc.runseq", RUNSEQ)

    ConfigFileUpdater(repo_dir).update_params({"cpl_dt": 10}, "nuopc.runseq")

    assert path.read_text() == RUNSEQ.replace("@1100", "@10")


def test_runseq_without_a_time_loop_raises(repo_dir):
    _write(repo_dir, "nuopc.runseq", "runSeq::\n  MED do_something\n  OCN do_something\n@\n::\n")

    with pytest.raises(ValueError, match="Could not find a line beginning"):
        ConfigFileUpdater(repo_dir).update_params({"cpl_dt": 10}, "nuopc.runseq")


def test_runseq_block_replaces_the_whole_sequence(repo_dir):
    path = _write(repo_dir, "nuopc.runseq", "runSeq::\n@1100\n  MED do_something\n  OCN do_something\n@\n::\n")
    block = dedent("""
        @1.0
          MED do_something2
          OCN
        @
        """)

    ConfigFileUpdater(repo_dir).update_params({"runseq_block": block}, "nuopc.runseq")

    assert path.read_text() == "runSeq::\n@1.0\n  MED do_something2\n  OCN\n@\n::\n"


def test_runseq_block_of_one_line_is_refused(repo_dir):
    text = "runSeq::\n@1100\n  MED do_something\n@\n::\n"
    path = _write(repo_dir, "nuopc.runseq", text)

    with pytest.raises(ValueError, match="at least two lines"):
        ConfigFileUpdater(repo_dir).update_params({"runseq_block": "@1\n"}, "nuopc.runseq")

    assert path.read_text() == text


# --- field_table ---


FIELD_TABLE = """# header comment
"prog_tracers","ocean_mod","temp"
horizontal-advection-scheme = mdppm
restart_file  = ocean_temp_salt.res.nc
/

# the atmosphere
 "TRACER", "atmos_mod", "sphum"
           "longname",     "specific humidity"
       "profile_type", "fixed", "surface_value=3.e-6" /
"rayleigh_damp_table","ocean_mod","rayleigh_damp_table"
"rayleigh","Lombok","itable=36,jtable=112"
"rayleigh","Ombai","itable=44,jtable=111"
"rayleigh","Torres","itable=62,jtable=106"/
"""


def _update_field_table(repo_dir, params, text=FIELD_TABLE, state=None):
    _write(repo_dir, "field_table", text)
    ConfigFileUpdater(repo_dir).update_params(params, "field_table", {} if state is None else state)
    return (repo_dir / "field_table").read_text()


def test_the_same_update_twice_changes_nothing_more(repo_dir):
    """
    The state of the positional markers makes a second run with the same input leave the file as it is.
    """
    path = _write(
        repo_dir,
        "field_table",
        """
"prog_tracers","ocean_mod","temp"
horizontal-advection-scheme = mdppm
vertical-advection-scheme = mdppm
restart_file  = ocean_temp_salt.res.nc
ppm_hlimiter = 3
ppm_vlimiter = 3
/
# added by FRE: sphum must be present in atmos
# specific humidity for moist runs
 "TRACER", "atmos_mod", "sphum"
           "longname",     "specific humidity"
           "units",        "kg/kg"
       "profile_type", "fixed", "surface_value=3.e-6" /

"rayleigh_damp_table","ocean_mod","rayleigh_damp_table"
"rayleigh","Lombok","itable=36,jtable=112,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Ombai","itable=44,jtable=111,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=106,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=107,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=108,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"
"rayleigh","Torres","itable=62,jtable=109,ktable_1=1,ktable_2=50,rayleigh_damp_table=5400"/
""",
    )

    params = {
        "temp": {
            "ocean_mod": {
                "prog_tracers": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        {
                            "key": "restart_file",
                            "value": "ocean_temp_salt2.res.nc",
                        },
                        {
                            "key": "ppm_hlimiter",
                            "value": "4",
                        },
                    ]
                }
            }
        },
        "sphum": {
            "atmos_mod": {
                "TRACER": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        {
                            "key": "profile_type",
                            "value": "fixed",
                            "params": {"surface_value": "1.e-6"},
                        },
                    ]
                }
            }
        },
        "rayleigh_damp_table": {
            "ocean_mod": {
                "rayleigh_damp_table": {
                    "methods": [
                        PRESERVED,
                        PRESERVED,
                        PRESERVED,
                        REMOVED,
                        {
                            "key": "rayleigh",
                            "value": "Ombai",
                            "params": {
                                "itable": "0",
                                "jtable": "0",
                                "ktable_1": "0",
                                "ktable_2": "0",
                                "rayleigh_damp_table": "0",
                            },
                        },
                    ]
                }
            }
        },
    }

    state = {}

    ConfigFileUpdater(repo_dir).update_params(params, "field_table", state)
    after_first = path.read_text()

    ConfigFileUpdater(repo_dir).update_params(params, "field_table", state)

    assert path.read_text() == after_first
    assert any(key.endswith("::BASE") for key in state)


def test_prune_empty_field_table_config_deletes_empty_entries():
    config = {
        "rayleigh_damp_table": {
            "ocean_mod": {
                "rayleigh_damp_table": {"methods": []},  # now should be deleted
            }
        },
        "temp": {
            "ocean_mod": {
                "prog_tracers": {"methods": [{"key": "k", "value": "v"}]},
            }
        },
    }

    prune_empty_field_table_config(config)

    assert "rayleigh_damp_table" not in config
    assert "temp" in config
    assert "ocean_mod" in config["temp"]
    assert "prog_tracers" in config["temp"]["ocean_mod"]


def test_only_the_changed_lines_are_rewritten(repo_dir):
    """
    Comments, blank lines and the layout of the lines that stay are kept, a value in the notation of its line.
    """
    params = {
        "temp": {"ocean_mod": {"prog_tracers": {"methods": [PRESERVED, {"key": "restart_file", "value": "new.nc"}]}}},
    }

    assert _update_field_table(repo_dir, params) == FIELD_TABLE.replace("ocean_temp_salt.res.nc", "new.nc")


def test_a_method_is_removed_and_a_record_changed(repo_dir):
    params = {
        "temp": {"ocean_mod": {"prog_tracers": {"methods": [REMOVED, PRESERVED]}}},
        "rayleigh_damp_table": {
            "ocean_mod": {
                "rayleigh_damp_table": {
                    "methods": [
                        PRESERVED,
                        {"key": "rayleigh", "value": "Ombai", "params": {"itable": 45}},
                        REMOVED,
                    ]
                }
            }
        },
    }

    updated = _update_field_table(repo_dir, params)

    records = FieldTableParser().parse(updated)["rayleigh_damp_table"]["ocean_mod"]["rayleigh_damp_table"]["rayleigh"]
    assert records == [
        {"value": "Lombok", "itable": 36, "jtable": 112},
        {"value": "Ombai", "itable": 45, "jtable": 111},
    ]
    assert "horizontal-advection-scheme" not in updated
    assert updated.startswith("# header comment\n")
    assert "# the atmosphere" in updated
    assert updated.endswith('"rayleigh","Ombai","itable=45,jtable=111"/\n')


def test_a_new_entry_is_added_after_the_others(repo_dir):
    params = {"age": {"ocean_mod": {"prog_tracers": {"methods": [{"key": "restart_file", "value": "age.nc"}]}}}}

    updated = _update_field_table(repo_dir, params)

    # after the last entry of its type, written like the entry before it
    new_entry = '"prog_tracers","ocean_mod","age"\nrestart_file  = age.nc\n/\n'
    assert updated == FIELD_TABLE.replace("/\n\n# the atmosphere", "/\n" + new_entry + "\n# the atmosphere")


def test_an_entry_left_with_no_methods_is_removed(repo_dir):
    params = {"temp": {"ocean_mod": {"prog_tracers": {"methods": [REMOVED, REMOVED]}}}}

    updated = _update_field_table(repo_dir, params)

    assert "temp" not in updated
    assert "# the atmosphere" in updated
    assert "prog_tracers" not in FieldTableParser().parse(updated)


def test_a_header_is_found_in_any_case(repo_dir):
    methods = [PRESERVED, PRESERVED, {"key": "units", "value": "kg/kg"}]
    params = {"SPHUM": {"ATMOS_MOD": {"tracer": {"methods": methods}}}}

    updated = _update_field_table(repo_dir, params)

    assert FieldTableParser().parse(updated)["tracer"]["atmos_mod"]["sphum"]["units"] == "kg/kg"
    assert updated.count('"TRACER"') == 1


def test_a_value_of_another_type_is_written_anew(repo_dir):
    params = {"temp": {"ocean_mod": {"prog_tracers": {"methods": [PRESERVED, {"key": "restart_file", "value": 5}]}}}}

    updated = _update_field_table(repo_dir, params)

    assert FieldTableParser().parse(updated)["prog_tracers"]["ocean_mod"]["temp"]["restart_file"] == 5
    assert "ocean_temp_salt.res.nc" not in updated


@pytest.mark.parametrize(
    ("field", "model", "field_type"),
    [("liq_wat", "atmos_mod", "TRACER"), ("liq_wat", "new_mod", "TRACER"), ("x", "ocean_mod", "diag_tables")],
)
def test_a_new_header_with_part_of_its_path_in_the_file(repo_dir, field, model, field_type):
    params = {field: {model: {field_type: {"methods": [{"key": "longname", "value": "cloud"}]}}}}

    updated = _update_field_table(repo_dir, params)

    assert FieldTableParser().parse(updated)[field_type][model][field] == {"longname": "cloud"}
    assert FieldTableParser().parse(updated)["prog_tracers"]["ocean_mod"]["temp"]


def test_a_method_with_and_without_parameters_is_refused(repo_dir):
    methods = [{"key": "a", "value": "x"}, {"key": "a", "value": "y", "params": {"p": 1}}]
    params = {"new": {"ocean_mod": {"prog_tracers": {"methods": methods}}}}
    methods.insert(0, {"key": "a", "value": "z", "params": {"p": 2}})

    with pytest.raises(ValueError, match="both a method with parameters and one without"):
        _update_field_table(repo_dir, params)
