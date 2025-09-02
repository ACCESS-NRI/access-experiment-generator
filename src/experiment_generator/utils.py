"""
Utility module

This module provides helper functions,

- `update_config_entries`: Recursively apply updates or removals to nested dictionaries.
"""


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
