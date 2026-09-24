"""
Resolve the base of a new experiment from an archived payu run.

For every run, payu records `<archive>/payu_jobs/<run>/run/<jobid>.json`, which holds
the control directory, the runlog commit that produced the run, and the experiment
UUID. That is everything needed to start a new experiment from an archived run, so
the run configuration never has to be copied out of an output directory.
"""

import json
from pathlib import Path

PAYU_JOBS_DIR = "payu_jobs"


def _read_job(job_file: Path) -> dict:
    return json.loads(job_file.read_text(encoding="utf-8"))


def _job_metadata(path: Path, base_run: int | None) -> tuple[Path, dict]:
    """
    Read the payu job metadata for run `base_run`.

    `path` may be an archive directory, a control directory,
    or a job metadata file (`payu_jobs/<run>/run/<jobid>.json`).
    """
    if path.is_file():
        return path, _read_job(path)

    for p in (path, path / "archive"):
        jobs = p / PAYU_JOBS_DIR
        if jobs.is_dir():
            break
    else:
        raise ValueError(
            f"`base_archive_path` {path} holds no {PAYU_JOBS_DIR}/ directory "
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

    # the most recent run of an experiment that is still running moves, so it is never chosen here
    if base_run is None:
        raise ValueError(f"`base_run` must name the run to start from; {jobs} holds runs {sorted(runs_path)}!")
    if base_run not in runs_path:
        raise ValueError(f"`base_run` {base_run} is not under {jobs}, available runs are {sorted(runs_path)}!")

    # payu writes one file per submission attempt, so a run that crashed and was
    # resubmitted has several. Only the attempt with `payu_run_status` 0 finished
    # and produced this run's output; the rest failed, some before recording a commit.
    for job_file in runs_path[base_run]:
        job = _read_job(job_file)
        if job.get("payu_run_status") == 0:
            return job_file, job
    raise ValueError(f"`base_run` {base_run} has no attempt recorded as successful under {jobs}!")


def _restart_path(archive_path: Path, base_run: int) -> Path:
    """
    Resolve the restart that run `base_run` ended at.

    A restart is never chosen freely, that is, the state at `restartXXX` was produced by the
    configuration of outputXXX, while configurations may drift between runs, so pairing one
    run's configuration with another run's state is quietly incoherent.
    """
    if not archive_path.is_dir():
        raise ValueError(f"Archive {archive_path} recorded in the run metadata does not exist!")

    path = archive_path / f"restart{base_run:03d}"
    if not path.is_dir():
        kept = sorted(int(d.name.removeprefix("restart")) for d in archive_path.glob("restart[0-9]*"))
        raise ValueError(
            f"Restart {path} is not in the archive, so run {base_run} cannot be continued from; "
            f"runs whose restarts are still kept are {kept}! Set `restart_path` yourself to start "
            f"from another run's state, which is not checked against this run's configuration."
        )
    return path


def _repository(job_file: Path, payu_control_path: str) -> str:
    """
    Where to clone the base run's configuration.

    The control directory is authoritative, but it can have been deleted, moved, or left
    in a home directory nobody else can read. `payu sync` leaves a bare clone of it beside
    the synced archive, holding the same commits, so fall back to that when there is one.
    """
    if Path(payu_control_path).is_dir():
        return payu_control_path

    # <archive>/payu_jobs/<run>/run/<jobid>.json
    runlog = job_file.parents[3] / "git-runlog"
    if runlog.is_dir():
        print(f" -- control directory {payu_control_path} is gone, using the bare clone {runlog}")
        return str(runlog)

    raise ValueError(
        f"Control directory {payu_control_path} recorded in {job_file} no longer exists, and the "
        f"archive holds no git-runlog bare clone, so this run's configuration cannot be recovered!"
    )


def apply_base_archive(indata: dict) -> None:
    """
    Fill the control experiment source in `indata` from an archived payu run in place.

    base_archive_path (str): An archive, a control directory, or one
        `payu_jobs/<run>/run/<jobid>.json` file, which names its own run.
    base_run (int): Which run of it to start from. Required, because the most recent moves.
    base_restart (bool): Continue from where that run ended, rather than starting from cold.
    """
    base = indata.get("base_archive_path")
    if not base:
        return

    if indata.get("base_restart") and indata.get("restart_path"):
        raise ValueError(
            f"`base_restart` and `restart_path` ({indata['restart_path']}) are both set, but "
            "`base_restart` resolves the restart of `base_run` while `restart_path` names one "
            "yourself. Set only one of them!"
        )

    job_file, job = _job_metadata(Path(base).expanduser().resolve(), indata.get("base_run"))

    payu_control_path = job.get("payu_control_path")
    payu_run_id = job.get("payu_run_id")
    if not payu_control_path or not payu_run_id:
        raise ValueError(
            f"{job_file} records no `payu_control_path` and `payu_run_id`: it is either an attempt "
            "that failed before recording them, or was written by a payu older than 1.3. Point at "
            "the archive and name the run with `base_run` to use the attempt that succeeded."
        )

    resolved = {
        "repository_url": _repository(job_file, payu_control_path),
        "start_point": payu_run_id,
        "parent_experiment": (job.get("experiment_metadata") or {}).get("experiment_uuid"),
    }
    if indata.get("base_restart"):
        resolved["restart_path"] = str(_restart_path(Path(job["payu_archive_path"]), job["payu_current_run"]))

    print(f"-- Base run metadata: {job_file}")
    for k, v in resolved.items():
        if v is None:
            continue
        if indata.get(k) in (None, ""):
            indata[k] = v
            print(f" -- {k}: {v}")
        elif indata[k] != v:
            print(f" -- {k}: keeping {indata[k]} from the YAML input, base run records {v}")

    if not indata.get("restart_path"):
        run = job["payu_current_run"]
        print(" -- `restart_path` is not specified, so the control experiment starts from cold")
        print(f" -- set `base_restart: true` to continue from the end of run {run} instead")
