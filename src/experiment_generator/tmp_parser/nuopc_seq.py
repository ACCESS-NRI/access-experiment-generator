from pathlib import Path


def read_runseq(filepath: Path) -> list[str]:
    with open(filepath, "r") as f:
        lines = f.readlines()

    inside_block = False
    commands: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("runSeq::"):
            inside_block = True
            continue
        if inside_block and stripped == "::":
            break
        if inside_block and stripped:
            commands.append(stripped)
    return commands


def modify_runseq(
    commands: list[str],
    old_val: str | None = None,
    new_val: str | None = None,
    new_block: str | None = None,
) -> list[str]:
    """
    if new_block is provided, replace entire runSeq block with new_block. Otherwise,
    replace line starting with @old_val with @new_val.
    """
    if new_block is not None:
        return [line.strip() for line in new_block.splitlines() if line.strip()]

    new_commands = []
    for cmd in commands:
        if cmd.strip().startswith(f"@{old_val}"):
            new_commands.append(f"@{new_val}")
        else:
            new_commands.append(cmd)
    return new_commands


def write_runseq(commands: list[str], output_path: Path, indent: int = 2):
    with open(output_path, "w") as f:
        f.write("runSeq::\n")
        for cmd in commands:
            tmp = cmd.strip()
            if not tmp:
                continue
            if tmp.startswith("@"):
                f.write(f"{tmp}\n")
            else:
                f.write(f"{' ' * indent}{tmp}\n")
        f.write("::\n")
