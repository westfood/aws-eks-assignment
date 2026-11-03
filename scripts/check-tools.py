#!/usr/bin/env python3
"""Check selected tool versions or Docker readiness without cloud API calls."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parent.parent


def output(command):
    result = subprocess.run(command, text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise ValueError(f"{command[0]} exited with status {result.returncode}")
    return result.stdout.strip() or result.stderr.strip()


def version(text):
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", text.lstrip("v"))
    if not match:
        raise ValueError("Unrecognized version output")
    return match.group(1)


def check_versions():
    expected = tomllib.loads((ROOT / "mise.toml").read_text())["tools"]
    probes = {
        "python": lambda: sys.version.split()[0],
        "terraform": lambda: json.loads(output(["terraform", "version", "-json"]))["terraform_version"],
        "awscli": lambda: version(output(["aws", "--version"])),
        "kubectl": lambda: json.loads(output(["kubectl", "version", "--client=true", "--output=json"]))["clientVersion"]["gitVersion"].removeprefix("v"),
        "helm": lambda: output(["helm", "version", "--template", "{{.Version}}"]).removeprefix("v").split("+")[0],
        "node": lambda: output(["node", "--version"]).removeprefix("v"),
        "actionlint": lambda: version(output(["actionlint", "-version"])),
    }
    failed = False
    for tool, probe in probes.items():
        try:
            actual = probe()
            if actual != expected[tool]:
                raise ValueError(f"selected {actual}; expected {expected[tool]}")
            print(f"PASS {tool} {actual}")
        except (ValueError, OSError, subprocess.SubprocessError, KeyError) as error:
            failed = True
            print(f"FAIL {tool}: {error}", file=sys.stderr)
    if failed:
        print("Use mise install --locked, then mise exec -- python scripts/check-tools.py.", file=sys.stderr)
    return 1 if failed else 0


def check_docker():
    try:
        for label, command in (
            ("Docker CLI", ["docker", "--version"]),
            ("Docker Compose", ["docker", "compose", "version", "--short"]),
            ("Docker Buildx", ["docker", "buildx", "version"]),
            ("Docker engine", ["docker", "version", "--format", "{{.Server.Version}}"]),
        ):
            print(f"PASS {label}: {output(command)}")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"FAIL Docker prerequisite: {error}. Check your installed Docker engine/context and plugins.", file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true", help="Check Docker prerequisites instead of pinned CLI versions")
    arguments = parser.parse_args()
    return check_docker() if arguments.docker else check_versions()


if __name__ == "__main__":
    raise SystemExit(main())
