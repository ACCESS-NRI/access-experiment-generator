import pytest
from experiment_generator.utils import (
    update_config_entries,
    _merge_lists_positional,
    _remove_state_key,
    PositionalMergeError,
)
from experiment_generator.common_var import REMOVED, PRESERVED


def test_update_config_entries_basic_changes_with_pop_key():
    """
    update_config_entries should apply nested updates, removals, and additions in place.
    """

    base = {
        "a": 1,
        "b": {"x": 2, "y": 3},
        "c": 4,
    }

    changes = {
        "a": 10,
        "b": {"x": None, "z": 5},
        "c": REMOVED,
        "d": 7,
    }

    expected = {
        "a": 10,
        "b": {"x": None, "y": 3, "z": 5},
        # "c" removed
        "d": 7,
    }

    update_config_entries(base, changes)
    assert base == expected


def test_update_config_entries_no_pop_key():
    """
    if pop_key is False, the function should not remove keys.
    """

    base = {
        "a": 1,
        "b": 2,
    }

    changes = {
        "a": REMOVED,
        "b": None,
    }

    expected = {
        "a": None,
        "b": None,
    }

    update_config_entries(base, changes, pop_key=False)
    assert base == expected


def test_update_config_entries_nested():
    """
    nested dict updates should merge into existing dict keys recursively.
    """

    base = {
        "outer": {
            "inner1": 1,
            "inner2": 2,
        },
        "a": 1,
    }

    changes = {
        "outer": {
            "inner1": 10,
            "inner2": 20,
        },
        "a": None,
    }

    expected = {
        "outer": {
            "inner1": 10,
            "inner2": 20,
        },
        "a": None,
    }

    update_config_entries(base, changes)
    assert base == expected


def test_update_config_entries_drops_REMOVE_items_inside_lists_and_empty_dict_elements():
    """
    Covers _clean_removes list branch:
      - drops literal REMOVE elements in lists
      - drops list elements that become empty mappings after cleaning
      - assigns cleaned list via update_config_entries
    """
    base = {}

    changes = {
        "lst": [
            1,
            REMOVED,
            {"a": REMOVED},
            {"b": 2},
        ]
    }

    expected = {"lst": [1, {"b": 2}]}

    update_config_entries(base, changes)
    assert base == expected


def test_update_config_entries_preserves_sequence_type_when_cleaning():
    """
    Covers type(x)(out_seq) path in _clean_removes by using a list.
    Also drops REMOVE items inside the list.
    """
    base = {}
    changes = {"lst": ["x", REMOVED, "y"]}
    update_config_entries(base, changes)
    assert base["lst"] == ["x", "y"]
    assert isinstance(base["lst"], list)  # sequence type preserved


def test_clean_removes_sets_none_when_pop_key_false_nested_mapping_replacement():
    """
    Hit `_clean_removes`'s mapping branch with pop_key=False where a child is REMOVED.
    Make base['outer'] not a mapping so update_config_entries assigns cleaned(change['outer']).
    """
    base = {"outer": 0}  # base['outer'] not a mapping -> triggers clean(assign) path
    changes = {"outer": {"a": REMOVED, "b": 2}}

    update_config_entries(base, changes, pop_key=False)

    assert base == {"outer": {"a": None, "b": 2}}


def test_update_config_entries_list_of_mappings_becoming_empty_results():
    """
    Ensures elements that clean to empty mappings are dropped, not leaving an empty list.
    """
    base = {"outer": {"lst": ["unchanged"]}}  # ensure we truly overwrite with cleaned list

    changes = {
        "outer": {
            "lst": [
                {"x": REMOVED},
                {"y": REMOVED},
            ]
        }
    }

    update_config_entries(base, changes)

    # assert "lst" not in base["outer"]  # cleaned list should be dropped entirely
    assert base == {}


def test_update_config_entries_mixed_nested_lists_and_scalars_clean_correctly():
    """
    A slightly more complex mixed structure to exercise multiple passes of recursion.
    """
    base = {"outer": {"values": [0]}}
    changes = {
        "outer": {
            "values": [
                REMOVED,
                {"k": REMOVED},
                {"k": 3, "t": [REMOVED, 4]},
                2,
            ]
        }
    }

    update_config_entries(base, changes)

    assert base == {"outer": {"values": [{"k": 3, "t": [4]}, 2]}}


def test_update_config_entries_preserved_scalar_skips_change():
    """
    _strip_preserved: scalar PRESERVED -> should_apply=False (skip change).
    """
    base = {"a": 1}
    changes = {"a": PRESERVED}
    update_config_entries(base, changes)
    assert base == {"a": 1}


def test_update_config_entries_preserved_mapping_becomes_empty_skips_key():
    """
    _strip_preserved: mapping where all children are PRESERVED -> nothing left -> skip key.
    """
    base = {"outer": {"x": 1, "y": 2}}
    changes = {"outer": {"x": PRESERVED, "y": PRESERVED}}
    update_config_entries(base, changes)
    assert base == {"outer": {"x": 1, "y": 2}}


def test_update_config_entries_preserved_mapping_whole_mapping_skips_key2():
    """
    _strip_preserved: mapping when PRESERVED is applied to the whole mapping -> skip key.
    """
    base = {"outer": {"x": 1, "y": 2}}
    changes = {"outer": PRESERVED}
    update_config_entries(base, changes)
    assert base == {"outer": {"x": 1, "y": 2}}


def test_update_config_entries_preserved_whole_list_skips_key():
    """
    _strip_preserved: sequence with a single PRESERVED element -> skip updating this key.
    """
    base = {"lst": [0, 1]}
    changes = {"lst": [PRESERVED]}
    update_config_entries(base, changes)
    assert base == {"lst": [0, 1]}


def test_update_config_entries_preserve_keeps_existing_replacing_and_appends():
    """
    List merging is positional: each change[i] replaces or merges with base[i].
    """
    base = {"lst": [10, 12]}
    changes = {"lst": [PRESERVED, 1, 2]}
    update_config_entries(base, changes)
    assert base == {"lst": [10, 1, 2]}


def test_update_config_entries_preserve_keeps_existing_replacing_and_appends2():
    """
    List merging is positional: each change[i] replaces or merges with base[i].
    """
    base = {"lst": [10, 12]}
    changes = {"lst": [1, 2]}
    update_config_entries(base, changes)
    assert base == {"lst": [1, 2]}


def test_merge_lists_positional_shorter_change_list():
    # change list is shorter than base list
    base = {"k": [1, 2, 3, 4]}
    change = {"k": [REMOVED, PRESERVED, 5]}
    update_config_entries(base, change, pop_key=True)
    # remove the first ele, preserve the 2nd ele, change the 3rd to 5, keep the 4th as-is
    assert base == {"k": [2, 5, 4]}


def test_merge_lists_positional_greater_change_list():
    # change list is shorter than base list
    base = {"k": [1, 2, 3]}
    change = {"k": [REMOVED, PRESERVED, 5, 6, 7]}
    update_config_entries(base, change, pop_key=True)
    # remove the first ele, preserve the 2nd ele, change the 3rd to 5, append 6 and 7
    assert base == {"k": [2, 5, 6, 7]}


def test_list_slot_mapping_merge_kept_when_non_empty():
    """
    Both sides are mappings at an index; merging produces non-empty -> slot kept.
    """
    base = {"lst": [{"a": 1}, {"b": 2}]}
    # change merges into index 0, adds 'x': 10
    changes = {"lst": [{"x": 10}]}
    update_config_entries(base, changes, pop_key=True)
    assert base == {"lst": [{"a": 1, "x": 10}, {"b": 2}]}


def test_list_slot_mapping_merge_drops_slot_when_empty_and_pop_key_true():
    """
    Both sides are mappings; change deletes the only key -> merged becomes {}.
    With pop_key=True, empty mapping slot is dropped.
    """
    base = {"lst": [{"a": 1}, {"keep": 1}]}
    # At index 0, remove key 'a' -> merged becomes {}
    changes = {"lst": [{"a": REMOVED}]}
    update_config_entries(base, changes, pop_key=True)
    # Index 0 dropped entirely; the remaining element shifts left
    assert base == {"lst": [{"keep": 1}]}


def test_list_slot_mapping_merge_nested_and_preserve_noop():
    """
    Ensure PRESERVE inside the mapping leaves existing base content untouched.
    """
    base = {"lst": [{"a": {"k": 1}}, {"b": 2}]}
    # At index 0, try to change 'a' but mark it as PRESERVE -> no change, then add 'c'
    changes = {"lst": [{"a": PRESERVED, "c": 3}]}
    update_config_entries(base, changes, pop_key=True)
    assert base == {"lst": [{"a": {"k": 1}, "c": 3}, {"b": 2}]}


def test_recursive_list_merge_basic_replace():
    """
    Both sides have a list at index 0 -> recurse and replace inner scalars positionally.
    """
    base = {"lst": [[10, 20, 30], "unchanged"]}
    # only inner first two replaced; third kept
    changes = {"lst": [[1, 2], PRESERVED]}
    update_config_entries(base, changes, pop_key=True)
    assert base == {"lst": [[1, 2, 30], "unchanged"]}


def test_drop_key_when_cleaned_to_empty_sequence_and_pop_key_true_scalar_base():
    base = {"lst": "list", "keep": 42}
    changes = {"lst": []}  # change is empty list and base is scalar
    update_config_entries(base, changes, pop_key=True)
    assert base == {"keep": 42}  # lst is dropped


def test_remove_state_key_format():
    assert _remove_state_key("k", 3) == "k::REMOVE[3]"


def test_merge_lists_positional_all_remove_returns_none():
    state = {}
    out = _merge_lists_positional(
        base_list=[1, 2, 3],
        change_list=[REMOVED, REMOVED, REMOVED],
        path="k",
        state=state,
        pop_key=True,
    )
    assert out is None


def test_merge_lists_positional_state_base_key_created_and_reused():
    state = {}

    base = [10, 20]
    _merge_lists_positional(
        base_list=base,
        change_list=[PRESERVED],
        path="k",
        state=state,
        pop_key=True,
    )
    assert "k::BASE" in state
    assert state["k::BASE"] == [10, 20]

    # mutate current base_list to prove baseline is stable
    base[:] = [999, 888]

    out2 = _merge_lists_positional(
        base_list=base,
        change_list=[PRESERVED],
        path="k",
        state=state,
        pop_key=True,
    )
    # baseline still the original snapshot
    assert state["k::BASE"] == [10, 20]
    assert out2[0] == 10


def test_merge_lists_positional_preserve_beyond_baseline_raises():
    state = {}
    with pytest.raises(PositionalMergeError):
        _merge_lists_positional(
            base_list=[1],
            change_list=[PRESERVED, PRESERVED],
            path="k",
            state=state,
            pop_key=True,
        )


def test_merge_lists_positional_fills_remaining_with_baseline_slots():
    out = _merge_lists_positional(
        base_list=[10, 20],
        change_list=[],  # no changes
        path="k",
        state={},
        pop_key=True,
    )
    assert out == [10, 20]


def test_update_config_entries_removes_key_when_cleaned_to_empty_mapping():
    base = {"a": 1, "keep": 2}
    changes = {"a": {"x": REMOVED}}  # cleans to {}

    update_config_entries(base, changes, pop_key=True)
    assert base == {"keep": 2}


def test_merge_lists_positional_state_none_is_initialised():
    # state=None triggers the "if state is None: state = {}" line
    out = _merge_lists_positional(
        base_list=[1],
        change_list=[PRESERVED],
        path="k",
        state=None,
        pop_key=True,
    )
    assert out == [1]


def test_merge_lists_positional_mapping_branch_uses_current_mapping_slot():
    state = {}

    # base_list[0] is a mapping, so base0[0] snapshot is a mapping
    base_list = [{"a": 1, "keep": 0}]
    change_list = [{"b": 2}]  # mapping -> triggers mapping merge branch

    out = _merge_lists_positional(
        base_list=base_list,
        change_list=change_list,
        path="k",
        state=state,
        pop_key=True,
    )

    # Crucial assertion: the merged mapping is literally the same object as base_list[0]
    # This proves line 203 "merged = base_list[i]" ran.
    assert out[0] is base_list[0]

    # And content merged as expected
    assert out == [{"a": 1, "keep": 0, "b": 2}]


# def test_empty_mapping_in_change_keeps_existing_slot():
#     base = {"lst": [{"a": 1}, {"b": 2}]}
#     # empty mapping also means PRESERVE
#     changes = {"lst": [{}, {"b": 3}]}
#     update_config_entries(base, changes, pop_key=True)
#     assert base == {"lst": [{"a": 1}, {"b": 3}]}

# def test_empty_mapping_for_missing_slot_does_not_append():
#     base = {"lst": [1]}
#     # {} at i=0 keeps base[0]; {} at i=2 with no base
#     changes = {"lst": [{}, 2, {}]}
#     update_config_entries(base, changes, pop_key=True)
#     assert base == {"lst": [1, 2]}

# def test_empty_mapping_when_base_is_empty_skips_cleanly():
#     base = {"lst": []}
#     changes = {"lst": [{}, {"x": 1}]}
#     update_config_entries(base, changes, pop_key=True)
#     assert base == {"lst": [{"x": 1}]}

# def test_empty_mapping_keeps_nested_types_unchanged():
#     base = {"lst": [{"k": 1}, "keep", [1, 2]]}
#     changes = {"lst": [{}, {"repl": True}, {}]}
#     update_config_entries(base, changes, pop_key=True)
#     # {} at i=0 keeps {"k":1}; {} at i=2 keeps [1,2]
#     assert base == {"lst": [{"k": 1}, {"repl": True}, [1, 2]]}

# def test_double_empty_mapping_beyond_base_is_ignored():
#     base = {"lst": ["only"]}
#      # i=0 keeps "only"; i=1,2 have no base so skipped
#     changes = {"lst": [{}, {}, {}]}
#     update_config_entries(base, changes, pop_key=True)
#     assert base == {"lst": ["only"]}
