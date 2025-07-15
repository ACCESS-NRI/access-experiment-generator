from pathlib import Path
from .utils import update_config_entries
from .tmp_parser.mom6_input import (
    read_mom_input,
    write_mom_input,
)


class Mom6InputUpdater:
    """
    Updating MOM6 input files.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_mom6_params(
        self,
        param_dict: dict,
        target_file: str,
    ) -> None:
        """
        Updates parameters and overwrites the MOM6 input file.

        Args:
            param_dict (dict): Dictionary of parameters to update.
            target_file (str): Name of the MOM6 input file.
        """
        nml_path = self.directory / target_file

        # Read the MOM6 input file
        raw_lines, base_params = read_mom_input(nml_path)

        # Update the parameters
        # Note: This will remove keys with value None or "REMOVE"
        update_config_entries(base_params, param_dict, pop_key=True)

        # Write the updated parameters back to the MOM6 input file
        write_mom_input(raw_lines, base_params, nml_path)
