from experiment_generator.utils import update_config_entries


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
        "b": {"y": 3, "z": 5},
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
        # "a" removed
    }

    update_config_entries(base, changes)
    assert base == expected
