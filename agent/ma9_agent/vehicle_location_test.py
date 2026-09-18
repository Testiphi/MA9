"""Bounded, no-race multiplayer search test for one account-owned vehicle."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from .garage_profile import owned_vehicle_ids
from .models import League
from .selection_runtime import _back_to_list, _click, _frame, _ocr, _rank_start
from .selection_strategy import vehicle_index
from .vehicle_screen import match_vehicle, read_page, selected_league


MAX_PAGES = 50
SWIPE_DURATION = 320


def _hit(context: Any, name: str, image: np.ndarray) -> bool:
    result = context.run_recognition(name, image)
    return bool(result and result.hit)


def _swipe(context: Any, direction: str) -> bool:
    x1, x2 = (1000, 600) if direction == "start" else (600, 1000)
    return bool(context.tasker.controller.post_swipe(x1, 420, x2, 420, SWIPE_DURATION).wait().succeeded)


def _ensure_owned_on(context: Any) -> bool:
    image = _frame(context)
    if _hit(context, "多人准备_仅拥有已开启", image):
        return True
    if not _hit(context, "多人准备_开启仅拥有", image):
        return False
    if not _click(context, 1128, 106):
        return False
    for _ in range(15):
        time.sleep(.4)
        if _hit(context, "多人准备_仅拥有已开启", _frame(context)):
            return True
    return False


def _rank_end(context: Any, rank: League) -> bool:
    # The selection list has a left edge at Bronze and no Legend -> Bronze wrap.
    if rank == League.LEGEND:
        return False
    next_rank = League(int(rank) + 1)
    if not _rank_start(context, next_rank):
        return False
    for _ in range(3):
        if not _swipe(context, "end"):
            return False
        time.sleep(.6)
        image = _frame(context)
        if selected_league(image) == rank and _hit(context, "多人准备_仅拥有已开启", image):
            return True
    return False


def _detail_check(context: Any, vehicle_id: str,
                  catalog: list[dict[str, Any]]) -> dict[str, Any]:
    for _ in range(8):
        time.sleep(.5)
        image = _frame(context)
        if not _hit(context, "多人运行时_车辆详情通用", image):
            continue
        # The name may scroll, so the list-card OCR is the primary identity.
        recognized = match_vehicle(_ocr(context, image, (107, 77, 347, 90)), catalog)
        if recognized and recognized["id"] != vehicle_id and recognized["confidence"] >= .95:
            return {"status": "wrong_detail", "detail_vehicle": recognized["title"]}
        return {"status": "found", "detail_name_verified": bool(recognized and recognized["id"] == vehicle_id)}
    return {"status": "detail_not_confirmed"}


def locate_once(context: Any, vehicle_id: str, rank: League, direction: str,
                catalog: list[dict[str, Any]], max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """Start from a rank boundary and stop after opening the requested detail."""
    if direction not in {"start", "end"}:
        raise ValueError(f"invalid search direction: {direction}")
    effective_direction = "start" if rank == League.LEGEND and direction == "end" else direction
    if not _ensure_owned_on(context):
        return {"status": "owned_filter_not_ready", "pages": 0}
    anchored = (_rank_start(context, rank) if effective_direction == "start"
                else _rank_end(context, rank))
    if not anchored:
        return {"status": "rank_anchor_failed", "pages": 0}

    previous_image: np.ndarray | None = None
    previous_names: tuple[str, ...] | None = None
    repeats = 0
    for page in range(1, max_pages + 1):
        image = _frame(context)
        current = selected_league(image)
        if current != rank:
            return {"status": "league_boundary", "pages": page - 1,
                    "observed_league": current.label if current else None}
        if not _hit(context, "多人准备_仅拥有已开启", image):
            return {"status": "unexpected_screen", "pages": page - 1}
        cards: list[dict[str, Any]] = []
        for attempt in range(5):
            if attempt:
                time.sleep(.6)
                image = _frame(context)
                if selected_league(image) != rank or not _hit(context, "多人准备_仅拥有已开启", image):
                    return {"status": "unexpected_screen", "pages": page}
            words = _ocr(context, image, (0, 190, 1280, 480))
            cards = read_page(image, words, catalog, retry_ocr=lambda roi: _ocr(context, image, roi))
            if cards and all(card["vehicle"] is not None for card in cards):
                break
        else:
            return {"status": "ocr_incomplete", "pages": page,
                    "unreadable_cards": [card["card"] for card in cards if card["vehicle"] is None]}
        names = tuple((card["vehicle"] or {}).get("id", "?") for card in cards)
        target = next((card for card in cards if card["vehicle"] and
                       card["vehicle"]["id"] == vehicle_id), None)
        if target:
            if not _click(context, *target["target"]):
                return {"status": "click_failed", "pages": page}
            detail = _detail_check(context, vehicle_id, catalog)
            return {**detail, "pages": page, "target": target["target"],
                    "card_name_confidence": target["vehicle"]["confidence"]}
        if previous_image is not None:
            before = cv2.resize(cv2.cvtColor(previous_image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            after = cv2.resize(cv2.cvtColor(image[190:665], cv2.COLOR_BGR2GRAY), (160, 60))
            distance = float(np.mean(cv2.absdiff(before, after)))
            repeats = repeats + 1 if names == previous_names and distance < 3 else 0
            if repeats >= 2:
                return {"status": "edge_reached", "pages": page}
        previous_image, previous_names = image, names
        if page < max_pages:
            if not _swipe(context, effective_direction):
                return {"status": "swipe_failed", "pages": page}
            time.sleep(.55)
    return {"status": "page_limit", "pages": max_pages}


def run_location_test(context: Any, catalog: dict[str, Any],
                      rotation: dict[str, Any], garage: dict[str, Any],
                      request: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema_version") != 1:
        raise ValueError("unsupported vehicle location test configuration")
    vehicle_id = request.get("vehicle_id")
    direction = request.get("from")
    repeats = request.get("repeats", 1)
    indexed = vehicle_index(catalog, rotation)
    if vehicle_id not in indexed or vehicle_id not in owned_vehicle_ids(garage):
        raise ValueError("test vehicle must be confirmed owned in the account garage")
    if direction not in {"start", "end"} or type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("test requires from=start/end and repeats=1..5")
    vehicle = indexed[vehicle_id]
    rank = League.from_label(vehicle["league"])
    report: dict[str, Any] = {"vehicle_id": vehicle_id, "vehicle_name": vehicle["title"],
                              "league": rank.label, "from": direction, "repeats": repeats,
                              "effective_from": ("start" if rank == League.LEGEND else direction),
                              "attempts": [], "status": "running", "never_starts_race": True}
    for index in range(repeats):
        if index and not _back_to_list(context):
            report["status"] = "return_to_list_failed"
            return report
        started = time.monotonic()
        result = locate_once(context, vehicle_id, rank, direction, catalog["vehicles"])
        report["attempts"].append({"trial": index + 1, **result,
                                   "seconds": round(time.monotonic() - started, 2)})
        if result["status"] != "found":
            report["status"] = result["status"]
            return report
    report["status"] = "found"
    return report
