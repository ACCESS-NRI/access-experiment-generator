import json
from pathlib import Path


def read_json(p: Path) -> dict:
    """
    Reads a json file and returns its content as a dict.
    """
    with p.open("r") as f:
        return json.load(f)


def write_json(obj: dict, p: Path) -> None:
    """
    Writes a dict to a json file, preserving formatting.
    """
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    tmp.replace(p)
