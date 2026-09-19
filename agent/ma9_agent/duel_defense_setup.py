"""Orchestrate five-car Duel defense setup from the qualification lineup."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .duel_map_screen import read_five_tracks
from .duel_selection import plan_live_weak_defense
from .duel_vehicle_runtime import CLASS_X, scan as scan_duel_vehicles
from .selection_runtime import _frame, _ocr


VALID_MODES = {"plan", "apply"}
VALID_STRATEGIES = {"weakest_current"}


def _write(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _map_order(report: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["big"], row["small"]) for row in report["tracks"]]


def _read_tracks(context: Any, reference: dict[str, Any], *,
                 timeout: float = 15.0, interval: float = .6) -> dict[str, Any]:
    """Wait through page transitions until all five ordered maps are stable."""
    deadline = time.monotonic() + timeout
    last_report: dict[str, Any] = {"complete": False, "tracks": [], "observed_groups": 0}
    while True:
        last_report = read_five_tracks(
            _ocr(context, _frame(context), (55, 165, 1190, 160)), reference)
        if last_report.get("complete") and len(last_report.get("tracks", [])) == 5:
            return last_report
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
    raise RuntimeError(
        "five-map OCR did not verify all defense tracks "
        f"within {timeout:g}s (groups={last_report.get('observed_groups', 0)}, "
        f"tracks={len(last_report.get('tracks', []))})")


def _run_task(context: Any, entry: str) -> None:
    detail = context.run_task(entry)
    if detail is None or not getattr(getattr(detail, "status", None), "succeeded", False):
        raise RuntimeError(f"failed: {entry}")


def parse_setup_params(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate GUI parameters before any game input."""
    vehicle_class = str(raw.get("class", "D")).upper()
    mode = raw.get("mode", "plan")
    strategy = raw.get("strategy", "weakest_current")
    max_pages = raw.get("max_pages", 25)
    if vehicle_class not in CLASS_X:
        raise ValueError("class must be one of R/S/A/B/C/D")
    if mode not in VALID_MODES:
        raise ValueError("mode must be plan or apply")
    if strategy not in VALID_STRATEGIES:
        raise ValueError("unsupported defense strategy")
    if type(max_pages) is not int or not 1 <= max_pages <= 50:
        raise ValueError("max_pages must be an integer between 1 and 50")
    return {"class": vehicle_class, "mode": mode, "strategy": strategy,
            "max_pages": max_pages}


def run_defense_setup(context: Any, root: Path, raw_params: dict[str, Any]) -> dict[str, Any]:
    """Plan or assign five cars. This function never presses the Start button."""
    params = parse_setup_params(raw_params)
    vehicle_class = params["class"]
    apply = params["mode"] == "apply"
    debug = root / "debug"
    progress_path = debug / "duel_defense_gui_setup.json"
    tracks_path = debug / "duel_tracks_live.json"
    scan_path = debug / "duel_vehicle_scan_live.json"
    plan_path = debug / "duel_defense_plan_live.json"
    progress: dict[str, Any] = {
        "status": "started",
        "mode": params["mode"],
        "strategy": params["strategy"],
        "vehicle_class": vehicle_class,
        "assigned": [],
        "starts_race": False,
    }
    _write(progress_path, progress)
    try:
        reference = json.loads(
            (root / "data/generated/duel_auto_candidates.json").read_text(encoding="utf-8"))
        catalog = json.loads(
            (root / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))
        # The GUI task may start on the main multiplayer page, the interrupted
        # qualifier page, or the lineup itself. Reuse the guarded navigation
        # pipeline before taking any map-dependent action.
        progress["status"] = "navigating"
        _write(progress_path, progress)
        _run_task(context, "对决_资格赛入口")
        tracks = _read_tracks(context, reference)
        _write(tracks_path, tracks)

        _run_task(context, "对决_防守_进入第1赛道选车")
        scan = scan_duel_vehicles(context, vehicle_class, catalog["vehicles"],
                                  max_pages=params["max_pages"])
        _write(scan_path, scan)
        if scan.get("status") not in {"edge_reached", "class_boundary"}:
            raise RuntimeError(f"{vehicle_class}-class scan stopped at {scan.get('status')}")
        if not context.tasker.controller.post_click(32, 25).wait().succeeded:
            raise RuntimeError("could not return from Duel vehicle selection")
        observed = _read_tracks(context, reference)
        _write(tracks_path, observed)
        if _map_order(observed) != _map_order(tracks):
            raise RuntimeError("defense map order changed after the garage scan")

        plan = plan_live_weak_defense(tracks, scan, vehicle_class=vehicle_class)
        _write(plan_path, plan)
        progress["plan"] = plan
        progress["status"] = "planned"
        _write(progress_path, progress)
        if not apply:
            return progress

        for slot in plan["slots"]:
            index = slot["slot"]
            _run_task(context, f"对决_防守_进入第{index}赛道选车")
            selection = scan_duel_vehicles(
                context, vehicle_class, catalog["vehicles"],
                target_id=slot["vehicle_id"], choose=True,
                max_pages=params["max_pages"],
                expected_performance=slot["performance"],
                expected_stars=slot.get("stars_lit"),
            )
            _write(scan_path, selection)
            if selection.get("status") != "assigned":
                raise RuntimeError(
                    f"slot {index} assignment unverified: {selection.get('status')}")
            observed = _read_tracks(context, reference)
            _write(tracks_path, observed)
            if _map_order(observed) != _map_order(tracks):
                raise RuntimeError(f"slot {index} map order changed")
            progress["assigned"].append({
                "slot": index,
                "vehicle_id": slot["vehicle_id"],
                "vehicle": slot["vehicle"],
                "class": vehicle_class,
                "performance": selection.get("performance"),
            })
            progress["status"] = "assigning"
            _write(progress_path, progress)
        progress["status"] = "five_assigned"
        _write(progress_path, progress)
        return progress
    except Exception as exc:
        progress["status"] = "stopped"
        progress["error"] = str(exc)
        _write(progress_path, progress)
        raise
