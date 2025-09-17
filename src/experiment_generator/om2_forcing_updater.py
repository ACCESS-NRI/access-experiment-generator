from pathlib import Path
from .tmp_parser.json_parser import read_json, write_json
from .utils import update_config_entries
import warnings
from .common_var import _is_removed_str, REMOVED

required = ["type", "dimension", "value", "calendar", "comment"]
allowed_types = {"scaling", "offset", "separable", REMOVED}


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
                raise ValueError("Did not find a valid perturbed fieldname!")

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
        elif isinstance(perts, list):
            # must be list[dict]
            if not all(isinstance(pert, dict) for pert in perts):
                raise TypeError(f"-- forcing.json '{fieldname}': 'perturbations' must be a dict or list of dicts")
        else:
            raise TypeError(f"-- forcing.json '{fieldname}': 'perturbations' must be a dict or list of dicts")

        # cleaned is list of dicts
        cleaned = []
        for p in perts:
            q = dict(p)
            t_ = q.get("type")

            # skip if REMOVED
            if _is_removed_str(t_):
                continue

            # drop invalid type
            if not isinstance(t_, str) or t_ not in allowed_types:
                raise ValueError(
                    f"-- forcing.json '{fieldname}': perturbation has invalid type '{t_}'. "
                    f"Allowed types: {sorted(allowed_types)}"
                )

            cleaned.append(q)

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
        if pert["type"] not in allowed_types:
            raise ValueError(f"Invalid perturbation type: {pert['type']}")

        dim = pert["dimension"]
        accepted_dim = (isinstance(dim, str) and dim in {"spatial", "temporal", "constant", "spatiotemporal"}) or (
            isinstance(dim, list) and dim == ["temporal", "spatial"]
        )
        if not accepted_dim:
            raise ValueError(f"Invalid perturbation dimension: {dim}")

        if pert["calendar"] not in {"forcing", "experiment"}:
            raise ValueError(f"Invalid perturbation calendar: {pert['calendar']}")
