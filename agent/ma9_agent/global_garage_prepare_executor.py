"""Narrow, evidence-gated click executor for the global-garage prepare flow (05AL-A).

Scope
-----
Five operating actions only -- ``open_filter`` (tap the filter funnel on the
garage list), ``toggle_owned`` (tap the ``已拥有`` checkbox on the filter
panel) and ``apply_filter`` (tap the lime ``完成`` button) -- and the session
must already start inside the global garage list. After filter verification,
``jump_d_section`` taps one fixed D shortcut and ``swipe_to_origin`` performs
bounded rightward drags inside the list. There is no entry navigation,
vehicle detail, unlock, star-up, car pick,
race start, inventory/account write, and no arbitrary-coordinate or node
interface.

This module owns no page reader, no planner and no sampler.  It consumes the
frozen planner's ``State`` :class:`~ma9_agent.global_garage_prepare_plan.State`
and :class:`~ma9_agent.global_garage_prepare_plan.Decision` plus one
caller-supplied ``Sample`` mapping (contract 05AL §"小接口") and returns a
fixed-key ``Outcome`` mapping.  It never mutates the planner, the screen
module, the observation adapter or the decision's authorisation fields.

Trust boundary -- recorded, never claimed as verified
----------------------------------------------------
* the ``Sample`` mapping is an in-process calling contract, not a
  cryptographic attestation: ``session_id``/``frame_id``/timestamps are
  validated but not proven, and the OCR list is *assumed* to belong to
  ``image`` (the observation adapter records the same caveat).  Old PNGs, a
  caller receipt or a cross-session mapping are therefore never trusted: the
  frame id must equal ``state.last_frame_id``, the observation must carry the
  same session/frame, and every control is re-measured here on the frame's own
  pixels;
* ``source`` is accepted only as ``mfa_context`` or ``fake``; a fake sample can
  drive the offline tests but the recorded evidence must never be reported as
  live input.

Calibration provenance (``captures/global_garage`` in the read-only root
workspace, measured 05AL-A; probes archived under
``MA9-evidence/20260930-05AL/A/tmp/``)

* filter funnel tile ``(1161, 87, 54, 53)`` -- the right-most tile of the
  class/icon row.  The row is byte-identical across all nine real garage-list
  frames; the tile is bright (mean gray 200.0 of a possible 255) and carries a
  dark glyph whose top row spans the full glyph width (measured 1.00) and whose
  widest row is its first (peak row 0 of 34), tapering to a 1 px stem.  Its
  neighbours fail: the six class letters have a top row of 0.03-0.06, the
  heart tile peaks at row 8-10 with a top row of 0.32 (the cleft between the
  lobes), and the ``R`` tile is narrower than the accepted glyph width band;
* ``完成`` button ``(58, 563, 303, 82)`` -- the lime fill of the filter panel
  (measured BGR ``(18.8, 247.2, 191.8)``, lime fraction 0.979 on *both* real
  panels against a maximum of 0.067 over every non-panel frame).  The label's
  whole OCR box ``[177, 586, 64, 37]`` lies inside the button, so the same
  frame must supply both the fill and exactly one label wholly inside the
  button. Labels outside that target ROI do not participate in uniqueness;
* the checkbox cell is the shared, already-calibrated ``CHECKBOX_ROI``
  ``(314, 188, 47, 48)``; this module re-reads its pixels and additionally
  demands an empty interior before it will accept an ``off`` verdict, and
  requires the ``已拥有`` label to be bound to the same row.

Timing and failure discipline (all values from the one injected monotonic
clock)

* absolute session deadline (exactly at the deadline is already too late), a
  3 s per-job ceiling clipped to that deadline, 0.02 s polling, and a frame age
  strictly below 3.0 s measured from ``capture_started_at`` to the moment before
  submission.  ``job.wait`` is never called and no in-flight native action is
  claimed to be cancellable;
* an attempt is registered for ``(session_id, action_id)`` *before*
  ``post_click``; a raised call, an invalid job id, a failing/unknown status or
  a timeout is never retried, and no receipt is fabricated.  The instance locks
  after any outcome other than ``succeeded`` and never opens or closes the
  MFA-owned controller.

Nothing here performs a device operation in the constructor, and nothing here
is a claim about the real MAA DLL or a live device: the offline tests exercise
an injected fake controller only.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Mapping, Sequence

import cv2
import numpy as np

from .global_garage_prepare_observation import ObserveResult, observe
from .global_garage_prepare_plan import (
    ACTION,
    APPLY_FILTER,
    ActionResult,
    Decision,
    FILTER_PANEL,
    GARAGE_LIST,
    OFF,
    ON,
    OPEN_FILTER,
    State,
    TOGGLE_OWNED,
    JUMP_D_SECTION,
    SWIPE_TO_ORIGIN,
    MAX_D_JUMPS,
    MAX_ORIGIN_SWIPES,
)
from .global_garage_screen import (
    CHECKBOX_ROI,
    PAGE_FILTER_PANEL,
    PAGE_GARAGE_LIST,
    classify_page,
    read_owned_filter,
)

#: Intents this executor will ever issue.
INTENTS = (OPEN_FILTER, TOGGLE_OWNED, APPLY_FILTER, JUMP_D_SECTION, SWIPE_TO_ORIGIN)
#: Sample provenance values accepted by this layer.
SUPPORTED_SOURCE = ("mfa_context", "fake")

#: Keys every Sample mapping must carry (contract 05AL §"小接口").
SAMPLE_KEYS = ("session_id", "frame_id", "capture_started_at", "captured_at",
               "image", "ocr", "observed", "source")

#: Poll interval, per-job ceiling and maximum accepted frame age.
POLL_S = 0.02
JOB_TIMEOUT_S = 3.0
MAX_FRAME_AGE_S = 3.0
# Fault containment if an injected clock/sleeper stops advancing. This is a
# poll limit, not evidence that native time has elapsed or a job was cancelled.
MAX_JOB_POLLS = math.ceil(JOB_TIMEOUT_S / POLL_S) + 2

#: Processed-frame contract of this layer (device stays 1920x1080).
FRAME_WIDTH, FRAME_HEIGHT = 1280, 720

#: Calibrated control regions on the native 1280x720 processed frame.
FILTER_BUTTON_ROI = (1161, 87, 54, 53)
DONE_BUTTON_ROI = (58, 563, 303, 82)
# Fixed top navigation tile; its D glyph may be dark or selected gray.
D_BUTTON_ROI = (732, 87, 54, 53)
# Both points lie inside the established first card row, away from the
# sidebar/header/bottom controls. Rightward drag moves toward global left.
LIST_SWIPE_ROI = (240, 250, 900, 150)
ORIGIN_SWIPE = (260, 360, 1100, 360, 350)  # SDK milliseconds; no manual scaling

#: Filter-tile structural gate (see module docstring for the measurements).
TILE_MIN_BRIGHTNESS = 170.0
TILE_INK_MAX_GRAY = 120
FILTER_GLYPH_WIDTH_FRACTION = (0.60, 0.88)
FILTER_GLYPH_HEIGHT_FRACTION = (0.45, 0.80)
FILTER_TOP_ROW_MIN = 0.90
FILTER_PEAK_ROW_MAX_FRACTION = 0.12
FILTER_STEM_MAX_FRACTION = 0.40
FILTER_BOTTOM_ROW_MAX = 0.20

#: Label/OCR gate shared by the two panel controls.
LABEL_MIN_CONFIDENCE = 0.85
OWNED_LABEL = "已拥有"
DONE_LABEL = "完成"
OWNED_LABEL_ROW_TOLERANCE = 8

#: ``完成`` button gate.
DONE_MIN_LIME_FRACTION = 0.45

#: Checkbox cell gate (A's own empty-interior guard for an ``off`` verdict).
CELL_MIN_STRUCTURE = 8.0
CELL_MIN_OUTLINE = 15.0
CELL_ON_MIN_GREEN = 0.35
CELL_OFF_MAX_GREEN = 0.08
CELL_BORDER_SKIP = 7
CELL_CORNER_SKIP = 4
CELL_INTERIOR_MAX_GRAY = 90
CELL_INTERIOR_MAX_STD = 8.0
CELL_INTERIOR_MAX_CHANNEL_DEVIATION = 8.0

_SUCCEEDED, _FAILED = "succeeded", "failed"
_BLOCKED, _TIMEOUT, _CANCELLED, _INDETERMINATE = "blocked", "timeout", "cancelled", "indeterminate"


# --------------------------------------------------------------------------- #
# small typed helpers
# --------------------------------------------------------------------------- #
def _top_d_button_evidence(image: np.ndarray) -> tuple[str | None, dict[str, Any]]:
    """Confirm only the fixed white navigation tile and its D topology.

    Relative contrast accepts the selected gray D without relaxing the shared
    badge reader. A straight full-height left stem and curved right edge
    distinguish D from a single-counter O; the tiny colored alert is excluded.
    This proves the control's pixels, not whether a selected tile is clickable.
    """
    x, y, w, h = D_BUTTON_ROI
    tile = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    # Absolute chroma tolerates the calibrated blue-gray dark ink, whose
    # HSV saturation is high solely because its intensity is low.
    neutral = np.ptp(tile.astype(np.int16), axis=2) <= 40
    white = neutral & (gray >= 230)
    # The established small colored alert occupies the top-right corner.
    borders = (white[:5, :36], white[-5:, :], white[:, :5], white[18:, -5:])
    background = float(np.median(gray))
    evidence = {"background_gray": background,
                "white_fraction": round(float(white.mean()), 3),
                "white_border_fractions": [round(float(b.mean()), 3) for b in borders]}
    if background < 230 or white.mean() < .60 or any(b.mean() < .80 for b in borders):
        return None, {**evidence, "letter": None, "reason": "white_tile_not_confirmed"}
    mask = (neutral & (gray < background - 65)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    parts = [i for i in range(1, count) if stats[i, 4] >= 20]
    evidence.update(parts=len(parts), ink_fraction=round(float(mask.mean()), 3),
                    contrast_threshold=background - 65)
    if len(parts) != 1:
        return None, {**evidence, "letter": None, "reason": "glyph_not_a_single_component"}
    i = parts[0]
    gx, gy, gw, gh, area = (int(v) for v in stats[i])
    evidence["glyph_box"] = [gx, gy, gw, gh]
    if not (9 <= gx <= 19 and 5 <= gy <= 14 and 22 <= gw <= 31
            and 29 <= gh <= 39 and .10 <= area / (w*h) <= .35):
        return None, {**evidence, "letter": None, "reason": "glyph_geometry_unsupported"}
    glyph = (labels == i).astype(np.uint8)
    n, _, holes, _ = cv2.connectedComponentsWithStats(1 - glyph, 8)
    enclosed = [a for a in holes[1:] if a[4] >= 12 and a[0] > 0 and a[1] > 0
                and a[0]+a[2] < w and a[1]+a[3] < h]
    evidence["counter_count"] = len(enclosed)
    if len(enclosed) != 1 or enclosed[0][3] / gh < .50:
        return None, {**evidence, "letter": None, "reason": "single_tall_counter_not_confirmed"}
    crop = glyph[gy:gy+gh, gx:gx+gw]
    left_stem = float(crop[:, :2].mean())
    right_edges = np.array([np.flatnonzero(row)[-1] for row in crop])
    mid_right = float(np.median(right_edges[gh//3:2*gh//3]))
    end_right = float(np.mean([right_edges[0], right_edges[-1]]))
    evidence.update(left_stem_fraction=round(left_stem, 3),
                    right_arc_depth=round(mid_right - end_right, 3),
                    hole_height_ratio=round(float(enclosed[0][3] / gh), 3))
    if left_stem < .90 or mid_right - end_right < 3:
        return None, {**evidence, "letter": None, "reason": "d_stem_and_arc_not_confirmed"}
    return "D", {**evidence, "letter": "D", "reason": "white_tile_and_d_topology_confirmed"}


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _roi_center(roi: Sequence[int]) -> tuple[int, int]:
    """Integer centre pixel of a validated region -- the only click target."""
    left, top, width, height = (int(v) for v in roi)
    return left + width // 2, top + height // 2


def _box_inside(box: Sequence[float], roi: Sequence[int]) -> bool:
    try:
        x, y, width, height = (float(v) for v in box)
    except (TypeError, ValueError):
        return False
    left, top = float(roi[0]), float(roi[1])
    right, bottom = left + float(roi[2]), top + float(roi[3])
    return left <= x and top <= y and x + width <= right and y + height <= bottom


def _sanitize_items(ocr: Iterable[Any] | None) -> tuple[list[dict[str, Any]], int]:
    """Keep only well-formed OCR items; count (never repair) the rejects.

    A label may only become evidence with a string text, a finite confidence in
    ``[0, 1]`` and a box of four finite values with positive extents inside the
    native frame; anything else is dropped, so a malformed or out-of-frame item
    can never be read as a control label.
    """
    items: list[dict[str, Any]] = []
    rejected = 0
    for raw in (ocr or []):
        if not isinstance(raw, dict):
            rejected += 1
            continue
        text = raw.get("text")
        confidence = raw.get("confidence")
        box = raw.get("box")
        if not isinstance(text, str) or not _finite_number(confidence):
            rejected += 1
            continue
        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            rejected += 1
            continue
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            rejected += 1
            continue
        if any(not _finite_number(v) for v in box):
            rejected += 1
            continue
        x, y, width, height = (float(v) for v in box)
        if (width <= 0 or height <= 0 or x < 0 or y < 0
                or x + width > FRAME_WIDTH or y + height > FRAME_HEIGHT):
            rejected += 1
            continue
        items.append({"text": text, "confidence": confidence,
                      "box": [x, y, width, height]})
    return items, rejected


def _matching_labels(items: Iterable[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    return [item for item in items
            if item["text"].strip() == text and item["confidence"] >= LABEL_MIN_CONFIDENCE]


def _label_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {"text": item["text"], "confidence": round(item["confidence"], 4),
            "box": [round(float(v), 1) for v in item["box"]]}


# --------------------------------------------------------------------------- #
# pixel gates (A's own calibration, no shared recogniser is modified)
# --------------------------------------------------------------------------- #
def _filter_button_evidence(frame: np.ndarray) -> tuple[bool, str, dict[str, Any]]:
    """Structural proof that the filter funnel occupies the calibrated tile.

    A bright tile alone is not enough -- the heart and the six class letters sit
    in equally bright tiles.  The accepted glyph is the only one that is
    widest on its first row (a flat, full-width mouth), tapers monotonically to
    a narrow stem and ends almost closed.
    """
    left, top, width, height = FILTER_BUTTON_ROI
    tile = frame[top:top + height, left:left + width]
    gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    ink = (gray < TILE_INK_MAX_GRAY).astype(np.uint8)
    rows = ink.sum(axis=1)
    cols = ink.sum(axis=0)
    evidence: dict[str, Any] = {"roi": list(FILTER_BUTTON_ROI),
                                "tile_brightness": round(brightness, 1)}
    ys = np.nonzero(rows)[0]
    xs = np.nonzero(cols)[0]
    if ys.size == 0 or xs.size == 0:
        return False, "filter_button_mark_missing", evidence
    gy0, gy1 = int(ys[0]), int(ys[-1])
    gx0, gx1 = int(xs[0]), int(xs[-1])
    glyph_width = gx1 - gx0 + 1
    glyph_height = gy1 - gy0 + 1
    sub = ink[gy0:gy1 + 1, gx0:gx1 + 1]
    row_width = sub.sum(axis=1).astype(np.float64)
    evidence.update({
        "glyph_box": [gx0, gy0, glyph_width, glyph_height],
        "ink_fraction": round(float(ink.mean()), 3),
        "top_row_fraction": round(float(row_width[0]) / glyph_width, 3),
        "peak_row": int(np.argmax(row_width)),
        "stem_fraction": round(float(row_width[int(glyph_height * 0.7)]) / glyph_width, 3),
        "bottom_row_fraction": round(float(row_width[-1]) / glyph_width, 3),
    })
    if brightness < TILE_MIN_BRIGHTNESS:
        return False, "filter_button_tile_not_bright", evidence
    if not (FILTER_GLYPH_WIDTH_FRACTION[0] <= glyph_width / width
            <= FILTER_GLYPH_WIDTH_FRACTION[1]):
        return False, "filter_button_glyph_width_unsupported", evidence
    if not (FILTER_GLYPH_HEIGHT_FRACTION[0] <= glyph_height / height
            <= FILTER_GLYPH_HEIGHT_FRACTION[1]):
        return False, "filter_button_glyph_height_unsupported", evidence
    if evidence["top_row_fraction"] < FILTER_TOP_ROW_MIN:
        return False, "filter_button_top_not_flat", evidence
    if evidence["peak_row"] > max(1, int(glyph_height * FILTER_PEAK_ROW_MAX_FRACTION)):
        return False, "filter_button_peak_not_at_top", evidence
    if evidence["stem_fraction"] > FILTER_STEM_MAX_FRACTION:
        return False, "filter_button_not_tapered", evidence
    if evidence["bottom_row_fraction"] > FILTER_BOTTOM_ROW_MAX:
        return False, "filter_button_bottom_not_narrow", evidence
    return True, "filter_button_funnel_confirmed", evidence


def _done_button_evidence(frame: np.ndarray,
                          items: list[dict[str, Any]]) -> tuple[bool, str, dict[str, Any]]:
    """Lime fill plus one same-frame ``完成`` label wholly inside the button."""
    left, top, width, height = DONE_BUTTON_ROI
    patch = frame[top:top + height, left:left + width]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    lime = ((hsv[:, :, 0] >= 25) & (hsv[:, :, 0] <= 45)
            & (hsv[:, :, 1] >= 150) & (hsv[:, :, 2] >= 180))
    labels = _matching_labels(items, DONE_LABEL)
    evidence: dict[str, Any] = {
        "roi": list(DONE_BUTTON_ROI),
        "lime_fraction": round(float(lime.mean()), 3),
        "aspect": round(width / height, 2),
        "mean_bgr": [round(float(v), 1) for v in patch.reshape(-1, 3).mean(axis=0)],
        "labels": [_label_evidence(item) for item in labels],
        "label_uniqueness_scope": "target_button_roi",
    }
    bound = [item for item in labels if _box_inside(item["box"], DONE_BUTTON_ROI)]
    evidence["labels_bound"] = len(bound)
    if evidence["lime_fraction"] < DONE_MIN_LIME_FRACTION:
        return False, "done_button_fill_not_confirmed", evidence
    if not bound:
        return False, "done_button_label_not_bound", evidence
    if len(bound) != 1:
        return False, "done_button_label_ambiguous", evidence
    return True, "done_button_lime_fill_and_label_confirmed", evidence


def _cell_evidence(frame: np.ndarray) -> dict[str, Any]:
    """A's own read of the ``已拥有`` cell, including an empty-interior guard."""
    left, top, width, height = CHECKBOX_ROI
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
    colours = patch[CELL_BORDER_SKIP:-CELL_BORDER_SKIP,
                    CELL_BORDER_SKIP:-CELL_BORDER_SKIP][mask].astype(np.float32)
    deviation = (float(np.abs(colours - np.median(colours, axis=0)).max())
                 if colours.size else 255.0)
    empty = (interior_max <= CELL_INTERIOR_MAX_GRAY
             and interior_std <= CELL_INTERIOR_MAX_STD
             and deviation <= CELL_INTERIOR_MAX_CHANNEL_DEVIATION)
    return {"roi": list(CHECKBOX_ROI),
            "structure": round(structure, 1),
            "green_fraction": round(fraction, 3),
            "outline_gap": round(outline_gap, 1),
            "interior_max_gray": round(interior_max, 1),
            "interior_std": round(interior_std, 1),
            "interior_channel_deviation": round(deviation, 1),
            "interior_empty": bool(empty)}


def _owned_state_evidence(frame: np.ndarray,
                          items: list[dict[str, Any]]) -> tuple[str | None, str, dict[str, Any]]:
    """Derive ``on``/``off``/unknown for the checkbox and prove the label binding."""
    left, top, width, height = CHECKBOX_ROI
    row_center = top + height // 2
    labels = _matching_labels(items, OWNED_LABEL)
    bound = [item for item in labels
             if item["box"][0] + item["box"][2] <= left
             and abs((item["box"][1] + item["box"][3] / 2) - row_center)
             <= OWNED_LABEL_ROW_TOLERANCE]
    reader = read_owned_filter(frame, None)
    cell = _cell_evidence(frame)
    evidence = {"roi": list(CHECKBOX_ROI), "labels": [_label_evidence(i) for i in labels],
                "labels_bound": len(bound), "cell": cell,
                "reader": {"state": reader.get("state"), "page": reader.get("page"),
                           "green_fraction": reader.get("green_fraction"),
                           "structure": reader.get("structure"),
                           "outline_gap": reader.get("outline_gap"),
                           "reasons": reader.get("reasons")}}
    if not bound:
        return None, "owned_label_not_bound_to_checkbox", evidence
    state = reader.get("state")
    if state == ON:
        if cell["green_fraction"] >= CELL_ON_MIN_GREEN:
            return ON, "owned_on_confirmed", evidence
        return None, "owned_on_not_confirmed_by_pixels", evidence
    if state == OFF:
        if (cell["interior_empty"] and cell["green_fraction"] <= CELL_OFF_MAX_GREEN
                and cell["outline_gap"] >= CELL_MIN_OUTLINE
                and cell["structure"] >= CELL_MIN_STRUCTURE):
            return OFF, "owned_off_confirmed", evidence
        return None, "owned_off_interior_not_confirmed", evidence
    return None, "owned_state_unknown", evidence


# --------------------------------------------------------------------------- #
# executor
# --------------------------------------------------------------------------- #
class ClickExecutor:
    """One single-session click executor; the constructor performs no I/O.

    Args:
        controller: an already-connected MAA controller.  Only ``post_click``
            is ever called on it; it is never opened, closed or force-killed.
        session_id: the session this instance is bound to.
        deadline: absolute monotonic deadline (``started_at + 30`` upstream).
        monotonic: the one injected monotonic clock for every timing value.
        sleep: injected sleeper used for the bounded poll.
        cancelled: ``() -> bool`` operator cancellation flag.
    """

    def __init__(self, controller: Any, *, session_id: str, deadline: float,
                 monotonic: Callable[[], float], sleep: Callable[[float], None],
                 cancelled: Callable[[], bool]) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not _finite_number(deadline):
            raise ValueError("deadline must be a finite number")
        for name, value in (("monotonic", monotonic), ("sleep", sleep),
                            ("cancelled", cancelled)):
            if not callable(value):
                raise ValueError(f"{name} must be callable")
        self._controller = controller
        self._session_id = session_id
        self._deadline = float(deadline)
        self._monotonic = monotonic
        self._sleep = sleep
        self._cancelled = cancelled
        self._attempted: set[tuple[str, int]] = set()
        self._in_flight = False
        self._stopped = False
        self._stop_reason: str | None = None
        #: Append-only audit of every real ``post_click`` entered (tests read it).
        self.calls: list[dict[str, Any]] = []
        #: Append-only audit of every rejected/gated decision (no device input).
        self.rejections: list[dict[str, Any]] = []

    # -- audit helpers ------------------------------------------------------ #
    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def stop_reason(self) -> str | None:
        return self._stop_reason

    def _lock(self, reason: str) -> None:
        if not self._stopped:
            self._stopped = True
            self._stop_reason = reason

    def _outcome(self, status: str, reason: str, *, action_id: int | None = None,
                 intent: str | None = None, issued: bool = False,
                 job_id: int | None = None, job_status: str | None = None,
                 submitted_at: float | None = None, completed_at: float | None = None,
                 receipt: ActionResult | None = None,
                 pre_frame_id: int = -1) -> dict[str, Any]:
        return {"status": status, "reason": reason, "session_id": self._session_id,
                "action_id": action_id, "intent": intent, "issued": bool(issued),
                "job_id": job_id, "job_status": job_status,
                "submitted_at": submitted_at, "completed_at": completed_at,
                "receipt": receipt, "pre_frame_id": pre_frame_id}

    def _stop(self, status: str, reason: str, **kwargs: Any) -> dict[str, Any]:
        """Every outcome except a real success locks the instance for good."""
        self._lock(reason)
        self.rejections.append({"status": status, "reason": reason,
                                "action_id": kwargs.get("action_id"),
                                "intent": kwargs.get("intent")})
        return self._outcome(status, reason, **kwargs)

    # -- entry point -------------------------------------------------------- #
    def execute(self, state: Any, decision: Any, sample: Any) -> Mapping[str, Any]:
        """Verify one issued decision against its own frame, then click once."""
        if self._stopped:
            return self._outcome(_BLOCKED, f"adapter_stopped:{self._stop_reason}")

        if not isinstance(state, State):
            return self._stop(_BLOCKED, "invalid_state")
        if not isinstance(decision, Decision):
            return self._stop(_BLOCKED, "invalid_decision")
        if not isinstance(sample, Mapping):
            return self._stop(_BLOCKED, "invalid_sample")
        missing = [key for key in SAMPLE_KEYS if key not in sample]
        if missing:
            return self._stop(_BLOCKED, "sample_missing_keys:" + ",".join(missing))

        if state.session_id != self._session_id:
            return self._stop(_BLOCKED, "state_session_mismatch")
        if sample["session_id"] != self._session_id:
            return self._stop(_BLOCKED, "sample_session_mismatch")

        if decision.kind != ACTION:
            return self._stop(_BLOCKED, f"decision_not_action:{decision.kind}")
        if decision.executable is not False:
            # A Decision that claims its own executability is outside the frozen
            # contract; authority here comes from this layer, never from the flag.
            return self._stop(_BLOCKED, "decision_authorization_tampered")
        intent = decision.intent
        if intent not in INTENTS:
            return self._stop(_BLOCKED, f"intent_not_whitelisted:{intent}")
        action_id = decision.action_id
        if not _plain_int(action_id) or action_id < 0:
            return self._stop(_BLOCKED, "malformed_action_id", intent=intent)
        if state.pending_action_id != action_id or state.pending_intent != intent:
            return self._stop(_BLOCKED, "no_matching_pending_action",
                              action_id=action_id, intent=intent)

        # -- sample shape -------------------------------------------------- #
        frame_id = sample["frame_id"]
        if not _plain_int(frame_id) or frame_id < 0:
            return self._stop(_BLOCKED, "malformed_sample_frame_id",
                              action_id=action_id, intent=intent)
        pre_frame_id = int(frame_id)
        image = sample["image"]
        if (not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3
                or image.dtype != np.uint8
                or (image.shape[1], image.shape[0]) != (FRAME_WIDTH, FRAME_HEIGHT)):
            return self._stop(_BLOCKED, "unsupported_processed_frame",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        observed = sample["observed"]
        if not isinstance(observed, ObserveResult):
            return self._stop(_BLOCKED, "invalid_observed_result",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        observation = observed.observation
        if (observation.session_id != self._session_id
                or observation.frame_id != frame_id
                or observed.observation.frame_id != frame_id):
            return self._stop(_BLOCKED, "observed_not_bound_to_sample",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if state.last_frame_id != frame_id:
            return self._stop(_BLOCKED, "sample_frame_not_current",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        source = sample["source"]
        if source not in SUPPORTED_SOURCE:
            return self._stop(_BLOCKED, f"invalid_sample_source:{source!r}",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if not isinstance(sample["ocr"], list):
            return self._stop(_BLOCKED, "invalid_sample_ocr",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)

        # -- dedup / re-entrancy ------------------------------------------- #
        key = (self._session_id, action_id)
        if self._in_flight:
            return self._stop(_BLOCKED, "concurrent_action_in_flight",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if key in self._attempted:
            return self._stop(_BLOCKED, "duplicate_action_attempt",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)

        # -- clock / cancellation ------------------------------------------ #
        if self._cancelled():
            return self._stop(_CANCELLED, "cancelled_before_submit",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        now = self._monotonic()
        if not _finite_number(now) or now < 0:
            return self._stop(_BLOCKED, "invalid_clock",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if now < state.last_now:
            return self._stop(_BLOCKED, "clock_regressed_before_submit",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if now >= self._deadline:
            return self._stop(_BLOCKED, "deadline_reached_before_submit",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)

        started_at = sample["capture_started_at"]
        captured_at = sample["captured_at"]
        if not _finite_number(started_at) or not _finite_number(captured_at):
            return self._stop(_BLOCKED, "invalid_sample_time",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        started_at, captured_at = float(started_at), float(captured_at)
        if started_at > captured_at or captured_at > now:
            return self._stop(_BLOCKED, "inconsistent_sample_time",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)
        if now - started_at >= MAX_FRAME_AGE_S:
            return self._stop(_BLOCKED, "frame_stale",
                              action_id=action_id, intent=intent,
                              pre_frame_id=pre_frame_id)

        # -- control gate (re-measured on this frame's own pixels) --------- #
        gate_ok, gate_reason, gate_evidence = self._gate(intent, state, image,
                                                         sample["ocr"], observation)
        if not gate_ok:
            self.rejections.append({"status": _BLOCKED, "reason": gate_reason,
                                    "action_id": action_id, "intent": intent,
                                    "evidence": gate_evidence})
            return self._stop(_BLOCKED, gate_reason, action_id=action_id,
                              intent=intent, pre_frame_id=pre_frame_id)
        target = _roi_center(gate_evidence["target_roi"])

        # -- submit --------------------------------------------------------- #
        # Register the attempt BEFORE the call: a raised call, a failing job or a
        # timeout is never retried, and no second post can be issued meanwhile.
        self._attempted.add(key)
        self._in_flight = True
        try:
            if self._cancelled():
                return self._stop(_CANCELLED, "cancelled_before_submit",
                                  action_id=action_id, intent=intent,
                                  pre_frame_id=pre_frame_id)
            submitted_at = self._monotonic()
            if (not _finite_number(submitted_at) or submitted_at < 0
                    or submitted_at >= self._deadline):
                return self._stop(_BLOCKED, "deadline_reached_before_submit",
                                  action_id=action_id, intent=intent,
                                  pre_frame_id=pre_frame_id)
            if submitted_at < now:
                return self._stop(_BLOCKED, "clock_regressed_before_submit",
                                  action_id=action_id, intent=intent,
                                  pre_frame_id=pre_frame_id)
            if submitted_at - started_at >= MAX_FRAME_AGE_S:
                return self._stop(_BLOCKED, "frame_stale",
                                  action_id=action_id, intent=intent,
                                  pre_frame_id=pre_frame_id)
            record = {"session_id": self._session_id, "action_id": action_id,
                      "intent": intent, "x": target[0], "y": target[1],
                      "submitted_at": submitted_at, "source": source,
                      "target_roi": list(gate_evidence["target_roi"]),
                      "result": "pending"}
            operation = "post_swipe" if intent == SWIPE_TO_ORIGIN else "post_click"
            record["operation"] = operation
            if intent == SWIPE_TO_ORIGIN:
                record.update(x=ORIGIN_SWIPE[0], y=ORIGIN_SWIPE[1],
                              end_x=ORIGIN_SWIPE[2], end_y=ORIGIN_SWIPE[3],
                              duration_ms=ORIGIN_SWIPE[4])
            self.calls.append(record)
            try:
                if intent == SWIPE_TO_ORIGIN:
                    job = self._controller.post_swipe(*ORIGIN_SWIPE)
                else:
                    job = self._controller.post_click(target[0], target[1])
            except Exception as error:                       # noqa: BLE001 - audited
                record["result"] = "raised"
                record["error"] = type(error).__name__
                return self._stop(_INDETERMINATE,
                                  f"{operation}_raised:{type(error).__name__}",
                                  action_id=action_id, intent=intent, issued=True,
                                  submitted_at=submitted_at,
                                  pre_frame_id=pre_frame_id)
            job_id = getattr(job, "job_id", None)
            if not _plain_int(job_id) or job_id <= 0:
                record["result"] = "invalid_job_id"
                return self._stop(_INDETERMINATE, "invalid_job_id",
                                  action_id=action_id, intent=intent, issued=True,
                                  submitted_at=submitted_at,
                                  pre_frame_id=pre_frame_id)
            record["job_id"] = job_id
            outcome = self._await(job, job_id, action_id, intent, submitted_at,
                                  pre_frame_id)
            record["result"] = outcome["status"]
            return outcome
        finally:
            self._in_flight = False

    # -- gate --------------------------------------------------------------- #
    def _gate(self, intent: str, state: State, image: np.ndarray,
              ocr: Any, observation: Any) -> tuple[bool, str, dict[str, Any]]:
        """Intent-specific verification of this frame; returns (ok, reason, evidence)."""
        items, rejected = _sanitize_items(ocr)
        if intent in (JUMP_D_SECTION, SWIPE_TO_ORIGIN):
            if (state.phase != "await_navigation_receipt" or state.open_purpose != "verify"
                    or state.toggle_target != ON or state.commit_kind != ON):
                return False, "navigation_outside_verified_filter_phase", {}
            if (not _plain_int(state.d_jumps_used) or not _plain_int(state.origin_swipes_used)
                    or not 1 <= state.d_jumps_used <= MAX_D_JUMPS
                    or not 0 <= state.origin_swipes_used <= MAX_ORIGIN_SWIPES
                    or (intent == SWIPE_TO_ORIGIN and state.origin_swipes_used < 1)
                    or (intent == JUMP_D_SECTION and state.origin_swipes_used != 0)):
                return False, "navigation_counter_invalid", {}
            if observation.page != GARAGE_LIST or observation.at_d_start is not False:
                return False, "navigation_requires_garage_non_start", {}
            measured = observe(image, items, session_id=observation.session_id,
                               frame_id=observation.frame_id)
            if measured.observation.page != GARAGE_LIST or measured.observation.at_d_start is not False:
                return False, "navigation_non_start_not_confirmed_by_pixels", {}
            ok, reason, evidence = _filter_button_evidence(image)
            if not ok:
                return False, reason, evidence
            x, y, w, h = D_BUTTON_ROI
            tile_mean = float(cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY).mean())
            letter, glyph = _top_d_button_evidence(image)
            evidence.update(d_button_brightness=tile_mean, d_button_glyph=glyph,
                            non_start_evidence=measured.diagnostics.get("at_d_start"),
                            target_roi=list(D_BUTTON_ROI if intent == JUMP_D_SECTION else LIST_SWIPE_ROI))
            if tile_mean < TILE_MIN_BRIGHTNESS or letter != "D":
                return False, "top_d_button_not_confirmed", evidence
            return True, "garage_navigation_controls_confirmed", evidence
        if intent == OPEN_FILTER:
            classified = classify_page(image)
            if observation.page != GARAGE_LIST:
                return False, "observation_page_not_garage_list", {
                    "observation_page": observation.page}
            if classified.get("page") != PAGE_GARAGE_LIST:
                return False, "frame_not_garage_list", {"classified": classified.get("page")}
            ok, reason, evidence = _filter_button_evidence(image)
            evidence["ocr_items_rejected"] = rejected
            evidence["target_roi"] = list(FILTER_BUTTON_ROI)
            return ok, reason, evidence

        if intent in (TOGGLE_OWNED, APPLY_FILTER):
            if observation.page != FILTER_PANEL:
                return False, "observation_page_not_filter_panel", {
                    "observation_page": observation.page}
            if observation.other_filters_clear is not True:
                return False, "other_filters_not_clear", {
                    "other_filters_clear": observation.other_filters_clear}
            # Reuse the calibrated adapter on the supplied pixels/OCR rather
            # than treating a caller's clear=True as a second visual anchor.
            panel = observe(image, items, session_id=observation.session_id,
                            frame_id=observation.frame_id)
            if panel.observation.page != FILTER_PANEL:
                return False, "frame_not_filter_panel", {}
            if panel.observation.other_filters_clear is not True:
                return False, "other_filters_not_confirmed_by_pixels", {
                    "other_filters_clear": panel.observation.other_filters_clear}
            owned_state, owned_reason, owned_evidence = _owned_state_evidence(image, items)
            owned_evidence["ocr_items_rejected"] = rejected
            owned_evidence["observed_owned"] = observation.owned_filter
            if owned_state is None:
                return False, owned_reason, owned_evidence
            if owned_state != observation.owned_filter:
                return False, "observed_owned_not_confirmed_by_pixels", owned_evidence
            if intent == TOGGLE_OWNED:
                if state.toggle_target not in (ON, OFF):
                    return False, "toggle_target_not_set", owned_evidence
                if owned_state == state.toggle_target:
                    return False, "toggle_target_not_opposite", owned_evidence
                owned_evidence["target_roi"] = list(CHECKBOX_ROI)
                owned_evidence["owned_state"] = owned_state
                return True, "toggle_owned_checkbox_confirmed", owned_evidence

            ok, reason, evidence = _done_button_evidence(image, items)
            evidence.update(owned_evidence)
            if state.toggle_target not in (ON, OFF):
                return False, "toggle_target_not_set", evidence
            if owned_state != state.toggle_target:
                return False, "submit_owned_not_matching_commit", evidence
            if not ok:
                return False, reason, evidence
            evidence["target_roi"] = list(DONE_BUTTON_ROI)
            evidence["owned_state"] = owned_state
            return True, "apply_filter_done_button_confirmed", evidence

        return False, "intent_not_whitelisted", {"intent": intent}

    # -- bounded wait ------------------------------------------------------- #
    def _await(self, job: Any, job_id: int, action_id: int, intent: str,
               submitted_at: float, pre_frame_id: int) -> dict[str, Any]:
        """Poll a real job under the strict deadlines; never call ``wait``.

        A terminal status observed at or after the deadline is late: it is
        audited (``job_id``/``job_status``/``completed_at``) but the outcome is
        ``timeout`` and no receipt is emitted, so the caller cannot drive the
        planner from it.
        """
        job_deadline = min(self._deadline, submitted_at + JOB_TIMEOUT_S)
        last_now = submitted_at
        for _poll in range(MAX_JOB_POLLS):
            if self._cancelled():
                return self._stop(_CANCELLED, "cancelled_during_job_wait",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, job_status="pending",
                                  submitted_at=submitted_at, pre_frame_id=pre_frame_id)
            now = self._monotonic()
            if not _finite_number(now) or now < 0:
                return self._stop(_INDETERMINATE, "invalid_clock_during_job_wait",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, submitted_at=submitted_at,
                                  pre_frame_id=pre_frame_id)
            if now < last_now:
                return self._stop(_INDETERMINATE, "clock_regressed_during_job_wait",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, submitted_at=submitted_at,
                                  pre_frame_id=pre_frame_id)
            last_now = now
            if now >= job_deadline or now >= self._deadline:
                # Exactly at the deadline is already too late; audit, never resume.
                late_status = self._read_status(job)
                return self._stop(_TIMEOUT, "job_not_completed_within_deadline",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, job_status=late_status or "unknown",
                                  submitted_at=submitted_at, completed_at=now,
                                  pre_frame_id=pre_frame_id)
            status = self._read_status(job)
            if status is None:
                return self._stop(_INDETERMINATE, "job_status_unreadable",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, submitted_at=submitted_at,
                                  pre_frame_id=pre_frame_id)
            if status == "terminal_unknown":
                return self._stop(_INDETERMINATE, "job_status_anomalous",
                                  action_id=action_id, intent=intent, issued=True,
                                  job_id=job_id, job_status="terminal_unknown",
                                  submitted_at=submitted_at, pre_frame_id=pre_frame_id)
            if status in (_SUCCEEDED, _FAILED):
                receipt = ActionResult(session_id=self._session_id,
                                       action_id=action_id,
                                       ok=status == _SUCCEEDED)
                return self._outcome(status, f"job_{status}",
                                     action_id=action_id, intent=intent, issued=True,
                                     job_id=job_id, job_status=status,
                                     submitted_at=submitted_at,
                                     completed_at=now, receipt=receipt,
                                     pre_frame_id=pre_frame_id)
            self._sleep(POLL_S)
        return self._stop(_INDETERMINATE, "job_poll_budget_exhausted",
                          action_id=action_id, intent=intent, issued=True,
                          job_id=job_id, submitted_at=submitted_at,
                          pre_frame_id=pre_frame_id)

    @staticmethod
    def _read_status(job: Any) -> str | None:
        """Read one job status sample; ``None`` means the query itself failed.

        The real v5.13.0 ``Job.status`` returns a ``Status`` whose ``done`` is
        the disjunction of ``succeeded``/``failed``; a handle that reports
        ``done`` while being neither is anomalous and must not be read as a
        success.
        """
        try:
            status = job.status
        except Exception:                                    # noqa: BLE001 - audited
            return None
        if status is None:
            return None
        try:
            succeeded = bool(status.succeeded)
            failed = bool(status.failed)
            done = bool(status.done)
        except Exception:                                    # noqa: BLE001 - audited
            return None
        if succeeded and failed:
            return "terminal_unknown"
        if succeeded:
            return _SUCCEEDED
        if failed:
            return _FAILED
        if done:
            return "terminal_unknown"
        return "running"


__all__ = [
    "ClickExecutor", "INTENTS", "SAMPLE_KEYS", "SUPPORTED_SOURCE",
    "POLL_S", "JOB_TIMEOUT_S", "MAX_FRAME_AGE_S",
    "FRAME_WIDTH", "FRAME_HEIGHT", "FILTER_BUTTON_ROI", "DONE_BUTTON_ROI",
    "CHECKBOX_ROI",
    "D_BUTTON_ROI", "LIST_SWIPE_ROI", "ORIGIN_SWIPE",
]
