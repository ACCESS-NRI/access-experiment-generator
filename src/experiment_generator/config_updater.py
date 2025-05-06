"""
Config.yaml Updater for the experiment management.

This module provides utilities to update `config.yaml` for experiments.
It includes methods for modifying parameters in both control and perturbation experiments.
"""

import warnings
from pathlib import Path
from .utils import read_yaml, write_yaml, update_config_entries


class ConfigUpdater:
    """
    A utility class for updating `config.yaml`.
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialise the ConfigUpdater with a working directory.
        """
        self.directory = directory

    def update_config_params(self, param_dict: dict, target_file: Path) -> None:
        """
        Update `config.yaml` parameters using values from the input dictionary.

        - Ensures the 'jobname' matches the directory name for consistency.
        - Overwrites the target YAML file in-place.

        Args:
            param_dict (dict): Dictionary of parameters to update in config.yaml.
            target_file (Path): Relative path to the config.yaml file within the directory.
        """
        nml_path = self.directory / target_file
        file_read = read_yaml(nml_path.as_posix())

        # Enforce jobname consistency
        if "jobname" in param_dict:
            if param_dict["jobname"] != self.directory.name:
                warnings.warn(
                    f"\n"
                    f"-- jobname must be the same as {self.directory.name}, "
                    f"hence jobname is forced to be {self.directory.name}!",
                    UserWarning,
                )
        param_dict["jobname"] = self.directory.name

        # Apply updates to the config.yaml file
        update_config_entries(file_read, param_dict)

        # write to the config.yaml file
        write_yaml(file_read, nml_path.as_posix())
