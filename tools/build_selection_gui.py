"""Build the standalone priority editor for the Windows release package."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("selection GUI package currently targets Windows")
    # Keep the previous development executable available while its window is open.
    output = ROOT / "build" / "selection_gui" / "current"
    pyinstaller([
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "ma9-selection",
        "--paths", str(ROOT / "agent"),
        "--distpath", str(output / "dist"),
        "--workpath", str(output / "work"),
        "--specpath", str(output / "spec"),
        str(ROOT / "tools" / "selection_gui.py"),
    ])
    result = output / "dist" / "ma9-selection.exe"
    if not result.is_file():
        raise FileNotFoundError(result)
    print(f"Selection GUI built: {result}")


if __name__ == "__main__":
    main()
