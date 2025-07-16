import re


def read_runseq(filepath):
    with open(filepath, "r") as f:
        lines = f.readlines()

    inside_block = False
    commands = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("runSeq::"):
            inside_block = True
            continue
        if stripped.startswith("::") and inside_block:
            break
        if inside_block and stripped:
            commands.append(stripped)
    return commands


def modify_runseq(commands, old_val="900", new_val="1080"):
    modified = []
    for cmd in commands:
        if cmd.strip().startswith(f"@{old_val}"):
            match = re.match(rf"@{old_val}\b", cmd.strip())
            if match:
                modified.append(cmd.replace(f"@{old_val}", f"@{new_val}", 1))
                continue
        modified.append(cmd)
    return modified


def write_runseq(commands, output_path):
    with open(output_path, "w") as f:
        f.write("runSeq::\n")
        for cmd in commands:
            f.write(f"  {cmd}\n")
        f.write("::\n")
