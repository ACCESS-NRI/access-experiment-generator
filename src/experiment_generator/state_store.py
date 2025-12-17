import json
from dataclasses import dataclass
from pathlib import Path
from .common_var import REMOVE_STATE_DIR


@dataclass
class RemoveStateStore:
    """
    Record REMOVE values for each positional REMOVE marker under a specific path.
    Hence a rerun removes the same items as before.
    """

    root_dir: Path
    remove_state_dirname: str = REMOVE_STATE_DIR

    def _state_dir(self) -> Path:
        """
        State directory path.
        """
        d = self.root_dir / self.remove_state_dirname
        d.mkdir(parents=True, exist_ok=True)
        return d

    def state_path(self, branch_name: str) -> Path:
        """
        State file path for a given branch name.
        """
        return self._state_dir() / f"{branch_name}.json"

    def load_state(self, branch_name: str) -> dict:
        """
        Load state for a given branch from a file.
        """
        fpath = self.state_path(branch_name)
        if not fpath.exists():
            return {}
        return json.loads(fpath.read_text())

    def save_state(self, branch_name: str, state: dict) -> None:
        """
        Save state for a given branch to a file.
        """
        fpath = self.state_path(branch_name)
        fpath.write_text(json.dumps(state, indent=2))
