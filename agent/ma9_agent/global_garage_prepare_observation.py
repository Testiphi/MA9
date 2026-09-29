"""Offline Observation adapter for the global-garage prepare flow (05AK-B).

Turns one native 1280x720 BGR frame plus the OCR item list of that same frame
into the pure planner's :class:`~ma9_agent.global_garage_prepare_plan.Observation`,
with per-field evidence and reasons.  This module is a thin adapter around the
existing page classifier, owned-checkbox reader and card detector; it adds two
visual judgements only (the non-owned filter controls on the panel, and the
D-start geometry of the list) and does not extend inventory recognition.

Trust boundary (recorded, never claimed as verified):

* ``session_id``/``frame_id`` are supplied by the future real sampling caller,
  strictly validated here (non-empty string; non-bool non-negative int) but
  never generated, incremented or clock-derived by this module;
* the OCR list is *assumed* to come from the same frame -- a calling
  convention this module cannot prove and does not pretend to authenticate.
  Items are accepted only with a string text, a finite confidence inside
  [0, 1] and a box of four finite values with positive width/height lying
  fully inside the native 1280x720 frame; anything else is counted as
  rejected and can never serve as field evidence.  The sort-direction label
  additionally requires its whole box inside the label ROI, not a centre hit;
* identical pixels may be two genuine stable samples, and reading one offline
  file twice is not two samples: only the caller's distinct frame_ids carry
  that meaning, and the planner already ignores stale frame_ids.

Every diagnostic is ``executable=False`` and ``offline_only``; no click target
and no action receipt is produced, and nothing here may be read as a live-ready
or device-authorisation claim.

Calibration (measured on the read-only frames of ``captures/global_garage``,
probes archived under ``MA9-evidence/20260929-05AK-B-observation/``):

* panel control cells (x, y, w, h): brand ``(314, 124, 47, 47)``, owned
  ``(314, 188, 47, 48)`` (already in the screen module), stars
  ``(314, 329, 47, 47)``, performance ``(314, 394, 47, 47)`` -- an unchecked
  cell shows a clear empty outline (structure ~69, green fraction 0.0,
  outline gap ~78-81) and a checked cell fills yellow-green (fraction 0.672
  measured on the real owned-on frame).  "Unchecked" additionally requires a
  provably empty interior: every real cell of both panels carries a small
  bright folded-corner decoration (~2x2 px at the cell's bottom-right, cell
  coords ~(38..39, 38..39)) over an otherwise uniform dark interior (gray
  ~= 9), so the interior check skips a 7 px border ring and a 4x4
  bottom-right corner and then demands a uniform dark remainder -- any
  unexplained mark (white/coloured tick, pollution) keeps the cell unknown
  instead of being read as empty;
* the sort-direction label ("升序" on both real panels, OCR box
  ``[52, 299, 44, 25]``) is a *direction* toggle and is never confused with
  the performance sort key -- their regions are disjoint.  The supported
  default-sort layout semantics: direction label reads 升序 and no sort key
  is selected.  No 降序 or selected-key frame exists in the corpus, so those
  states are only ever reported from what is actually read;
* the D-start left rail: a white square section badge (~48x49) on a vertical
  dotted divider.  The badge glyph is separated structurally: the letter D has
  exactly one enclosed counter spanning most of the glyph (hole height /
  glyph height 0.70 real / 0.64 synthetic), while the real R badge measures
  0.33 (synthetic R 0.22, B has two holes, C/S none).  At the list origin the
  D badge centre sits at x~158 (badge top y~408) with the first card column
  of both rows aligned at x~219; the divider-to-column offset is ~61 px on
  both real section markers, so a displaced marker means a scrolled list;
* the badge/marker zone (x 100..210, y 390..480) is below the header band and
  the top D/C/B/A/S/R jump buttons (y ~86..140), which are excluded from the
  start judgement by construction, as is any OCR letter: a lone "D" string
  never overrides image context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

from .global_garage_prepare_plan import (
    FILTER_PANEL,
    GARAGE_LIST,
    Observation,
    OFF,
    ON,
    OTHER_PAGE,
    UNKNOWN_FILTER,
    UNKNOWN_PAGE,
)
from .global_garage_screen import (
    CHECKBOX_MIN_OUTLINE,
    CHECKBOX_ROI,
    CHECKBOX_MIN_STRUCTURE,
    OWNED_OFF,
    OWNED_ON,
    OWNED_UNKNOWN,
    PAGE_FILTER_PANEL,
    PAGE_GARAGE_LIST,
    PAGE_HOME,
    PAGE_UNSUPPORTED,
    SPAN_FULL_MAX,
    SPAN_FULL_MIN,
    classify_page,
    detect_card_boxes,
    read_owned_filter,
)

#: Panel cells of the three non-owned controls (x, y, w, h), calibrated 05AK-B.
CONTROL_ROIS = {
    "brand": (314, 124, 47, 47),
    "stars": (314, 329, 47, 47),
    "performance": (314, 394, 47, 47),
}
#: Region (x0, y0, x1, y1) holding the sort-direction label 升序/降序.
SORT_LABEL_ROI = (40, 288, 130, 332)
ASCENDING_TEXT = "升序"
DESCENDING_TEXT = "降序"
#: Minimum OCR confidence for the textual sort label (matches the screen module).
SORT_MIN_CONFIDENCE = .85

#: OCR item contract: boxes are four finite values with positive width/height
#: fully inside the native frame; confidences are finite inside [0, 1].
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720

#: Interior evidence window for an unchecked control cell: skip the border
#: ring, exclude the bottom-right folded-corner decoration (~2x2 bright px at
#: cell coords ~(38..39, 38..39) on every real cell of both panels), then
#: require a uniform dark remainder before a cell may count as unchecked.
CELL_BORDER_SKIP = 7
CELL_CORNER_SKIP = 4
CELL_INTERIOR_MAX_GRAY = 90
CELL_INTERIOR_MAX_STD = 8.0

#: Search zone (x0, y0, x1, y1) for the left-rail section badge; the top class
#: buttons (y ~86..140) and the header band are outside by construction.
MARKER_ZONE = (100, 390, 210, 480)
MARKER_MIN_SIDE, MARKER_MAX_SIDE = 40, 60
MARKER_MIN_AREA = 900
#: Calibrated position of the D badge at the list origin.
D_MARKER_CENTER_X = (148, 168)
D_MARKER_TOP_Y = (400, 416)
#: Calibrated first-column left edge at the list origin, both rows aligned.
FIRST_COLUMN_X = (209, 229)
ROW_ALIGN_TOLERANCE = 6
#: A card column whose left edge is below this is left of any section-start
#: position: the list is scrolled and this is definite non-start evidence.
SCROLLED_LEFT_X = 200

#: Badge glyph structural thresholds (real D hole ratio 0.70, real R 0.33;
#: synthetic Hershey D 0.64, R 0.22, B two holes, C/S/A none).
GLYPH_DARK_THRESHOLD = 100
GLYPH_MIN_HEIGHT = 15
GLYPH_MIN_WIDTH = 8
GLYPH_INK_FRACTION = (.10, .45)
GLYPH_MIN_PART_AREA = 20
HOLE_MIN_AREA = 12
HOLE_RATIO_D_MIN = .50
HOLE_RATIO_OTHER_MAX = .35

#: Dotted divider thresholds: transitions of the bright-dot pattern along one
#: column of the content band (real markers peak at 38; scrolled frames show
#: diffuse 14-26 across many columns).
DIVIDER_BAND = (225, 640)
DIVIDER_WINDOW = 8
DIVIDER_ACTIVE_TRANSITIONS = 16
DIVIDER_PEAK_TRANSITIONS = 30
DIVIDER_MAX_ACTIVE_COLUMNS = 8

_LIST_PAGE_ROIS = "measurement_regions_only"


@dataclass(frozen=True)
class ObserveResult:
    """Planner observation plus per-field evidence; never executable."""

    observation: Observation
    diagnostics: dict[str, Any]
    executable: bool = False
    offline_only: bool = True


# --------------------------------------------------------------------------- #
# OCR sanitation
# --------------------------------------------------------------------------- #
def _finite_unit(value: Any) -> float | None:
    """Finite float inside [0, 1], or None; never raises on huge ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


def _finite_coordinate(value: Any) -> float | None:
    """Finite float coordinate, or None; never raises on huge ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        return None


def _sanitize_ocr(ocr: Iterable[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], int]:
    """Keep only well-formed items; count (never silently fix) the rejects.

    An item is kept only with a string text, a finite confidence inside
    [0, 1] and a box of four finite values with positive width/height lying
    fully inside the native 1280x720 frame.  NaN/Infinity, out-of-unit
    confidences, negative/zero extents and out-of-frame boxes are dropped
    rather than trusted: an isolated string must not override image context,
    and rejected items can never become field evidence.
    """
    items: list[dict[str, Any]] = []
    rejected = 0
    for raw in (ocr or []):
        if not isinstance(raw, dict):
            rejected += 1
            continue
        text = raw.get("text")
        confidence = _finite_unit(raw.get("confidence"))
        box = raw.get("box")
        if not isinstance(text, str) or confidence is None:
            rejected += 1
            continue
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            rejected += 1
            continue
        coords = [_finite_coordinate(v) for v in box]
        if any(c is None or not math.isfinite(c) for c in coords):
            rejected += 1
            continue
        x, y, width, height = (float(c) for c in coords)
        if (width <= 0 or height <= 0 or x < 0 or y < 0
                or x + width > FRAME_WIDTH or y + height > FRAME_HEIGHT):
            rejected += 1
            continue
        items.append({"text": text, "confidence": confidence,
                      "box": [x, y, width, height]})
    return items, rejected


def _box_inside(box: Sequence[float], roi: tuple[int, int, int, int]) -> bool:
    """The whole box must lie inside the ROI, not merely its centre."""
    x, y, width, height = box
    left, top, right, bottom = roi
    return (left <= x and top <= y and x + width <= right and y + height <= bottom)


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
def _classify(image: np.ndarray, items: list[dict[str, Any]]) -> dict[str, Any]:
    result = classify_page(image, items)
    raw = result["page"]
    if raw == PAGE_GARAGE_LIST:
        mapped, reason = GARAGE_LIST, "garage_list_as_classified"
    elif raw == PAGE_FILTER_PANEL:
        mapped, reason = FILTER_PANEL, "filter_panel_as_classified"
    elif raw == PAGE_HOME:
        # Positive home evidence only (bright-textured cards without the garage
        # header); recognition failure maps to unknown below, never to other.
        mapped, reason = OTHER_PAGE, "home_page_evidence_mapped_to_other"
    else:
        mapped = UNKNOWN_PAGE
        reason = "unsupported_size" if raw == PAGE_UNSUPPORTED else "no_positive_page_evidence"
    return {"mapped": mapped, "classified": raw, "reason": reason,
            "reasons": list(result["reasons"]), "evidence": result["evidence"],
            "supported": bool(result["supported"])}


# --------------------------------------------------------------------------- #
# other filters (panel only)
# --------------------------------------------------------------------------- #
def _cell_state(frame: np.ndarray, roi: tuple[int, int, int, int]) -> dict[str, Any]:
    """One panel control cell: checked / unchecked / unknown, with evidence.

    Mirrors the owned-checkbox reader's evidence rules: the cell body must be
    visible (structure), a yellow-green fill means selected, and "unchecked"
    needs the empty outline -- plus a provably empty interior.  The interior
    check skips the border ring and the bottom-right folded-corner
    decoration (measured on every real cell of both panels) and then demands
    a uniform dark remainder, so a white or coloured mark inside a cell is
    reported as unknown content instead of an empty box.
    """
    left, top, width, height = roi
    patch = frame[top:top + height, left:left + width]
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    structure = float(gray.std())
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    green = ((hsv[:, :, 0] >= 25) & (hsv[:, :, 0] <= 70)
             & (hsv[:, :, 1] >= 90) & (hsv[:, :, 2] >= 130))
    fraction = float(green.mean())
    border = np.concatenate([gray[:5].ravel(), gray[-5:].ravel(),
                             gray[:, :5].ravel(), gray[:, -5:].ravel()])
    outline_gap = float(border.mean() - gray[8:40, 8:40].mean())
    interior = gray[CELL_BORDER_SKIP:-CELL_BORDER_SKIP, CELL_BORDER_SKIP:-CELL_BORDER_SKIP]
    mask = np.ones(interior.shape, dtype=bool)
    mask[-CELL_CORNER_SKIP:, -CELL_CORNER_SKIP:] = False
    checkable = interior[mask]
    interior_max = float(checkable.max()) if checkable.size else 255.0
    interior_std = float(checkable.std()) if checkable.size else 255.0
    # Luma alone misses saturated blue and thin dark marks.  All seven real
    # unchecked interiors are uniform BGR (33, 9, 0) outside the decoration.
    # Check each channel relative to its median without hardcoding that colour;
    # this only withholds an off verdict, never promotes unknown to on/off.
    colours = patch[CELL_BORDER_SKIP:-CELL_BORDER_SKIP,
                    CELL_BORDER_SKIP:-CELL_BORDER_SKIP][mask].astype(np.float32)
    channel_deviation = (float(np.abs(colours - np.median(colours, axis=0)).max())
                         if colours.size else 255.0)
    interior_empty = (interior_max <= CELL_INTERIOR_MAX_GRAY
                      and interior_std <= CELL_INTERIOR_MAX_STD
                      and channel_deviation <= 8.0)
    evidence = {"roi": list(roi), "structure": round(structure, 1),
                "green_fraction": round(fraction, 3), "outline_gap": round(outline_gap, 1),
                "interior_max_gray": round(interior_max, 1),
                "interior_std": round(interior_std, 1),
                "interior_channel_deviation": round(channel_deviation, 1),
                "interior_window": {"border_skip": CELL_BORDER_SKIP,
                                    "bottom_right_corner_skip": CELL_CORNER_SKIP}}
    if structure < CHECKBOX_MIN_STRUCTURE:
        return {**evidence, "state": "unknown", "reason": "control_body_not_confirmed"}
    if fraction >= .35:
        return {**evidence, "state": "checked", "reason": "control_filled_yellow_green"}
    if fraction <= .08 and outline_gap >= CHECKBOX_MIN_OUTLINE:
        if interior_empty:
            return {**evidence, "state": "unchecked",
                    "reason": "control_outline_visible_and_empty_interior"}
        return {**evidence, "state": "unknown", "reason": "unexplained_interior_content"}
    return {**evidence, "state": "unknown", "reason": "control_body_ambiguous"}


def _sort_direction(items: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """Read the direction label; contradictory readings stay unknown.

    A label counts only when its whole box lies inside the label ROI -- a
    centre hit from a frame-spanning box is not label evidence.
    """
    found = []
    for item in items:
        if item["confidence"] < SORT_MIN_CONFIDENCE:
            continue
        text = item["text"].strip()
        if text in (ASCENDING_TEXT, DESCENDING_TEXT) and _box_inside(item["box"], SORT_LABEL_ROI):
            found.append({**item, "box": [round(v, 1) for v in item["box"]]})
    kinds = {item["text"].strip() for item in found}
    if len(kinds) > 1:
        return "conflict", found
    if not kinds:
        return None, found
    return (ASCENDING_TEXT if kinds == {ASCENDING_TEXT} else DESCENDING_TEXT), found


def _observe_other_filters(frame: np.ndarray,
                           items: list[dict[str, Any]]) -> tuple[bool | None, dict[str, Any]]:
    controls = {name: _cell_state(frame, roi) for name, roi in CONTROL_ROIS.items()}
    direction, label_items = _sort_direction(items)
    evidence = {"controls": controls,
                "sort_direction": {"value": direction, "label_items": label_items,
                                   "roi": list(SORT_LABEL_ROI),
                                   "semantics": "direction_toggle_never_a_sort_key"},
                "rois": _LIST_PAGE_ROIS}
    checked = [name for name, cell in controls.items() if cell["state"] == "checked"]
    unknown = [name for name, cell in controls.items() if cell["state"] == "unknown"]
    unchecked = [name for name, cell in controls.items() if cell["state"] == "unchecked"]
    if checked:
        return False, {**evidence, "value": False,
                       "reasons": [f"control_checked:{name}" for name in checked]}
    if direction == DESCENDING_TEXT:
        return False, {**evidence, "value": False,
                       "reasons": ["sort_direction_not_default_ascending"]}
    if direction == "conflict":
        return None, {**evidence, "value": None,
                      "reasons": ["sort_direction_readings_conflict"]}
    if len(unchecked) == len(CONTROL_ROIS) and direction == ASCENDING_TEXT:
        return True, {**evidence, "value": True,
                      "reasons": ["all_controls_unselected_default_ascending_sort"]}
    reasons = []
    if unknown:
        reasons.extend(f"control_state_unknown:{name}" for name in unknown)
    if direction is None:
        reasons.append("sort_direction_unknown")
    return None, {**evidence, "value": None, "reasons": reasons or ["other_filters_not_confirmable"]}


# --------------------------------------------------------------------------- #
# D-start geometry (list only)
# --------------------------------------------------------------------------- #
def _marker_candidates(frame: np.ndarray) -> list[dict[int, int]]:
    """White square section badges inside the calibrated marker zone."""
    x0, y0, x1, y1 = MARKER_ZONE
    zone = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(zone, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 1] < 60) & (hsv[:, :, 2] > 170)).astype(np.uint8)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(white, 8)
    out = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if (MARKER_MIN_SIDE <= w <= MARKER_MAX_SIDE and MARKER_MIN_SIDE <= h <= MARKER_MAX_SIDE
                and abs(w - h) <= 6 and area >= MARKER_MIN_AREA):
            out.append({"x": x0 + x, "y": y0 + y, "w": w, "h": h})
    return out


def _badge_letter(frame: np.ndarray, badge: dict[int, int]) -> tuple[str | None, dict[str, Any]]:
    """Structural letter check: "D", a confident non-D, or None.

    D has exactly one enclosed counter spanning most of the glyph height; a
    small top loop (R/P), two counters (B) or none (C/S/A) is confidently not
    D.  Anything between the ratio bands or failing the sanity gates stays
    unreadable rather than guessed.
    """
    x, y, w, h = badge["x"], badge["y"], badge["w"], badge["h"]
    gray = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    glyph = (gray < GLYPH_DARK_THRESHOLD).astype(np.uint8)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(glyph, 8)
    parts = [index for index in range(1, count) if stats[index][4] >= GLYPH_MIN_PART_AREA]
    ink_fraction = float(glyph.mean())
    evidence: dict[str, Any] = {"ink_fraction": round(ink_fraction, 3), "parts": len(parts)}
    if len(parts) != 1:
        return None, {**evidence, "letter": None, "reason": "glyph_not_a_single_component"}
    px, py, pw, ph, _area = (int(v) for v in stats[parts[0]])
    evidence["glyph_box"] = [px, py, pw, ph]
    if ph < GLYPH_MIN_HEIGHT or pw < GLYPH_MIN_WIDTH:
        return None, {**evidence, "letter": None, "reason": "glyph_too_small"}
    if not GLYPH_INK_FRACTION[0] <= ink_fraction <= GLYPH_INK_FRACTION[1]:
        return None, {**evidence, "letter": None, "reason": "glyph_ink_fraction_out_of_range"}

    light = (gray >= GLYPH_DARK_THRESHOLD).astype(np.uint8)
    n_holes, _labels, hstats, _centroids = cv2.connectedComponentsWithStats(light, 8)
    holes = []
    for index in range(1, n_holes):
        hx, hy, hw, hh, ha = (int(v) for v in hstats[index])
        touches = hx == 0 or hy == 0 or hx + hw == w or hy + hh == h
        if not touches and ha >= HOLE_MIN_AREA:
            holes.append((hh, hw, ha))
    evidence["holes"] = [{"h": hh, "w": hw, "area": ha} for hh, hw, ha in holes]
    if len(holes) == 0 or len(holes) == 2:
        return "other", {**evidence, "letter": "other",
                         "reason": "enclosed_counter_count_is_not_one"}
    if len(holes) > 2:
        return None, {**evidence, "letter": None, "reason": "glyph_holes_uninterpretable"}
    ratio = holes[0][0] / ph
    evidence["hole_height_ratio"] = round(ratio, 3)
    if ratio >= HOLE_RATIO_D_MIN:
        return "D", {**evidence, "letter": "D", "reason": "single_tall_enclosed_counter"}
    if ratio <= HOLE_RATIO_OTHER_MAX:
        return "other", {**evidence, "letter": "other",
                         "reason": "counter_too_short_for_d"}
    return None, {**evidence, "letter": None, "reason": "counter_ratio_inconclusive"}


def _divider_evidence(frame: np.ndarray, center_x: int) -> dict[str, Any]:
    """Dotted-divider check along the column band through the badge centre."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    top, bottom = DIVIDER_BAND
    lo, hi = max(0, center_x - DIVIDER_WINDOW), min(frame.shape[1], center_x + DIVIDER_WINDOW + 1)
    transitions = {}
    for x in range(lo, hi):
        column = gray[top:bottom, x] > 150
        transitions[x] = int((np.diff(column.astype(np.int8)) != 0).sum())
    active = [x for x, value in transitions.items() if value >= DIVIDER_ACTIVE_TRANSITIONS]
    peak = max(transitions.values()) if transitions else 0
    through = any(abs(x - center_x) <= 3 for x in active)
    ok = (peak >= DIVIDER_PEAK_TRANSITIONS and len(active) <= DIVIDER_MAX_ACTIVE_COLUMNS
          and through)
    return {"ok": bool(ok), "peak_transitions": peak,
            "active_columns": active, "search_band": [lo, hi]}


def _first_column(frame: np.ndarray) -> dict[str, Any]:
    """First-column geometry: aligned full cards of both rows, nothing lefter."""
    boxes = detect_card_boxes(frame)
    rows: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for box in boxes:
        rows.setdefault(box["row"], []).append(box)
    lefts = {row: sorted(box["box"][0] for box in entries) for row, entries in rows.items()}
    all_lefts = [left for row in (0, 1) for left in lefts[row]]
    leftmost = min(all_lefts) if all_lefts else None
    clipped_left = any(box["clipped_left"] for box in boxes)
    aligned = bool(lefts[0] and lefts[1]
                   and abs(lefts[0][0] - lefts[1][0]) <= ROW_ALIGN_TOLERANCE)
    full = bool(lefts[0] and lefts[1])
    for row in (0, 1):
        if rows[row]:
            width = min(box["box"][2] for box in rows[row] if box["box"][0] == lefts[row][0])
            full = full and SPAN_FULL_MIN <= width <= SPAN_FULL_MAX
    return {"row_lefts": {str(row): lefts[row] for row in (0, 1)},
            "leftmost": leftmost, "clipped_left": bool(clipped_left),
            "aligned": aligned, "first_cards_full": full,
            "box_count": len(boxes)}


def _observe_at_d_start(frame: np.ndarray) -> tuple[bool | None, dict[str, Any]]:
    badges = _marker_candidates(frame)
    letters = [_badge_letter(frame, badge) for badge in badges]
    badge_evidence = [{"box": [b["x"], b["y"], b["w"], b["h"]], **letter}
                      for b, (_letter, letter) in zip(badges, letters)]
    columns = _first_column(frame)
    evidence = {"markers": badge_evidence, "first_column": columns,
                "rois": _LIST_PAGE_ROIS,
                "calibration": {"d_marker_center_x": list(D_MARKER_CENTER_X),
                                "d_marker_top_y": list(D_MARKER_TOP_Y),
                                "first_column_x": list(FIRST_COLUMN_X)}}
    leftmost = columns["leftmost"]
    scrolled = columns["clipped_left"] or (leftmost is not None and leftmost < SCROLLED_LEFT_X)

    readable = [entry for entry in badge_evidence if entry["letter"] in ("D", "other")]
    if any(entry["letter"] == "other" for entry in readable):
        return False, {**evidence, "value": False,
                       "reasons": ["non_d_section_marker_visible"]}
    if len(badges) > 1:
        return None, {**evidence, "value": None, "reasons": ["marker_layout_ambiguous"]}

    if len(badges) == 1:
        badge = badges[0]
        center_x = badge["x"] + badge["w"] // 2
        divider = _divider_evidence(frame, center_x)
        evidence["divider"] = divider
        position_ok = (D_MARKER_CENTER_X[0] <= center_x <= D_MARKER_CENTER_X[1]
                       and D_MARKER_TOP_Y[0] <= badge["y"] <= D_MARKER_TOP_Y[1])
        column_ok = (columns["aligned"] and columns["first_cards_full"]
                     and leftmost is not None
                     and FIRST_COLUMN_X[0] <= leftmost <= FIRST_COLUMN_X[1])
        if readable and readable[0]["letter"] == "D":
            if position_ok and divider["ok"] and column_ok and not scrolled:
                return True, {**evidence, "value": True,
                              "reasons": ["d_marker_divider_and_first_column_all_confirmed"]}
            if scrolled:
                return False, {**evidence, "value": False,
                               "reasons": ["list_scrolled_left_of_start"]}
            if not position_ok:
                return None, {**evidence, "value": None,
                              "reasons": ["d_marker_not_at_calibrated_position"]}
            if not divider["ok"]:
                return None, {**evidence, "value": None,
                              "reasons": ["divider_dots_not_confirmed"]}
            return None, {**evidence, "value": None,
                          "reasons": ["first_column_geometry_not_confirmed"]}
        # A badge is visible but its letter is unreadable: geometry alone never
        # proves the D start (any section start looks the same).
        if scrolled:
            return False, {**evidence, "value": False,
                           "reasons": ["list_scrolled_left_of_start"]}
        return None, {**evidence, "value": None, "reasons": ["d_marker_letter_unreadable"]}

    if scrolled:
        return False, {**evidence, "value": False,
                       "reasons": ["list_scrolled_left_of_start"]}
    return None, {**evidence, "value": None, "reasons": ["d_marker_missing"]}


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def observe(image: np.ndarray, ocr: Iterable[dict[str, Any]] | None, *,
            session_id: str, frame_id: int) -> ObserveResult:
    """Convert one native frame plus its same-frame OCR into an Observation.

    ``image`` must be a non-empty HxWx3 uint8 BGR ndarray; anything else
    (grey, four-channel, wrong dtype, empty) raises a uniform ValueError at
    the entry point instead of failing inside OpenCV.  A well-formed frame of
    a non-native size is accepted and yields an unknown page and unknown
    fields.  ``ocr`` is the caller's item list for *this* frame -- the
    binding is a calling convention this module records but cannot verify.
    """
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")
    if not isinstance(frame_id, int) or isinstance(frame_id, bool) or frame_id < 0:
        raise ValueError("frame_id must be a non-negative integer")
    if not isinstance(image, np.ndarray):
        raise ValueError("image must be a BGR ndarray")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"image must be HxWx3 BGR, got shape {tuple(image.shape)}")
    if image.dtype != np.uint8:
        raise ValueError(f"image dtype must be uint8, got {image.dtype}")
    if image.size == 0:
        raise ValueError("image must not be empty")

    items, rejected = _sanitize_ocr(ocr)
    page = _classify(image, items)

    owned_result = read_owned_filter(image, items)
    owned_state = owned_result["state"]
    owned = {k: v for k, v in owned_result.items() if k != "evidence"}
    # The shared reader's off verdict checks outline/colour only.  Withhold
    # that verdict here unless this adapter also confirms an empty interior;
    # do not alter the shared reader or promote an unknown result to on/off.
    if page["classified"] == PAGE_FILTER_PANEL and owned_state == OWNED_OFF:
        guard = _cell_state(image, CHECKBOX_ROI)
        owned["adapter_empty_interior_guard"] = guard
        if guard["state"] != "unchecked":
            owned_state = UNKNOWN_FILTER
            owned["state"] = UNKNOWN_FILTER
            owned["reasons"] = ["owned_empty_interior_not_confirmed"]

    if page["classified"] == PAGE_FILTER_PANEL:
        other_filters, other_evidence = _observe_other_filters(image, items)
    else:
        other_filters = None
        other_evidence = {"value": None,
                          "reasons": ["other_filters_only_readable_inside_the_filter_panel"]}

    if page["classified"] == PAGE_GARAGE_LIST:
        at_d_start, d_evidence = _observe_at_d_start(image)
    else:
        at_d_start = None
        d_evidence = {"value": None,
                      "reasons": ["at_d_start_only_judgeable_on_a_confirmed_garage_list"]}

    observation = Observation(session_id=session_id, frame_id=frame_id, page=page["mapped"],
                              owned_filter=owned_state, other_filters_clear=other_filters,
                              at_d_start=at_d_start)
    diagnostics = {
        "session_id": session_id,
        "frame_id": frame_id,
        "page": page,
        "owned_filter": owned,
        "other_filters_clear": other_evidence,
        "at_d_start": d_evidence,
        "ocr": {"items_used": len(items), "items_rejected": rejected,
                "same_frame_binding": "caller_contract_not_verified_by_this_module"},
        "executable": False,
        "offline_only": True,
    }
    return ObserveResult(observation=observation, diagnostics=diagnostics)


__all__ = ["ObserveResult", "observe", "Observation",
           "GARAGE_LIST", "FILTER_PANEL", "UNKNOWN_PAGE", "OTHER_PAGE",
           "ON", "OFF", "UNKNOWN_FILTER", "CONTROL_ROIS", "SORT_LABEL_ROI",
           "MARKER_ZONE", "FIRST_COLUMN_X"]
