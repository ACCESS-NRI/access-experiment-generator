"""
Utility module

This module provides helper functions
 - `update_config_entries`: Recursively apply updates or removals to nested dictionaries.
 - Support for two special markers:
    - REMOVE: delete a key or element (or set to ``None`` if ``pop_key=False``).
        #TODO: pop_key=False should be removed?
    - PRESERVED: keep a key or element (do not delete or modify).
"""

from collections.abc import Mapping, Sequence
from .common_var import _is_removed_str, _is_preserved_str, _is_seq


def _strip_preserved(x):
    """
    Remove any value marked as `PRESERVED` from an update tree.

    Rules:
      - Scalar PRESERVED -> do not apply this key - should_apply=False
      - Mapping -> recursively strip; if nothing left, should_apply=False
      - Sequence:
          - ["PRESERVED"] -> keep whole list as-is (should_apply=False)
    """
    # scalar PRESERVED
    if _is_preserved_str(x):
        return False, None

    # mapping
    if isinstance(x, Mapping):
        out = type(x)()
        applied_any = False
        for k, v in x.items():
            apply_child, v2 = _strip_preserved(v)
            if apply_child:
                out[k] = v2
                applied_any = True
        if not applied_any:
            return False, None
        return True, out

    # sequence (non-str)
    if _is_seq(x):
        # whole-list PRESERVED
        if len(x) == 1 and _is_preserved_str(x[0]):
            return False, None
        # if any PRESERVED appears, be conservative: skip updating this key
        if any(_is_preserved_str(v) for v in x):
            return False, None
        # otherwise pass through unchanged
        return True, x

    # everything else: apply as-is
    return True, x


def _clean_removes(x, *, pop_key: bool) -> object:
    """
    Recursively clean 'REMOVE' markers from nested structures.

    - In mappings: entries with REMOVED are dropped (or set to None if pop_key is False).
    - In sequences (non-strings): elements that are REMOVED are dropped; elements that
      clean to an empty mapping are dropped; sequence type is preserved (list).
    - Scalars (including None) pass through unchanged.
    - TODO: pop_key=False? Still need this behaviour? CAN BE DELETED?
    """
    # Mapping: clean keys/values and drop or null per pop_key
    if isinstance(x, Mapping):
        out = type(x)()
        for k, v in x.items():
            if _is_removed_str(v):
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
    if _is_seq(x):
        out_seq = []
        for item in x:
            # drop literal REMOVED elements
            if _is_removed_str(item):
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

    PRESERVE process:
    - PRESERVED is processed before REMOVED logic:
        - Any key or element marked as PRESERVED is ignored so that the value already in `base` is preserved.
    REMOVED process:
    - We standardise REMOVED processing for top-level and nested keys by wrapping each candidate change as {k: v}
      and passing it to the cleaning routine. After cleaning:
       - If k remains, use its cleaned value.
       - If k is absent, it was removed during cleaning, so remove it from base.
    """
    for k, v in change.items():
        # strip RESERVED first
        should_apply, v = _strip_preserved(v)
        if not should_apply:
            continue  # no change for this key; keep existing value

        if isinstance(v, Mapping) and isinstance(base.get(k), Mapping):
            update_config_entries(base[k], v, pop_key=pop_key)
            if pop_key and isinstance(base[k], Mapping) and not base[k]:
                base.pop(k, None)
            continue

        cleaned = _clean_removes({k: v}, pop_key=pop_key)

        if k in cleaned:
            val = cleaned[k]
            if pop_key:
                # if isinstance(val, Mapping) and not val:
                #     # special case: cleaned to empty mapping and pop_key=True -> remove key
                #     base.pop(k, None)
                #     continue
                if isinstance(val, Sequence) and not isinstance(val, str) and len(val) == 0:
                    # special case: cleaned to empty sequence and pop_key=True -> remove key
                    base.pop(k, None)
                    continue
            base[k] = val
        else:
            base.pop(k, None)
