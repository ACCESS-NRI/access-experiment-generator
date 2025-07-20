import pytest
from pathlib import Path
from experiment_generator.nuopc_runseq_updater import NuopcRunseqUpdater


def test_update_nuopc_runseq_cpl_dt(tmp_path, capsys):
    repo_dir = tmp_path / "test_repo"
    rel_path = Path("nuopc.runseq")
    runseq_path = repo_dir / rel_path
    runseq_path.parent.mkdir(parents=True, exist_ok=True)
    runseq_path.write_text(
        "runSeq::\n" "@1100\n" "  MED do_something\n" "  OCN do_something\n" "@\n" "::\n",
    )

    updater = NuopcRunseqUpdater(repo_dir)

    params = {
        "cpl_dt": 10,
    }
    updater.update_nuopc_runseq(params, runseq_path.name)
    updated = runseq_path.read_text()

    assert "@10" in updated.splitlines()[1].strip()
    assert "@1100" not in updated


def test_update_nuopc_runseq_raises_if_no_at_line(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    bad_runseq = repo / "nuopc.runseq"
    bad_runseq.write_text(
        "runSeq::\n" "  MED do_something\n" "  OCN do_something\n" "@\n" "::\n",
    )

    updater = NuopcRunseqUpdater(repo)

    with pytest.raises(ValueError, match="Could not find a line beginning"):
        updater.update_nuopc_runseq({"cpl_dt": 10}, bad_runseq.name)
