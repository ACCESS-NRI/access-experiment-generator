from pathlib import Path
import re
from typing import Any

# allow % inside assignment keys, and in tag lines
_REG_PATTERN = re.compile(r"^(\s*)([%\w]+)\s*=\s*(.*?)\s*(!.*)?$")
# matches lines like "KPP%", or "MLE%XXX" (with optional indent)
_REG_TAG = re.compile(r"^\s*%?\w+(?:%\w+)*%?\s*$")


def read_mom_input(path: str) -> tuple[list[str], dict[str, str]]:
    """
    Read a MOM_input-style file.

    Returns
    -------
    lines   : list[str]        # original text, line-preserving
    params  : dict[str, str]   # key→value pairs (keys may contain '%')
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines(True)
    params: dict[str, str] = {}
    for ln in lines:
        m = _REG_PATTERN.match(ln)
        if m:
            _, name, rhs, _ = m.groups()
            params[name] = rhs.strip()
    return lines, params


def _format_conversion(val: Any) -> str:
    """
    Format conversion -> bools as True/False.
    """
    return "True" if val is True else "False" if val is False else str(val)


def write_mom_input(
    lines: list[str],
    params: dict[str, Any],
    out_path: str,
    remove_missing: bool = True,
) -> None:
    """
    Updating MOM_input lines, preserving original format.

    - Existing keys present in `params` are updated.
      - Only the RHS is changed, comments and spacing are preserved.
      - If the RHS text is identical, the line is unchanged.
    - Existing keys absent from `params` are removed if `remove_missing` is True.
      - The assignment line is removed.
      - Any immediately following comment lines are also removed.
    - New keys in `params` that were not in the original file are appended at the end.
    """
    out: list[str] = []
    skip_comment_block = False
    seen_keys: set[str] = set()

    for ln in lines:
        stripped = ln.strip()

        # skip pure comments after a removed assignment/tag
        if skip_comment_block and stripped.startswith("!"):
            continue
        skip_comment_block = False

        # assignment
        m = _REG_PATTERN.match(ln)
        if m:
            indent, name, rhs, comment = m.groups()
            seen_keys.add(name)

            # remove keys not in params
            if remove_missing and name not in params:
                skip_comment_block = True
                continue

            # If we don't have an override for this key, keep original line
            if name not in params:
                out.append(ln)
                continue

            # keep and rewrite
            new_rhs = _format_conversion(params[name])
            # If rhs unchanged, keep exact line
            if rhs.strip() == new_rhs:
                out.append(ln)
                continue

            # keep everything except rhs
            rhs_left, rhs_right = m.span(3)
            out.append(ln[:rhs_left] + new_rhs + ln[rhs_right:])
            continue

        # section/tag line
        if _REG_TAG.match(stripped):
            out.append(ln)
            continue

        out.append(ln)

    # append new parameters that never existed in the file
    to_add = [k for k in params.keys() if k not in seen_keys]
    if to_add:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.append("\n! --- Added parameters ---\n")
        for k in to_add:
            v = _format_conversion(params[k])
            out.append(f"{k} = {v}\n")

    Path(out_path).write_text("".join(out))
