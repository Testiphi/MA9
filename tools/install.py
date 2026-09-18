from pathlib import Path

import shutil
import sys

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("Usage: python install.py <version> <os> <arch>")
    print("Example: python install.py v1.0.0 win x86_64")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]


def get_dotnet_platform_tag():
    """自动检测当前平台并返回对应的dotnet平台标签"""
    if os_name == "win" and arch == "x86_64":
        platform_tag = "win-x64"
    elif os_name == "win" and arch == "aarch64":
        platform_tag = "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        platform_tag = "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        platform_tag = "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        platform_tag = "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        platform_tag = "linux-arm64"
    else:
        print("Unsupported OS or architecture.")
        print("available parameters:")
        print("version: e.g., v1.0.0")
        print("os: [win, macos, linux, android]")
        print("arch: [aarch64, x86_64]")
        sys.exit(1)

    return platform_tag


def get_agent_platform_tag():
    """Return the folder tag produced by tools/build_agent.py."""
    if os_name == "android":
        return None
    os_tag = {"win": "win", "macos": "macos", "linux": "linux"}.get(os_name)
    arch_tag = {"x86_64": "x64", "aarch64": "arm64"}.get(arch)
    if os_tag is None or arch_tag is None:
        return None
    return f"{os_tag}-{arch_tag}"


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        print('请先下载 MaaFramework 到 "deps"。')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )



def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )
    for relative in (
        Path("data/multiplayer_profile.json"),
        Path("data/generated/champion_rotation.json"),
        Path("data/generated/vehicle_catalog.json"),
        Path("data/generated/duel_auto_candidates.json"),
        Path("data/sources/multiplayer_tracks.json"),
    ):
        destination = install_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(working_dir / relative, destination)

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    interface["version"] = version

    # 开发时从 .venv 启动；发布包优先使用 PyInstaller 生成的独立 Agent。
    agent_tag = get_agent_platform_tag()
    agent_bundle = working_dir / "build" / "agent" / str(agent_tag) / "dist" / "ma9-agent"
    agent_executable = agent_bundle / ("ma9-agent.exe" if os_name == "win" else "ma9-agent")
    if agent_tag is None:
        interface.pop("agent", None)
    elif agent_executable.exists():
        executable_name = agent_executable.name
        interface["agent"] = {
            "child_exec": f"./agent/ma9-agent/{executable_name}",
            "child_args": [],
        }
    else:
        interface["agent"] = {
            "child_exec": "python",
            "child_args": ["./agent/main.py"],
        }

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )
    shutil.copy2(
        working_dir / "NOTICE",
        install_path,
    )
    shutil.copytree(
        working_dir / "LICENSES",
        install_path / "LICENSES",
        dirs_exist_ok=True,
    )
    editor_executable = working_dir / "build" / "selection_gui" / "current" / "dist" / "ma9-selection.exe"
    if os_name == "win" and editor_executable.is_file():
        shutil.copy2(editor_executable, install_path / editor_executable.name)


def install_agent():
    agent_tag = get_agent_platform_tag()
    if agent_tag is None:
        return
    bundle = working_dir / "build" / "agent" / agent_tag / "dist" / "ma9-agent"
    if bundle.exists():
        shutil.copytree(bundle, install_path / "agent" / "ma9-agent", dirs_exist_ok=True)
    else:
        print("Warning: bundled Agent not found; packaging Python sources and requiring a system Python runtime.")
        shutil.copytree(
            working_dir / "agent",
            install_path / "agent",
            ignore=shutil.ignore_patterns("__pycache__", "tests", "requirements-dev.txt"),
            dirs_exist_ok=True,
        )


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()

    print(f"Install to {install_path} successfully.")
