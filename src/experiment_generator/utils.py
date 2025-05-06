"""
Utility module

This module provides helper functions,
- `read_yaml`: Load a YAML file into a Python dictionary with preserved quotes.
- `write_yaml`: Dump a Python dictionary back to a YAML file, maintaining format.
- `update_config_entries`: Recursively apply updates or removals to nested dictionaries.
"""

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


def update_config_entries(base: dict, change: dict, pop_key: bool = True) -> None:
    """
    Recursively update or remove entries in a nested dictionary.

    Args:
        base (dict): Original dictionary to modify in-place.
        changes (dict): Dictionary of updates where:
            - If a value is None or 'REMOVE', the key is removed (if pop_key=True),
              or set to None otherwise.
            - If a value is a dict and the corresponding base entry is a dict,
              the update is applied recursively.
            - Otherwise, the base key is set to the new value.
        pop_key (bool): If True, keys with None or 'REMOVE' values are popped.
    """
    for k, v in change.items():
        if v is None or v == "REMOVE":
            if pop_key:
                # Remove it immediately
                base.pop(k, None)
            else:
                base[k] = None
        elif isinstance(v, dict) and k in base and isinstance(base[k], dict):
            update_config_entries(base[k], v)
        else:
            base[k] = v
