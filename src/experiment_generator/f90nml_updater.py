import os
from pathlib import Path
import numpy as np
import f90nml


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
        Updates namelist parameters based on the YAML configuration.

        Args:
            target_file (Path): Path to the namelist file, relative to `self.directory`.
            param_dict (dict[str, dict[str, any]]):
                Mapping from namelist section names to
                dictionaries of variable names to new values.

                Use value=None or "REMOVE" to delete a variable.

                Special key "turning_angle" will generate
                "cosw" and "sinw" entries in the "dynamics_nml" section.
        """
        nml_path = self.directory / target_file
        nml_tmp_path = nml_path.with_suffix(".tmp")

        nml_all = f90nml.read(nml_path)

        for group_name, group_value in param_dict.items():
            if not isinstance(group_value, dict):
                raise ValueError(
                    f"Expected dict for {group_name}, got {type(group_value)}"
                )

            if "turning_angle" in group_value:
                turning_angle = group_value.pop("turning_angle")
                if turning_angle == "REMOVE" or turning_angle is None:
                    nml_all.setdefault(group_name, {}).pop("turning_angle", None)
                    continue

                if target_file.endswith(("cice_in.nml", "ice_in")):
                    tmp = np.radians(turning_angle)
                    cosw = np.cos(tmp)
                    sinw = np.sin(tmp)

                    if "dynamics_nml" not in nml_all:
                        nml_all["dynamics_nml"] = {}

                    nml_all["dynamics_nml"]["cosw"] = cosw
                    nml_all["dynamics_nml"]["sinw"] = sinw

            # Ensure the groupname exists
            if group_name not in nml_all:
                nml_all[group_name] = {}

            for var, value in group_value.items():
                if value == "REMOVE" or value is None:
                    nml_all[group_name].pop(var, None)
                else:
                    nml_all[group_name][var] = value

            # if not nml_all[group_name]:
            #     nml_all.pop(group_name, None)

        f90nml.write(nml_all, nml_tmp_path, force=True)
        nml_tmp_path.replace(nml_path)

        format_nml_params(nml_path, param_dict)


def format_nml_params(nml_path: str, param_dict: dict) -> None:
    """
    Ensures proper formatting in the namelist file.

    This method correctly formats boolean values and ensures Fortran syntax
    is preserved when updating parameters.

    Args:
        nml_path (str): The path to specific f90 namelist file.
        param_dict (dict): The dictionary of parameters to update.
    Example:
        YAML input:
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
                if tmp_param in line:
                    fileread[idx] = f"    {tmp_param} = {tmp_values}\n"
                    break

    with open(nml_path, "w", encoding="utf-8") as f:
        f.writelines(fileread)
