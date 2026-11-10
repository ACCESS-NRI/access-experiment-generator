import json

import pytest

from experiment_generator.source_experiment import _restart_path, apply_source_experiment


def write_job(archive, run, job_id="100.gadi-pbs.json", **overrides):
    """
    Write one payu job metadata file, as payu does after each run.
    """
    job_dir = archive / "payu_jobs" / str(run) / "run"
    job_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "payu_current_run": run,
        "payu_version": "1.3.6",
        "payu_control_path": str(archive.parent / "control"),
        "payu_archive_path": str(archive),
        "payu_run_id": f"{run:040d}",
        "payu_run_status": 0,
        "experiment_metadata": {"experiment_uuid": f"uuid-{run}"},
    }
    job.update(overrides)
    job_file = job_dir / job_id
    job_file.write_text(json.dumps(job), encoding="utf-8")
    return job_file


@pytest.fixture
def source_run(tmp_path):
    """
    A control directory and the archive of three runs made from it.
    """
    (tmp_path / "control").mkdir()
    archive = tmp_path / "archive"
    for run in (1, 2, 3):
        write_job(archive, run)
    return archive


def test_no_source_experiment_path_is_a_noop(tmp_path):
    indata = {"repository_url": "https://github.com/ACCESS-NRI/access-experiment-generator.git"}
    apply_source_experiment(indata)
    assert indata == {"repository_url": "https://github.com/ACCESS-NRI/access-experiment-generator.git"}


def test_resolves_the_named_run(tmp_path, source_run):
    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    apply_source_experiment(indata)

    assert indata["repository_url"] == str(tmp_path / "control")
    assert indata["start_point"] == f"{3:040d}"
    assert indata["parent_experiment"] == "uuid-3"
    assert "restart_path" not in indata


def test_source_run_is_required_and_lists_what_is_there(tmp_path, source_run):
    """
    The most recent run of an experiment that is still running moves, so it is never implied.
    """
    indata = {"source_experiment_path": str(source_run)}
    with pytest.raises(ValueError, match=r"`source_run` must name the run.*\[1, 2, 3\]"):
        apply_source_experiment(indata)


def test_resolves_from_control_directory(tmp_path, source_run):
    """
    A control directory whose `archive` points at the archive works just as well.
    """
    (tmp_path / "control" / "archive").symlink_to(source_run)
    indata = {"source_experiment_path": str(tmp_path / "control"), "source_run": 3}
    apply_source_experiment(indata)
    assert indata["start_point"] == f"{3:040d}"


def test_resolves_directly_from_a_job_file(tmp_path, source_run):
    """
    A job JSON identifies its own run, so source_run is inferred.
    """
    job_file = source_run / "payu_jobs" / "2" / "run" / "100.gadi-pbs.json"
    indata = {"source_experiment_path": str(job_file)}
    apply_source_experiment(indata)

    assert indata["source_run"] == 2
    assert indata["repository_url"] == str(tmp_path / "control")
    assert indata["start_point"] == f"{2:040d}"
    assert indata["parent_experiment"] == "uuid-2"


def test_job_file_must_contain_a_json_object(source_run):
    job_file = write_job(source_run, 2)
    job_file.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        apply_source_experiment({"source_experiment_path": str(job_file)})


def test_job_file_must_be_in_a_payu_archive(tmp_path):
    job_file = tmp_path / "job.json"
    job_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="must be under.*payu_jobs"):
        apply_source_experiment({"source_experiment_path": str(job_file)})


def test_job_file_run_must_be_an_integer(source_run):
    job_file = write_job(source_run, 2, payu_current_run="2")

    with pytest.raises(ValueError, match=r"invalid `payu_current_run` '2'"):
        apply_source_experiment({"source_experiment_path": str(job_file)})


def test_job_file_run_must_match_its_directory(source_run):
    job_file = write_job(source_run, 2, payu_current_run=3)

    with pytest.raises(ValueError, match=r"records `payu_current_run` 3.*stored under run 2"):
        apply_source_experiment({"source_experiment_path": str(job_file)})


def test_job_file_rejects_a_different_source_run(source_run):
    job_file = source_run / "payu_jobs" / "2" / "run" / "100.gadi-pbs.json"
    indata = {"source_experiment_path": str(job_file), "source_run": 1}

    with pytest.raises(ValueError, match=r"`source_run` is 1.*records run 2"):
        apply_source_experiment(indata)


def test_job_file_must_record_a_successful_attempt(source_run):
    job_file = write_job(source_run, 2, payu_run_status=1)
    indata = {"source_experiment_path": str(job_file)}

    with pytest.raises(ValueError, match="is not a successful attempt"):
        apply_source_experiment(indata)


def test_source_run_selects_an_earlier_run(tmp_path, source_run):
    indata = {"source_experiment_path": str(source_run), "source_run": 1}
    apply_source_experiment(indata)
    assert indata["start_point"] == f"{1:040d}"
    assert indata["parent_experiment"] == "uuid-1"


def test_resubmitted_run_uses_the_attempt_that_succeeded(tmp_path, source_run):
    """
    A resubmitted run writes one file per attempt; only the successful one produced output.
    """
    write_job(source_run, 3, job_id="100.gadi-pbs.json", payu_run_id="a" * 40, payu_run_status=1)
    write_job(source_run, 3, job_id="200.gadi-pbs.json", payu_run_id="b" * 40, payu_run_status=0)
    write_job(source_run, 3, job_id="300.gadi-pbs.json", payu_run_id=None, payu_run_status=None)

    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    apply_source_experiment(indata)
    assert indata["start_point"] == "b" * 40


def test_run_with_no_successful_attempt(tmp_path, source_run):
    write_job(source_run, 3, job_id="100.gadi-pbs.json", payu_run_status=1)  # overwrites the fixture's
    write_job(source_run, 3, job_id="200.gadi-pbs.json", payu_run_status=1)

    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    with pytest.raises(ValueError, match="no attempt recorded as successful"):
        apply_source_experiment(indata)


def test_conflicting_yaml_values_are_rejected(tmp_path, source_run):
    indata = {"source_experiment_path": str(source_run), "source_run": 3, "start_point": "abc1234"}
    with pytest.raises(ValueError, match=r"metadata conflicts.*`start_point` is 'abc1234'"):
        apply_source_experiment(indata)

    # Do not partially apply source values when one of them conflicts.
    assert "repository_url" not in indata


def test_unknown_source_run_lists_what_is_available(tmp_path, source_run):
    indata = {"source_experiment_path": str(source_run), "source_run": 9}
    with pytest.raises(ValueError, match=r"available runs are \[1, 2, 3\]"):
        apply_source_experiment(indata)


def test_directory_without_payu_jobs(tmp_path):
    (tmp_path / "not_an_archive").mkdir()
    indata = {"source_experiment_path": str(tmp_path / "not_an_archive")}
    with pytest.raises(ValueError, match="holds no payu_jobs/ directory"):
        apply_source_experiment(indata)


def test_metadata_from_an_older_payu(tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    write_job(archive, 1, payu_run_id=None)
    indata = {"source_experiment_path": str(archive), "source_run": 1}
    with pytest.raises(ValueError, match="older than 1.2"):
        apply_source_experiment(indata)


def test_falls_back_to_the_bare_clone_when_the_control_is_gone(tmp_path, source_run, capsys):
    """
    `payu sync` leaves a bare clone beside the synced archive, holding the same commits.
    """
    (tmp_path / "control").rmdir()
    (source_run / "git-runlog").mkdir()

    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    apply_source_experiment(indata)

    assert indata["repository_url"] == str(source_run / "git-runlog")
    assert "is gone, using the bare clone" in capsys.readouterr().out


def test_control_gone_and_no_bare_clone(tmp_path, source_run):
    (tmp_path / "control").rmdir()
    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    with pytest.raises(ValueError, match="no git-runlog bare clone"):
        apply_source_experiment(indata)


def test_the_control_directory_wins_when_it_is_there(tmp_path, source_run):
    (source_run / "git-runlog").mkdir()
    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    apply_source_experiment(indata)
    assert indata["repository_url"] == str(tmp_path / "control")


def test_source_restart_uses_the_restart_of_the_chosen_run(tmp_path, source_run):
    for number in (1, 2, 3):
        (source_run / f"restart{number:03d}").mkdir()

    indata = {"source_experiment_path": str(source_run), "source_run": 2, "source_restart": True}
    apply_source_experiment(indata)
    assert indata["restart_path"] == str(source_run / "restart002")


def test_restart_requires_an_existing_archive(tmp_path):
    with pytest.raises(ValueError, match="Archive.*does not exist"):
        _restart_path(tmp_path / "missing-archive", 2)


def test_without_source_restart_the_control_starts_cold(tmp_path, source_run, capsys):
    (source_run / "restart003").mkdir()
    indata = {"source_experiment_path": str(source_run), "source_run": 3}
    apply_source_experiment(indata)

    assert "restart_path" not in indata
    assert "starts from cold" in capsys.readouterr().out


def test_pruned_restart_names_the_runs_that_can_be_continued(tmp_path, source_run):
    """
    Pairing one run's configuration with another run's state is not offered as a fix.
    """
    for number in (1, 3):
        (source_run / f"restart{number:03d}").mkdir()
    (source_run / "restart004-old").mkdir()
    (source_run / "restart005").touch()

    indata = {"source_experiment_path": str(source_run), "source_run": 2, "source_restart": True}
    with pytest.raises(ValueError, match=r"run 2 cannot be continued from.*\[1, 3\]"):
        apply_source_experiment(indata)


def test_explicit_restart_path_is_not_called_a_cold_start(tmp_path, source_run, capsys):
    indata = {"source_experiment_path": str(source_run), "source_run": 3, "restart_path": "/somewhere/restart004"}
    apply_source_experiment(indata)
    assert "starts from cold" not in capsys.readouterr().out


def test_payu_jobs_holding_no_run_metadata(tmp_path):
    """
    A `payu_jobs` directory can exist while holding nothing usable.
    """
    jobs = tmp_path / "archive" / "payu_jobs"
    (jobs / "logs").mkdir(parents=True)  # not a run number
    (jobs / "4" / "run").mkdir(parents=True)  # a run number, but no job file

    indata = {"source_experiment_path": str(tmp_path / "archive"), "source_run": 4}
    with pytest.raises(ValueError, match="No payu run metadata found"):
        apply_source_experiment(indata)


def test_restart_uses_the_current_location_of_a_moved_archive(tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    job_file = write_job(archive, 1, payu_archive_path=str(tmp_path / "vanished"))
    (archive / "restart001").mkdir()

    indata = {"source_experiment_path": str(job_file), "source_restart": True}
    apply_source_experiment(indata)
    assert indata["source_run"] == 1
    assert indata["restart_path"] == str(archive / "restart001")


def test_metadata_without_an_experiment_uuid(tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    write_job(archive, 1, experiment_metadata={})

    indata = {"source_experiment_path": str(archive), "source_run": 1}
    apply_source_experiment(indata)
    assert "parent_experiment" not in indata


def test_an_explicit_value_matching_the_archive_is_not_reported(tmp_path, source_run, capsys):
    indata = {"source_experiment_path": str(source_run), "source_run": 3, "start_point": f"{3:040d}"}
    apply_source_experiment(indata)

    out = capsys.readouterr().out
    assert "start_point" not in out
    assert "keeping" not in out


def test_source_restart_and_restart_path_together(tmp_path, source_run):
    """
    One asks for the restart of `source_run` to be resolved, the other names one; not both.
    """
    (source_run / "restart003").mkdir()
    indata = {
        "source_experiment_path": str(source_run),
        "source_run": 3,
        "source_restart": True,
        "restart_path": str(source_run / "restart003"),
    }
    with pytest.raises(ValueError, match="Set only one of them"):
        apply_source_experiment(indata)


@pytest.mark.parametrize("source_run", ["3", 3.0, True])
def test_source_run_must_be_an_integer(source_run, tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    write_job(archive, 3)

    indata = {"source_experiment_path": str(archive), "source_run": source_run}
    with pytest.raises(ValueError, match="must be an integer"):
        apply_source_experiment(indata)


def test_source_restart_must_be_a_boolean(source_run):
    indata = {"source_experiment_path": str(source_run), "source_run": 3, "source_restart": "false"}
    with pytest.raises(ValueError, match="must be true or false"):
        apply_source_experiment(indata)


def test_metadata_run_must_match_its_directory(tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    write_job(archive, 3, payu_current_run=2)

    indata = {"source_experiment_path": str(archive), "source_run": 3}
    with pytest.raises(ValueError, match=r"records `payu_current_run` 2.*stored under run 3"):
        apply_source_experiment(indata)


def test_experiment_metadata_must_be_a_mapping(tmp_path):
    archive = tmp_path / "archive"
    (tmp_path / "control").mkdir()
    write_job(archive, 1, experiment_metadata="not-a-mapping")

    indata = {"source_experiment_path": str(archive), "source_run": 1}
    with pytest.raises(ValueError, match="invalid `experiment_metadata`"):
        apply_source_experiment(indata)
