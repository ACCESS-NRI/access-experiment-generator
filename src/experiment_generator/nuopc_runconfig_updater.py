"""
nuopc.runconfig Updater.

This module provides utilities for updating `nuopc.runconfig` configuration files.
"""

from pathlib import Path
from .utils import update_config_entries
from .tmp_parser.nuopc_config import read_nuopc_config, write_nuopc_config


class NuopcRunConfigUpdater:
    """
    A utility class for updating `nuopc.runconfig` configuration file.
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialise the updater with the working directory.
        """
        self.directory = directory

    def update_runconfig_params(
        self,
        param_dict: dict,
        target_file: str,
    ) -> None:
        """
        Updates parameters and overwrites the `nuopc.runconfig` file.

        This method reads the file, updates entries based on the provided dictionary,
        and writes the modified configuration back to file.
        """
        nml_path = self.directory / target_file

        file_read = read_nuopc_config(nml_path)
        update_config_entries(file_read, param_dict)
        write_nuopc_config(file_read, nml_path)
