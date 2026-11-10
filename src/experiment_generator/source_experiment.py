"""Resolve a new experiment's base from metadata written by payu.

Payu writes `<archive>/payu_jobs/<run>/run/<jobid>.json` for each run attempt.
The source can be named by its control directory, archive directory, or one of
these job JSON files; its metadata supplies the repository, exact commit, and UUID.
"""

import json
from pathlib import Path

PAYU_JOBS_DIR = "payu_jobs"


def _read_job(job_file: Path) -> dict:
    """Read one payu job metadata file."""
    job = json.loads(job_file.read_text(encoding="utf-8"))
    if not isinstance(job, dict):
        raise ValueError(f"{job_file} must contain a JSON object!")
    return job


def _archive_path(job_file: Path) -> Path:
    """Return the archive containing a payu job metadata file."""
    run_dir = job_file.parent.parent
    if (
        job_file.suffix != ".json"
        or job_file.parent.name != "run"
        or run_dir.parent.name != PAYU_JOBS_DIR
        or not run_dir.name.isdigit()
    ):
        expected = f"<archive>/{PAYU_JOBS_DIR}/<run>/run/<jobid>.json"
        raise ValueError(f"Job metadata {job_file} must be under {expected}!")
    return run_dir.parent.parent


def _job_metadata(path: Path, source_run: int | None) -> tuple[Path, Path, dict]:
    """
    Select one successful payu job and return its file, archive, and metadata.

    A job JSON identifies its own run. An archive or control directory needs
    `source_run` because it can contain several runs and submission attempts.
    """
    if source_run is not None and (isinstance(source_run, bool) or not isinstance(source_run, int)):
        raise ValueError(f"`source_run` must be an integer, got {source_run!r}!")

    # A job JSON is already an exact selection, so source_run can be inferred.
    if path.is_file():
        archive_path = _archive_path(path)
        job = _read_job(path)
        recorded_run = job.get("payu_current_run")
        if isinstance(recorded_run, bool) or not isinstance(recorded_run, int):
            raise ValueError(f"{path} has invalid `payu_current_run` {recorded_run!r}; expected an integer!")
        if recorded_run != int(path.parent.parent.name):
            raise ValueError(
                f"{path} records `payu_current_run` {recorded_run}, "
                f"but it is stored under run {path.parent.parent.name}!"
            )
        if source_run is not None and source_run != recorded_run:
            raise ValueError(f"`source_run` is {source_run}, but job metadata {path} records run {recorded_run}!")
        if job.get("payu_run_status") != 0:
            raise ValueError(
                f"Job metadata {path} is not a successful attempt "
                f"(`payu_run_status` is {job.get('payu_run_status')!r})!"
            )
        return path, archive_path, job

    # A control directory has an archive link; an archive has payu_jobs directly.
    for p in (path, path / "archive"):
        jobs = p / PAYU_JOBS_DIR
        if jobs.is_dir():
            break
    else:
        raise ValueError(
            f"`source_experiment_path` {path} holds no {PAYU_JOBS_DIR}/ directory "
            f"(looked in {path} and {path / 'archive'})! "
        )

    runs_path = {}
    for run_dir in jobs.iterdir():
        if run_dir.name.isdigit():
            job_files = sorted((run_dir / "run").glob("*.json"))
            if job_files:
                runs_path[int(run_dir.name)] = job_files
    if not runs_path:
        raise ValueError(f"No payu run metadata found under {jobs}!")

    # The newest run can still be changing, so directory input never guesses a run.
    if source_run is None:
        raise ValueError(f"`source_run` must name the run to start from; {jobs} holds runs {sorted(runs_path)}!")
    if source_run not in runs_path:
        raise ValueError(f"`source_run` {source_run} is not under {jobs}, available runs are {sorted(runs_path)}!")

    # payu writes one file per submission attempt, so a run that crashed and was
    # resubmitted has several. Only the attempt with `payu_run_status` 0 finished
    # and produced this run's output; the rest failed, some before recording a commit.
    for job_file in runs_path[source_run]:
        job = _read_job(job_file)
        if job.get("payu_run_status") == 0:
            if job.get("payu_current_run") != source_run:
                raise ValueError(
                    f"{job_file} records `payu_current_run` {job.get('payu_current_run')!r}, "
                    f"but it is stored under run {source_run}!"
                )
            return job_file, p, job
    raise ValueError(f"`source_run` {source_run} has no attempt recorded as successful under {jobs}!")


def _restart_path(archive_path: Path, source_run: int) -> Path:
    """
    Resolve the restart that run `source_run` ended at.

    `restartNNN` is the state produced by run NNN's configuration. Using the exact
    matching run avoids silently pairing one run's configuration with another's state.
    """
    if not archive_path.is_dir():
        raise ValueError(f"Archive {archive_path} does not exist!")

    path = archive_path / f"restart{source_run:03d}"
    if not path.is_dir():
        kept = []
        for entry in archive_path.iterdir():
            number = entry.name.removeprefix("restart")
            if entry.is_dir() and entry.name.startswith("restart") and number.isdigit():
                kept.append(int(number))
        kept.sort()
        raise ValueError(
            f"Restart {path} is not in the archive, so run {source_run} cannot be continued from; "
            f"runs whose restarts are still kept are {kept}! Set `restart_path` yourself to start "
            f"from another run's state, which is not checked against this run's configuration."
        )
    return path


def _repository(archive_path: Path, job_file: Path, payu_control_path: str) -> str:
    """
    Where to clone the source run's configuration.

    The control directory is authoritative, but it can have been deleted, moved, or left
    in a home directory nobody else can read. `payu sync` leaves a bare clone of it beside
    the synced archive, holding the same commits, so fall back to that when there is one.
    """
    if Path(payu_control_path).is_dir():
        return payu_control_path

    runlog = archive_path / "git-runlog"
    if runlog.is_dir():
        print(f" -- control directory {payu_control_path} is gone, using the bare clone {runlog}")
        return str(runlog)

    raise ValueError(
        f"Control directory {payu_control_path} recorded in {job_file} no longer exists, and the "
        f"archive holds no git-runlog bare clone, so this run's configuration cannot be recovered!"
    )


def apply_source_experiment(indata: dict) -> None:
    """
    Fill the control experiment source in `indata` from an archived payu run in place.

    source_experiment_path (str): A control directory, an archive directory, or a
        `<archive>/payu_jobs/<run>/run/<jobid>.json` file.
    source_run (int): Which run to use. Required for a directory; inferred from a job JSON.
    source_restart (bool): Continue from where that run ended, rather than starting from cold.
    """
    base = indata.get("source_experiment_path")
    if not base:
        return

    source_restart = indata.get("source_restart", False)
    if not isinstance(source_restart, bool):
        raise ValueError(f"`source_restart` must be true or false, got {source_restart!r}!")

    if source_restart and indata.get("restart_path"):
        raise ValueError(
            f"`source_restart` and `restart_path` ({indata['restart_path']}) are both set, but "
            "`source_restart` resolves the restart of `source_run` while `restart_path` names one "
            "yourself. Set only one of them!"
        )

    job_file, archive_path, job = _job_metadata(Path(base).expanduser().resolve(), indata.get("source_run"))

    required_fields = ("payu_control_path", "payu_run_id")
    missing_fields = [key for key in required_fields if not job.get(key)]
    if missing_fields:
        raise ValueError(
            f"{job_file} is missing required metadata {missing_fields}. It may be incomplete or "
            "have been written by a payu older than 1.2. Point at the archive and name the run "
            "with `source_run` to select the attempt that succeeded."
        )

    experiment_metadata = job.get("experiment_metadata") or {}
    if not isinstance(experiment_metadata, dict):
        raise ValueError(f"{job_file} has invalid `experiment_metadata`; expected a mapping!")

    resolved = {
        "source_run": job["payu_current_run"],
        "repository_url": _repository(archive_path, job_file, job["payu_control_path"]),
        "start_point": job["payu_run_id"],
        "parent_experiment": experiment_metadata.get("experiment_uuid"),
    }
    if source_restart:
        # Use the archive holding the selected JSON, not its possibly stale recorded path.
        resolved["restart_path"] = str(_restart_path(archive_path, job["payu_current_run"]))

    # Validate everything before changing indata, so a conflict cannot leave a partial result.
    for key, value in resolved.items():
        configured = indata.get(key)
        if value is not None and configured not in (None, "", value):
            raise ValueError(
                f"Source-run metadata conflicts with the YAML input: `{key}` is {configured!r}, "
                f"but the source run records {value!r}. Remove the explicit value or omit "
                "`source_experiment_path`."
            )

    print(f"-- Source run metadata: {job_file}")
    for k, v in resolved.items():
        if v is None:
            continue
        if indata.get(k) in (None, ""):
            indata[k] = v
            print(f" -- {k}: {v}")

    if not indata.get("restart_path"):
        print(" -- `restart_path` is not specified, so the control experiment starts from cold")
        print(f" -- set `source_restart: true` to continue from the end of run {job['payu_current_run']} instead")
