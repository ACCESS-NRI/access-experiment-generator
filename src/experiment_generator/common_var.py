from collections.abc import Sequence

# Experiment specific attributes
BRANCH_KEY = "branches"
REMOVED = "REMOVE"
RESERVED = "RESERVE"


def _is_removed_str(x) -> bool:
    """
    Check if a value is the explicit delete marker ("REMOVE").

    Returns True if `x` is a string equal to REMOVED, otherwise False.
    """
    return isinstance(x, str) and x == REMOVED


def _is_reserved_str(x) -> bool:
    """
    Check if a value is the explicit keep marker ("RESERVED").

    Returns True if `x` is a string equal to RESERVED, otherwise False.
    """
    return isinstance(x, str) and x == RESERVED


def _is_seq(x) -> bool:
    """
    Check if a value is a sequence (e.g. list) but not a string.

    Returns True if `x` is a sequence and not a string, otherwise False.
    """
    return isinstance(x, Sequence) and not isinstance(x, str)
