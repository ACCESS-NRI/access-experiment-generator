"""
Config.yaml Updater for the experiment management.

This module provides utilities to update YAML configuration files for experiments.
It includes methods for modifying parameters in both control and perturbation experiments.
"""

import warnings
from pathlib import Path
from .utils import read_yaml, write_yaml, update_config_entries


class ConfigUpdater:
    """
    A utility class for updating config.yaml.

    This class provides static methods to modify `config.yaml`.
    It ensures consistency in parameter updates.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_config_params(self, param_dict: dict, target_file: Path) -> None:
        """
        Updates namelist parameters and overwrites namelist file.

        Args:
            param_dict (dict): The dictionary of parameters to update.
            filename (str): The name of the namelist file.
        """
        nml_path = self.directory / target_file
        print(nml_path)

        file_read = read_yaml(nml_path.as_posix())

        if "jobname" in param_dict:
            if param_dict["jobname"] != self.directory.name:
                warnings.warn(
                    f"\n"
                    f"-- jobname must be the same as {self.directory.name}, "
                    f"hence jobname is forced to be {self.directory.name}!",
                    UserWarning,
                )
        param_dict["jobname"] = self.directory.name
        update_config_entries(file_read, param_dict)

        write_yaml(file_read, nml_path.as_posix())

    def update_perturb_jobname(self, target_file: str) -> None:
        """
        Updates the `jobname` field in `config.yaml` for perturbation experiments.

        Args:
            expt_path (str): The path to the perturbation experiment directory.
            expt_name (str): The name of the perturbation experiment.
        """
        config_path = self.directory / "config.yaml"
        config_data = read_yaml(config_path)
        config_data["jobname"] = target_file
        write_yaml(config_data, config_path)
