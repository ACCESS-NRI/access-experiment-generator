"""
Configuration file updater.

Every configuration file handled here has a parser with the same interface: `parse(text)` returns a
dict that is edited in place, and `str()` of that dict is the text to write back, unchanged apart from
the edits. That covers the parsers from access-config-utils (YAML, JSON, MOM6 input, NUOPC runconfig and
run sequence, Fortran namelists and FMS field tables), so one updater serves them all: parse the file,
merge the parameters from the YAML input with `update_config_entries`, and write the file back.

A few files need more than that generic merge. Most have a hook that runs on the parsed file first and
says which part of it to merge which changes into:
 - `config.yaml`: `jobname` is forced to be the name of the experiment directory.
 - Fortran namelists: each group is merged on its own, so that a group left empty stays in the file for
   the model to read; CICE's `turning_angle` is converted to `cosw`/`sinw`; and a string written in
   Fortran syntax is converted to the values it stands for.
 - `MOM_input`: a parameter given at the top level that the file only has in a block is refused.
 - `atmosphere/forcing.json`: each field is looked up in `inputs`, and its perturbations validated.

Two files are not a merge of the parameters at all, so they apply the parameters themselves:
 - `nuopc.runseq`: the parameters are `cpl_dt`, the new value of the first time loop, or `runseq_block`,
   a whole new run sequence.
 - `field_table`: the parameters are laid out by field, model and field type, with the methods of each
   entry as a list, and are merged on that layout before only the lines that changed are written.

A value of ~ (None) is only written to YAML files, as a null value. Every other file refuses it: each
format has its own idea of a key with no value, and REMOVE and PRESERVE say what is meant instead.
"""

import math
import os
import re
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from access.config import (
    FieldTableParser,
    FortranNMLParser,
    JSONParser,
    MOM6InputParser,
    NUOPCParser,
    NUOPCRunSeqParser,
    YAMLParser,
)
from access.config.config_dict import ConfigBlockList

from .common_var import PRESERVED, REMOVED, _is_preserved_str, _is_removed_str
from .utils import _plain, update_config_entries

# A part of a parsed file, the changes to merge into it, and the path to report them under
MergeTarget = tuple[dict, dict, str]


def _merge_at_root(config: dict, params: dict, target_file: str, directory: Path) -> list[MergeTarget]:
    return [(config, params, target_file)]


def _refuse_none(params: dict, path: str) -> None:
    """
    Refuse ~ (None) in the changes to a file that is not a YAML file.
    """
    for key, value in params.items():
        key_path = f"{path}.{key}"
        if value is None or (isinstance(value, list) and None in value):
            raise ValueError(
                f"\n -- {key_path}: ~ (no value) can only be written to a YAML file: use REMOVE to remove it "
                "(the model then uses its default) or PRESERVE to keep its value"
            )
        if isinstance(value, dict):
            _refuse_none(value, key_path)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    _refuse_none(item, f"{key_path}[{i}]")


# --- config.yaml ---


def _prepare_yaml(config: dict, params: dict, target_file: str, directory: Path) -> list[MergeTarget]:
    """
    Force `jobname` in payu's `config.yaml` to be the name of the experiment directory.
    """
    if Path(target_file).name != "config.yaml":
        return _merge_at_root(config, params, target_file, directory)

    if "jobname" in params and params["jobname"] != directory.name:
        warnings.warn(
            f"\n-- jobname must be the same as {directory.name}, hence jobname is forced to be {directory.name}!",
            UserWarning,
        )
    return [(config, {**params, "jobname": directory.name}, target_file)]


# --- Fortran namelists ---

CICE_NAMELISTS = ("cice_in.nml", "ice_in")

# Fortran constants, as they could be written in the YAML input
_FORTRAN_STRING = re.compile(r"""'((?:[^']|'')*)'|"((?:[^"]|"")*)\"""")
_FORTRAN_INTEGER = re.compile(r"[+-]?\d+")
_FORTRAN_REAL = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][+-]?\d+)?")
_FORTRAN_LOGICALS = {".true.": True, ".t.": True, ".false.": False, ".f.": False}


def _fortran_constant(text: str, as_string: bool = False) -> tuple[bool, object]:
    """
    Convert the text of one Fortran constant to its Python value.

    Returns whether the text is a Fortran constant, and its value if it is. With `as_string`, for a
    variable that holds strings, unquoted text is the string it spells (e.g. `001` or `m`), not a number
    or a logical.
    """
    text = text.strip()
    match = _FORTRAN_STRING.fullmatch(text)
    if match:
        if match.group(1) is not None:
            return True, match.group(1).replace("''", "'")
        return True, match.group(2).replace('""', '"')
    if as_string:
        return True, text
    if text.lower() in _FORTRAN_LOGICALS:
        return True, _FORTRAN_LOGICALS[text.lower()]
    if _FORTRAN_INTEGER.fullmatch(text):
        return True, int(text)
    if _FORTRAN_REAL.fullmatch(text):
        return True, float(text.lower().replace("d", "e"))
    return False, text


def _split_fortran_list(text: str) -> list[str]:
    """
    Split the text of a list of Fortran constants at the commas that are not inside quotes.
    """
    items, item, quote = [], "", None
    for char in text:
        if quote:
            # a doubled quote inside a string closes and opens it again
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == ",":
            items.append(item)
            item = ""
            continue
        item += char
    return [*items, item]


def _holds_strings(current) -> bool:
    """
    Whether the value in the file is a string, or a list of strings.
    """
    if isinstance(current, list):
        return bool(current) and all(isinstance(item, str) for item in current)
    return isinstance(current, str)


def _from_fortran_text(value, current=None):
    """
    Convert a string written in Fortran syntax to the value(s) it stands for.

    Namelist values used to be written into the file as given, so the YAML input could hold the Fortran
    text itself, e.g. `fields_in: "'u_flux', 'v_flux'"`, `processor_shape: "'slenderX1'"` or
    `flag: .true.` (which YAML reads as a string). A string that is a Fortran constant, or a
    comma-separated list of them, is converted; anything else is left as the string it is.

    `current`, the value in the file, tells a string from a number: where the file holds a string,
    unquoted text is that string (e.g. `001`), and where it holds a list of strings, unquoted items are
    strings (e.g. `m, d, x`). Elsewhere, e.g. for a new variable, numbers and logicals are converted.
    """
    if not isinstance(value, str):
        return value
    as_string = _holds_strings(current)
    if as_string and not isinstance(current, list):
        # a string variable: its new value is the text, without the quotes if it has them
        return _fortran_constant(value, as_string=True)[1]

    # a single string constant may itself contain commas
    is_constant, constant = _fortran_constant(value)
    if is_constant:
        return constant

    items = _split_fortran_list(value)
    if len(items) == 1:
        return value
    constants = [_fortran_constant(item, as_string) for item in items]
    if not all(is_constant for is_constant, _ in constants):
        return value
    return [constant for _, constant in constants]


def _turning_angle_changes(config: dict, turning_angle) -> dict:
    """
    The changes to `cosw` and `sinw` in CICE's `dynamics_nml` that a `turning_angle` stands for.

    ref: https://github.com/aekiss/ensemble/blob/b27e4b7992683e4308bf630aa16da21730ccb11a/ensemble.py#L63C77-L63C89
    """
    if _is_removed_str(turning_angle):
        return {"cosw": REMOVED, "sinw": REMOVED}

    if _is_preserved_str(turning_angle):
        dyn = config.get("dynamics_nml", {})
        if "cosw" not in dyn and "sinw" not in dyn:
            raise ValueError("Cannot preserve turning_angle: no existing cosw and sinw found in `dynamics_nml`")
        return {}

    angle = math.radians(turning_angle)
    return {"cosw": math.cos(angle), "sinw": math.sin(angle)}


def _prepare_namelist(config: dict, params: dict, target_file: str, directory: Path) -> list[MergeTarget]:
    """
    Merge each namelist group on its own.

    The groups themselves are never removed, even when all their variables are, because the model
    reading the file expects to find them. A group not in the file yet is added.
    """
    targets = []
    for group_name, group_value in params.items():
        if not isinstance(group_value, dict):
            raise ValueError(f"Expected dict for {group_name}, got {type(group_value)}")
        if isinstance(config.get(group_name), ConfigBlockList):
            raise ValueError(
                f"\n -- {target_file}: namelist group '{group_name}' appears more than once in the file, "
                "so it is not clear which one to update!"
            )

        group = config.get(group_name) or {}
        changes = {var: _from_fortran_text(value, group.get(var)) for var, value in group_value.items()}

        # `turning_angle` is never written itself: in CICE namelists, it sets cosw and sinw instead
        if group_name == "dynamics_nml" and "turning_angle" in changes:
            # checked here, as it is not among the changes returned
            _refuse_none({"turning_angle": changes["turning_angle"]}, f"{target_file}.{group_name}")
            turning_angle = changes.pop("turning_angle")
            if target_file.endswith(CICE_NAMELISTS):
                # an explicit cosw or sinw takes precedence
                changes = {**_turning_angle_changes(config, turning_angle), **changes}

        if group_name not in config:
            config[group_name] = {}
        targets.append((config[group_name], changes, f"{target_file}.{group_name}"))

    return targets


# --- MOM_input ---


def _blocks_holding(config: dict, key: str) -> list[str]:
    """
    The names of the parameter blocks (e.g. `MLE` for `MLE%` ... `%MLE`) that hold `key`.
    """
    return [name for name, block in config.items() if isinstance(block, dict) and key in block]


def _prepare_mom_input(config: dict, params: dict, target_file: str, directory: Path) -> list[MergeTarget]:
    """
    Refuse a parameter given at the top level that the file only has in a block.

    A parameter at the top level of the YAML input is a top-level parameter, and the parameters of a
    block are nested under its name, e.g. `MLE: {USE_BODNER23: false}`. The old parser did not read
    the blocks, so YAML inputs written for it give them at the top level, where they would be added
    as new parameters that MOM6 ignores, as they are outside their block.
    """
    for key, value in params.items():
        if isinstance(value, dict) or key in config:
            continue
        blocks = _blocks_holding(config, key)
        if blocks:
            raise ValueError(
                f"\n -- {target_file}: '{key}' is in the {', '.join(f'{b}%' for b in blocks)} "
                f"block{'s' if len(blocks) > 1 else ''}, not at the top level: nest it under its block, "
                f"e.g. `{blocks[0]}: {{{key}: ...}}`"
            )

    return _merge_at_root(config, params, target_file, directory)


# --- atmosphere/forcing.json (ACCESS-OM2) ---

ALLOWED_PERTURBATION_TYPES = {"scaling", "offset", "separable", REMOVED, PRESERVED}


def _find_matching_param_index(inputs: list, fieldname: str) -> int | None:
    """
    Locate the index of a parameter in the 'inputs' list by field name.
    """
    for i, base in enumerate(inputs):
        if base.get("fieldname") == fieldname:
            return i
    return None


def _validate_single_perturbation(pert: dict) -> None:
    """
    Validate a single perturbation dict.
    """
    if pert["type"] not in ALLOWED_PERTURBATION_TYPES:
        raise ValueError(f"Invalid perturbation type: {pert['type']}")

    dim = pert["dimension"]
    accepted_dim = (isinstance(dim, str) and dim in {"spatial", "temporal", "constant", "spatiotemporal"}) or (
        isinstance(dim, list) and dim == ["temporal", "spatial"]
    )
    if not accepted_dim:
        raise ValueError(f"Invalid perturbation dimension: {dim}")

    if pert["calendar"] not in {"forcing", "experiment"}:
        raise ValueError(f"Invalid perturbation calendar: {pert['calendar']}")


def _preprocess_perturbations(fieldname: str, updates: dict) -> None:
    """
    Process `updates["perturbations"]`.
    Warns and removes the key from `updates` if unsuitable.
    """
    perts = updates.get("perturbations")

    # treat empty as "no change"
    if perts in ({}, []):
        warnings.warn(
            f"-- forcing.json '{fieldname}': empty 'perturbations' provided; skipping.",
            UserWarning,
        )
        updates.pop("perturbations", None)
        return

    # accept dict -> wrap it to list[dict]
    if isinstance(perts, dict):
        perts = [perts]
    elif not isinstance(perts, list) or not all(isinstance(pert, dict) for pert in perts):
        raise TypeError(f"-- forcing.json '{fieldname}': 'perturbations' must be a dict or list of dicts")

    # cleaned is list of dicts
    cleaned = []
    for p in perts:
        # A value given once for every branch arrives as a one-element list, which the merge would
        # unwrap for a key of the file but not inside a new perturbation. No field of a perturbation is
        # a one-element list (a separable one has two dimensions and two files), so unwrap it here.
        q = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in p.items()}
        t_ = q.get("type")

        # skip if REMOVED, and if PRESERVE keep the existing perturbation at this index
        if _is_removed_str(t_) or _is_preserved_str(t_):
            continue

        # Drop any fields set to PRESERVE within this perturbation (leave those as-is on disk)
        for k in list(q.keys()):
            if _is_preserved_str(q[k]):
                q.pop(k, None)

        if not isinstance(t_, str) or t_ not in ALLOWED_PERTURBATION_TYPES:
            raise ValueError(
                f"-- forcing.json '{fieldname}': perturbation has invalid type '{t_}'. "
                f"Allowed types: {sorted(ALLOWED_PERTURBATION_TYPES)}"
            )

        cleaned.append(q)

    if not cleaned:
        warnings.warn(
            f"-- forcing.json: all perturbations for field '{fieldname}' are marked for removal; "
            "skipping perturbations.",
            UserWarning,
        )
        # Drop the key so it doesn't carry an empty/removed set forward
        updates.pop("perturbations", None)
        return

    for pert in cleaned:
        _validate_single_perturbation(pert)

    # keep only the cleaned ones
    updates["perturbations"] = cleaned


def _prepare_forcing(config: dict, params: dict, target_file: str, directory: Path) -> list[MergeTarget]:
    """
    Merge the changes for each field into its entry in `inputs`.
    """
    targets = []
    for fieldname, field_updates in params.items():
        idx = _find_matching_param_index(config["inputs"], fieldname)
        if idx is None:
            raise ValueError("Did not find a valid perturbed fieldname!")

        updates = dict(field_updates)
        if "perturbations" in updates:
            perts = updates["perturbations"]
            if perts is None:
                # checked here, as an empty set of perturbations is dropped below
                _refuse_none({"perturbations": perts}, f"{target_file}.{fieldname}")
            if _is_preserved_str(perts) or (
                isinstance(perts, list) and len(perts) == 1 and _is_preserved_str(perts[0])
            ):
                # don't touch existing perts for this field
                updates.pop("perturbations")
            else:
                _preprocess_perturbations(fieldname, updates)

        # Drop any top-level keys explicitly marked PRESERVE (do not change this key)
        updates = {k: v for k, v in updates.items() if not _is_preserved_str(v)}

        field = config["inputs"][idx]
        if "perturbations" in updates:
            # merge into a list, as a single perturbation would otherwise be written as a dict
            # (a one-element list is taken as a single value for a key that is not a list yet)
            field.setdefault("perturbations", [])

        targets.append((field, updates, target_file))

    return targets


# --- nuopc.runseq ---

_TIME_LOOP = re.compile(r"@\d+(\.\d*)?")
_RUNSEQ_PARAMS = ("cpl_dt", "runseq_block")


def _apply_runseq(config: dict, params: dict, target_file: str, directory: Path, state: dict | None) -> None:
    """
    Replace the whole run sequence by `runseq_block`, or else the first time loop by `@<cpl_dt>`.

    Nothing changes when neither is given, e.g. for a branch whose `cpl_dt` is PRESERVE.
    """
    unknown = [key for key in params if key not in _RUNSEQ_PARAMS]
    if unknown:
        raise ValueError(f"\n -- {target_file}: unknown parameters {unknown}, only {list(_RUNSEQ_PARAMS)} can be set")

    if params.get("runseq_block"):
        lines = [line.strip() for line in params["runseq_block"].splitlines() if line.strip()]
        if len(lines) < 2:
            raise ValueError("runseq_block must have at least two lines")
        config["runSeq"] = lines
        return

    cpl_dt = params.get("cpl_dt", PRESERVED)
    if _is_preserved_str(cpl_dt):
        return
    # the new line has to be a time loop itself, so REMOVE or a negative value are refused
    if not _TIME_LOOP.fullmatch(f"@{cpl_dt}"):
        raise ValueError(f"\n -- {target_file}: cpl_dt must be a number of seconds, not {cpl_dt!r}")

    run_sequence = config["runSeq"]
    index = next(
        (i for i, line in enumerate(run_sequence) if _TIME_LOOP.fullmatch(line.strip())),
        None,
    )
    if index is None:
        raise ValueError("Could not find a line beginning with '@<number>'in nuopc.runseq file")
    run_sequence[index] = f"@{cpl_dt}"


# --- field_table ---


def prune_empty_field_table_config(config: dict) -> None:
    """
    In field_table semantics, an entry with no methods should be removed entirely.
    """
    # config[field][model][field_type] = {"methods": [...]}
    for field in list(config.keys()):
        field_map = config[field]
        for model in list(field_map.keys()):
            model_map = field_map[model]
            for field_type in list(model_map.keys()):
                block = model_map[field_type]
                methods = block.get("methods", None)

                # treat missing methods as no entry
                if not methods:
                    del model_map[field_type]

            if not model_map:
                del field_map[model]
        if not field_map:
            del config[field]


def _typed(value):
    """
    Return the number a string spells, as the field table parser reads one, or the value itself.

    The value is made a builtin first: the YAML input is loaded round-trip, so a float in it is
    ruamel.yaml's `ScalarFloat`, which the parsed field table refuses, as a parsed `Config` does.
    """
    value = _plain(value)
    if isinstance(value, str):
        for convert in (int, float):
            try:
                return convert(value)
            except ValueError:
                pass
    return value


def _methods_view(entry: dict) -> dict:
    """
    The methods of a field in the layout of the input: one `{"key", "value"[, "params"]}` per line.
    """
    methods = []
    for key, value in entry.items():
        if isinstance(value, list):
            for record in value:
                params = {k: v for k, v in record.items() if k != "value"}
                methods.append({"key": key, "value": record["value"], "params": params})
        else:
            methods.append({"key": key, "value": value})
    return {"methods": methods}


def _methods_entry(methods: list) -> dict:
    """
    The methods of a field as the field table parser lays them out: a method with parameters is
    one record of a list, any other is a value.
    """
    entry: dict = {}
    for method in methods:
        key, params = str(method["key"]).lower(), method.get("params") or {}
        if params:
            record = {
                "value": _typed(method["value"]),
                **{k: _typed(v) for k, v in params.items()},
            }
            if not isinstance(entry.setdefault(key, []), list):
                raise ValueError(f"'{key}' is both a method with parameters and one without")
            entry[key].append(record)
        else:
            entry[key] = _typed(method["value"])
    return entry


def _sync_entry(block: dict, entry: dict) -> None:
    """
    Make the methods of a field in the file those of `entry`, changing only what differs.
    """
    for key in [key for key in block if key not in entry]:
        del block[key]
    for key, value in entry.items():
        if key in block and block[key] == value:
            continue
        try:
            block[key] = value
        except (TypeError, ValueError):
            # the value cannot take the place of the old one (another type, or a list of another
            # shape): write it anew, at the end
            if key in block:
                del block[key]
            block[key] = value


def _sync(config: dict, wanted: dict, spelling: dict) -> None:
    """
    Make the headers of the file those of `wanted`: remove the ones that went, change the
    ones that stay, and add the new ones after the last.
    """
    for field_type, model, field in [
        (field_type, model, field)
        for field_type, models in config.items()
        for model, fields in models.items()
        for field in fields
    ]:
        if (field_type, model, field) not in wanted:
            # deleting the last entry of a model or a type takes the empty block with it
            del config[field_type][model][field]

    for (field_type, model, field), entry in wanted.items():
        if field_type in config and model in config[field_type] and field in config[field_type][model]:
            _sync_entry(config[field_type][model][field], entry)
            continue
        names = spelling.get((field_type, model, field), (field_type, model, field))
        # a header written for the first time, with whatever of its path the file lacks
        node = config
        for depth, name in enumerate(names):
            if name not in node:
                nested = entry
                for inner in reversed(names[depth + 1 :]):
                    nested = {inner: nested}
                node[name] = nested
                break
            node = node[name]


def _apply_field_table(config: dict, params: dict, target_file: str, directory: Path, state: dict | None) -> None:
    """
    Merge the parameters, laid out as `{field: {model: {field_type: {"methods": [...]}}}}` with each method
    a line of the entry in the order of the file, into the field table.
    """
    # The parser reads the names of a header in lower case, as the field manager does.
    spelling = {}  # the names as written in the input, for a header that is not in the file yet
    changes: dict = {}
    for field, models in params.items():
        for model, field_types in models.items():
            for field_type, block in field_types.items():
                names = tuple(name.lower() for name in (field, model, field_type))
                spelling[(names[2], names[1], names[0])] = (field_type, model, field)
                changes.setdefault(names[0], {}).setdefault(names[1], {})[names[2]] = block

    view: dict = {}
    for field_type, models in config.items():
        for model, fields in models.items():
            for field, entry in fields.items():
                view.setdefault(field, {}).setdefault(model, {})[field_type] = _methods_view(entry)

    update_config_entries(view, changes, pop_key=True, path=target_file, state=state)
    prune_empty_field_table_config(view)

    wanted = {
        (field_type, model, field): _methods_entry(block["methods"])
        for field, models in view.items()
        for model, field_types in models.items()
        for field_type, block in field_types.items()
    }
    _sync(config, wanted, spelling)


# --- the updater ---


@dataclass(frozen=True)
class _Format:
    matches: Callable[[str], bool]
    parser: type
    prepare: Callable[[dict, dict, str, Path], list[MergeTarget]] = _merge_at_root
    # takes the place of `prepare` and the generic merge, for a file whose parameters are not a merge
    apply: Callable[[dict, dict, str, Path, dict | None], None] | None = None
    # whether ~ (None) can be written, as a null value
    accepts_none: bool = False


def _is_namelist(filename: str) -> bool:
    return filename.endswith("_in") or filename.endswith(".nml") or os.path.basename(filename) == "namelists"


_FORMATS = (
    _Format(_is_namelist, FortranNMLParser, _prepare_namelist),
    _Format(lambda filename: filename.endswith(".yaml"), YAMLParser, _prepare_yaml, accepts_none=True),
    _Format(lambda filename: filename == "nuopc.runconfig", NUOPCParser),
    _Format(lambda filename: filename == "MOM_input", MOM6InputParser, _prepare_mom_input),
    _Format(lambda filename: filename == "atmosphere/forcing.json", JSONParser, _prepare_forcing),
    _Format(lambda filename: filename == "nuopc.runseq", NUOPCRunSeqParser, apply=_apply_runseq),
    _Format(lambda filename: filename.endswith("field_table"), FieldTableParser, apply=_apply_field_table),
)


def _format_for(filename: str) -> _Format | None:
    return next((fmt for fmt in _FORMATS if fmt.matches(filename)), None)


class ConfigFileUpdater:
    """
    Updates any configuration file that one of the parsers can read.
    """

    def __init__(self, directory: Path) -> None:
        """
        Initialise the updater with the experiment directory.
        """
        self.directory = Path(directory)

    @staticmethod
    def parser_for(filename: str):
        """
        Return the parser for a configuration file, or None if there is no parser for it.
        """
        fmt = _format_for(str(filename))
        return None if fmt is None else fmt.parser()

    def update_params(self, param_dict: dict, target_file: str, state: dict | None = None) -> None:
        """
        Update a configuration file with the parameters from the YAML input, and overwrite it.

        Args:
            param_dict (dict): Parameters to update, add or remove ("REMOVE"), nested as in the file.
            target_file (str): Path of the file, relative to the experiment directory.
            state (dict | None): State of positional REMOVE markers, see `update_config_entries`.
        """
        filename = str(target_file)
        fmt = _format_for(filename)
        if fmt is None:
            raise ValueError(f"No parser available for {filename}")

        path = self.directory / filename
        text = path.read_text(encoding="utf-8")
        try:
            config = fmt.parser().parse(text)
        except Exception as err:
            # the parser's message gives the line and the column, but not the file
            raise ValueError(
                f"\n -- {filename}: {fmt.parser.__name__} cannot read this file, so it is not changed:\n{err}"
            ) from err

        if fmt.apply is not None:
            if not fmt.accepts_none:
                _refuse_none(param_dict, filename)
            fmt.apply(config, param_dict, filename, self.directory, state)
        else:
            for base, changes, change_path in fmt.prepare(config, param_dict, filename, self.directory):
                # the changes as they will be written, e.g. without the perturbations marked REMOVE
                if not fmt.accepts_none:
                    _refuse_none(changes, change_path)
                update_config_entries(base, changes, pop_key=True, path=change_path, state=state)

        # write to a temporary file first, so that a failure cannot leave the file half written
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.write_text(str(config), encoding="utf-8")
        tmp_path.replace(path)
