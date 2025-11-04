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

        # Update runseq block if provided
        if "runseq_block" in param_dict and param_dict["runseq_block"]:
            new_commands = modify_runseq(
                commands=[], # ignore when new_block is provided
                new_block=param_dict["runseq_block"],
            )
            write_runseq(new_commands, nml_path)
            return

        # Otherwise, just update cpl_dt line
        raw_lines = read_runseq(nml_path)

        old_val = None
        for line in raw_lines:
            stripped = line.strip()
            if stripped.startswith("@") and stripped[1:].isdigit():
                old_val = stripped[1:]
                break

        if old_val is None:
            raise ValueError("Could not find a line beginning with '@<number>'in nuopc.runseq file")

        new_commands = modify_runseq(raw_lines, old_val=old_val, new_val=param_dict["cpl_dt"])
        write_runseq(new_commands, nml_path)
