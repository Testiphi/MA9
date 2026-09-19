"""Bounded Duel garage scan and optional safe assignment of one car."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from .duel_vehicle_screen import _current_rating, read_visible_cards
from .selection_runtime import _click, _frame, _ocr
from .vehicle_screen import match_vehicle


CLASS_X = {"R": 808, "S": 874, "A": 940, "B": 1006, "C": 1071, "D": 1137}


def _selection_title(context: Any, frame: np.ndarray) -> bool:
    return any("车辆选择" in row["text"] for row in _ocr(context, frame, (40, 60, 220, 60)))


def _visible(context: Any, frame: np.ndarray, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = _ocr(context, frame, (0, 120, 1280, 500))
    return read_visible_cards(frame, words, catalog,
                              retry_ocr=lambda roi: _ocr(context, frame, roi))


def _detail_stars(frame: np.ndarray) -> tuple[int | None, int | None]:
    lit = slots = 0
    for index in range(6):
        blue, green, red = map(int, frame[95, 180 + 24 * index])
        gold = red >= 190 and green >= 150 and blue < 160
        gray = 75 <= red <= 180 and max(abs(red - green), abs(green - blue)) < 20
        if not (gold or gray):
            break
        slots += 1
        lit += gold
    return (lit, slots) if slots >= 3 else (None, None)


def _detail(context: Any, expected_id: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    for _ in range(8):
        time.sleep(.5)
        frame = _frame(context)
        words = _ocr(context, frame, (160, 76, 300, 110))
        observed = match_vehicle(words, catalog)
        if observed and observed["id"] == expected_id:
            lower = _ocr(context, frame, (200, 560, 800, 150))
            occupied = any("已被放置" in row["text"] or "所在的赛道" in row["text"]
                           for row in lower)
            has_select = any("选择" in row["text"] for row in _ocr(context, frame, (1000, 600, 270, 105)))
            rating = next((score for row in _ocr(context, frame, (900, 90, 210, 90))
                           if (score := _current_rating(row["text"])) is not None), None)
            stars_lit, star_slots = _detail_stars(frame)
            return {"status": "detail_verified", "occupied_elsewhere": occupied,
                    "select_available": has_select, "detail_vehicle": observed,
                    "performance": rating, "stars_lit": stars_lit, "star_slots": star_slots}
        if observed and observed["confidence"] >= .95:
            return {"status": "wrong_detail", "detail_vehicle": observed}
    return {"status": "detail_not_verified"}


def scan(context: Any, vehicle_class: str, catalog: list[dict[str, Any]], *,
         target_id: str | None = None, choose: bool = False,
         max_pages: int = 25, expected_performance: int | None = None,
         expected_stars: int | None = None) -> dict[str, Any]:
    """Scan from a class tab, dedupe overlapping pages, and stop at an edge.

    ``choose`` only assigns a verified, unoccupied car; it never starts a race.
    """
    if type(choose) is not bool or type(max_pages) is not int:
        raise ValueError("choose must be boolean and max_pages must be an integer")
    if vehicle_class not in CLASS_X or not 1 <= max_pages <= 50:
        raise ValueError("unsupported Duel class or page limit")
    by_id = {row["id"]: row for row in catalog}
    if target_id is not None and (target_id not in by_id or by_id[target_id]["class"] != vehicle_class):
        raise ValueError("target vehicle is absent from this class")
    if choose and target_id is None:
        raise ValueError("choose requires a target vehicle")
    if ((expected_performance is not None and (type(expected_performance) is not int or expected_performance < 100))
            or (expected_stars is not None and (type(expected_stars) is not int or not 1 <= expected_stars <= 6))):
        raise ValueError("invalid expected performance or stars")
    frame = _frame(context)
    if not _selection_title(context, frame):
        return {"status": "not_duel_selection", "pages": 0, "vehicles": []}
    if not _click(context, CLASS_X[vehicle_class], 103):
        return {"status": "class_click_failed", "pages": 0, "vehicles": []}
    time.sleep(.8)
    found: dict[str, dict[str, Any]] = {}
    previous: tuple[str, ...] | None = None
    previous_image: np.ndarray | None = None
    for page in range(1, max_pages + 1):
        frame = _frame(context)
        if not _selection_title(context, frame):
            return {"status": "selection_lost", "pages": page - 1, "vehicles": list(found.values())}
        cards = _visible(context, frame, catalog)
        if cards and found and all(row["class"] != vehicle_class for row in cards):
            return {"status": "target_not_found" if target_id else "class_boundary", "pages": page - 1,
                    "vehicles": list(found.values()), "next_class": cards[0]["class"]}
        if not cards or any(row["class"] != vehicle_class for row in cards):
            return {"status": "class_or_ocr_unverified", "pages": page,
                    "vehicles": list(found.values()), "visible": cards}
        fingerprint = tuple(row["vehicle"]["id"] for row in cards)
        for row in cards:
            found.setdefault(row["vehicle"]["id"], {**row, "page": page})
        if target_id in fingerprint:
            card = next(row for row in cards if row["vehicle"]["id"] == target_id)
            if not _click(context, *card["target"]):
                return {"status": "card_click_failed", "pages": page, "vehicles": list(found.values())}
            detail = _detail(context, target_id, catalog)
            result = {**detail, "pages": page, "vehicles": list(found.values()),
                      "selected_card": card}
            if detail["status"] == "detail_verified":
                card_rating = card["performance"][0] if card["performance"] else None
                detail_rating = detail["performance"]
                clipped_thousands = (card_rating is not None and detail_rating is not None
                                     and card_rating < 1000 <= detail_rating
                                     and detail_rating % 1000 == card_rating)
                if (card_rating is not None and detail_rating is not None
                        and card_rating != detail_rating and not clipped_thousands):
                    result["status"] = "list_detail_rating_mismatch"
                    return result
                if clipped_thousands:
                    result["list_rating_clipped"] = True
                if (expected_performance is not None and detail["performance"] != expected_performance):
                    result["status"] = "performance_mismatch"
                    return result
                if expected_stars is not None and detail["stars_lit"] != expected_stars:
                    result["status"] = "stars_mismatch"
                    return result
            if not choose or detail["status"] != "detail_verified":
                return result
            if detail["occupied_elsewhere"]:
                result["status"] = "occupied_elsewhere"
                return result
            if not detail["select_available"] or not _click(context, 1139, 658):
                result["status"] = "select_failed"
                return result
            result["status"] = "assignment_unverified"
            for _ in range(10):
                time.sleep(.5)
                frame = _frame(context)
                changed = any("更换车辆" in row["text"]
                              for row in _ocr(context, frame, (470, 470, 720, 90)))
                displayed = match_vehicle(_ocr(context, frame, (0, 170, 1280, 190)), catalog)
                if changed and displayed and displayed["id"] == target_id:
                    result["status"] = "assigned"
                    break
            return result
        if previous is not None and fingerprint == previous:
            before = cv2.resize(cv2.cvtColor(previous_image[170:610], cv2.COLOR_BGR2GRAY), (160, 55))
            after = cv2.resize(cv2.cvtColor(frame[170:610], cv2.COLOR_BGR2GRAY), (160, 55))
            if float(np.mean(cv2.absdiff(before, after))) < 3:
                return {"status": "target_not_found" if target_id else "edge_reached",
                        "pages": page, "vehicles": list(found.values())}
        if page == max_pages:
            break
        previous, previous_image = fingerprint, frame
        if not context.tasker.controller.post_swipe(1090, 480, 400, 480, 460).wait().succeeded:
            return {"status": "swipe_failed", "pages": page, "vehicles": list(found.values())}
        time.sleep(.7)
    return {"status": "page_limit", "pages": max_pages, "vehicles": list(found.values())}
