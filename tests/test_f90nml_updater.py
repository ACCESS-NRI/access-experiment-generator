import math
import numpy as np
import pytest
from experiment_generator.f90nml_updater import F90NamelistUpdater, format_nml_params
import f90nml


def test_update_nml_params_invalid_and_valid_group_value(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    nml_file = repo_dir / "dummy.nml"
    nml_file.write_text("&grp\n /\n")
    updater = F90NamelistUpdater(repo_dir)
    # group value must be dict
    params = {"grp": 1}
    with pytest.raises(ValueError):
        updater.update_nml_params(params, nml_file.name)

    # group value now is a dict
    params = {"grp": {"inner": 1}}
    updater.update_nml_params(params, nml_file.name)
    parsed = f90nml.read(nml_file)

    assert parsed["grp"]["inner"] == 1


def test_update_nml_params_remove(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    nml_file = repo_dir / "ice_in"
    nml_file.write_text("&grp\n  inner = 1/\n")
    updater = F90NamelistUpdater(repo_dir)

    # set value to None
    updater.update_nml_params({"grp": {"inner": None}}, nml_file.name)
    parsed = f90nml.read(nml_file)
    assert "inner" in parsed["grp"]
    assert parsed["grp"]["inner"] == "None"  # f90nml saw the literal string

    # set value to string `REMOVE`
    updater.update_nml_params({"grp": {"inner": 2}}, nml_file.name)
    updater.update_nml_params({"grp": {"inner": "REMOVE"}}, nml_file.name)
    parsed = f90nml.read(nml_file)
    assert "inner" not in parsed["grp"]


# @pytest.mark.parametrize("angle", [0, 30, 90])
# def test_turning_angle_writes_cosw_sinw(tmp_path, angle):
#     repo = tmp_path / "repo"
#     repo.mkdir()

#     nml_file = repo / "cice_in.nml"
#     nml_file.write_text("&ice_nml\n /\n")

#     updater = F90NamelistUpdater(repo)
#     updater.update_nml_params({"ice_nml": {"turning_angle": angle}}, nml_file.name)

#     parsed = f90nml.read(nml_file)

#     rad = math.radians(angle)

#     assert np.isclose(parsed["dynamics_nml"]["cosw"], math.cos(rad), atol=1e-12)
#     assert np.isclose(parsed["dynamics_nml"]["sinw"], math.sin(rad), atol=1e-12)


def test_group_created_and_vars_set(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    nml_file = repo / "grp.nml"
    nml_file.write_text("&dummy/\n")

    updater = F90NamelistUpdater(repo)
    updater.update_nml_params({"ice_nml": {"A": 1, "B": 2}}, nml_file.name)

    parsed = f90nml.read(nml_file)
    assert parsed["ice_nml"]["A"] == 1
    assert parsed["ice_nml"]["B"] == 2


def test_format_nml_params_boolean_and_list(tmp_path):

    nml_file = tmp_path / "test.nml"
    nml_file.write_text(
        "&tgrp\n" "    flag   = .false.\n" "    items  = 'x', 'y'\n" "/\n",
    )

    format_nml_params(
        nml_file.as_posix(),
        {"tgrp": {"flag": True, "items": "'a', 'b'"}},
    )

    txt = nml_file.read_text()
    assert "flag = .true." in txt
    assert "items = 'a', 'b'" in txt


def test_format_nml_params_skips_comment_lines(tmp_path):
    nml_file = tmp_path / "test.nml"
    nml_file.write_text(
        "&dummy\n" "! flag should not be touched here\n" "    flag = .false.\n" "/\n",
    )

    # expect only the real assignment line to change
    format_nml_params(
        nml_file.as_posix(),
        {"dummy": {"flag": True}},
    )

    lines = nml_file.read_text().splitlines()
    # comment line remains unchanged
    assert lines[1].startswith("! flag")
    # assignment line updated
    assert "flag = .true." in lines[2]


def test_format_nml_params_exact_varname_match(tmp_path):
    nml_file = tmp_path / "test.nml"
    nml_file.write_text("&dummy\n" "    ! days = 99\n" "    days = 30\n" "    days_to_increment = 5\n" "/\n")

    format_nml_params(
        nml_file.as_posix(),
        {"dummy": {"days": 31}},
    )

    lines = nml_file.read_text().splitlines()
    assert lines[1].strip() == "! days = 99"
    assert lines[2].strip() == "days = 31"
    assert lines[3].strip() == "days_to_increment = 5"


def test_turning_angle_compute_and_deletes_key(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "ice_in"
    f.write_text("&dynamics_nml  \n/\n")
    updater = F90NamelistUpdater(repo)
    updater.update_nml_params({"dynamics_nml": {"turning_angle": 30}}, f.name)
    parsed = f90nml.read(f)

    assert "turning_angle" not in parsed["dynamics_nml"]
    rad = math.radians(30)
    assert np.isclose(parsed["dynamics_nml"]["cosw"], math.cos(rad))
    assert np.isclose(parsed["dynamics_nml"]["sinw"], math.sin(rad))


def test_turning_angle_under_other_group_does_not_compute_cos_sin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "ice_in"
    f.write_text("&grp \n/\n")
    updater = F90NamelistUpdater(repo)
    updater.update_nml_params({"grp": {"turning_angle": 20}}, f.name)
    parsed = f90nml.read(f)
    # turning_angle remains/updates in grp
    assert parsed["grp"]["turning_angle"] == 20.0
    # no cos/sin created
    assert "dynamics_nml" not in parsed


def test_turning_angle_remove_only_affects_dynamics_cos_sin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "ice_in"
    # seed cos/sin and a turning_angle under grp (not dynamics)
    f.write_text("&grp  \n/\n&dynamics_nml\n  cosw = 0.5\n  sinw = 0.5\n/\n")
    updater = F90NamelistUpdater(repo)
    # REMOVE under grp should not touch cos/sin; turning_angle in grp handled by normal loop
    updater.update_nml_params({"grp": {"turning_angle": "REMOVE"}}, f.name)
    parsed = f90nml.read(f)
    assert parsed["dynamics_nml"]["cosw"] == 0.5
    assert parsed["dynamics_nml"]["sinw"] == 0.5

    # REMOVE under dynamics_nml drops cos/sin and deletes the key
    updater.update_nml_params({"dynamics_nml": {"turning_angle": "REMOVE"}}, f.name)
    parsed = f90nml.read(f)
    assert "dynamics_nml" in parsed
    assert "cosw" not in parsed["dynamics_nml"]
    assert "sinw" not in parsed["dynamics_nml"]
    assert parsed["dynamics_nml"] == {}


def test_turning_angle_preserve_requires_existing_cos_sin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "ice_in"
    # dynamics_nml with NO cos and sin
    f.write_text("&dynamics_nml  \n/\n")
    updater = F90NamelistUpdater(repo)

    # PRESERVE but no cos and sin -> should raise
    with pytest.raises(ValueError):
        updater.update_nml_params({"dynamics_nml": {"turning_angle": "PRESERVE"}}, f.name)


def test_turning_angle_preserve_keeps_existing_cos_sin(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "ice_in"
    f.write_text("&dynamics_nml\n cosw = 0.1\n  sinw = 0.2\n/\n")
    updater = F90NamelistUpdater(repo)
    updater.update_nml_params({"dynamics_nml": {"turning_angle": "PRESERVE"}}, f.name)
    parsed = f90nml.read(f)

    assert "turning_angle" not in parsed["dynamics_nml"]
    assert parsed["dynamics_nml"]["cosw"] == 0.1
    assert parsed["dynamics_nml"]["sinw"] == 0.2
