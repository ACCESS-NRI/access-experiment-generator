from pathlib import Path
from .tmp_parser.nuopc_seq import (
    read_runseq,
    modify_runseq,
    write_runseq,
)


class NuopcRunseqUpdater:
    """
    A utility class for updating nuopc_runseq input files.

    Methods:
        - `update_nuopc_runseq`: Updates MOM6 input parameters.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_nuopc_runseq(
        self,
        param_dict: dict,
        target_file: str,
    ) -> None:
        """
        Updates parameters and overwrites the MOM6 input file.
        """
        nml_path = self.directory / target_file

        raw_lines = read_runseq(nml_path)

        old_val = None
        for line in raw_lines:
            stripped = line.strip()
            if stripped.startswith("@") and stripped[1:].isdigit():
                old_val = stripped[1:]
                break

        if old_val is None:
            raise ValueError("Could not find a line beginning with '@<number>'in nuopc.runseq file")

        modifies_lines = modify_runseq(raw_lines, old_val=old_val, new_val=param_dict["cpl_dt"])
        write_runseq(modifies_lines, nml_path)
