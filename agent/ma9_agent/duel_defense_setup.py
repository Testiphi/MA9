"""Orchestrate five-car Duel defense setup from the qualification lineup."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .account_conflict import account_conflict_from_ocr
from .duel_map_screen import read_five_tracks
from .duel_selection import plan_live_weak_defense
from .duel_vehicle_runtime import (CLASS_ORDER, CLASS_X, assign_visible,
                                   scan as scan_duel_vehicles)
from .selection_runtime import _frame, _ocr


VALID_MODES = {"plan", "apply"}
VALID_STRATEGIES = {"weakest_current"}
RETRYABLE_DETAIL_STATUSES = {"detail_not_verified", "wrong_detail",
                             "list_detail_rating_mismatch"}
RETRYABLE_TARGET_SCAN_STATUSES = {
    *RETRYABLE_DETAIL_STATUSES,
    "target_not_found",
    "target_temporarily_unreadable",
    "page_ocr_unverified",
}


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


def _recognition_hit(context: Any, node: str) -> bool:
    result = context.run_recognition(node, _frame(context))
    return bool(result and result.hit)


def _current_unselected_slot(context: Any) -> int:
    """Return the expanded empty slot, falling back to a fresh slot-1 setup."""
    for slot in range(1, 6):
        if _recognition_hit(context, f"对决_防守_第{slot}赛道展开未选车"):
            return slot
    return 1


def _recover_account_conflict(context: Any) -> bool:
    """Immediately close a confirmed other-device login popup."""
    try:
        report = account_conflict_from_ocr(
            _ocr(context, _frame(context), (140, 200, 1000, 330)))
        if not report["detected"]:
            return False
        if not context.tasker.controller.post_click(1090, 244).wait().succeeded:
            return False
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            time.sleep(.5)
            observed = account_conflict_from_ocr(
                _ocr(context, _frame(context), (140, 200, 1000, 330)))
            if not observed["detected"]:
                return True
    except Exception:
        # Recovery is best effort while another failure is already being handled.
        return False
    return False


def _record_assignment(progress: dict[str, Any], slot: dict[str, Any],
                       selection: dict[str, Any]) -> None:
    progress["assigned"].append({
        "slot": slot["slot"],
        "vehicle_id": slot["vehicle_id"],
        "vehicle": slot["vehicle"],
        "class": slot["class"],
        "performance": selection.get("performance"),
    })
    progress["status"] = "assigning"


def _scan_class_ladder(context: Any, vehicle_class: str,
                       catalog: list[dict[str, Any]], max_pages: int,
                       *, required: int = 5) -> dict[str, Any]:
    """Scan lower classes only when the requested class has too few cars."""
    start = CLASS_ORDER.index(vehicle_class)
    reports: list[dict[str, Any]] = []
    vehicles: dict[str, dict[str, Any]] = {}
    for candidate_class in CLASS_ORDER[start:]:
        report = scan_duel_vehicles(
            context, candidate_class, catalog, max_pages=max_pages)
        if (not report.get("scan_complete")
                or report.get("status") not in {"edge_reached", "class_boundary"}):
            return {
                **report,
                "requested_class": vehicle_class,
                "scanned_classes": [row["class"] for row in reports],
            }
        reports.append({
            "class": candidate_class,
            "status": report["status"],
            "pages": report.get("pages"),
            "vehicles": len(report.get("vehicles", [])),
        })
        for card in report.get("vehicles", []):
            vehicle = card.get("vehicle") or {}
            if card.get("class") == candidate_class and vehicle.get("id"):
                vehicles.setdefault(vehicle["id"], card)
        if len(vehicles) >= required:
            return {
                "status": "class_ladder_complete",
                "scan_complete": True,
                "assignment_complete": False,
                "requested_class": vehicle_class,
                "scanned_classes": [row["class"] for row in reports],
                "class_reports": reports,
                "vehicles": list(vehicles.values()),
            }
    return {
        "status": "insufficient_owned_vehicles",
        "scan_complete": True,
        "assignment_complete": False,
        "requested_class": vehicle_class,
        "scanned_classes": [row["class"] for row in reports],
        "class_reports": reports,
        "vehicles": list(vehicles.values()),
    }


def _retry_target_after_wrong_detail(context: Any, selection: dict[str, Any],
                                     vehicle_class: str, target: dict[str, Any],
                                     catalog: list[dict[str, Any]],
                                     max_pages: int) -> dict[str, Any]:
    """Boundedly restart a target scan after transient OCR or list motion."""
    retries = 0
    while (selection.get("status") in RETRYABLE_TARGET_SCAN_STATUSES
           and retries < 2):
        # Detail failures leave the vehicle detail open. Scan/edge failures
        # already leave us on the garage list, so pressing Back there would
        # incorrectly return to the five-track lineup.
        if selection.get("status") in RETRYABLE_DETAIL_STATUSES:
            if not context.tasker.controller.post_click(32, 25).wait().succeeded:
                return selection
        selection = scan_duel_vehicles(
            context, vehicle_class, catalog,
            target_id=target["vehicle_id"], choose=True, max_pages=max_pages,
            expected_performance=target["performance"],
            expected_stars=target.get("stars_lit"),
            # The normal assignment already used the recorded page hint.  A
            # retry deliberately scans from the class start so an inaccurate
            # hint or unusual swipe inertia cannot make the target unreachable.
            page_hint=None,
        )
        retries += 1
        selection["defense_rescan_count"] = retries
    return selection


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


def run_defense_setup(context: Any, root: Path, raw_params: dict[str, Any], *,
                      _conflict_retry: int = 0) -> dict[str, Any]:
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
        if _recognition_hit(context, "对决_防守_已选车可开始"):
            progress["status"] = "already_configured"
            progress["existing_defense_preserved"] = True
            _write(progress_path, progress)
            return progress
        start_slot = _current_unselected_slot(context)
        progress["resumed_from_slot"] = start_slot
        tracks = _read_tracks(context, reference)
        _write(tracks_path, tracks)

        _run_task(context, f"对决_防守_进入第{start_slot}赛道选车")
        scan = _scan_class_ladder(context, vehicle_class, catalog["vehicles"],
                                  params["max_pages"])
        _write(scan_path, scan)
        if (not scan.get("scan_complete")
                or scan.get("status") != "class_ladder_complete"):
            raise RuntimeError(f"{vehicle_class}-class scan stopped at {scan.get('status')}")
        plan = plan_live_weak_defense(tracks, scan, vehicle_class=vehicle_class)
        _write(plan_path, plan)
        progress["plan"] = plan
        progress["status"] = "planned"
        _write(progress_path, progress)
        if not apply:
            if not context.tasker.controller.post_click(32, 25).wait().succeeded:
                raise RuntimeError("could not return from Duel vehicle selection")
            observed = _read_tracks(context, reference)
            _write(tracks_path, observed)
            if _map_order(observed) != _map_order(tracks):
                raise RuntimeError("defense map order changed after the garage scan")
            return progress

        # The full scan ends on the weakest cars. Select the first pending slot
        # directly from that page instead of leaving and entering it again.
        first = plan["slots"][start_slot - 1]
        selection = assign_visible(
            context, first["vehicle_id"], catalog["vehicles"],
            expected_performance=first["performance"],
            expected_stars=first.get("stars_lit"),
        )
        if selection.get("status") == "target_not_visible":
            # Normally the weakest car remains visible at the scan edge. Keep a
            # bounded fallback for unusual card layouts or OCR overlap.
            if not context.tasker.controller.post_click(32, 25).wait().succeeded:
                raise RuntimeError(f"could not return for slot {start_slot} fallback")
            observed = _read_tracks(context, reference)
            _write(tracks_path, observed)
            if _map_order(observed) != _map_order(tracks):
                raise RuntimeError(f"slot {start_slot} fallback map order changed")
            _run_task(context, f"对决_防守_进入第{start_slot}赛道选车")
            selection = scan_duel_vehicles(
                context, first["class"], catalog["vehicles"],
                target_id=first["vehicle_id"], choose=True,
                max_pages=params["max_pages"],
                expected_performance=first["performance"],
                expected_stars=first.get("stars_lit"),
                page_hint=first.get("scan_page"),
            )
        selection = _retry_target_after_wrong_detail(
            context, selection, first["class"], first, catalog["vehicles"],
            params["max_pages"])
        _write(scan_path, selection)
        if selection.get("status") != "assigned":
            raise RuntimeError(
                f"slot {start_slot} assignment unverified: {selection.get('status')}")
        observed = _read_tracks(context, reference)
        _write(tracks_path, observed)
        if _map_order(observed) != _map_order(tracks):
            raise RuntimeError(f"slot {start_slot} map order changed")
        _record_assignment(progress, first, selection)
        _write(progress_path, progress)

        for slot in plan["slots"][start_slot:]:
            index = slot["slot"]
            _run_task(context, f"对决_防守_进入第{index}赛道选车")
            selection = scan_duel_vehicles(
                context, slot["class"], catalog["vehicles"],
                target_id=slot["vehicle_id"], choose=True,
                max_pages=params["max_pages"],
                expected_performance=slot["performance"],
                expected_stars=slot.get("stars_lit"),
                page_hint=slot.get("scan_page"),
            )
            selection = _retry_target_after_wrong_detail(
                context, selection, slot["class"], slot, catalog["vehicles"],
                params["max_pages"])
            _write(scan_path, selection)
            if selection.get("status") != "assigned":
                raise RuntimeError(
                    f"slot {index} assignment unverified: {selection.get('status')}")
            observed = _read_tracks(context, reference)
            _write(tracks_path, observed)
            if _map_order(observed) != _map_order(tracks):
                raise RuntimeError(f"slot {index} map order changed")
            _record_assignment(progress, slot, selection)
            _write(progress_path, progress)
        progress["status"] = "five_assigned"
        _write(progress_path, progress)
        return progress
    except Exception as exc:
        if _conflict_retry < 1 and _recover_account_conflict(context):
            progress["status"] = "recovering_account_conflict"
            progress["account_conflict_retries"] = _conflict_retry + 1
            _write(progress_path, progress)
            return run_defense_setup(context, root, raw_params,
                                     _conflict_retry=_conflict_retry + 1)
        progress["status"] = "stopped"
        progress["error"] = str(exc)
        _write(progress_path, progress)
        raise
