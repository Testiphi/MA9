"""Independently verify five assigned defense cars on the lineup screen."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from ma9_agent.duel_map_screen import read_five_tracks  # noqa: E402
from ma9_agent.vehicle_screen import match_vehicle  # noqa: E402
from probe_vehicle_fields import recognize_roi  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, default=Path(os.environ.get("MA9_ADB_PATH", "adb")))
    parser.add_argument("--address", default="127.0.0.1:16384")
    parser.add_argument("--expanded-slot", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    plan = json.loads((ROOT / "debug/duel_defense_plan_live.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    reference = json.loads((ROOT / "data/generated/duel_auto_candidates.json").read_text(encoding="utf-8"))
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
    current = args.expanded_slot
    rows = []
    for slot in plan["slots"]:
        index = slot["slot"]
        if index != current:
            job = tasker.post_task(f"对决_防守_从第{current}切到第{index}赛道")
            if not job.wait().succeeded:
                raise RuntimeError(f"could not expand defense slot {index}")
            current = index
            time.sleep(.5)
        frame = controller.post_screencap().get(wait=True)
        cv2.imwrite(str(ROOT / f"debug/duel_defense_slot_{index}.png"), frame)
        maps = read_five_tracks(recognize_roi(tasker, frame, (55, 165, 1190, 160)), reference)
        visible = match_vehicle(recognize_roi(tasker, frame, (0, 170, 1280, 200)), catalog)
        actual = next((track for track in maps["tracks"] if track["slot"] == index), None)
        passed = (maps["complete"] and actual is not None
                  and (actual["big"], actual["small"]) == (slot["track"]["big"], slot["track"]["small"])
                  and visible is not None and visible["id"] == slot["vehicle_id"])
        row = {"slot": index, "expected_map": slot["track"], "observed_map": actual,
               "expected_vehicle": slot["vehicle"], "observed_vehicle": visible,
               "passed": passed}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {"complete": len(rows) == 5 and all(row["passed"] for row in rows), "slots": rows,
              "race_started": False}
    (ROOT / "debug/duel_defense_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
