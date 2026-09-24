"""Read-only observation of the unique expanded slot on the Duel lineup page.

This module answers exactly one question about an already-open five-slot Duel
lineup screenshot (the ``资格赛`` qualifier or the ``挑战`` challenge page):
**which of the five slots is currently expanded**.

Hard scope limits (05E):

* pure observation - no click, no garage entry, no vehicle assignment, no
  ``Controller``, no ADB, no ``scan``/``assign_visible`` call, no logging and
  no filesystem access; the caller owns capture, OCR and any later action;
* no map-name reference table, and no opponent/ticket/fuel/rating/vehicle data
  is read or required;
* a slot is never inferred from a page title, a map name, a green button alone
  or from a caller-supplied expectation.  The returned ordinal is *geometry of
  the expanded region* only.

Slot identity model
-------------------
The lineup strip lays five cells on a fixed pitch of ``SLOT_PITCH`` px.  Exactly
one cell is expanded (it carries the wide bright panel and the bright-green
``选择车辆`` / ``更换车辆`` button); the other four are collapsed narrow columns.
The strip is left-anchored, so the expanded cell's right boundary is::

    panel_right(n) = PANEL_RIGHT_BASE + SLOT_PITCH * (n - 1)

The committed static condition ``assets/resource/pipeline/duel_slot_navigation.json``
locates the same boundary through the expanded cell's selection button
(``ColorMatch`` ROIs at x = 589/701/816/930/1045, ``method`` 4 == ``cv2.COLOR_BGR2RGB``,
lower/upper ``(180,240,0)``-``(210,255,40)``).  This module re-uses that colour
and geometry but strips the entry ``Click``/``next`` actions and the
defence-only title template, so no pipeline node is executed here.

``PANEL_RIGHT_BASE``, ``SLOT_PITCH`` and ``BUTTON_CENTER_BASE`` are calibrated
against the committed resources plus the fixed 1280x720 samples listed in the
05E evidence report.  Only 1280x720 frames are accepted; a differently sized
screenshot is refused (``unsupported_size``) instead of being silently scaled.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import cv2
import numpy as np


SUPPORTED_SIZE = (1280, 720)

#: Horizontal pitch of the five lineup cells, in pixels at 1280x720.
SLOT_PITCH = 114
#: Left edge of the lineup strip.
STRIP_LEFT = 60
#: Right edge of the lineup strip.
STRIP_RIGHT = 1247
#: Right boundary of the expanded cell when the first slot is expanded.
PANEL_RIGHT_BASE = 791
#: Width of the expanded cell.
EXPANDED_WIDTH = 731
#: Centre of the expanded selection button when the first slot is expanded.
BUTTON_CENTER_BASE = 608.5

#: Bright-green selection button of the expanded cell (BGR2RGB components).
BUTTON_COLOR_LOWER = (180, 240, 0)
BUTTON_COLOR_UPPER = (210, 255, 40)
#: Vertical band that holds the expanded cell's selection button.
BUTTON_BAND = (455, 575)
#: Size class of the expanded selection button.
BUTTON_WIDTH_RANGE = (140, 220)
BUTTON_HEIGHT_RANGE = (36, 70)
BUTTON_AREA_RANGE = (4500, 12000)

#: Vertical band used for the "bright panel" column profile.
PROFILE_BAND = (210, 545)
#: A column belongs to the bright panel above this fraction of the band.
BRIGHT_RATIO = 0.40
#: The expanded panel run must be at least this wide.
PANEL_RUN_MIN_WIDTH = 100
#: The panel run must end this far right of the button's right edge.
PANEL_RIGHT_EXTENSION = (55, 150)

#: A collapsed cell marker is a narrow bright run outside the expanded panel.
#: The upper bound stays well below ``PANEL_RUN_MIN_WIDTH`` so a panel can never
#: be mistaken for a marker; observed markers are 19-41 px wide.
COLLAPSED_MARKER_MAX_WIDTH = 60
COLLAPSED_MARKER_MIN_WIDTH = 8

#: Accepted residual between a measured boundary and its slot grid position.
SLOT_TOLERANCE = 30
#: Accepted residual between the button centre and its slot grid position.
BUTTON_TOLERANCE = 40

#: Page titles that identify a Duel lineup page (qualifier / challenge).
LINEUP_TITLES = ("资格赛", "挑战")
#: Title region of the lineup page, as ``(x, y, w, h)``.
LINEUP_TITLE_ROI = (55, 70, 250, 120)
#: Title of the Duel garage page, which is *not* a lineup page.
SELECTION_PAGE_TITLE = "车辆选择"

REASON_VERIFIED = "verified"
REASON_UNSUPPORTED_SIZE = "unsupported_size"
REASON_NO_BUTTON = "no_expanded_button"
REASON_MULTIPLE_BUTTONS = "multiple_expanded_buttons"
REASON_PANEL_UNVERIFIED = "expanded_panel_unverified"
REASON_SLOT_CONFLICT = "slot_geometry_conflict"
REASON_MARKER_CONFLICT = "collapsed_marker_conflict"
REASON_TITLE_MISSING = "page_title_missing"
REASON_TITLE_CONFLICT = "page_title_conflict"


def _result(page: str, slot: int | None, reason: str, *,
            title: str | None = None, ocr_used: bool = False,
            **evidence: Any) -> dict[str, Any]:
    return {
        "page": page,
        "expanded_slot": slot,
        "slot_verified": slot is not None and reason == REASON_VERIFIED,
        "reason": reason,
        "page_title": title,
        "ocr_used": ocr_used,
        "evidence": evidence,
    }


def _as_frame(frame: Any) -> np.ndarray:
    if not isinstance(frame, np.ndarray):
        raise TypeError("frame must be a numpy array")
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError("frame must be a uint8 BGR image of shape (h, w, 3)")
    return frame


def _green_mask(frame: np.ndarray) -> np.ndarray:
    """Bright-green mask using the committed ``ColorMatch`` colour space."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return cv2.inRange(rgb, BUTTON_COLOR_LOWER, BUTTON_COLOR_UPPER)


def _bright_mask(frame: np.ndarray) -> np.ndarray:
    """Bright content mask (saturated or near-white) used for column profiles."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    return (((value >= 150) & (saturation >= 40)) | (value >= 205)).astype(np.uint8)


def _runs(flags: np.ndarray, *, min_width: int = 1) -> list[tuple[int, int]]:
    """Inclusive ``(left, right)`` runs of non-zero flags."""
    found: list[tuple[int, int]] = []
    start: int | None = None
    for index in range(flags.size + 1):
        inside = index < flags.size and int(flags[index]) > 0
        if inside and start is None:
            start = index
        elif not inside and start is not None:
            if index - start >= min_width:
                found.append((start, index - 1))
            start = None
    return found


def _strip_profile(frame: np.ndarray) -> np.ndarray:
    """Bright fraction per column inside the lineup strip's vertical band."""
    top, bottom = PROFILE_BAND
    band = _bright_mask(frame)[top:bottom, STRIP_LEFT:STRIP_RIGHT]
    profile = band.sum(axis=0).astype(np.float32) / (bottom - top)
    flags = (profile >= BRIGHT_RATIO).astype(np.int32)
    padded = np.zeros(frame.shape[1], dtype=np.int32)
    padded[STRIP_LEFT:STRIP_RIGHT] = flags
    return padded


def _button_candidates(frame: np.ndarray) -> list[dict[str, Any]]:
    """Bright-green blobs inside the expanded-button band and size class."""
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    top, bottom = BUTTON_BAND
    mask[top:bottom, STRIP_LEFT:STRIP_RIGHT] = _green_mask(frame)[top:bottom, STRIP_LEFT:STRIP_RIGHT]
    # The button label is dark text inside a green pill; close small gaps so a
    # single button cannot be reported as two candidates.
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        if not (BUTTON_WIDTH_RANGE[0] <= width <= BUTTON_WIDTH_RANGE[1]
                and BUTTON_HEIGHT_RANGE[0] <= height <= BUTTON_HEIGHT_RANGE[1]
                and BUTTON_AREA_RANGE[0] <= area <= BUTTON_AREA_RANGE[1]):
            continue
        candidates.append({
            "box": [x, y, width, height],
            "area": area,
            "center_x": round(float(centroids[index][0]), 1),
            "right": x + width - 1,
        })
    candidates.sort(key=lambda row: row["box"][0])
    return candidates


def _panel_run(profile: np.ndarray, button: dict[str, Any]) -> tuple[int, int] | None:
    """Bright run that carries the expanded button and ends at the panel edge."""
    button_right = button["right"]
    for left, right in _runs(profile, min_width=PANEL_RUN_MIN_WIDTH):
        if left <= button_right <= right:
            return left, right
    return None


def _slot_from(value: float, base: float, tolerance: float) -> tuple[int | None, float]:
    residual = value - base
    steps = round(residual / SLOT_PITCH)
    slot = 1 + steps
    if not 1 <= slot <= 5 or abs(residual - steps * SLOT_PITCH) > tolerance:
        return None, residual
    return slot, residual


def _collapsed_centers(slot: int, panel_right: float) -> dict[int, float]:
    centers: dict[int, float] = {}
    for index in range(1, slot):
        centers[index] = STRIP_LEFT + SLOT_PITCH / 2 + SLOT_PITCH * (index - 1)
    for index in range(slot + 1, 6):
        centers[index] = panel_right + SLOT_PITCH / 2 + SLOT_PITCH * (index - slot - 1)
    return centers


def _markers(profile: np.ndarray, panel_left: int, panel_right: int) -> list[dict[str, Any]]:
    """Narrow bright runs outside the expanded panel: collapsed cell markers.

    The exclusion span is the *derived* panel, not the measured bright run: the
    bright run's left end is content-dependent (the attack layout puts the
    player/opponent block on the panel's dark left half), while the model knows
    the panel always starts at ``panel_right - EXPANDED_WIDTH``.
    """
    found = []
    for left, right in _runs(profile, min_width=COLLAPSED_MARKER_MIN_WIDTH):
        width = right - left + 1
        if width > COLLAPSED_MARKER_MAX_WIDTH:
            continue
        if left >= panel_left and right <= panel_right:
            continue
        found.append({
            "x": int(left),
            "right": int(right),
            "center_x": round((left + right) / 2, 1),
        })
    return found


def _title_from_ocr(ocr: Iterable[dict[str, Any]] | None) -> tuple[str | None, str | None]:
    """Return ``(matched_title, conflict)`` from caller-supplied OCR entries.

    Only boxes whose centre falls inside the lineup title region are inspected.
    Map names, opponent names and every other string are ignored by design, and
    a row without a usable box is skipped rather than guessed at.
    """
    if ocr is None:
        return None, None
    left, top, width, height = LINEUP_TITLE_ROI
    matched: str | None = None
    for row in ocr:
        if not isinstance(row, dict) or not row.get("text"):
            continue
        box = row.get("box")
        if not isinstance(box, Sequence) or len(box) < 4:
            continue
        bx, by, bw, bh = (float(value) for value in box[:4])
        center_x, center_y = bx + bw / 2, by + bh / 2
        if not (left <= center_x <= left + width and top <= center_y <= top + height):
            continue
        text = str(row["text"])
        if SELECTION_PAGE_TITLE in text:
            return matched, SELECTION_PAGE_TITLE
        for title in LINEUP_TITLES:
            if title in text:
                matched = title
    return matched, None


def _cells(slot: int, panel_left: int, panel_right: int) -> list[dict[str, Any]]:
    """Derived x-span of the five cells; geometry only, no navigation policy."""
    rows = []
    for index in range(1, 6):
        if index == slot:
            left, right = panel_left, panel_right
        elif index < slot:
            left = STRIP_LEFT + SLOT_PITCH * (index - 1)
            right = left + SLOT_PITCH - 1
        else:
            left = panel_right + 1 + SLOT_PITCH * (index - slot - 1)
            right = left + SLOT_PITCH - 1
        rows.append({"slot": index, "left": int(left), "right": int(right),
                     "expanded": index == slot})
    return rows


def observe_lineup_slot(frame: np.ndarray, *,
                        ocr: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Report the uniquely expanded slot of an open Duel lineup screenshot.

    ``frame`` must be a ``uint8`` BGR image already captured by the caller; OCR
    stays outside and may be handed in as normalised entries
    (``{"text": str, "box": [x, y, w, h]}``) that are used for the page-title
    guard only.  The result is a pure function of the arguments: the same input
    always yields the same output, and no global state is read or written.

    ``expanded_slot`` is ``1..5`` only when the frame is the five-slot lineup
    with exactly one expanded cell and every geometric cue agrees: the single
    expanded selection button, the expanded panel edge on the slot grid, and
    the collapsed-cell markers on their own grid.  Anything unclear - wrong
    size, no expanded cell, several candidates, an occluded or unreadable
    panel, markers off the cell grid, a mismatching page title - yields
    ``expanded_slot=None`` with ``slot_verified=False``.  There is no fallback
    to slot 1, and an expected slot can never be handed in.
    """
    image = _as_frame(frame)
    height, width = image.shape[:2]
    size = [width, height]

    if (width, height) != SUPPORTED_SIZE:
        return _result("not_lineup", None, REASON_UNSUPPORTED_SIZE, size=size,
                       supported=list(SUPPORTED_SIZE))

    title, conflict = _title_from_ocr(ocr)
    ocr_used = ocr is not None

    candidates = _button_candidates(image)
    if not candidates:
        return _result("not_lineup", None, REASON_NO_BUTTON, title=title,
                       ocr_used=ocr_used, size=size, button_candidates=0)
    if len(candidates) > 1:
        return _result("ambiguous", None, REASON_MULTIPLE_BUTTONS, title=title,
                       ocr_used=ocr_used, size=size,
                       button_candidates=len(candidates),
                       buttons=[row["box"] for row in candidates])

    button = candidates[0]
    profile = _strip_profile(image)
    run = _panel_run(profile, button)
    if run is None:
        return _result("not_lineup", None, REASON_PANEL_UNVERIFIED, title=title,
                       ocr_used=ocr_used, size=size, button=button)

    extension = run[1] - button["right"]
    if not PANEL_RIGHT_EXTENSION[0] <= extension <= PANEL_RIGHT_EXTENSION[1]:
        return _result("not_lineup", None, REASON_PANEL_UNVERIFIED, title=title,
                       ocr_used=ocr_used, size=size, button=button,
                       panel_bright_run=list(run), panel_extension=extension)

    slot_panel, panel_residual = _slot_from(
        float(run[1]), PANEL_RIGHT_BASE, SLOT_TOLERANCE)
    slot_button, button_residual = _slot_from(
        float(button["center_x"]), BUTTON_CENTER_BASE, BUTTON_TOLERANCE)
    if slot_panel is None or slot_button is None or slot_panel != slot_button:
        return _result("ambiguous", None, REASON_SLOT_CONFLICT, title=title,
                       ocr_used=ocr_used, size=size, button=button,
                       panel_bright_run=list(run), slot_from_panel=slot_panel,
                       slot_from_button=slot_button,
                       panel_residual=round(panel_residual, 1),
                       button_residual=round(button_residual, 1))

    slot = slot_panel
    panel_right = int(run[1])
    panel_left = panel_right - EXPANDED_WIDTH
    panel = {"left": panel_left, "right": panel_right}
    markers = _markers(profile, panel_left, panel_right)
    centers = _collapsed_centers(slot, float(panel_right))
    resolved = []
    used: set[int] = set()
    for marker in markers:
        best: tuple[float, int] | None = None
        for index, center in centers.items():
            if index in used:
                continue
            distance = abs(marker["center_x"] - center)
            if best is None or distance < best[0]:
                best = (distance, index)
        if best is None or best[0] > SLOT_TOLERANCE:
            return _result("ambiguous", None, REASON_MARKER_CONFLICT, title=title,
                           ocr_used=ocr_used, size=size, button=button,
                           panel=panel, collapsed_markers=markers,
                           collapsed_cell_centers={str(key): value
                                                   for key, value in centers.items()})
        used.add(best[1])
        resolved.append({**marker, "slot": best[1],
                         "offset": round(marker["center_x"] - centers[best[1]], 1)})

    if conflict is not None:
        return _result("not_lineup", None, REASON_TITLE_CONFLICT, title=conflict,
                       ocr_used=ocr_used, size=size, button=button,
                       panel=panel, slot_from_panel=slot)
    if ocr_used and title is None:
        return _result("ambiguous", None, REASON_TITLE_MISSING, title=None,
                       ocr_used=ocr_used, size=size, button=button,
                       panel=panel, slot_from_panel=slot)

    return _result(
        "duel_lineup", slot, REASON_VERIFIED, title=title, ocr_used=ocr_used,
        size=size,
        button=button,
        panel=panel,
        panel_bright_run=list(run),
        slot_from_panel=slot_panel,
        slot_from_button=slot_button,
        panel_residual=round(panel_residual, 1),
        button_residual=round(button_residual, 1),
        pitch=SLOT_PITCH,
        collapsed_markers=resolved,
        collapsed_markers_present=bool(resolved),
        collapsed_cell_centers={str(key): value for key, value in centers.items()},
        cells=_cells(slot, panel_left, panel_right),
    )
