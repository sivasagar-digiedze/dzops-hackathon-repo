import subprocess

def extract_commands(output):
    commands = []
    capture = False

    for line in output.split("\n"):
        line = line.strip()

        if line.lower().startswith("commands"):
            capture = True
            continue

        if capture:
            if not line or ":" in line:
                break

            commands.append(line.replace("*", "").strip())

    return commands


def run_commands(commands):
    results = []

    for cmd in commands:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        results.append({
            "command": cmd,
            "output": result.stdout,
            "error": result.stderr
        })

    return results