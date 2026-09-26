"""Bounded Duel garage scan and optional safe assignment of one car."""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
from maa.pipeline import JRecognitionType, JTemplateMatch

from .duel_lineup_slot import observe_lineup_slot
from .duel_vehicle_screen import (_current_rating, read_clipped_candidate,
                                  read_visible_cards, rolling_identity)
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

#: Bounded right-edge completion (MA9-05N).  The card the 16:9 right edge clips
#: is not readable on the page where it appears, and the next fling can carry
#: the list past it: the recorded slot-3 A scan had the target's card clipped at
#: x 1069 and one swipe later only its left tail was left on screen.  When such
#: a card's visible name resolves uniquely it is worth a small, controlled
#: re-position -- at most :data:`EDGE_REPOSITION_LIMIT` swipes of
#: :data:`EDGE_REPOSITION_SWIPE` per page, each about 45% of the page swipe --
#: because only a *full* observation is ever clicked, and because the swipe
#: distance is never assumed: every attempt is followed by a fresh settled read.
EDGE_REPOSITION_LIMIT = 3
EDGE_REPOSITION_SWIPE = (1010, 470, 710, 470, 650)
EDGE_REPOSITION_INTERVAL = .4

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


def _visible(context: Any, frame: np.ndarray, catalog: list[dict[str, Any]]
             ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read one frame: the fully visible cards and the clipped right-edge card.

    Both come from the same OCR pass.  The clipped card is returned separately
    because its geometry is not safe to click: it only tells the scan that a
    full observation of that card is still owed.
    """
    words = _ocr(context, frame, (0, 120, 1280, 500))
    cards = read_visible_cards(frame, words, catalog,
                               retry_ocr=lambda roi: _ocr(context, frame, roi))
    clipped = read_clipped_candidate(words, catalog)
    return cards, ([clipped] if clipped is not None else [])


def _fingerprint(cards: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(row["vehicle"]["id"] for row in cards)


#: Largest movement, per coordinate and in 1280x720 pixels, tolerated between
#: two consecutive independent readings of the *same* target card (MA9-05N2).
#: The FE3 pair the scan must confirm moved its card by 2 px only while its name
#: was readable in both frames (card left 708 -> 706, click target 893 -> 891),
#: so 12 px is six times the observed OCR jitter.  This is a chosen tolerance,
#: not a claim about real movement: the 690 px of a page swipe is the *command*
#: coordinate difference of that large gesture, not a floor every real
#: displacement clears -- the live list can also shift by a few pixels.  It is
#: enough that the bound still cannot accept the clear cases: the neighbouring
#: column sits at least 320 px away and the second card row is 227 px below the
#: first, while the class and the row are checked independently of the margin.
TARGET_GEOMETRY_TOLERANCE = 12


def _target_read(cards: list[dict[str, Any]], target_id: str | None
                 ) -> tuple[dict[str, Any] | None, bool]:
    """One complete target card of ``cards``, and whether the id was claimed.

    ``cards`` only ever holds fully visible cards, so a target the right edge
    clips never reaches this helper.  A page that shows the id on two cards
    cannot say which one is the target: the card is then ``None`` while the id
    still counts as claimed, which keeps that ambiguous page from confirming
    anything.
    """
    if target_id is None:
        return None, False
    matches = [row for row in cards if row["vehicle"]["id"] == target_id]
    return (matches[0] if len(matches) == 1 else None), bool(matches)


def _same_target_card(first: dict[str, Any], second: dict[str, Any],
                      tolerance: int = TARGET_GEOMETRY_TOLERANCE) -> bool:
    """Whether two readings describe the same, unmoved target card.

    The class and both the card box and the click target have to agree within
    :data:`TARGET_GEOMETRY_TOLERANCE`; a name that merely repeats may not stand
    in for the target's geometry.
    """
    if first["class"] != second["class"]:
        return False
    return all(abs(before - after) <= tolerance
               for before, after in zip([*first["card"], *first["target"]],
                                        [*second["card"], *second["target"]]))


def _sample_visible(context: Any, catalog: list[dict[str, Any]], *,
                    attempts: int = 4, interval: float = .18,
                    target_id: str | None = None,
                    target_state: list[dict[str, Any] | None] | None = None,
                    ) -> tuple[np.ndarray | None, list[dict[str, Any]], bool,
                               list[dict[str, Any]]]:
    """Read a settled list page without trusting one animated OCR frame.

    Long vehicle names scroll inside their cards.  A name can therefore be
    absent or split in one OCR pass even though the garage itself did not
    move.  Prefer the most complete repeated fingerprint and only call the
    page stable when the same card set was observed at least twice.

    A target scan additionally accepts the target itself: two consecutive
    independent reads that name that one complete card and put its card box and
    click target within :data:`TARGET_GEOMETRY_TOLERANCE` are enough even when
    an unrelated neighbour's own rolling name changed between them, because the
    target is what this scan is about.  The returned frame is always the newest
    one, so the coordinates can never be stale.  A missing or ambiguous read and
    any larger movement break the run, and a window that read the target without
    confirming it is never reported as stable: a rolling name the OCR lost must
    not be mistaken for a car that is not on the page.  That is enforced on the
    early exit too -- once *this window* has claimed the id, a later whole-page
    repeat is no longer accepted as the settled page, because the seen target is
    exactly what such a page would otherwise silently erase.

    ``target_state`` is the small local continuity cell shared by the two
    windows of one :func:`_stable_sample_visible` call.  On entry it holds the
    target reading of the capture immediately before this window (``None`` at
    the first window), and on every return this window writes back the reading
    of its own *last actual capture*.  That is what keeps a real target run
    continuous across the artificial window boundary without ever promoting an
    older sighting to immediate predecessor.

    The last element is the clipped right-edge card of the chosen sample, kept
    apart from the fully visible cards so it can neither steady nor unsteady
    the page fingerprint.
    """
    samples: list[tuple[np.ndarray, list[dict[str, Any]], tuple[str, ...],
                        list[dict[str, Any]]]] = []
    previous: tuple[str, ...] | None = None
    # The reading just before this window: a fresh call starts from nothing,
    # while the second window of one bounded call starts from the first
    # window's own last actual capture.
    previous_target = target_state[0] if target_state is not None else None
    claimed = False
    seen: tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]] | None = None
    for attempt in range(attempts):
        frame = _frame(context)
        if not _selection_title(context, frame):
            if target_state is not None:
                target_state[0] = None
            return None, [], False, []
        cards, clipped = _visible(context, frame, catalog)
        fingerprint = _fingerprint(cards)
        target_card, target_claimed = _target_read(cards, target_id)
        if target_claimed:
            claimed = True
            seen = (frame, cards, clipped)
        samples.append((frame, cards, fingerprint, clipped))
        # Most settled pages expose four complete cards. Two equal reads are
        # sufficient there; animated/partial pages retain the full retry budget.
        # A page whose id is ambiguous is not settled evidence, so it may not
        # steady the page either.  Neither may a whole-page repeat once this
        # window has already claimed the target: the id was seen and not yet
        # confirmed, so a page without it is not the settled page -- reading it
        # that way is how a seen target gets forgotten and the caller gets
        # authorised to swipe past it.
        target_stable = (target_card is not None and previous_target is not None
                         and _same_target_card(previous_target, target_card))
        if target_stable or (fingerprint == previous and len(cards) >= 4
                             and not target_claimed and not claimed):
            if target_state is not None:
                target_state[0] = target_card
            return frame, cards, True, clipped
        previous = fingerprint
        previous_target = target_card
        if attempt + 1 < attempts:
            time.sleep(interval)
    counts: dict[tuple[str, ...], int] = {}
    for _frame_value, _cards, fingerprint, _clipped in samples:
        if fingerprint:
            counts[fingerprint] = counts.get(fingerprint, 0) + 1
    repeated = {key for key, count in counts.items() if count >= 2}
    candidates = [sample for sample in samples if sample[2] in repeated] or samples
    # Prefer a complete OCR pass; for ties use the newest coordinates.
    frame, cards, fingerprint, clipped = max(
        enumerate(candidates), key=lambda item: (len(item[1][1]), item[0]))[1]
    # Every route out of the loop hands the next window the target reading of
    # this window's last actual capture -- never the earlier capture that the
    # ``seen`` branch below returns, which would let the next window bridge a
    # gap the target was absent from.
    if target_state is not None:
        target_state[0] = previous_target
    if claimed:
        # The target was read in this window but never confirmed by two
        # consecutive consistent target reads, so the window may not report a
        # settled page that simply lacks it.  Return the pair of the newest
        # capture that named the target -- one capture, so frame and cards stay
        # consistent -- with ``stable`` false: nothing is ever opened or swiped
        # from an unverified window, and the caller keeps the sighting when it
        # weighs its second window.
        assert seen is not None
        return seen[0], seen[1], False, seen[2]
    return frame, cards, bool(fingerprint and fingerprint in repeated), clipped


def _stable_sample_visible(context: Any, catalog: list[dict[str, Any]], *,
                           attempts: int = 4, interval: float = .18,
                           target_id: str | None = None,
                           ) -> tuple[np.ndarray | None, list[dict[str, Any]], bool,
                                      list[dict[str, Any]]]:
    """Give an animated page one extra complete sampling window before use.

    The two windows are one bounded budget of ``2 * attempts`` captures, not two
    independent votes.  A window that read the target without confirming it
    returns the capture that named it, and that sighting is carried into the
    second window: when the second window settles on the page without the
    target, the page is reported as unverified instead of as a settled page the
    target is simply not on.  A target the first window never named keeps the
    original whole-page rule unchanged, for inventory and target scans alike.

    The artificial window split does not break a real target run.  The first
    window hands the second one the target reading of its own *last actual
    capture*, so two consecutive readings that happen to straddle the boundary
    (the recorded capture 4 and capture 5) are still one run and confirm on the
    newest one.  A first window whose last capture did *not* name the target
    hands on ``None``, so a sighting from earlier in that window never stands in
    as the immediate predecessor: one reading after a gap stays one reading.
    Nothing survives the call -- the continuity cell is local, so every fresh
    call starts from ``None``.
    """
    state: list[dict[str, Any] | None] = [None]
    frame, cards, stable, clipped = _sample_visible(
        context, catalog, attempts=attempts, interval=interval,
        target_id=target_id, target_state=state)
    if frame is None or stable:
        return frame, cards, stable, clipped
    seen = any(row["vehicle"]["id"] == target_id for row in cards)
    time.sleep(interval)
    frame, cards, stable, clipped = _sample_visible(
        context, catalog, attempts=attempts, interval=interval,
        target_id=target_id, target_state=state)
    if seen and stable and not any(row["vehicle"]["id"] == target_id
                                   for row in cards):
        return frame, cards, False, clipped
    return frame, cards, stable, clipped


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


def _identity_evidence(evidence: list[dict[str, Any]], words: list[dict[str, Any]]) -> bool:
    """Add one frame's identity words to the bounded page evidence.

    Returns whether the frame contributed anything new, which is how the
    caller counts the distinct readable frames of one page.
    """
    fresh = False
    known = {(item["text"], tuple(item["box"])) for item in evidence}
    for item in words:
        signature = (item["text"], tuple(item["box"]))
        if signature in known:
            continue
        known.add(signature)
        evidence.append(item)
        fresh = True
    return fresh


def _detail(context: Any, expected_id: str, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify one detail page, with a bounded multi-frame name read.

    The detail title scrolls horizontally as well: the recorded frames read
    ``FORMULA E`` + ``GEN 3 EV0 CI`` and then ``3 EVO CHAMPIONSH`` for one car.
    The identity block is therefore accumulated over the bounded attempts of
    this one visit, and the rolling fallback only runs once at least two frames
    of the same page contributed words.  A frame that shows the garage list
    title instead clears the accumulation: fragments of two different pages must
    never be combined into one identity.
    """
    last_verified: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []
    name_frames = 0
    for _ in range(DETAIL_ATTEMPTS):
        time.sleep(DETAIL_INTERVAL)
        frame = _frame(context)
        words = _ocr(context, frame, (160, 76, 300, 110))
        if _selection_title(context, frame):
            evidence.clear()
            name_frames = 0
            continue
        if _identity_evidence(evidence, words):
            name_frames += 1
        observed = match_vehicle(words, catalog)
        if observed is None and name_frames >= 2:
            observed = rolling_identity(evidence, catalog)
        if observed and observed["id"] == expected_id:
            lower = _ocr(context, frame, (200, 560, 800, 150))
            occupied = any("已被放置" in row["text"] or "所在的赛道" in row["text"]
                           for row in lower)
            rating = next((score for row in _ocr(context, frame, (900, 90, 210, 90))
                           if (score := _current_rating(row["text"])) is not None), None)
            stars_lit, star_slots = _detail_stars(frame)
            verified = {"status": "detail_verified", "occupied_elsewhere": occupied,
                        "select_available": False, "detail_vehicle": observed,
                        "detail_name_frames": name_frames,
                        "detail_identity_basis": observed.get("identity_basis", "title"),
                        "performance": rating, "stars_lit": stars_lit,
                        "star_slots": star_slots}
            if occupied:
                return verified
            if _select_button_ready(context, frame):
                verified["select_available"] = True
                return verified
            last_verified = verified
        elif observed and (observed["confidence"] >= .95
                           or observed.get("identity_basis") == "rolling_fragment"):
            # A unique rolling reading of another car is evidence of the wrong
            # page, not an unclear one: it keeps the bounded retry.
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
        frame, cards, stable, _clipped = _stable_sample_visible(
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
    sampled_frame, cards, stable, clipped = _stable_sample_visible(
        context, catalog, attempts=3, target_id=target_id)
    if sampled_frame is None:
        return _result("not_duel_selection", 0, [])
    if not stable:
        return _result("page_ocr_unverified", 0, [])
    card = next((row for row in cards if row["vehicle"]["id"] == target_id), None)
    if card is None:
        # A target that is only there as the clipped right-edge card is not
        # visible: this path never re-positions, so its geometry stays unused.
        extra = {"clipped_target": clipped[0]} if clipped else {}
        return _result("target_not_visible", 0, cards, **extra)
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

    Coverage is bounded and observable: a clipped right-edge card whose visible
    name resolves uniquely is followed up with at most
    :data:`EDGE_REPOSITION_LIMIT` small re-positions per page (counted in
    ``edge_repositions``), and if that budget runs out before the card can be
    observed whole the scan returns ``edge_candidate_unresolved`` with
    ``scan_complete`` False instead of reporting a complete traversal or a
    missing target.  The page limit and the swipe budget stay in force.
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
    edge_repositions = 0
    for page in range(fast_forward + 1, max_pages + 1):
        frame, cards, stable, clipped = _stable_sample_visible(
            context, catalog, target_id=target_id)
        if frame is None:
            return _result("selection_lost", page - 1, list(found.values()))
        if not stable:
            # A target scan that read its car but never confirmed it lands here
            # too: nothing is opened and no page swipe is authorised on an
            # unconfirmed target.  The target id is reported so the two cases
            # stay diagnosable apart.
            extra = {"target_id": target_id} if target_id is not None else {}
            return _result("page_ocr_unverified", page, list(found.values()),
                           unstable_samples=2, **extra)
        # The sampled page is handled as it is read -- page/class guards, the
        # inventory record and the current complete target -- and only then is
        # the bounded right-edge completion attempted.  A card the screen edge
        # clips is not readable here and the next fling can carry the list past
        # it, so a card whose visible name resolves uniquely over the whole
        # catalog gets a small, controlled re-position until it has had a full
        # observation.  Because the full target of this page is served first, a
        # car that is already visible whole is never slid away for an unrelated
        # edge card, and every complete observation is booked before the list
        # can move.  Nothing is clicked before a full observation: the clipped
        # row carries no usable geometry, and the swipe distance is never
        # assumed either.
        #
        # Every candidate that still owes a full observation is kept as a debt
        # until *that exact car* is seen whole.  It is never dropped because the
        # next frame's OCR lost it, because the fling overshot it, or because a
        # different candidate appeared: those all leave the page incompletely
        # covered, which is reported as such instead of as a complete traversal.
        owed: dict[str, dict[str, Any]] = {}
        edge_attempts = 0
        while True:
            if not cards:
                return _result("page_ocr_unverified", page, list(found.values()),
                               edge_repositions=edge_repositions)
            target_cards = [row for row in cards if row["class"] == vehicle_class]
            foreign_classes = {row["class"] for row in cards
                               if row["class"] != vehicle_class}
            unexpected = foreign_classes - lower_classes
            if unexpected:
                return _result("class_or_ocr_unverified", page, list(found.values()),
                               visible=cards, unexpected_classes=sorted(unexpected),
                               edge_repositions=edge_repositions)
            # A transition page can contain the tail of the requested class and
            # the head of the next one.  Keep its requested-class cards and stop
            # only on a stable page containing lower classes alone.
            next_class_card = next((row for row in cards
                                    if row["class"] in lower_classes), None)
            at_boundary = not target_cards and bool(foreign_classes) and stable
            fingerprint = _fingerprint(target_cards)
            for row in target_cards:
                found.setdefault(row["vehicle"]["id"], {**row, "page": page})
            if not at_boundary and target_id in fingerprint:
                card = next(row for row in target_cards
                            if row["vehicle"]["id"] == target_id)
                result = _try_target(
                    context, card, page, list(found.values()), target_id, catalog,
                    choose=choose, expected_performance=expected_performance,
                    expected_stars=expected_stars,
                    verify_list_detail_rating=verify_list_detail_rating)
                result["fast_forward_swipes"] = fast_forward
                result["edge_repositions"] = edge_repositions
                if result["status"] != "target_temporarily_unreadable":
                    return result
            for row in clipped:
                vehicle_id = row["vehicle"]["id"]
                if (row["class"] == vehicle_class and vehicle_id not in found
                        and vehicle_id not in owed):
                    owed[vehicle_id] = row
            for vehicle_id in [key for key in owed if key in fingerprint]:
                del owed[vehicle_id]
            if at_boundary:
                # A lower-class page is only a real boundary when nothing on the
                # previous page still owes a full observation.  Otherwise the
                # owed car was carried out of view and the traversal is
                # incomplete, not a finished one.
                if owed:
                    return _result("edge_candidate_unresolved", page,
                                   list(found.values()),
                                   edge_candidate=next(iter(owed.values())),
                                   edge_repositions=edge_repositions,
                                   boundary_reason="edge_candidate_overshot")
                status = "target_not_found" if target_id else "class_boundary"
                return _result(status, page - 1, list(found.values()),
                               boundary_reason="next_class",
                               edge_repositions=edge_repositions,
                               next_class=(next_class_card["class"]
                                           if next_class_card is not None else None))
            if not owed:
                break
            if edge_attempts >= EDGE_REPOSITION_LIMIT:
                return _result("edge_candidate_unresolved", page,
                               list(found.values()),
                               edge_candidate=next(iter(owed.values())),
                               edge_repositions=edge_repositions,
                               boundary_reason="edge_reposition_budget")
            edge_attempts += 1
            edge_repositions += 1
            if not context.tasker.controller.post_swipe(
                    *EDGE_REPOSITION_SWIPE).wait().succeeded:
                return _result("swipe_failed", page - 1, list(found.values()),
                               edge_candidate=next(iter(owed.values())),
                               edge_repositions=edge_repositions)
            time.sleep(EDGE_REPOSITION_INTERVAL)
            frame, cards, stable, clipped = _stable_sample_visible(
                context, catalog, target_id=target_id)
            if frame is None:
                return _result("selection_lost", page - 1, list(found.values()),
                               edge_candidate=next(iter(owed.values())),
                               edge_repositions=edge_repositions)
            if not stable:
                return _result("page_ocr_unverified", page, list(found.values()),
                               unstable_samples=2,
                               edge_candidate=next(iter(owed.values())),
                               edge_repositions=edge_repositions)
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
                           boundary_reason="list_edge", edge_repositions=edge_repositions)
        if page == max_pages:
            break
        previous, previous_image = fingerprint, frame
        if not context.tasker.controller.post_swipe(1090, 480, 400, 480, 300).wait().succeeded:
            return _result("swipe_failed", page, list(found.values()),
                           edge_repositions=edge_repositions)
        time.sleep(.4)
    return _result("page_limit", max_pages, list(found.values()),
                   edge_repositions=edge_repositions)
