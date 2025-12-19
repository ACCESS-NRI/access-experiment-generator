from pathlib import Path

from .tmp_parser.field_table import read_field_table, write_field_table

from .utils import update_config_entries


def prune_empty_field_table_config(config: dict) -> None:
    """
    In field_table semantics, an entry with no methods should be removed entirely.
    """
    # config[field][model][field_type] = {"methods": [...]}
    for field in list(config.keys()):
        field_map = config[field]
        for model in list(field_map.keys()):
            model_map = field_map[model]
            for field_type in list(model_map.keys()):
                block = model_map[field_type]
                methods = block.get("methods", None)

                # treat missing methods as no entry
                if not methods:
                    del model_map[field_type]

            if not model_map:
                del field_map[model]
        if not field_map:
            del config[field]


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
        prune_empty_field_table_config(config)
        write_field_table(config, fpath)
