"""Stage a clean Windows preview with the existing MFAAvalonia desktop UI.

Run after ``tools/build_agent.py`` and the local Windows package have supplied
MFAAvalonia and MaaFramework native files. Account configs, logs and captures
are deliberately omitted from the distributable.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import jsonc


ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "install"
BASE = ROOT / "build/portable"
DESTINATION = BASE / "MA9-preview"
AGENT = ROOT / "build/agent/win-x64/dist/ma9-agent"
TASKS = {"多人运行时_数据自检", "多人循环3局_入口", "多人循环20局_入口",
         "通用_账号被顶_识别", "对决_防守自动规划入口", "对决_防守自动配置入口"}


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_dir(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", action="store_true", help="also create MA9-preview.zip")
    args = parser.parse_args()
    target = DESTINATION.resolve()
    safe_root = BASE.resolve()
    if target.parent != safe_root or target == ROOT or target == SOURCE_UI.resolve():
        raise RuntimeError(f"unsafe preview destination: {target}")
    if not (AGENT / "ma9-agent.exe").is_file():
        raise FileNotFoundError("build the standalone Agent before staging the preview")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for name in ("MFAAvalonia.exe", "MFAAvalonia.dll", "MFAAvalonia.deps.json",
                 "MFAAvalonia.runtimeconfig.json", "libloader.dll", "appsettings.json",
                 "LICENSE", "NOTICE"):
        _copy_file(SOURCE_UI / name, target / name)
    for name in ("libs", "plugins", "runtimes", "LICENSES"):
        _copy_dir(SOURCE_UI / name, target / name)
    _copy_dir(AGENT, target / "agent/ma9-agent")
    _copy_dir(ROOT / "assets/resource", target / "resource")
    for name in ("data/multiplayer_profile.json", "data/generated/champion_rotation.json",
                 "data/generated/vehicle_catalog.json", "data/generated/duel_auto_candidates.json",
                 "data/sources/multiplayer_tracks.json"):
        _copy_file(ROOT / name, target / name)

    with (ROOT / "assets/interface.json").open(encoding="utf-8") as stream:
        interface = jsonc.load(stream)
    interface["agent"] = {"child_exec": "./agent/ma9-agent/ma9-agent.exe", "child_args": []}
    interface["controller"] = [row for row in interface["controller"] if row["type"] == "Adb"]
    interface["task"] = [row for row in interface["task"] if row["entry"] in TASKS]
    if {row["entry"] for row in interface["task"]} != TASKS:
        raise RuntimeError("one or more preview tasks are missing from assets/interface.json")
    (target / "interface.json").write_text(json.dumps(interface, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    (target / "试用说明.txt").write_text(
        "MA9 多人模式试用版（Windows x64）\n\n"
        "使用前：\n"
        "1. 完整解压本压缩包，不要直接在压缩包内运行。\n"
        "2. 在 MuMu 模拟器中开启 ADB，运行《狂野飙车 9》国服并设为中文。\n"
        "3. 游戏保持横屏，建议 1280×720，并先进入游戏主页。\n\n"
        "第一次运行：\n"
        "1. 双击 MFAAvalonia.exe。\n"
        "2. 控制器选择“安卓端”，资源选择“官服”，连接正在运行的模拟器。\n"
        "3. 先运行“多人运行时数据自检（Agent）”。自检成功后再继续。\n"
        "4. 从游戏主页运行连续3局的多人循环，并观察选车、开赛和结算。\n"
        "5. 3局完整结束后，再考虑运行连续20局版本。\n\n"
        "任务会实际选车、消耗油量并开始比赛，无需安装 VS Code 或 Python。\n"
        "此预览包不包含开发者的车库、个人选车排序、截图或日志。\n"
        "个人车库扫描及排序尚未纳入试用包；当前使用内置推荐与游戏内的“仅拥有”筛选，\n"
        "无法确认可用车辆时会停止。其他模拟器和账号仍需实机验证。\n\n"
        "出现异常时请停止任务，保留 debug 目录，并记录模拟器版本、分辨率、\n"
        "开始任务时所在页面和最后停留页面。公开发送日志前请检查本机路径和游戏昵称。\n",
        encoding="utf-8")
    unexpected = [name for name in ("debug", "logs", "config", "captures", "downloads")
                  if (target / name).exists()]
    if unexpected:
        raise RuntimeError(f"private or temporary directories leaked into preview: {unexpected}")
    count = sum(1 for path in target.rglob("*") if path.is_file())
    size = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    print(f"Staged {count} files ({size / 1024**2:.1f} MiB) at {target}")
    if args.zip:
        archive = shutil.make_archive(str(BASE / "MA9-preview"), "zip", root_dir=BASE,
                                      base_dir=target.name)
        print(f"Archive: {archive}")


if __name__ == "__main__":
    main()
