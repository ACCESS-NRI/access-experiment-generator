from ruamel.yaml import YAML

ryaml = YAML()
ryaml.preserve_quotes = True


def read_yaml(yaml_path: str) -> dict:
    """
    Reads a YAML file and returns a dictionary.
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        return ryaml.load(f)


def write_yaml(data: dict, yaml_path: str) -> None:
    """
    Writes a dictionary to a YAML file while preserving formatting.
    """
    with open(yaml_path, "w", encoding="utf-8") as f:
        ryaml.dump(data, f)


def update_config_entries(base: dict, change: dict) -> None:
    """
    Recursively update nuopc_runconfig and config.yaml entries.
    """

    for k, v in change.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            update_config_entries(base[k], v)
        else:
            base[k] = v
