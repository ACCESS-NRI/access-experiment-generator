from pathlib import Path
from .tmp_parser.json_parser import read_json, write_json
from .utils import update_config_entries


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
            if not isinstance(updates, dict):
                raise ValueError(f"The yaml input {fieldname} must be a dict!")

            for required_key in ("filename", "cname"):
                if required_key not in updates or not updates[required_key]:
                    raise ValueError(f"The yaml input {fieldname} must have a non-empty '{required_key}' key!")

            idx = self._find_matching_param_index(file_read["inputs"], fieldname)
            if idx is None:
                raise ValueError("Not found a valid perturbed fieldname!")

            base = file_read["inputs"][idx]

            if "perturbations" in updates:
                perts = updates["perturbations"]
                if isinstance(perts, dict):
                    perts = [perts]
                    updates["perturbations"] = perts
                elif isinstance(perts, list):
                    pass
                else:
                    raise TypeError(
                        f"The yaml input {fieldname} must have 'perturbations' as a list of dicts or a dict"
                    )

                for pert in perts:
                    self._validate_perturbation(pert)

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

    @staticmethod
    def _validate_perturbation(pert: dict) -> None:
        required = ["type", "dimension", "value", "calendar", "comment"]
        missing = [m for m in required if m not in pert]
        if missing:
            raise ValueError(f"Perturbation is missing required fields: {', '.join(missing)}")

        if pert["type"] not in {"scaling", "offset", "separable"}:
            raise ValueError(f"Invalid perturbation type: {pert['type']}")

        dim = pert["dimension"]
        accepted_dim = (isinstance(dim, str) and dim in {"spatial", "temporal", "constant", "spatiotemporal"}) or (
            isinstance(dim, list) and (dim == ["spatial", "temporal"] or dim == ["temporal", "spatial"])
        )
        if not accepted_dim:
            raise ValueError(f"Invalid perturbation dimension: {dim}")

        if pert["calendar"] not in {"forcing", "experiment"}:
            raise ValueError(f"Invalid perturbation calendar: {pert['calendar']}")
