import pytest

from experiment_generator.common_var import (
    REMOVED,
    PRESERVED,
    _is_removed_str,
    _is_preserved_str,
    _is_seq,
)


def test_is_removed_str_true():
    assert _is_removed_str(REMOVED) is True


@pytest.mark.parametrize(
    "value",
    [
        PRESERVED,  # other marker
        "REMOVE ",  # similar but not exact
        " ",  # empty string
        None,  # None value
        1,  # integer
        ["REMOVE"],  # list
    ],
)
def test_is_removed_str_false(value):
    assert _is_removed_str(value) is False


def test_is_preserved_str_true():
    assert _is_preserved_str(PRESERVED) is True


@pytest.mark.parametrize(
    "value",
    [
        REMOVED,  # other marker
        "PRESERVE ",  # similar but not exact
        " ",  # empty string
        None,  # None value
        1,  # integer
        ["PRESERVE"],  # list
    ],
)
def test_is_preserved_str_false(value):
    assert _is_preserved_str(value) is False


@pytest.mark.parametrize(
    "value",
    [
        [],  # list
        [1, 2, 3],  # list with integers
        (),  # tuple
        ("a", "b"),  # tuple
        ("a",),
    ],
)
def test_is_seq_true(value):
    assert _is_seq(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "abc",  # string
        "",  # empty string
        None,
        123,
        1.23,
        {"a": 1},  # mapping (not Sequence)
    ],
)
def test_is_seq_false(value):
    assert _is_seq(value) is False
