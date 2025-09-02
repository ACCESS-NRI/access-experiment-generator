"""
A temporary parser for YAML format files.

- `read_yaml`: Load a YAML file into a Python dictionary with preserved quotes.
- `write_yaml`: Dump a Python dictionary back to a YAML file, maintaining format.
"""

import ruamel.yaml

ryaml = ruamel.yaml.YAML()
ryaml.indent(mapping=2, sequence=4, offset=2)

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
