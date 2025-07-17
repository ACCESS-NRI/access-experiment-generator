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
    comm_width: int = 31,
    pop_key: bool = True,  # expose the flag used internally
) -> None:
    """
    Rewrite `lines` using updated `params`, writing to `out_path`.

    • Keys still present in `params` are rewritten with new values.
    • Keys missing from `params` are removed (plus any immediate comment block).
    • New keys in `params` are appended at the end under a banner.
    """
    comm_col = comm_width + 1
    out: list[str] = []
    skip_comment_block = False
    align_comment = False

    for ln in lines:
        stripped = ln.strip()

        # skip pure comments after a removed assignment/tag
        if skip_comment_block and stripped.startswith("!"):
            continue
        skip_comment_block = False

        # assignment
        m = _REG_PATTERN.match(ln)
        if m:
            indent, name, _, comment = m.groups()

            # remove tags
            if name not in params:
                skip_comment_block = True
                align_comment = False
                continue

            # keep and rewrite
            new_rhs = _format_conversion(params[name])
            lhs = f"{indent}{name} = {new_rhs}"
            if comment:
                lhs = lhs.ljust(comm_width) + " !   " + comment.lstrip("! ").rstrip("\n")
            out.append(lhs + "\n")
            align_comment = True
            continue

        # section/tag line
        if _REG_TAG.match(stripped):
            out.append(ln)
            continue

        # pure-comment after a rewrite hence align it
        if align_comment and stripped.startswith("!"):
            out.append(" " * comm_col + "!   " + ln.lstrip("! ").rstrip("\n") + "\n")
            continue

        align_comment = False
        out.append(ln)

    # append new parameters that never existed in the file
    existing_keys = {m.group(2) for m in map(_REG_PATTERN.match, lines) if m}
    to_add = [k for k in params if k not in existing_keys]
    if to_add:
        out.append("\n! --- Added parameters ---\n")
        for k in to_add:
            v = _format_conversion(params[k])
            out.append(f"{k} = {v}".ljust(comm_width) + "\n")

    Path(out_path).write_text("".join(out))
