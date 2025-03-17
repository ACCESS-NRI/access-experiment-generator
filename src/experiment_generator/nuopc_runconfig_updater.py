"""
nuopc.runconfig Updater for the experiment management.

This module provides utilities for updating `nuopc.runconfig` configuration files.
It supports:
- Updating namelist parameters dynamically.
- Applying perturbation experiments.
- Ensuring compatibility with `om3utils`.

"""

from pathlib import Path
from .utils import update_config_entries
from .tmp_parser.nuopc_config import read_nuopc_config, write_nuopc_config


class NuopcRunConfigUpdater:
    """
    A utility class for updating `nuopc.runconfig` configuration file.

    Methods:
        - `update_runconfig_params`: Updates `nuopc.runconfig` parameters.
        - `update_nuopc_config_perturb`: Applies perturbation experiment configurations.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_runconfig_params(
        self,
        param_dict: dict,
        target_file: str,
    ) -> None:
        """
        Updates parameters and overwrites the `nuopc.runconfig` file.

        Args:
            expt_path (str): Path to the experiment directory.
            param_dict (dict): Dictionary of parameters to update.
            filename (str): Name of the `nuopc.runconfig` file.
            append_group_list (list, optional): List of groups to append.
            indx (int, optional): Index to append to the group name if required.
        """
        nml_path = self.directory / target_file

        file_read = read_nuopc_config(nml_path)
        update_config_entries(file_read, param_dict)
        write_nuopc_config(file_read, nml_path)
