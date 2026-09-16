"""Build a self-contained MA9 Agent for the current desktop platform."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

import maa
from PyInstaller.__main__ import run as run_pyinstaller


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"


def platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = {"windows": "win", "darwin": "macos", "linux": "linux"}.get(system)
    arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    if os_name is None:
        raise RuntimeError(f"unsupported build platform: {system}/{machine}")
    return f"{os_name}-{arch}"


def required_maa_binaries() -> list[Path]:
    binary_dir = Path(maa.__file__).resolve().parent / "bin"
    patterns = ("*MaaAgentServer*", "*MaaUtils*", "*opencv_world4_maa*")
    found: list[Path] = []
    for pattern in patterns:
        matches = [path for path in binary_dir.glob(pattern) if path.is_file()]
        if not matches:
            raise FileNotFoundError(f"missing MaaFW Agent runtime binary: {pattern} in {binary_dir}")
        found.extend(matches)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="remove the current platform output before building")
    args = parser.parse_args()

    tag = platform_tag()
    output_root = ROOT / "build" / "agent" / tag
    dist_path = output_root / "dist"
    work_path = output_root / "work"
    spec_path = output_root / "spec"
    if args.clean and output_root.exists():
        shutil.rmtree(output_root)
    for path in (dist_path, work_path, spec_path):
        path.mkdir(parents=True, exist_ok=True)

    pyinstaller_args = [
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "ma9-agent",
        "--paths",
        str(AGENT_DIR),
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        "--specpath",
        str(spec_path),
    ]
    for binary in required_maa_binaries():
        pyinstaller_args.extend(("--add-binary", f"{binary}{os.pathsep}maa/bin"))
    pyinstaller_args.append(str(AGENT_DIR / "main.py"))
    run_pyinstaller(pyinstaller_args)

    executable = dist_path / "ma9-agent" / ("ma9-agent.exe" if os.name == "nt" else "ma9-agent")
    if not executable.is_file():
        raise FileNotFoundError(f"Agent build did not produce {executable}")
    size = sum(path.stat().st_size for path in executable.parent.rglob("*") if path.is_file())
    print(f"Agent built: {executable}")
    print(f"Bundle size: {size / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
