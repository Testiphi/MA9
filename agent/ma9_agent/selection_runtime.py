"""Bounded OCR-based recommended selection for the existing multiplayer loop."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from maa.pipeline import JOCR, JRecognitionType

from .models import League
from .selection_strategy import planned_vehicles
from .vehicle_screen import (LEAGUE_CENTERS, normalize,
                             parse_fuel, read_page, selected_league)


__all__ = ["frame_of", "ocr_roi", "scan_rank", "select_recommended", "_frame", "_ocr"]


def ocr_roi(context: Any, image: np.ndarray, roi: tuple[int, int, int, int]) -> list[dict[str, Any]]:
    detail = context.run_recognition_direct(JRecognitionType.OCR, JOCR(roi=roi), image)
    return ([{"text": item.text, "confidence": float(item.score), "box": list(item.box)}
             for item in detail.all_results] if detail else [])


def frame_of(context: Any) -> np.ndarray:
    return normalize(context.tasker.controller.post_screencap().get(wait=True))


# Compatibility for existing callers and their patch points. New integrations
# use the public names; both names initially refer to the same callable.
_frame = frame_of
_ocr = ocr_roi


def _click(context: Any, x: int, y: int) -> bool:
    return bool(context.tasker.controller.post_click(x, y).wait().succeeded)


def _rank_start(context: Any, rank: League) -> bool:
    if not _click(context, LEAGUE_CENTERS[int(rank)], 106):
        return False
    for _ in range(15):
        time.sleep(.4)
        image = _frame(context)
        result = context.run_recognition("多人准备_仅拥有已开启", image)
        if selected_league(image) == rank and result and result.hit:
            return True
    return False


def _rank_end(context: Any, rank: League) -> bool:
    """Anchor at the previous rank's right edge via the next rank's start."""
    if rank == League.LEGEND or not _rank_start(context, League(int(rank) + 1)):
        return False
    for _ in range(5):
        if not context.tasker.controller.post_swipe(600, 420, 1000, 420, 320).wait().succeeded:
            return False
        time.sleep(.6)
        image = _frame(context)
        owned = context.run_recognition("多人准备_仅拥有已开启", image)
        if selected_league(image) == rank and owned and owned.hit:
            return True
    return False


def _fingerprint(records: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple((item["vehicle"] or {}).get("id", "?") for item in records)


def _read_records(context: Any, image: np.ndarray, rank: League,
                  catalog: list[dict[str, Any]]) -> tuple[np.ndarray, list[dict[str, Any]], bool]:
    """Retry an unsettled page; never silently skip an unidentified car."""
    records: list[dict[str, Any]] = []
    for attempt in range(5):
        if attempt:
            time.sleep(.6)
            image = _frame(context)
            if selected_league(image) != rank:
                return image, [], False
            owned = context.run_recognition("多人准备_仅拥有已开启", image)
            if not owned or not owned.hit:
                return image, [], False
        words = _ocr(context, image, (0, 190, 1280, 480))
        records = read_page(image, words, catalog, retry_ocr=lambda roi: _ocr(context, image, roi))
        if records and all(item["vehicle"] is not None for item in records):
            return image, records, True
    return image, records, False


def scan_rank(context: Any, rank: League, catalog: list[dict[str, Any]],
              max_pages: int = 50, stop_when: str | None = None) -> tuple[dict[str, dict[str, Any]], str, int]:
    if not _rank_start(context, rank):
        return {}, "rank_not_ready", 0
    found: dict[str, dict[str, Any]] = {}
    previous_fingerprint: tuple[str, ...] | None = None
    previous_image: np.ndarray | None = None
    repeats = 0
    for page in range(1, max_pages + 1):
        image = _frame(context)
        current = selected_league(image)
        if current != rank:
            return found, "league_boundary" if current is not None else "rank_unknown", page - 1
        result = context.run_recognition("多人准备_仅拥有已开启", image)
        if not result or not result.hit:
            return found, "owned_filter_lost", page - 1
        image, records, complete = _read_records(context, image, rank, catalog)
        if not complete:
            return found, "ocr_incomplete", page - 1
        fingerprint = _fingerprint(records)
        if previous_image is not None:
            first = cv2.resize(cv2.cvtColor(previous_image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            second = cv2.resize(cv2.cvtColor(image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            distance = float(np.mean(cv2.absdiff(first, second)))
            repeats = repeats + 1 if fingerprint == previous_fingerprint and distance < 3 else 0
            if repeats >= 2:
                return found, "edge_reached", page
        for item in records:
            vehicle = item["vehicle"]
            if vehicle and vehicle["id"] not in found:
                found[vehicle["id"]] = {**item, "page": page, "league": rank.label}
        # A dry priority car is still a resolved candidate. Stop here so the
        # next priority can be searched without sweeping to the rank boundary.
        if stop_when and stop_when in found:
            return found, "target_visible", page
        previous_image, previous_fingerprint = image, fingerprint
        if page == max_pages:
            break
        if not context.tasker.controller.post_swipe(1000, 420, 600, 420, 320).wait().succeeded:
            return found, "swipe_failed", page
        time.sleep(.55)
    return found, "page_limit", max_pages


def _detail_ready(context: Any) -> bool:
    for attempt in range(3):
        if attempt:
            time.sleep(.6)
        image = _frame(context)
        detail = context.run_recognition("多人运行时_车辆详情通用", image)
        if not detail or not detail.hit:
            continue
        # The list card establishes identity before the safe car-body click.
        # Long detail names scroll and can OCR as a different catalog variant.
        fuel = parse_fuel(_ocr(context, image, (460, 623, 260, 70)))
        if fuel is None:
            continue
        if fuel <= 0:
            return False
        if any((result := context.run_recognition(node, image)) and result.hit
               for node in ("TouchDrive_已开启", "TouchDrive_点击开")):
            return True
    return False


def _back_to_list(context: Any) -> bool:
    if not _click(context, 40, 30):
        return False
    for _ in range(15):
        time.sleep(.4)
        image = _frame(context)
        result = context.run_recognition("多人准备_仅拥有已开启", image)
        if result and result.hit:
            return True
    return False


def _open_visible_card(context: Any, card: dict[str, Any]) -> bool | None:
    """Open an OCR-identified card while it is still visible on the current page."""
    if not _click(context, *card["target"]):
        return None
    time.sleep(.8)
    if _detail_ready(context):
        return True
    return False if _back_to_list(context) else None


def _search_and_open(context: Any, rank: League, expected_id: str,
                     catalog: list[dict[str, Any]], reverse: bool,
                     max_pages: int) -> bool | None:
    anchored = _rank_end(context, rank) if reverse else _rank_start(context, rank)
    if not anchored:
        return None
    previous_image: np.ndarray | None = None
    previous_fingerprint: tuple[str, ...] | None = None
    repeats = 0
    for page in range(max_pages):
        image = _frame(context)
        if selected_league(image) != rank:
            return None
        owned = context.run_recognition("多人准备_仅拥有已开启", image)
        if not owned or not owned.hit:
            return None
        image, visible, complete = _read_records(context, image, rank, catalog)
        if not complete:
            return None
        choice = next((card for card in visible if card["vehicle"] and card["vehicle"]["id"] == expected_id), None)
        if choice is not None:
            return _open_visible_card(context, choice)
        if previous_image is not None:
            first = cv2.resize(cv2.cvtColor(previous_image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            second = cv2.resize(cv2.cvtColor(image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            distance = float(np.mean(cv2.absdiff(first, second)))
            fingerprint = _fingerprint(visible)
            repeats = repeats + 1 if fingerprint == previous_fingerprint and distance < 3 else 0
            if repeats >= 2:
                return None
        previous_image, previous_fingerprint = image, _fingerprint(visible)
        if page == max_pages - 1:
            break
        begin, end = ((600, 1000) if reverse else (1000, 600))
        if not context.tasker.controller.post_swipe(begin, 420, end, 420, 320).wait().succeeded:
            return None
        time.sleep(.55)
    return None


def _open_vehicle(context: Any, rank: League, expected_id: str,
                  catalog: list[dict[str, Any]], max_pages: int = 50) -> bool | None:
    """Re-find by OCR, preferring the right edge where priority cars cluster."""
    if rank != League.LEGEND:
        opened = _search_and_open(context, rank, expected_id, catalog, True, max_pages)
        if opened is not None:
            return opened
    return _search_and_open(context, rank, expected_id, catalog, False, max_pages)


def select_recommended(context: Any, root: Path, player_league: str,
                       catalog: dict[str, Any], rotation: dict[str, Any],
                       strategy: dict[str, Any]) -> dict[str, Any]:
    """Select the first usable priority; leave the list ready for reverse fallback otherwise."""
    planned = planned_vehicles(player_league, catalog, rotation, strategy)
    by_rank: dict[League, tuple[dict[str, dict[str, Any]], str, int]] = {}
    report: dict[str, Any] = {"player_league": player_league, "priority_count": len(planned),
                              "rank_scans": {}, "attempted": [], "status": "fallback"}
    rejected: set[str] = set()
    for car in planned:
        rank = League.from_label(car["league"])
        if rank not in by_rank:
            result = scan_rank(context, rank, catalog["vehicles"], stop_when=car["catalog_id"])
            if result[1] == "target_visible":
                report["rank_scans"][rank.label] = {"status": "target_visible", "pages": result[2],
                                                     "recognized": len(result[0])}
                card = result[0][car["catalog_id"]]
                if card["fuel"] != 0:
                    report["attempted"].append(car["catalog_id"])
                    opened = _open_visible_card(context, card)
                    if opened is None:
                        report["status"] = "scan_error"
                        return report
                    if opened:
                        report["status"] = "selected"
                        report["vehicle_id"] = car["catalog_id"]
                        report["vehicle_name"] = car["title"]
                        return report
                # The next car gets its own bounded first-pass search. The
                # old full-rank rescan caused 599 to be found only on return.
                rejected.add(car["catalog_id"])
                continue
            by_rank[rank] = result
            report["rank_scans"][rank.label] = {"status": result[1], "pages": result[2],
                                                 "recognized": len(result[0])}
            if result[1] not in {"league_boundary", "edge_reached"}:
                if result[1] == "ocr_incomplete":
                    snapshot = root / "debug" / "selection_ocr_failure.png"
                    snapshot.parent.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(snapshot), _frame(context))
                    report["diagnostic_image"] = str(snapshot)
                report["status"] = "scan_error"
                return report
        card = by_rank[rank][0].get(car["catalog_id"])
        if card is None or card["fuel"] == 0 or car["catalog_id"] in rejected:
            continue
        report["attempted"].append(car["catalog_id"])
        opened = _open_vehicle(context, rank, car["catalog_id"], catalog["vehicles"])
        if opened is None:
            report["status"] = "scan_error"
            return report
        if opened:
            report["status"] = "selected"
            report["vehicle_id"] = car["catalog_id"]
            report["vehicle_name"] = car["title"]
            return report
        image = _frame(context)
        if not (result := context.run_recognition("多人准备_仅拥有已开启", image)) or not result.hit:
            report["status"] = "unexpected_screen"
            return report
    return report
