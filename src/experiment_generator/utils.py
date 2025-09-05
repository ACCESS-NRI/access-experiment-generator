"""
Utility module

This module provides helper functions
`update_config_entries`: Recursively apply updates or removals to nested dictionaries.
"""

from collections.abc import Mapping, Sequence
from .common_var import REMOVED


def _clean_removes(x, *, pop_key: bool) -> object:
    """
    Recursively clean 'REMOVE' markers from nested structures.

    - In mappings: entries with REMOVED are dropped (or set to None if pop_key is False).
    - In sequences (non-strings): elements that are REMOVED are dropped; elements that
      clean to an empty mapping are dropped; sequence type is preserved (list/tuple).
    - Scalars (including None) pass through unchanged.
    - TODO: pop_key=False? Still need this behaviour? CAN BE DELETED?
    """
    # Mapping: clean keys/values and drop or null per pop_key
    if isinstance(x, Mapping):
        out = type(x)()
        for k, v in x.items():
            if isinstance(v, str) and v == REMOVED:
                if pop_key:
                    # drop this key entirely
                    continue
                else:
                    # keep key, set to None
                    out[k] = None
            else:
                out[k] = _clean_removes(v, pop_key=pop_key)
        return out

    # Sequence (but not str): clean each item; drop REMOVED and items that become {}
    if isinstance(x, Sequence) and not isinstance(x, str):
        out_seq = []
        for item in x:
            # drop literal REMOVED elements
            if isinstance(item, str) and item == REMOVED:
                continue
            item_clean = _clean_removes(item, pop_key=pop_key)
            # if an element becomes an empty mapping, drop it (special-case tidy)
            if isinstance(item_clean, Mapping) and not item_clean:
                continue
            out_seq.append(item_clean)
        return type(x)(out_seq)

    # Scalars (including None) pass through unchanged
    return x


def update_config_entries(base: dict, change: dict, pop_key: bool = True) -> None:
    """
    Recursively update or remove entries in a nested dictionary in place.

    - If both base[k] and change[k] are mappings, merge recursively.
    - Otherwise, the change is cleaned (via _clean_removes) and assigned.
      Cleaning rules:
        * REMOVED in mappings -> drop key (pop_key=True) or set None (pop_key=False).
        * REMOVED in sequences -> drop element; elements that clean to {} -> drop element.
        * Scalars pass through.

    REMOVED process:
    - We standardise REMOVED processing for top-level and nested keys by wrapping each candidate change as {k: v}
      and passing it to the cleaning routine. After cleaning:
       - If k remains, use its cleaned value.
       - If k is absent, it was removed during cleaning, so remove it from base.
    """
    for k, v in change.items():
        if isinstance(v, Mapping) and isinstance(base.get(k), Mapping):
            update_config_entries(base[k], v, pop_key=pop_key)
            continue

        cleaned = _clean_removes({k: v}, pop_key=pop_key)

        if k in cleaned:
            base[k] = cleaned[k]
        else:
            base.pop(k, None)
