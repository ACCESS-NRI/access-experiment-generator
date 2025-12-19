"""
Utility module

This module provides helper functions
 - `update_config_entries`: Recursively apply updates or removals to nested dictionaries.
 - Support for two special markers:
    - "REMOVE": delete a key or element (or set to ``None`` if ``pop_key=False``).
        #TODO: pop_key=False should be removed?
    - "PRESERVE": keep a key or element (do not delete or modify).
"""

from collections.abc import Mapping, Sequence
from .common_var import _is_removed_str, _is_preserved_str, _is_seq
from copy import deepcopy


def _path_join(path: str, key: str) -> str:
    if not path:
        return str(key)
    if str(key).startswith("["):
        return f"{path}{key}"
    return f"{path}.{key}"


def _remove_state_key(path: str, index: int) -> str:
    """
    uniquely identify a positional REMOVE marker at this location
    """
    return f"{path}::REMOVE[{index}]"


def _strip_preserved(x):
    """
    Remove any value marked as `PRESERVE` from an update tree.

    Rules:
      - Scalar "PRESERVE" -> do not apply this key - should_apply=False
      - Mapping -> recursively strip; if nothing left, should_apply=False
      - Sequence:
          - ["PRESERVE"] -> keep whole list as-is (should_apply=False)
    """
    # scalar "PRESERVE"
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
        # whole-list "PRESERVE" (explicitly keep the entire list as-is)
        if len(x) == 1 and _is_preserved_str(x[0]):
            return False, None
        # allow "PRESERVE" at element level to pass through for positional merge
        return True, x

    # everything else: apply as-is
    return True, x


def _clean_removes(x, *, pop_key: bool) -> object:
    """
    Recursively clean 'REMOVE' markers from nested structures.

    - In mappings: entries with "REMOVE" are dropped (or set to None if pop_key is False).
    - In sequences (non-strings): elements that are "REMOVE" are dropped; elements that
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

    # Sequence (but not str): clean each item; drop "REMOVE" and items that become {}
    if _is_seq(x):
        out_seq = []
        for item in x:
            # drop literal "REMOVE" elements
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


class PositionalMergeError(ValueError):
    pass


def _merge_lists_positional(
    base_list: list, change_list: list, *, path: str, state: dict | None, pop_key: bool
) -> list | None:
    """
    Merge two lists by index:

    - For indices i present in change_list:
        * if change[i] is "PRESERVE" -> keep base[i] as-is (skip)
        * if change[i] is "REMOVE"    -> drop base[i]
        * if both are mappings      -> recursively merge dicts
        * if both are lists         -> recursively positional-merge lists
        * else                      -> replace base[i] with cleaned change[i]
    - For indices beyond len(change_list): keep base items unchanged.
    - For indices beyond len(base_list): append cleaned change items.

    "REMOVE" / "PRESERVE" for scalars and nested structures are respected.

    Updates:
        merge two lists by index, but make REMOVE unaccidental deletions explicit across runs
            1. First run, for each positional REMOVE, record a unique key in state store
            2. On later runs, REMOVE[i] removes that recorded value wherever it appears, even if indices shifted.
        can return None if the entire list is removed
    """
    if state is None:
        state = {}

    # If every element in change_list is "REMOVE", remove the whole thing
    if change_list and len(change_list) == len(base_list) and all(_is_removed_str(c) for c in change_list):
        return None

    base_key = f"{path}::BASE"
    if base_key not in state:
        # deepcopy to avoid later mutations affecting the snapshot
        state[base_key] = deepcopy(base_list)
    base0 = state[base_key]  # stable baseline for all runs

    def _baseline_slot(i: int):
        """
        Keep baseline results deterministic across runs.
        """
        return deepcopy(base0[i])

    out = type(base_list)()
    max_len = max(len(base0), len(change_list))

    # walk both lists by index, building a new list.
    for i in range(max_len):
        have_base = i < len(base0)
        have_change = i < len(change_list)

        if not have_change:
            # keep remainder of base as-is
            out.append(_baseline_slot(i))
            continue

        c = change_list[i]

        if not have_base and (_is_removed_str(c) or _is_preserved_str(c)):
            raise PositionalMergeError(
                f"\n -- {path}[{i}]: {c!r} refers to a non-existent baseline slot "
                f"(baseline length={len(base0)}). \n"
                "    -- Please check the number of REMOVE/PRESERVE markers "
                "in your YAML input file!"
            )

        # # {} or "PRESERVE" -> no-op for this slot
        # TODO: not sure for this now??
        # if isinstance(c, Mapping) and not c:
        #     if have_base:
        #         out.append(base_list[i])
        #     continue

        if _is_preserved_str(c):
            out.append(_baseline_slot(i))
            # if no base slot, do nothing (don't append "PRESERVE")
            continue

        # Drop this slot if "REMOVE"
        if _is_removed_str(c):
            continue

        # If both sides exist and are mappings, recursively merge
        if have_base and isinstance(base0[i], Mapping) and isinstance(c, Mapping):
            merged = base_list[i]
            update_config_entries(merged, c, pop_key=pop_key, path=_path_join(path, f"[{i}]"), state=state)
            if not merged and pop_key:
                continue
            out.append(merged)
            continue

        # If both sides exist and are lists, recursively merge lists
        if have_base and isinstance(base0[i], list) and isinstance(c, list):
            out.append(
                _merge_lists_positional(base0[i], c, path=_path_join(path, f"[{i}]"), state=state, pop_key=pop_key)
            )
            continue

        # Otherwise: replace with cleaned change element
        cleaned = _clean_removes(c, pop_key=pop_key)
        # Drop empty mapping element if pop_key=True
        if isinstance(cleaned, Mapping) and not cleaned and pop_key:
            continue
        out.append(cleaned)

    # If pop_key and list becomes empty, then delete the whole list
    if pop_key and len(out) == 0:
        return []

    return out


def update_config_entries(
    base: dict, change: dict, path: str = "", state: dict | None = None, pop_key: bool = True
) -> None:
    """
    Recursively update or remove entries in a nested dictionary in place.

    - If both base[k] and change[k] are mappings, merge recursively.
    - Otherwise, the change is cleaned (via _clean_removes) and assigned.
      Cleaning rules:
        * "REMOVE" in mappings -> drop key (pop_key=True) or set None (pop_key=False).
        * "REMOVE" in sequences -> drop element; elements that clean to {} -> drop element.
        * Scalars pass through.

    "PRESERVE" process:
    - "PRESERVE" is processed before "REMOVE" logic:
        - Any key or element marked as "PRESERVE" is ignored so that the value already in `base` is preserved.
    "REMOVE" process:
    - We standardise "REMOVE" processing for top-level and nested keys by wrapping each candidate change as {k: v}
      and passing it to the cleaning routine. After cleaning:
       - If k remains, use its cleaned value.
       - If k is absent, it was removed during cleaning, so remove it from base.

    Update:
        support state store for
            - remembering positional REMOVE markers across runs,
            - preserving existing formatting by in-place list updates.
    """
    if state is None:
        state = {}

    for k, v in change.items():
        # strip "PRESERVE" first
        should_apply, v = _strip_preserved(v)
        if not should_apply:
            continue  # no change for this key; keep existing value

        key_path = _path_join(path, str(k))

        if isinstance(v, Mapping) and isinstance(base.get(k), Mapping):
            update_config_entries(base[k], v, path=key_path, state=state, pop_key=pop_key)
            if pop_key and isinstance(base[k], Mapping) and not base[k]:
                base.pop(k, None)
            continue

        if isinstance(base.get(k), list) and isinstance(v, list):
            merged = _merge_lists_positional(base[k], v, path=key_path, state=state, pop_key=pop_key)
            # if merge returned None -> delete key
            if merged is None or (pop_key and isinstance(merged, list) and len(merged) == 0):
                base.pop(k, None)
                continue

            # inplace update to preserve formatting and comments
            base_list = base[k]

            # if nothing changes then do nothing to preserve formatting
            if base_list == merged:
                continue

            # overwrite existing slots
            n = min(len(base_list), len(merged))
            for i in range(n):
                base_list[i] = merged[i]

            # append new items
            for i in range(len(base_list), len(merged)):
                base_list.append(merged[i])

            # remove extra old items
            while len(base_list) > len(merged):
                base_list.pop()

            continue

        cleaned = _clean_removes({k: v}, pop_key=pop_key)

        if k in cleaned:
            val = cleaned[k]
            if pop_key:
                if isinstance(val, Mapping) and not val:
                    # special case: cleaned to empty mapping and pop_key=True -> remove key
                    base.pop(k, None)
                    continue
                if isinstance(val, Sequence) and not isinstance(val, str) and len(val) == 0:
                    # special case: cleaned to empty sequence and pop_key=True -> remove key
                    base.pop(k, None)
                    continue
            base[k] = val
        else:
            base.pop(k, None)
