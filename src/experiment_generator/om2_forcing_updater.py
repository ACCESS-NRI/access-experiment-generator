from pathlib import Path
from .tmp_parser.json_parser import read_json, write_json
from .utils import update_config_entries
import warnings
from .common_var import REMOVED


class Om2ForcingUpdater:
    """
    A utility class for updating OM2 forcing files, e.g., `forcing.json`
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_forcing_params(
        self,
        param_dict: dict,
        target_file: Path,
    ) -> None:
        forcing_path = self.directory / target_file
        file_read = read_json(forcing_path)

        for fieldname, updates in param_dict.items():
            idx = self._find_matching_param_index(file_read["inputs"], fieldname)
            if idx is None:
                raise ValueError("Not found a valid perturbed fieldname!")

            base = file_read["inputs"][idx]

            if "perturbations" in updates:
                self._preprocess_perturbations(fieldname, updates)

            update_config_entries(base, updates)

        write_json(file_read, forcing_path)

    @staticmethod
    def _find_matching_param_index(inputs: list, fieldname: str) -> int | None:
        """
        Locate the index of a parameter in the 'inputs' list by field name.
        """
        for i, base in enumerate(inputs):
            if base.get("fieldname") != fieldname:
                continue
            return i
        return None

    def _preprocess_perturbations(self, fieldname: str, updates: dict) -> None:
        """
        process `updates["perturbations"]`.
        Warns and removes the key from `updates` if unsuitable.
        """
        perts = updates.get("perturbations")

        # treat falsy as "no change"
        if perts in (None, {}, []):
            warnings.warn(
                f"-- forcing.json '{fieldname}': empty/None 'perturbations' provided; skipping.",
                UserWarning,
            )
            updates.pop("perturbations", None)
            return

        # accept dict -> wrap it to list[dict]
        if isinstance(perts, dict):
            perts = [perts]
            updates["perturbations"] = perts

        # accept list[dict]
        elif isinstance(perts, list) and all(isinstance(pert, dict) for pert in perts):
            pass
        else:
            raise TypeError(f"-- forcing.json '{fieldname}': 'perturbations' must be a dict or list of dicts")

        required = ["type", "dimension", "value", "calendar", "comment"]

        def _is_to_remove(pert: dict) -> bool:
            if all(pert.get(k) in REMOVED for k in required):
                return True
            if pert.get("type") in REMOVED:
                return True
            return False

        cleaned = [p for p in perts if not _is_to_remove(p)]
        if not cleaned:
            warnings.warn(
                f"-- forcing.json: all perturbations for field '{fieldname}' are marked for removal; "
                "skipping perturbations.",
                UserWarning,
            )
            # Drop the key so it doesn't carry an empty/removed set forward
            updates.pop("perturbations", None)
            return

        # validate each dict
        for pert in cleaned:
            self._validate_single_perturbation(pert)

        # keep only the cleaned ones
        updates["perturbations"] = cleaned

    @staticmethod
    def _validate_single_perturbation(pert: dict) -> None:
        """
        Validate a single perturbation dict.
        """
        if pert["type"] not in {"scaling", "offset", "separable"}:
            raise ValueError(f"Invalid perturbation type: {pert['type']}")

        dim = pert["dimension"]
        accepted_dim = (isinstance(dim, str) and dim in {"spatial", "temporal", "constant", "spatiotemporal"}) or (
            isinstance(dim, list) and dim == ["temporal", "spatial"]
        )
        if not accepted_dim:
            raise ValueError(f"Invalid perturbation dimension: {dim}")

        if pert["calendar"] not in {"forcing", "experiment"}:
            raise ValueError(f"Invalid perturbation calendar: {pert['calendar']}")
