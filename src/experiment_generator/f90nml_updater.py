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
        param_dict: dict,
        target_file: str,
    ) -> None:
        """
        Updates namelist parameters based on the YAML configuration.

        Args:
            param_dict (dict): The dictionary of parameters to update.
            target_file (str): The file to update.
        """
        nml_path = self.directory / target_file
        nml_tmp_path = nml_path.with_suffix(".tmp")

        patch_dict = {}

        for nml_name, nml_value in param_dict.items():
            if nml_name == "turning_angle":
                patch_dict["cosw"] = np.cos(nml_value * np.pi / 180.0)
                patch_dict["sinw"] = np.sin(nml_value * np.pi / 180.0)
            else:
                patch_dict[nml_name] = nml_value

        f90nml.patch(nml_path, patch_dict, nml_tmp_path)
        os.rename(nml_tmp_path, nml_path)
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
