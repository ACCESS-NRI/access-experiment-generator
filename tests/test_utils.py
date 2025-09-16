from experiment_generator.utils import update_config_entries
from experiment_generator.common_var import REMOVED


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
        "c": "REMOVE",
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
        "a": "REMOVE",
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
