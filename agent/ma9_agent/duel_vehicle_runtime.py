"""Bounded Duel garage scan and optional safe assignment of one car."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
from maa.pipeline import JRecognitionType, JTemplateMatch

from .duel_lineup_slot import observe_lineup_slot
from .duel_vehicle_screen import _current_rating, read_visible_cards
from .selection_runtime import _click, _frame, _ocr
from .vehicle_screen import match_vehicle


CLASS_ORDER = ("R", "S", "A", "B", "C", "D")
CLASS_X = {"R": 808, "S": 874, "A": 940, "B": 1006, "C": 1071, "D": 1137}
RETRYABLE_TARGET_STATUSES = {"detail_not_verified", "wrong_detail",
                             "list_detail_rating_mismatch"}
DETAIL_ATTEMPTS = 8
DETAIL_INTERVAL = .5
SELECT_BUTTON_ROI = (1020, 610, 240, 100)
SELECT_BUTTON_TEMPLATE = "navigation/duel/detail_select_text.png"

#: Vertical band ``(top, bottom)`` of the expanded lineup cell's vehicle name
#: block, in 1280x720 pixels.  Calibrated on the fixed frames listed in the 05L
#: evidence report: the two name lines sit at y 214-263 on every measured slot,
#: while the performance score + class letter row (``4,837S``) starts at y 259
#: and the track names live left of the block.  The band is slot-independent
#: because the five cells only move horizontally.
LINEUP_IDENTITY_BAND = (200, 258)
#: Width of the identity read, measured back from the expanded panel's right
#: edge.  The name block is right-anchored ~76 px inside the panel, so it moves
#: with the panel on slots 2..5; the nearest non-identity text (the expanded
#: track name) ends at least 461 px left of the panel edge on every measured
#: slot, and the neighbouring collapsed cells start 19-30 px right of it.
LINEUP_IDENTITY_SPAN = 340


def _selection_title(context: Any, frame: np.ndarray) -> bool:
    return any("车辆选择" in row["text"] for row in _ocr(context, frame, (40, 60, 220, 60)))


def _wait_selection_frame(context: Any, timeout: float = 5.0) -> np.ndarray | None:
    """Wait for the garage title after the slot-navigation transition."""
    deadline = time.monotonic() + timeout
    while True:
        frame = _frame(context)
        if _selection_title(context, frame):
            return frame
        if time.monotonic() >= deadline:
            return None
        time.sleep(.35)


def _visible(context: Any, frame: np.ndarray, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = _ocr(context, frame, (0, 120, 1280, 500))
    return read_visible_cards(frame, words, catalog,
                              retry_ocr=lambda roi: _ocr(context, frame, roi))


def _fingerprint(cards: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(row["vehicle"]["id"] for row in cards)


def _sample_visible(context: Any, catalog: list[dict[str, Any]], *,
                    attempts: int = 4, interval: float = .18,
                    target_id: str | None = None,
                    ) -> tuple[np.ndarray | None, list[dict[str, Any]], bool]:
    """Read a settled list page without trusting one animated OCR frame.

    Long vehicle names scroll inside their cards.  A name can therefore be
    absent or split in one OCR pass even though the garage itself did not
    move.  Prefer the most complete repeated fingerprint and only call the
    page stable when the same card set was observed at least twice.
    """
    samples: list[tuple[np.ndarray, list[dict[str, Any]], tuple[str, ...]]] = []
    previous: tuple[str, ...] | None = None
    for attempt in range(attempts):
        frame = _frame(context)
        if not _selection_title(context, frame):
            return None, [], False
        cards = _visible(context, frame, catalog)
        fingerprint = _fingerprint(cards)
        samples.append((frame, cards, fingerprint))
        # Most settled pages expose four complete cards. Two equal reads are
        # sufficient there; animated/partial pages retain the full retry
        # budget. For a target scan, two consecutive sightings of that exact
        # vehicle are also enough even on a short class tail.
        target_stable = (target_id is not None and target_id in fingerprint
                         and fingerprint == previous)
        if fingerprint == previous and (len(cards) >= 4 or target_stable):
            return frame, cards, True
        previous = fingerprint
        if attempt + 1 < attempts:
            time.sleep(interval)
    counts: dict[tuple[str, ...], int] = {}
    for _frame_value, _cards, fingerprint in samples:
        if fingerprint:
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
    repeated = {key for key, count in counts.items() if count >= 2}
    candidates = [sample for sample in samples if sample[2] in repeated] or samples
    # Prefer a complete OCR pass; for ties use the newest coordinates.
    frame, cards, fingerprint = max(
        enumerate(candidates), key=lambda item: (len(item[1][1]), item[0]))[1]
    return frame, cards, bool(fingerprint and fingerprint in repeated)


def _stable_sample_visible(context: Any, catalog: list[dict[str, Any]], *,
                           attempts: int = 4, interval: float = .18,
                           target_id: str | None = None,
                           ) -> tuple[np.ndarray | None, list[dict[str, Any]], bool]:
    """Give an animated page one extra complete sampling window before use."""
    frame, cards, stable = _sample_visible(
        context, catalog, attempts=attempts, interval=interval, target_id=target_id)
    if frame is None or stable:
        return frame, cards, stable
    time.sleep(interval)
    return _sample_visible(
        context, catalog, attempts=attempts, interval=interval, target_id=target_id)


def _gray_list(frame: np.ndarray) -> np.ndarray:
    return cv2.resize(cv2.cvtColor(frame[170:610], cv2.COLOR_BGR2GRAY), (160, 55))


def _result(status: str, pages: int, vehicles: list[dict[str, Any]],
            **extra: Any) -> dict[str, Any]:
    """Keep garage traversal and assignment completion as separate facts."""
    return {
        "status": status,
        "pages": pages,
        "vehicles": vehicles,
        "scan_complete": status in {"edge_reached", "class_boundary", "target_not_found"},
        "assignment_complete": status == "assigned",
        **extra,
    }


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


def _active_select_button(frame: np.ndarray) -> bool:
    """Reject a dimmed detail page even if its old button text still matches."""
    button = frame[625:690, 1045:1235]
    blue, green, red = (float(button[:, :, index].mean()) for index in range(3))
    bright_green = float((button[:, :, 1] > 180).mean())
    return bright_green >= .8 and green >= 180 and green - max(red, blue) >= 30


def _select_button_ready(context: Any, frame: np.ndarray) -> bool:
    """Require the detail button's template in its fixed ROI and active colour."""
    try:
        detail = context.run_recognition_direct(
            JRecognitionType.TemplateMatch,
            JTemplateMatch(template=[SELECT_BUTTON_TEMPLATE], roi=SELECT_BUTTON_ROI,
                           threshold=[.9]),
            frame)
    except Exception:
        return False
    return bool(detail and detail.hit and _active_select_button(frame))


def _detail(context: Any, expected_id: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    last_verified: dict[str, Any] | None = None
    for _ in range(DETAIL_ATTEMPTS):
        time.sleep(DETAIL_INTERVAL)
        frame = _frame(context)
        words = _ocr(context, frame, (160, 76, 300, 110))
        observed = match_vehicle(words, catalog)
        if observed and observed["id"] == expected_id:
            lower = _ocr(context, frame, (200, 560, 800, 150))
            occupied = any("已被放置" in row["text"] or "所在的赛道" in row["text"]
                           for row in lower)
            rating = next((score for row in _ocr(context, frame, (900, 90, 210, 90))
                           if (score := _current_rating(row["text"])) is not None), None)
            stars_lit, star_slots = _detail_stars(frame)
            verified = {"status": "detail_verified", "occupied_elsewhere": occupied,
                        "select_available": False, "detail_vehicle": observed,
                        "performance": rating, "stars_lit": stars_lit,
                        "star_slots": star_slots}
            if occupied:
                return verified
            if _select_button_ready(context, frame):
                verified["select_available"] = True
                return verified
            last_verified = verified
        elif observed and observed["confidence"] >= .95:
            return {"status": "wrong_detail", "detail_vehicle": observed}
    if last_verified is not None:
        return {**last_verified, "select_wait_timed_out": True}
    return {"status": "detail_not_verified"}


def _lineup_identity(context: Any, frame: np.ndarray,
                     catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Read only the expanded lineup cell's vehicle-name block of one frame.

    The page-wide ``(0, 170, 1280, 190)`` band used before this helper mixed
    the performance score and class letter (``4,837S``), the track names and
    the neighbouring collapsed cells into a single ``match_vehicle`` call, so
    the target's own name was never matched on its own.

    The block is right-anchored inside the expanded panel, so its position is
    taken from the read-only lineup observer's panel geometry instead of from a
    fixed page-wide band; that also moves it correctly on slots 2..5.  Nothing
    is filtered by text here, so a digit name (``004C``, ``370Z``) or a
    single-letter suffix (``Nevera R``) survives intact.  Returns the panel,
    the region that was read and the vehicle read there (``None`` when the
    block names no vehicle, or when no single expanded panel was found).
    """
    observed = observe_lineup_slot(frame)
    panel = observed["evidence"].get("panel") if observed else None
    if observed["expanded_slot"] is None or panel is None:
        return {"panel": None, "region": None, "vehicle": None}
    top, bottom = LINEUP_IDENTITY_BAND
    left = panel["right"] - LINEUP_IDENTITY_SPAN
    region = (left, top, panel["right"] - left, bottom - top)
    words = _ocr(context, frame, region)
    return {"panel": panel, "region": list(region),
            "vehicle": match_vehicle(words, catalog)}


def _finish_target(context: Any, card: dict[str, Any], page: int,
                   vehicles: list[dict[str, Any]], target_id: str,
                   catalog: list[dict[str, Any]], *, choose: bool,
                   expected_performance: int | None,
                   expected_stars: int | None,
                   verify_list_detail_rating: bool = True) -> dict[str, Any]:
    if not _click(context, *card["target"]):
        return _result("card_click_failed", page, vehicles)
    detail = _detail(context, target_id, catalog)
    result = _result(detail["status"], page, vehicles,
                     **{key: value for key, value in detail.items() if key != "status"},
                     selected_card=card)
    if detail["status"] == "detail_verified":
        if verify_list_detail_rating:
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
        else:
            # Name-first single-slot route: the detail already names the exact
            # target, so only the *implicit* "list score == detail score"
            # equality is suspended.  The raw OCR reading is reported unchanged
            # and the disabled comparison is stated explicitly.
            result["list_detail_rating_compare"] = "disabled"
        if expected_performance is not None and detail["performance"] != expected_performance:
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
    if not detail["select_available"]:
        result["status"] = "select_unavailable"
        return result
    if not _click(context, 1139, 658):
        result["status"] = "select_click_failed"
        return result
    result["status"] = "assignment_unverified"
    identity: dict[str, Any] = {"panel": None, "region": None, "vehicle": None}
    for _ in range(10):
        time.sleep(.5)
        frame = _frame(context)
        changed = any("更换车辆" in row["text"]
                      for row in _ocr(context, frame, (470, 470, 720, 90)))
        identity = _lineup_identity(context, frame, catalog)
        displayed = identity["vehicle"]
        if changed and displayed and displayed["id"] == target_id:
            result["status"] = "assigned"
            result["assignment_complete"] = True
            break
    # Post-selection evidence: the same frame carries both the "back on the
    # lineup" cue above and this identity read, so a later failure can be told
    # apart from an unreadable or wrong-lineup cell.  Existing keys keep their
    # meaning.
    result["lineup_identity"] = identity
    return result


def _try_target(context: Any, card: dict[str, Any], page: int,
                vehicles: list[dict[str, Any]], target_id: str,
                catalog: list[dict[str, Any]], *, choose: bool,
                expected_performance: int | None,
                expected_stars: int | None,
                verify_list_detail_rating: bool = True,
                attempts: int = 2) -> dict[str, Any]:
    """Reacquire a card after a moving list opens a neighbouring detail."""
    current = card
    last: dict[str, Any] | None = None
    for attempt in range(attempts):
        last = _finish_target(
            context, current, page, vehicles, target_id, catalog, choose=choose,
            expected_performance=expected_performance,
            expected_stars=expected_stars,
            verify_list_detail_rating=verify_list_detail_rating)
        last["target_attempts"] = attempt + 1
        if last["status"] not in RETRYABLE_TARGET_STATUSES:
            return last
        if not _click(context, 32, 25):
            return last
        time.sleep(.65)
        frame, cards, stable = _stable_sample_visible(
            context, catalog, attempts=3, target_id=target_id)
        if frame is None:
            return _result("selection_lost", page, vehicles,
                           target_attempts=attempt + 1)
        if not stable:
            return _result("target_temporarily_unreadable", page, vehicles,
                           target_attempts=attempt + 1)
        replacement = next(
            (row for row in cards if row["vehicle"]["id"] == target_id), None)
        if replacement is None:
            return _result("target_temporarily_unreadable", page, vehicles,
                           target_attempts=attempt + 1)
        current = replacement
    assert last is not None
    return last


def assign_visible(context: Any, target_id: str, catalog: list[dict[str, Any]], *,
                   expected_performance: int | None = None,
                   expected_stars: int | None = None) -> dict[str, Any]:
    """Assign a target already visible on the current Duel garage page.

    This formal defence path keeps the strict default: the implicit list/detail
    rating equality stays verified (``_try_target``'s default ``True``).
    """
    frame = _wait_selection_frame(context)
    if frame is None:
        return _result("not_duel_selection", 0, [])
    sampled_frame, cards, stable = _stable_sample_visible(
        context, catalog, attempts=3, target_id=target_id)
    if sampled_frame is None:
        return _result("not_duel_selection", 0, [])
    if not stable:
        return _result("page_ocr_unverified", 0, [])
    card = next((row for row in cards if row["vehicle"]["id"] == target_id), None)
    if card is None:
        return _result("target_not_visible", 0, cards)
    return _try_target(context, card, 0, cards, target_id, catalog, choose=True,
                       expected_performance=expected_performance,
                       expected_stars=expected_stars)


def scan(context: Any, vehicle_class: str, catalog: list[dict[str, Any]], *,
         target_id: str | None = None, choose: bool = False,
         max_pages: int = 25, expected_performance: int | None = None,
         expected_stars: int | None = None,
         page_hint: int | None = None,
         verify_list_detail_rating: bool = True) -> dict[str, Any]:
    """Scan from a class tab, dedupe overlapping pages, and stop at an edge.

    ``choose`` only assigns a verified, unoccupied car; it never starts a race.

    ``verify_list_detail_rating`` keeps the strict default.  Only when it is
    explicitly ``False`` does the scan skip the *implicit* "list current score
    must equal detail current score" comparison (and the resulting
    ``list_detail_rating_mismatch`` retry); an explicit ``expected_performance``
    or ``expected_stars`` is still enforced and the raw detail reading is
    reported unchanged with ``list_detail_rating_compare == "disabled"``.
    """
    if type(choose) is not bool or type(max_pages) is not int:
        raise ValueError("choose must be boolean and max_pages must be an integer")
    if type(verify_list_detail_rating) is not bool:
        raise ValueError("verify_list_detail_rating must be boolean")
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
    if page_hint is not None and (type(page_hint) is not int or not 1 <= page_hint <= max_pages):
        raise ValueError("page_hint must be within the scan page limit")
    frame = _wait_selection_frame(context)
    if frame is None:
        return _result("not_duel_selection", 0, [])
    if not _click(context, CLASS_X[vehicle_class], 103):
        return _result("class_click_failed", 0, [])
    time.sleep(.45)
    # The inventory pass records each car's approximate page. On later slot
    # assignments, jump close to that page without rerunning OCR over every
    # stronger car. Stop one page early to tolerate different swipe inertia.
    fast_forward = max(0, (page_hint or 1) - 2) if target_id else 0
    for _ in range(fast_forward):
        if not context.tasker.controller.post_swipe(1090, 480, 400, 480, 300).wait().succeeded:
            return _result("swipe_failed", 0, [], fast_forward_swipes=_)
        time.sleep(.35)
    found: dict[str, dict[str, Any]] = {}
    previous: tuple[str, ...] | None = None
    previous_image: np.ndarray | None = None
    unchanged_swipes = 0
    class_index = CLASS_ORDER.index(vehicle_class)
    lower_classes = set(CLASS_ORDER[class_index + 1:])
    for page in range(fast_forward + 1, max_pages + 1):
        frame, cards, stable = _stable_sample_visible(
            context, catalog, target_id=target_id)
        if frame is None:
            return _result("selection_lost", page - 1, list(found.values()))
        if not stable:
            return _result("page_ocr_unverified", page, list(found.values()),
                           unstable_samples=2)
        if not cards:
            return _result("page_ocr_unverified", page, list(found.values()))
        target_cards = [row for row in cards if row["class"] == vehicle_class]
        foreign_classes = {row["class"] for row in cards if row["class"] != vehicle_class}
        unexpected = foreign_classes - lower_classes
        if unexpected:
            return _result("class_or_ocr_unverified", page, list(found.values()),
                           visible=cards, unexpected_classes=sorted(unexpected))
        # A transition page can contain the tail of the requested class and
        # the head of the next one.  Keep its requested-class cards and stop
        # only on a stable page containing lower classes alone.
        if not target_cards and foreign_classes and stable:
            status = "target_not_found" if target_id else "class_boundary"
            return _result(status, page - 1, list(found.values()),
                           boundary_reason="next_class",
                           next_class=next((row["class"] for row in cards
                                           if row["class"] in lower_classes), None))
        fingerprint = _fingerprint(target_cards)
        for row in target_cards:
            found.setdefault(row["vehicle"]["id"], {**row, "page": page})
        if target_id in fingerprint:
            card = next(row for row in target_cards if row["vehicle"]["id"] == target_id)
            result = _try_target(
                context, card, page, list(found.values()), target_id, catalog,
                choose=choose, expected_performance=expected_performance,
                expected_stars=expected_stars,
                verify_list_detail_rating=verify_list_detail_rating)
            result["fast_forward_swipes"] = fast_forward
            if result["status"] != "target_temporarily_unreadable":
                return result
        if previous is not None and fingerprint == previous:
            if float(np.mean(cv2.absdiff(_gray_list(previous_image), _gray_list(frame)))) < 3:
                unchanged_swipes += 1
            else:
                unchanged_swipes = 0
        else:
            unchanged_swipes = 0
        if unchanged_swipes >= 2:
            status = "target_not_found" if target_id else "edge_reached"
            return _result(status, page, list(found.values()),
                           boundary_reason="list_edge")
        if page == max_pages:
            break
        previous, previous_image = fingerprint, frame
        if not context.tasker.controller.post_swipe(1090, 480, 400, 480, 300).wait().succeeded:
            return _result("swipe_failed", page, list(found.values()))
        time.sleep(.4)
    return _result("page_limit", max_pages, list(found.values()))
