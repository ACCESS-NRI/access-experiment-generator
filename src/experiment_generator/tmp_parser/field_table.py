from pathlib import Path
import re


HEADER_PATTERN = re.compile(r'^\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*$')
THREE_STRINGS_PATTERN = re.compile(r'^\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*$')
TWO_STRINGS_PATTERN = re.compile(r'^\s*"([^"]*)"\s*,\s*"([^"]*)"\s*$')
ASSIGNMENT_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)\s*=\s*(.*?)\s*$")


def _strip_comments(line: str) -> str:
    if line.lstrip().startswith("#"):
        return ""
    return line.rstrip("\n")


def _split_end(line: str) -> tuple[str, bool]:
    parts = line.rstrip()
    if parts.endswith("/"):
        return parts[:-1].rstrip(), True
    return parts, False


def _parse_param_blob(blob: str) -> dict:
    """
    Specific for 3-quoted method lines
    """
    parts = [p.strip() for p in blob.split(",") if p.strip()]
    param_dict: dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            return {}
        key, value = p.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return {}
        param_dict[key] = value
    return param_dict


def read_field_table(path) -> dict:

    config = {}

    current_header: tuple[str, str, str] | None = None  # field_type, model, field

    with open(Path(path), "r") as f:
        for line in f:
            line = _strip_comments(line)

            if not line.strip():
                continue

            body, is_end = _split_end(line)

            if current_header is None:
                header_match = HEADER_PATTERN.match(body)
                if not header_match:
                    raise ValueError(f"Expected header (3 quoted strings), got: {line.strip()}")
                current_header = (header_match.group(1), header_match.group(2), header_match.group(3))
                methods = []
                if is_end:
                    _store_field(config, current_header, methods)
                    current_header = None
                continue

            # inside a field definition
            if body.strip():
                # 3 strings
                method_match = THREE_STRINGS_PATTERN.match(body)
                if method_match:
                    key, value, blob = method_match.group(1), method_match.group(2), method_match.group(3)
                    param_dict = _parse_param_blob(blob)
                    if param_dict:
                        methods.append({"key": key, "value": value, "params": param_dict})
                else:
                    # 2 strings
                    method_match = TWO_STRINGS_PATTERN.match(body)
                    if method_match:
                        methods.append({"key": method_match.group(1), "value": method_match.group(2)})
                    else:
                        # this is for assignment format - reading only
                        method_match = ASSIGNMENT_PATTERN.match(body)
                        if method_match:
                            methods.append({"key": method_match.group(1), "value": method_match.group(2)})
            if is_end:
                _store_field(config, current_header, methods)
                current_header = None
                methods = []

    if current_header is not None:
        raise ValueError(f"Unclosed entry {current_header} (missing trailing '/' terminator).")

    return config


def _store_field(config: dict, header: tuple[str, str, str], methods: list[dict]) -> None:
    field_type, model, field = header

    if field not in config:
        config[field] = {}
    if model not in config[field]:
        config[field][model] = {}
    if field_type not in config[field][model]:
        config[field][model][field_type] = {"methods": []}

    config[field][model][field_type]["methods"].extend(methods)


def _params_to_blob(params: dict) -> str:
    """
    Convert parameter dictionary to blob string.
    """
    parts = []
    for key in sorted(params.keys()):
        value = params[key]
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def write_field_table(config: dict, file: Path) -> None:
    """
    Only write in strict 2-quoted / 3-quoted format for consistency.

    - Header: "field_type","model","field"
    - Method: "key","value" or "key","value","k=v,k2=v2,k3=v3..."
    - End: '/' on the last line of the entry only
    """
    with open(Path(file), "w") as f:
        first = True  # to manage the first blank line and blank lines between entries

        for field in config.keys():
            for model in config[field].keys():
                for field_type in config[field][model].keys():
                    block = config[field][model][field_type] or {}
                    # print(block)
                    methods = block.get("methods", [])

                    if not first:
                        f.write("\n")
                    first = False

                    # header must be field_type, model, field
                    f.write(f'"{field_type}", "{model}", "{field}"\n')

                    if not methods:
                        f.write(" /\n")
                        continue

                    for index, method in enumerate(methods):
                        key = method.get("key")
                        value = method.get("value")
                        params = method.get("params", {})

                        if isinstance(params, dict) and params:
                            blob = _params_to_blob(params)
                            line = f'"{key}", "{value}", "{blob}"'
                        else:
                            line = f'"{key}", "{value}"'

                        f.write(line + ("\n/\n" if index == len(methods) - 1 else "\n"))
