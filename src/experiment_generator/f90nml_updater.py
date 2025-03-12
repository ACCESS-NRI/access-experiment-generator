import os
import numpy as np
import f90nml
from pathlib import Path


class F90NamelistUpdater:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_nml_params(
        self,
        param_dict: dict,
        target_file: str,
        append_group_list: list = None,
        indx: int = None,
    ) -> None:
        """
        Updates namelist parameters based on the YAML configuration.

        Args:
            param_dict (dict): The dictionary of parameters to update.
            target_file (str): The file to update.
        """
        nml_path = self.directory / target_file
        nml_tmp_path = nml_path.with_suffix(".tmp")

        if indx is not None:
            nml_group = get_namelist_group(append_group_list, indx)
            patch_dict = {nml_group: {}}
        else:
            nml_group = None
            patch_dict = {}

        for nml_name, nml_value in param_dict.items():
            if nml_group is not None:
                group = patch_dict.setdefault(nml_group, {})
            else:
                group = patch_dict

            if nml_name == "turning_angle":
                group["cosw"] = np.cos(nml_value * np.pi / 180.0)
                group["sinw"] = np.sin(nml_value * np.pi / 180.0)
            else:
                group[nml_name] = nml_value

        f90nml.patch(nml_path, patch_dict, nml_tmp_path)
        os.rename(nml_tmp_path, nml_path)
        format_nml_params(nml_path, param_dict)


def get_namelist_group(list_of_groupname: list[str], indx: int) -> str:
    """
    Retrieves the namelist group corresponding to the given index.

    Args:
        list_of_groupname (list[str]): List of namelist group names.
        indx (int): Index to retrieve from the list.

    Returns:
        str: The corresponding namelist group name.
    """
    nml_group = list_of_groupname[indx]
    return nml_group


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
                if tmp_param in line:
                    fileread[idx] = f"    {tmp_param} = {tmp_values}\n"
                    break

    with open(nml_path, "w", encoding="utf-8") as f:
        f.writelines(fileread)
