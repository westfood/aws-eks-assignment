#!/usr/bin/env python3
"""Export both pages of architecture.drawio using draw.io Desktop.

The .drawio file is the editable source. Tested with Desktop 32.6.1; its
--page-index option is 1-based. This script does not change the source file.
Set DRAWIO_BIN to the desktop executable if it is not installed on PATH.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


DIRECTORY = Path(__file__).resolve().parent


def find_drawio():
    candidates = [
        os.environ.get("DRAWIO_BIN"),
        shutil.which("drawio"),
        shutil.which("draw.io"),
        "/Applications/draw.io.app/Contents/MacOS/draw.io",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("Install draw.io Desktop or set DRAWIO_BIN to its executable.")


def main():
    executable = find_drawio()
    with tempfile.TemporaryDirectory(prefix="aws-eks-diagram-") as profile:
        for page, name in ((1, "architecture"), (2, "architecture-identity")):
            for extension in ("svg", "png"):
                output = DIRECTORY / f"{name}.{extension}"
                command = [
                    executable, "--disable-update", f"--user-data-dir={profile}",
                    "--export", "--format", extension, "--theme", "light",
                    "--page-index", str(page), "--border", "24", "--embed-diagram",
                    "--timeout", "60", "--output", str(output),
                ]
                if extension == "svg":
                    command += ["--embed-svg-images", "--embed-svg-fonts", "false"]
                command.append(str(DIRECTORY / "architecture.drawio"))
                subprocess.run(command, check=True, timeout=90)
                if not output.is_file() or output.stat().st_size == 0:
                    raise SystemExit(f"draw.io did not produce {output.name}")
                print(f"Exported {output.name}", flush=True)


if __name__ == "__main__":
    main()
