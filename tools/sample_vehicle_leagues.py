"""Bounded higher-league list OCR survey; restores the selected league afterward."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from collect_vehicle_scan import (ROOT, capture, capture_expected, is_list, scan_list,
                                  template_seen)
from probe_vehicle_fields import LEAGUES, LEAGUE_CENTERS, make_tasker, selected_league
from vehicle_scan_merge import merge_vehicle_records


OWNED_ON = ROOT / "assets/resource/image/navigation/multiplayer/owned_on.png"
OWNED_OFF = ROOT / "assets/resource/image/navigation/multiplayer/owned_off.png"


def owned_filter(frame: np.ndarray) -> str:
    on = template_seen(frame, OWNED_ON, (1090, 75, 80, 65), .9)
    off = template_seen(frame, OWNED_OFF, (1090, 75, 80, 65), .9)
    return "on" if on and not off else "off" if off and not on else "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leagues", nargs="+", choices=LEAGUES,
                        default=list(LEAGUES[3:]))
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--temporary-owned-on", action="store_true",
                        help="enable only-owned for this survey, then restore its original state")
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 60:
        parser.error("survey max-pages must be 1..60")
    config = json.loads((ROOT / "debug/vehicle_scan_env.json").read_text(encoding="utf-8"))
    tasker = make_tasker(ROOT / "assets/resource", Path(config["adb_path"]), config["address"])
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    controller = tasker.controller
    start_frame = controller.post_screencap().get(wait=True)
    if not is_list(start_frame):
        parser.error("start on the multiplayer vehicle selection list")
    original_league = selected_league(start_frame)
    if original_league is None:
        parser.error("cannot determine the currently selected league")
    run_dir = args.output_dir or ROOT / "debug/vehicle_scans" / datetime.now().strftime("league_survey_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    original_owned_filter = owned_filter(start_frame)
    if args.temporary_owned_on and original_owned_filter == "unknown":
        parser.error("cannot determine the current only-owned filter state")
    report = {"original_league": original_league,
              "original_owned_filter": original_owned_filter,
              "owned_filter": original_owned_filter,
              "leagues": {}, "status": "partial"}
    all_records = []
    try:
        if args.temporary_owned_on and original_owned_filter == "off":
            if not controller.post_click(1128, 106).wait().succeeded:
                report["status"] = "owned_filter_click_failed"
                raise RuntimeError("failed to enable only-owned filter")
            frame, ready = capture_expected(
                controller, run_dir / "owned_filter_on.png",
                lambda image: is_list(image) and owned_filter(image) == "on",
                timeout=15,
            )
            if not ready:
                report["status"] = "owned_filter_not_ready"
                raise RuntimeError("could not verify only-owned filter is enabled")
        report["owned_filter"] = "on" if args.temporary_owned_on else original_owned_filter
        for league in args.leagues:
            frame = controller.post_screencap().get(wait=True)
            if not is_list(frame):
                report["status"] = "unexpected_screen"
                break
            if not controller.post_click(LEAGUE_CENTERS[LEAGUES.index(league)], 106).wait().succeeded:
                report["status"] = "rank_click_failed"
                break
            time.sleep(.6)
            confirmation, ready = capture_expected(
                controller, run_dir / league / "rank_start.png",
                lambda image: is_list(image) and selected_league(image) == league,
                timeout=15,
            )
            if not ready:
                report["status"] = "rank_not_ready"
                break
            result = scan_list(tasker, run_dir / league, catalog, args.max_pages,
                               expected_league=league)
            records = [item for page in result["pages"] for item in page["records"]]
            all_records.extend(records)
            report["leagues"][league] = {"status": result["status"],
                                          "pages": len(result["pages"]),
                                          "cards": len(records),
                                          "recognized": sum(item["values"]["vehicle"] is not None for item in records),
                                          "unique_vehicle_ids": result["unique_vehicle_ids"]}
            print(json.dumps({"league": league, **report["leagues"][league]}, ensure_ascii=False), flush=True)
            if result["status"] in {"unexpected_screen", "swipe_failed"}:
                report["status"] = result["status"]
                break
        else:
            report["status"] = "sampled"
    finally:
        frame = controller.post_screencap().get(wait=True)
        if is_list(frame):
            if args.temporary_owned_on and owned_filter(frame) != original_owned_filter:
                if controller.post_click(1128, 106).wait().succeeded:
                    capture_expected(
                        controller, run_dir / "restored.png",
                        lambda image: is_list(image) and owned_filter(image) == original_owned_filter,
                        timeout=15,
                    )
            # Toggling only-owned can reset the list to bronze, so restore the
            # selected league after the filter has settled.
            time.sleep(.8)
            frame = capture(controller, run_dir / "restored.png")
            if is_list(frame) and selected_league(frame) != original_league:
                controller.post_click(LEAGUE_CENTERS[LEAGUES.index(original_league)], 106).wait()
            restored, _ = capture_expected(
                controller, run_dir / "restored.png",
                lambda image: is_list(image) and selected_league(image) == original_league
                and owned_filter(image) == original_owned_filter,
                timeout=15,
            )
            report["restored_league"] = selected_league(restored)
            report["restored_owned_filter"] = owned_filter(restored)
        else:
            report["restored_league"] = None
            report["restored_owned_filter"] = "unknown"
        merged = merge_vehicle_records(all_records)
        (run_dir / "vehicles.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (run_dir / "survey.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "restored_league": report["restored_league"],
                      "recognized_unique": len(merged["vehicles"]), "output_dir": str(run_dir)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
