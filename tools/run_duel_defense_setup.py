"""Read five defense maps, scan owned D cars and optionally assign five.

Run from the five-map defense lineup. This tool never presses Start or submits
times. Without --apply it only writes a live plan under debug/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from maa.agent_client import AgentClient
from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.duel_selection import plan_live_weak_defense  # noqa: E402


def _run(tasker: Tasker, entry: str, timeout: int) -> None:
    job = tasker.post_task(entry)
    deadline = time.monotonic() + timeout
    while not job.done and time.monotonic() < deadline:
        time.sleep(.3)
    if not job.done:
        tasker.post_stop().wait()
        raise RuntimeError(f"timeout in {entry}")
    if not job.succeeded:
        raise RuntimeError(f"failed: {entry}")
    print(f"OK {entry}", flush=True)


def _report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_tracks(tasker: Tasker, path: Path) -> dict:
    _run(tasker, "对决_读取五张地图", 60)
    report = _report(path)
    if not report.get("complete"):
        raise RuntimeError("five-map OCR did not verify all tracks")
    return report


def _map_order(report: dict) -> list[tuple[str, str]]:
    """Ignore screen positions, which move when a different slot expands."""
    return [(row["big"], row["small"]) for row in report["tracks"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="assign the five planned cars")
    parser.add_argument("--resume", action="store_true", help="continue a stopped --apply run")
    parser.add_argument("--adb", type=Path, default=Path(os.environ.get("MA9_ADB_PATH", "adb")))
    parser.add_argument("--address", default="127.0.0.1:16384")
    args = parser.parse_args()
    debug = ROOT / "debug"
    debug.mkdir(exist_ok=True)
    tracks_path = debug / "duel_tracks_live.json"
    scan_path = debug / "duel_vehicle_scan_live.json"
    plan_path = debug / "duel_defense_plan_live.json"
    report_path = debug / "duel_defense_setup_live.json"
    request_path = ROOT / "config/duel_vehicle_request.json"
    old_request = request_path.read_bytes() if request_path.exists() else None
    if args.resume and not args.apply:
        parser.error("--resume requires --apply")
    progress = (_report(report_path) if args.resume else
                {"status": "started", "apply": args.apply, "assigned": []})
    if args.resume and (not progress.get("plan") or progress.get("status") != "stopped"):
        parser.error("no stopped defense run with a saved plan to resume")
    progress.pop("error", None)

    Tasker.set_log_dir(str(debug / "live_maa"))
    resource = Resource()
    if not resource.post_bundle(ROOT / "assets/resource").wait().succeeded:
        raise RuntimeError("resource load failed")
    controller = AdbController(args.adb, args.address)
    controller.set_screenshot_target_short_side(720)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("ADB connection failed")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("tasker bind failed")
    client = AgentClient.create_tcp()
    with (debug / "live_agent.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, str(ROOT / "agent/main.py"), client.identifier],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            if not client.bind(resource) or not client.register_sink(resource, controller, tasker):
                raise RuntimeError("agent bind failed")
            if not client.connect():
                raise RuntimeError("agent connect failed")
            tracks = _read_tracks(tasker, tracks_path)
            if args.resume:
                plan = progress["plan"]
                if _map_order({"tracks": [slot["track"] for slot in plan["slots"]]}) != _map_order(tracks):
                    raise RuntimeError("defense maps differ from the saved plan")
            else:
                _run(tasker, "对决_防守_进入第1赛道选车", 90)
                _run(tasker, "对决_扫描D级车辆", 480)
                scan = _report(scan_path)
                if not controller.post_click(32, 25).wait().succeeded:
                    raise RuntimeError("could not return from vehicle selection")
                time.sleep(1.2)
                if _map_order(_read_tracks(tasker, tracks_path)) != _map_order(tracks):
                    raise RuntimeError("defense maps changed after garage scan")
                plan = plan_live_weak_defense(tracks, scan)
                plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                progress["plan"] = plan
                progress["status"] = "planned"
                report_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("PLAN " + ", ".join(slot["vehicle"] for slot in plan["slots"]), flush=True)
            if args.apply:
                for slot in plan["slots"]:
                    index = slot["slot"]
                    if index in {done["slot"] for done in progress["assigned"]}:
                        continue
                    _run(tasker, f"对决_防守_进入第{index}赛道选车", 90)
                    request_path.write_text(json.dumps({
                        "class": "D", "vehicle_id": slot["vehicle_id"],
                        "performance": slot["performance"], "choose": True,
                        "max_pages": 25,
                    }, ensure_ascii=False), encoding="utf-8")
                    _run(tasker, "对决_按配置查找车辆", 300)
                    selection = _report(scan_path)
                    if selection.get("status") != "assigned":
                        raise RuntimeError(f"slot {index} assignment unverified: {selection.get('status')}")
                    observed = _read_tracks(tasker, tracks_path)
                    if _map_order(observed) != _map_order(tracks):
                        raise RuntimeError(f"slot {index} map order changed")
                    progress["assigned"].append({"slot": index, "vehicle_id": slot["vehicle_id"],
                                                 "vehicle": slot["vehicle"],
                                                 "performance": selection.get("performance")})
                    progress["status"] = "assigning"
                    report_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
                    print(f"ASSIGNED {index}/5 {slot['vehicle']}", flush=True)
                progress["status"] = "five_assigned"
            report_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 0
        except Exception as exc:
            progress["status"] = "stopped"
            progress["error"] = str(exc)
            report_path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            raise
        finally:
            if tasker.running:
                tasker.post_stop().wait()
            client.disconnect()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            if old_request is None:
                request_path.unlink(missing_ok=True)
            else:
                request_path.write_bytes(old_request)


if __name__ == "__main__":
    raise SystemExit(main())
