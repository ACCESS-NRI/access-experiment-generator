from pathlib import Path

from .tmp_parser.field_table import read_field_table, write_field_table

from .utils import update_config_entries


class FieldTableUpdater:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def update_field_table_params(
        self,
        param_dict: dict,
        target_file: str,
        state: dict,
    ) -> None:
        fpath = self.directory / target_file
        config = read_field_table(fpath)
        update_config_entries(config, param_dict, pop_key=True, path=str(target_file), state=state)
        write_field_table(config, fpath)
