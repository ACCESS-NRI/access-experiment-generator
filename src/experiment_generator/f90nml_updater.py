"""
Fortran Namelist Updater.

This module provides functionality for updating F90namelist
files (`*.nml` or `*_in`) based on values defined in a YAML configuration.
It supports parameter additions, updates, deletions, and specific logic
(e.g. calculating cos/sin of a turning angle for CICE models).
"""

from pathlib import Path
import numpy as np
import f90nml
import re
from .common_var import _is_removed_str, _is_preserved_str


class F90NamelistUpdater:
    """
    A utility class for updating fortran namelists.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_nml_params(
        self,
        param_dict: dict[str, dict[str, any]],
        target_file: Path,
    ) -> None:
        """
        Updates namelist parameters based on the YAML input file.

        Args:
            param_dict (dict[str, dict[str, any]]):
                1. Mapping from namelist section names to parameter-value pairs.
                2. Use value=None or "REMOVE" to delete a variable.
                3. Special handling for "turning_angle": computes "cosw" and "sinw"
                   and inserts them into the `dynamics_nml` block.
            target_file (Path): Path to the namelist file, relative to `self.directory`.
        """
        nml_path = self.directory / target_file
        nml_tmp_path = nml_path.with_suffix(".tmp")

        nml_all = f90nml.read(nml_path)

        for group_name, group_value in param_dict.items():
            if not isinstance(group_value, dict):
                raise ValueError(f"Expected dict for {group_name}, got {type(group_value)}")

            # Special handling for 'turning_angle'
            # ref: https://github.com/aekiss/ensemble/blob/b27e4b7992683e4308bf630aa16da21730ccb11a/ensemble.py\
            # #L63C77-L63C89
            if "turning_angle" in group_value:
                turning_angle = group_value["turning_angle"]

                # Only manage cos/sin and delete 'turning_angle' when it's in dynamics_nml
                if group_name == "dynamics_nml":
                    # remove turning_angle from dynamics_nml
                    group_value.pop("turning_angle", None)

                    # Only CICE namelists manage cosw/sinw
                    if target_file.endswith(("cice_in.nml", "ice_in")):
                        if _is_removed_str(turning_angle):
                            # drop cos/sin
                            if "dynamics_nml" in nml_all:
                                nml_all["dynamics_nml"].pop("cosw", None)
                                nml_all["dynamics_nml"].pop("sinw", None)
                                if not nml_all["dynamics_nml"]:
                                    nml_all.pop("dynamics_nml", None)

                        elif _is_preserved_str(turning_angle) or turning_angle is None:
                            dyn = nml_all.get("dynamics_nml", {})
                            if "cosw" not in dyn and "sinw" not in dyn:
                                raise ValueError(
                                    "Cannot preserve turning_angle: no existing cosw and sinw found in `dynamics_nml`"
                                )
                        else:
                            tmp = np.radians(turning_angle)
                            cosw = np.cos(tmp)
                            sinw = np.sin(tmp)
                            nml_all.setdefault("dynamics_nml", {})
                            nml_all["dynamics_nml"]["cosw"] = cosw
                            nml_all["dynamics_nml"]["sinw"] = sinw
                else:
                    # turning_angle is in some other group -> do NOT touch cos/sin.
                    # Leave it to the normal per-variable loop below (REMOVE / PRESERVE / None rules).
                    pass

            # Ensure the groupname exists
            if group_name not in nml_all:
                nml_all[group_name] = {}

            # Update or remove variables
            for var, value in group_value.items():
                if _is_removed_str(value):
                    nml_all[group_name].pop(var, None)
                    continue
                if _is_preserved_str(value) or value is None:
                    # Preserve None: do not alter existing values, do not delete.
                    continue
                nml_all[group_name][var] = value

        f90nml.write(nml_all, nml_tmp_path, force=True)
        nml_tmp_path.replace(nml_path)

        # Postprocessing to ensure proper formatting
        format_nml_params(nml_path, param_dict)


def format_nml_params(nml_path: str, param_dict: dict) -> None:
    """
    Ensure proper formatting in the namelist file, particularly for booleans and list-like strings.

    This method correctly formats boolean values and ensures Fortran syntax
    is preserved when updating parameters.

    Args:
        nml_path (str): The path to specific f90 namelist file.
        param_dict (dict): The dictionary of parameters to update.
    Example:
        YAML input file:
            ocean/input.nml:
                mom_oasis3_interface_nml:
                    fields_in: "'u_flux', 'v_flux', 'lprec'"
                    fields_out: "'t_surf', 's_surf', 'u_surf'"

        Resulting `.nml` or `_in` file:
            &mom_oasis3_interface_nml
                fields_in = 'u_flux', 'v_flux', 'lprec'
                fields_out = 't_surf', 's_surf', 'u_surf'
    """
    with open(nml_path, "r", encoding="utf-8") as f:
        fileread = f.readlines()

    for _, tmp_subgroups in param_dict.items():
        for tmp_param, tmp_values in tmp_subgroups.items():
            # convert Python bool to Fortran logical
            if isinstance(tmp_values, bool):
                tmp_values = ".true." if tmp_values else ".false."

            for idx, line in enumerate(fileread):
                if line.lstrip().startswith("!"):
                    continue
                words = [w for w in re.split(r"[^a-zA-Z0-9_]+", line) if w]
                if tmp_param in words:
                    fileread[idx] = f"    {tmp_param} = {tmp_values}\n"
                    break

    with open(nml_path, "w", encoding="utf-8") as f:
        f.writelines(fileread)
